from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_customer, require_same_origin
from app.models import AuditLog, NotificationLog, NotificationPreference, User

router = APIRouter(prefix="/api/v1/customer/notification-preferences", tags=["notifications"])


class PreferenceUpdate(BaseModel):
    whatsapp_order_updates: bool
    whatsapp_marketing: bool
    language: str


class PreferenceView(PreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)


def _get_or_create(customer_id, db: Session) -> NotificationPreference:
    preference = db.get(NotificationPreference, customer_id)
    if preference is None:
        preference = NotificationPreference(customer_id=customer_id, language="en")
        db.add(preference)
        db.flush()
    return preference


@router.get("", response_model=PreferenceView)
def get_preferences(user: User = Depends(require_customer), db: Session = Depends(get_db)) -> PreferenceView:
    preference = db.get(NotificationPreference, user.customer.id)
    if preference is None:
        return PreferenceView(whatsapp_order_updates=False, whatsapp_marketing=False, language=user.customer.preferred_language)
    return PreferenceView.model_validate(preference)


@router.put("", response_model=PreferenceView, dependencies=[Depends(require_same_origin)])
def update_preferences(
    payload: PreferenceUpdate,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    if payload.language not in {"en", "te"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Choose English or Telugu")
    preference = _get_or_create(user.customer.id, db)
    preference.whatsapp_order_updates = payload.whatsapp_order_updates
    preference.whatsapp_marketing = payload.whatsapp_marketing
    preference.language = payload.language
    user.customer.preferred_language = payload.language
    if not payload.whatsapp_order_updates:
        db.execute(
            update(NotificationLog)
            .where(
                NotificationLog.customer_id == user.customer.id,
                NotificationLog.channel == "whatsapp",
                NotificationLog.provider_state == "manual_required",
            )
            .values(provider_state="obsolete")
        )
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="customer.notification_preferences.updated",
            entity_type="customer",
            entity_id=user.customer.id,
            before_after_summary={
                "whatsapp_order_updates": payload.whatsapp_order_updates,
                "whatsapp_marketing": payload.whatsapp_marketing,
                "language": payload.language,
            },
        )
    )
    db.commit()
    db.refresh(preference)
    return preference

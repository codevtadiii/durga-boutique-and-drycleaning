from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_permission, require_same_origin
from app.models import AuditLog, NotificationLog, User

router = APIRouter(prefix="/api/v1/staff/notifications", tags=["notifications"])


@router.get("")
def notification_queue(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("notification:read")),
) -> list[dict]:
    rows = db.scalars(
        select(NotificationLog)
        .options(selectinload(NotificationLog.order))
        .order_by(NotificationLog.created_at.desc())
        .limit(300)
    )
    return [
        {
            "id": str(item.id),
            "order_id": str(item.order_id) if item.order_id else None,
            "order_number": item.order.order_number if item.order else None,
            "event_type": item.event_type,
            "channel": item.channel,
            "state": item.provider_state,
            "created_at": item.created_at.isoformat(),
        }
        for item in rows
    ]


@router.post("/{notification_id}/manual-sent", dependencies=[Depends(require_same_origin)])
def mark_manual_message_sent(
    notification_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("notification:send")),
) -> dict[str, str]:
    notification = db.scalar(
        select(NotificationLog).where(NotificationLog.id == notification_id).with_for_update()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification was not found")
    if notification.channel != "whatsapp" or notification.provider_state != "manual_required":
        raise HTTPException(status_code=409, detail="This notification is not waiting for manual WhatsApp sending")
    notification.provider_state = "manually_sent"
    notification.handled_by_user_id = actor.id
    notification.handled_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="notification.manually_sent",
            entity_type="notification",
            entity_id=notification.id,
            before_after_summary={"provider_state": "manually_sent"},
        )
    )
    db.commit()
    return {"state": "manually_sent", "message": "Staff marked the WhatsApp message as sent. Delivery was not independently confirmed."}

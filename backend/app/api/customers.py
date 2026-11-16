from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import normalize_phone
from app.api.deps import get_current_user, get_db, require_customer, require_permission, require_same_origin
from app.api.schemas import CustomerCreateInput, CustomerProfile, PinResetInput, RegistrationApproveInput, RegistrationRequestView
from app.core.security import hash_secret, new_qr_secret, password_hash
from app.models import (
    AuditLog,
    Customer,
    CustomerQrToken,
    NotificationPreference,
    RegistrationRequest,
    User,
)

customer_router = APIRouter(prefix="/api/v1/customer", tags=["customers"])
staff_router = APIRouter(prefix="/api/v1/staff", tags=["staff customers"])


@staff_router.get("/customers")
def search_customers(
    query: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("customer:read")),
) -> list[dict[str, str]]:
    term = query.strip()
    if len(term) < 2 or len(term) > 120:
        raise HTTPException(status_code=422, detail="Enter at least two characters to search")
    rows = db.execute(
        select(Customer, User.phone)
        .join(User, User.id == Customer.user_id)
        .where(or_(Customer.full_name.ilike(f"%{term}%"), User.phone.ilike(f"%{term}%")))
        .order_by(Customer.full_name)
        .limit(50)
    )
    return [
        {"id": str(customer.id), "full_name": customer.full_name, "phone": phone, "preferred_language": customer.preferred_language}
        for customer, phone in rows
    ]


@staff_router.get("/registration-requests", response_model=list[RegistrationRequestView])
def list_registration_requests(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("customer:read")),
) -> list[RegistrationRequest]:
    return list(
        db.scalars(
            select(RegistrationRequest).where(RegistrationRequest.status == "pending").order_by(RegistrationRequest.created_at)
        )
    )


@staff_router.post("/registration-requests/{request_id}/approve", response_model=CustomerProfile)
def approve_registration(
    request_id: UUID,
    payload: RegistrationApproveInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customer:create")),
    _: None = Depends(require_same_origin),
) -> Customer:
    registration = db.get(RegistrationRequest, request_id)
    if registration is None or registration.status != "pending":
        raise HTTPException(status_code=404, detail="Registration request was not found")
    if db.scalar(select(User.id).where(User.phone == registration.phone)):
        raise HTTPException(status_code=409, detail="A profile already uses this mobile number")

    user = User(
        phone=registration.phone,
        pin_hash=password_hash.hash(payload.pin),
        account_type="customer",
        phone_verified_at=datetime.now(timezone.utc),
    )
    customer = Customer(
        user=user,
        full_name=registration.full_name,
        preferred_language=registration.preferred_language,
    )
    customer.notification_preferences = NotificationPreference(
        whatsapp_order_updates=registration.whatsapp_order_updates,
        whatsapp_marketing=registration.whatsapp_marketing,
        language=registration.preferred_language,
    )
    registration.status = "approved"
    registration.reviewed_by_user_id = actor.id
    registration.reviewed_at = datetime.now(timezone.utc)
    db.add_all([user, customer])
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="customer.registration.approved",
            entity_type="customer",
            entity_id=customer.id,
            before_after_summary={"registration_request_id": str(registration.id)},
        )
    )
    db.commit()
    return customer


@staff_router.post("/customers", response_model=CustomerProfile, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreateInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customer:create")),
    _: None = Depends(require_same_origin),
) -> Customer:
    phone = normalize_phone(payload.phone)
    if db.scalar(select(User.id).where(User.phone == phone)):
        raise HTTPException(status_code=409, detail="A profile already uses this mobile number")
    user = User(
        phone=phone,
        pin_hash=password_hash.hash(payload.pin),
        account_type="customer",
        phone_verified_at=datetime.now(timezone.utc),
    )
    customer = Customer(user=user, full_name=payload.full_name.strip(), preferred_language=payload.preferred_language)
    customer.notification_preferences = NotificationPreference(
        whatsapp_order_updates=payload.whatsapp_order_updates,
        whatsapp_marketing=payload.whatsapp_marketing,
        language=payload.preferred_language,
    )
    db.add_all([user, customer])
    db.flush()
    db.add(AuditLog(actor_user_id=actor.id, action="customer.created", entity_type="customer", entity_id=customer.id))
    db.commit()
    return customer


@staff_router.patch("/customers/{customer_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
def reset_customer_pin(
    customer_id: UUID,
    payload: PinResetInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customer:manage")),
    _: None = Depends(require_same_origin),
) -> None:
    customer = db.scalar(select(Customer).options(selectinload(Customer.user)).where(Customer.id == customer_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer was not found")
    customer.user.pin_hash = password_hash.hash(payload.pin)
    for auth_session in customer.user.sessions:
        auth_session.revoked_at = datetime.now(timezone.utc)
    db.add(AuditLog(actor_user_id=actor.id, action="customer.pin.reset", entity_type="customer", entity_id=customer.id))
    db.commit()


@customer_router.post("/qr", dependencies=[Depends(require_same_origin)])
def rotate_customer_qr(
    customer_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    customer = customer_user.customer
    now = datetime.now(timezone.utc)
    for token in customer.qr_tokens:
        if token.revoked_at is None:
            token.revoked_at = now
    raw_token = new_qr_secret()
    db.add(CustomerQrToken(customer_id=customer.id, token_hash=hash_secret(raw_token)))
    db.commit()
    return {"qr_value": f"durga-customer:{raw_token}"}


@staff_router.post("/customer-qr/resolve", dependencies=[Depends(require_same_origin)])
def resolve_customer_qr(
    payload: dict[str, str],
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("customer:lookup")),
) -> CustomerProfile:
    raw_value = payload.get("qr_value", "")
    prefix = "durga-customer:"
    if not raw_value.startswith(prefix) or len(raw_value) > 100:
        raise HTTPException(status_code=422, detail="This is not a Durga customer QR code")
    token = db.scalar(
        select(CustomerQrToken)
        .options(selectinload(CustomerQrToken.customer).selectinload(Customer.user))
        .where(CustomerQrToken.token_hash == hash_secret(raw_value[len(prefix) :]), CustomerQrToken.revoked_at.is_(None))
    )
    if token is None:
        raise HTTPException(status_code=404, detail="Customer QR code has expired")
    db.add(AuditLog(actor_user_id=actor.id, action="customer.qr.resolved", entity_type="customer", entity_id=token.customer.id))
    db.commit()
    return CustomerProfile(
        id=token.customer.id,
        full_name=token.customer.full_name,
        phone=token.customer.user.phone,
        preferred_language=token.customer.preferred_language,
    )

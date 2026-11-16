import secrets
import uuid
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.api.auth import normalize_phone
from app.api.deps import get_db, require_customer, require_permission, require_same_origin
from app.api.finance import _order_balance
from app.api.schemas import PhotoView
from app.core.config import get_settings
from app.models import (
    AuditLog,
    BookingContact,
    Customer,
    CustomerApproval,
    Garment,
    Order,
    OrderItem,
    OrderStatusHistory,
    NotificationLog,
    Service,
    ServiceCategory,
    User,
)
from app.services.notifications import queue_manual_update

public_router = APIRouter(prefix="/api/v1/public", tags=["public catalogue"])
booking_router = APIRouter(prefix="/api/v1", tags=["bookings and orders"])
staff_router = APIRouter(prefix="/api/v1/staff", tags=["staff orders"])
customer_router = APIRouter(prefix="/api/v1/customer", tags=["customer orders"])
CATEGORY_DISPLAY_ORDER = ("Men", "Women", "Household", "Kids", "Special Services", "Other Services")


class BookingGarmentInput(BaseModel):
    service_id: uuid.UUID
    garment_type: str = Field(min_length=2, max_length=100)
    quantity: int = Field(ge=1, le=25)
    fabric: str | None = Field(default=None, max_length=100)
    colour: str | None = Field(default=None, max_length=60)
    condition_notes: str | None = Field(default=None, max_length=1000)
    special_instructions: str | None = Field(default=None, max_length=1000)


class BookingInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=10, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    pickup_preference: Literal["drop_off", "pickup", "delivery"] | None = None
    preferred_language: Literal["en", "te"] = "en"
    requested_delivery_at: datetime | None = None
    garments: list[BookingGarmentInput] = Field(min_length=1, max_length=25)

    @field_validator("requested_delivery_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Include a time zone with the requested delivery date")
        return value

    @field_validator("garments")
    @classmethod
    def cap_total_garments(cls, value):
        if sum(item.quantity for item in value) > 40:
            raise ValueError("A booking can include up to 40 garments")
        return value


class ActualGarmentInput(BaseModel):
    garment_id: uuid.UUID | None = None
    service_id: uuid.UUID
    garment_type: str = Field(min_length=2, max_length=100)
    fabric: str | None = Field(default=None, max_length=100)
    colour: str | None = Field(default=None, max_length=60)
    condition_notes: str | None = Field(default=None, max_length=1000)
    special_instructions: str | None = Field(default=None, max_length=1000)
    quoted_price_paise: int | None = Field(default=None, ge=1, le=100_000_000)


class VerifyOrderInput(BaseModel):
    customer_id: uuid.UUID
    identity_checked_in_person: bool
    expected_delivery_at: datetime
    garments: list[ActualGarmentInput] = Field(min_length=1, max_length=40)

    @field_validator("expected_delivery_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("Include a time zone with the expected delivery date")
        if value.astimezone(ZoneInfo(get_settings().business_timezone)).date() < datetime.now(
            ZoneInfo(get_settings().business_timezone)
        ).date():
            raise ValueError("Choose today or a future delivery date")
        return value


class OrderApprovalInput(BaseModel):
    decision: Literal["approved", "rejected"]


class StatusChangeInput(BaseModel):
    status: Literal["received_at_shop", "processing", "quality_check", "ready_for_collection", "out_for_delivery", "delivered", "cancelled"]
    note: str | None = Field(default=None, max_length=500)
    cancellation_reason: str | None = Field(default=None, max_length=500)


class DeliveryRevisionInput(BaseModel):
    expected_delivery_at: datetime

    @field_validator("expected_delivery_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("Include a time zone with the revised delivery date")
        zone = ZoneInfo(get_settings().business_timezone)
        if value.astimezone(zone).date() < datetime.now(zone).date():
            raise ValueError("Choose today or a future delivery date")
        return value


class WhatsAppDraftInput(BaseModel):
    notification_id: uuid.UUID | None = None


@public_router.get("/services")
def public_services(db: Session = Depends(get_db)) -> list[dict]:
    categories = db.scalars(
        select(ServiceCategory)
        .options(selectinload(ServiceCategory.services))
        .where(ServiceCategory.active.is_(True), ServiceCategory.services.any(Service.active.is_(True)))
        .order_by(
            case({name: index for index, name in enumerate(CATEGORY_DISPLAY_ORDER)}, value=ServiceCategory.name_en, else_=len(CATEGORY_DISPLAY_ORDER)),
            ServiceCategory.name_en,
        )
    )
    return [
        {
            "id": str(category.id),
            "name": {"en": category.name_en, "te": category.name_te},
            "services": [
                {
                    "id": str(service.id),
                    "name": {"en": service.name_en, "te": service.name_te},
                    "description": {"en": service.description_en, "te": service.description_te},
                    "price_paise": _public_service_price(service),
                    "quotation_required": service.quotation_required or service.price_paise == 0,
                    "price_is_starting": service.price_is_starting,
                    "additional_charge_paise": service.additional_charge_paise,
                    "garment_type": service.garment_type,
                    "pricing_unit": service.pricing_unit,
                    "turnaround_days": service.turnaround_days,
                }
                for service in category.services
                if service.active
            ],
        }
        for category in categories
    ]


def _public_service_price(service: Service) -> int | None:
    return service.price_paise if service.price_paise > 0 else None


@booking_router.post("/bookings", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_same_origin)])
def create_booking(payload: BookingInput, db: Session = Depends(get_db)) -> dict[str, str]:
    service_ids = {item.service_id for item in payload.garments}
    services = {
        service.id: service
        for service in db.scalars(
            select(Service).where(Service.id.in_(service_ids), Service.active.is_(True)).order_by(Service.id).with_for_update()
        )
    }
    if len(services) != len(service_ids):
        raise HTTPException(status_code=422, detail="One or more selected services are unavailable")

    order = Order(
        order_number=f"DUR-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}",
        status="booking_received",
        requested_delivery_at=payload.requested_delivery_at,
    )
    order.booking_contact = BookingContact(
        full_name=payload.full_name.strip(),
        phone=normalize_phone(payload.phone),
        address=payload.address,
        pickup_preference=payload.pickup_preference,
    )
    for requested in payload.garments:
        service = services[requested.service_id]
        for _ in range(requested.quantity):
            item = OrderItem(
                service_id=service.id,
                service_name_snapshot=service.name_en,
                unit_price_paise_snapshot=0 if service.quotation_required or service.price_paise == 0 else service.price_paise,
                pricing_unit_snapshot=service.pricing_unit,
                quantity=1,
                line_total_paise=0 if service.quotation_required or service.price_paise == 0 else service.price_paise + service.additional_charge_paise,
            )
            item.garments.append(
                Garment(
                    garment_type=(service.garment_type or requested.garment_type).strip(),
                    fabric=requested.fabric,
                    colour=requested.colour,
                    condition_notes=requested.condition_notes,
                    special_instructions=requested.special_instructions,
                )
            )
            order.items.append(item)
    order.status_history.append(OrderStatusHistory(to_status="booking_received", note="Booking request received"))
    db.add(order)
    db.commit()
    return {
        "order_number": order.order_number,
        "status": order.status,
        "message": "Request received. The shop will verify the garments, price, and delivery date with you.",
    }


@staff_router.get("/orders")
def staff_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, max_length=120),
    delayed_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("order:read")),
) -> list[dict]:
    statement = select(Order).options(
        selectinload(Order.customer).selectinload(Customer.user),
        selectinload(Order.booking_contact),
        selectinload(Order.items),
    )
    if status_filter:
        statement = statement.where(Order.status == status_filter)
    if delayed_only:
        statement = statement.where(
            Order.expected_delivery_at < datetime.now(timezone.utc),
            Order.status.not_in(["delivered", "cancelled"]),
        )
    if query:
        search = f"%{query.strip()}%"
        statement = statement.outerjoin(Order.booking_contact).outerjoin(Order.customer).outerjoin(Customer.user).where(
            or_(Order.order_number.ilike(search), BookingContact.phone.ilike(search), User.phone.ilike(search))
        )
    orders = db.scalars(statement.order_by(Order.created_at.desc()).limit(250))
    return [_order_list_item(order) for order in orders]


@staff_router.get("/orders/{order_id}")
def staff_order_detail(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("order:read")),
) -> dict:
    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.customer).selectinload(Customer.user),
            selectinload(Order.booking_contact),
            selectinload(Order.items).selectinload(OrderItem.garments).selectinload(Garment.photos),
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    return {
        **_order_list_item(order),
        "customer_id": str(order.customer_id) if order.customer_id else None,
        "requested_delivery_at": order.requested_delivery_at.isoformat() if order.requested_delivery_at else None,
        "proposed_total_paise": order.proposed_total_paise,
        "confirmed_total_paise": order.confirmed_total_paise,
        "delivery_date_pending_approval": order.delivery_date_pending_approval,
        "booking_contact": {
            "full_name": order.booking_contact.full_name,
            "phone": order.booking_contact.phone,
            "address": order.booking_contact.address,
            "pickup_preference": order.booking_contact.pickup_preference,
        } if order.booking_contact else None,
        "garments": [
            {
                "id": str(garment.id),
                "service_id": str(item.service_id) if item.service_id else "",
                "service_name": item.service_name_snapshot,
                "type": garment.garment_type,
                "quantity": item.quantity,
                "unit_price_paise": item.unit_price_paise_snapshot if item.unit_price_paise_snapshot > 0 else None,
                "line_total_paise": item.line_total_paise if item.line_total_paise > 0 else None,
                "pricing_unit": item.pricing_unit_snapshot,
                "fabric": garment.fabric,
                "colour": garment.colour,
                "condition_notes": garment.condition_notes,
                "special_instructions": garment.special_instructions,
                "photos": [str(photo.id) for photo in garment.photos],
            }
            for item in order.items for garment in item.garments
        ],
        "timeline": [
            {"status": item.to_status, "note": item.note, "at": item.occurred_at.isoformat()}
            for item in sorted(order.status_history, key=lambda history: history.occurred_at)
        ],
    }


def _order_list_item(order: Order) -> dict:
    customer = order.customer
    contact = order.booking_contact
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "customer_name": customer.full_name if customer else (contact.full_name if contact else ""),
        "phone": customer.user.phone if customer else (contact.phone if contact else ""),
        "status": order.status,
        "expected_delivery_at": order.expected_delivery_at.isoformat() if order.expected_delivery_at else None,
        "proposed_delivery_at": order.proposed_delivery_at.isoformat() if order.proposed_delivery_at else None,
        "garment_count": sum(item.quantity for item in order.items),
        "created_at": order.created_at.isoformat(),
        "is_delayed": bool(
            order.expected_delivery_at
            and order.expected_delivery_at < datetime.now(timezone.utc)
            and order.status not in {"delivered", "cancelled"}
        ),
    }


@staff_router.post("/orders/{order_id}/verify", dependencies=[Depends(require_same_origin)])
def verify_order(
    order_id: uuid.UUID,
    payload: VerifyOrderInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("order:verify")),
) -> dict:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.garments))
        .where(Order.id == order_id)
        .with_for_update()
    )
    customer = db.get(Customer, payload.customer_id)
    if order is None or customer is None:
        raise HTTPException(status_code=404, detail="Order or customer was not found")
    if order.status not in {"booking_received", "awaiting_verification"}:
        raise HTTPException(status_code=409, detail="This order is no longer awaiting physical verification")
    if not payload.identity_checked_in_person:
        raise HTTPException(status_code=422, detail="Confirm the customer's identity in person or with their QR code")
    if order.booking_contact is None:
        raise HTTPException(status_code=409, detail="This order has no booking contact to verify")

    existing = {garment.id: garment for item in order.items for garment in item.garments}
    submitted_ids = [garment.garment_id for garment in payload.garments if garment.garment_id is not None]
    if len(submitted_ids) != len(set(submitted_ids)) or any(item_id not in existing for item_id in submitted_ids):
        raise HTTPException(status_code=422, detail="A garment was duplicated or does not belong to this order")

    used_service_ids = {item.service_id for item in payload.garments}
    services = {
        service.id: service
        for service in db.scalars(
            select(Service).where(Service.id.in_(used_service_ids), Service.active.is_(True)).order_by(Service.id).with_for_update()
        )
    }
    if len(services) != len(used_service_ids):
        raise HTTPException(status_code=422, detail="One or more selected services are unavailable")

    removed = [garment for garment_id, garment in existing.items() if garment_id not in set(submitted_ids)]
    if any(garment.photos for garment in removed):
        raise HTTPException(status_code=409, detail="Remove intake photos through the correction process before changing garment count")
    old_items = {garment.order_item for garment in removed}
    for garment in removed:
        db.delete(garment)

    quote_total = 0
    for actual in payload.garments:
        service = services[actual.service_id]
        quote_required = service.quotation_required or service.price_paise == 0
        if quote_required and actual.quoted_price_paise is None:
            raise HTTPException(status_code=422, detail=f"Enter a staff quotation for {service.name_en}")
        base_price = actual.quoted_price_paise if quote_required else service.price_paise
        assert base_price is not None
        line_total = base_price + service.additional_charge_paise
        if actual.garment_id:
            garment = existing[actual.garment_id]
            item = garment.order_item
        else:
            item = OrderItem(order=order, quantity=1)
            garment = Garment(order_item=item)
            db.add(item)
        item.service_id = service.id
        item.service_name_snapshot = service.name_en
        item.unit_price_paise_snapshot = base_price
        item.pricing_unit_snapshot = service.pricing_unit
        item.quantity = 1
        item.line_total_paise = line_total
        garment.garment_type = (service.garment_type or actual.garment_type).strip()
        garment.fabric = actual.fabric
        garment.colour = actual.colour
        garment.condition_notes = actual.condition_notes
        garment.special_instructions = actual.special_instructions
        quote_total += line_total

    db.flush()
    for item in old_items:
        if not db.scalar(select(Garment.id).where(Garment.order_item_id == item.id)):
            db.delete(item)

    previous_status = order.status
    order.customer_id = customer.id
    order.status = "awaiting_customer_approval"
    order.proposed_total_paise = quote_total
    order.proposed_delivery_at = payload.expected_delivery_at
    order.delivery_date_pending_approval = False
    order.status_history.append(
        OrderStatusHistory(
            actor_user_id=actor.id,
            from_status=previous_status,
            to_status="awaiting_verification",
            note="Garments and customer identity checked at the shop",
        )
    )
    order.status_history.append(
        OrderStatusHistory(
            actor_user_id=actor.id,
            from_status="awaiting_verification",
            to_status="awaiting_customer_approval",
            note="Final price and expected date sent for customer approval",
        )
    )
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="order.physically_verified",
            entity_type="order",
            entity_id=order.id,
            before_after_summary={"customer_id": str(customer.id), "garment_count": len(payload.garments), "proposed_total_paise": quote_total},
        )
    )
    queue_manual_update(
        db,
        order.id,
        "order_price_date_approval",
        f"proposal:{order.id}:{quote_total}:{payload.expected_delivery_at.isoformat()}:{uuid.uuid4()}",
    )
    db.commit()
    return {"order_number": order.order_number, "status": order.status, "proposed_total_paise": quote_total}


@customer_router.get("/dashboard")
def customer_dashboard(db: Session = Depends(get_db), user: User = Depends(require_customer)) -> dict:
    customer_id = user.customer.id
    orders = list(db.scalars(select(Order).where(Order.customer_id == customer_id)))
    counts = {name: 0 for name in ("total", "in_progress", "pending", "ready", "delivered", "cancelled", "garments")}
    total_value = paid = refunded = outstanding = 0
    for order in orders:
        counts["total"] += 1
        if order.status in {"order_confirmed", "received_at_shop", "processing", "quality_check", "out_for_delivery"}:
            counts["in_progress"] += 1
        if order.status in {"booking_received", "awaiting_verification", "awaiting_customer_approval"}:
            counts["pending"] += 1
        if order.status == "ready_for_collection":
            counts["ready"] += 1
        if order.status == "delivered":
            counts["delivered"] += 1
        if order.status == "cancelled":
            counts["cancelled"] += 1
        counts["garments"] += sum(item.quantity for item in order.items)
        if order.confirmed_total_paise is not None and order.status != "cancelled":
            total, collected, returned = _order_balance(db, order.id)
            total_value += total
            paid += collected
            refunded += returned
            outstanding += total - collected + returned
    return {
        **counts,
        "finalized_order_value_paise": total_value,
        "amount_paid_paise": paid,
        "refunds_paise": refunded,
        "outstanding_balance_paise": outstanding,
    }


@customer_router.get("/orders")
def customer_orders(db: Session = Depends(get_db), user: User = Depends(require_customer)) -> list[dict]:
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.garments), selectinload(Order.status_history))
        .where(Order.customer_id == user.customer.id)
        .order_by(Order.created_at.desc())
        .limit(200)
    )
    return [_customer_order_detail(order) for order in orders]


@customer_router.get("/orders/{order_id}")
def customer_order_detail(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_customer),
) -> dict:
    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.garments).selectinload(Garment.photos),
            selectinload(Order.status_history),
        )
        .where(Order.id == order_id, Order.customer_id == user.customer.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    return _customer_order_detail(order)


def _customer_order_detail(order: Order) -> dict:
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status,
        "expected_delivery_at": order.expected_delivery_at.isoformat() if order.expected_delivery_at else None,
        "proposed_delivery_at": order.proposed_delivery_at.isoformat() if order.proposed_delivery_at else None,
        "proposed_total_paise": order.proposed_total_paise,
        "confirmed_total_paise": order.confirmed_total_paise,
        "delivery_date_pending_approval": order.delivery_date_pending_approval,
        "garments": [
            {
                "id": str(garment.id),
                "type": garment.garment_type,
                "service": item.service_name_snapshot,
                "quantity": item.quantity,
                "unit_price_paise": item.unit_price_paise_snapshot if item.unit_price_paise_snapshot > 0 else None,
                "line_total_paise": item.line_total_paise if item.line_total_paise > 0 else None,
                "pricing_unit": item.pricing_unit_snapshot,
                "price_paise": item.line_total_paise // max(item.quantity, 1) if item.line_total_paise > 0 else None,
                "fabric": garment.fabric,
                "colour": garment.colour,
                "condition_notes": garment.condition_notes,
                "special_instructions": garment.special_instructions,
                "status": garment.processing_status,
                "photos": [str(photo.id) for photo in garment.photos],
            }
            for item in order.items
            for garment in item.garments
        ],
        "timeline": [
            {"status": item.to_status, "note": item.note, "at": item.occurred_at.isoformat()}
            for item in sorted(order.status_history, key=lambda history: history.occurred_at)
        ],
    }


@customer_router.post("/orders/{order_id}/approvals", dependencies=[Depends(require_same_origin)])
def approve_order_proposal(
    order_id: uuid.UUID,
    payload: OrderApprovalInput,
    db: Session = Depends(get_db),
    user: User = Depends(require_customer),
) -> dict:
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == user.customer.id).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    if order.proposed_delivery_at is None or order.proposed_total_paise is None:
        raise HTTPException(status_code=409, detail="There is no price and date waiting for approval")
    if order.status != "awaiting_customer_approval" and not order.delivery_date_pending_approval:
        raise HTTPException(status_code=409, detail="There is no change waiting for approval")

    is_initial_confirmation = order.status == "awaiting_customer_approval"
    order.approvals.append(
        CustomerApproval(
            confirmed_total_paise=order.proposed_total_paise,
            confirmed_delivery_at=order.proposed_delivery_at,
            method="customer_portal",
            decision=payload.decision,
        )
    )
    db.execute(
        update(NotificationLog)
        .where(
            NotificationLog.order_id == order.id,
            NotificationLog.event_type == "order_price_date_approval",
            NotificationLog.provider_state == "manual_required",
        )
        .values(provider_state="obsolete")
    )
    if payload.decision == "approved":
        order.confirmed_total_paise = order.proposed_total_paise
        order.expected_delivery_at = order.proposed_delivery_at
        order.proposed_delivery_at = None
        order.proposed_total_paise = None
        order.delivery_date_pending_approval = False
        if is_initial_confirmation:
            previous_status = order.status
            order.status = "order_confirmed"
            order.confirmed_at = datetime.now(timezone.utc)
            order.status_history.append(
                OrderStatusHistory(from_status=previous_status, to_status=order.status, note="Customer approved the price and delivery date")
            )
    else:
        if is_initial_confirmation:
            previous_status = order.status
            order.status = "awaiting_verification"
            order.status_history.append(
                OrderStatusHistory(from_status=previous_status, to_status=order.status, note="Customer declined the proposed price or date")
            )
        order.proposed_delivery_at = None
        order.proposed_total_paise = None
        order.delivery_date_pending_approval = False
    db.add(AuditLog(actor_user_id=user.id, action=f"order.proposal.{payload.decision}", entity_type="order", entity_id=order.id))
    if payload.decision == "approved" and is_initial_confirmation:
        queue_manual_update(db, order.id, "order_confirmed", f"confirmed:{order.id}:{uuid.uuid4()}")
    db.commit()
    return {"order_number": order.order_number, "status": order.status, "expected_delivery_at": order.expected_delivery_at.isoformat() if order.expected_delivery_at else None}


@staff_router.patch("/orders/{order_id}/status", dependencies=[Depends(require_same_origin)])
def change_order_status(
    order_id: uuid.UUID,
    payload: StatusChangeInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("order:status")),
) -> dict[str, str]:
    transitions = {
        "booking_received": {"cancelled"},
        "awaiting_verification": {"cancelled"},
        "awaiting_customer_approval": {"cancelled"},
        "order_confirmed": {"received_at_shop", "cancelled"},
        "received_at_shop": {"processing", "cancelled"},
        "processing": {"quality_check", "cancelled"},
        "quality_check": {"processing", "ready_for_collection"},
        "ready_for_collection": {"out_for_delivery", "delivered", "processing"},
        "out_for_delivery": {"delivered", "ready_for_collection"},
    }
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    if payload.status not in transitions.get(order.status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot change an order from {order.status} to {payload.status}")
    if payload.status == "cancelled" and not payload.cancellation_reason:
        raise HTTPException(status_code=422, detail="Add a cancellation reason")
    previous = order.status
    order.status = payload.status
    if payload.status == "cancelled":
        order.cancellation_reason = payload.cancellation_reason
    history = OrderStatusHistory(
        actor_user_id=actor.id,
        from_status=previous,
        to_status=payload.status,
        note=payload.note or payload.cancellation_reason,
    )
    order.status_history.append(history)
    db.flush()
    queue_manual_update(db, order.id, f"order_status_{payload.status}", f"status:{history.id}")
    db.add(AuditLog(actor_user_id=actor.id, action="order.status.changed", entity_type="order", entity_id=order.id,
                    before_after_summary={"from": previous, "to": payload.status}))
    db.commit()
    return {"order_number": order.order_number, "status": order.status}


@staff_router.patch("/orders/{order_id}/delivery-date", dependencies=[Depends(require_same_origin)])
def revise_delivery_date(
    order_id: uuid.UUID,
    payload: DeliveryRevisionInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("order:delivery")),
) -> dict[str, str]:
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    if order.status in {"delivered", "cancelled"} or order.confirmed_total_paise is None:
        raise HTTPException(status_code=409, detail="Only a confirmed, unfinished order can have a revised date")
    old_date = order.expected_delivery_at
    db.execute(
        update(NotificationLog)
        .where(
            NotificationLog.order_id == order.id,
            NotificationLog.provider_state == "manual_required",
            NotificationLog.event_type.in_(["delivery_reminder", "delivery_delay", "delivery_date_revised"]),
        )
        .values(provider_state="obsolete")
    )
    order.proposed_delivery_at = payload.expected_delivery_at
    order.proposed_total_paise = order.confirmed_total_paise
    order.delivery_date_pending_approval = True
    order.status_history.append(
        OrderStatusHistory(
            actor_user_id=actor.id,
            from_status=order.status,
            to_status=order.status,
            note=f"Revised delivery date proposed: {payload.expected_delivery_at.isoformat()}",
        )
    )
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="order.delivery_date.revised",
            entity_type="order",
            entity_id=order.id,
            before_after_summary={"previous": old_date.isoformat() if old_date else None, "proposed": payload.expected_delivery_at.isoformat()},
        )
    )
    queue_manual_update(
        db,
        order.id,
        "delivery_date_revised",
        f"delivery_revision:{order.id}:{payload.expected_delivery_at.isoformat()}:{uuid.uuid4()}",
    )
    db.commit()
    return {"order_number": order.order_number, "message": "Revised date is saved and waiting for customer approval"}


@staff_router.post("/orders/{order_id}/whatsapp-draft", dependencies=[Depends(require_same_origin)])
def whatsapp_draft(
    order_id: uuid.UUID,
    payload: WhatsAppDraftInput | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("notification:send")),
) -> dict[str, str]:
    order = db.scalar(select(Order).options(selectinload(Order.customer).selectinload(Customer.user)).where(Order.id == order_id))
    if order is None or order.customer is None:
        raise HTTPException(status_code=404, detail="A verified customer is required for this order")
    preferences = order.customer.notification_preferences
    if preferences is None or not preferences.whatsapp_order_updates:
        raise HTTPException(status_code=409, detail="The customer has not opted in to WhatsApp order updates")
    notification = None
    if payload and payload.notification_id:
        notification = db.get(NotificationLog, payload.notification_id)
        if notification is None or notification.order_id != order.id:
            raise HTTPException(status_code=404, detail="Notification was not found for this order")
        if notification.provider_state != "manual_required":
            raise HTTPException(status_code=409, detail="This message is no longer waiting to be sent")
    number = "".join(character for character in get_settings().shop_whatsapp_number if character.isdigit())
    if not number:
        raise HTTPException(status_code=503, detail="The shop WhatsApp number has not been configured")
    delivery = order.proposed_delivery_at or order.expected_delivery_at
    local_today = datetime.now(ZoneInfo(get_settings().business_timezone)).date()
    delivery_day = delivery.astimezone(ZoneInfo(get_settings().business_timezone)).date() if delivery else None
    days_left = (delivery_day - local_today).days if delivery_day else None
    date_text = delivery_day.strftime("%d %B %Y") if delivery_day else "to be confirmed"
    balance = 0
    if order.confirmed_total_paise is not None:
        total, paid, refunded = _order_balance(db, order.id)
        balance = total - paid + refunded
    state = notification.event_type if notification else "order_update"
    if state == "delivery_reminder":
        countdown = "today" if days_left == 0 else "tomorrow" if days_left == 1 else f"in {days_left} days"
        message = (
            f"నమస్కారం {order.customer.full_name}, మీ ఆర్డర్ {order.order_number} {countdown} సిద్ధంగా ఉంటుంది. తేదీ: {date_text}."
            if preferences.language == "te"
            else f"Hello {order.customer.full_name}, your order {order.order_number} is expected {countdown} ({date_text})."
        )
    elif state == "delivery_delay":
        if order.proposed_delivery_at is None:
            message = (
                f"నమస్కారం {order.customer.full_name}, మీ ఆర్డర్ {order.order_number} ఆలస్యమైంది. క్షమించండి; కొత్త తేదీని త్వరలో తెలియజేస్తాము."
                if preferences.language == "te"
                else f"Hello {order.customer.full_name}, your order {order.order_number} is delayed. We are sorry; we will confirm a revised date shortly."
            )
        else:
            message = (
                f"నమస్కారం {order.customer.full_name}, మీ ఆర్డర్ {order.order_number} ఆలస్యమైంది. ప్రతిపాదిత కొత్త తేదీ: {date_text}."
                if preferences.language == "te"
                else f"Hello {order.customer.full_name}, your order {order.order_number} is delayed. Proposed revised date: {date_text}."
            )
    elif state in {"delivery_date_revised", "order_price_date_approval"}:
        proposed_total = order.proposed_total_paise or order.confirmed_total_paise or 0
        message = (
            f"నమస్కారం {order.customer.full_name}, మీ ఆర్డర్ {order.order_number} కోసం ప్రతిపాదిత తేదీ {date_text}, మొత్తం ₹{proposed_total // 100}.{proposed_total % 100:02d}. దయచేసి అంగీకరించండి."
            if preferences.language == "te"
            else f"Hello {order.customer.full_name}, proposed date for order {order.order_number}: {date_text}. Proposed total: Rs {proposed_total // 100}.{proposed_total % 100:02d}. Please review and approve in your account."
        )
    elif state == "payment_received":
        message = (
            f"నమస్కారం {order.customer.full_name}, మీ ఆర్డర్ {order.order_number} చెల్లింపు నమోదు చేయబడింది. మిగిలిన మొత్తం ₹{balance // 100}.{balance % 100:02d}."
            if preferences.language == "te"
            else f"Hello {order.customer.full_name}, a payment has been recorded for order {order.order_number}. Remaining balance: Rs {balance // 100}.{balance % 100:02d}."
        )
    elif order.status == "ready_for_collection":
        message = (
            f"శుభవార్త! మీ ఆర్డర్ {order.order_number} తీసుకెళ్లడానికి సిద్ధంగా ఉంది. మిగిలిన మొత్తం ₹{balance // 100}.{balance % 100:02d}."
            if preferences.language == "te"
            else f"Good news! Your order {order.order_number} is ready for collection. Remaining balance: Rs {balance // 100}.{balance % 100:02d}."
        )
    else:
        message = (
            f"నమస్కారం {order.customer.full_name}, మీ ఆర్డర్ {order.order_number} స్థితి: {order.status.replace('_', ' ')}. అంచనా తేదీ: {date_text}."
            if preferences.language == "te"
            else f"Hello {order.customer.full_name}, your order {order.order_number} status is {order.status.replace('_', ' ')}. Expected date: {date_text}."
        )
    if notification is not None:
        db.add(AuditLog(actor_user_id=actor.id, action="notification.draft.prepared", entity_type="notification", entity_id=notification.id))
        db.commit()
    return {"url": f"https://wa.me/{number}?text={quote(message)}", "message": message}

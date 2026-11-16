from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Customer, NotificationLog, Order


def queue_manual_update(
    db: Session,
    order_id: UUID,
    event_type: str,
    idempotency_key: str,
) -> NotificationLog | None:
    existing = db.scalar(select(NotificationLog).where(NotificationLog.idempotency_key == idempotency_key))
    if existing is not None:
        return None
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.customer).selectinload(Customer.notification_preferences))
        .where(Order.id == order_id)
    )
    if order is None or order.customer is None:
        return None
    preferences = order.customer.notification_preferences
    opted_in = bool(preferences and preferences.whatsapp_order_updates)
    entry = NotificationLog(
        customer_id=order.customer_id,
        order_id=order.id,
        channel="whatsapp" if opted_in else "staff",
        event_type=event_type,
        idempotency_key=idempotency_key,
        provider_state="manual_required" if opted_in else "customer_opted_out",
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    return entry

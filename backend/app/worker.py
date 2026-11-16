import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import AuditLog, DataExport, Order
from app.services.notifications import queue_manual_update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("durga.worker")
REMINDER_DAYS = {0, 1, 2, 3}
OPEN_STATUSES = {
    "order_confirmed",
    "received_at_shop",
    "processing",
    "quality_check",
    "out_for_delivery",
}


def process_delivery_alerts() -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    local_today = now.astimezone(ZoneInfo(settings.business_timezone)).date()
    cutoff = datetime.combine(local_today + timedelta(days=3), datetime.max.time(), ZoneInfo(settings.business_timezone))
    created = 0
    with SessionLocal() as db:
        expired_exports = db.scalars(
            select(DataExport).where(
                DataExport.status == "ready",
                DataExport.expires_at.is_not(None),
                DataExport.expires_at <= now,
            )
        )
        media_root = Path(settings.media_root).resolve()
        for export in expired_exports:
            if export.storage_key:
                archive_path = (media_root / export.storage_key).resolve()
                if media_root in archive_path.parents:
                    archive_path.unlink(missing_ok=True)
            export.status = "expired"
            db.add(
                AuditLog(
                    action="data_export.expired",
                    entity_type="data_export",
                    entity_id=export.id,
                )
            )
        orders = db.scalars(
            select(Order).where(
                Order.status.in_(OPEN_STATUSES),
                Order.expected_delivery_at.is_not(None),
                Order.expected_delivery_at <= cutoff,
            )
        )
        for order in orders:
            due_day = order.expected_delivery_at.astimezone(ZoneInfo(settings.business_timezone)).date()
            days_left = (due_day - local_today).days
            if days_left < 0:
                event = "delivery_delay"
                key = f"delay:{order.id}:{order.expected_delivery_at.isoformat()}"
            elif days_left in REMINDER_DAYS:
                event = "delivery_reminder"
                key = f"reminder:{order.id}:{order.expected_delivery_at.isoformat()}:{days_left}"
            else:
                continue
            if queue_manual_update(db, order.id, event, key) is not None:
                created += 1
        db.commit()
    return created


def main() -> None:
    logger.info("Reminder worker started; WhatsApp messages are prepared for manual sending only")
    while True:
        try:
            created = process_delivery_alerts()
            if created:
                logger.info("Created %s reminder or delay alert records", created)
        except Exception:
            logger.exception("Could not process delivery reminders")
        time.sleep(60)


if __name__ == "__main__":
    main()

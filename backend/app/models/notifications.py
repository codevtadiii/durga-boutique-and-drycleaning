import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True)
    whatsapp_order_updates: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    whatsapp_marketing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    language: Mapped[str] = mapped_column(String(5), default="en", server_default="en")

    customer: Mapped["Customer"] = relationship(back_populates="notification_preferences")


class NotificationTemplate(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "notification_templates"
    __table_args__ = (UniqueConstraint("event_type", "language", "channel", name="uq_notification_template_locale"),)

    event_type: Mapped[str] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(5))
    channel: Mapped[str] = mapped_column(String(20))
    template_body: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationLog(UUIDPrimaryKey, Base):
    __tablename__ = "notification_logs"
    __table_args__ = (Index("ix_notification_logs_order_created", "order_id", "created_at"),)

    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notification_templates.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(20))
    event_type: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True)
    provider_state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    handled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    outbox: Mapped["NotificationOutbox | None"] = relationship(back_populates="notification", uselist=False)
    order: Mapped["Order | None"] = relationship()


class NotificationOutbox(UUIDPrimaryKey, Base):
    __tablename__ = "notification_outbox"

    notification_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_logs.id", ondelete="CASCADE"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    notification: Mapped[NotificationLog] = relationship(back_populates="outbox")

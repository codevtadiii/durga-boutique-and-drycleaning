import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Order(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booking_received','awaiting_verification','order_confirmed','received_at_shop',"
            "'awaiting_customer_approval','processing','quality_check','ready_for_collection','out_for_delivery','delivered','cancelled')",
            name="ck_orders_status",
        ),
        Index("ix_orders_status_due", "status", "expected_delivery_at"),
    )

    order_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), default="booking_received", index=True)
    requested_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    proposed_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_total_paise: Mapped[int | None] = mapped_column(Integer)
    proposed_total_paise: Mapped[int | None] = mapped_column(Integer)
    delivery_date_pending_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))

    customer: Mapped["Customer | None"] = relationship()
    booking_contact: Mapped["BookingContact | None"] = relationship(back_populates="order", uselist=False)
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    approvals: Mapped[list["CustomerApproval"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class BookingContact(TimestampMixin, Base):
    __tablename__ = "booking_contacts"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    address: Mapped[str | None] = mapped_column(String(500))
    pickup_preference: Mapped[str | None] = mapped_column(String(24))

    order: Mapped[Order] = relationship(back_populates="booking_contact")


class OrderItem(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),)

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("services.id", ondelete="SET NULL"))
    service_name_snapshot: Mapped[str] = mapped_column(String(120))
    unit_price_paise_snapshot: Mapped[int] = mapped_column(Integer)
    pricing_unit_snapshot: Mapped[str] = mapped_column(String(30), default="per item")
    quantity: Mapped[int] = mapped_column(Integer)
    line_total_paise: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
    garments: Mapped[list["Garment"]] = relationship(back_populates="order_item", cascade="all, delete-orphan")


class Garment(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "garments"

    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"), index=True)
    garment_type: Mapped[str] = mapped_column(String(100))
    fabric: Mapped[str | None] = mapped_column(String(100))
    colour: Mapped[str | None] = mapped_column(String(60))
    condition_notes: Mapped[str | None] = mapped_column(Text)
    special_instructions: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[str] = mapped_column(String(32), default="received")
    quality_status: Mapped[str] = mapped_column(String(32), default="pending")

    order_item: Mapped[OrderItem] = relationship(back_populates="garments")
    photos: Mapped[list["UploadedFile"]] = relationship(back_populates="garment")


class UploadedFile(UUIDPrimaryKey, Base):
    __tablename__ = "uploaded_files"

    garment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("garments.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(24), default="intake_photo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    garment: Mapped["Garment | None"] = relationship(back_populates="photos")


class OrderStatusHistory(UUIDPrimaryKey, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    order: Mapped[Order] = relationship(back_populates="status_history")


class CustomerApproval(UUIDPrimaryKey, Base):
    __tablename__ = "customer_approvals"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    confirmed_total_paise: Mapped[int] = mapped_column(Integer)
    confirmed_delivery_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    method: Mapped[str] = mapped_column(String(24))
    decision: Mapped[str] = mapped_column(String(16), default="approved")
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="approvals")

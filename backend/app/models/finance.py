import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Payment(UUIDPrimaryKey, Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_payments_amount_positive"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    method: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="successful", index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    allocations: Mapped[list["PaymentAllocation"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="payment")


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_payment_allocations_amount_positive"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), primary_key=True)
    amount_paise: Mapped[int] = mapped_column(Integer)

    payment: Mapped[Payment] = relationship(back_populates="allocations")


class Refund(UUIDPrimaryKey, Base):
    __tablename__ = "refunds"
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_refunds_amount_positive"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    method: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(500))
    refunded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    payment: Mapped[Payment] = relationship(back_populates="refunds")


class ExpenseCategory(UUIDPrimaryKey, Base):
    __tablename__ = "expense_categories"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    active: Mapped[bool] = mapped_column(default=True)


class Expense(UUIDPrimaryKey, Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_expenses_amount_positive"),)

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("expense_categories.id", ondelete="RESTRICT"), index=True)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uploaded_files.id", ondelete="SET NULL"))


class DailyClosing(UUIDPrimaryKey, Base):
    __tablename__ = "daily_closings"

    business_date: Mapped[date] = mapped_column(Date, unique=True)
    closed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    transaction_totals_by_method: Mapped[dict] = mapped_column(JSON)
    expense_totals_by_category: Mapped[dict] = mapped_column(JSON)
    expense_total_paise: Mapped[int] = mapped_column(Integer)
    counted_cash_paise: Mapped[int] = mapped_column(Integer)
    cash_variance_paise: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(1000))
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

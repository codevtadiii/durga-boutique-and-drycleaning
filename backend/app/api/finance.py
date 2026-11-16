import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_customer, require_permission, require_same_origin
from app.models import (
    AuditLog,
    Expense,
    ExpenseCategory,
    Order,
    Payment,
    PaymentAllocation,
    Refund,
    User,
)
from app.services.notifications import queue_manual_update

router = APIRouter(prefix="/api/v1", tags=["payments and expenses"])


class PaymentCreate(BaseModel):
    amount_paise: int = Field(gt=0, le=100_000_000)
    idempotency_key: uuid.UUID
    method: Literal["cash", "upi", "card", "bank_transfer", "other"]
    transaction_reference: str | None = Field(default=None, max_length=120)


class RefundCreate(BaseModel):
    amount_paise: int = Field(gt=0, le=100_000_000)
    idempotency_key: uuid.UUID
    method: Literal["cash", "upi", "card", "bank_transfer", "other"]
    reason: str = Field(min_length=3, max_length=500)


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class ExpenseCreate(BaseModel):
    category_id: uuid.UUID
    amount_paise: int = Field(gt=0, le=100_000_000)
    description: str | None = Field(default=None, max_length=1000)
    spent_at: datetime


class PaymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: str
    status: str
    amount_paise: int
    transaction_reference: str | None
    paid_at: datetime


class ExpenseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    amount_paise: int
    description: str | None
    spent_at: datetime


def _order_balance(db: Session, order_id: uuid.UUID) -> tuple[int, int, int]:
    finalized = db.scalar(select(Order.confirmed_total_paise).where(Order.id == order_id)) or 0
    paid = db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount_paise), 0))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(PaymentAllocation.order_id == order_id, Payment.status == "successful")
    ) or 0
    refunded = db.scalar(
        select(func.coalesce(func.sum(Refund.amount_paise), 0))
        .join(Payment, Payment.id == Refund.payment_id)
        .join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.order_id == order_id)
    ) or 0
    return int(finalized), int(paid), int(refunded)


@router.post(
    "/staff/orders/{order_id}/payments",
    response_model=PaymentView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_same_origin)],
)
def record_payment(
    order_id: uuid.UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("payment:record")),
) -> Payment:
    existing = db.scalar(select(Payment).where(Payment.idempotency_key == str(payload.idempotency_key)))
    if existing is not None:
        existing_order = db.scalar(
            select(PaymentAllocation.order_id).where(PaymentAllocation.payment_id == existing.id)
        )
        if (
            existing_order != order_id
            or existing.amount_paise != payload.amount_paise
            or existing.method != payload.method
            or existing.transaction_reference != payload.transaction_reference
        ):
            raise HTTPException(status_code=409, detail="This payment request key was already used for different details")
        return existing
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.customer_id is None or order.confirmed_total_paise is None:
        raise HTTPException(status_code=409, detail="Confirm the customer, price, and delivery date before recording payment")
    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="A cancelled order cannot accept a payment")
    total, paid, refunded = _order_balance(db, order_id)
    outstanding = total - paid + refunded
    if payload.amount_paise > outstanding:
        raise HTTPException(status_code=409, detail="Payment is greater than the remaining balance")
    payment = Payment(
        customer_id=order.customer_id,
        recorded_by_user_id=actor.id,
        method=payload.method,
        status="successful",
        amount_paise=payload.amount_paise,
        idempotency_key=str(payload.idempotency_key),
        transaction_reference=payload.transaction_reference,
        paid_at=datetime.now(timezone.utc),
    )
    payment.allocations.append(PaymentAllocation(order_id=order.id, amount_paise=payload.amount_paise))
    db.add(payment)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="payment.recorded",
            entity_type="payment",
            entity_id=payment.id,
            before_after_summary={"order_id": str(order.id), "amount_paise": payload.amount_paise, "method": payload.method},
        )
    )
    queue_manual_update(db, order.id, "payment_received", f"payment:{payment.id}")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Payment).where(Payment.idempotency_key == str(payload.idempotency_key)))
        existing_order = db.scalar(
            select(PaymentAllocation.order_id).where(PaymentAllocation.payment_id == existing.id)
        ) if existing else None
        if (
            existing
            and existing_order == order_id
            and existing.amount_paise == payload.amount_paise
            and existing.method == payload.method
            and existing.transaction_reference == payload.transaction_reference
        ):
            return existing
        raise HTTPException(status_code=409, detail="Payment conflicts with an existing financial record")
    return payment


@router.post(
    "/staff/orders/{order_id}/payments/{payment_id}/refunds",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_same_origin)],
)
def record_refund(
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    payload: RefundCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("refund:record")),
) -> dict:
    existing_refund = db.scalar(select(Refund).where(Refund.idempotency_key == str(payload.idempotency_key)))
    if existing_refund is not None:
        existing_order = db.scalar(
            select(PaymentAllocation.order_id).where(PaymentAllocation.payment_id == existing_refund.payment_id)
        )
        if (
            existing_refund.payment_id != payment_id
            or existing_order != order_id
            or existing_refund.amount_paise != payload.amount_paise
            or existing_refund.method != payload.method
            or existing_refund.reason != payload.reason
        ):
            raise HTTPException(status_code=409, detail="This refund request key was already used for different details")
        return {"id": str(existing_refund.id), "amount_paise": existing_refund.amount_paise, "refunded_at": existing_refund.refunded_at}
    payment = db.scalar(
        select(Payment)
        .options(selectinload(Payment.allocations), selectinload(Payment.refunds))
        .where(Payment.id == payment_id, Payment.status == "successful")
        .with_for_update()
    )
    allocation = next((item for item in payment.allocations if item.order_id == order_id), None) if payment else None
    if payment is None or allocation is None:
        raise HTTPException(status_code=404, detail="Payment for this order was not found")
    remaining = allocation.amount_paise - sum(refund.amount_paise for refund in payment.refunds)
    if payload.amount_paise > remaining:
        raise HTTPException(status_code=409, detail="Refund is greater than the unrefunded payment")
    refund = Refund(
        payment_id=payment.id,
        amount_paise=payload.amount_paise,
        idempotency_key=str(payload.idempotency_key),
        method=payload.method,
        reason=payload.reason,
        refunded_at=datetime.now(timezone.utc),
    )
    db.add(refund)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="payment.refunded",
            entity_type="refund",
            entity_id=refund.id,
            before_after_summary={"payment_id": str(payment.id), "amount_paise": payload.amount_paise},
        )
    )
    queue_manual_update(db, order_id, "refund_recorded", f"refund:{refund.id}")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_refund = db.scalar(select(Refund).where(Refund.idempotency_key == str(payload.idempotency_key)))
        existing_order = db.scalar(
            select(PaymentAllocation.order_id).where(PaymentAllocation.payment_id == existing_refund.payment_id)
        ) if existing_refund else None
        if (
            existing_refund
            and existing_refund.payment_id == payment_id
            and existing_order == order_id
            and existing_refund.amount_paise == payload.amount_paise
            and existing_refund.method == payload.method
            and existing_refund.reason == payload.reason
        ):
            return {
                "id": str(existing_refund.id),
                "amount_paise": existing_refund.amount_paise,
                "refunded_at": existing_refund.refunded_at,
            }
        raise HTTPException(status_code=409, detail="Refund conflicts with an existing financial record")
    return {"id": str(refund.id), "amount_paise": refund.amount_paise, "refunded_at": refund.refunded_at}


@router.get("/customer/payments", response_model=list[PaymentView])
def customer_payments(
    db: Session = Depends(get_db),
    user: User = Depends(require_customer),
) -> list[Payment]:
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.customer_id == user.customer.id)
            .order_by(Payment.paid_at.desc())
            .limit(200)
        )
    )


@router.get("/staff/payment-orders")
def search_payment_orders(
    query: str = Query(min_length=3, max_length=24),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("payment:read")),
) -> list[dict]:
    term = query.strip()
    if len(term) < 3:
        raise HTTPException(status_code=422, detail="Enter at least three characters from the order number")
    rows = db.scalars(
        select(Order)
        .where(
            Order.order_number.ilike(f"%{term}%"),
            Order.confirmed_total_paise.is_not(None),
            Order.status != "cancelled",
        )
        .order_by(Order.created_at.desc())
        .limit(30)
    )
    results = []
    for order in rows:
        total, paid, refunded = _order_balance(db, order.id)
        results.append(
            {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "status": order.status,
                "finalized_order_value_paise": total,
                "outstanding_balance_paise": total - paid + refunded,
            }
        )
    return results


@router.get("/staff/orders/{order_id}/payments")
def staff_order_payments(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("payment:read")),
) -> list[dict]:
    if db.get(Order, order_id) is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    payments = db.scalars(
        select(Payment)
        .join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .options(selectinload(Payment.refunds))
        .where(PaymentAllocation.order_id == order_id)
        .order_by(Payment.paid_at.desc())
    )
    return [
        {
            "id": str(payment.id),
            "method": payment.method,
            "status": payment.status,
            "amount_paise": payment.amount_paise,
            "transaction_reference": payment.transaction_reference,
            "paid_at": payment.paid_at.isoformat(),
            "refunds": [
                {
                    "id": str(refund.id),
                    "amount_paise": refund.amount_paise,
                    "method": refund.method,
                    "reason": refund.reason,
                    "refunded_at": refund.refunded_at.isoformat(),
                }
                for refund in payment.refunds
            ],
        }
        for payment in payments
    ]


@router.get("/staff/expense-categories")
def list_expense_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("expense:read")),
) -> list[dict[str, str]]:
    rows = db.scalars(select(ExpenseCategory).where(ExpenseCategory.active.is_(True)).order_by(ExpenseCategory.name))
    return [{"id": str(item.id), "name": item.name} for item in rows]


@router.post("/staff/expense-categories", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_same_origin)])
def create_expense_category(
    payload: ExpenseCategoryCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("expense:write")),
) -> dict[str, str]:
    name = payload.name.strip()
    if db.scalar(select(ExpenseCategory.id).where(func.lower(ExpenseCategory.name) == name.lower())):
        raise HTTPException(status_code=409, detail="This expense category already exists")
    category = ExpenseCategory(name=name, active=True)
    db.add(category)
    db.flush()
    db.add(AuditLog(actor_user_id=actor.id, action="expense_category.created", entity_type="expense_category", entity_id=category.id))
    db.commit()
    return {"id": str(category.id), "name": category.name}


@router.get("/staff/expenses", response_model=list[ExpenseView])
def list_expenses(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("expense:read")),
) -> list[Expense]:
    return list(db.scalars(select(Expense).order_by(Expense.spent_at.desc()).limit(500)))


@router.post("/staff/expenses", response_model=ExpenseView, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_same_origin)])
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("expense:write")),
) -> Expense:
    if payload.spent_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Include the expense time zone")
    if db.get(ExpenseCategory, payload.category_id) is None:
        raise HTTPException(status_code=404, detail="Expense category was not found")
    expense = Expense(
        category_id=payload.category_id,
        recorded_by_user_id=actor.id,
        amount_paise=payload.amount_paise,
        description=payload.description,
        spent_at=payload.spent_at,
    )
    db.add(expense)
    db.flush()
    db.add(AuditLog(actor_user_id=actor.id, action="expense.recorded", entity_type="expense", entity_id=expense.id))
    db.commit()
    return expense


@router.get("/staff/orders/{order_id}/balance")
def staff_order_balance(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("payment:read")),
) -> dict[str, int]:
    if db.get(Order, order_id) is None:
        raise HTTPException(status_code=404, detail="Order was not found")
    total, paid, refunded = _order_balance(db, order_id)
    return {
        "finalized_order_value_paise": total,
        "collections_paise": paid,
        "refunds_paise": refunded,
        "outstanding_balance_paise": total - paid + refunded,
    }

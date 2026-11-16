from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission, require_same_origin
from app.core.config import get_settings
from app.models import AuditLog, DailyClosing, Expense, ExpenseCategory, Payment, Refund, User

router = APIRouter(prefix="/api/v1/staff/daily-closings", tags=["daily closing"])


class ClosingSubmit(BaseModel):
    counted_cash_paise: int = Field(ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class ClosingView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_date: date
    transaction_totals_by_method: dict
    expense_totals_by_category: dict
    expense_total_paise: int
    expected_cash_paise: int
    counted_cash_paise: int | None
    cash_variance_paise: int | None
    notes: str | None
    closed_at: datetime | None


def _business_window(day: date) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(get_settings().business_timezone)
    start = datetime.combine(day, time.min, tzinfo=timezone)
    return start, start + timedelta(days=1)


def _totals(db: Session, day: date) -> tuple[dict, dict, int, int]:
    start, end = _business_window(day)
    collections = {
        method: int(total or 0)
        for method, total in db.execute(
            select(Payment.method, func.sum(Payment.amount_paise))
            .where(Payment.status == "successful", Payment.paid_at >= start, Payment.paid_at < end)
            .group_by(Payment.method)
        )
    }
    refunds = {
        method: int(total or 0)
        for method, total in db.execute(
            select(Refund.method, func.sum(Refund.amount_paise))
            .join(Payment, Payment.id == Refund.payment_id)
            .where(Refund.refunded_at >= start, Refund.refunded_at < end)
            .group_by(Refund.method)
        )
    }
    expense_totals = {
        name: int(total or 0)
        for name, total in db.execute(
            select(ExpenseCategory.name, func.sum(Expense.amount_paise))
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(Expense.spent_at >= start, Expense.spent_at < end)
            .group_by(ExpenseCategory.name)
        )
    }
    expense_total = sum(expense_totals.values())
    transaction_totals = {
        "collections": collections,
        "refunds": refunds,
        "net_by_method": {
            method: collections.get(method, 0) - refunds.get(method, 0)
            for method in collections.keys() | refunds.keys()
        },
    }
    expected_cash = collections.get("cash", 0) - refunds.get("cash", 0)
    return transaction_totals, expense_totals, expense_total, expected_cash


def _view(day: date, totals: tuple[dict, dict, int, int], counted: int | None = None, variance: int | None = None,
          notes: str | None = None, closed_at: datetime | None = None) -> ClosingView:
    transactions, expenses, expense_total, expected_cash = totals
    return ClosingView(
        business_date=day,
        transaction_totals_by_method=transactions,
        expense_totals_by_category=expenses,
        expense_total_paise=expense_total,
        expected_cash_paise=expected_cash,
        counted_cash_paise=counted,
        cash_variance_paise=variance,
        notes=notes,
        closed_at=closed_at,
    )


@router.get("/{business_date}", response_model=ClosingView)
def get_closing(
    business_date: date,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("closing:read")),
) -> ClosingView:
    closing = db.scalar(select(DailyClosing).where(DailyClosing.business_date == business_date))
    if closing is not None:
        expected = closing.transaction_totals_by_method.get("net_by_method", {}).get("cash", 0)
        return ClosingView(
            business_date=business_date,
            transaction_totals_by_method=closing.transaction_totals_by_method,
            expense_totals_by_category=closing.expense_totals_by_category,
            expense_total_paise=closing.expense_total_paise,
            expected_cash_paise=expected,
            counted_cash_paise=closing.counted_cash_paise,
            cash_variance_paise=closing.cash_variance_paise,
            notes=closing.notes,
            closed_at=closing.closed_at,
        )
    return _view(business_date, _totals(db, business_date))


@router.post("/{business_date}/close", response_model=ClosingView, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_same_origin)])
def close_day(
    business_date: date,
    payload: ClosingSubmit,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("closing:write")),
) -> ClosingView:
    if db.scalar(select(DailyClosing.id).where(DailyClosing.business_date == business_date)) is not None:
        raise HTTPException(status_code=409, detail="This day has already been closed")
    totals = _totals(db, business_date)
    transaction_totals, expense_totals, expense_total, expected_cash = totals
    variance = payload.counted_cash_paise - expected_cash
    closing = DailyClosing(
        business_date=business_date,
        closed_by_user_id=actor.id,
        transaction_totals_by_method=transaction_totals,
        expense_totals_by_category=expense_totals,
        expense_total_paise=expense_total,
        counted_cash_paise=payload.counted_cash_paise,
        cash_variance_paise=variance,
        notes=payload.notes,
    )
    db.add(closing)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="daily_closing.created",
            entity_type="daily_closing",
            entity_id=closing.id,
            before_after_summary={"business_date": business_date.isoformat(), "cash_variance_paise": variance},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This day was closed by another staff member")
    return _view(
        business_date,
        totals,
        counted=payload.counted_cash_paise,
        variance=variance,
        notes=payload.notes,
        closed_at=closing.closed_at,
    )

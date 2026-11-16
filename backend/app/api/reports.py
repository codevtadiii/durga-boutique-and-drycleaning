import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.config import get_settings
from app.models import AuditLog, Customer, Expense, Order, OrderItem, Payment, PaymentAllocation, Refund, User

router = APIRouter(prefix="/api/v1/staff", tags=["analytics and reports"])


def _window(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=422, detail="Choose a period of 367 days or less")
    zone = ZoneInfo(get_settings().business_timezone)
    return datetime.combine(start_date, time.min, zone), datetime.combine(end_date + timedelta(days=1), time.min, zone)


def _sum(db: Session, column, *conditions) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(column), 0)).where(*conditions)) or 0)


def _period_summary(db: Session, start: datetime, end: datetime) -> dict[str, int]:
    finalized_sales = _sum(
        db,
        Order.confirmed_total_paise,
        Order.confirmed_at >= start,
        Order.confirmed_at < end,
        Order.confirmed_total_paise.is_not(None),
        Order.status != "cancelled",
    )
    order_count = int(
        db.scalar(
            select(func.count(Order.id)).where(
                Order.confirmed_at >= start,
                Order.confirmed_at < end,
                Order.confirmed_total_paise.is_not(None),
                Order.status != "cancelled",
            )
        )
        or 0
    )
    collections = _sum(db, Payment.amount_paise, Payment.status == "successful", Payment.paid_at >= start, Payment.paid_at < end)
    refunds = _sum(db, Refund.amount_paise, Refund.refunded_at >= start, Refund.refunded_at < end)
    expenses = _sum(db, Expense.amount_paise, Expense.spent_at >= start, Expense.spent_at < end)

    paid_by_order = (
        select(PaymentAllocation.order_id.label("order_id"), func.sum(PaymentAllocation.amount_paise).label("amount"))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(Payment.status == "successful")
        .group_by(PaymentAllocation.order_id)
        .subquery()
    )
    refund_by_order = (
        select(PaymentAllocation.order_id.label("order_id"), func.sum(Refund.amount_paise).label("amount"))
        .join(Refund, Refund.payment_id == PaymentAllocation.payment_id)
        .group_by(PaymentAllocation.order_id)
        .subquery()
    )
    balances = db.execute(
        select(
            Order.confirmed_total_paise,
            func.coalesce(paid_by_order.c.amount, 0),
            func.coalesce(refund_by_order.c.amount, 0),
        )
        .outerjoin(paid_by_order, paid_by_order.c.order_id == Order.id)
        .outerjoin(refund_by_order, refund_by_order.c.order_id == Order.id)
        .where(Order.confirmed_total_paise.is_not(None), Order.status != "cancelled")
    )
    outstanding = sum(int(total or 0) - int(paid or 0) + int(refunded or 0) for total, paid, refunded in balances)
    new_customers = int(
        db.scalar(select(func.count(Customer.id)).where(Customer.created_at >= start, Customer.created_at < end)) or 0
    )
    previous_customer_ids = select(Order.customer_id).where(Order.confirmed_at < start, Order.customer_id.is_not(None))
    returning_customers = int(
        db.scalar(
            select(func.count(func.distinct(Order.customer_id))).where(
                Order.confirmed_at >= start,
                Order.confirmed_at < end,
                Order.customer_id.in_(previous_customer_ids),
            )
        )
        or 0
    )
    delayed_orders = int(
        db.scalar(
            select(func.count(Order.id)).where(
                Order.expected_delivery_at < datetime.now(timezone.utc),
                Order.status.not_in(["delivered", "cancelled"]),
            )
        )
        or 0
    )
    return {
        "finalized_order_value_paise": finalized_sales,
        "collections_paise": collections,
        "refunds_paise": refunds,
        "expenses_paise": expenses,
        "net_cash_flow_paise": collections - refunds - expenses,
        "outstanding_balance_paise": outstanding,
        "average_order_value_paise": finalized_sales // order_count if order_count else 0,
        "finalized_orders": order_count,
        "new_customers": new_customers,
        "returning_customers": returning_customers,
        "delayed_orders": delayed_orders,
    }


def _growth(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) * 100 / previous, 1)


@router.get("/analytics/summary")
def analytics_summary(
    from_date: date = Query(),
    to_date: date = Query(),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics:read")),
) -> dict:
    start, end = _window(from_date, to_date)
    period_days = (to_date - from_date).days + 1
    previous_start = start - timedelta(days=period_days)
    previous = _period_summary(db, previous_start, start)
    current = _period_summary(db, start, end)
    current["growth_percent"] = {
        key: _growth(current[key], previous[key])
        for key in ("finalized_order_value_paise", "collections_paise", "new_customers", "finalized_orders")
    }
    current["previous_period"] = previous
    current["from_date"] = from_date.isoformat()
    current["to_date"] = to_date.isoformat()
    return current


@router.get("/analytics/services")
def analytics_services(
    from_date: date = Query(),
    to_date: date = Query(),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics:read")),
) -> list[dict]:
    start, end = _window(from_date, to_date)
    rows = db.execute(
        select(
            OrderItem.service_name_snapshot,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.line_total_paise),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.confirmed_at >= start, Order.confirmed_at < end, Order.status != "cancelled")
        .group_by(OrderItem.service_name_snapshot)
        .order_by(func.sum(OrderItem.quantity).desc())
    )
    return [
        {"service": name, "garments": int(quantity or 0), "finalized_order_value_paise": int(total or 0)}
        for name, quantity, total in rows
    ]


@router.get("/reports/{report_name}.csv")
def export_report(
    report_name: str,
    from_date: date = Query(),
    to_date: date = Query(),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("report:export")),
) -> Response:
    start, end = _window(from_date, to_date)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if report_name == "orders":
        writer.writerow(["Order number", "Customer ID", "Status", "Finalized value (paise)", "Expected delivery"])
        rows = db.scalars(
            select(Order)
            .where(Order.created_at >= start, Order.created_at < end)
            .order_by(Order.created_at)
            .limit(10000)
        )
        for order in rows:
            writer.writerow([order.order_number, order.customer_id or "", _safe_cell(order.status), order.confirmed_total_paise or "", order.expected_delivery_at or ""])
    elif report_name == "collections":
        writer.writerow(["Payment ID", "Customer ID", "Method", "Amount (paise)", "Reference", "Paid at"])
        rows = db.scalars(
            select(Payment)
            .where(Payment.paid_at >= start, Payment.paid_at < end, Payment.status == "successful")
            .order_by(Payment.paid_at)
            .limit(10000)
        )
        for payment in rows:
            writer.writerow([payment.id, payment.customer_id, _safe_cell(payment.method), payment.amount_paise, _safe_cell(payment.transaction_reference or ""), payment.paid_at.isoformat()])
    elif report_name == "expenses":
        writer.writerow(["Expense ID", "Category ID", "Amount (paise)", "Description", "Spent at"])
        rows = db.scalars(
            select(Expense)
            .where(Expense.spent_at >= start, Expense.spent_at < end)
            .order_by(Expense.spent_at)
            .limit(10000)
        )
        for expense in rows:
            writer.writerow([expense.id, expense.category_id, expense.amount_paise, _safe_cell(expense.description or ""), expense.spent_at.isoformat()])
    else:
        raise HTTPException(status_code=404, detail="Choose orders, collections, or expenses")

    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="report.exported",
            entity_type="report",
            before_after_summary={"report": report_name, "from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
        )
    )
    db.commit()
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="durga-{report_name}-{from_date}-{to_date}.csv"'},
    )


def _safe_cell(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value

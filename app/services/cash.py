from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cash import CashMovement, CashMovementType, CashSession, CashSessionStatus
from app.models.sale import Payment, PaymentMethod, Sale, SaleStatus
from app.schemas.cash import CashSummary

ZERO = Decimal("0.00")


def get_open_session(db: Session) -> CashSession | None:
    return db.scalar(select(CashSession).where(CashSession.status == CashSessionStatus.ABIERTA))


def require_open_session(db: Session) -> CashSession:
    session = get_open_session(db)
    if session is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay una caja abierta")
    return session


def session_summary(db: Session, session: CashSession) -> CashSummary:
    paid_sales = (Sale.cash_session_id == session.id, Sale.status == SaleStatus.PAGADA)

    sales_count, sales_total = db.execute(
        select(func.count(Sale.id), func.coalesce(func.sum(Sale.total), ZERO)).where(*paid_sales)
    ).one()

    by_method = {method: ZERO for method in PaymentMethod}
    for method, amount in db.execute(
        select(Payment.method, func.sum(Payment.amount))
        .join(Sale)
        .where(*paid_sales)
        .group_by(Payment.method)
    ):
        by_method[method] = amount

    movements = dict(
        db.execute(
            select(CashMovement.type, func.sum(CashMovement.amount))
            .where(CashMovement.session_id == session.id)
            .group_by(CashMovement.type)
        ).all()
    )
    cash_in = movements.get(CashMovementType.INGRESO, ZERO)
    cash_out = movements.get(CashMovementType.EGRESO, ZERO)

    return CashSummary(
        sales_count=sales_count,
        sales_total=sales_total,
        by_method=by_method,
        cash_in=cash_in,
        cash_out=cash_out,
        expected_cash=session.opening_amount + by_method[PaymentMethod.EFECTIVO] + cash_in - cash_out,
    )

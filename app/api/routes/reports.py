from datetime import date, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import DbSession, StaffUser
from app.core.config import settings
from app.core.timeutils import local_datetime
from app.models.sale import Sale, SaleStatus
from app.schemas.report import DaySales

router = APIRouter(prefix="/reports", tags=["Reportes"])

MAX_RANGE_DAYS = 92


@router.get("/daily-sales", response_model=list[DaySales])
def daily_sales(db: DbSession, _: StaffUser, date_from: date, date_to: date):
    """Total cobrado y número de ventas por día (días sin ventas incluidos, en 0)."""
    if date_to < date_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "date_to es anterior a date_from")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"El rango máximo es de {MAX_RANGE_DAYS} días"
        )

    local_day = func.date(func.timezone(settings.timezone, Sale.created_at))
    rows = db.execute(
        select(local_day, func.sum(Sale.total), func.count(Sale.id))
        .where(
            Sale.status == SaleStatus.PAGADA,
            Sale.created_at >= local_datetime(date_from, time.min),
            Sale.created_at < local_datetime(date_to + timedelta(days=1), time.min),
        )
        .group_by(local_day)
    ).all()
    by_day = {day: (total, count) for day, total, count in rows}

    result = []
    day = date_from
    while day <= date_to:
        total, count = by_day.get(day, (Decimal("0.00"), 0))
        result.append(DaySales(day=day, total=total, count=count))
        day += timedelta(days=1)
    return result

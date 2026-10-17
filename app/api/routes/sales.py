from datetime import date, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession, StaffUser, get_or_404
from app.core.timeutils import local_datetime, now
from app.models.cash import CashSessionStatus
from app.models.sale import Sale, SaleStatus
from app.schemas.sale import SaleCreate, SaleRead, SaleVoid
from app.services.sales import create_sale

router = APIRouter(prefix="/sales", tags=["Caja y ventas"])


@router.post("", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
def register_sale(data: SaleCreate, db: DbSession, user: StaffUser):
    """Cobra servicios. Con `appointment_id` y sin `items`, cobra los servicios de la cita
    y la marca como completada. La suma de `payments` debe ser igual al total."""
    return create_sale(db, data, user)


@router.get("", response_model=list[SaleRead])
def list_sales(
    db: DbSession,
    _: StaffUser,
    date_from: date | None = Query(default=None, description="Por defecto, hoy"),
    date_to: date | None = Query(default=None, description="Inclusive. Por defecto, igual a date_from"),
    client_id: int | None = None,
    cash_session_id: int | None = None,
    status_in: SaleStatus | None = Query(default=None, alias="status"),
):
    date_from = date_from or now().date()
    date_to = date_to or date_from
    stmt = (
        select(Sale)
        .options(selectinload(Sale.items), selectinload(Sale.payments), selectinload(Sale.client))
        .where(
            Sale.created_at >= local_datetime(date_from, time.min),
            Sale.created_at < local_datetime(date_to + timedelta(days=1), time.min),
        )
        .order_by(Sale.created_at.desc())
    )
    if client_id is not None:
        stmt = stmt.where(Sale.client_id == client_id)
    if cash_session_id is not None:
        stmt = stmt.where(Sale.cash_session_id == cash_session_id)
    if status_in is not None:
        stmt = stmt.where(Sale.status == status_in)
    return db.scalars(stmt).all()


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: int, db: DbSession, _: StaffUser):
    return get_or_404(db, Sale, sale_id, "Venta no encontrada")


@router.post("/{sale_id}/void", response_model=SaleRead)
def void_sale(sale_id: int, data: SaleVoid, db: DbSession, admin: AdminUser):
    """Anula una venta. Solo es posible mientras su caja siga abierta."""
    sale = get_or_404(db, Sale, sale_id, "Venta no encontrada")
    if sale.status == SaleStatus.ANULADA:
        raise HTTPException(status.HTTP_409_CONFLICT, "La venta ya está anulada")
    if sale.cash_session.status != CashSessionStatus.ABIERTA:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Solo se pueden anular ventas de la caja abierta"
        )
    sale.status = SaleStatus.ANULADA
    sale.voided_at = now()
    sale.voided_by_id = admin.id
    sale.void_reason = data.reason
    db.commit()
    return sale

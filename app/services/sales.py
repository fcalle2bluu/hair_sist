from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_or_404
from app.models.appointment import Appointment, AppointmentStatus, RELEASED_STATUSES
from app.models.client import Client
from app.models.employee import Employee
from app.models.sale import Payment, Sale, SaleItem, SaleStatus
from app.models.service import Service
from app.models.user import User
from app.schemas.sale import SaleCreate, SaleItemCreate
from app.services.cash import ZERO, require_open_session


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)


def create_sale(db: Session, data: SaleCreate, user: User) -> Sale:
    session = require_open_session(db)

    appointment: Appointment | None = None
    client_id = data.client_id
    if data.appointment_id is not None:
        appointment = get_or_404(db, Appointment, data.appointment_id, "Cita no encontrada")
        if appointment.status in RELEASED_STATUSES:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "No se puede cobrar una cita cancelada o sin asistencia"
            )
        if any(s.status == SaleStatus.PAGADA for s in appointment.sales):
            raise HTTPException(status.HTTP_409_CONFLICT, "Esta cita ya fue cobrada")
        if client_id is None:
            client_id = appointment.client_id
        elif client_id != appointment.client_id:
            raise _unprocessable("El cliente no coincide con el de la cita")
    if client_id is not None:
        get_or_404(db, Client, client_id, "Cliente no encontrado")

    item_inputs = data.items
    if not item_inputs:
        if appointment is None:
            raise _unprocessable("La venta debe tener al menos un item")
        item_inputs = [
            SaleItemCreate(
                service_id=s.service_id, employee_id=appointment.employee_id, unit_price=s.price
            )
            for s in appointment.services
        ]

    services = {
        s.id: s
        for s in db.scalars(
            select(Service).where(Service.id.in_({i.service_id for i in item_inputs}))
        )
    }
    employee_ids = {i.employee_id for i in item_inputs if i.employee_id is not None}
    found_employees = set(db.scalars(select(Employee.id).where(Employee.id.in_(employee_ids))))
    if missing := employee_ids - found_employees:
        raise _unprocessable(f"Estilistas no encontrados: {sorted(missing)}")

    items: list[SaleItem] = []
    for item in item_inputs:
        service = services.get(item.service_id)
        if service is None:
            raise _unprocessable(f"Servicio no encontrado: {item.service_id}")
        unit_price = service.price if item.unit_price is None else item.unit_price
        gross = unit_price * item.quantity
        if item.discount > gross:
            raise _unprocessable(f"El descuento de '{service.name}' supera su importe")
        items.append(
            SaleItem(
                service_id=service.id,
                employee_id=item.employee_id,
                description=service.name,
                quantity=item.quantity,
                unit_price=unit_price,
                discount=item.discount,
                total=gross - item.discount,
            )
        )

    subtotal = sum((i.total for i in items), ZERO)
    if data.discount > subtotal:
        raise _unprocessable("El descuento supera el subtotal")
    total = subtotal - data.discount

    paid = sum((p.amount for p in data.payments), ZERO)
    if paid != total:
        raise _unprocessable(f"Los pagos ({paid}) no coinciden con el total ({total})")

    sale = Sale(
        cash_session_id=session.id,
        client_id=client_id,
        appointment_id=appointment.id if appointment else None,
        subtotal=subtotal,
        discount=data.discount,
        total=total,
        notes=data.notes,
        created_by_id=user.id,
        items=items,
        payments=[Payment(**p.model_dump()) for p in data.payments],
    )
    db.add(sale)
    if appointment is not None:
        appointment.status = AppointmentStatus.COMPLETADA

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta cita ya fue cobrada") from exc
    db.refresh(sale)
    return sale

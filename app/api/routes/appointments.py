from datetime import date, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, DbSession, StaffUser, get_or_404
from app.core.config import settings
from app.core.timeutils import local_datetime, localize, now
from app.models.appointment import (
    RELEASED_STATUSES,
    Appointment,
    AppointmentService,
    AppointmentStatus,
)
from app.models.client import Client
from app.models.employee import Employee
from app.models.service import Service
from app.models.user import Role, User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatusChange,
    AppointmentUpdate,
    AvailabilitySlots,
)
from app.schemas.report import DayCount
from app.services.scheduling import (
    EDITABLE_STATUSES,
    available_slots,
    check_transition,
    commit_appointment,
    load_services,
    validate_slot,
)

router = APIRouter(prefix="/appointments", tags=["Agenda y citas"])

MAX_RANGE_DAYS = 62
# Estados que un estilista puede marcar en sus propias citas.
STYLIST_STATUSES = {AppointmentStatus.EN_CURSO, AppointmentStatus.COMPLETADA}

_load_options = (
    selectinload(Appointment.services).selectinload(AppointmentService.service),
    selectinload(Appointment.employee),
    selectinload(Appointment.client),
    selectinload(Appointment.sales),
)


def _stylist_employee_id(user: User) -> int | None:
    """Para estilistas devuelve su id de estilista; para el resto, None (sin restricción)."""
    if user.role != Role.ESTILISTA:
        return None
    if user.employee is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Tu usuario no está vinculado a ningún estilista"
        )
    return user.employee.id


def _get_appointment(db: Session, appointment_id: int, user: User) -> Appointment:
    appointment = get_or_404(db, Appointment, appointment_id, "Cita no encontrada")
    own_id = _stylist_employee_id(user)
    if own_id is not None and appointment.employee_id != own_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo puedes ver tus propias citas")
    return appointment


def _active_client(db: Session, client_id: int) -> Client:
    client = get_or_404(db, Client, client_id, "Cliente no encontrado")
    if not client.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El cliente está desactivado")
    return client


def _lines(services: list[Service]) -> list[AppointmentService]:
    return [
        AppointmentService(service=s, price=s.price, duration_minutes=s.duration_minutes)
        for s in services
    ]


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    db: DbSession,
    user: CurrentUser,
    date_from: date | None = Query(default=None, description="Por defecto, hoy"),
    date_to: date | None = Query(default=None, description="Inclusive. Por defecto, igual a date_from"),
    employee_id: int | None = None,
    client_id: int | None = None,
    status_in: list[AppointmentStatus] | None = Query(default=None, alias="status"),
):
    """Agenda por rango de fechas. Los estilistas solo ven sus propias citas."""
    date_from = date_from or now().date()
    date_to = date_to or date_from
    if date_to < date_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "date_to es anterior a date_from")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"El rango máximo es de {MAX_RANGE_DAYS} días"
        )

    stmt = (
        select(Appointment)
        .options(*_load_options)
        .where(
            Appointment.start_at >= local_datetime(date_from, time.min),
            Appointment.start_at < local_datetime(date_to + timedelta(days=1), time.min),
        )
        .order_by(Appointment.start_at)
    )
    own_id = _stylist_employee_id(user)
    if own_id is not None:
        employee_id = own_id
    if employee_id is not None:
        stmt = stmt.where(Appointment.employee_id == employee_id)
    if client_id is not None:
        stmt = stmt.where(Appointment.client_id == client_id)
    if status_in:
        stmt = stmt.where(Appointment.status.in_(status_in))
    return db.scalars(stmt).all()


@router.get("/availability", response_model=AvailabilitySlots)
def availability(
    db: DbSession,
    _: CurrentUser,
    employee_id: int,
    day: date,
    service_ids: list[int] = Query(min_length=1),
):
    """Horarios libres de un estilista en un día para los servicios indicados."""
    employee = get_or_404(db, Employee, employee_id, "Estilista no encontrado")
    services = load_services(db, service_ids)
    duration = sum(s.duration_minutes for s in services)
    return AvailabilitySlots(
        employee_id=employee.id,
        duration_minutes=duration,
        slots=available_slots(db, employee, day, duration),
    )


@router.get("/calendar", response_model=list[DayCount])
def calendar(
    db: DbSession,
    user: CurrentUser,
    month: str = Query(pattern=r"^\d{4}-\d{2}$", description="Mes en formato AAAA-MM"),
    employee_id: int | None = None,
):
    """Cantidad de citas activas por día del mes (para el calendario mensual)."""
    year, mon = map(int, month.split("-"))
    if not 1 <= mon <= 12:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Mes inválido")
    first = date(year, mon, 1)
    next_month = date(year + mon // 12, mon % 12 + 1, 1)

    local_day = func.date(func.timezone(settings.timezone, Appointment.start_at))
    stmt = (
        select(local_day, func.count(Appointment.id))
        .where(
            Appointment.start_at >= local_datetime(first, time.min),
            Appointment.start_at < local_datetime(next_month, time.min),
            Appointment.status.not_in(RELEASED_STATUSES),
        )
        .group_by(local_day)
        .order_by(local_day)
    )
    own_id = _stylist_employee_id(user)
    if own_id is not None:
        employee_id = own_id
    if employee_id is not None:
        stmt = stmt.where(Appointment.employee_id == employee_id)
    return [DayCount(day=day, count=count) for day, count in db.execute(stmt)]


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(data: AppointmentCreate, db: DbSession, user: StaffUser):
    client = _active_client(db, data.client_id)
    employee = get_or_404(db, Employee, data.employee_id, "Estilista no encontrado")
    services = load_services(db, data.service_ids)

    start = localize(data.start_at)
    end = start + timedelta(minutes=sum(s.duration_minutes for s in services))
    validate_slot(db, employee, services, start, end)

    appointment = Appointment(
        client=client,
        employee=employee,
        start_at=start,
        end_at=end,
        notes=data.notes,
        created_by_id=user.id,
        services=_lines(services),
    )
    db.add(appointment)
    commit_appointment(db)
    return appointment


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(appointment_id: int, db: DbSession, user: CurrentUser):
    return _get_appointment(db, appointment_id, user)


@router.patch("/{appointment_id}", response_model=AppointmentRead)
def update_appointment(
    appointment_id: int, data: AppointmentUpdate, db: DbSession, user: StaffUser
):
    """Reprograma (fecha, estilista, servicios) o edita notas de una cita pendiente o confirmada."""
    appointment = _get_appointment(db, appointment_id, user)
    if appointment.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Solo se pueden editar citas pendientes o confirmadas (estado actual: {appointment.status})",
        )

    if data.client_id is not None:
        appointment.client = _active_client(db, data.client_id)
    if "notes" in data.model_fields_set:
        appointment.notes = data.notes

    if data.employee_id is not None or data.start_at is not None or data.service_ids is not None:
        employee = (
            get_or_404(db, Employee, data.employee_id, "Estilista no encontrado")
            if data.employee_id is not None
            else appointment.employee
        )
        start = localize(data.start_at) if data.start_at is not None else appointment.start_at
        if data.service_ids is not None:
            services = load_services(db, data.service_ids)
            duration = sum(s.duration_minutes for s in services)
        else:
            services = [line.service for line in appointment.services]
            duration = sum(line.duration_minutes for line in appointment.services)
        end = start + timedelta(minutes=duration)

        validate_slot(db, employee, services, start, end, exclude_appointment_id=appointment.id)
        appointment.employee = employee
        appointment.start_at = start
        appointment.end_at = end
        if data.service_ids is not None:
            appointment.services = _lines(services)

    commit_appointment(db)
    return appointment


@router.post("/{appointment_id}/status", response_model=AppointmentRead)
def change_status(
    appointment_id: int, data: AppointmentStatusChange, db: DbSession, user: CurrentUser
):
    """Confirmar, iniciar, completar, cancelar o marcar inasistencia.

    Los estilistas solo pueden marcar sus propias citas como en curso o completadas.
    """
    appointment = _get_appointment(db, appointment_id, user)
    if user.role == Role.ESTILISTA and data.status not in STYLIST_STATUSES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permiso para ese cambio de estado")
    check_transition(appointment.status, data.status)

    appointment.status = data.status
    if data.status in (AppointmentStatus.CANCELADA, AppointmentStatus.NO_ASISTIO):
        appointment.cancel_reason = data.reason
    db.commit()
    return appointment

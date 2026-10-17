"""Reglas de agenda: servicios válidos, horario del estilista, ausencias y cruces de citas."""

from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutils import local_datetime, now, to_local
from app.models.appointment import Appointment, AppointmentStatus, RELEASED_STATUSES
from app.models.employee import Employee, EmployeeTimeOff
from app.models.service import Service

S = AppointmentStatus
ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    S.PENDIENTE: {S.CONFIRMADA, S.EN_CURSO, S.COMPLETADA, S.CANCELADA, S.NO_ASISTIO},
    S.CONFIRMADA: {S.EN_CURSO, S.COMPLETADA, S.CANCELADA, S.NO_ASISTIO},
    S.EN_CURSO: {S.COMPLETADA},
    S.COMPLETADA: set(),
    S.CANCELADA: set(),
    S.NO_ASISTIO: set(),
}
EDITABLE_STATUSES = (S.PENDIENTE, S.CONFIRMADA)


def load_services(db: Session, service_ids: list[int]) -> list[Service]:
    if len(set(service_ids)) != len(service_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Hay servicios repetidos")
    found = {s.id: s for s in db.scalars(select(Service).where(Service.id.in_(service_ids)))}
    missing = [i for i in service_ids if i not in found]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Servicios no encontrados: {missing}")
    inactive = [found[i].name for i in service_ids if not found[i].is_active]
    if inactive:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Servicios inactivos: {', '.join(inactive)}"
        )
    return [found[i] for i in service_ids]


def fits_schedule(employee: Employee, start: datetime, end: datetime) -> bool:
    local_start, local_end = to_local(start), to_local(end)
    if local_start.date() != local_end.date():
        return False
    return any(
        block.weekday == local_start.weekday()
        and block.start_time <= local_start.time()
        and local_end.time() <= block.end_time
        for block in employee.schedules
    )


def _overlapping_appointments(employee_id: int, start: datetime, end: datetime):
    return select(Appointment).where(
        Appointment.employee_id == employee_id,
        Appointment.status.not_in(RELEASED_STATUSES),
        Appointment.start_at < end,
        Appointment.end_at > start,
    )


def _overlapping_time_off(employee_id: int, start: datetime, end: datetime):
    return select(EmployeeTimeOff).where(
        EmployeeTimeOff.employee_id == employee_id,
        EmployeeTimeOff.start_at < end,
        EmployeeTimeOff.end_at > start,
    )


def validate_slot(
    db: Session,
    employee: Employee,
    services: list[Service],
    start: datetime,
    end: datetime,
    exclude_appointment_id: int | None = None,
) -> None:
    if not employee.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El estilista no está activo")

    offered = {s.id for s in employee.services}
    not_offered = [s.name for s in services if s.id not in offered]
    if not_offered:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{employee.first_name} no realiza: {', '.join(not_offered)}",
        )

    if not fits_schedule(employee, start, end):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "La cita está fuera del horario de trabajo del estilista"
        )

    if db.scalar(_overlapping_time_off(employee.id, start, end).limit(1)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El estilista tiene una ausencia registrada en ese horario"
        )

    stmt = _overlapping_appointments(employee.id, start, end)
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    if db.scalar(stmt.limit(1)):
        raise HTTPException(status.HTTP_409_CONFLICT, "El estilista ya tiene una cita en ese horario")


def commit_appointment(db: Session) -> None:
    """Confirma cambios traduciendo el choque de la restricción de exclusión a un 409."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23P01":  # exclusion_violation
            raise HTTPException(
                status.HTTP_409_CONFLICT, "El estilista ya tiene una cita en ese horario"
            ) from exc
        raise


def check_transition(current: AppointmentStatus, new: AppointmentStatus) -> None:
    if new not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"No se puede pasar una cita de '{current}' a '{new}'"
        )


def available_slots(
    db: Session, employee: Employee, day: date, duration_minutes: int
) -> list[datetime]:
    """Horarios de inicio libres para un servicio de la duración indicada."""
    step = timedelta(minutes=settings.slot_minutes)
    length = timedelta(minutes=duration_minutes)
    day_start = local_datetime(day, time.min)
    day_end = day_start + timedelta(days=1)

    busy = [
        (a.start_at, a.end_at)
        for a in db.scalars(_overlapping_appointments(employee.id, day_start, day_end))
    ]
    busy += [
        (t.start_at, t.end_at)
        for t in db.scalars(_overlapping_time_off(employee.id, day_start, day_end))
    ]

    current = now()
    slots: list[datetime] = []
    for block in employee.schedules:
        if block.weekday != day.weekday():
            continue
        slot = local_datetime(day, block.start_time)
        block_end = local_datetime(day, block.end_time)
        while slot + length <= block_end:
            slot_end = slot + length
            if slot >= current and not any(slot < b_end and slot_end > b_start for b_start, b_end in busy):
                slots.append(slot)
            slot += step
    return slots

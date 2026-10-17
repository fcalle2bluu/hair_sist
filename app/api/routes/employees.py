from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AdminUser, CurrentUser, DbSession, get_or_404
from app.core.timeutils import localize
from app.models.employee import Employee, EmployeeSchedule, EmployeeTimeOff, employee_services
from app.models.service import Service
from app.models.user import User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeDetail,
    EmployeeRead,
    EmployeeUpdate,
    ScheduleBlock,
    ScheduleBlockRead,
    ServiceIds,
    TimeOffCreate,
    TimeOffRead,
)

router = APIRouter(prefix="/employees", tags=["Estilistas"])


def _get_employee(db: Session, employee_id: int) -> Employee:
    return get_or_404(db, Employee, employee_id, "Estilista no encontrado")


def _load_services(db: Session, service_ids: list[int]) -> list[Service]:
    unique_ids = set(service_ids)
    services = db.scalars(select(Service).where(Service.id.in_(unique_ids))).all()
    if missing := unique_ids - {s.id for s in services}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Servicios no encontrados: {sorted(missing)}"
        )
    return list(services)


def _check_user_link(db: Session, user_id: int | None, employee_id: int | None = None) -> None:
    if user_id is None:
        return
    get_or_404(db, User, user_id, "Usuario no encontrado")
    stmt = select(Employee.id).where(Employee.user_id == user_id)
    if employee_id is not None:
        stmt = stmt.where(Employee.id != employee_id)
    if db.scalar(stmt):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese usuario ya está vinculado a otro estilista")


@router.get("", response_model=list[EmployeeDetail])
def list_employees(
    db: DbSession,
    _: CurrentUser,
    service_id: int | None = None,
    include_inactive: bool = False,
):
    """Lista estilistas. Con `service_id` devuelve solo quienes realizan ese servicio."""
    stmt = (
        select(Employee)
        .options(selectinload(Employee.services), selectinload(Employee.schedules))
        .order_by(Employee.first_name, Employee.last_name)
    )
    if not include_inactive:
        stmt = stmt.where(Employee.is_active.is_(True))
    if service_id is not None:
        stmt = stmt.join(employee_services).where(employee_services.c.service_id == service_id)
    return db.scalars(stmt).all()


@router.post("", response_model=EmployeeDetail, status_code=status.HTTP_201_CREATED)
def create_employee(data: EmployeeCreate, db: DbSession, _: AdminUser):
    _check_user_link(db, data.user_id)
    employee = Employee(**data.model_dump(exclude={"service_ids"}))
    employee.services = _load_services(db, data.service_ids)
    db.add(employee)
    db.commit()
    return employee


@router.get("/{employee_id}", response_model=EmployeeDetail)
def get_employee(employee_id: int, db: DbSession, _: CurrentUser):
    return _get_employee(db, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeDetail)
def update_employee(employee_id: int, data: EmployeeUpdate, db: DbSession, _: AdminUser):
    employee = _get_employee(db, employee_id)
    changes = data.model_dump(exclude_unset=True)
    if "user_id" in changes:
        _check_user_link(db, changes["user_id"], employee_id=employee.id)
    for field, value in changes.items():
        setattr(employee, field, value)
    db.commit()
    return employee


@router.put("/{employee_id}/services", response_model=EmployeeDetail)
def set_services(employee_id: int, data: ServiceIds, db: DbSession, _: AdminUser):
    """Reemplaza la lista de servicios (especialidades) que realiza el estilista."""
    employee = _get_employee(db, employee_id)
    employee.services = _load_services(db, data.service_ids)
    db.commit()
    return employee


# --- Horario semanal ---


@router.get("/{employee_id}/schedule", response_model=list[ScheduleBlockRead])
def get_schedule(employee_id: int, db: DbSession, _: CurrentUser):
    return _get_employee(db, employee_id).schedules


@router.put("/{employee_id}/schedule", response_model=list[ScheduleBlockRead])
def set_schedule(employee_id: int, blocks: list[ScheduleBlock], db: DbSession, _: AdminUser):
    """Reemplaza el horario semanal completo. Se permiten varios bloques por día."""
    employee = _get_employee(db, employee_id)
    ordered = sorted(blocks, key=lambda b: (b.weekday, b.start_time))
    for prev, curr in zip(ordered, ordered[1:]):
        if prev.weekday == curr.weekday and curr.start_time < prev.end_time:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Bloques superpuestos el día {curr.weekday}",
            )
    employee.schedules = [EmployeeSchedule(**b.model_dump()) for b in ordered]
    db.commit()
    db.refresh(employee)
    return employee.schedules


# --- Ausencias ---


@router.get("/{employee_id}/time-off", response_model=list[TimeOffRead])
def list_time_off(employee_id: int, db: DbSession, _: CurrentUser):
    return _get_employee(db, employee_id).time_off


@router.post(
    "/{employee_id}/time-off", response_model=TimeOffRead, status_code=status.HTTP_201_CREATED
)
def add_time_off(employee_id: int, data: TimeOffCreate, db: DbSession, _: AdminUser):
    _get_employee(db, employee_id)
    time_off = EmployeeTimeOff(
        employee_id=employee_id,
        start_at=localize(data.start_at),
        end_at=localize(data.end_at),
        reason=data.reason,
    )
    db.add(time_off)
    db.commit()
    return time_off


@router.delete("/{employee_id}/time-off/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_off(employee_id: int, time_off_id: int, db: DbSession, _: AdminUser):
    time_off = db.get(EmployeeTimeOff, time_off_id)
    if time_off is None or time_off.employee_id != employee_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausencia no encontrada")
    db.delete(time_off)
    db.commit()

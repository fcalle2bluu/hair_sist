from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.appointment import AppointmentStatus
from app.schemas.client import ClientBrief
from app.schemas.common import ORMModel
from app.schemas.employee import EmployeeBrief


class AppointmentCreate(BaseModel):
    client_id: int
    employee_id: int
    start_at: datetime = Field(description="Si no incluye zona horaria se toma la del salón")
    service_ids: list[int] = Field(min_length=1)
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    """Reprogramar o editar una cita pendiente o confirmada."""

    client_id: int | None = None
    employee_id: int | None = None
    start_at: datetime | None = None
    service_ids: list[int] | None = Field(default=None, min_length=1)
    notes: str | None = None


class AppointmentStatusChange(BaseModel):
    status: AppointmentStatus
    reason: str | None = Field(default=None, max_length=255)


class AppointmentServiceRead(ORMModel):
    service_id: int
    service_name: str
    price: Decimal
    duration_minutes: int


class AppointmentRead(ORMModel):
    id: int
    client: ClientBrief
    employee: EmployeeBrief
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    notes: str | None
    cancel_reason: str | None
    services: list[AppointmentServiceRead]
    total_price: Decimal
    is_paid: bool
    created_at: datetime


class AvailabilitySlots(BaseModel):
    employee_id: int
    duration_minutes: int
    slots: list[datetime]

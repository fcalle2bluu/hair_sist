from datetime import datetime, time

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.common import ORMModel
from app.schemas.service import ServiceBrief


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    color: str = Field(default="#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    user_id: int | None = None
    service_ids: list[int] = []


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    user_id: int | None = None
    is_active: bool | None = None


class ScheduleBlock(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = lunes ... 6 = domingo")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def check_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        return self


class ScheduleBlockRead(ScheduleBlock, ORMModel):
    id: int


class ServiceIds(BaseModel):
    service_ids: list[int]


class TimeOffCreate(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def check_order(self):
        if self.end_at <= self.start_at:
            raise ValueError("La fecha de fin debe ser posterior a la de inicio")
        return self


class TimeOffRead(ORMModel):
    id: int
    start_at: datetime
    end_at: datetime
    reason: str | None


class EmployeeRead(ORMModel):
    id: int
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    color: str
    user_id: int | None
    is_active: bool
    services: list[ServiceBrief]


class EmployeeDetail(EmployeeRead):
    schedules: list[ScheduleBlockRead]


class EmployeeBrief(ORMModel):
    id: int
    first_name: str
    last_name: str
    color: str

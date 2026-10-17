from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Table,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.service import Service
from app.models.user import User

employee_services = Table(
    "employee_services",
    Base.metadata,
    Column("employee_id", ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
    Column("service_id", ForeignKey("services.id", ondelete="CASCADE"), primary_key=True),
)


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(7), default="#8b5cf6")  # color en la agenda
    is_active: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User | None] = relationship(back_populates="employee")
    services: Mapped[list[Service]] = relationship(secondary=employee_services)
    schedules: Mapped[list["EmployeeSchedule"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="[EmployeeSchedule.weekday, EmployeeSchedule.start_time]",
    )
    time_off: Mapped[list["EmployeeTimeOff"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeTimeOff.start_at",
    )


class EmployeeSchedule(Base):
    """Bloque de trabajo semanal. Puede haber varios por día (ej. turno partido)."""

    __tablename__ = "employee_schedules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("end_time > start_time", name="time_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = lunes ... 6 = domingo
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    employee: Mapped[Employee] = relationship(back_populates="schedules")


class EmployeeTimeOff(Base):
    """Ausencias: vacaciones, permisos, citas médicas, etc."""

    __tablename__ = "employee_time_off"
    __table_args__ = (CheckConstraint("end_at > start_at", name="time_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))

    employee: Mapped[Employee] = relationship(back_populates="time_off")

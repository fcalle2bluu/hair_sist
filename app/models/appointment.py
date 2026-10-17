import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column
from app.models.client import Client
from app.models.employee import Employee
from app.models.service import Service

if TYPE_CHECKING:
    from app.models.sale import Sale


class AppointmentStatus(enum.StrEnum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    EN_CURSO = "en_curso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"
    NO_ASISTIO = "no_asistio"


# Estados que liberan el horario del estilista.
RELEASED_STATUSES = (AppointmentStatus.CANCELADA, AppointmentStatus.NO_ASISTIO)


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        # Garantía a nivel de base de datos: un estilista no puede tener dos citas
        # activas que se crucen (requiere la extensión btree_gist).
        ExcludeConstraint(
            ("employee_id", "="),
            (text("tstzrange(start_at, end_at)"), "&&"),
            name="excl_appointments_employee_overlap",
            using="gist",
            where=text("status NOT IN ('cancelada', 'no_asistio')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(
        enum_column(AppointmentStatus), default=AppointmentStatus.PENDIENTE
    )
    notes: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    client: Mapped[Client] = relationship()
    employee: Mapped[Employee] = relationship()
    services: Mapped[list["AppointmentService"]] = relationship(
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="AppointmentService.id",
    )
    sales: Mapped[list["Sale"]] = relationship(back_populates="appointment")

    @property
    def total_price(self) -> Decimal:
        return sum((s.price for s in self.services), Decimal("0"))

    @property
    def is_paid(self) -> bool:
        return any(sale.status == "pagada" for sale in self.sales)


class AppointmentService(Base):
    """Servicio dentro de una cita. Copia precio y duración al momento de agendar."""

    __tablename__ = "appointment_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    duration_minutes: Mapped[int]

    appointment: Mapped[Appointment] = relationship(back_populates="services")
    service: Mapped[Service] = relationship()

    @property
    def service_name(self) -> str:
        return self.service.name

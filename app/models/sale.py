import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_column
from app.models.appointment import Appointment
from app.models.cash import CashSession
from app.models.client import Client
from app.models.employee import Employee
from app.models.service import Service
from app.models.user import User


class SaleStatus(enum.StrEnum):
    PAGADA = "pagada"
    ANULADA = "anulada"


class PaymentMethod(enum.StrEnum):
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"
    OTRO = "otro"


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        # Una cita solo puede cobrarse una vez (salvo que la venta se anule).
        Index(
            "uq_sales_appointment_paid",
            "appointment_id",
            unique=True,
            postgresql_where=text("status = 'pagada' AND appointment_id IS NOT NULL"),
        ),
        CheckConstraint("discount >= 0", name="discount_non_negative"),
        CheckConstraint("total >= 0", name="total_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"), index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    status: Mapped[SaleStatus] = mapped_column(enum_column(SaleStatus), default=SaleStatus.PAGADA)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    void_reason: Mapped[str | None] = mapped_column(String(255))

    cash_session: Mapped[CashSession] = relationship()
    client: Mapped[Client | None] = relationship()
    appointment: Mapped[Appointment | None] = relationship(back_populates="sales")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", order_by="SaleItem.id"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", order_by="Payment.id"
    )


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("discount >= 0", name="discount_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))
    # Quién realizó el servicio (base para comisiones).
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    sale: Mapped[Sale] = relationship(back_populates="items")
    service: Mapped[Service | None] = relationship()
    employee: Mapped[Employee | None] = relationship()


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(enum_column(PaymentMethod))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reference: Mapped[str | None] = mapped_column(String(100))

    sale: Mapped[Sale] = relationship(back_populates="payments")

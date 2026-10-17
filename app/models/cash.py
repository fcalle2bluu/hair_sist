import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_column
from app.models.user import User


class CashSessionStatus(enum.StrEnum):
    ABIERTA = "abierta"
    CERRADA = "cerrada"


class CashSession(Base):
    """Turno de caja: desde la apertura hasta el cierre con arqueo."""

    __tablename__ = "cash_sessions"
    __table_args__ = (
        # Solo puede haber una caja abierta a la vez.
        Index(
            "uq_cash_sessions_single_open",
            "status",
            unique=True,
            postgresql_where=text("status = 'abierta'"),
        ),
        CheckConstraint("opening_amount >= 0", name="opening_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[CashSessionStatus] = mapped_column(
        enum_column(CashSessionStatus), default=CashSessionStatus.ABIERTA
    )
    opened_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    opened_by: Mapped[User | None] = relationship(foreign_keys=[opened_by_id])
    closed_by: Mapped[User | None] = relationship(foreign_keys=[closed_by_id])
    movements: Mapped[list["CashMovement"]] = relationship(
        back_populates="session", order_by="CashMovement.created_at"
    )


class CashMovementType(enum.StrEnum):
    INGRESO = "ingreso"
    EGRESO = "egreso"


class CashMovement(Base):
    """Entradas o salidas de efectivo que no son ventas (ej. compra de insumos)."""

    __tablename__ = "cash_movements"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"), index=True)
    type: Mapped[CashMovementType] = mapped_column(enum_column(CashMovementType))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    concept: Mapped[str] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[CashSession] = relationship(back_populates="movements")

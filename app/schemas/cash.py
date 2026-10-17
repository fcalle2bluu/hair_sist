from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.cash import CashMovementType, CashSessionStatus
from app.models.sale import PaymentMethod
from app.schemas.common import ORMModel


class CashOpen(BaseModel):
    opening_amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    notes: str | None = None


class CashClose(BaseModel):
    counted_cash: Decimal = Field(
        ge=0, max_digits=10, decimal_places=2, description="Efectivo contado físicamente"
    )
    notes: str | None = None


class CashMovementCreate(BaseModel):
    type: CashMovementType
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    concept: str = Field(min_length=1, max_length=255)


class CashMovementRead(ORMModel):
    id: int
    type: CashMovementType
    amount: Decimal
    concept: str
    created_by_id: int | None
    created_at: datetime


class CashSummary(BaseModel):
    sales_count: int
    sales_total: Decimal
    by_method: dict[PaymentMethod, Decimal]
    cash_in: Decimal
    cash_out: Decimal
    expected_cash: Decimal


class CashSessionRead(ORMModel):
    id: int
    status: CashSessionStatus
    opened_by_id: int | None
    opened_at: datetime
    opening_amount: Decimal
    closed_by_id: int | None
    closed_at: datetime | None
    expected_cash: Decimal | None
    counted_cash: Decimal | None
    difference: Decimal | None
    notes: str | None


class CashSessionDetail(CashSessionRead):
    summary: CashSummary
    movements: list[CashMovementRead]

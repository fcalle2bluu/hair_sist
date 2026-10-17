from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.sale import PaymentMethod, SaleStatus
from app.schemas.client import ClientBrief
from app.schemas.common import ORMModel


class SaleItemCreate(BaseModel):
    service_id: int
    employee_id: int | None = Field(default=None, description="Estilista que realizó el servicio")
    quantity: int = Field(default=1, gt=0)
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2,
        description="Si se omite, se usa el precio del servicio",
    )
    discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)


class PaymentCreate(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)


class SaleCreate(BaseModel):
    client_id: int | None = None
    appointment_id: int | None = Field(
        default=None, description="Si se envía sin items, se cobran los servicios de la cita"
    )
    items: list[SaleItemCreate] = []
    discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    payments: list[PaymentCreate] = []
    notes: str | None = None


class SaleVoid(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class SaleItemRead(ORMModel):
    id: int
    service_id: int | None
    employee_id: int | None
    description: str
    quantity: int
    unit_price: Decimal
    discount: Decimal
    total: Decimal


class PaymentRead(ORMModel):
    id: int
    method: PaymentMethod
    amount: Decimal
    reference: str | None


class SaleRead(ORMModel):
    id: int
    cash_session_id: int
    client: ClientBrief | None
    appointment_id: int | None
    status: SaleStatus
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    notes: str | None
    created_by_id: int | None
    created_at: datetime
    voided_at: datetime | None
    void_reason: str | None
    items: list[SaleItemRead]
    payments: list[PaymentRead]

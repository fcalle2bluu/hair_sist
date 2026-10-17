from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None


class CategoryRead(ORMModel):
    id: int
    name: str
    is_active: bool


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: int | None = None
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    duration_minutes: int = Field(gt=0, le=24 * 60)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category_id: int | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    duration_minutes: int | None = Field(default=None, gt=0, le=24 * 60)
    is_active: bool | None = None


class ServiceRead(ORMModel):
    id: int
    name: str
    category_id: int | None
    category: CategoryRead | None
    description: str | None
    price: Decimal
    duration_minutes: int
    is_active: bool


class ServiceBrief(ORMModel):
    id: int
    name: str
    price: Decimal
    duration_minutes: int
    is_active: bool

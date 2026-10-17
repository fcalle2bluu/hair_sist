from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DaySales(BaseModel):
    day: date
    total: Decimal
    count: int


class DayCount(BaseModel):
    day: date
    count: int

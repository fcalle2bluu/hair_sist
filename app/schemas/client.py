from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.client import ClientNoteKind
from app.schemas.common import ORMModel


class ClientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    birth_date: date | None = None
    allergies: str | None = None
    notes: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    birth_date: date | None = None
    allergies: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ClientRead(ClientBase, ORMModel):
    id: int
    email: str | None = None
    is_active: bool
    created_at: datetime


class ClientBrief(ORMModel):
    id: int
    first_name: str
    last_name: str
    phone: str | None


class ClientNoteCreate(BaseModel):
    kind: ClientNoteKind = ClientNoteKind.GENERAL
    content: str = Field(min_length=1)


class ClientNoteRead(ORMModel):
    id: int
    kind: ClientNoteKind
    content: str
    author_id: int | None
    created_at: datetime

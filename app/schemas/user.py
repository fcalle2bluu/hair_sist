import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.models.user import Role
from app.schemas.common import ORMModel


def _normalize_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9@._+-]{3,255}", value):
        raise ValueError("El usuario debe tener al menos 3 caracteres: letras, números, @ . _ + -")
    return value


# Nombre de usuario para ingresar: un nombre simple ("admin", "ana.torres") o un email.
# Se guarda en la columna `email` por compatibilidad.
LowerEmail = Annotated[str, AfterValidator(_normalize_username)]
# bcrypt solo usa los primeros 72 bytes de la contraseña.
Password = Annotated[str, Field(min_length=4, max_length=72)]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: LowerEmail
    full_name: str = Field(min_length=1, max_length=150)
    role: Role
    password: Password


class UserUpdate(BaseModel):
    email: LowerEmail | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role: Role | None = None
    is_active: bool | None = None
    password: Password | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password


class UserRead(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    employee_id: int | None = None
    created_at: datetime

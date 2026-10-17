import enum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.employee import Employee


class Role(enum.StrEnum):
    ADMIN = "admin"
    RECEPCIONISTA = "recepcionista"
    ESTILISTA = "estilista"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role))
    is_active: Mapped[bool] = mapped_column(default=True)

    employee: Mapped["Employee | None"] = relationship(back_populates="user")

    @property
    def employee_id(self) -> int | None:
        return self.employee.id if self.employee else None

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession, get_or_404
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Usuarios"])


def _ensure_email_free(db: DbSession, email: str, exclude_id: int | None = None) -> None:
    stmt = select(User.id).where(User.email == email)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese email")


@router.get("", response_model=list[UserRead])
def list_users(db: DbSession, _: AdminUser):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DbSession, _: AdminUser):
    _ensure_email_free(db, data.email)
    user = User(
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: DbSession, _: AdminUser):
    return get_or_404(db, User, user_id, "Usuario no encontrado")


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: UserUpdate, db: DbSession, admin: AdminUser):
    user = get_or_404(db, User, user_id, "Usuario no encontrado")
    changes = data.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("is_active") is False or changes.get("role", admin.role) != admin.role):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivarte ni quitarte el rol de administrador")
    if "email" in changes:
        _ensure_email_free(db, changes["email"], exclude_id=user.id)
    if password := changes.pop("password", None):
        user.hashed_password = hash_password(password)
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    return user

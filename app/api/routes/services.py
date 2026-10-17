from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, CurrentUser, DbSession, get_or_404
from app.models.service import Service, ServiceCategory
from app.schemas.service import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
)

router = APIRouter(tags=["Servicios"])


def _commit_category(db: DbSession) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre") from exc


def _check_category(db: DbSession, category_id: int | None) -> None:
    if category_id is not None:
        get_or_404(db, ServiceCategory, category_id, "Categoría no encontrada")


# --- Categorías ---


@router.get("/service-categories", response_model=list[CategoryRead])
def list_categories(db: DbSession, _: CurrentUser, include_inactive: bool = False):
    stmt = select(ServiceCategory).order_by(ServiceCategory.name)
    if not include_inactive:
        stmt = stmt.where(ServiceCategory.is_active.is_(True))
    return db.scalars(stmt).all()


@router.post(
    "/service-categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED
)
def create_category(data: CategoryCreate, db: DbSession, _: AdminUser):
    category = ServiceCategory(name=data.name)
    db.add(category)
    _commit_category(db)
    return category


@router.patch("/service-categories/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, data: CategoryUpdate, db: DbSession, _: AdminUser):
    category = get_or_404(db, ServiceCategory, category_id, "Categoría no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    _commit_category(db)
    return category


# --- Servicios ---


@router.get("/services", response_model=list[ServiceRead])
def list_services(
    db: DbSession,
    _: CurrentUser,
    category_id: int | None = None,
    q: str | None = Query(default=None, description="Busca por nombre"),
    include_inactive: bool = False,
):
    stmt = select(Service).options(selectinload(Service.category)).order_by(Service.name)
    if category_id is not None:
        stmt = stmt.where(Service.category_id == category_id)
    if q:
        stmt = stmt.where(Service.name.ilike(f"%{q.strip()}%"))
    if not include_inactive:
        stmt = stmt.where(Service.is_active.is_(True))
    return db.scalars(stmt).all()


@router.post("/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(data: ServiceCreate, db: DbSession, _: AdminUser):
    _check_category(db, data.category_id)
    service = Service(**data.model_dump())
    db.add(service)
    db.commit()
    return service


@router.get("/services/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: DbSession, _: CurrentUser):
    return get_or_404(db, Service, service_id, "Servicio no encontrado")


@router.patch("/services/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, data: ServiceUpdate, db: DbSession, _: AdminUser):
    service = get_or_404(db, Service, service_id, "Servicio no encontrado")
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _check_category(db, changes["category_id"])
    for field, value in changes.items():
        setattr(service, field, value)
    db.commit()
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_service(service_id: int, db: DbSession, _: AdminUser):
    """Desactiva el servicio: deja de ofrecerse pero se conserva en citas y ventas pasadas."""
    service = get_or_404(db, Service, service_id, "Servicio no encontrado")
    service.is_active = False
    db.commit()

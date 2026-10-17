from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, CurrentUser, DbSession, StaffUser, get_or_404
from app.models.appointment import Appointment, AppointmentService
from app.models.client import Client, ClientNote
from app.schemas.appointment import AppointmentRead
from app.schemas.client import (
    ClientCreate,
    ClientNoteCreate,
    ClientNoteRead,
    ClientRead,
    ClientUpdate,
)
from app.schemas.common import Page

router = APIRouter(prefix="/clients", tags=["Clientes"])


@router.get("", response_model=Page[ClientRead])
def list_clients(
    db: DbSession,
    _: CurrentUser,
    q: str | None = Query(default=None, description="Busca por nombre, teléfono o email"),
    include_inactive: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    stmt = select(Client)
    if not include_inactive:
        stmt = stmt.where(Client.is_active.is_(True))
    if q:
        term = f"%{q.strip()}%"
        full_name = func.concat(Client.first_name, " ", Client.last_name)
        stmt = stmt.where(
            or_(full_name.ilike(term), Client.phone.ilike(term), Client.email.ilike(term))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Client.first_name, Client.last_name).offset(skip).limit(limit)
    ).all()
    return Page(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(data: ClientCreate, db: DbSession, _: StaffUser):
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: int, db: DbSession, _: CurrentUser):
    return get_or_404(db, Client, client_id, "Cliente no encontrado")


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(client_id: int, data: ClientUpdate, db: DbSession, _: StaffUser):
    client = get_or_404(db, Client, client_id, "Cliente no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_client(client_id: int, db: DbSession, _: AdminUser):
    """Desactiva al cliente (se conserva su historial)."""
    client = get_or_404(db, Client, client_id, "Cliente no encontrado")
    client.is_active = False
    db.commit()


@router.get("/{client_id}/notes", response_model=list[ClientNoteRead])
def list_notes(client_id: int, db: DbSession, _: CurrentUser):
    return get_or_404(db, Client, client_id, "Cliente no encontrado").technical_notes


@router.post(
    "/{client_id}/notes", response_model=ClientNoteRead, status_code=status.HTTP_201_CREATED
)
def add_note(client_id: int, data: ClientNoteCreate, db: DbSession, user: CurrentUser):
    """Notas generales o fórmulas técnicas (tinte, decoloración...). Cualquier rol puede agregar."""
    get_or_404(db, Client, client_id, "Cliente no encontrado")
    note = ClientNote(client_id=client_id, author_id=user.id, **data.model_dump())
    db.add(note)
    db.commit()
    return note


@router.get("/{client_id}/appointments", response_model=list[AppointmentRead])
def client_history(
    client_id: int,
    db: DbSession,
    _: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Historial de citas del cliente, de la más reciente a la más antigua."""
    get_or_404(db, Client, client_id, "Cliente no encontrado")
    return db.scalars(
        select(Appointment)
        .where(Appointment.client_id == client_id)
        .options(
            selectinload(Appointment.services).selectinload(AppointmentService.service),
            selectinload(Appointment.employee),
            selectinload(Appointment.client),
        )
        .order_by(Appointment.start_at.desc())
        .limit(limit)
    ).all()

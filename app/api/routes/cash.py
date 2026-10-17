from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, DbSession, StaffUser, get_or_404
from app.core.timeutils import now
from app.models.cash import CashMovement, CashSession, CashSessionStatus
from app.schemas.cash import (
    CashClose,
    CashMovementCreate,
    CashMovementRead,
    CashOpen,
    CashSessionDetail,
    CashSessionRead,
)
from app.services.cash import get_open_session, require_open_session, session_summary

router = APIRouter(prefix="/cash", tags=["Caja y ventas"])


def _detail(db: Session, session: CashSession) -> CashSessionDetail:
    return CashSessionDetail.model_validate(
        {
            **CashSessionRead.model_validate(session).model_dump(),
            "summary": session_summary(db, session),
            "movements": session.movements,
        }
    )


@router.get("/current", response_model=CashSessionDetail | None)
def current_session(db: DbSession, _: StaffUser):
    """Caja abierta con su resumen en vivo, o `null` si no hay ninguna."""
    session = get_open_session(db)
    return _detail(db, session) if session else None


@router.post("/open", response_model=CashSessionDetail, status_code=status.HTTP_201_CREATED)
def open_session(data: CashOpen, db: DbSession, user: StaffUser):
    if get_open_session(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una caja abierta")
    session = CashSession(
        opening_amount=data.opening_amount, notes=data.notes, opened_by_id=user.id
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una caja abierta") from exc
    return _detail(db, session)


@router.post(
    "/movements", response_model=CashMovementRead, status_code=status.HTTP_201_CREATED
)
def add_movement(data: CashMovementCreate, db: DbSession, user: StaffUser):
    """Registra una entrada o salida de efectivo que no es venta (ej. compra de insumos)."""
    session = require_open_session(db)
    movement = CashMovement(session_id=session.id, created_by_id=user.id, **data.model_dump())
    db.add(movement)
    db.commit()
    return movement


@router.post("/close", response_model=CashSessionDetail)
def close_session(data: CashClose, db: DbSession, user: StaffUser):
    """Cierra la caja: compara el efectivo esperado con el contado (arqueo)."""
    session = require_open_session(db)
    expected = session_summary(db, session).expected_cash
    session.status = CashSessionStatus.CERRADA
    session.closed_by_id = user.id
    session.closed_at = now()
    session.expected_cash = expected
    session.counted_cash = data.counted_cash
    session.difference = data.counted_cash - expected
    if data.notes:
        session.notes = f"{session.notes}\n{data.notes}" if session.notes else data.notes
    db.commit()
    return _detail(db, session)


@router.get("/sessions", response_model=list[CashSessionRead])
def list_sessions(
    db: DbSession,
    _: AdminUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=200),
):
    return db.scalars(
        select(CashSession).order_by(CashSession.opened_at.desc()).offset(skip).limit(limit)
    ).all()


@router.get("/sessions/{session_id}", response_model=CashSessionDetail)
def get_session(session_id: int, db: DbSession, _: AdminUser):
    return _detail(db, get_or_404(db, CashSession, session_id, "Caja no encontrada"))

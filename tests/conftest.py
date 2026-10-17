import os

os.environ["SECRET_KEY"] = "clave-de-pruebas-suficientemente-larga-para-hs256"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://hair:hair@localhost:5433/hair_sist_test"
)

from datetime import datetime, time, timedelta  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.timeutils import local_datetime, now  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402

PASSWORD = "clave-segura-123"


def _create_database_if_missing(url: str) -> None:
    parsed = make_url(url)
    admin_dsn = parsed.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (parsed.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{parsed.database}"')


@pytest.fixture(scope="session", autouse=True)
def database():
    _create_database_if_missing(os.environ["DATABASE_URL"])
    cfg = Config("alembic.ini")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(database):
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def create_user(db, role: Role, email: str) -> User:
    user = User(email=email, full_name=email.split("@")[0], role=role, hashed_password=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


def login(client, email: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def admin(client, db):
    create_user(db, Role.ADMIN, "admin@example.com")
    return login(client, "admin@example.com")


@pytest.fixture
def reception(client, db):
    create_user(db, Role.RECEPCIONISTA, "recepcion@example.com")
    return login(client, "recepcion@example.com")


def tomorrow_at(hour: int, minute: int = 0) -> str:
    day = now().date() + timedelta(days=1)
    return local_datetime(day, time(hour, minute)).isoformat()


@pytest.fixture
def salon(client, admin):
    """Servicio, estilista con horario 9:00-19:00 todos los días y un cliente."""
    corte = client.post(
        "/api/services", json={"name": "Corte", "price": "30.00", "duration_minutes": 60}, headers=admin
    ).json()
    tinte = client.post(
        "/api/services", json={"name": "Tinte", "price": "80.00", "duration_minutes": 90}, headers=admin
    ).json()
    manicure = client.post(
        "/api/services", json={"name": "Manicure", "price": "20.00", "duration_minutes": 30}, headers=admin
    ).json()
    employee = client.post(
        "/api/employees",
        json={"first_name": "Ana", "service_ids": [corte["id"], tinte["id"]]},
        headers=admin,
    ).json()
    resp = client.put(
        f"/api/employees/{employee['id']}/schedule",
        json=[{"weekday": d, "start_time": "09:00", "end_time": "19:00"} for d in range(7)],
        headers=admin,
    )
    assert resp.status_code == 200, resp.text
    customer = client.post(
        "/api/clients", json={"first_name": "Carla", "last_name": "Mendoza", "phone": "987654321"}, headers=admin
    ).json()
    return {
        "corte": corte,
        "tinte": tinte,
        "manicure": manicure,
        "employee": employee,
        "client": customer,
    }


def book(client, headers, salon, start: str, service_keys=("corte",)):
    return client.post(
        "/api/appointments",
        json={
            "client_id": salon["client"]["id"],
            "employee_id": salon["employee"]["id"],
            "start_at": start,
            "service_ids": [salon[k]["id"] for k in service_keys],
        },
        headers=headers,
    )


def parse(dt: str) -> datetime:
    return datetime.fromisoformat(dt)

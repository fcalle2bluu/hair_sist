from app.models import Role
from tests.conftest import create_user, login


def test_login_and_me(client, db):
    create_user(db, Role.ADMIN, "jefa@example.com")
    headers = login(client, "JEFA@example.com")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_login_wrong_password(client, db):
    create_user(db, Role.ADMIN, "jefa@example.com")
    resp = client.post("/api/auth/login", data={"username": "jefa@example.com", "password": "mala-clave"})
    assert resp.status_code == 401


def test_requires_token(client):
    assert client.get("/api/clients").status_code == 401


def test_reception_cannot_manage_catalog_or_users(client, reception):
    resp = client.post(
        "/api/services", json={"name": "Corte", "price": "30", "duration_minutes": 30}, headers=reception
    )
    assert resp.status_code == 403
    assert client.get("/api/users", headers=reception).status_code == 403


def test_admin_creates_user_with_unique_email(client, admin):
    payload = {"email": "Nueva@Example.com", "full_name": "Nueva", "role": "recepcionista", "password": "12345678"}
    resp = client.post("/api/users", json=payload, headers=admin)
    assert resp.status_code == 201
    assert resp.json()["email"] == "nueva@example.com"
    assert client.post("/api/users", json=payload, headers=admin).status_code == 409


def test_client_search_notes_and_deactivate(client, admin):
    created = client.post(
        "/api/clients",
        json={"first_name": "Lucía", "last_name": "Fernández", "phone": "998877665", "allergies": "Amoníaco"},
        headers=admin,
    ).json()
    client.post("/api/clients", json={"first_name": "Jorge"}, headers=admin)

    page = client.get("/api/clients", params={"q": "lucía fer"}, headers=admin).json()
    assert page["total"] == 1 and page["items"][0]["id"] == created["id"]
    assert client.get("/api/clients", params={"q": "99887"}, headers=admin).json()["total"] == 1

    note = client.post(
        f"/api/clients/{created['id']}/notes",
        json={"kind": "formula", "content": "7.1 + oxidante 20 vol, 35 min"},
        headers=admin,
    )
    assert note.status_code == 201
    assert len(client.get(f"/api/clients/{created['id']}/notes", headers=admin).json()) == 1

    assert client.delete(f"/api/clients/{created['id']}", headers=admin).status_code == 204
    assert client.get("/api/clients", headers=admin).json()["total"] == 1


def test_overlapping_schedule_blocks_rejected(client, admin, salon):
    resp = client.put(
        f"/api/employees/{salon['employee']['id']}/schedule",
        json=[
            {"weekday": 0, "start_time": "09:00", "end_time": "13:00"},
            {"weekday": 0, "start_time": "12:00", "end_time": "18:00"},
        ],
        headers=admin,
    )
    assert resp.status_code == 422


def test_employees_filtered_by_service(client, admin, salon):
    by_corte = client.get("/api/employees", params={"service_id": salon["corte"]["id"]}, headers=admin).json()
    by_manicure = client.get("/api/employees", params={"service_id": salon["manicure"]["id"]}, headers=admin).json()
    assert [e["id"] for e in by_corte] == [salon["employee"]["id"]]
    assert by_manicure == []


def test_username_login_with_short_password(client, admin):
    payload = {"email": "Recepcion", "full_name": "Recepción", "role": "recepcionista", "password": "2221"}
    resp = client.post("/api/users", json=payload, headers=admin)
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "recepcion"

    login = client.post("/api/auth/login", data={"username": "recepcion", "password": "2221"})
    assert login.status_code == 200

    too_short = {**payload, "email": "otro", "password": "123"}
    assert client.post("/api/users", json=too_short, headers=admin).status_code == 422
    bad_chars = {**payload, "email": "con espacio", "password": "2221"}
    assert client.post("/api/users", json=bad_chars, headers=admin).status_code == 422

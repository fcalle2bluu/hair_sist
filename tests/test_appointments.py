from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.timeutils import now
from app.models import Appointment, Role
from tests.conftest import book, create_user, login, parse, tomorrow_at


def test_create_appointment_computes_end_and_total(client, reception, salon):
    resp = book(client, reception, salon, tomorrow_at(10), ("corte", "tinte"))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert parse(data["end_at"]) - parse(data["start_at"]) == timedelta(minutes=150)
    assert data["total_price"] == "110.00"
    assert data["status"] == "pendiente"
    assert [s["service_name"] for s in data["services"]] == ["Corte", "Tinte"]


def test_overlapping_appointment_rejected(client, reception, salon):
    assert book(client, reception, salon, tomorrow_at(10)).status_code == 201
    resp = book(client, reception, salon, tomorrow_at(10, 30))
    assert resp.status_code == 409
    # Justo al terminar la anterior sí se puede.
    assert book(client, reception, salon, tomorrow_at(11)).status_code == 201


def test_outside_schedule_rejected(client, reception, salon):
    resp = book(client, reception, salon, tomorrow_at(18, 30))  # terminaría 19:30
    assert resp.status_code == 409
    assert "horario" in resp.json()["detail"]


def test_service_not_offered_rejected(client, reception, salon):
    resp = book(client, reception, salon, tomorrow_at(10), ("manicure",))
    assert resp.status_code == 422
    assert "Manicure" in resp.json()["detail"]


def test_time_off_blocks_booking(client, admin, reception, salon):
    resp = client.post(
        f"/api/employees/{salon['employee']['id']}/time-off",
        json={"start_at": tomorrow_at(9), "end_at": tomorrow_at(12), "reason": "Cita médica"},
        headers=admin,
    )
    assert resp.status_code == 201
    assert book(client, reception, salon, tomorrow_at(11)).status_code == 409
    assert book(client, reception, salon, tomorrow_at(12)).status_code == 201


def test_availability_excludes_booked_slots(client, reception, salon):
    book(client, reception, salon, tomorrow_at(10))
    day = (now().date() + timedelta(days=1)).isoformat()
    resp = client.get(
        "/api/appointments/availability",
        params={"employee_id": salon["employee"]["id"], "day": day, "service_ids": [salon["corte"]["id"]]},
        headers=reception,
    )
    assert resp.status_code == 200
    slots = {parse(s) for s in resp.json()["slots"]}
    assert parse(tomorrow_at(9)) in slots
    assert parse(tomorrow_at(9, 15)) not in slots  # 9:15-10:15 choca con 10:00
    assert parse(tomorrow_at(10, 30)) not in slots
    assert parse(tomorrow_at(11)) in slots
    assert parse(tomorrow_at(18)) in slots
    assert parse(tomorrow_at(18, 15)) not in slots  # se pasaría de las 19:00


def test_cancel_frees_slot(client, reception, salon):
    appt = book(client, reception, salon, tomorrow_at(10)).json()
    resp = client.post(
        f"/api/appointments/{appt['id']}/status",
        json={"status": "cancelada", "reason": "Cliente avisó"},
        headers=reception,
    )
    assert resp.status_code == 200
    assert resp.json()["cancel_reason"] == "Cliente avisó"
    assert book(client, reception, salon, tomorrow_at(10)).status_code == 201


def test_invalid_status_transition(client, reception, salon):
    appt = book(client, reception, salon, tomorrow_at(10)).json()
    url = f"/api/appointments/{appt['id']}/status"
    assert client.post(url, json={"status": "completada"}, headers=reception).status_code == 200
    assert client.post(url, json={"status": "pendiente"}, headers=reception).status_code == 409


def test_reschedule(client, reception, salon):
    first = book(client, reception, salon, tomorrow_at(10)).json()
    second = book(client, reception, salon, tomorrow_at(12)).json()

    url = f"/api/appointments/{second['id']}"
    assert client.patch(url, json={"start_at": tomorrow_at(10, 30)}, headers=reception).status_code == 409

    resp = client.patch(url, json={"start_at": tomorrow_at(14), "service_ids": [salon["tinte"]["id"]]}, headers=reception)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert parse(data["end_at"]) == parse(tomorrow_at(15, 30))
    assert data["total_price"] == "80.00"

    # Reprogramar sobre su propio horario no debe chocar consigo misma.
    resp = client.patch(f"/api/appointments/{first['id']}", json={"start_at": tomorrow_at(10, 15)}, headers=reception)
    assert resp.status_code == 200


def test_list_agenda_by_date(client, reception, salon):
    book(client, reception, salon, tomorrow_at(10))
    book(client, reception, salon, tomorrow_at(15))
    day = (now().date() + timedelta(days=1)).isoformat()
    agenda = client.get("/api/appointments", params={"date_from": day}, headers=reception).json()
    assert [parse(a["start_at"]) for a in agenda] == [parse(tomorrow_at(10)), parse(tomorrow_at(15))]
    assert client.get("/api/appointments", headers=reception).json() == []  # hoy no hay citas


def test_stylist_sees_only_own_appointments(client, db, admin, reception, salon):
    stylist_user = create_user(db, Role.ESTILISTA, "ana@example.com")
    client.patch(f"/api/employees/{salon['employee']['id']}", json={"user_id": stylist_user.id}, headers=admin)
    other = client.post(
        "/api/employees", json={"first_name": "Luis", "service_ids": [salon["corte"]["id"]]}, headers=admin
    ).json()
    client.put(
        f"/api/employees/{other['id']}/schedule",
        json=[{"weekday": d, "start_time": "09:00", "end_time": "19:00"} for d in range(7)],
        headers=admin,
    )
    mine = book(client, reception, salon, tomorrow_at(10)).json()
    theirs = book(client, reception, {**salon, "employee": other}, tomorrow_at(10)).json()

    headers = login(client, "ana@example.com")
    day = (now().date() + timedelta(days=1)).isoformat()
    agenda = client.get("/api/appointments", params={"date_from": day}, headers=headers).json()
    assert [a["id"] for a in agenda] == [mine["id"]]
    assert client.get(f"/api/appointments/{theirs['id']}", headers=headers).status_code == 403

    status_url = f"/api/appointments/{mine['id']}/status"
    assert client.post(status_url, json={"status": "cancelada"}, headers=headers).status_code == 403
    assert client.post(status_url, json={"status": "en_curso"}, headers=headers).status_code == 200
    # Los estilistas no pueden crear citas.
    assert book(client, headers, salon, tomorrow_at(16)).status_code == 403


def test_database_rejects_overlap_even_without_api(db, client, reception, salon):
    appt = book(client, reception, salon, tomorrow_at(10)).json()
    start = parse(appt["start_at"]) + timedelta(minutes=15)
    db.add(
        Appointment(
            client_id=salon["client"]["id"],
            employee_id=salon["employee"]["id"],
            start_at=start,
            end_at=start + timedelta(minutes=30),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_month_calendar_counts(client, reception, salon):
    book(client, reception, salon, tomorrow_at(10))
    book(client, reception, salon, tomorrow_at(12))
    cancelled = book(client, reception, salon, tomorrow_at(15)).json()
    client.post(f"/api/appointments/{cancelled['id']}/status", json={"status": "cancelada"}, headers=reception)

    day = now().date() + timedelta(days=1)
    resp = client.get("/api/appointments/calendar", params={"month": day.strftime("%Y-%m")}, headers=reception)
    assert resp.status_code == 200, resp.text
    assert {"day": day.isoformat(), "count": 2} in resp.json()  # la cancelada no cuenta

    assert client.get("/api/appointments/calendar", params={"month": "2026-13"}, headers=reception).status_code == 422

from tests.conftest import book, tomorrow_at


def open_cash(client, headers, amount="100.00"):
    resp = client.post("/api/cash/open", json={"opening_amount": amount}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_sale_requires_open_cash(client, reception, salon):
    resp = client.post(
        "/api/sales",
        json={"items": [{"service_id": salon["corte"]["id"]}], "payments": [{"method": "efectivo", "amount": "30"}]},
        headers=reception,
    )
    assert resp.status_code == 409


def test_only_one_open_cash(client, reception):
    open_cash(client, reception)
    assert client.post("/api/cash/open", json={"opening_amount": "0"}, headers=reception).status_code == 409


def test_checkout_appointment(client, reception, salon):
    open_cash(client, reception)
    appt = book(client, reception, salon, tomorrow_at(10), ("corte", "tinte")).json()

    resp = client.post(
        "/api/sales",
        json={
            "appointment_id": appt["id"],
            "discount": "10.00",
            "payments": [
                {"method": "efectivo", "amount": "40.00"},
                {"method": "tarjeta", "amount": "60.00", "reference": "VOUCHER-123"},
            ],
        },
        headers=reception,
    )
    assert resp.status_code == 201, resp.text
    sale = resp.json()
    assert sale["subtotal"] == "110.00"
    assert sale["total"] == "100.00"
    assert sale["client"]["id"] == salon["client"]["id"]
    assert {i["employee_id"] for i in sale["items"]} == {salon["employee"]["id"]}

    status = client.get(f"/api/appointments/{appt['id']}", headers=reception).json()["status"]
    assert status == "completada"

    again = client.post(
        "/api/sales",
        json={"appointment_id": appt["id"], "payments": [{"method": "efectivo", "amount": "110"}]},
        headers=reception,
    )
    assert again.status_code == 409


def test_payments_must_match_total(client, reception, salon):
    open_cash(client, reception)
    resp = client.post(
        "/api/sales",
        json={
            "items": [{"service_id": salon["corte"]["id"], "quantity": 2}],
            "payments": [{"method": "efectivo", "amount": "50.00"}],
        },
        headers=reception,
    )
    assert resp.status_code == 422
    assert "60.00" in resp.json()["detail"]


def test_item_price_override_and_discount_limit(client, reception, salon):
    open_cash(client, reception)
    item = {"service_id": salon["corte"]["id"], "unit_price": "45.00", "discount": "5.00"}
    resp = client.post(
        "/api/sales",
        json={"items": [item], "payments": [{"method": "transferencia", "amount": "40.00"}]},
        headers=reception,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["total"] == "40.00"

    item["discount"] = "50.00"
    resp = client.post("/api/sales", json={"items": [item], "payments": []}, headers=reception)
    assert resp.status_code == 422


def test_cash_close_with_movements_and_void(client, admin, reception, salon):
    open_cash(client, reception, "100.00")

    def sell(amount, method):
        resp = client.post(
            "/api/sales",
            json={
                "items": [{"service_id": salon["corte"]["id"], "unit_price": amount}],
                "payments": [{"method": method, "amount": amount}],
            },
            headers=reception,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    sell("30.00", "efectivo")
    sell("50.00", "tarjeta")
    voided = sell("20.00", "efectivo")

    resp = client.post(f"/api/sales/{voided['id']}/void", json={"reason": "Error de cobro"}, headers=reception)
    assert resp.status_code == 403  # solo admin
    resp = client.post(f"/api/sales/{voided['id']}/void", json={"reason": "Error de cobro"}, headers=admin)
    assert resp.status_code == 200 and resp.json()["status"] == "anulada"

    client.post("/api/cash/movements", json={"type": "egreso", "amount": "15.00", "concept": "Compra de toallas"}, headers=reception)
    client.post("/api/cash/movements", json={"type": "ingreso", "amount": "5.00", "concept": "Sencillo"}, headers=reception)

    current = client.get("/api/cash/current", headers=reception).json()
    summary = current["summary"]
    assert summary["sales_count"] == 2
    assert summary["sales_total"] == "80.00"
    assert summary["by_method"]["efectivo"] == "30.00"
    assert summary["by_method"]["tarjeta"] == "50.00"
    # 100 apertura + 30 efectivo + 5 ingreso - 15 egreso
    assert summary["expected_cash"] == "120.00"

    closed = client.post("/api/cash/close", json={"counted_cash": "118.50"}, headers=reception).json()
    assert closed["status"] == "cerrada"
    assert closed["expected_cash"] == "120.00"
    assert closed["difference"] == "-1.50"
    assert client.get("/api/cash/current", headers=reception).json() is None

    # Con la caja cerrada ya no se puede anular.
    sale_id = client.get("/api/sales", headers=admin).json()[0]["id"]
    resp = client.post(f"/api/sales/{sale_id}/void", json={"reason": "tarde"}, headers=admin)
    assert resp.status_code == 409

"""Stock module API (spec stock-hygiène 3, 4, 8): products, suppliers, receipts, use, inventory, change log."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from daftar.tables import audit_log, stock_movement
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def cab(make_practice: Factory, make_user: Factory, auth_headers: Factory) -> Any:
    p = make_practice("Cabinet Sfax", specialty="dentiste", practitioners=["Dr. Fadoua"])
    owner = make_user(p, "owner", name="Dr. Fadoua")
    nisrine = make_user(p, "assistant", name="Nisrine")
    dentist = make_user(p, "dentist", name="Dr. Karim")
    return type("Cab", (), {
        "practice": p, "owner": auth_headers(owner), "assistant": auth_headers(nisrine), "dentist": auth_headers(dentist),
    })


def product(client: TestClient, headers: dict[str, str], name: str = "Gants d’examen", **values: Any) -> dict[str, Any]:
    res = client.post("/api/stock/products", json={"name": name, "category": "hygiene", "unit": "boite", **values},
                      headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def supplier(client: TestClient, headers: dict[str, str], name: str = "Dentalia Sfax", **values: Any) -> dict[str, Any]:
    res = client.post("/api/stock/suppliers", json={"name": name, **values}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def receive(client: TestClient, headers: dict[str, str], lines: list[dict[str, Any]], **values: Any) -> Any:
    return client.post("/api/stock/receipts", json={"lines": lines, **values}, headers=headers)


def products_by_name(client: TestClient, headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    res = client.get("/api/stock/products", headers=headers)
    assert res.status_code == 200, res.text
    return {p["name"]: p for p in res.json()}


# --- products and suppliers -----------------------------------------------------------------------------------------


def test_the_assistant_creates_a_product_that_starts_empty(client: TestClient, cab: Any) -> None:
    sup = supplier(client, cab.assistant, phone="74 000 000", whatsapp="20 123 456")
    assert (sup["phone"], sup["whatsapp"]) == ("+21674000000", "+21620123456")
    created = product(client, cab.assistant, supplierId=sup["id"], minQuantity=4, note="Taille M")
    assert created == {
        "id": created["id"], "name": "Gants d’examen", "category": "hygiene", "unit": "boite", "supplierId": sup["id"],
        "supplierName": "Dentalia Sfax", "minQuantity": 4, "note": "Taille M", "ean": None, "active": True,
        "quantity": 0, "status": "empty", "expiresOn": None, "expiry": None, "averageCostMillimes": None,
        "lastUsedAt": None,
    }
    assert_problem(client.post("/api/stock/products", json={"name": " gants D’EXAMEN "}, headers=cab.owner), 409,
                   "product_exists")
    res = client.patch(f"/api/stock/products/{created['id']}", json={"minQuantity": 6, "supplierId": None},
                       headers=cab.owner)
    assert res.status_code == 200, res.text
    assert (res.json()["minQuantity"], res.json()["supplierId"]) == (6, None)


@pytest.mark.parametrize(
    ("body", "code"),
    [({"name": ""}, "validation"), ({"name": "X", "category": "jouets"}, "validation"),
     ({"name": "X", "unit": "kilo"}, "validation"), ({"name": "X", "minQuantity": -1}, "validation"),
     ({"name": "X", "ean": "12AB"}, "validation"), ({"name": "X", "supplierId": 999_999}, "invalid_supplier")],
)
def test_product_validation(client: TestClient, cab: Any, body: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/stock/products", json=body, headers=cab.assistant), 422, code)


def test_products_and_suppliers_are_set_up_by_assistant_and_owner_only(client: TestClient, cab: Any) -> None:
    assert_problem(client.post("/api/stock/products", json={"name": "X"}, headers=cab.dentist), 403, "forbidden")
    assert_problem(client.post("/api/stock/suppliers", json={"name": "X"}, headers=cab.dentist), 403, "forbidden")
    assert_problem(client.post("/api/stock/products/starter", headers=cab.dentist), 403, "forbidden")
    assert client.get("/api/stock/products", headers=cab.dentist).status_code == 200
    assert client.get("/api/stock/suppliers", headers=cab.dentist).status_code == 200
    assert_problem(client.get("/api/stock/products"), 401, "unauthorized")


def test_ids_of_another_practice_are_not_found(client: TestClient, cab: Any, make_user: Factory,
                                               auth_headers: Factory) -> None:
    stranger = auth_headers(make_user(role="owner"))
    mine = product(client, cab.assistant)
    sup = supplier(client, cab.assistant)
    assert client.get("/api/stock/products", headers=stranger).json() == []
    assert client.get("/api/stock/suppliers", headers=stranger).json() == []
    assert_problem(client.patch(f"/api/stock/products/{mine['id']}", json={"name": "Y"}, headers=stranger), 404, "not_found")
    assert_problem(client.delete(f"/api/stock/products/{mine['id']}", headers=stranger), 404, "not_found")
    assert_problem(client.patch(f"/api/stock/suppliers/{sup['id']}", json={"name": "Y"}, headers=stranger), 404, "not_found")
    assert_problem(client.post("/api/stock/products", json={"name": "Z", "supplierId": sup["id"]}, headers=stranger),
                   422, "invalid_supplier")
    assert_problem(receive(client, stranger, [{"productId": mine["id"], "quantity": 1}]), 422, "invalid_product")
    assert_problem(client.post("/api/stock/movements", json={"productId": mine["id"], "kind": "use", "quantity": 1},
                               headers=stranger), 422, "invalid_product")


def test_start_list_once_and_in_the_users_language(client: TestClient, cab: Any, make_user: Factory,
                                                   auth_headers: Factory) -> None:
    res = client.post("/api/stock/products/starter", headers=cab.assistant)
    assert res.status_code == 200, res.text
    created = res.json()["created"]
    assert created >= 10
    names = products_by_name(client, cab.assistant)
    assert names["Carpules d’articaïne"]["category"] == "anesthesie" and names["Carpules d’articaïne"]["minQuantity"] >= 1
    assert client.post("/api/stock/products/starter", headers=cab.assistant).json() == {"created": 0}
    arabic = make_user(role="assistant", lang="ar")
    res = client.post("/api/stock/products/starter", headers=auth_headers(arabic))
    assert res.json()["created"] >= 5
    assert any("قفازات" in p["name"] for p in client.get("/api/stock/products", headers=auth_headers(arabic)).json())


def test_suppliers_list_and_delete_only_when_unused(client: TestClient, cab: Any) -> None:
    used = supplier(client, cab.assistant, note="Livre le mardi")
    spare = supplier(client, cab.assistant, name="Médical Sud")
    product(client, cab.assistant, supplierId=used["id"])
    listed = client.get("/api/stock/suppliers", headers=cab.assistant).json()
    assert [(s["name"], s["products"]) for s in listed] == [("Dentalia Sfax", 1), ("Médical Sud", 0)]
    assert_problem(client.delete(f"/api/stock/suppliers/{used['id']}", headers=cab.assistant), 409, "supplier_in_use")
    assert client.delete(f"/api/stock/suppliers/{spare['id']}", headers=cab.assistant).status_code == 204
    res = client.patch(f"/api/stock/suppliers/{used['id']}", json={"active": False, "phone": ""}, headers=cab.owner)
    assert (res.json()["active"], res.json()["phone"]) == (False, None)
    assert_problem(client.post("/api/stock/suppliers", json={"name": "dentalia SFAX"}, headers=cab.owner), 409,
                   "supplier_exists")
    assert_problem(client.post("/api/stock/suppliers", json={"name": "X", "phone": "123"}, headers=cab.owner), 422,
                   "invalid_phone")


# --- receipts ---------------------------------------------------------------------------------------------------------


def test_a_receipt_adds_stock_and_sets_prices_lots_and_the_default_supplier(client: TestClient, cab: Any) -> None:
    sup = supplier(client, cab.assistant)
    gloves = product(client, cab.assistant, minQuantity=4)
    carpules = product(client, cab.assistant, "Carpules d’articaïne", category="anesthesie")
    res = receive(client, cab.assistant, [
        {"productId": gloves["id"], "quantity": 10, "unitPriceMillimes": 12_000},
        {"productId": carpules["id"], "quantity": 2, "unitPriceMillimes": 45_500, "lot": " A123 ",
         "expiresOn": "2026-11-20"},
        {"productId": gloves["id"], "quantity": 30, "unitPriceMillimes": 16_000},
    ], supplierId=sup["id"], reference="BL 4412", receivedOn="2026-10-29")
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["receivedOn"], body["supplierName"], body["reference"], body["createdBy"]) == (
        "2026-10-29", "Dentalia Sfax", "BL 4412", "Nisrine")
    assert body["totalMillimes"] == 10 * 12_000 + 2 * 45_500 + 30 * 16_000
    assert [(line["productName"], line["quantity"], line["lot"]) for line in body["lines"]] == [
        ("Gants d’examen", 10, ""), ("Carpules d’articaïne", 2, "A123"), ("Gants d’examen", 30, "")]
    names = products_by_name(client, cab.assistant)
    assert (names["Gants d’examen"]["quantity"], names["Gants d’examen"]["status"]) == (40, "ok")
    assert names["Gants d’examen"]["averageCostMillimes"] == 15_000
    assert names["Gants d’examen"]["supplierId"] == sup["id"]  # learnt from the first delivery
    assert (names["Carpules d’articaïne"]["expiresOn"], names["Carpules d’articaïne"]["expiry"]) == ("2026-11-20", "soon")
    listed = client.get("/api/stock/receipts", headers=cab.owner).json()
    assert [r["id"] for r in listed] == [body["id"]]
    assert client.get(f"/api/stock/receipts/{body['id']}", headers=cab.owner).json() == body


@pytest.mark.parametrize(
    ("lines", "values", "status", "code"),
    [([], {}, 422, "validation"),
     ([{"productId": 0, "quantity": 1}], {}, 422, "invalid_product"),
     ("gloves", {"receivedOn": "2026-10-31"}, 422, "day_in_future"),
     ("gloves:0", {}, 422, "validation"),
     ("gloves:price", {}, 422, "validation"),
     ("gloves", {"supplierId": 999_999}, 422, "invalid_supplier")],
)
def test_receipt_validation(client: TestClient, cab: Any, lines: Any, values: dict[str, Any], status: int, code: str) -> None:
    gloves = product(client, cab.assistant)
    if lines == "gloves":
        lines = [{"productId": gloves["id"], "quantity": 1}]
    elif lines == "gloves:0":
        lines = [{"productId": gloves["id"], "quantity": 0}]
    elif lines == "gloves:price":
        lines = [{"productId": gloves["id"], "quantity": 1, "unitPriceMillimes": 12.5}]
    assert_problem(receive(client, cab.assistant, lines, **values), status, code)


def test_receipts_are_not_for_the_dentist_and_not_in_a_suspended_practice(
    client: TestClient, cab: Any, make_practice: Factory, make_user: Factory, auth_headers: Factory
) -> None:
    gloves = product(client, cab.assistant)
    assert_problem(receive(client, cab.dentist, [{"productId": gloves["id"], "quantity": 1}]), 403, "forbidden")
    assert_problem(client.get("/api/stock/receipts", headers=cab.dentist), 403, "forbidden")
    suspended = auth_headers(make_user(make_practice(status="suspended"), "assistant"))
    assert_problem(receive(client, suspended, [{"productId": gloves["id"], "quantity": 1}]), 402, "subscription_suspended")


# --- use, waste, inventory -------------------------------------------------------------------------------------------


@pytest.fixture
def stocked(client: TestClient, cab: Any, make_patient: Factory, make_appointment: Factory, make_service: Factory) -> Any:
    sup = supplier(client, cab.assistant)
    gloves = product(client, cab.assistant, minQuantity=4, supplierId=sup["id"])
    composite = product(client, cab.assistant, "Composite", category="restauration", unit="piece", minQuantity=2)
    receive(client, cab.assistant, [{"productId": gloves["id"], "quantity": 10, "unitPriceMillimes": 12_000},
                                    {"productId": composite["id"], "quantity": 3, "unitPriceMillimes": 30_000}],
            supplierId=sup["id"], receivedOn="2026-10-30")
    soin = make_service(cab.practice, "Soin carie / composite", 45)
    pat = make_patient(cab.practice, first_name="Amira", last_name="Trabelsi")
    appt = make_appointment(pat, starts_at=T0 - timedelta(hours=1), duration_min=45, service_id=soin.id, status="done",
                            practitioner_id=cab.practice.practitioners[0].id)
    return type("S", (), {"supplier": sup, "gloves": gloves, "composite": composite, "soin": soin, "appt": appt})


def use(client: TestClient, headers: dict[str, str], product_id: int, quantity: int = 1, **values: Any) -> Any:
    return client.post("/api/stock/movements", json={"productId": product_id, "kind": "use", "quantity": quantity, **values},
                       headers=headers)


def test_the_dentist_records_what_was_used_for_an_appointment(client: TestClient, cab: Any, stocked: Any) -> None:
    res = use(client, cab.dentist, stocked.composite["id"], appointmentId=stocked.appt.id)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["movement"]["kind"] == "use" and body["movement"]["quantity"] == -1
    assert body["movement"]["serviceId"] == stocked.soin.id  # taken from the appointment
    assert body["movement"]["serviceName"] == "Soin carie / composite"
    assert body["movement"]["appointmentId"] == stocked.appt.id and body["movement"]["patientName"] == "Amira Trabelsi"
    assert body["movement"]["unitCostMillimes"] is None  # the dentist does not see prices
    assert body["movement"]["createdBy"] == "Dr. Karim" and body["movement"]["createdAt"] == "2026-10-30T09:00:00+01:00"
    assert (body["product"]["quantity"], body["product"]["status"]) == (2, "low")
    assert body["product"]["averageCostMillimes"] is None
    assert body["product"]["lastUsedAt"] == "2026-10-30T09:00:00+01:00"
    listed = client.get(f"/api/stock/movements?appointmentId={stocked.appt.id}", headers=cab.assistant).json()
    assert [(m["productName"], m["quantity"], m["unitCostMillimes"]) for m in listed] == [("Composite", -1, 30_000)]


def test_use_can_go_below_zero_and_says_so(client: TestClient, cab: Any, stocked: Any) -> None:
    body = use(client, cab.assistant, stocked.composite["id"], 5).json()
    assert (body["product"]["quantity"], body["product"]["status"]) == (-2, "empty")


def test_waste_and_inventory_are_for_assistant_and_owner(client: TestClient, cab: Any, stocked: Any, db: Engine) -> None:
    waste = {"productId": stocked.gloves["id"], "kind": "waste", "quantity": 2, "reason": "Boîte mouillée"}
    assert_problem(client.post("/api/stock/movements", json=waste, headers=cab.dentist), 403, "forbidden")
    res = client.post("/api/stock/movements", json=waste, headers=cab.assistant)
    assert res.status_code == 201, res.text
    assert res.json()["product"]["quantity"] == 8
    counts = {"reason": "Inventaire du 30/10", "counts": [{"productId": stocked.gloves["id"], "counted": 6},
                                                          {"productId": stocked.composite["id"], "counted": 3}]}
    assert_problem(client.post("/api/stock/inventory", json=counts, headers=cab.dentist), 403, "forbidden")
    assert_problem(client.post("/api/stock/inventory", json={**counts, "reason": " "}, headers=cab.assistant), 422,
                   "validation")
    res = client.post("/api/stock/inventory", json=counts, headers=cab.assistant)
    assert res.status_code == 200, res.text
    assert res.json()["adjusted"] == 1  # the composite count matched
    assert {p["name"]: p["quantity"] for p in res.json()["products"]} == {"Gants d’examen": 6, "Composite": 3}
    with db.connect() as conn:
        row = conn.execute(select(stock_movement.c.quantity, stock_movement.c.reason)
                           .where(stock_movement.c.kind == "adjust")).one()
    assert tuple(row) == (-2, "Inventaire du 30/10")


@pytest.mark.parametrize(
    ("body", "code"),
    [({"kind": "use", "quantity": 0}, "validation"), ({"kind": "use", "quantity": -1}, "validation"),
     ({"kind": "receipt", "quantity": 1}, "validation"), ({"kind": "adjust", "quantity": 1}, "validation"),
     ({"kind": "use", "quantity": 1, "serviceId": 999_999}, "invalid_service"),
     ({"kind": "use", "quantity": 1, "appointmentId": 999_999}, "invalid_appointment")],
)
def test_movement_validation(client: TestClient, cab: Any, stocked: Any, body: dict[str, Any], code: str) -> None:
    res = client.post("/api/stock/movements", json={"productId": stocked.gloves["id"], **body}, headers=cab.assistant)
    assert_problem(res, 422, code)


def test_an_inactive_product_takes_no_movement(client: TestClient, cab: Any, stocked: Any) -> None:
    client.patch(f"/api/stock/products/{stocked.gloves['id']}", json={"active": False}, headers=cab.assistant)
    assert_problem(use(client, cab.assistant, stocked.gloves["id"]), 422, "product_inactive")
    assert_problem(receive(client, cab.assistant, [{"productId": stocked.gloves["id"], "quantity": 1}]), 422,
                   "product_inactive")


def test_a_product_with_history_is_deactivated_not_deleted(client: TestClient, cab: Any, stocked: Any) -> None:
    assert_problem(client.delete(f"/api/stock/products/{stocked.gloves['id']}", headers=cab.assistant), 409,
                   "product_in_use")
    spare = product(client, cab.assistant, "Erreur de saisie")
    assert client.delete(f"/api/stock/products/{spare['id']}", headers=cab.assistant).status_code == 204
    assert_problem(client.delete(f"/api/stock/products/{spare['id']}", headers=cab.dentist), 403, "forbidden")


# --- corrections by the owner, with the change log (section 8) --------------------------------------------------------


def test_only_the_owner_deletes_a_movement_and_it_is_logged(client: TestClient, cab: Any, stocked: Any, db: Engine) -> None:
    used = use(client, cab.dentist, stocked.gloves["id"], 3).json()["movement"]
    path = f"/api/stock/movements/{used['id']}"
    assert_problem(client.request("DELETE", path, json={"reason": "Erreur"}, headers=cab.assistant), 403, "forbidden")
    assert_problem(client.request("DELETE", path, json={"reason": ""}, headers=cab.owner), 422, "validation")
    res = client.request("DELETE", path, json={"reason": "Saisi deux fois"}, headers=cab.owner)
    assert res.status_code == 204, res.text
    assert products_by_name(client, cab.owner)["Gants d’examen"]["quantity"] == 10
    log = client.get("/api/audit-log", headers=cab.owner).json()
    assert log[0]["entity"] == "stock_movement" and log[0]["entityId"] == used["id"] and log[0]["action"] == "delete"
    assert (log[0]["userName"], log[0]["reason"], log[0]["at"]) == ("Dr. Fadoua", "Saisi deux fois", "2026-10-30T09:00:00+01:00")
    assert log[0]["before"]["quantity"] == -3 and log[0]["before"]["product"] == "Gants d’examen"
    assert_problem(client.get("/api/audit-log", headers=cab.assistant), 403, "forbidden")
    receipt_movement = client.get(f"/api/stock/movements?productId={stocked.gloves['id']}", headers=cab.owner).json()[-1]
    assert receipt_movement["kind"] == "receipt"
    assert_problem(client.request("DELETE", f"/api/stock/movements/{receipt_movement['id']}", json={"reason": "x"},
                                  headers=cab.owner), 409, "receipt_movement")


def test_the_owner_deletes_a_receipt_with_its_lines_and_the_log_keeps_them(client: TestClient, cab: Any, stocked: Any,
                                                                           db: Engine) -> None:
    receipt = client.get("/api/stock/receipts", headers=cab.owner).json()[0]
    path = f"/api/stock/receipts/{receipt['id']}"
    assert_problem(client.request("DELETE", path, json={"reason": "Doublon"}, headers=cab.assistant), 403, "forbidden")
    assert client.request("DELETE", path, json={"reason": "Doublon"}, headers=cab.owner).status_code == 204
    assert {p["name"]: p["quantity"] for p in client.get("/api/stock/products", headers=cab.owner).json()} == {
        "Gants d’examen": 0, "Composite": 0}
    entry = client.get("/api/audit-log", headers=cab.owner).json()[0]
    assert entry["entity"] == "stock_receipt" and entry["reason"] == "Doublon"
    assert [(line["product"], line["quantity"], line["unitPriceMillimes"]) for line in entry["before"]["lines"]] == [
        ("Gants d’examen", 10, 12_000), ("Composite", 3, 30_000)]
    assert_problem(client.get(path, headers=cab.owner), 404, "not_found")
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(audit_log)).scalar_one() == 1


# --- à commander, dashboard, badges ------------------------------------------------------------------------------------


def test_to_order_groups_low_products_by_supplier(client: TestClient, cab: Any, stocked: Any) -> None:
    use(client, cab.assistant, stocked.gloves["id"], 7)  # 3 left, minimum 4
    loose = product(client, cab.assistant, "Gobelets", minQuantity=2)  # no supplier, empty
    product(client, cab.assistant, "Sans seuil")  # no minimum: never proposed
    res = client.get("/api/stock/to-order", headers=cab.dentist)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 2
    first, second = body["groups"]
    assert first["supplier"] == {"id": stocked.supplier["id"], "name": "Dentalia Sfax", "phone": None, "whatsapp": None}
    assert first["items"] == [{"productId": stocked.gloves["id"], "name": "Gants d’examen", "unit": "boite",
                               "quantity": 3, "minQuantity": 4, "suggested": 5}]
    assert second["supplier"] is None and second["items"][0]["productId"] == loose["id"]
    dashboard = client.get("/api/dashboard", headers=cab.assistant).json()
    assert dashboard["stockToOrder"] == 2
    assert client.get("/api/badges", headers=cab.assistant).json()["stockToOrder"] == 2


# --- owner: spending and use per act (section 4.3) -------------------------------------------------------------------


def test_stats_show_spending_and_material_cost_per_act(client: TestClient, cab: Any, stocked: Any,
                                                       make_appointment: Factory, make_patient: Factory) -> None:
    other = make_patient(cab.practice)
    make_appointment(other, starts_at=T0 - timedelta(days=1), duration_min=45, service_id=stocked.soin.id, status="done",
                     practitioner_id=cab.practice.practitioners[0].id)
    use(client, cab.dentist, stocked.composite["id"], appointmentId=stocked.appt.id)
    use(client, cab.dentist, stocked.gloves["id"], 2, appointmentId=stocked.appt.id)
    use(client, cab.dentist, stocked.gloves["id"], 1)  # not for an act
    receive(client, cab.assistant, [{"productId": stocked.gloves["id"], "quantity": 5, "unitPriceMillimes": 10_000}],
            receivedOn="2026-09-15")
    assert_problem(client.get("/api/stock/stats?month=2026-10", headers=cab.assistant), 403, "forbidden")
    res = client.get("/api/stock/stats?month=2026-10", headers=cab.owner)
    assert res.status_code == 200, res.text
    s = res.json()
    assert s["month"] == "2026-10"
    assert s["spendingMillimes"] == 10 * 12_000 + 3 * 30_000 and s["previousSpendingMillimes"] == 50_000
    assert s["bySupplier"] == [{"name": "Dentalia Sfax", "amountMillimes": 210_000}]
    assert s["byCategory"] == [{"category": "hygiene", "amountMillimes": 120_000},
                               {"category": "restauration", "amountMillimes": 90_000}]
    soin, none = s["byService"]
    assert (soin["name"], soin["treatments"], soin["materialCostMillimes"], soin["perTreatmentMillimes"]) == (
        "Soin carie / composite", 2, 30_000 + 2 * 12_000, 27_000)
    assert [(i["name"], i["quantity"], i["costMillimes"]) for i in soin["items"]] == [
        ("Composite", 1, 30_000), ("Gants d’examen", 2, 24_000)]
    assert (none["serviceId"], none["name"], none["materialCostMillimes"], none["perTreatmentMillimes"]) == (
        None, None, 12_000, None)
    assert s["usageMillimes"] == 66_000
    assert [(t["name"], t["costMillimes"]) for t in s["topMaterials"]] == [("Gants d’examen", 36_000), ("Composite", 30_000)]
    assert_problem(client.get("/api/stock/stats?month=2026-13", headers=cab.owner), 422, "validation")


def test_csv_export_of_the_month(client: TestClient, cab: Any, stocked: Any) -> None:
    use(client, cab.dentist, stocked.composite["id"], appointmentId=stocked.appt.id, reason="=HYPERLINK(1)")
    assert_problem(client.get("/api/stock/export.csv?month=2026-10", headers=cab.assistant), 403, "forbidden")
    res = client.get("/api/stock/export.csv?month=2026-10", headers=cab.owner)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    assert res.headers["content-disposition"] == 'attachment; filename="stock-2026-10.csv"'
    text = res.content.decode("utf-8")
    assert text.startswith("﻿Date;Type;Produit;")
    lines = text.strip().split("\r\n")
    assert len(lines) == 4  # header, two receipt lines, one use
    assert "Composite" in lines[-1] and "Soin carie / composite" in lines[-1] and "'=HYPERLINK(1)" in lines[-1]
    assert ";-1;" in lines[-1] and "30,000" in lines[-1]


def test_the_practice_export_contains_the_stock_and_the_change_log(client: TestClient, cab: Any, stocked: Any) -> None:
    used = use(client, cab.dentist, stocked.gloves["id"], 2, appointmentId=stocked.appt.id).json()["movement"]
    client.request("DELETE", f"/api/stock/movements/{used['id']}", json={"reason": "Erreur"}, headers=cab.owner)
    data = client.get("/api/practice/export", headers=cab.owner).json()
    assert [s["name"] for s in data["suppliers"]] == ["Dentalia Sfax"]
    assert [p["name"] for p in data["stockProducts"]] == ["Gants d’examen", "Composite"]
    assert len(data["stockReceipts"]) == 1 and len(data["stockReceiptLines"]) == 2
    assert [m["kind"] for m in data["stockMovements"]] == ["receipt", "receipt"]
    assert [(e["entity"], e["reason"]) for e in data["auditLog"]] == [("stock_movement", "Erreur")]

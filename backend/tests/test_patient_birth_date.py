"""The optional full birth date of a patient (spec stock-hygiène 6): labs need it on specimen labels. When it is set, the
birth year is its year; patients with a year only stay valid."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem

Factory = Callable[..., Any]
NEW = {"firstName": "Amira", "lastName": "Trabelsi", "phone": "20 123 456", "lang": "fr"}


@pytest.fixture
def owner(make_practice: Factory, make_user: Factory, auth_headers: Factory) -> Any:
    user = make_user(make_practice(), "owner")
    return type("Owner", (), {"headers": auth_headers(user), "practice": type("P", (), {"id": user.practice_id})()})


def test_a_birth_date_gives_the_year(client: TestClient, owner: Any) -> None:
    res = client.post("/api/patients", json={**NEW, "birthDate": "1978-03-12"}, headers=owner.headers)
    assert res.status_code == 201, res.text
    assert (res.json()["birthDate"], res.json()["birthYear"]) == ("1978-03-12", 1978)
    item = client.get("/api/patients", headers=owner.headers).json()["items"][0]
    assert (item["birthDate"], item["birthYear"]) == ("1978-03-12", 1978)
    same = client.post("/api/patients", json={**NEW, "birthDate": "1990-01-02", "birthYear": 1990}, headers=owner.headers)
    assert same.status_code == 201 and same.json()["birthYear"] == 1990


def test_a_year_alone_stays_valid(client: TestClient, owner: Any, make_patient: Factory) -> None:
    res = client.post("/api/patients", json={**NEW, "birthYear": 1985}, headers=owner.headers)
    assert (res.json()["birthDate"], res.json()["birthYear"]) == (None, 1985)
    old = make_patient(owner.practice, birth_year=1960)  # a patient from before the birth date existed
    assert client.get(f"/api/patients/{old.id}", headers=owner.headers).json()["birthDate"] is None


@pytest.mark.parametrize(
    ("body", "code"),
    [({"birthDate": "1978-03-12", "birthYear": 1979}, "birth_year_mismatch"),
     ({"birthDate": "2026-10-31"}, "invalid_birth_date"),  # tomorrow
     ({"birthDate": "1899-12-31"}, "invalid_birth_date"),
     ({"birthDate": "12/03/1978"}, "validation")],
)
def test_a_wrong_birth_date_is_refused(client: TestClient, owner: Any, body: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/patients", json={**NEW, **body}, headers=owner.headers), 422, code)


def test_changing_the_date_or_the_year(client: TestClient, owner: Any, make_patient: Factory) -> None:
    pat = make_patient(owner.practice, birth_year=1980)
    res = client.patch(f"/api/patients/{pat.id}", json={"birthDate": "1978-03-12"}, headers=owner.headers)
    assert res.status_code == 200, res.text
    assert (res.json()["birthDate"], res.json()["birthYear"]) == ("1978-03-12", 1978)  # the date wins over the old year
    assert_problem(client.patch(f"/api/patients/{pat.id}", json={"birthYear": 1979}, headers=owner.headers), 422,
                   "birth_year_mismatch")
    assert_problem(client.patch(f"/api/patients/{pat.id}", json={"birthYear": None}, headers=owner.headers), 422,
                   "birth_year_mismatch")
    assert client.patch(f"/api/patients/{pat.id}", json={"birthYear": 1978, "notes": "x"}, headers=owner.headers).status_code == 200
    cleared = client.patch(f"/api/patients/{pat.id}", json={"birthDate": None}, headers=owner.headers).json()
    assert (cleared["birthDate"], cleared["birthYear"]) == (None, 1978)  # the year stays
    both = client.patch(f"/api/patients/{pat.id}", json={"birthDate": None, "birthYear": None}, headers=owner.headers).json()
    assert (both["birthDate"], both["birthYear"]) == (None, None)
    again = client.patch(f"/api/patients/{pat.id}", json={"birthDate": "2001-07-01", "birthYear": None}, headers=owner.headers)
    assert again.status_code == 200 and again.json()["birthYear"] == 2001  # the form clears the year field


def test_the_import_keeps_the_full_birth_date(client: TestClient, owner: Any, make_patient: Factory) -> None:
    from daftar.imports import birth_values

    assert birth_values(date(1978, 3, 12), None, current=None) == {"birth_date": date(1978, 3, 12), "birth_year": 1978}
    assert birth_values(None, 1985, current=None) == {"birth_year": 1985}
    # a year alone never overwrites a known date of another year – the date is more precise
    assert birth_values(None, 1985, current=date(1978, 3, 12)) == {}
    assert birth_values(None, 1978, current=date(1978, 3, 12)) == {}
    assert birth_values(None, None, current=None) == {}

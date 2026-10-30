"""Slugs (sub-domains), opening hours, specialties and their default service catalogs, governorates."""

from datetime import date, time
from typing import Any

import pytest
from pydantic import ValidationError

from daftar.catalog import DEFAULT_CATALOGS, SPECIALTIES, insert_default_services
from daftar.hours import DEFAULT_WEEKLY_HOURS, WeeklyHours, agenda_range, windows_for
from daftar.schemas import ApiModel
from daftar.slugs import RESERVED_SLUGS, demo_slug, slug_problem, suggest_slug
from daftar.tunisia import GOVERNORATES

# --- slugs ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("slug", ["cabinet-lac", "dr-ben-salah", "abc", "a1b", "x" * 40, "demo-ab12cd34"])
def test_valid_slugs(slug: str) -> None:
    assert slug_problem(slug) is None


@pytest.mark.parametrize(
    "slug",
    ["ab", "x" * 41, "-cabinet", "cabinet-", "Cabinet", "cabinet_lac", "cabinet lac", "café", "", "cabinet.lac"],
)
def test_invalid_slugs(slug: str) -> None:
    assert slug_problem(slug) == "invalid"


@pytest.mark.parametrize("slug", ["www", "app", "api", "admin", "demo", "mail", "smtp", "static", "assets", "daftar", "status", "monitoring", "test"])
def test_reserved_slugs(slug: str) -> None:
    assert slug in RESERVED_SLUGS
    assert slug_problem(slug) == "reserved"


@pytest.mark.parametrize(
    ("name", "want"),
    [
        ("Cabinet Dentaire El Menzah", "cabinet-dentaire-el-menzah"),
        ("Dr. Leïla Ben Salah", "dr-leila-ben-salah"),
        ("  Kiné  & Sport!! ", "kine-sport"),
        ("عيادة", "cabinet"),  # nothing Latin left
        ("Ab", "ab-cabinet"),  # too short alone
        ("Un nom de cabinet vraiment beaucoup trop long pour une adresse", "un-nom-de-cabinet-vraiment-beaucoup-trop"),
        ("Admin", "admin-cabinet"),  # reserved
    ],
)
def test_suggest_slug(name: str, want: str) -> None:
    assert suggest_slug(name) == want
    assert slug_problem(suggest_slug(name)) is None


def test_demo_slugs() -> None:
    slugs = {demo_slug() for _ in range(50)}
    assert len(slugs) == 50
    for slug in slugs:
        assert slug.startswith("demo-") and len(slug) == 13 and slug_problem(slug) is None


# --- opening hours --------------------------------------------------------------------------------------------------


def test_default_hours_are_monday_to_saturday_with_a_lunch_break() -> None:
    assert DEFAULT_WEEKLY_HOURS == {
        **{str(d): [["08:00", "12:30"], ["14:00", "18:00"]] for d in range(1, 7)},
        "7": [],
    }


def test_windows_for_a_day() -> None:
    assert windows_for(DEFAULT_WEEKLY_HOURS, date(2026, 10, 30)) == [(time(8, 0), time(12, 30)), (time(14, 0), time(18, 0))]
    assert windows_for(DEFAULT_WEEKLY_HOURS, date(2026, 11, 1)) == []  # Sunday
    assert windows_for({"1": [["09:00", "13:00"]]}, date(2026, 11, 3)) == []  # days missing in the JSON are closed


def test_agenda_range_is_earliest_to_latest_opening() -> None:
    hours = {**{str(d): [] for d in range(1, 8)}, "2": [["09:30", "12:00"]], "6": [["07:45", "11:00"]], "4": [["14:00", "19:15"]]}
    assert agenda_range(hours) == (time(7, 45), time(19, 15))
    assert agenda_range({str(d): [] for d in range(1, 8)}) is None


class _Hours(ApiModel):
    weekly_hours: WeeklyHours


def test_weekly_hours_validation_normalizes() -> None:
    model = _Hours.model_validate({"weeklyHours": {"1": [["14:00", "18:00"], ["08:00", "12:00"]], "7": []}})
    assert model.weekly_hours["1"] == [["08:00", "12:00"], ["14:00", "18:00"]]  # sorted
    assert model.weekly_hours["3"] == []  # every day present after validation


@pytest.mark.parametrize(
    "hours",
    [
        {"8": [["08:00", "12:00"]]},  # no such weekday
        {"1": [["12:00", "08:00"]]},  # end before start
        {"1": [["08:00", "08:00"]]},
        {"1": [["8:00", "12:00"]]},  # HH:MM only
        {"1": [["08:00", "24:30"]]},
        {"1": [["08:00", "12:00"], ["11:00", "13:00"]]},  # overlapping windows
        {"1": [["08:00"]]},
        {"1": [["08:00", "12:00"]] * 7},  # at most 6 windows a day
    ],
)
def test_weekly_hours_validation_rejects(hours: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _Hours.model_validate({"weeklyHours": hours})


# --- specialties and catalogs ---------------------------------------------------------------------------------------


def test_every_specialty_has_a_catalog() -> None:
    assert SPECIALTIES == (
        "generaliste", "dentiste", "pediatre", "gynecologue", "dermatologue", "ophtalmologue",
        "cardiologue", "orl", "kinesitherapeute", "psychologue", "autre",
    )
    assert set(DEFAULT_CATALOGS) == set(SPECIALTIES)
    for specialty, items in DEFAULT_CATALOGS.items():
        assert items, specialty
        assert any(item.online_bookable for item in items), specialty
        for item in items:
            assert item.name_fr and item.name_ar and 5 <= item.duration_min <= 480, (specialty, item)


@pytest.mark.parametrize(
    ("specialty", "expected"),
    [
        ("generaliste", [("Consultation", 20), ("Contrôle", 15), ("Certificat médical", 10), ("Vaccination", 15), ("Urgence", 20)]),
        ("pediatre", [("Consultation", 30), ("Suivi croissance", 20), ("Vaccination", 15)]),
        ("kinesitherapeute", [("Séance", 45), ("Bilan", 60)]),
        ("psychologue", [("Séance", 50), ("Premier entretien", 60)]),
        ("autre", [("Consultation", 30), ("Contrôle", 20)]),
    ],
)
def test_catalogs_from_the_design(specialty: str, expected: list[tuple[str, int]]) -> None:
    assert [(i.name_fr, i.duration_min) for i in DEFAULT_CATALOGS[specialty]][: len(expected)] == expected


def test_dentist_catalog_from_section_11() -> None:
    items = DEFAULT_CATALOGS["dentiste"]
    assert [(i.name_fr, i.duration_min) for i in items] == [
        ("Consultation", 30), ("Contrôle", 20), ("Détartrage", 45), ("Soin carie / composite", 45), ("Extraction", 30),
        ("Traitement de canal", 60), ("Couronne – séance", 60), ("Blanchiment", 60), ("Urgence / douleur", 30),
    ]
    assert [i.name_fr for i in items if i.online_bookable] == ["Consultation", "Contrôle", "Détartrage"]


def test_insert_default_services(db: Any, make_practice: Any) -> None:
    from sqlalchemy import select

    from daftar.tables import service

    p = make_practice(specialty="pediatre")
    with db.begin() as conn:
        assert insert_default_services(conn, p.id, "pediatre") == len(DEFAULT_CATALOGS["pediatre"])
        rows = conn.execute(select(service).where(service.c.practice_id == p.id).order_by(service.c.sort)).all()
    assert [(r.name_fr, r.duration_min, r.price_millimes, r.active) for r in rows[:2]] == [
        ("Consultation", 30, None, True),
        ("Suivi croissance", 20, None, True),
    ]
    assert [r.sort for r in rows] == list(range(1, len(rows) + 1))


def test_twenty_four_governorates() -> None:
    assert len(GOVERNORATES) == 24
    assert {"tunis", "ariana", "ben_arous", "manouba", "sfax", "sousse", "kebili", "tozeur"} <= set(GOVERNORATES)

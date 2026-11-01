"""Sterilisation and specimen labels (spec stock-hygiène 5.3, 6, 7) – rules without a database."""

from datetime import date

import pytest

from daftar.catalog import SPECIALTIES
from daftar.label_rules import (
    LABEL_FORMATS,
    PACKAGINGS,
    SPECIMEN_KINDS,
    PackQuery,
    initials,
    label_settings,
    next_label_code,
    pack_code,
    pack_contents,
    pack_query,
    pack_state,
    specimen_code,
    sterile_until,
)


def test_a_pack_code_names_autoclave_cycle_and_pack() -> None:
    assert pack_code("A3", 412, 7) == "A3-0412-07"
    assert pack_code("A1", 1, 1) == "A1-0001-01"
    assert pack_code("A12", 123456, 99) == "A12-123456-99"  # a long counter of the autoclave stays readable


def test_specimen_codes_are_short_and_unique_per_print() -> None:
    assert specimen_code(1042, 3) == "E1042-03"
    assert specimen_code(7, 12) == "E7-12"


def test_the_next_autoclave_code_follows_the_codes_given_and_never_comes_back() -> None:
    assert next_label_code(0) == "A1"
    assert next_label_code(2) == "A3"  # A1 and A2 were given – even if A1's autoclave is gone, A1 stays its code
    assert next_label_code(98) == "A99"
    with pytest.raises(ValueError):
        next_label_code(99)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Nisrine Hamza", "NH"), ("Dr. Amira Ben Salem", "ABS"), ("Dr Fadoua", "F"), ("  karim  ", "K"),
     ("Pr. Ali Ben Salah Trabelsi", "ABS"), ("نسرين حمزة", "نح"), ("", "")],
)
def test_initials_skip_titles_and_keep_three_letters(name: str, expected: str) -> None:
    assert initials(name) == expected


def test_a_pack_is_sterile_before_its_date_only() -> None:
    sterilised = date(2026, 11, 1)
    assert sterile_until(sterilised, 90) == date(2027, 1, 30)
    until = sterile_until(sterilised, 90)
    assert pack_state(result="ok", used=False, expires_on=until, today=date(2027, 1, 29)) == "usable"
    assert pack_state(result="ok", used=False, expires_on=until, today=until) == "expired"  # "à utiliser avant le …"
    assert pack_state(result="ok", used=True, expires_on=until, today=date(2027, 3, 1)) == "used"
    # a cycle found "non conforme" later recalls every pack, used or not
    assert pack_state(result="not_ok", used=True, expires_on=until, today=sterilised) == "not_sterile"
    assert pack_state(result="not_ok", used=False, expires_on=until, today=sterilised) == "not_sterile"
    # a cancelled cycle (entered by mistake) keeps its codes, none of its labels is valid
    assert pack_state(result="ok", used=False, expires_on=until, today=sterilised, cancelled=True) == "cancelled"
    assert pack_state(result="not_ok", used=False, expires_on=until, today=until, cancelled=True) == "cancelled"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("A3-0412-07", PackQuery(code="A3-0412-07", device="A3", number=412, seq=7)),
     ("a3 0412 07", PackQuery(code="A3-0412-07", device="A3", number=412, seq=7)),
     ("412-7", PackQuery(code=None, device=None, number=412, seq=7)),
     ("412", PackQuery(code=None, device=None, number=412, seq=None)),
     ("A3-412", PackQuery(code=None, device="A3", number=412, seq=None)),
     ("kit", None), ("", None), ("A3-0412-07-1", None)],
)
def test_what_the_desk_types_finds_the_pack(text: str, expected: PackQuery | None) -> None:
    assert pack_query(text) == expected


@pytest.mark.parametrize(
    ("typed", "code"),
    [("Q&)à'&é)àè", "A1-0412-07"),  # a scanner in its US layout on a French (AZERTY) keyboard
     ("Qé)àààç)&à", "A2-0009-10"),
     ("q&)à\"(-)àà", "A1-0356-00"),
     ("\u06341-0412-07", "A1-0412-07"),  # … on an Arabic keyboard: the key of A writes a shin (shifted: a kasra)
     ("\u06501-0412-07", "A1-0412-07")],
)
def test_a_scanner_typing_in_the_wrong_keyboard_layout_still_finds_the_pack(typed: str, code: str) -> None:
    found = pack_query(typed)
    assert found is not None and found.code == code


def test_ordinary_text_is_not_mistaken_for_a_scanned_code() -> None:
    assert pack_query("Kit d'extraction") is None
    assert pack_query("(é)") is None


def test_settings_have_defaults_and_keep_what_the_practice_chose() -> None:
    defaults = label_settings({})
    assert defaults == {
        "formats": {"sterile": "roll62", "specimen": "roll62"},
        "shelf_life_days": {"sachet": 90, "double_sachet": 90, "conteneur": 90, "champ": 90},
    }
    chosen = label_settings({"formats": {"specimen": "a4_3x8", "sterile": "fax"}, "shelf_life_days": {"sachet": 30, "x": 9}})
    assert chosen["formats"] == {"sterile": "roll62", "specimen": "a4_3x8"}  # unknown values fall back
    assert chosen["shelf_life_days"]["sachet"] == 30 and "x" not in chosen["shelf_life_days"]
    assert set(LABEL_FORMATS) == {"roll62", "label57x32", "a4_3x8"}
    assert PACKAGINGS == ("sachet", "double_sachet", "conteneur", "champ")


def test_specimen_kinds_follow_the_spec() -> None:
    assert SPECIMEN_KINDS == ("edta", "sec", "citrate", "heparine", "urine", "selles", "frottis", "autre")


@pytest.mark.parametrize("specialty", SPECIALTIES)
def test_every_specialty_has_pack_templates_in_both_languages(specialty: str) -> None:
    fr, ar = pack_contents(specialty, "fr"), pack_contents(specialty, "ar")
    assert len(fr) == len(ar) >= 3
    assert all(0 < len(x) <= 60 for x in fr + ar)
    if specialty == "dentiste":
        assert {"Kit examen", "Kit extraction"} <= set(fr)

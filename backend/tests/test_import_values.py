"""Import value rules (section 14): amounts, dates, times, phones, names, yes/no, language, header suggestions."""

from datetime import date, datetime, time

import pytest

from daftar.import_values import (
    ImportValueError,
    is_date_only,
    parse_bool,
    parse_date,
    parse_datetime,
    parse_duration,
    parse_lang,
    parse_millimes,
    parse_phone,
    parse_time,
    parse_year,
    split_full_name,
    suggest_mapping,
)

# --- amounts: the one rule -------------------------------------------------------------------------------------
# Amounts are dinars. Spaces separate thousands. With "." and "," the LAST one is the decimal separator.
# A single separator that occurs once is ALWAYS the decimal separator (Tunisian notation: 12,500 DT = 12.5 DT);
# one that occurs several times separates thousands. Text with more than 3 decimals is refused (no silent rounding);
# numeric Excel cells (floats) are rounded half-up to the millime. Negative amounts are refused.


@pytest.mark.parametrize(
    ("raw", "millimes"),
    [
        ("12,5", 12_500),
        ("12.5", 12_500),
        ("12,500", 12_500),
        ("12.500", 12_500),
        ("12,050", 12_050),
        ("120", 120_000),
        ("0,001", 1),
        ("1 250,500", 1_250_500),
        ("1 250,5", 1_250_500),
        ("1 250", 1_250_000),
        ("1.250,5", 1_250_500),
        ("1,250.5", 1_250_500),
        ("1.250", 1_250),  # once → decimal: 1,250 DT (not one thousand)
        ("12 000", 12_000_000),
        ("120 DT", 120_000),
        ("120DT", 120_000),
        ("120 TND", 120_000),
        ("120 د.ت", 120_000),
        ("+120", 120_000),
        ("0", 0),
        (120, 120_000),
        (12.5, 12_500),
        (12.0005, 12_001),  # numeric cells: half-up to the millime
        (10 / 3, 3_333),
        (0, 0),
    ],
)
def test_amounts(raw: object, millimes: int) -> None:
    assert parse_millimes(raw) == millimes


@pytest.mark.parametrize(
    "raw",
    [
        "12,3456",  # more than 3 decimals in text: refused, not rounded
        "-5", "-5,000", -1,  # no negative balances
        "abc", "1e5", True, float("nan"), float("inf"),
        "12,5,0.1", "12 5", "1.25.000",  # thousands groups must have 3 digits
        "1.250.000", "1,250,000",  # several separators = thousands → 1 250 000 DT, above the limit
        "100000,001", "100 001",  # above 100 000 DT
    ],
)
def test_invalid_amounts(raw: object) -> None:
    with pytest.raises(ImportValueError):
        parse_millimes(raw)


def test_empty_amount_is_none() -> None:
    assert parse_millimes("") is None and parse_millimes(None) is None and parse_millimes("  ") is None


# --- dates and times -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "fmt", "expected"),
    [
        ("30/10/2026", "dmy", date(2026, 10, 30)),
        ("30-10-2026", "dmy", date(2026, 10, 30)),
        ("30.10.2026", "dmy", date(2026, 10, 30)),
        ("3/1/2026", "dmy", date(2026, 1, 3)),
        ("3/1/2026", "mdy", date(2026, 3, 1)),
        ("2026-10-30", "dmy", date(2026, 10, 30)),
        ("2026/10/30", "mdy", date(2026, 10, 30)),
        ("2026-10-30", "ymd", date(2026, 10, 30)),
        ("30/10/26", "dmy", date(2026, 10, 30)),
        ("30/10/85", "dmy", date(1985, 10, 30)),
        ("30/10/2026 09:30", "dmy", date(2026, 10, 30)),
        ("2026-10-30T09:30:00", "dmy", date(2026, 10, 30)),
        (datetime(2026, 10, 30, 9, 30), "dmy", date(2026, 10, 30)),
        (date(1985, 3, 1), "dmy", date(1985, 3, 1)),
        (45000, "dmy", date(2023, 3, 15)),  # Excel serial number
        (45000.75, "dmy", date(2023, 3, 15)),
        ("45000", "dmy", date(2023, 3, 15)),
    ],
)
def test_dates(raw: object, fmt: str, expected: date) -> None:
    assert parse_date(raw, fmt, today=date(2026, 10, 30)) == expected


@pytest.mark.parametrize("raw", ["31/02/2026", "2026-13-01", "demain", "12", "0", 3_000_000, "30/10"])
def test_invalid_dates(raw: object) -> None:
    with pytest.raises(ImportValueError):
        parse_date(raw, "dmy", today=date(2026, 10, 30))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("09:30", time(9, 30)), ("9:30", time(9, 30)), ("9h30", time(9, 30)), ("09H30", time(9, 30)), ("9h", time(9, 0)),
     ("14:05:00", time(14, 5)), (time(8, 15), time(8, 15)), (datetime(2026, 1, 1, 16, 45), time(16, 45)),
     (0.375, time(9, 0)), (0.5208333333, time(12, 30))],
)
def test_times(raw: object, expected: time) -> None:
    assert parse_time(raw) == expected


@pytest.mark.parametrize("raw", ["25:00", "9:75", "midi", 1.5, -0.1])
def test_invalid_times(raw: object) -> None:
    with pytest.raises(ImportValueError):
        parse_time(raw)


def test_datetimes() -> None:
    assert parse_datetime("30/10/2026 09:30", "dmy", today=date(2026, 10, 30)) == datetime(2026, 10, 30, 9, 30)
    assert parse_datetime(datetime(2026, 10, 30, 9, 30), "dmy", today=date(2026, 10, 30)) == datetime(2026, 10, 30, 9, 30)
    assert parse_datetime(46325.375, "dmy", today=date(2026, 10, 30)) == datetime(2026, 10, 30, 9, 0)
    with pytest.raises(ImportValueError):
        parse_datetime("30/10/2026", "dmy", today=date(2026, 10, 30))  # no time


@pytest.mark.parametrize(("raw", "minutes"), [("30", 30), (45, 45), (45.0, 45), ("30 min", 30), ("1h", 60), ("1h30", 90),
                                              ("1:15", 75)])
def test_durations(raw: object, minutes: int) -> None:
    assert parse_duration(raw) == minutes


@pytest.mark.parametrize("raw", ["0", "4", "481", "beaucoup", 30.5])
def test_invalid_durations(raw: object) -> None:
    with pytest.raises(ImportValueError):
        parse_duration(raw)


def test_years() -> None:
    assert parse_year("1985", today=date(2026, 10, 30)) == 1985
    assert parse_year(1985.0, today=date(2026, 10, 30)) == 1985
    for bad in ("1899", "2027", "85", "abc"):
        with pytest.raises(ImportValueError):
            parse_year(bad, today=date(2026, 10, 30))


# --- phones ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (20123456, "+21620123456"),
        (20123456.0, "+21620123456"),
        ("20123456.0", "+21620123456"),
        ("2.0123456E7", "+21620123456"),
        (21620123456, "+21620123456"),  # 00216… stored as a number loses the leading zeros
        ("0021620123456", "+21620123456"),
        ("+216 20 123 456", "+21620123456"),
        ("20 123 456 / 98 765 432", "+21620123456"),  # several numbers: the first valid one
        ("98-765-432 ; 71 000 000", "+21698765432"),
        ("+33 6 12 34 56 78", "+33612345678"),
        ("٢٠١٢٣٤٥٦", "+21620123456"),  # Arabic-Indic digits from an Arabic keyboard (security review N1)
        ("٢٠ ١٢٣ ٤٥٦ / ۹۸ ۷۶۵ ۴۳۲", "+21620123456"),
    ],
)
def test_phones(raw: object, expected: str) -> None:
    assert parse_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "abc", 1234567, "06 12 34 56 78", "２０１２３４５６", "२०१२३४५६"])
def test_invalid_phones(raw: object) -> None:
    with pytest.raises(ImportValueError):
        parse_phone(raw)


# --- names, yes/no, language -----------------------------------------------------------------------------------

def test_full_names_are_split_by_the_chosen_order() -> None:
    assert split_full_name("Ben Ali  Amira", "last_first") == ("Amira", "Ben Ali")
    assert split_full_name("Amira Ben Ali", "first_last") == ("Amira", "Ben Ali")
    assert split_full_name("الطرابلسي أميرة", "last_first") == ("أميرة", "الطرابلسي")
    with pytest.raises(ImportValueError):
        split_full_name("Trabelsi", "last_first")


@pytest.mark.parametrize(("raw", "expected"), [("oui", True), ("Oui", True), ("x", True), ("1", True), (1, True), (True, True),
                                               ("نعم", True), ("yes", True), ("non", False), ("0", False), (0, False),
                                               ("لا", False), ("", None), (None, None)])
def test_yes_no(raw: object, expected: bool | None) -> None:
    assert parse_bool(raw) is expected


def test_yes_no_rejects_other_text() -> None:
    with pytest.raises(ImportValueError):
        parse_bool("peut-être")


@pytest.mark.parametrize(("raw", "expected"), [("fr", "fr"), ("Français", "fr"), ("francais", "fr"), ("F", "fr"),
                                               ("ar", "ar"), ("Arabe", "ar"), ("عربي", "ar"), ("العربية", "ar"), ("", None)])
def test_languages(raw: str, expected: str | None) -> None:
    assert parse_lang(raw) == expected


def test_unknown_language() -> None:
    with pytest.raises(ImportValueError):
        parse_lang("allemand")


# --- suggestion from headers -----------------------------------------------------------------------------------

def test_french_headers() -> None:
    headers = ["N° dossier", "Nom", "Prénom", "Tél.", "Date de naissance", "Allergies", "Reste à payer", "Remarques"]
    assert suggest_mapping(headers) == {
        "externalRef": 0, "lastName": 1, "firstName": 2, "phone": 3, "birthDate": 4, "alerts": 5,
        "openingBalance": 6, "notes": 7,
    } | {k: None for k in ("fullName", "birthYear", "lang", "reminderConsent", "date", "time", "datetime",
                           "durationMin", "endTime", "service", "practitioner")}


def test_arabic_and_english_headers() -> None:
    m = suggest_mapping(["اللقب", "الاسم", "الهاتف", "تاريخ الولادة"])
    assert (m["lastName"], m["firstName"], m["phone"], m["birthDate"]) == (0, 1, 2, 3)
    m = suggest_mapping(["Full name", "Mobile", "Year of birth", "Language"])
    assert (m["fullName"], m["phone"], m["birthYear"], m["lang"]) == (0, 1, 2, 3)
    m = suggest_mapping(["Nom et prénom", "GSM", "Solde"])
    assert (m["fullName"], m["lastName"], m["firstName"], m["phone"], m["openingBalance"]) == (0, None, None, 1, 2)


def test_appointment_headers() -> None:
    m = suggest_mapping(["Date RDV", "Heure", "Durée", "Patient", "Téléphone", "Acte", "Médecin", "Observation"])
    assert (m["date"], m["time"], m["durationMin"], m["fullName"], m["phone"], m["service"], m["practitioner"], m["notes"]) == (
        0, 1, 2, 3, 4, 5, 6, 7)


def test_each_column_is_suggested_once() -> None:
    m = suggest_mapping(["Téléphone", "Téléphone 2", "Nom"])
    assert m["phone"] == 0 and m["lastName"] == 2
    assert list(m.values()).count(0) == 1


def test_an_appointment_column_rdv_next_to_a_time_column_is_the_date() -> None:
    """Code review M5: "RDV" (Excel date cells) + "Heure" used to become one date-time column – every visit at 00:00."""
    m = suggest_mapping(["RDV", "Heure", "Nom", "Prénom", "Tél"])
    assert (m["date"], m["time"], m["datetime"]) == (0, 1, None)
    assert suggest_mapping(["Rendez-vous", "Nom"])["datetime"] == 0  # without a time column it holds both


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(datetime(2026, 11, 5), True), (date(2026, 11, 5), True), (46331, True), ("46331", True), ("05/11/2026", True),
     (datetime(2026, 11, 5, 9, 30), False), (46331.375, False), ("05/11/2026 09:30", False), ("demain", False)],
)
def test_a_cell_with_a_day_but_no_time(raw: object, expected: bool) -> None:
    assert is_date_only(raw, "dmy", today=date(2026, 10, 31)) is expected


def test_two_digit_years_of_appointments_take_the_nearest_century() -> None:
    """Code review N10: "05/01/27" in a list of visits is January 2027, not 1927; birth dates stay in the past."""
    today = date(2026, 10, 31)
    assert parse_date("05/01/27", "dmy", today=today, nearest_century=True) == date(2027, 1, 5)
    assert parse_date("20/10/26", "dmy", today=today, nearest_century=True) == date(2026, 10, 20)
    assert parse_date("14/03/98", "dmy", today=today, nearest_century=True) == date(1998, 3, 14)
    assert parse_datetime("05/01/27 09:00", "dmy", today=today, nearest_century=True) == datetime(2027, 1, 5, 9, 0)
    assert parse_date("05/01/27", "dmy", today=today) == date(1927, 1, 5)  # a birth date

"""Reading spreadsheets for the import (section 14): xlsx, xls, csv/txt with encoding and delimiter detection."""

import codecs
import io
import zipfile
from datetime import datetime

import pytest

from daftar.import_files import MAX_BYTES, ImportFileError, read_table, read_workbook
from tests.import_helpers import csv_bytes, xls_biff2, xlsx


def test_xlsx_with_several_sheets_and_typed_cells() -> None:
    data = xlsx(
        ("Patients", [["Nom", "Tél", "Naissance"], ["Trabelsi", 20123456, datetime(1985, 3, 1)],
                      [None, None, None], ["Ben Ali", 98765432.0, 31107]]),
        ("Vide", []),
    )
    book = read_workbook("patients.xlsx", data)
    assert book.sheet_names == ["Patients", "Vide"]
    table = read_table(book, "Patients", header_row=1)
    assert table.headers == ["Nom", "Tél", "Naissance"]
    assert [(n, cells) for n, cells in table.rows] == [
        (2, ["Trabelsi", 20123456, datetime(1985, 3, 1)]),
        (4, ["Ben Ali", 98765432.0, 31107]),  # the empty row 3 is skipped, numbering stays the sheet's
    ]


def test_header_row_choice_and_files_without_headers() -> None:
    book = read_workbook("x.xlsx", xlsx(("F", [["Liste des patients"], ["Nom", "Prénom"], ["A", "B"]])))
    assert read_table(book, "F", header_row=2).headers == ["Nom", "Prénom"]
    plain = read_table(book, "F", header_row=0)
    assert plain.headers == ["Colonne A", "Colonne B"]
    assert [n for n, _ in plain.rows] == [1, 2, 3]
    with pytest.raises(ImportFileError) as caught:
        read_table(book, "F", header_row=4)
    assert caught.value.code == "invalid_header_row"
    with pytest.raises(ImportFileError) as caught:
        read_table(book, "G", header_row=1)
    assert caught.value.code == "unknown_sheet"


def test_blank_header_cells_get_a_column_name() -> None:
    book = read_workbook("x.xlsx", xlsx(("F", [["Nom", None, "Tél"], ["A", "x", "20123456"]])))
    assert read_table(book, "F", header_row=1).headers == ["Nom", "Colonne B", "Tél"]


def test_xls_files_are_read_with_xlrd() -> None:
    book = read_workbook("ancien.xls", xls_biff2([["Nom", "Tel", "Ne le"], ["Trabelsi", 20123456.0, 31107.0]]))
    table = read_table(book, book.sheet_names[0], header_row=1)
    assert table.headers == ["Nom", "Tel", "Ne le"]
    assert table.rows == [(2, ["Trabelsi", 20123456.0, 31107.0])]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (csv_bytes(["Nom;Prénom;Solde", "Trabelsi;Amira;12,5"]), ["Trabelsi", "Amira", "12,5"]),
        (codecs.BOM_UTF8 + csv_bytes(["Nom;Prénom;Solde", "Trabelsi;Amira;12,5"]), ["Trabelsi", "Amira", "12,5"]),
        (csv_bytes(["Nom,Prénom,Solde", 'Trabelsi,Amira,"12,5"']), ["Trabelsi", "Amira", "12,5"]),
        (csv_bytes(["Nom\tPrénom\tSolde", "Trabelsi\tAmira\t12,5"]), ["Trabelsi", "Amira", "12,5"]),
        (codecs.BOM_UTF16_LE + "Nom\tPrénom\tSolde\r\nTrabelsi\tAmira\t12,5".encode("utf-16-le"), ["Trabelsi", "Amira", "12,5"]),
        (csv_bytes(["Nom;Prénom;Solde", "Trabelsi;Amira;12,5"], newline="\n"), ["Trabelsi", "Amira", "12,5"]),
    ],
)
def test_csv_delimiters_and_unicode_encodings(data: bytes, expected: list[str]) -> None:
    book = read_workbook("export.csv", data)
    table = read_table(book, book.sheet_names[0], header_row=1)
    assert table.headers == ["Nom", "Prénom", "Solde"]
    assert table.rows == [(2, expected)]


def test_arabic_csv_in_windows_1256() -> None:
    data = csv_bytes(["اللقب;الاسم;الهاتف", "الطرابلسي;أميرة;20123456", "بن علي;سامي;98765432"], encoding="cp1256")
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")
    table = read_table(read_workbook("مرضى.csv", data), "CSV", header_row=1)
    assert table.headers == ["اللقب", "الاسم", "الهاتف"]
    assert table.rows[1] == (3, ["بن علي", "سامي", "98765432"])


def test_french_csv_in_windows_1252() -> None:
    data = csv_bytes(["Nom;Prénom;Remarque", "Lefèvre;Élodie;Allergie à l'aspirine – œdème"], encoding="cp1252")
    table = read_table(read_workbook("patients.txt", data), "CSV", header_row=1)
    assert table.rows == [(2, ["Lefèvre", "Élodie", "Allergie à l'aspirine – œdème"])]


def test_csv_quotes_and_nul_bytes() -> None:
    data = csv_bytes(['Nom;Notes', '"Ben Ali";"ligne 1\nligne 2; avec point-virgule"', "Gharbi\x00;x"])
    table = read_table(read_workbook("a.csv", data), "CSV", header_row=1)
    assert table.rows == [(2, ["Ben Ali", "ligne 1\nligne 2; avec point-virgule"]), (3, ["Gharbi", "x"])]


def test_limits() -> None:
    with pytest.raises(ImportFileError) as caught:
        read_workbook("big.csv", b"x" * (MAX_BYTES + 1))
    assert (caught.value.status, caught.value.code) == (413, "file_too_large")

    lines = ["Nom;Tel"] + [f"N{i};{20000000 + i}" for i in range(20_001)]
    book = read_workbook("many.csv", csv_bytes(lines))
    with pytest.raises(ImportFileError) as caught:
        read_table(book, "CSV", header_row=1)
    assert (caught.value.status, caught.value.code) == (422, "too_many_rows")
    assert len(read_table(read_workbook("ok.csv", csv_bytes(lines[:20_001])), "CSV", header_row=1).rows) == 20_000

    wide = csv_bytes([";".join(f"c{i}" for i in range(101)), ";".join("x" for _ in range(101))])
    with pytest.raises(ImportFileError) as caught:
        read_table(read_workbook("wide.csv", wide), "CSV", header_row=1)
    assert caught.value.code == "too_many_columns"


def test_zip_bombs_are_refused() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/worksheets/sheet1.xml", " " * (70 * 1024 * 1024))
    assert len(out.getvalue()) < MAX_BYTES
    with pytest.raises(ImportFileError) as caught:
        read_workbook("bomb.xlsx", out.getvalue())
    assert caught.value.code == "file_too_complex"


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("vide.csv", b"", "empty_file"),
        ("vide.csv", b"\r\n\r\n", "empty_file"),
        ("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "unsupported_file"),
        ("doc.pdf", b"%PDF-1.7 ...", "unsupported_file"),
        ("faux.xlsx", b"PK\x03\x04 not really a zip", "unreadable_file"),
        ("texte.docx", None, "unsupported_file"),
        ("faux.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100, "unreadable_file"),
    ],
)
def test_unusable_files(name: str, data: bytes | None, code: str) -> None:
    if data is None:  # a Word file is a zip without a workbook
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("word/document.xml", "<w/>")
        data = out.getvalue()
    with pytest.raises(ImportFileError) as caught:
        read_workbook(name, data)
    assert (caught.value.status, caught.value.code) == (422, code)

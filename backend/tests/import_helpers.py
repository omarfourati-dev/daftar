"""Builders for import test files – everything is generated here, nothing is downloaded."""

from __future__ import annotations

import io
import struct
from typing import Any

from openpyxl import Workbook


def xlsx(*sheets: tuple[str, list[list[Any]]]) -> bytes:
    """``xlsx(("Patients", [["Nom", "Tél"], ["Trabelsi", 20123456]]), ("Autre", [...]))``."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets:
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _record(kind: int, data: bytes = b"") -> bytes:
    return struct.pack("<HH", kind, len(data)) + data


def xls_biff2(rows: list[list[Any]]) -> bytes:
    """A minimal genuine Excel 2.x worksheet (BIFF2 stream, what xlrd reads as .xls): text and number cells."""
    out = [_record(0x0009, struct.pack("<HH", 0x0002, 0x0010)), _record(0x0042, struct.pack("<H", 1252))]
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            head = struct.pack("<HH", r, c) + b"\x00\x00\x00"
            if value is None:
                continue
            if isinstance(value, int | float):
                out.append(_record(0x0003, head + struct.pack("<d", float(value))))
            else:
                text = str(value).encode("cp1252")
                out.append(_record(0x0004, head + bytes([len(text)]) + text))
    out.append(_record(0x000A))
    return b"".join(out)


def csv_bytes(lines: list[str], encoding: str = "utf-8", newline: str = "\r\n") -> bytes:
    return newline.join(lines).encode(encoding)

from typing import Any

import pytest
from pydantic import ValidationError

from daftar.money import Millimes, PositiveMillimes, dinars, format_millimes
from daftar.schemas import ApiModel


@pytest.mark.parametrize(
    ("millimes", "text"),
    [
        (120_000, "120 DT"),
        (12_500, "12,500 DT"),
        (500, "0,500 DT"),
        (5, "0,005 DT"),
        (0, "0 DT"),
        (1_250_000, "1 250 DT"),
        (1_250_050, "1 250,050 DT"),
        (-500, "-0,500 DT"),
    ],
)
def test_format_millimes(millimes: int, text: str) -> None:
    assert format_millimes(millimes) == text


def test_dinars_to_millimes() -> None:
    assert dinars(12.5) == 12_500
    assert dinars(120) == 120_000
    assert dinars(0.001) == 1


class _Payment(ApiModel):
    amount_millimes: PositiveMillimes
    deposit_millimes: Millimes = 0


def test_money_fields_are_whole_millimes_in_camel_case() -> None:
    p = _Payment.model_validate({"amountMillimes": 12_500, "depositMillimes": 0})
    assert p.model_dump() == {"amountMillimes": 12_500, "depositMillimes": 0}


@pytest.mark.parametrize(
    "payload",
    [
        {"amountMillimes": 0},
        {"amountMillimes": -1},
        {"amountMillimes": 12.5},
        {"amountMillimes": "12500"},
        {"amountMillimes": 100_000_001},
        {"amountMillimes": 1, "depositMillimes": -1},
    ],
)
def test_money_fields_reject_invalid_amounts(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _Payment.model_validate(payload)

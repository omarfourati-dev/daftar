"""Rules of the stock module that need no database: traffic light, average price, expiry, order quantity, start lists."""

import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from daftar.catalog import SPECIALTIES
from daftar.stock_rules import (
    CATEGORIES,
    UNITS,
    CostMove,
    cost_order,
    moving_costs,
    expiry_state,
    needs_order,
    reorder_quantity,
    soonest_expiry,
    starter_items,
    stock_status,
)

TODAY = date(2026, 10, 31)


def _migration(name: str) -> object:
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_categories_and_units_are_the_ones_the_database_accepts() -> None:
    migration = _migration("0008_stock.py")
    assert [c.strip(" '") for c in migration.CATEGORIES.split(",")] == list(CATEGORIES)  # type: ignore[attr-defined]
    assert [u.strip(" '") for u in migration.UNITS.split(",")] == list(UNITS)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("quantity", "minimum", "status"),
    [(0, 0, "empty"), (-3, 5, "empty"), (1, 0, "ok"), (5, 5, "low"), (4, 5, "low"), (6, 5, "ok"), (1, 1, "low")],
)
def test_traffic_light(quantity: int, minimum: int, status: str) -> None:
    assert stock_status(quantity, minimum) == status


def test_a_product_never_received_is_grey_not_red() -> None:
    """After the start list: nothing was ever delivered or counted – "Pas encore reçu", not "Épuisé"."""
    assert stock_status(0, 4, received=False) == "unreceived"
    assert not needs_order(stock=0, min_quantity=4, active=True, received=False)


def receipt(move_id: int, quantity: int, price: int | None) -> CostMove:
    return CostMove(move_id, "receipt", quantity, price)


def out(move_id: int, quantity: int, kind: str = "use") -> CostMove:
    return CostMove(move_id, kind, -quantity, None)


def test_the_average_follows_what_is_in_stock() -> None:
    """Review M1: two years at 12 DT, all used; 10 boxes at 18 DT are all that is left – they cost 18 DT."""
    costs = moving_costs([receipt(1, 100, 12_000), out(2, 100), receipt(3, 10, 18_000), out(4, 1)])
    assert costs.average == 18_000
    assert costs.unit_costs == {1: 12_000, 2: 12_000, 3: 18_000, 4: 18_000}


def test_a_delivery_mixes_with_the_stock_left() -> None:
    costs = moving_costs([receipt(1, 10, 12_000), out(2, 4), receipt(3, 10, 16_000), out(4, 1, "waste")])
    assert costs.average == 14_500  # (6 × 12 + 10 × 16) / 16
    assert costs.unit_costs[4] == 14_500
    assert moving_costs([receipt(1, 1, 1), receipt(2, 2, 2)]).average == 2  # 5/3 = 1.67 → half up to the millime
    assert moving_costs([receipt(1, 1, 1), receipt(2, 1, 2)]).average == 2  # 1.5 → 2


def test_a_negative_stock_counts_as_nothing_and_early_uses_take_the_first_price() -> None:
    costs = moving_costs([out(1, 5), receipt(2, 10, 15_000), out(3, 1)])
    assert costs.average == 15_000
    assert costs.unit_costs == {1: 15_000, 2: 15_000, 3: 15_000}  # used before any price was known: the first one


def test_lines_without_a_price_keep_the_average() -> None:
    costs = moving_costs([receipt(1, 10, 12_000), receipt(2, 10, None), out(3, 15), CostMove(4, "adjust", 3, None)])
    assert costs.average == 12_000
    assert costs.unit_costs == {1: 12_000, 2: None, 3: 12_000, 4: 12_000}
    assert moving_costs([receipt(1, 3, None), out(2, 1)]).average is None
    assert moving_costs([receipt(1, 3, None), out(2, 1)]).unit_costs == {1: None, 2: None}
    assert moving_costs([]).average is None


def test_a_delivery_entered_later_counts_from_the_end_of_its_day() -> None:
    entered = datetime(2026, 11, 1, 9, tzinfo=UTC)
    assert cost_order(7, "receipt", entered, date(2026, 11, 1)) == (entered, 7)  # entered the same day
    assert cost_order(7, "receipt", entered, date(2026, 10, 28)) == (datetime(2026, 10, 28, 23, tzinfo=UTC), 7)
    assert cost_order(8, "use", entered, None) == (entered, 8)


def test_soonest_expiry_assumes_the_first_expiring_lots_are_used_first() -> None:
    lots = [(date(2026, 11, 10), 10), (date(2027, 3, 1), 10), (None, 5)]
    assert soonest_expiry(25, lots) == date(2026, 11, 10)
    assert soonest_expiry(15, lots) == date(2027, 3, 1)  # the November lot is used up
    assert soonest_expiry(5, lots) is None  # what is left has no expiry date
    assert soonest_expiry(40, lots) == date(2026, 11, 10)  # more than received (inventory): the oldest lot counts
    assert soonest_expiry(0, lots) is None and soonest_expiry(-2, lots) is None
    assert soonest_expiry(3, []) is None


@pytest.mark.parametrize(
    ("expires", "state"),
    [(None, None), (date(2026, 10, 30), "expired"), (date(2026, 10, 31), "soon"), (date(2026, 11, 29), "soon"),
     (date(2026, 11, 30), None)],
)
def test_expiry_state_flags_expired_and_less_than_30_days(expires: date | None, state: str | None) -> None:
    assert expiry_state(expires, TODAY) == state


def test_what_to_order_and_how_much() -> None:
    assert needs_order(stock=3, min_quantity=3, active=True)
    assert needs_order(stock=-1, min_quantity=2, active=True)
    assert not needs_order(stock=4, min_quantity=3, active=True)
    assert not needs_order(stock=0, min_quantity=0, active=True)  # no threshold: nobody asked to reorder
    assert not needs_order(stock=0, min_quantity=5, active=False)
    assert reorder_quantity(stock=3, min_quantity=5) == 7  # back to twice the minimum
    assert reorder_quantity(stock=-4, min_quantity=5) == 10  # a negative stock is unknown, not a debt
    assert reorder_quantity(stock=0, min_quantity=1) == 2


def test_start_lists_per_specialty() -> None:
    dentist = {i.name_fr for i in starter_items("dentiste")}
    assert {"Gants d’examen", "Carpules d’articaïne", "Pompes à salive", "Sachets de stérilisation"} <= dentist
    gp = {i.name_fr for i in starter_items("generaliste")}
    assert {"Seringues 5 ml", "Tubes EDTA", "Tubes secs", "Tubes citrate", "Bandelettes urinaires"} <= gp
    for specialty in SPECIALTIES:
        items = starter_items(specialty)
        assert len(items) >= 5, specialty
        assert len({i.name_fr.lower() for i in items}) == len(items), specialty
        assert len({i.name_ar for i in items}) == len(items), specialty
        for item in items:
            assert item.category in CATEGORIES and item.unit in UNITS and item.min_quantity >= 1
            assert 1 <= len(item.name_fr) <= 120 and 1 <= len(item.name_ar) <= 120

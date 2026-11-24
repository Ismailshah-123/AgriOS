import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.units.area import AreaUnit, from_hectares, to_hectares


def test_acre_is_exact_international_definition() -> None:
    assert to_hectares(Decimal(1), AreaUnit.ACRE) == Decimal("0.40468564224")


@pytest.mark.parametrize("value", ["0.0001", "1", "2.5", "12.3456", "99999.9999"])
def test_area_round_trip_within_1e_9(value: str) -> None:
    v = Decimal(value)
    for unit in AreaUnit:
        assert abs(from_hectares(to_hectares(v, unit), unit) - v) < Decimal("1e-9")


def test_kanal_and_marla_not_accepted_until_sourced() -> None:
    assert {u.value for u in AreaUnit} == {"ha", "acre"}


def test_cursor_round_trip() -> None:
    ts, rid = datetime(2026, 11, 22, 10, 0, tzinfo=UTC), uuid.uuid4()
    assert decode_cursor(encode_cursor(ts, rid)) == (ts, rid)


@pytest.mark.parametrize("bad", ["", "!!!", "bm90LWpzb24", "WyJ4IiwgInkiXQ"])
def test_invalid_cursor_is_422(bad: str) -> None:
    with pytest.raises(AppError) as exc:
        decode_cursor(bad)
    assert exc.value.status_code == 422 and exc.value.field == "cursor"

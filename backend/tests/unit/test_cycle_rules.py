from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.farms.models import CycleStatus
from app.farms.service import CycleState, validate_cycle

TODAY = date(2026, 11, 22)
FIELD_HA = Decimal("2.0")


def state(**kw: object) -> CycleState:
    base = {"status": CycleStatus.PLANNED, "sowing_date": None, "expected_harvest_date": None,
            "harvest_date": None, "area_ha": None}  # fmt: skip
    return CycleState(**{**base, **kw})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "s",
    [
        state(),
        state(sowing_date=date(2027, 1, 10)),  # planned in the future
        state(
            status=CycleStatus.ACTIVE,
            sowing_date=date(2026, 10, 1),
            expected_harvest_date=date(2027, 3, 1),
            area_ha=Decimal("2.0"),
        ),
        state(
            status=CycleStatus.HARVESTED,
            sowing_date=date(2026, 3, 1),
            harvest_date=date(2026, 7, 1),
        ),
        state(status=CycleStatus.ABANDONED),
    ],  # fmt: skip
)
def test_valid_cycles(s: CycleState) -> None:
    validate_cycle(s, FIELD_HA, TODAY)


@pytest.mark.parametrize(
    ("s", "field"),
    [
        (state(status=CycleStatus.ACTIVE), "sowing_date"),
        (state(status=CycleStatus.ACTIVE, sowing_date=date(2026, 12, 1)), "sowing_date"),
        (state(status=CycleStatus.HARVESTED, sowing_date=date(2026, 3, 1)), "harvest_date"),
        (state(sowing_date=date(2026, 3, 1), harvest_date=date(2026, 2, 1)), "harvest_date"),
        (state(sowing_date=date(2026, 3, 1), harvest_date=date(2026, 12, 1)), "harvest_date"),
        (
            state(sowing_date=date(2026, 3, 1), expected_harvest_date=date(2026, 1, 1)),
            "expected_harvest_date",
        ),
        (state(sowing_date=date(1999, 12, 31)), "sowing_date"),
        (state(sowing_date=date(2028, 1, 1)), "sowing_date"),
        (state(area_ha=Decimal("2.0001")), "area_ha"),
    ],  # fmt: skip
)
def test_invalid_cycles_name_the_field(s: CycleState, field: str) -> None:
    with pytest.raises(AppError) as exc:
        validate_cycle(s, FIELD_HA, TODAY)
    assert (exc.value.status_code, exc.value.field) == (422, field)

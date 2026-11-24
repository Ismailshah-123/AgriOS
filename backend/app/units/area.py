"""Area units. Hectares are stored internally; conversion happens at the API edge.

Only units with an exact, citable definition are accepted for input. Kanal and marla
are deliberately NOT supported yet: their size differs between regions/revenue
systems in Pakistan, so they stay blocked until a verified official source is
recorded (docs/04-database/DATABASE_DESIGN.md, "kanal/marla verified from official
source").
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AreaUnit(StrEnum):
    HECTARE = "ha"
    ACRE = "acre"


@dataclass(frozen=True)
class UnitDefinition:
    unit: AreaUnit
    label: str
    square_metres: Decimal
    source: str


DEFINITIONS: dict[AreaUnit, UnitDefinition] = {
    AreaUnit.HECTARE: UnitDefinition(
        AreaUnit.HECTARE, "hectare", Decimal(10_000), "SI: 1 ha = 10,000 m² (exact)"
    ),
    AreaUnit.ACRE: UnitDefinition(
        AreaUnit.ACRE,
        "acre",
        Decimal("4046.8564224"),
        "International acre: 4,046.8564224 m² (exact, 1959 international yard)",
    ),
}

_HA = DEFINITIONS[AreaUnit.HECTARE].square_metres


def to_hectares(value: Decimal, unit: AreaUnit) -> Decimal:
    return value * DEFINITIONS[unit].square_metres / _HA


def from_hectares(hectares: Decimal, unit: AreaUnit) -> Decimal:
    return hectares * _HA / DEFINITIONS[unit].square_metres

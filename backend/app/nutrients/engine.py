"""Fertilizer arithmetic for FR6 (pure, Decimal). CLAUDE.md hard rule 2: doses come ONLY
from stored, cited, reviewed tables; otherwise the service refuses and escalates.

REVIEWED_TABLES and PRODUCTS are intentionally EMPTY: no Pakistan-specific requirement
table and no product composition source has been reviewed yet (see docs/FEATURE_STATUS.md).
An entry may be added only with its citation, reviewer and review date. Tests exercise the
arithmetic with clearly synthetic test-only tables.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

HA_PER_ACRE = Decimal("0.40468564224")


@dataclass(frozen=True)
class ReviewedTable:
    crop_code: str
    nutrient_kg_per_ha: dict[str, Decimal]  # e.g. {"N": ..., "P2O5": ..., "K2O": ...}
    source: str  # full citation
    region: str
    reviewed_by: str
    reviewed_on: date


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    nutrient_fraction: dict[str, Decimal]  # mass fraction, e.g. {"N": Decimal("0.46")}
    source: str


REVIEWED_TABLES: dict[str, ReviewedTable] = {}
PRODUCTS: dict[str, Product] = {}


@dataclass(frozen=True)
class Dose:
    nutrient: str
    nutrient_kg_per_ha: Decimal
    product: str
    product_kg_per_ha: Decimal
    product_kg_per_acre: Decimal
    product_kg_for_field: Decimal | None


def _kg(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def doses(table: ReviewedTable, plan: dict[str, Product], area_ha: Decimal | None) -> list[Dose]:
    """Product amount supplying each planned nutrient: need / fraction. A nutrient whose
    product does not contain it is an error (never silently 0)."""
    out = []
    for nutrient, product in plan.items():
        need = table.nutrient_kg_per_ha[nutrient]
        frac = product.nutrient_fraction.get(nutrient)
        if not frac:
            raise ValueError(f"{product.name} does not supply {nutrient}")
        per_ha = need / frac
        out.append(
            Dose(
                nutrient=nutrient,
                nutrient_kg_per_ha=need,
                product=product.name,
                product_kg_per_ha=_kg(per_ha),
                product_kg_per_acre=_kg(per_ha * HA_PER_ACRE),
                product_kg_for_field=_kg(per_ha * area_ha) if area_ha else None,
            )
        )
    return out

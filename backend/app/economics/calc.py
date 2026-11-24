"""Crop-cycle profitability from the farmer's own records (pure, Decimal, no I/O).

Definitions (stated in the API response so the farmer can reconcile by hand):
  total_cost       = sum of expenses (PKR)
  revenue          = sum over SOLD lots of quantity_kg x price_pkr_per_kg (PKR)
  profit           = revenue - total_cost (PKR; negative = loss)
  cost_per_ha/acre = total_cost / field area (acre = 0.40468564224 ha, exact)
  break_even_price = total_cost / harvested_kg (PKR/kg): price needed for ALL harvested kg
  break_even_yield = total_cost / average sold price (kg): yield needed at that price
Anything that would divide by zero or by an unknown is None, never 0.
Money is rounded half-up to 2 decimals only at the end.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

HA_PER_ACRE = Decimal("0.40468564224")
CENT = Decimal("0.01")


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Lot:
    quantity_kg: Decimal
    price_pkr_per_kg: Decimal | None


@dataclass(frozen=True)
class Summary:
    total_cost_pkr: Decimal
    cost_by_category_pkr: dict[str, Decimal]
    harvested_kg: Decimal
    sold_kg: Decimal
    unsold_kg: Decimal
    revenue_pkr: Decimal
    profit_pkr: Decimal
    average_price_pkr_per_kg: Decimal | None
    cost_per_ha_pkr: Decimal | None
    cost_per_acre_pkr: Decimal | None
    break_even_price_pkr_per_kg: Decimal | None
    break_even_yield_kg: Decimal | None


def summarise(
    expenses: Iterable[tuple[str, Decimal]], lots: Iterable[Lot], area_ha: Decimal | None
) -> Summary:
    by_cat: dict[str, Decimal] = {}
    for category, amount in expenses:
        by_cat[category] = by_cat.get(category, Decimal(0)) + amount
    cost = sum(by_cat.values(), Decimal(0))
    lots = list(lots)
    harvested = sum((x.quantity_kg for x in lots), Decimal(0))
    sold = [x for x in lots if x.price_pkr_per_kg is not None]
    sold_kg = sum((x.quantity_kg for x in sold), Decimal(0))
    revenue = sum((x.quantity_kg * x.price_pkr_per_kg for x in sold), Decimal(0))  # type: ignore[operator]
    avg_price = revenue / sold_kg if sold_kg > 0 else None
    return Summary(
        total_cost_pkr=money(cost),
        cost_by_category_pkr={k: money(v) for k, v in sorted(by_cat.items())},
        harvested_kg=harvested,
        sold_kg=sold_kg,
        unsold_kg=harvested - sold_kg,
        revenue_pkr=money(revenue),
        profit_pkr=money(revenue - cost),
        average_price_pkr_per_kg=money(avg_price) if avg_price is not None else None,
        cost_per_ha_pkr=money(cost / area_ha) if area_ha else None,
        cost_per_acre_pkr=money(cost / area_ha * HA_PER_ACRE) if area_ha else None,
        break_even_price_pkr_per_kg=money(cost / harvested) if harvested > 0 else None,
        break_even_yield_kg=(cost / avg_price).quantize(CENT, rounding=ROUND_HALF_UP)
        if avg_price
        else None,
    )

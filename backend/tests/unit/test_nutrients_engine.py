"""FR6 arithmetic hand cases. The table and products below are SYNTHETIC test fixtures,
not agronomic advice; production registries stay empty until a reviewed source exists."""

from datetime import date
from decimal import Decimal as D

import pytest

from app.nutrients.engine import PRODUCTS, REVIEWED_TABLES, Product, ReviewedTable, doses

SYNTHETIC = ReviewedTable(
    crop_code="test_crop", nutrient_kg_per_ha={"N": D("120"), "P2O5": D("60")},
    source="SYNTHETIC TEST TABLE - not a real recommendation", region="test",
    reviewed_by="test", reviewed_on=date(2026, 1, 1),
)  # fmt: skip
N_PRODUCT = Product("n46", "Test N product 46%", {"N": D("0.46")}, "SYNTHETIC")
P_PRODUCT = Product("p46", "Test P product 46%", {"P2O5": D("0.46"), "N": D("0.18")}, "SYNTHETIC")


def test_hand_cases_need_divided_by_fraction() -> None:
    n, p = doses(SYNTHETIC, {"N": N_PRODUCT, "P2O5": P_PRODUCT}, area_ha=D("2"))
    assert n.product_kg_per_ha == D("260.9")  # 120 / 0.46 = 260.869...
    assert n.product_kg_per_acre == D("105.6")  # 260.869... x 0.40468564224 = 105.570...
    assert n.product_kg_for_field == D("521.7")  # x 2 ha = 521.739...
    assert p.product_kg_per_ha == D("130.4")  # 60 / 0.46 = 130.434...


def test_product_without_the_nutrient_is_an_error_not_zero() -> None:
    with pytest.raises(ValueError, match="does not supply P2O5"):
        doses(SYNTHETIC, {"P2O5": N_PRODUCT}, area_ha=None)


def test_unknown_area_gives_no_field_total() -> None:
    (n,) = doses(SYNTHETIC, {"N": N_PRODUCT}, area_ha=None)
    assert n.product_kg_for_field is None


def test_production_registries_hold_only_cited_reviewed_entries() -> None:
    for t in REVIEWED_TABLES.values():
        assert t.source and t.reviewed_by and t.reviewed_on and "SYNTHETIC" not in t.source
    for p in PRODUCTS.values():
        assert p.source and "SYNTHETIC" not in p.source

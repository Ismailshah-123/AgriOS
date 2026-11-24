"""FR10 acceptance 'reconciles with spreadsheet': a hand-worked case, step by step."""

from decimal import Decimal as D

from app.economics.calc import HA_PER_ACRE, Lot, summarise


def test_hand_worked_cycle_reconciles() -> None:
    expenses = [
        ("seed", D("12500.00")),
        ("fertilizer", D("18750.50")),
        ("labour", D("9000.00")),
        ("fertilizer", D("1249.50")),
    ]
    lots = [Lot(D("2000"), D("30.00")), Lot(D("500"), D("25.50")), Lot(D("300"), None)]
    s = summarise(expenses, lots, area_ha=D("2"))
    # cost 12500 + 18750.50 + 9000 + 1249.50 = 41500.00
    assert s.total_cost_pkr == D("41500.00")
    assert s.cost_by_category_pkr == {
        "fertilizer": D("20000.00"),
        "labour": D("9000.00"),
        "seed": D("12500.00"),
    }
    # revenue 2000 x 30 + 500 x 25.50 = 60000 + 12750 = 72750; 300 kg unsold
    assert (s.harvested_kg, s.sold_kg, s.unsold_kg) == (D("2800"), D("2500"), D("300"))
    assert s.revenue_pkr == D("72750.00") and s.profit_pkr == D("31250.00")
    assert s.average_price_pkr_per_kg == D("29.10")  # 72750 / 2500
    assert s.cost_per_ha_pkr == D("20750.00")  # 41500 / 2 ha
    assert s.cost_per_acre_pkr == D("8397.23")  # 20750 x 0.40468564224 = 8397.2270...
    assert s.break_even_price_pkr_per_kg == D("14.82")  # 41500 / 2800 = 14.8214...
    assert s.break_even_yield_kg == D("1426.12")  # 41500 / 29.10 = 1426.1168...


def test_loss_and_unknowns_stay_none_never_zero() -> None:
    s = summarise([("labour", D("10000"))], [], area_ha=None)
    assert s.revenue_pkr == D("0.00") and s.profit_pkr == D("-10000.00")
    assert s.average_price_pkr_per_kg is None and s.break_even_yield_kg is None
    assert s.break_even_price_pkr_per_kg is None and s.cost_per_ha_pkr is None


def test_unsold_harvest_gives_break_even_price_but_no_yield() -> None:
    s = summarise([("seed", D("900"))], [Lot(D("100"), None)], area_ha=D("0.5"))
    assert s.break_even_price_pkr_per_kg == D("9.00") and s.break_even_yield_kg is None
    assert s.revenue_pkr == D("0.00") and s.unsold_kg == D("100")


def test_acre_factor_is_the_exact_international_acre() -> None:
    assert D("4046.8564224") / D("10000") == HA_PER_ACRE

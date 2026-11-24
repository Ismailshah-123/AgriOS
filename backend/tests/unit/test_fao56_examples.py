"""FAO-56 worked examples as regression tests for app.irrigation.kc.

Reference: Allen et al. (1998) FAO Irrigation and Drainage Paper 56, chapter 6,
https://www.fao.org/4/x0490e/x0490e0b.htm (read 2026-11-24). Values below are transcribed
from the printed examples and tables, not re-derived. FAO prints results to 2 decimals
(ETc in Example 26 to 1 decimal), so tolerances equal half the printed precision.

Day convention: FAO Eq. 66 uses i = day number within the growing season [1 .. length],
so the sowing/planting day is i = 1. kc_for_day takes days after planting d (planting
day d = 0), hence i = d + 1.
"""

from datetime import date, timedelta

import pytest

from app.irrigation import kc

# Example 28 "Numerical determination of Kc" (dry bean, Box 15 / Fig. 36):
# stages 25 / 25 / 30 / 20 days; Kc ini 0.15, Kc mid 1.19, Kc end 0.35.
DRY_BEAN = kc.CropKc(
    kc_ini=(0.15, 0.15), kc_mid=(1.19, 1.19), kc_end=(0.35, 0.35),
    stages=(25, 25, 30, 20), stage_source="FAO-56 Example 28",
)  # fmt: skip


@pytest.mark.parametrize(
    ("fao_day_i", "stage", "printed_kc"),
    [(20, "initial", 0.15), (40, "development", 0.77), (70, "mid_season", 1.19),
     (95, "late_season", 0.56)],
)  # fmt: skip
def test_example_28_eq66_daily_kc(fao_day_i: int, stage: str, printed_kc: float) -> None:
    got = kc.kc_for_day(DRY_BEAN, fao_day_i - 1)
    assert got is not None
    assert got[0] == stage
    assert got[1] == pytest.approx(printed_kc, abs=0.005)
    assert got[2] == pytest.approx(printed_kc, abs=0.005)


def test_eq66_reaches_kc_end_on_the_last_season_day() -> None:
    # i = Lini + Ldev + Lmid + Llate = 100: (100 - 80) / 20 = 1 -> Kc end (0.35)
    assert kc.kc_for_day(DRY_BEAN, 99) == ("late_season", 0.35, 0.35)
    assert kc.kc_for_day(DRY_BEAN, 100) is None  # beyond the season: nothing estimated


@pytest.mark.parametrize(
    ("example", "kc_value", "et0", "printed_etc", "tol"),
    [("Example 24", 0.85, 4.0, 3.4, 0.05),   # ETc = 0.85 (4.0) = 3.4 mm/day
     ("Example 25", 0.60, 5.0, 3.0, 0.05),   # ETc = 0.60 (5) = 3.0 mm/day
     ("Example 26", 0.42, 4.0, 1.7, 0.05)],  # ETc = 0.42 (4) = 1.7 mm/day (printed 1 dp)
)  # fmt: skip
def test_eq58_etc_equals_kc_times_et0(
    example: str, kc_value: float, et0: float, printed_etc: float, tol: float
) -> None:
    crop = kc.CropKc(
        kc_ini=(kc_value, kc_value), kc_mid=(1.0, 1.0), kc_end=(1.0, 1.0),
        stages=(10, 10, 10, 10), stage_source=example,
    )  # fmt: skip
    planting = date(2026, 1, 1)
    row = kc.etc_series(crop, planting, [{"date": "2026-01-03", "et0_fao_mm": et0}])[0]
    assert row["stage"] == "initial"
    assert row["etc_low_mm"] == pytest.approx(printed_etc, abs=tol)
    assert row["etc_high_mm"] == pytest.approx(printed_etc, abs=tol)
    assert row["et0_mm"] == et0  # mm/day in, mm/day out: no unit conversion applied


def test_tomato_and_cotton_tables_match_fao56_tables_11_and_12() -> None:
    # Table 11 rows: tomato "30, 40, 40, 25, 135, January, Arid Region";
    # cotton "30, 50, 60, 55, 195, Mar-May, Egypt; Pakistan; Calif."
    # Table 12: tomato Kc mid 1.15, Kc end 0.70-0.90; cotton Kc mid 1.15-1.20, Kc end 0.70-0.50.
    # Per-crop Kc ini is an image in the online text; 0.60 / 0.35 are the Table 12 group
    # values (Solanum family / fibre crops) and stay flagged for expert review.
    t, c = kc.CROPS["tomato"], kc.CROPS["cotton"]
    assert t.stages == (30, 40, 40, 25) and sum(t.stages) == 135
    assert (t.kc_mid, t.kc_end) == ((1.15, 1.15), (0.70, 0.90))
    assert c.stages == (30, 50, 60, 55) and sum(c.stages) == 195
    assert (c.kc_mid, c.kc_end) == ((1.15, 1.20), (0.50, 0.70))
    assert t.review_status == c.review_status == "transcribed_from_FAO56_pending_expert_review"


def test_series_uses_calendar_days_after_planting() -> None:
    planting = date(2026, 1, 1)
    day40 = (planting + timedelta(days=39)).isoformat()  # FAO day i = 40
    row = kc.etc_series(DRY_BEAN, planting, [{"date": day40, "et0_fao_mm": 5.0}])[0]
    assert row["kc_low"] == pytest.approx(0.77, abs=0.005)

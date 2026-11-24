"""FR7 boundary tests: pH reaction classes, ECe salinity classes, crop salt tolerance."""

from decimal import Decimal

import pytest

from app.soil.interpret import interpret
from app.soil.models import EcMethod, PhMethod, PMethod, SoilObservation


def obs(**kw: object) -> SoilObservation:
    base = {
        "ph": None,
        "ph_method": PhMethod.WATER_1_1,
        "ec_ds_m": None,
        "ec_method": EcMethod.SATURATED_PASTE_ECE,
        "organic_matter_pct": None,
        "organic_carbon_pct": None,
        "nitrogen_total_pct": None,
        "phosphorus_mg_kg": None,
        "phosphorus_method": PMethod.UNKNOWN,
        "potassium_mg_kg": None,
        "texture": None,
        "data_origin": "measured",
    }
    base.update(kw)
    return SoilObservation(**base)


def ph_class(v: str) -> str:
    flags = interpret(obs(ph=Decimal(v)))["flags"]
    return next(f["class"] for f in flags if f["measure"] == "ph")


@pytest.mark.parametrize(
    ("ph", "cls"),
    [
        ("3.4", "ultra_acid"),
        ("3.5", "extremely_acid"),
        ("5.0", "very_strongly_acid"),
        ("5.1", "strongly_acid"),
        ("6.5", "slightly_acid"),
        ("6.6", "neutral"),
        ("7.3", "neutral"),
        ("7.4", "slightly_alkaline"),
        ("8.4", "moderately_alkaline"),
        ("8.5", "strongly_alkaline"),
        ("9.0", "strongly_alkaline"),
        ("9.1", "very_strongly_alkaline"),
    ],
)
def test_ph_reaction_class_boundaries(ph: str, cls: str) -> None:
    assert ph_class(ph) == cls


def test_sodicity_hint_from_ph_85_with_source() -> None:
    flags = interpret(obs(ph=Decimal("8.5")))["flags"]
    s = next(f for f in flags if f["class"] == "possible_sodicity")
    assert "Handbook 60" in s["source"]
    assert not any(
        f["class"] == "possible_sodicity" for f in interpret(obs(ph=Decimal("8.4")))["flags"]
    )


@pytest.mark.parametrize(
    ("ec", "cls"),
    [
        ("1.99", "nonsaline"),
        ("2", "very_slightly_saline"),
        ("4", "slightly_saline"),
        ("8", "moderately_saline"),
        ("16", "strongly_saline"),
    ],
)
def test_ece_salinity_boundaries(ec: str, cls: str) -> None:
    f = interpret(obs(ec_ds_m=Decimal(ec)))["flags"]
    assert next(x["class"] for x in f if x["measure"] == "ec_ds_m") == cls


def test_tomato_salt_tolerance_threshold_and_yield_estimate() -> None:
    at = interpret(obs(ec_ds_m=Decimal("2.5")), ["tomato"])["flags"]
    assert not any(f["class"] == "above_crop_threshold" for f in at)
    above = interpret(obs(ec_ds_m=Decimal("4.5")), ["tomato"])["flags"]
    f = next(f for f in above if f["class"] == "above_crop_threshold")
    assert f["expected_relative_yield_pct"] == pytest.approx(100 - 9.9 * 2.0)
    assert "Maas" in f["source"]


def test_method_mismatch_is_not_evaluated_not_guessed() -> None:
    r = interpret(
        obs(
            ph=Decimal("6.0"),
            ph_method=PhMethod.CACL2,
            ec_ds_m=Decimal("3"),
            ec_method=EcMethod.EXTRACT_1_1,
        )
    )
    assert r["flags"] == []
    assert {n["measure"] for n in r["not_evaluated"]} == {"ph", "ec_ds_m"}


def test_fertility_values_never_rated_and_no_doses() -> None:
    r = interpret(
        obs(
            phosphorus_mg_kg=Decimal("5"),
            potassium_mg_kg=Decimal("90"),
            organic_matter_pct=Decimal("0.7"),
        )
    )
    assert r["flags"] == []
    assert {n["measure"] for n in r["not_evaluated"]} == {
        "phosphorus_mg_kg",
        "potassium_mg_kg",
        "organic_matter_pct",
    }
    assert "No fertilizer" in r["dose_policy"]


def test_missing_and_origin_warnings() -> None:
    r = interpret(obs(ph=Decimal("7"), ph_method=PhMethod.UNKNOWN, data_origin="farmer_entered"))
    codes = {w["code"] for w in r["warnings"]}
    assert codes == {"missing_measures", "unknown_method", "not_lab_measured"}

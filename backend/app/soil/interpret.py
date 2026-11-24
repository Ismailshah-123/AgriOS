"""Soil interpretation using only cited, method-appropriate thresholds (FR7).

Rules (MODULE_CONTRACTS s3): a flag always carries its source; when no reviewed
threshold exists for a measure (or the lab method does not match the threshold's
method) the measure is listed under `not_evaluated` with the reason, never guessed.
No fertilizer or amendment quantities are produced here (CLAUDE.md hard rule 2).
"""

from __future__ import annotations

from typing import Any

from app.soil.models import EcMethod, PhMethod, SoilObservation

SSM = (
    "Soil Science Division Staff (2017). Soil Survey Manual. USDA Handbook 18, "
    "chapter 3 (reaction and salinity classes)."
)
MAAS_HOFFMAN = (
    "Maas, E.V. & Hoffman, G.J. (1977). Crop salt tolerance - current "
    "assessment. J. Irrig. Drain. Div. ASCE 103:115-134; as tabulated in "
    "FAO Irrigation and Drainage Paper 29 (Ayers & Westcot, 1985)."
)

HB60 = (
    "U.S. Salinity Laboratory Staff (1954). Diagnosis and Improvement of Saline and "
    "Alkali Soils. USDA Agriculture Handbook 60."
)
# (upper bound exclusive, class) — Soil Survey Manual reaction classes (pH, 1:1 water).
PH_CLASSES = [
    (3.5, "ultra_acid"),
    (4.5, "extremely_acid"),
    (5.1, "very_strongly_acid"),
    (5.6, "strongly_acid"),
    (6.1, "moderately_acid"),
    (6.6, "slightly_acid"),
    (7.4, "neutral"),
    (7.9, "slightly_alkaline"),
    (8.5, "moderately_alkaline"),
    (9.1, "strongly_alkaline"),
    (99, "very_strongly_alkaline"),
]
# Soil Survey Manual salinity classes, ECe (saturated paste extract), dS/m.
EC_CLASSES = [
    (2, "nonsaline"),
    (4, "very_slightly_saline"),
    (8, "slightly_saline"),
    (16, "moderately_saline"),
    (1e9, "strongly_saline"),
]
# Maas-Hoffman threshold (dS/m ECe) and yield decline slope (% per dS/m) per crop code.
SALT_TOLERANCE = {"tomato": (2.5, 9.9)}
WATER_PH = {PhMethod.WATER_1_1, PhMethod.WATER_1_2_5}
KEY_MEASURES = [
    "ph",
    "ec_ds_m",
    "organic_matter_pct",
    "phosphorus_mg_kg",
    "potassium_mg_kg",
    "texture",
]


def _classify(v: float, table: list[tuple[float, str]]) -> str:
    return next(c for upper, c in table if v < upper)


def interpret(obs: SoilObservation, crop_codes: list[str] | None = None) -> dict[str, Any]:
    flags: list[dict[str, Any]] = []
    not_eval: list[dict[str, str]] = []
    if obs.ph is not None:
        ph = float(obs.ph)
        if obs.ph_method in WATER_PH:
            cls = _classify(ph, PH_CLASSES)
            level = "info" if 5.6 <= ph < 7.9 else "watch" if 5.1 <= ph < 8.5 else "warning"
            flags.append(
                {
                    "measure": "ph",
                    "value": ph,
                    "unit": "pH",
                    "class": cls,
                    "level": level,
                    "source": SSM,
                    "message": f"Soil reaction: {cls.replace('_', ' ')} (pH {ph}).",
                }
            )
            if ph >= 8.5:
                flags.append(
                    {
                        "measure": "ph",
                        "value": ph,
                        "unit": "pH",
                        "level": "warning",
                        "class": "possible_sodicity",
                        "source": HB60,
                        "message": "pH >= 8.5 often accompanies sodic conditions. Ask "
                        "the lab for ESP/SAR before deciding on any amendment.",
                    }
                )
        else:
            not_eval.append(
                {
                    "measure": "ph",
                    "reason": f"Reaction classes are defined for "
                    f"water pH; method is '{obs.ph_method}'.",
                }
            )
    if obs.ec_ds_m is not None:
        ec = float(obs.ec_ds_m)
        if obs.ec_method == EcMethod.SATURATED_PASTE_ECE:
            cls = _classify(ec, EC_CLASSES)
            flags.append(
                {
                    "measure": "ec_ds_m",
                    "value": ec,
                    "unit": "dS/m",
                    "class": cls,
                    "level": "info" if ec < 4 else "warning",
                    "source": SSM,
                    "message": f"Salinity class: {cls.replace('_', ' ')} (ECe {ec} dS/m).",
                }
            )
            for crop in crop_codes or []:
                if crop in SALT_TOLERANCE:
                    t, slope = SALT_TOLERANCE[crop]
                    if ec > t:
                        ry = max(0.0, round(100 - slope * (ec - t), 1))
                        flags.append(
                            {
                                "measure": "ec_ds_m",
                                "value": ec,
                                "unit": "dS/m",
                                "class": "above_crop_threshold",
                                "level": "warning",
                                "source": MAAS_HOFFMAN,
                                "crop": crop,
                                "expected_relative_yield_pct": ry,
                                "message": f"ECe {ec} dS/m exceeds the {crop} threshold of {t} "
                                f"dS/m; published response predicts ~{ry}% relative "
                                f"yield (estimate, not a field measurement).",
                            }
                        )
        else:
            not_eval.append(
                {
                    "measure": "ec_ds_m",
                    "reason": "Salinity classes need ECe "
                    "(saturated paste); conversion from other ratios depends on "
                    "soil texture and is not applied.",
                }
            )
    for m in (
        "organic_matter_pct",
        "organic_carbon_pct",
        "nitrogen_total_pct",
        "phosphorus_mg_kg",
        "potassium_mg_kg",
        "calcium_mg_kg",
        "magnesium_mg_kg",
        "sulfur_mg_kg",
        "zinc_mg_kg",
        "iron_mg_kg",
        "boron_mg_kg",
        "cec_cmol_kg",
    ):
        if getattr(obs, m) is not None:
            not_eval.append(
                {
                    "measure": m,
                    "reason": "No reviewed fertility classification "
                    "for this lab method and region is stored yet.",
                }
            )
    missing = [m for m in KEY_MEASURES if getattr(obs, m) is None]
    warnings = []
    if missing:
        warnings.append(
            {
                "code": "missing_measures",
                "measures": missing,
                "message": "Some key measures were not reported: " + ", ".join(missing) + ".",
            }
        )
    if obs.ph_method == PhMethod.UNKNOWN and obs.ph is not None:
        warnings.append(
            {
                "code": "unknown_method",
                "measures": ["ph"],
                "message": "pH method unknown; ask the lab (1:1 or 1:2.5 water?).",
            }
        )
    if obs.data_origin != "measured":
        warnings.append(
            {
                "code": "not_lab_measured",
                "measures": [],
                "message": "Values were entered manually or from a field kit, not a "
                "laboratory report; treat interpretation with caution.",
            }
        )
    return {
        "flags": flags,
        "not_evaluated": not_eval,
        "warnings": warnings,
        "dose_policy": "No fertilizer or amendment quantities are given without a "
        "reviewed, cited reference table.",
    }

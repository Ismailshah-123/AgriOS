"""The asking user's OWN farm records, for questions like "summarise my soil tests".

Every query filters by Farm.owner_id == user_id (tenant isolation); nothing here can read
another user's data. Values keep their units and data origin. Missing data is listed as
missing — never filled in. This is recorded farm data, not retrieved knowledge, and the
answer shows it separately (cited as [F]).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crop_health.models import CropHealthAnalysis, CropHealthCase
from app.economics.models import Expense, HarvestSale
from app.farms.models import CropCycle, CropDefinition, Farm
from app.farms.models import Field as FieldModel
from app.soil.models import SoilObservation

SOIL_FIELDS = (
    ("ph", "pH", ""),
    ("ec_ds_m", "EC", "dS/m"),
    ("organic_matter_pct", "organic matter", "%"),
    ("nitrogen_total_pct", "total N", "%"),
    ("phosphorus_mg_kg", "P", "mg/kg"),
    ("potassium_mg_kg", "K", "mg/kg"),
    ("zinc_mg_kg", "Zn", "mg/kg"),
)


def _num(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def collect(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    fields = db.execute(
        select(FieldModel, Farm)
        .join(Farm, Farm.id == FieldModel.farm_id)
        .where(Farm.owner_id == user_id)
        .order_by(Farm.name, FieldModel.name)
    ).all()
    field_ids = [f.id for f, _ in fields]
    missing: list[str] = []
    out: dict[str, Any] = {"farms": sorted({farm.name for _, farm in fields}), "fields": []}
    if not fields:
        n_farms = db.scalar(select(func.count(Farm.id)).where(Farm.owner_id == user_id)) or 0
        out["farms_without_fields"] = n_farms
        return {**out, "missing": ["fields"], "empty": True}
    cycles = db.execute(
        select(CropCycle, CropDefinition.name_en)
        .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
        .where(CropCycle.field_id.in_(field_ids))
        .order_by(CropCycle.sowing_date.desc().nulls_last())
    ).all()
    soils = db.scalars(
        select(SoilObservation)
        .where(SoilObservation.field_id.in_(field_ids))
        .order_by(SoilObservation.sampled_on.desc())
    ).all()
    for fld, farm in fields:
        cyc = [
            {
                "crop": name,
                "status": c.status.value,
                "variety": c.variety,
                "sowing_date": c.sowing_date.isoformat() if c.sowing_date else None,
                "days_after_sowing": (date.today() - c.sowing_date).days if c.sowing_date else None,
                "id": c.id,
            }
            for c, name in cycles
            if c.field_id == fld.id
        ]
        soil = next((s for s in soils if s.field_id == fld.id), None)
        soil_out = None
        if soil is None:
            missing.append(f"soil test for field '{fld.name}'")
        else:
            vals = {lbl: (_num(getattr(soil, a)), u) for a, lbl, u in SOIL_FIELDS}
            soil_out = {
                "sampled_on": soil.sampled_on.isoformat(),
                "origin": soil.data_origin.value,
                "values": {k: f"{v} {u}".strip() for k, (v, u) in vals.items() if v is not None},
                "not_measured": [k for k, (v, _) in vals.items() if v is None],
                "texture": soil.texture.value if soil.texture else None,
            }
        if not cyc:
            missing.append(f"crop cycle for field '{fld.name}'")
        out["fields"].append(
            {
                "farm": farm.name,
                "field": fld.name,
                "area_ha": float(fld.area_ha),
                "district": farm.district,
                "cycles": [{k: v for k, v in c.items() if k != "id"} for c in cyc[:3]],
                "latest_soil_test": soil_out,
            }
        )
    cycle_ids = [c.id for c, _ in cycles]
    if cycle_ids:
        cost = db.scalar(
            select(func.sum(Expense.amount_pkr)).where(Expense.crop_cycle_id.in_(cycle_ids))
        )
        revenue = db.scalar(
            select(func.sum(HarvestSale.quantity_kg * HarvestSale.price_pkr_per_kg)).where(
                HarvestSale.crop_cycle_id.in_(cycle_ids)
            )
        )
        out["economics"] = {
            "recorded_expenses_pkr": _num(cost),
            "recorded_revenue_pkr": _num(revenue),
            "origin": "farmer_entered",
        }
    cases = db.execute(
        select(CropHealthCase.status, func.count())
        .where(CropHealthCase.owner_id == user_id)
        .group_by(CropHealthCase.status)
    ).all()
    out["crop_doctor_cases"] = {s.value: n for s, n in cases}
    latest = db.execute(
        select(CropHealthAnalysis.predicted_class, CropHealthAnalysis.decision)
        .join(CropHealthCase, CropHealthCase.id == CropHealthAnalysis.case_id)
        .where(CropHealthCase.owner_id == user_id)
        .order_by(CropHealthAnalysis.created_at.desc())
        .limit(3)
    ).all()
    out["recent_crop_doctor_results"] = [
        {"predicted_class": p, "decision": d.value, "origin": "inferred"} for p, d in latest
    ]
    out["missing"] = missing
    out["empty"] = False
    return out


def as_prompt_block(ctx: dict[str, Any]) -> str:
    """Compact, labelled text for the LLM. Only the user's own records."""
    if ctx.get("empty"):
        return "The user has no fields recorded in AgriOS yet."
    lines = []
    for f in ctx["fields"]:
        lines.append(
            f"- Field '{f['field']}' on farm '{f['farm']}', {f['area_ha']} ha"
            + (f", district {f['district']}" if f["district"] else "")
        )
        for c in f["cycles"]:
            lines.append(
                f"  crop cycle: {c['crop']} ({c['status']}), sown {c['sowing_date']}, "
                f"{c['days_after_sowing']} days after sowing [farmer_entered]"
            )
        s = f["latest_soil_test"]
        if s:
            vals = ", ".join(f"{k} {v}" for k, v in s["values"].items()) or "no values"
            lines.append(
                f"  latest soil test {s['sampled_on']} [{s['origin']}]: {vals}; "
                f"not measured: {', '.join(s['not_measured']) or 'none'}"
            )
    if ctx.get("economics"):
        e = ctx["economics"]
        lines.append(
            f"- Recorded expenses PKR {e['recorded_expenses_pkr']}, recorded revenue "
            f"PKR {e['recorded_revenue_pkr']} [farmer_entered]"
        )
    if ctx.get("crop_doctor_cases"):
        lines.append(f"- Crop Doctor cases by status: {ctx['crop_doctor_cases']}")
    for r in ctx.get("recent_crop_doctor_results", []):
        lines.append(
            f"- Crop Doctor result: {r['predicted_class'] or 'no accepted diagnosis'} "
            f"(decision {r['decision']}) [inferred by model]"
        )
    if ctx.get("missing"):
        lines.append(f"- Missing records: {'; '.join(ctx['missing'])}")
    return "\n".join(lines)

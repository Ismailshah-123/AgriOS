"""The allow-listed tool set. Each handler calls an existing owner-scoped service."""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.agents.registry import Tool, ToolContext, ToolResult, register
from app.core.errors import AppError
from app.crop_health.models import CropHealthAnalysis, CropHealthCase
from app.farms import repository as farm_repo
from app.farms import service as farm_service
from app.farms.models import CropCycle, Farm
from app.farms.models import Field as FieldModel
from app.farms.schemas import CropCycleUpdate, FarmUpdate
from app.irrigation import kc
from app.irrigation import service as irrigation
from app.mlops import registry as model_registry
from app.soil import interpret as soil_rules
from app.soil import service as soil_service
from app.weather import indicators
from app.weather import service as weather_service


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class NoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: uuid.UUID


class KnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=200)


class FarmLocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    farm_id: uuid.UUID
    latitude: Decimal = Field(ge=-90, le=90, decimal_places=2)
    longitude: Decimal = Field(ge=-180, le=180, decimal_places=2)


class SowingDateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cycle_id: uuid.UUID
    sowing_date: date


class FarmsOut(_Out):
    farms: list[dict[str, Any]]


class FieldContextOut(_Out):
    field: dict[str, Any]
    farm: dict[str, Any]
    crop_cycle: dict[str, Any] | None


class SoilOut(_Out):
    observations: int
    latest: dict[str, Any] | None
    missing_measures: list[str]


class WeatherToolOut(_Out):
    status: str
    indicators: list[dict[str, Any]]


class WaterOut(_Out):
    status: str
    missing_information: list[str]


class CropHealthOut(_Out):
    model_status: str
    cases: list[dict[str, Any]]


class KnowledgeOut(_Out):
    matches: list[dict[str, Any]]
    documents_available: int


class WriteOut(_Out):
    changed: str


def _farms(ctx: ToolContext, _: NoInput) -> ToolResult:
    rows = ctx.db.execute(
        select(Farm, FieldModel)
        .outerjoin(FieldModel, FieldModel.farm_id == Farm.id)
        .where(Farm.owner_id == ctx.user.id)
        .order_by(Farm.name, FieldModel.name)
    ).all()
    farms: dict[uuid.UUID, dict[str, Any]] = {}
    for farm, fld in rows:
        f = farms.setdefault(
            farm.id,
            {
                "id": str(farm.id),
                "name": farm.name,
                "has_coordinates": farm.latitude is not None and farm.longitude is not None,
                "fields": [],
            },
        )
        if fld is not None:
            f["fields"].append({"id": str(fld.id), "name": fld.name, "area_ha": float(fld.area_ha)})
    out = list(farms.values())
    n_fields = sum(len(f["fields"]) for f in out)
    return ToolResult("ok", {"farms": out}, f"{len(out)} farm(s), {n_fields} field(s).")


def _field_context(ctx: ToolContext, a: FieldInput) -> ToolResult:
    row = farm_repo.get_field_row(ctx.db, ctx.user.id, a.field_id)
    if row is None:
        raise AppError("not_found", "Field not found.", 404)
    fld: FieldModel = row[0]
    farm = farm_repo.get_owned_farm(ctx.db, ctx.user.id, fld.farm_id)
    assert farm is not None  # noqa: S101 - field ownership implies farm ownership
    cyc = irrigation.active_cycle(ctx.db, fld.id)
    cycle = None
    missing: list[str] = []
    if cyc is None:
        missing.append("active_crop_cycle")
    else:
        c, code = cyc
        dap = (date.today() - c.sowing_date).days if c.sowing_date else None
        crop_kc = kc.CROPS.get(code)
        stage = kc.kc_for_day(crop_kc, dap) if crop_kc and dap is not None else None
        cycle = {
            "id": str(c.id),
            "crop": code,
            "variety": c.variety,
            "status": c.status,
            "sowing_date": c.sowing_date.isoformat() if c.sowing_date else None,
            "days_after_planting": dap,
            "fao56_stage": stage[0] if stage else None,
            "data_origin": "farmer_entered",
        }
        if c.sowing_date is None:
            missing.append("crop_cycle.sowing_date")
    has_xy = farm.latitude is not None and farm.longitude is not None
    if not has_xy:
        missing.append("farm.coordinates")
    data = {
        "field": {"id": str(fld.id), "name": fld.name, "area_ha": float(fld.area_ha)},
        "farm": {
            "id": str(farm.id),
            "name": farm.name,
            "district": farm.district,
            "province": farm.province,
            "latitude": float(farm.latitude) if farm.latitude is not None else None,
            "longitude": float(farm.longitude) if farm.longitude is not None else None,
        },
        "crop_cycle": cycle,
    }
    crop = f"{cycle['crop']} ({cycle['fao56_stage'] or 'stage unknown'})" if cycle else "no crop"
    return ToolResult("ok", data, f"Field '{fld.name}' on '{farm.name}': {crop}.", missing=missing)


def _soil(ctx: ToolContext, a: FieldInput) -> ToolResult:
    s = soil_service.summary(ctx.db, ctx.user, a.field_id)
    latest = s.latest.model_dump(mode="json") if s.latest else None
    missing = (
        [m for m in soil_rules.KEY_MEASURES if latest.get(m) is None] if latest else ["soil_test"]
    )
    data = {"observations": s.observations, "latest": latest, "missing_measures": missing}
    if latest is None:
        return ToolResult("unavailable", data, "No soil test recorded for this field.", [], missing)
    ev = [
        {
            "type": "soil_observation",
            "id": latest["id"],
            "sampled_on": latest["sampled_on"],
            "data_origin": latest["data_origin"],
        }
    ]
    flags = latest["interpretation"]["flags"]
    return ToolResult(
        "ok",
        data,
        f"Latest soil test {latest['sampled_on']} ({latest['data_origin']}): "
        f"{len(flags)} interpreted flag(s), {len(missing)} key measure(s) missing.",
        ev,
        [f"soil.{m}" for m in missing],
    )


def _weather(ctx: ToolContext, a: FieldInput) -> ToolResult:
    w = weather_service.get_weather(ctx.db, ctx.user, ctx.weather, field_id=a.field_id)
    data = w.model_dump(mode="json")
    if w.status == "unavailable":
        return ToolResult(
            "unavailable",
            data,
            f"Weather unavailable ({w.reason}).",
            missing=[f"weather:{w.reason}"],
        )
    ev = [
        {
            "type": "weather_snapshot",
            "provider": (w.provider or {}).get("name"),
            "retrieved_at": data["retrieved_at"],
            "status": w.status,
        }
    ]
    return ToolResult(
        "ok",
        data,
        f"Weather {w.status} (retrieved {w.age_minutes} min ago); "
        f"{len(w.indicators)} indicator(s).",
        ev,
    )


def _water(ctx: ToolContext, a: FieldInput) -> ToolResult:
    d = irrigation.water_demand(ctx.db, ctx.user, a.field_id, ctx.weather)
    if d["status"] != "ok":
        return ToolResult(
            "unavailable",
            d,
            "Crop water demand cannot be estimated yet.",
            missing=d["missing_information"],
        )
    t = d["totals"]
    return ToolResult(
        "ok",
        d,
        f"Estimated ETc {t['etc_low_mm']}-{t['etc_high_mm']} mm over {t['days']} days "
        f"(ET0 {t['et0_mm']} mm, gross rain {t['gross_rain_mm']} mm).",
        [{"type": "method", "source": d["source"]}],
    )


def _crop_health(ctx: ToolContext, a: FieldInput) -> ToolResult:
    if farm_repo.get_field_row(ctx.db, ctx.user.id, a.field_id) is None:
        raise AppError("not_found", "Field not found.", 404)
    avail = model_registry.availability(ctx.db, ctx.settings.model_path)
    cases = ctx.db.scalars(
        select(CropHealthCase)
        .join(CropCycle, CropCycle.id == CropHealthCase.crop_cycle_id)
        .where(CropCycle.field_id == a.field_id)
        .order_by(CropHealthCase.created_at.desc())
        .limit(5)
    ).all()
    items = []
    for c in cases:
        an = ctx.db.scalar(
            select(CropHealthAnalysis)
            .where(CropHealthAnalysis.case_id == c.id)
            .order_by(CropHealthAnalysis.created_at.desc())
            .limit(1)
        )
        items.append(
            {
                "case_id": str(c.id),
                "status": c.status,
                "inference_status": c.inference_status,
                "created_at": c.created_at.isoformat(),
                "decision": an.decision if an else None,
                "predicted_class": an.predicted_class if an else None,
                "calibrated_confidence": float(an.calibrated_conf) if an else None,
                "data_origin": "inferred" if an else None,
            }
        )
    data = {"model_status": avail.status, "model_reason": avail.reason, "cases": items}
    missing = [] if items else ["crop_doctor_case"]
    if avail.status != "ready":
        missing.append(f"crop_doctor_model:{avail.status}")
    ev = [{"type": "crop_health_case", "id": i["case_id"]} for i in items]
    return ToolResult(
        "ok" if items else "unavailable",
        data,
        f"{len(items)} Crop Doctor case(s); model {avail.status}.",
        ev,
        missing,
    )


def _sources() -> list[dict[str, str]]:
    out = [
        {
            "id": k,
            "module": "weather_risk",
            **{x: v[x] for x in ("basis", "source", "review_status")},
        }
        for k, v in indicators.RULES.items()
    ]
    out += [
        {
            "id": "soil_reaction_salinity_classes",
            "module": "soil",
            "basis": "pH reaction and ECe salinity classes",
            "source": soil_rules.SSM,
            "review_status": "published",
        },
        {
            "id": "salt_tolerance_maas_hoffman",
            "module": "soil",
            "basis": "Crop salt tolerance threshold and yield-decline slope",
            "source": soil_rules.MAAS_HOFFMAN,
            "review_status": "published",
        },
        {
            "id": "fao56_crop_coefficients",
            "module": "irrigation",
            "basis": "ETc = Kc x ET0 with stage-based crop coefficient",
            "source": kc.FAO56,
            "review_status": "transcribed_from_FAO56_pending_expert_review",
        },
        {
            "id": "crop_doctor_decision_rule",
            "module": "crop_health",
            "basis": "Temperature-"
            "scaled confidence threshold plus energy-based out-of-scope rejection; low "
            "confidence is never a diagnosis",
            "source": "ml/reports/MODEL_CARD.md",
            "review_status": "internal_method",
        },
    ]
    return out


def _knowledge(ctx: ToolContext, a: KnowledgeInput) -> ToolResult:
    """Method references used by AgriOS + passages from the licence-verified library
    (same hybrid retrieval as /knowledge/ask; quoted, never generated)."""
    from app.knowledge import retrieval
    from app.knowledge.providers import get_embedder
    from app.knowledge.service import searchable_count

    words = {w for w in re.findall(r"[a-z0-9]+", a.query.lower()) if len(w) > 2}
    scored = []
    for s in _sources():
        hay = " ".join(s.values()).lower().replace("_", " ")
        hits = sum(1 for w in words if w in hay)
        if hits:
            scored.append((hits, s))
    matches = [s for _, s in sorted(scored, key=lambda x: -x[0])[:5]]
    passages = retrieval.hybrid(ctx.db, a.query, embedder=get_embedder(ctx.settings))[:3]
    docs = [
        {
            "id": str(p.chunk_id),
            "source": f"{p.source['title']} ({p.source['publisher']})",
            "section": p.section,
            "page": p.page,
            "licence": p.source["licence"],
            "text": p.text[:500],
            "data_origin": "retrieved",
        }
        for p in passages
    ]
    data = {
        "matches": matches,
        "passages": docs,
        "documents_available": searchable_count(ctx.db),
        "note": "Method references used by AgriOS, plus quoted passages from licence-verified "
        "sources. Full cited answers: Agricultural Knowledge page.",
    }
    found = bool(matches or docs)
    return ToolResult(
        "ok" if found else "unavailable",
        data,
        f"{len(matches)} method reference(s), {len(docs)} verified passage(s) matched.",
        [{"type": "reference", "id": m["id"], "source": m["source"]} for m in matches]
        + [{"type": "passage", "id": d["id"], "source": d["source"]} for d in docs],
        [] if found else ["knowledge_documents"],
    )


def _set_location(ctx: ToolContext, a: FarmLocationInput) -> ToolResult:
    out = farm_service.update_farm(
        ctx.db,
        ctx.user,
        a.farm_id,
        FarmUpdate(latitude=a.latitude, longitude=a.longitude),
        ctx.request_id,
    )
    return ToolResult(
        "ok",
        {
            "changed": "farm.coordinates",
            "farm_id": str(out.id),
            "latitude": str(out.latitude),
            "longitude": str(out.longitude),
        },
        f"Farm '{out.name}' coordinates set.",
    )


def _set_sowing(ctx: ToolContext, a: SowingDateInput) -> ToolResult:
    out = farm_service.update_cycle(
        ctx.db,
        ctx.user,
        a.cycle_id,
        CropCycleUpdate(sowing_date=a.sowing_date),
        ctx.request_id,
        date.today(),
    )
    return ToolResult(
        "ok",
        {
            "changed": "crop_cycle.sowing_date",
            "cycle_id": str(out.id),
            "sowing_date": a.sowing_date.isoformat(),
        },
        "Crop cycle sowing date updated.",
    )


for _t in (
    Tool(
        "list_farms_and_fields",
        "List the user's farms and fields.",
        "read",
        "owner",
        NoInput,
        FarmsOut,
        _farms,
        5.0,
        ("farm_operations",),
    ),
    Tool(
        "get_field_context",
        "Field, farm location and active crop cycle with FAO-56 stage.",
        "read",
        "owner",
        FieldInput,
        FieldContextOut,
        _field_context,
        5.0,
        ("farm_operations", "crop_health", "soil", "weather", "irrigation"),
    ),
    Tool(
        "get_soil_summary",
        "Latest soil test, cited interpretation and missing measures.",
        "read",
        "owner",
        FieldInput,
        SoilOut,
        _soil,
        5.0,
        ("soil",),
    ),
    Tool(
        "get_weather",
        "Cached/retrieved forecast and cited weather risk indicators.",
        "read",
        "owner",
        FieldInput,
        WeatherToolOut,
        _weather,
        15.0,
        ("weather",),
    ),
    Tool(
        "get_water_demand",
        "FAO-56 ETc estimate for the active crop cycle.",
        "read",
        "owner",
        FieldInput,
        WaterOut,
        _water,
        15.0,
        ("irrigation",),
    ),
    Tool(
        "get_crop_health",
        "Recent Crop Doctor cases and model availability.",
        "read",
        "owner",
        FieldInput,
        CropHealthOut,
        _crop_health,
        5.0,
        ("crop_health",),
    ),
    Tool(
        "search_method_references",
        "Search the cited methods AgriOS uses.",
        "read",
        "owner",
        KnowledgeInput,
        KnowledgeOut,
        _knowledge,
        2.0,
        ("knowledge",),
    ),
    Tool(
        "set_farm_location",
        "Set farm latitude/longitude (needed for weather).",
        "write",
        "owner",
        FarmLocationInput,
        WriteOut,
        _set_location,
        5.0,
        ("farm_operations",),
    ),
    Tool(
        "set_cycle_sowing_date",
        "Set the crop cycle sowing/planting date.",
        "write",
        "owner",
        SowingDateInput,
        WriteOut,
        _set_sowing,
        5.0,
        ("farm_operations",),
    ),
):
    register(_t)

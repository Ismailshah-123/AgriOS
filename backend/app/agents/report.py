"""Structured agent response and the cross-module field condition report.

Only what the tools returned is reported. Unavailable modules stay visible as gaps in
`coverage` and `missing_information`; nothing is filled in.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from pydantic_core import to_jsonable_python

from app.agents.agents import AGENTS, Request, Section
from app.agents.models import AgentAction

REPORT_SOURCES = ("soil", "weather", "irrigation", "crop_health")


def _unique(items: list[Any]) -> list[Any]:
    seen, out = set(), []
    for i in items:
        key = repr(i)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


def _action(a: AgentAction) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "tool": a.tool,
        "args": a.args,
        "description": a.description,
        "status": a.status,
        "expires_at": a.expires_at.isoformat(),
    }


def _field_report(req: Request, by: dict[str, Section], now: datetime) -> dict[str, Any]:
    ctx = req.context or {}
    weather = by.get("weather")
    soil = by.get("soil")
    crop = by.get("crop_health")
    water = by.get("irrigation")
    coverage = {k: (by[k].status if k in by else "not_run") for k in REPORT_SOURCES}
    available = sum(1 for v in coverage.values() if v == "ok")
    latest_soil = (soil.data.get("latest") or {}) if soil else {}
    cases = (crop.data.get("cases") or []) if crop else []
    return {
        "title": f"Field condition report — {(ctx.get('field') or {}).get('name', 'field')}",
        "generated_at": now.isoformat(),
        "field": ctx.get("field"),
        "farm": ctx.get("farm"),
        "crop": ctx.get("crop_cycle"),
        "soil": {
            "status": coverage["soil"],
            "findings": soil.findings if soil else [],
            "sampled_on": latest_soil.get("sampled_on"),
            "data_origin": latest_soil.get("data_origin"),
        },
        "weather": {
            "status": coverage["weather"],
            "findings": weather.findings[:1] if weather else [],
            "current": weather.data.get("current") if weather else None,
            "daily": weather.data.get("daily") if weather else [],
        },
        "risks": (weather.data.get("indicators") or []) if weather else [],
        "water_demand": {
            "status": coverage["irrigation"],
            "findings": water.findings if water else [],
            "totals": water.data.get("totals") if water else None,
        },
        "crop_health": {
            "status": coverage["crop_health"],
            "findings": crop.findings if crop else [],
            "model_status": crop.data.get("model_status") if crop else None,
        },
        "timestamps": {
            "report_generated_at": now.isoformat(),
            "weather_retrieved_at": weather.data.get("retrieved_at") if weather else None,
            "soil_sampled_on": latest_soil.get("sampled_on"),
            "latest_crop_case_at": cases[0]["created_at"] if cases else None,
        },
        "coverage": coverage,
        "confidence": (
            f"Based on {available} of {len(REPORT_SOURCES)} data sources. Sections marked "
            "unavailable or partial were not assessed; no values were estimated in their place."
        ),
    }


def build(
    intent: str,
    req: Request,
    sections: list[Section],
    missing: list[str],
    actions: list[AgentAction],
    now: datetime,
) -> dict[str, Any]:
    by = {s.agent: s for s in sections}
    lines: list[str] = []
    if intent == "help":
        lines.append(
            "I can report on a field's soil, weather risks, crop water demand and "
            "Crop Doctor results, or a complete field condition report. Try: "
            "'Give me a complete condition report for my tomato field'."
        )
    if any(m.startswith(("field_id", "field (")) for m in missing):
        lines.append("Select a field so the agents can read its records.")
    for s in sections:
        lines.append(f"{s.title}: " + (s.findings[0] if s.findings else f"{s.status}."))
    if actions:
        lines.append(f"{len(actions)} change(s) proposed and waiting for your approval.")
    all_missing = _unique(missing + [m for s in sections for m in s.missing])
    resp = {
        "answer": "\n".join(lines),
        "intent": intent,
        "agents": [AGENTS[s.agent].describe() for s in sections],
        "context": req.context,
        "sections": [asdict(s) for s in sections],
        "report": _field_report(req, by, now) if intent == "field_report" else None,
        "suggested_actions": _unique([a for s in sections for a in s.actions]),
        "missing_information": all_missing,
        "evidence": _unique([e for s in sections for e in s.evidence]),
        "pending_actions": [_action(a) for a in actions],
        "limitations": _unique([x for s in sections for x in s.limitations]),
        "llm_used": False,
        "generated_by": "deterministic orchestrator (rules + typed tools)",
    }
    return to_jsonable_python(resp)  # stored as JSONB: datetimes -> ISO strings

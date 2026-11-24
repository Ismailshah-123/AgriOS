"""The six agricultural agents. Each one = a purpose, a tool plan, and a composer that turns
tool results into a section: findings, suggested actions (each with its reason and
evidence), missing information and limitations. Deterministic: no LLM, no invented values,
no fertilizer/pesticide doses (CLAUDE.md hard rules 2, 4, 8)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.agents.registry import ToolResult


@dataclass
class Call:
    tool: str
    args: dict[str, Any]


@dataclass
class Outcome:
    tool: str
    status: str  # ok | unavailable | error | timeout | denied | proposed
    result: ToolResult | None = None
    error_code: str | None = None


@dataclass
class Request:
    message: str
    field_id: str | None
    farm_id: str | None
    context: dict[str, Any] | None = None  # get_field_context output


@dataclass
class Section:
    agent: str
    title: str
    status: str = "ok"
    findings: list[str] = field(default_factory=list)
    actions: list[dict[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def act(self, action: str, reason: str) -> None:
        self.actions.append({"agent": self.agent, "action": action, "reason": reason})


def _base(agent: str, title: str, outs: list[Outcome]) -> tuple[Section, list[ToolResult]]:
    s = Section(agent, title)
    ok = []
    for o in outs:
        if o.result is not None:
            s.missing += o.result.missing
            s.evidence += o.result.evidence
            ok.append(o.result)
        elif o.status not in ("proposed",):
            s.missing.append(f"{o.tool}:{o.error_code or o.status}")
    if not ok or all(r.status == "unavailable" for r in ok):
        s.status = "unavailable"
    elif len(ok) < len(outs):
        s.status = "partial"
    return s, ok


class Agent:
    name = ""
    title = ""
    purpose = ""
    needs_field = True

    def plan(self, req: Request) -> list[Call]:
        raise NotImplementedError

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "purpose": self.purpose}


class CropHealthAgent(Agent):
    name, title = "crop_health", "Crop health"
    purpose = (
        "Summarises Crop Doctor cases for the field and the model's availability. Never "
        "diagnoses from weather; low confidence is reported as 'no definitive diagnosis'."
    )

    def plan(self, req: Request) -> list[Call]:
        return [Call("get_crop_health", {"field_id": req.field_id})]

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        s, ok = _base(self.name, self.title, outs)
        if not ok:
            return s
        d = ok[0].data
        s.data = {"model_status": d["model_status"], "cases": d["cases"]}
        if d["model_status"] != "ready":
            s.findings.append(
                f"No validated Crop Doctor model is active ({d['model_status']}); photos can "
                "be stored but no automated diagnosis is produced."
            )
        if not d["cases"]:
            s.findings.append("No Crop Doctor cases recorded for this field.")
            s.act("Photograph affected leaves in Crop Doctor.", "No crop-health evidence yet.")
            return s
        c = d["cases"][0]
        when = c["created_at"][:10]
        if c["decision"] == "accepted":
            s.findings.append(
                f"Latest case ({when}): model suggests {c['predicted_class']} with calibrated "
                f"confidence {c['calibrated_confidence']:.2f} (inferred, not lab-confirmed)."
            )
        elif c["decision"] in ("unsure", "out_of_scope"):
            s.findings.append(f"Latest case ({when}): no definitive diagnosis ({c['decision']}).")
            s.act("Request expert review or add clearer photos.", "Model confidence was low.")
        else:
            s.findings.append(f"Latest case ({when}): analysis {c['inference_status']}.")
        s.limitations.append("Model predictions are decision support, not confirmed diagnoses.")
        return s


class SoilAgent(Agent):
    name, title = "soil", "Soil condition"
    purpose = (
        "Reads the latest soil test and its cited interpretation (pH, salinity, crop salt "
        "tolerance), lists missing measures, and never fills or doses."
    )

    def plan(self, req: Request) -> list[Call]:
        return [Call("get_soil_summary", {"field_id": req.field_id})]

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        s, ok = _base(self.name, self.title, outs)
        if not ok or ok[0].data["latest"] is None:
            s.findings.append("No soil test is recorded for this field.")
            s.act(
                "Add a laboratory soil test (pH, ECe, organic matter, P, K, texture).",
                "Soil condition cannot be assessed without measurements.",
            )
            return s
        latest = ok[0].data["latest"]
        s.data = {"latest": latest, "observations": ok[0].data["observations"]}
        s.findings.append(f"Latest test {latest['sampled_on']} ({latest['data_origin']}).")
        interp = latest["interpretation"]
        for f in interp["flags"] + interp["warnings"]:
            src = f.get("source")
            s.findings.append(f"{f.get('message')}" + (f" [source: {src[:60]}…]" if src else ""))
        for n in interp["not_evaluated"]:
            s.limitations.append(f"{n.get('measure')}: {n.get('reason')}")
        if ok[0].data["missing_measures"]:
            s.act(
                "Ask the lab for: " + ", ".join(ok[0].data["missing_measures"]) + ".",
                "These key measures are missing from the latest test.",
            )
        s.limitations.append(interp["dose_policy"])
        return s


class WeatherAgent(Agent):
    name, title = "weather", "Weather and agricultural risk"
    purpose = (
        "Retrieves the field forecast (Open-Meteo, cached) and evaluates cited risk "
        "indicators. Weather risk is never presented as a disease diagnosis."
    )
    ADVICE = {
        "heavy_rainfall": "Check field drainage and postpone operations needing dry soil.",
        "high_wind": "Avoid spraying on the windy days listed; check staking.",
        "frost_risk": "Protect frost-sensitive plants on the listed nights.",
        "late_blight_smith_period": "Inspect tomato leaves for blight symptoms; upload "
        "photos to Crop Doctor if lesions appear.",
    }

    def plan(self, req: Request) -> list[Call]:
        return [Call("get_weather", {"field_id": req.field_id})]

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        s, ok = _base(self.name, self.title, outs)
        if not ok:
            return s
        w = ok[0].data
        if w["status"] == "unavailable":
            if w.get("reason") == "location_missing":
                s.findings.append("Farm coordinates are missing, so no forecast was requested.")
                s.act(
                    "Set the farm location, e.g. 'set farm location to 31.52, 74.36'.",
                    "Weather needs real coordinates; none are invented.",
                )
            else:
                s.findings.append(f"Weather provider unavailable ({w.get('reason')}).")
            return s
        cur = w.get("current") or {}
        s.data = {
            k: w.get(k)
            for k in (
                "status",
                "retrieved_at",
                "age_minutes",
                "provider",
                "current",
                "daily",
                "indicators",
                "not_evaluated",
            )
        }
        s.findings.append(
            f"Now: {cur.get('temperature_c')} °C, RH {cur.get('relative_humidity_pct')} %, "
            f"wind {cur.get('wind_speed_kmh')} km/h ({w['status']}, retrieved "
            f"{w.get('age_minutes')} min ago; source {(w.get('provider') or {}).get('name')})."
        )
        if w["status"] == "stale":
            s.limitations.append("Forecast is stale: the provider could not be reached.")
        for ind in w["indicators"]:
            s.findings.append(f"[{ind['level']}] {ind['message']}")
            if ind["id"] in self.ADVICE:
                s.act(self.ADVICE[ind["id"]], f"Indicator '{ind['id']}' ({ind['source'][:50]}…)")
        s.limitations.append(w["disclaimer"])
        for n in w["not_evaluated"]:
            s.limitations.append(f"{n['indicator']} not evaluated: {n['reason']}")
        return s


class IrrigationAgent(Agent):
    name, title = "irrigation", "Crop water demand"
    purpose = (
        "Estimates crop water demand (FAO-56 ETc = Kc x ET0) for the active crop cycle and "
        "compares it with forecast rain. Advisory only: it never controls equipment."
    )

    def plan(self, req: Request) -> list[Call]:
        return [Call("get_water_demand", {"field_id": req.field_id})]

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        s, ok = _base(self.name, self.title, outs)
        if not ok:
            return s
        d = ok[0].data
        s.limitations += d["limitations"]
        if d["status"] != "ok":
            s.findings.append(
                "Water demand cannot be estimated: missing "
                + ", ".join(d["missing_information"])
                + "."
            )
            if "crop_cycle.sowing_date" in d["missing_information"]:
                s.act(
                    "Enter the sowing/transplanting date, e.g. 'set sowing date 2026-10-01'.",
                    "FAO-56 stages are counted from planting.",
                )
            return s
        t = d["totals"]
        s.data = {
            k: d[k]
            for k in (
                "current_stage",
                "days_after_planting",
                "totals",
                "daily",
                "units",
                "method",
                "source",
                "weather_retrieved_at",
            )
        }
        s.findings.append(
            f"Stage {d['current_stage']} (day {d['days_after_planting']}). Estimated crop water "
            f"demand {t['etc_low_mm']}-{t['etc_high_mm']} mm over {t['days']} days "
            f"(ET0 {t['et0_mm']} mm; inferred)."
        )
        if t["gross_rain_mm"] is not None:
            s.findings.append(f"Forecast gross rain {t['gross_rain_mm']} mm (not effective rain).")
            if t["gross_rain_mm"] < t["etc_low_mm"]:
                s.act(
                    "Check soil moisture and plan irrigation for the coming days.",
                    "Forecast rain is below the lower estimate of crop water demand.",
                )
        return s


class FarmOperationsAgent(Agent):
    name, title = "farm_operations", "Farm records"
    purpose = (
        "Reads farms, fields and crop cycles, and PROPOSES record changes (farm location, "
        "sowing date) that run only after the owner approves them."
    )
    needs_field = False
    LATLON = re.compile(r"(-?\d{1,2}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)")
    DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

    def plan(self, req: Request) -> list[Call]:
        return [Call("list_farms_and_fields", {})]

    def proposals(self, req: Request) -> list[Call]:
        msg, ctx = req.message.lower(), req.context or {}
        out = []
        m = self.LATLON.search(msg)
        farm_id = (ctx.get("farm") or {}).get("id") or req.farm_id
        if m and ("location" in msg or "coordinat" in msg) and farm_id:
            lat, lon = (round(float(v), 2) for v in m.groups())
            out.append(
                Call(
                    "set_farm_location",
                    {"farm_id": farm_id, "latitude": str(lat), "longitude": str(lon)},
                )
            )
        d = self.DATE.search(msg)
        cycle = ctx.get("crop_cycle")
        if d and ("sow" in msg or "plant" in msg or "transplant" in msg) and cycle:
            try:
                date.fromisoformat(d.group(1))
            except ValueError:
                return out
            out.append(
                Call("set_cycle_sowing_date", {"cycle_id": cycle["id"], "sowing_date": d.group(1)})
            )
        return out

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        s, ok = _base(self.name, self.title, outs)
        for r in ok:
            if "farms" in r.data:
                s.data["farms"] = r.data["farms"]
                for f in r.data["farms"]:
                    names = ", ".join(x["name"] for x in f["fields"]) or "no fields"
                    loc = "located" if f["has_coordinates"] else "no coordinates"
                    s.findings.append(f"{f['name']} ({loc}): {names}.")
        return s


class KnowledgeAgent(Agent):
    name, title = "knowledge", "Methods and sources"
    purpose = (
        "Answers 'why/how' questions from the cited methods AgriOS actually uses. It does not "
        "generate agronomic advice; reviewed knowledge documents (RAG) are not loaded yet."
    )
    needs_field = False

    def plan(self, req: Request) -> list[Call]:
        return [Call("search_method_references", {"query": req.message[:200]})]

    def compose(self, req: Request, outs: list[Outcome]) -> Section:
        s, ok = _base(self.name, self.title, outs)
        if not ok:
            return s
        d = ok[0].data
        s.data = {"matches": d["matches"]}
        for m in d["matches"]:
            s.findings.append(f"{m['id']}: {m['basis']} — {m['source']}")
        if not d["matches"]:
            s.findings.append("No AgriOS method reference matches this question.")
        s.limitations.append(d["note"])
        return s


AGENTS: dict[str, Agent] = {
    a.name: a
    for a in (
        CropHealthAgent(),
        SoilAgent(),
        WeatherAgent(),
        IrrigationAgent(),
        FarmOperationsAgent(),
        KnowledgeAgent(),
    )
}

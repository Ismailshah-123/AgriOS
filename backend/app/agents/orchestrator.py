"""Deterministic orchestrator: intent -> agents -> bounded tool execution -> structured
response. Runs fully without an LLM (CLAUDE.md hard rule 8). Write tools are never
executed here: they become pending actions that the owner must approve (hard rule 9)."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.agents import registry, report
from app.agents import tools as _tools  # noqa: F401 - registers the tool set
from app.agents.agents import AGENTS, Call, Outcome, Request, Section
from app.agents.models import (
    ActionStatus,
    AgentAction,
    AgentRun,
    AgentStep,
    RunStatus,
    StepStatus,
)
from app.agents.registry import ToolContext, ToolError
from app.audit import service as audit
from app.core.errors import AppError
from app.farms import repository as farm_repo
from app.farms.models import Farm, Field

MAX_STEPS = 12
RUN_BUDGET_S = 45.0
ACTION_TTL = timedelta(hours=24)

# (intent, keywords, agents) in priority order; keywords match at a word start.
INTENTS: list[tuple[str, tuple[str, ...], list[str]]] = [
    (
        "field_report",
        ("report", "condition", "overview", "complete", "assessment", "رپورٹ", "حالت"),
        ["soil", "weather", "irrigation", "crop_health"],
    ),
    ("update_records", ("set ", "update ", "change "), ["farm_operations"]),
    (
        "crop_health",
        ("disease", "diagnos", "crop doctor", "leaf", "leaves", "spots", "blight", "بیماری"),
        ["crop_health"],
    ),
    (
        "irrigation",
        ("irrigat", "water demand", "water need", "evapotrans", "et0", "etc", "پانی", "آبپاشی"),
        ["irrigation"],
    ),
    (
        "weather",
        ("weather", "rain", "forecast", "temperature", "wind", "frost", "humid", "موسم", "بارش"),
        ["weather"],
    ),
    ("soil", ("soil", "ph", "salin", "nutrient", "organic", "texture", "مٹی"), ["soil"]),
    (
        "knowledge",
        ("why", "how is", "how do", "source", "method", "reference", "explain", "what is"),
        ["knowledge"],
    ),
    ("farm_records", ("farm", "field", "crop cycle", "my fields", "list"), ["farm_operations"]),
]


def classify(message: str) -> tuple[str, list[str]]:
    msg = message.lower()
    best: tuple[int, int, str, list[str]] | None = None
    for prio, (intent, kws, agents) in enumerate(INTENTS):
        hits = sum(1 for k in kws if re.search(r"(?<!\w)" + re.escape(k), msg))
        if hits and (best is None or (hits, -prio) > (best[0], best[1])):
            best = (hits, -prio, intent, agents)
        if hits and intent == "field_report":  # explicit report request wins
            return intent, agents
    return (best[2], best[3]) if best else ("help", [])


def _outcome(ctx: ToolContext, call: Call) -> Outcome:
    try:
        r = registry.execute(ctx, call.tool, call.args)
        return Outcome(call.tool, r.status, r)
    except ToolError as e:
        status = {
            "timeout": "timeout",
            "not_found": "denied",
            "unknown_tool": "denied",
            "invalid_input": "denied",
            "approval_required": "denied",
        }.get(e.code, "error")
        return Outcome(call.tool, status, None, e.code)


def _resolve(
    ctx: ToolContext, farm_id: uuid.UUID | None, field_id: uuid.UUID | None, needs_field: bool
) -> tuple[uuid.UUID | None, uuid.UUID | None, list[str]]:
    if field_id is not None:
        row = farm_repo.get_field_row(ctx.db, ctx.user.id, field_id)
        if row is None:
            raise AppError("not_found", "Field not found.", 404)
        if farm_id is not None and row[0].farm_id != farm_id:
            raise AppError("validation_error", "Field does not belong to that farm.", 422)
        return row[0].farm_id, field_id, []
    if farm_id is not None and farm_repo.get_owned_farm(ctx.db, ctx.user.id, farm_id) is None:
        raise AppError("not_found", "Farm not found.", 404)
    if not needs_field:
        return farm_id, None, []
    q = select(Field.id, Field.farm_id).join(Farm).where(Farm.owner_id == ctx.user.id)
    if farm_id is not None:
        q = q.where(Field.farm_id == farm_id)
    rows = ctx.db.execute(q.limit(2)).all()
    if len(rows) == 1:  # the only field: unambiguous
        return rows[0][1], rows[0][0], []
    return farm_id, None, ["field_id (select a field)" if rows else "field (create a field)"]


def run(
    ctx: ToolContext, message: str, farm_id: uuid.UUID | None, field_id: uuid.UUID | None
) -> AgentRun:
    t0 = time.perf_counter()
    intent, names = classify(message)
    needs_field = intent == "update_records" or any(AGENTS[n].needs_field for n in names)
    farm_id, field_id, missing = _resolve(ctx, farm_id, field_id, needs_field)
    req = Request(message, str(field_id) if field_id else None, str(farm_id) if farm_id else None)
    steps: list[tuple[str, Call, Outcome, int]] = []

    def call(agent: str, c: Call) -> Outcome:
        if len(steps) >= MAX_STEPS or time.perf_counter() - t0 > RUN_BUDGET_S:
            o = Outcome(c.tool, "timeout", None, "run_budget_exhausted")
            steps.append((agent, c, o, 0))
            return o
        s0 = time.perf_counter()
        o = _outcome(ctx, c)
        steps.append((agent, c, o, int((time.perf_counter() - s0) * 1000)))
        return o

    if field_id is not None:
        o = call("farm_operations", Call("get_field_context", {"field_id": req.field_id}))
        if o.result is not None:
            req.context = o.result.data
            missing += o.result.missing
    sections: list[Section] = []
    proposals: list[tuple[Call, str]] = []
    if needs_field and field_id is None:
        names = []  # cannot run field agents without a field: ask instead of guessing
    for n in names:
        agent = AGENTS[n]
        if intent == "update_records":
            for c in AGENTS["farm_operations"].proposals(req):  # type: ignore[attr-defined]
                try:
                    registry.validate_input(c.tool, c.args)
                    proposals.append((c, registry.TOOLS[c.tool].description))
                    steps.append((n, c, Outcome(c.tool, "proposed"), 0))
                except ToolError as e:
                    steps.append((n, c, Outcome(c.tool, "denied", None, e.code), 0))
            if not proposals:
                missing.append(
                    "recognised change (e.g. 'set farm location to 31.52, 74.36' or "
                    "'set sowing date 2026-10-01')"
                )
        outs = [call(n, c) for c in agent.plan(req)]
        sections.append(agent.compose(req, outs))

    now = datetime.now(UTC)
    run_row = AgentRun(
        user_id=ctx.user.id,
        farm_id=farm_id,
        field_id=field_id,
        message=message,
        intent=intent,
        agents=names,
        status=RunStatus.COMPLETED,
        response={},
        duration_ms=0,
    )
    ctx.db.add(run_row)
    ctx.db.flush()
    actions = []
    for c, desc in proposals:
        a = AgentAction(
            user_id=ctx.user.id,
            run_id=run_row.id,
            agent="farm_operations",
            tool=c.tool,
            args=c.args,
            description=f"{desc} {c.args}",
            status=ActionStatus.PENDING,
            requested_by=ctx.user.id,
            expires_at=now + ACTION_TTL,
        )
        ctx.db.add(a)
        ctx.db.flush()
        audit.record(
            ctx.db,
            action="agent_action.proposed",
            entity="agent_action",
            entity_id=a.id,
            actor_id=ctx.user.id,
            request_id=ctx.request_id,
            meta={"tool": c.tool, "run_id": str(run_row.id)},
        )
        actions.append(a)
    for i, (agent, c, o, ms) in enumerate(steps):
        ctx.db.add(
            AgentStep(
                run_id=run_row.id,
                position=i,
                agent=agent,
                tool=c.tool,
                mode=registry.TOOLS[c.tool].mode if c.tool in registry.TOOLS else "read",
                input=c.args,
                status=StepStatus(o.status),
                summary=o.result.summary if o.result else None,
                error_code=o.error_code,
                duration_ms=ms,
            )
        )
    response = report.build(intent, req, sections, missing, actions, now)
    run_row.response = response
    run_row.status = (
        RunStatus.PARTIAL
        if response["missing_information"] or any(s.status != "ok" for s in sections)
        else RunStatus.COMPLETED
    )
    run_row.duration_ms = int((time.perf_counter() - t0) * 1000)
    audit.record(
        ctx.db,
        action="agent_run.completed",
        entity="agent_run",
        entity_id=run_row.id,
        actor_id=ctx.user.id,
        request_id=ctx.request_id,
        meta={"intent": intent, "steps": len(steps), "status": run_row.status},
    )
    ctx.db.commit()
    return run_row


def section_dict(s: Section) -> dict[str, Any]:
    return asdict(s)

# Agent system — architecture, tool registry, permissions and approvals
Summary: how AgriOS agents work as implemented in Phase 4B (`backend/app/agents/`). Deterministic: no LLM is called (CLAUDE.md hard rule 8); an LLM adapter may later only re-phrase the structured output.

## 1. Request flow
```
POST /api/v1/agent/runs {message, farm_id?, field_id?}   (JWT, owner-scoped)
  -> orchestrator.classify(message)      keyword intent rules (EN + basic Urdu), priority order
  -> _resolve(): ownership check (404 for another user's farm/field); the only field is
     auto-selected, otherwise the run asks the user to choose (never guesses)
  -> get_field_context tool (field, farm, active crop cycle, FAO-56 stage)
  -> each selected agent: plan() -> tool calls -> registry.execute() -> compose() section
  -> write intents: proposals become agent_actions (status pending); nothing is written
  -> report.build(): answer, sections, field report, suggested actions, missing info,
     evidence, pending actions, limitations, llm_used=false
  -> persist agent_runs + agent_steps (+ agent_actions); audit agent_run.completed
```
Bounds: at most 12 tool steps and a 45 s run budget; steps beyond either are recorded as `timeout` (`run_budget_exhausted`) and the run is `partial`.

## 2. Intents
| Intent | Example | Agents |
|---|---|---|
| field_report | "Give me a complete condition report for my tomato field" | soil, weather, irrigation, crop_health |
| update_records | "set farm location to 31.52, 74.36", "set sowing date 2026-10-01" | farm_operations (proposals) |
| crop_health / irrigation / weather / soil | "Will it rain this week?", "موسم کیسا ہے" | the matching agent |
| knowledge | "Explain the source of the Smith period" | knowledge |
| farm_records | "list my fields" | farm_operations |
| help | anything unmatched | none (capability message) |

## 3. Agents (`app/agents/agents.py`)
| Agent | Purpose | Tools |
|---|---|---|
| Crop Health | Crop Doctor cases + model availability; low confidence is "no definitive diagnosis" | get_crop_health |
| Soil Intelligence | Latest soil test, cited interpretation, missing measures; no doses | get_soil_summary |
| Weather Intelligence | Forecast + cited risk indicators; advice per indicator; never a diagnosis | get_weather |
| Irrigation Planning | FAO-56 ETc vs forecast rain; advisory only, no equipment control | get_water_demand |
| Farm Operations | Farms/fields listing; proposes record changes for approval | list_farms_and_fields, set_farm_location*, set_cycle_sowing_date* |
| Agricultural Knowledge | Answers "why/how" from the cited methods AgriOS uses; reviewed documents (RAG) not loaded | search_method_references |
(* write tool, approval required)

## 4. Tool registry (`app/agents/registry.py`, `tools.py`)
Each tool declares name, description, mode (read/write), permission (`owner`), Pydantic input and output schemas, timeout and handler. `GET /api/v1/agent/catalogue` returns the full machine-readable list with JSON schemas.

| Tool | Mode | Timeout | Calls (existing service) |
|---|---|---|---|
| list_farms_and_fields | read | 5 s | owner-scoped farm/field query |
| get_field_context | read | 5 s | farms repository + irrigation.active_cycle + FAO-56 stage |
| get_soil_summary | read | 5 s | soil.service.summary |
| get_weather | read | 15 s | weather.service.get_weather (cache, provider) |
| get_water_demand | read | 15 s | irrigation.service.water_demand |
| get_crop_health | read | 5 s | crop_health cases + mlops.registry.availability |
| search_method_references | read | 2 s | in-code citation registry (weather RULES, soil sources, FAO-56, decision rule) |
| set_farm_location | write | 5 s | farms.service.update_farm (validation + audit) |
| set_cycle_sowing_date | write | 5 s | farms.service.update_cycle (cycle rules + audit) |

Executor guarantees (`registry.execute`): unknown tool → `unknown_tool`; schema failure → `invalid_input`; write without approval → `approval_required`; DB work beyond the timeout → `timeout` (PostgreSQL `SET LOCAL statement_timeout`; the weather provider has its own HTTP timeout); malformed handler output → `invalid_output`. There is no SQL, shell, file or code-execution tool.

## 5. Permissions and approvals (`app/agents/approvals.py`)
- Identity: every endpoint requires the JWT user; every tool runs as that user; services return 404 for other users' records (tenant isolation tested).
- Default read-only: only the two write tools exist, and the orchestrator never executes them.
- Lifecycle: `pending → approved → executed | failed`, `pending → rejected`, `pending → expired` (24 h TTL, evaluated lazily on list/approve). Approval claims the row atomically (`UPDATE … WHERE status='pending'`), so a double click cannot execute twice (second call → 409).
- Recorded: `requested_by`, `decided_by` + `decided_at`, `executed_by` + `executed_at`, `result` / `error_code`.
- Audit events: `agent_action.proposed|approved|rejected|expired|executed|failed`, `agent_run.completed`, plus the domain event written by the farm service itself.
- Execution re-validates the stored arguments against the tool schema and re-checks ownership inside the service.

## 6. Data model (migration 0006)
`agent_runs` (user, farm, field, message, intent, agents, status, response JSONB, duration), `agent_steps` (run, position, agent, tool, mode, input, status, summary, error_code, duration), `agent_actions` (approval workflow columns above). Downgrade drops the three tables.

## 7. Known limitations
- Intent detection is keyword-based (EN + a few Urdu words); paraphrases outside the keyword lists fall back to `help`.
- Knowledge agent searches method references only; verified RAG over reviewed documents is Proposed.
- No LLM phrasing; answers are templated from structured findings.

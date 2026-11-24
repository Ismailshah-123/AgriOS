# MODULE_CONTRACTS.md — integration contracts for future modules and agents
Status: **Proposed contracts (2026-11-23). Nothing below is implemented unless marked Implemented.**
Purpose: let Crop Health, Soil, Weather, Irrigation, Nutrients, Economics, Knowledge and the agent framework plug into the Phase 2 platform core without rework. Companion to ARCHITECTURE_ROADMAP_PROPOSAL.md (sections 4-9).

## 1. The spine (Implemented)
`users 1─N farms 1─N fields 1─N crop_cycles N─1 crop_definitions` — migrations 0001-0002.
- Every module record references `fields.id` or `crop_cycles.id` with `ON DELETE RESTRICT`.
- **Single ownership entry point:** `app.farms.service.get_owned_cycle_context(db, user, cycle_id) -> (CropCycle, Field, Farm)`; raises 404 `not_found` for missing *or foreign* ids. Modules never query farm tables directly.
- Every write calls `app.audit.service.record(...)` inside the same transaction (append-only, DB-enforced).
- Measurements carry `data_origin` (`app.kernel.origin.DataOrigin`) and a unit; areas are stored in hectares.

## 2. Crop Health / Computer Vision (Implemented 2026-11-23, except a real model loader)
Three separate concepts (the documented `case_status` enum is unchanged):
| Concept | Where | Values |
|---|---|---|
| `case_status` | `diagnosis_cases.status` | submitted, retake, unsure, accepted, out_of_scope, expert_review, closed |
| `inference_status` (+) | `diagnosis_cases.inference_status` | not_started, queued, running, completed, failed, model_unavailable |
| `model_availability` (+) | system, `GET /models/availability`, `/ready` | not_registered, not_installed, checksum_mismatch, loading, ready, error |
Rules: a case always has `crop_cycle_id` (validated via section 1). No active model ⇒ `inference_status = model_unavailable`, `case_status` stays `submitted`, **no prediction row is written**. Predictions always store `model_version_id`.
```python
class Predictor(Protocol):          # app/mlops
    task: str                        # "crop_health_image", later "soil_suitability", ...
    def predict(self, x: ModelInput) -> RawOutput: ...   # logits + label list; no decisions
# Calibration (temperature), OOD score and the accept/unsure/out_of_scope rule live in the
# pipeline, configured from the immutable model_versions row - never inside the model.
```

## 3. Domain calculators and services (Proposed, Phases 4-6)
Pure functions in `app/calculators` (no I/O, no LLM); services add persistence and audit.
| Module | Input contract | Output contract | Refusal |
|---|---|---|---|
| FAO-56 irrigation | cycle context + weather series + cited Kc | `{et0, kc, etc, effective_rain, net_mm, gross_mm, volume_m3_per_ha, assumptions[], source_refs[]}` | missing Kc source ⇒ 422 `no_source` |
| Nutrients | cycle context + soil obs + cited requirement | `{nutrient_need, product_amount, cost, source_ref}` | no reviewed table ⇒ 422 `no_source` |
| Soil | field + soil observation | flags with threshold `source_ref` | unknown threshold ⇒ no flag, stated |
| Weather/risk | coarse farm location (0.01°) | observations labelled `retrieved` + provider + retrieved_at; indicators labelled "indicator" | provider down ⇒ cache/manual, labelled |
| Economics | cycle-scoped expenses/harvests/sales | totals, cost/acre, margin, break-even; all labelled estimate | — |
Every recommendation response includes `sources[]`, `assumptions[]`, `uncertainty` (API_CONTRACTS global rule).

## 4. Knowledge / RAG (Proposed, Phase 9)
`knowledge_documents` is the single source register (licence required) for RAG **and** the cited reference tables used by section 3. `/ask` returns `{answer, citations[]}` or `{answer: null, reason: "no_verified_guidance"}`. A verifier blocks uncited claims and any dose without a reference-table source.

## 5. Agent framework (Proposed, Phase 7) — one orchestrator, not eight chatbots
```python
class ToolSpec(BaseModel):           # registry entry; tools wrap existing services only
    name: str; version: str; description: str
    input_model: type[BaseModel]; output_model: type[BaseModel]
    scope: Literal["read", "compute", "propose", "write"]
    roles: set[UserRole]; consequential: bool; idempotent: bool
    timeout_s: float; max_retries: int = 1

class AgentProfile(BaseModel):       # the 8 planned "agents" are profiles over one registry
    name: str; purpose: str; allowed_tools: set[str]
    max_steps: int; workflows: list[str]; explanation_template: str
```
Execution (single `ToolExecutor`): authorize (profile allow-list x user role x record ownership via section 1; the agent acts **as the user**) → validate input → call service → validate output (units, origin) → read/compute: record step with evidence refs | write: create `ApprovalRequest{id, run_id, tool, args, args_sha256, preview, expires_at}` and pause → on approval: re-authorize, re-validate, execute the **stored** args (hash must match) → audit.
- Run status: planning, running, awaiting_approval, completed, failed, cancelled, expired.
- Failure: one retry on transient errors, then `failed` with "nothing was changed". A tool result is never synthesized.
- Planner: deterministic workflows (default; work with the LLM disabled) or an optional LLM planner limited to the profile's tools, step and token caps. LLM text is never stored as a fact, measurement, diagnosis or dose.
- Triggers: user request | cron (Asia/Karachi) | domain event via an outbox table, all executed by the worker process from a DB job queue.
- Audit: `agent_runs`, `tool_invocations`, `approval_requests`, plus `audit_events` for every commit.

| Profile | First tools | Writes (need approval) |
|---|---|---|
| Farm Management | cycles.read, tasks.propose | reminders, record changes |
| Crop Health | case.get, inference.status, knowledge.ask | expert escalation |
| Weather & Risk | weather.get, risk.evaluate | notifications (policy decision pending, see C9) |
| Soil Intelligence | soil.interpret | none |
| Irrigation Optimization | weather.get, fao56.calc, water_balance | irrigation plan |
| Nutrient & Fertilizer | soil.read, fertilizer.calc (cited only) | fertilizer plan |
| Farm Finance | economics.summary, budget.variance | expense drafts |
| Knowledge / RAG | knowledge.ask (verifier) | none |

## 6. Open decisions needed before the matching phase
C7 parallel timeline; C9 whether opt-in in-app notifications need per-item approval; kanal/marla official definition source; LLM provider (D9); Kc and nutrient reference sources (D8).

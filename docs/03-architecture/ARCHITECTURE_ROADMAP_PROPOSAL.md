# ARCHITECTURE_ROADMAP_PROPOSAL.md — architecture assessment and roadmap (DRAFT)
Status: **Proposed, awaiting developer review (2026-11-22).** Does not replace ARCHITECTURE.md, DATABASE_DESIGN.md or API_CONTRACTS.md. Items marked (+) are additions that need approval before those docs are updated.
Sources compared: the academic proposal PDF, Developer Guide v2 PDF, CLAUDE.md, all docs/0x files, and the Phase 1 code (re-run 2026-11-22).

---

## 1. Where the project actually is (verified)

| Area | State | Evidence |
|---|---|---|
| Backend | App factory, env config (SecretStr DB URL, CORS without `*`), error envelope, JSON logs + request id, `/health`, `/ready` (DB check), Alembic scaffold with **no tables** | pytest 21/21, ruff and format clean (re-run today) |
| Frontend | React 19 + Vite + Tailwind v4 shell, typed API client, live status card, routing; the only route is `/crop-doctor` | Vitest 13/13, eslint, tsc clean (re-run today) |
| Database | Not used. Docker daemon off; local PostgreSQL 18 service running, but we have no credentials (intended) | `docker version` fails; service `postgresql-x64-18` Running |
| Domain modules | None: no auth, farms, Crop Doctor upload, calculators, weather, soil, economics, RAG, agents | file tree |
| CI / Compose | Not present (`.github/` and `infrastructure/` contain only empty directories) | file tree |
| Git | `master`, **no commits**, everything untracked | `git status` |
| ML | No dataset, no audit, no splits, no runs. All results PENDING | `ml/` contains no files |

**Conclusion:** Phase 1 is a clean, well-tested **platform skeleton**. It is not yet a Crop Doctor module. "Complete Crop Doctor upload/storage/persistence" is really **not started**, and it cannot be built correctly until users, farms, fields and crop cycles exist, because a case belongs to a crop cycle owned by a user.

## 2. Defects and gaps in Phase 1

| # | Finding | Severity | Fix in |
|---|---|---|---|
| D1 | `get_db()` raises `RuntimeError` when there is no DB, so requests get a 500 `internal_error`. It should be an `AppError("database_unavailable", 503)` | Medium | Phase 2 |
| D2 | `get_engine()` reads global `get_settings()` and ignores `app.state.settings`, so tests cannot inject a test DB URL through `create_app(settings)` | Medium | Phase 2 |
| D3 | `.gitignore` misses `backup/`, `_cleanup_review/`, root `data/`, `datasets/`, `*.zip`, `*.safetensors`, `*.ckpt`, `*.pkl`, `*.joblib`, `ml/models/**` (only .pt/.pth/.onnx are listed), `ml/reports/**/checkpoints`, `.claude/settings.local.json` | High (before first commit) | Staging step |
| D4 | The UI frames AgriOS as single-purpose: `/` redirects to `/crop-doctor`, and the nav has one item. This contradicts DESIGN.md §3 (Home, Fields, Doctor, Tools, More) | Medium | Phase 3 |
| D5 | Empty root folders `agents/`, `shared/`, `infrastructure/*`, `knowledge/{chunking,…}` duplicate the backend modules that ARCHITECTURE.md places in `backend/app/{agents,knowledge}`. Git ignores empty folders, so this is only confusing, not harmful | Low | Decide (§11) |
| D6 | CLAUDE.md rule 12 points to `docs/FEATURE_STATUS.md`, which does not exist. Feature status currently lives in PROGRESS.md | Low | Doc fix (approval) |
| D7 | IMPLEMENTATION_PLAN step 7 says "Crop Doctor API stub (returns 'unsure')". That is a fabricated model output. Replace it with `inference_status = model_unavailable` (§5.4) | **High (policy)** | Phase 3 |
| D8 | Starlette deprecation warning about `httpx` in TestClient | Low | Track |
| D9 | No CI or Compose yet (already listed as open in PROGRESS) | Medium | Phase 2 |

## 3. Proposal vs repository: what is missing

All P0 and P1 modules in the proposal are missing. The documented decisions are good and should be kept. Conflicts between the documents:

| Conflict | Proposal | Repo docs | Recommendation |
|---|---|---|---|
| Table names | `soil_tests, crop_cases, agent_steps, approvals, audit_logs, knowledge_sources` | `soil_observations, diagnosis_cases, tool_invocations, audit_events, knowledge_documents` | Use the **DATABASE_DESIGN.md** names; the proposal itself says migrations are authoritative |
| Approvals table | `approvals` exists | missing | Add `approval_requests` (+) |
| Irrigation agent priority | P0 (Table 29) | P1 (CLAUDE.md, resolved) | Keep P1, but build it *first* because its tools need no model (§8.6) |
| Your expanded vision (8 agents, budgets, inventory, soil ML) | 1 real agent P0, others "designs" | same | §10: 2–3 real agent profiles on one orchestrator; the rest are Proposed |
| Input inventory warnings | not in docs | not in docs | (+) P2 ledger table; out of FYP core |
| Budgets and what-if | what-if mentioned (P1/P2) | FR10, FR16 | Budgets P1 (cheap), what-if P1 as pure functions |

## 4. Architecture

### 4.1 Style (unchanged)
Modular monolith: one FastAPI app plus one **worker process from the same codebase** (scheduled and background jobs). PostgreSQL 15+ with pgvector. The stack is kept. Additions only:

| Addition | Why | Rejected alternative |
|---|---|---|
| `pwdlib[argon2]` / `argon2-cffi`, `PyJWT` | Auth per SECURITY.md | — |
| `Pillow` (+ `opencv-python-headless` later) | Magic-byte checks, decode, EXIF strip by re-encode, quality checks | — |
| `httpx` (runtime) | Weather and LLM adapters | requests |
| DB-backed job queue (`jobs` table, `FOR UPDATE SKIP LOCKED`) + an in-process scheduler in the worker | No new infrastructure. Jobs are transactional with domain writes. Fits a 1-dev budget | Celery + Redis: an extra service and broker with no FYP benefit |
| `pgvector` (python), a local multilingual sentence-embedding model | RAG without a paid API | Hosted vector DB |
| `react-i18next`, `react-hook-form` + `zod` | EN/UR, validated forms | — |

### 4.2 Backend module boundaries (`backend/app/<module>/{models,schemas,service,router}.py`)

```
core/        config, errors, logging, security (JWT, hashing), pagination, ids
kernel/      DataOrigin enum, Quantity{value,unit,data_origin,source_ref,observed_at}, Evidence, Uncertainty
units/       pure: area (ha internal), mass (kg internal), volume, depth; cited definitions
identity/    users, refresh tokens, roles, RBAC deps, current_user
audit/       append-only audit_events + record() service (used by every write)
farms/       farms, fields, crop catalogue, crop cycles, stages, activities, input applications
references/  (+) cited reference tables: Kc, stage lengths, nutrient requirements, soil/risk thresholds
calculators/ pure functions: fao56 (ET0 PM, ETc, water balance), fertilizer, economics, soil_rules, risk
weather/     WeatherProvider adapters (Open-Meteo forecast, NASA POWER history), cache, fallback
soil/        soil observations, interpretation (rules) and suitability baseline
irrigation/  irrigation plans (calc + persistence + status)
nutrients/   fertilizer plans (refuses without a reviewed source)
economics/   expenses, harvests, sales, budgets, summaries, what-if
doctor/      cases, upload pipeline, quality gate, decision rule, case status
mlops/       model registry, availability, Predictor interface, inference jobs, monitoring stats
storage/     StorageBackend (local private FS now; S3-compatible later), signed URLs, retention
knowledge/   sources, ingestion, chunking, embeddings, hybrid retrieval, verifier, /ask
agents/      tool registry, executor, policies, approvals, orchestrator, workflows, LLM adapter
tasks/       tasks, reminders, in-app notifications
experts/     review queue, corrected labels, case messages
jobs/        queue, scheduler, outbox dispatcher (worker entrypoint)
sync/        offline batch with idempotency
admin/       users, models, audit browsing, system health
```
Rules (existing, now enforced): a module touches only its own tables and calls other modules through their `service`. Calculators have no I/O. Nothing in the decision path imports the LLM adapter.

### 4.3 Shared domain entities (the spine)
`User → Farm → Field → CropCycle` is the root. **Every** domain record hangs off a `crop_cycle_id` or a `field_id`. Ownership resolves through that chain in one service call: `farms.service.assert_owns(user, cycle_id)`, which returns 404 when the user is not the owner.
Cross-cutting value types: `Quantity` (value, unit, data_origin, source_ref, observed_at), `Evidence` (source doc/chunk/page or tool-step id), `Uncertainty` (level words plus numeric value where valid).

### 4.4 Database (DATABASE_DESIGN.md plus proposed additions)

| Group | Tables ((+) = addition) |
|---|---|
| Identity / audit | users, refresh_tokens (+), audit_events (append-only) |
| Farm | farms, fields, crop_definitions, crop_cycles, activities, input_applications |
| References (+) | crop_kc_values, crop_stage_lengths, nutrient_requirements, soil_thresholds, risk_thresholds, unit_definitions. Each row: `source_doc_id` → knowledge_documents, page/table, review_status |
| Observations | soil_observations, weather_observations (+provider, retrieved_at, is_forecast, grid lat/lon), sensor_readings (is_simulated) |
| Doctor | diagnosis_cases (+inference_status, +quality jsonb), diagnosis_predictions, expert_reviews, case_messages |
| MLOps | model_versions (+task, +labels, +sha256, +artifact_uri, +ood_threshold, +model_card_uri), model_predictions (+, P1, tabular models) |
| Plans | irrigation_plans, fertilizer_plans (plan_status) |
| Economics | expenses, harvest_records, revenues (sales), budgets (+), scenarios (+, P2), inventory_items / stock_movements (+, P2) |
| Knowledge | knowledge_documents (the **single source register** for RAG *and* reference tables), knowledge_chunks (vector + tsvector), qa_answers (+, citations need a parent), citations |
| Agents | agent_runs, tool_invocations, approval_requests (+), automation_subscriptions (+) |
| Jobs | jobs (+), domain_events outbox (+) |
| Tasks | tasks, reminders, notifications |

Money: `NUMERIC(14,2)` + `currency` (default PKR). Mass in kg internally (maund conversion only from a verified definition). Area in ha internally.

### 4.5 API contracts
Follow API_CONTRACTS.md. Proposed **additive** changes, which need approval:
1. Case response gains `inference_status` and `model_availability` (§5.4). Existing `status` values are unchanged.
2. New groups: `/expenses`, `/harvests`, `/revenues`, `/budgets`, `/economics/summary?cycle_id=`, `/tasks`, `/notifications`, `/automations`, `/approvals` (list), `/references/*` (admin review), `/files/{id}` (signed and short-lived), `/models/availability`.
3. `/ready` gains `checks.models` and `checks.storage`.
4. OpenAPI snapshot test (already required) lands in Phase 2, so every later change is visible in review.

### 4.6 Authentication and authorization
- Argon2 hashes. Access JWT 15 min (Bearer). Refresh token rotating, stored **hashed** in `refresh_tokens` (revocable), sent as an httpOnly SameSite=Strict cookie (this turns on `allow_credentials` for listed origins).
- Roles: farmer, expert, admin. FastAPI dependencies `require_role(...)`, plus ownership checks in services, never in routers alone.
- Experts see only assigned cases. Admins never see farm data unless an audited support action is added later.
- Agents act **as the requesting user**: same ownership checks and no elevated identity.
- Login and upload rate limits: in-process limiter now, documented as single-instance only.

### 4.7 Background jobs and scheduling
`worker` = `python -m app.jobs.worker`: it polls `jobs`, runs the scheduler (cron rows per automation subscription, Asia/Karachi), and dispatches `domain_events` (outbox, written in the same transaction as the domain change). Jobs: inference, weather refresh, risk evaluation, daily summary, retention purge, ingestion. Each job is idempotent (unique `dedupe_key`), retries with backoff up to N, then goes to `failed` and is visible to admin.

### 4.8 Storage and data governance
Private root `STORAGE_PATH/{owner_id}/{yyyy}/{uuid}.webp`. The pipeline is: magic-byte check, size ≤ 8 MB, decode, dimension check, re-encode (removes EXIF and GPS), sha256, store. No public URLs; `/files/{id}` uses HMAC-signed, expiring links. `consent_flag` on the case (off by default). Retention job deletes images and derived artifacts after the configured period or when the user asks. Audit keeps IDs, not content. Farm location is rounded (for example to 0.1°) before storage and before weather calls.

### 4.9 Model registry and inference
- `model_versions` holds immutable rows per task (`crop_health_image`, later `soil_suitability`, `risk_tabular`). Activation is admin-only and audited. Startup and `/ready` verify sha256.
- `Predictor` protocol: `predict(input) -> RawOutput(logits, labels)`. The pipeline then applies temperature, OOD score, decision rule and explanation. Weights load as `state_dict`/safetensors only (never untrusted pickle).
- **Availability** (system): `not_registered | not_installed | checksum_mismatch | loading | ready | error`.
- Every prediction stores `model_version_id`. The monitoring view shows confidence distribution, rejection rate and expert disagreement per version.

### 4.10 Frontend structure
`src/features/{auth,dashboard,farms,crop-doctor,soil,weather,irrigation,nutrients,finance,knowledge,assistant,tasks,expert,admin}`, each with `api.ts`, `pages/`, `components/`.
- Farmer (mobile, DESIGN §3): bottom bar **Home · Fields · Doctor · Tools · More**. Tools contains Irrigation, Nutrients, Soil, Weather & Risk, Finance, Units. More contains Ask, Assistant, Tasks, Settings.
- Desktop sidebar groups: Overview · Farm (Farms & fields, Cycles, Activities) · Intelligence (Crop Doctor, Soil, Weather & Risk) · Planning (Irrigation, Nutrients) · Finance · Knowledge · Assistant (Runs, Approvals, Automations) · Tasks. Expert: Review queue. Admin: Users, Sources & references, Models, Audit, System.
- Keep the existing rule: **the nav lists only shipped modules.**
- Home dashboard: farm switcher, current-cycle card, StatTiles (each with an origin badge, unit and date), alerts, pending approvals, recent activity.

## 5. Crop Doctor (first module, correctly scoped)

### 5.1 Pipeline
validate → store → quality gate → (inference job) → calibrate → OOD → decision → explain → guidance (accepted only) → persist + audit. This follows ARCHITECTURE.md.

### 5.2 What can ship before the model exists
Upload, validation, storage, case persistence, history, case detail, consent, expert escalation, and the quality gate (blur/exposure metrics are recorded; thresholds are **provisional** until tuned on validation data, and labelled so).

### 5.3 Status model (the case_status enum is unchanged)
- `case_status` (documented): submitted | retake | unsure | accepted | out_of_scope | expert_review | closed
- `inference_status` (+, workflow of the analysis job): `not_started | queued | running | completed | failed | model_unavailable`
- `model_availability` (system property, §4.9). It is **not** stored per case; the case only stores `inference_error_code` when a run fails.

### 5.4 Rule
With no active model, a case stays `submitted` with `inference_status = model_unavailable`. The UI says: "Analysis model not installed yet. Your photo is saved. You can send it to an expert." **No prediction row is written.** This replaces the "stub returns unsure" plan (D7).

## 6. Intelligence modules (no LLM in any decision path)

| Module | Implementation | Validation | Data needed now? |
|---|---|---|---|
| FAO-56 irrigation | ET0 Penman-Monteith (daily), ETc = Kc·ET0, effective rain (documented method), net/gross, root-zone water balance Dr, TAW/RAW, 4-strategy simulation | Reproduce FAO-56 worked examples (record abs error); hand cases | Only the FAO-56 paper (Kc tables entered with page refs) |
| Weather & risk | Open-Meteo (forecast) + NASA POWER (history, radiation) adapters, cache, fallback to cache/manual (labelled); rule indicators with sourced thresholds | Adapter contract tests with recorded fixtures; boundary tests | Free APIs (check terms: Open-Meteo free tier is non-commercial) |
| Soil intelligence | Soil observations; pH/EC/salinity flags from cited thresholds; rule-based crop suitability; ML suitability only with suitable data (Kaggle crop-recommendation = demo only, labelled non-representative) | Boundary tests; rule vs ML comparison if done | Cited threshold source |
| Nutrients | need = demand − soil supply (≥0); product = need / fraction / efficiency; refuses with 422 `no_source` | Urea 100/0.46 = 217.4 kg/ha; refusal test | Provincial/PARC tables (D8) |
| Farm economics | §7 | Spreadsheet reconciliation | None |
| Crop Doctor model | §5 | E1, E2, E5, E7 | **Dataset** |

## 7. Farm economics (agricultural farm finance, not ERP)
- **Entities:** `expenses` (cycle or farm-level; category ∈ seed, fertilizer, pesticide, labour, machinery, irrigation, energy, transport, land_rent, other; amount, qty+unit optional, date, data_origin, optional `input_application_id`), `harvest_records` (qty kg, grade, date), `revenues` (sale qty, price/unit, buyer optional), `budgets` (cycle × category planned amount), `scenarios` (P2, saved what-if inputs).
- **Pure calculators:** total and per-category cost; cost per acre/ha; revenue; gross margin = revenue − variable costs; net profit = revenue − all costs (incl. allocated farm-level overhead by area share, rule shown); break-even yield = total cost / price; break-even price = total cost / yield; budget variance; what-if (price ±, yield ±, input cost ±).
- Every output is labelled **estimate** with its assumptions. No yield or income improvement claims.

## 8. Agentic AI: one orchestrator, many tools, a few profiles

### 8.1 Components
```
Trigger (user request | schedule | domain event)
  → Orchestrator: picks AgentProfile, builds context from authorized records only
  → Planner: DeterministicWorkflow (default, LLM-free) | LLMPlanner (optional, bounded steps/tokens)
  → ToolExecutor: authz → validate input → call service → validate output → evidence
       ├─ read/compute tool → result recorded
       └─ write tool → ApprovalRequest (preview + args hash), run pauses (awaiting_approval)
  → Approval (user) → re-authorize, re-validate, execute stored args exactly → audit
  → Responder: template (LLM off) or LLM wording over tool outputs, with evidence refs
```

### 8.2 Tool contract (registry)
`name, version, description, input_model, output_model, scope (read|compute|propose|write), roles, consequential: bool, idempotent: bool, timeout, retry_policy`. Tools are thin wrappers over **existing services**, so agents can never do anything the UI cannot.

### 8.3 Agent profile
`name, purpose, allowed_tools[], approval_policy, max_steps, workflows[], explanation_template`. The eight requested "agents" become **profiles** over one registry and one executor, not eight chatbots.

### 8.4 Controls
Allow-list per profile × role. Writes always need approval (FR9). LLM output is untrusted: it is parsed into a tool call and validated, never written to the DB directly. Retrieved text is data, not instructions. Dose filter on every output. One retry on transient tool error, then `failed` with "nothing was changed". Tool results are never synthesized.
Audit: `agent_runs` (trigger, profile, user, status) and `tool_invocations` (args, result digest, duration, error, approval id), plus `audit_events` for each commit.

### 8.5 Run status
`planning | running | awaiting_approval | completed | failed | cancelled | expired`. Approvals expire (for example after 72 h) and must be re-proposed with fresh data.

### 8.6 Profiles: what is real in the FYP

| Profile | Tools | FYP status |
|---|---|---|
| Irrigation Planning | read cycle/field, weather.get, fao56.calc, water_balance, irrigation_plan.propose(write) | **Implement first** (no model needed) |
| Crop Health Assistant | case.get, inference.status, knowledge.ask, expert.escalate(write) | **Implement** (P0); full path after model freeze |
| Weather & Risk | weather.get, risk.evaluate, notification.create(opt-in) | Implement as a workflow (cheap) |
| Farm Finance | economics.summary, budget.variance (read only) | Implement as a workflow (cheap, read-only) |
| Knowledge | knowledge.ask (verifier) | A tool used by the others, plus `/ask` |
| Soil, Nutrient, Farm Management | soil.interpret, fertilizer.calc, cycle/task tools | Tool specs only, **Proposed** |

### 8.7 Automation workflows (all in-app only; no SMS/email/push; external notifier = interface only, disabled)

| Workflow | Trigger | Writes | Approval |
|---|---|---|---|
| Daily farm summary | cron 06:00 PKT, opt-in | own notification | Opt-in subscription is the authorization |
| Weather risk alert | `weather.updated` event | own notification | opt-in |
| Irrigation recommendation | daily / on demand | irrigation_plan (proposed) | **Yes** to save |
| Crop inspection reminder | stage change / N days since last case | reminder | **Yes** |
| Planting / harvest reminder | cycle stage template (cited lengths) | reminder | **Yes** |
| Fertilizer schedule | stage + cited table | fertilizer_plan | **Yes**; refuses without source |
| Expense capture | user message → draft expense | expense | **Yes** |
| Harvest profitability summary | `harvest.recorded` | none (read) | No |
| Input inventory warning | stock below threshold | notification | P2 (needs inventory ledger) |

## 9. RAG and verified knowledge
Source register (`knowledge_documents`: title, publisher, year, url/doi, access date, **licence required**, crop/topic/language, review_status). Ingestion job: section chunking → multilingual embeddings (local) → pgvector HNSW + `tsvector('simple')` (Urdu has no stemmer). Retrieval: structured filter (crop/stage/topic) → hybrid (vector + keyword, reciprocal-rank fusion) → optional rerank → generation restricted to retrieved passages (or extractive template when LLM is off) → **verifier** (each claim maps to a citation; no dose without a reference-table source) → answer or `no_verified_guidance`. Evaluation: S1/S2/S3 on a 40–60 question set (AI_ML_RESEARCH_PLAN). The same register backs the cited reference tables used by the calculators.

## 10. Essential FYP vs future commercial

| Essential (FYP, ship to production bar) | Important if on schedule (P1) | Future / commercial (architecture hooks only) |
|---|---|---|
| Auth + RBAC + audit; farm/field/cycle/activities | Weather adapter + risk indicators | Real IoT, irrigation controllers, drones |
| Crop Doctor: upload → model → calibrated decision → Grad-CAM, 4 states | Economics (expenses, harvest, sales, budgets, summary, what-if) | SMS/WhatsApp/push notifications |
| Independent CV model E1/E2/E5/E7, model card | Expert queue | Marketplace, prices, payments |
| Soil records + pH/EC flags | Offline drafts + sync | Multi-tenant orgs, billing, SSO |
| FAO-56 irrigation + fertilizer from cited tables | Irrigation agent + 2 workflows | All-crop coverage, Sindhi speech |
| Verified RAG + verifier + S1–S3 eval | EN/UR UI | Inventory ledger, scenario library, NDVI, knowledge graph (P2) |
| Agent framework + Crop Health Assistant, audited approvals | | Automated retraining |

## 11. Roadmap (Day 0 = 2026-11-22; Day 60 = 2027-01-21)
Two tracks. The **ML track** cannot slip its gates. The **software track** fills the dataset wait.

| Phase | Days (dates) | Software deliverable | ML track in parallel |
|---|---|---|---|
| P2 Platform core | 1–4 (Nov 23–26) | Compose DB, CI, kernel/units, identity/auth, audit, farms/fields/cycles API | Dataset audit, licences, pathway note → **G1 Nov 27** |
| P3 Crop Doctor intake + UI shell | 5–9 (Nov 27–Dec 1) | Login + farm screens, nav per DESIGN, case upload/storage/persistence, quality gate, model registry + availability | Clean, dedupe, group splits |
| P4 Calculators + references | 10–13 (Dec 2–5) | units, FAO-56 ET0/ETc/balance, fertilizer, economics, soil rules: pure + validated; reference tables + review | **Freeze splits Dec 7**, E1 |
| P5 Weather, soil, irrigation | 14–17 (Dec 6–9) | adapters + cache, soil module, risk indicators, irrigation plans + UI | E2 transfer |
| P6 Farm economics | 18–21 (Dec 10–13) | expenses, harvest, sales, budgets, summary, what-if + UI | E2, error analysis |
| P7 Agent framework | 22–27 (Dec 14–19) | registry, executor, approvals, audit, worker/scheduler; Irrigation profile; daily-summary + risk workflows | calibration, thresholds, Grad-CAM, E7 |
| P8 Model integration | 28–30 (Dec 20–22) | Predictor wired, Crop Health Assistant end to end | **G2 model freeze Dec 22** |
| P9 RAG | 31–38 (Dec 23–30) | sources, ingestion, retrieval, verifier, /ask, eval S1–S3 | model card, failure log |
| P10 Expert, tasks, offline, i18n | 39–46 (Dec 31–Jan 7) | expert queue, reminders/notifications, PWA drafts + sync, EN/UR | — |
| P11 Integration | 47–49 (Jan 8–10) | E2E, polish; **feature freeze Jan 10, G3 Jan 11** | — |
| Eval & report | 51–60 (Jan 12–21) | final tests, security, backups, report, demo | final test set once → **G4 Jan 17, G5 Jan 21** |

Honest risk: one developer running both tracks is the main threat. If behind at G2, cut in this order: what-if/scenarios, Finance and Risk workflows, offline sync beyond drafts, Urdu polish. Never cut evaluation, citations, access control or tests.

## 12. Testing, monitoring, deployment
- **Tests:** unit (calculators 95%), API (success, validation, auth, ownership for every endpoint), integration (upload → case → audit; agent → approval → commit), security (bad files, tokens, injection), contract snapshot, LLM-disabled suite, Playwright E2E later.
- **DB tests:** `@pytest.mark.db` against `TEST_DATABASE_URL` (Compose DB, per-test transaction rollback). When it is unset, the tests are **skipped and the count is reported**, never silently passed. No SQLite substitution (UUID/JSONB/pgvector fidelity).
- **Monitoring:** JSON logs (exists), admin metrics endpoint (latency, inference time, rejection rate, adapter failures), drift flag per model version.
- **Compose:** `db` (pgvector image, pinned tag, **host port 5433** to avoid the local PG18 on 5432, password from git-ignored root `.env`), `api`, `worker`, `frontend` (static + nginx proxy). Healthchecks, non-root.
- **CI:** backend (ruff, pytest with a Postgres service container), frontend (lint, tsc, vitest, build), pip-audit/npm audit (warn).

## 13. Git staging plan (NOT executed; awaiting approval)
1. Extend `.gitignore` (D3): `backup/`, `_cleanup_review/`, `data/`, `datasets/`, `ml/data/`, `ml/models/`, `ml/reports/**/checkpoints/`, `*.zip`, `*.tar.gz`, `*.safetensors`, `*.ckpt`, `*.pkl`, `*.joblib`, `*.npy`, `.claude/settings.local.json`.
2. Verify: `git status --ignored --short` shows backup/, _cleanup_review/ and frontend/dist as ignored. `git ls-files --others --exclude-standard` lists only intended files. Grep the staged files for secrets (`password=`, `SECRET`, `postgresql://`).
3. Commits on branch `main` (rename from `master`, optional):
   - `chore: repository scaffolding`: .gitignore, .env.example, README.md, CLAUDE.md, AgriOS.code-workspace
   - `docs: project documentation and academic proposal`: docs/ (incl. the two PDFs, 4.7 MB; or keep the PDFs out if you prefer)
   - `feat(backend): Phase 1 foundation`: backend/ (incl. uv.lock; excludes .venv, caches)
   - `feat(frontend): Phase 1 shell`: frontend/ (incl. package-lock.json; excludes node_modules, dist)
4. No push until a remote is chosen (none is configured).

## 14. Recommended next phase: Phase 2 "Platform core" (backend only, ~3–4 days)
**Why this first:** Crop Doctor persistence, calculators-with-plans, economics and agents all need `user → farm → field → crop_cycle` plus audit. Building upload first would mean redoing ownership later.

**Deliverables**
1. `docker-compose.yml` (db only), `.env.example` additions (`POSTGRES_*` names only, `TEST_DATABASE_URL`, `JWT_SECRET`), README steps.
2. `.github/workflows/ci.yml` (backend with Postgres service, frontend).
3. Fix D1, D2. Add `kernel/` (DataOrigin, Quantity) and `units/` (ha/acre exact; kanal/marla held as **unverified** definitions until a source is recorded).
4. Migration `0001`: users, refresh_tokens, audit_events, farms, fields, crop_definitions (names only, no Kc values), crop_cycles, activities.
5. Endpoints: `/auth/register|login|refresh|me`; CRUD `/farms`, `/fields`, `/crop-cycles`, `/activities` with cursor pagination.
6. Audit event on every write; OpenAPI snapshot test.

**Acceptance tests (measurable)**
- Migration up → down → up on an empty DB (CI).
- Auth: register, duplicate email 409, wrong password 401, expired token 401, refresh rotation (old token rejected), login rate limit 429.
- Ownership: for each of 4 resources, another user's GET/PATCH/DELETE returns **404** (≥12 tests); expert/admin role matrix.
- Audit: each create/update/delete writes exactly one audit event (actor, action, entity, id), with no PII in meta.
- Units: acre↔ha round-trip within 1e-9; unverified units are rejected for computation with a clear error.
- Validation: negative area, future sowing date beyond a limit, unknown unit → 422 envelope.
- Coverage ≥ 90% on the new modules; ruff clean; CI green; existing 21 + 13 tests still pass.
- If the DB is unavailable on the dev machine: DB tests are reported as skipped, with the count, in PROGRESS.

**Your actions needed:** start Docker Desktop (or give a local PG role yourself via `.env`; never paste it to me), approve the `.gitignore` and staging plan, and approve the additive contract changes in §4.5 and §5.3.
**If Docker stays unavailable:** swap the order and run **Phase 4 (pure calculators)** first. It needs no DB and no dataset.

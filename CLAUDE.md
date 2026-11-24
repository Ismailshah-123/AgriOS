# CLAUDE.md — AgriOS permanent instructions
Summary: loaded every session. Rules, doc map, token discipline. Keep under 120 lines. Details live in the other files; open only what the task needs.

## Project
AgriOS: AI farm decision support for Pakistan (FYP, 1 dev, ~60 days, PKR 10-15k).
Core = CAAIE: crop image model (+ optional context), calibrated confidence, OOD rejection, Grad-CAM/SHAP, expert escalation.
Stack: FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL15 (+pgvector), PyTorch, React+TS+Vite+Tailwind+shadcn, PWA (IndexedDB), EN/UR, Docker Compose, GitHub Actions.
Modular monolith. Core engine and calculators NEVER depend on an LLM.

## Session loop (always)
1. Read `PROGRESS.md` top section only (Current state, Next tasks).
2. Open only the docs in the map below that match the task.
3. One module per session. Write tests first or together. Run them.
4. Finish: update `PROGRESS.md` (max 10 lines), commit with clear message.

## Doc map (read on demand)
| Task | Read |
|---|---|
| UI, screens, i18n | DESIGN.md |
| Structure, modules, adapters | ARCHITECTURE.md |
| What/why/acceptance | PRODUCT_REQUIREMENTS.md |
| Tables, migrations | DATABASE_DESIGN.md |
| Endpoints, schemas | API_CONTRACTS.md |
| Models, experiments, RAG eval | AI_ML_RESEARCH_PLAN.md |
| Datasets, consent, retention | DATA_GOVERNANCE.md |
| Auth, uploads, agents, AI safety | SECURITY.md |
| Tests, quality gates | TESTING_QA.md |
| What to build next | IMPLEMENTATION_PLAN.md |
| Docker, CI, backups, demo host | DEPLOYMENT_OPERATIONS.md |
| Token/work rules, prompts | CLAUDE_WORKFLOW.md |
| Status, results | PROGRESS.md |

## Hard rules (never break)
1. Never invent results, accuracy, statistics, references, farmer feedback. Result tables stay PENDING until a saved run file exists.
2. No LLM-generated pesticide/fertilizer dose. Doses only from stored, cited, reviewed tables; else refuse + escalate.
3. Label data origin everywhere: measured | farmer_entered | retrieved | inferred | simulated. Show units.
4. Never fill missing data with made-up values. Use availability mask.
5. No multimodal-improvement claim without valid paired data (Pathway A). Default assumption: Pathway B.
6. Low confidence = no definitive diagnosis; ask for photo, show shortlist, escalate to expert.
7. Sensors/drones are simulated (`is_simulated` flag + visible label).
8. LLM API is an integration, not our model. System must run with LLM adapter disabled.
9. Every write by agent or expert creates an audit event. Agents: allow-listed tools, approval gate for writes.
10. Test set opened once. Splits frozen Day 15. Model frozen Day 30. Features frozen Day 49.
11. Never commit secrets, data, model files, `.env`.
12. Feature status labels only: Proposed | Implemented | Evaluated | Future. Track in `docs/FEATURE_STATUS.md`.

## Resolved doc conflicts (follow these)
- P0 agent = Crop Health Assistant. Irrigation Planning Agent = P1.
- Early stopping on validation macro F1.
- Feature freeze Day 49, gate G3 Day 50.
- Supported vision crop: tomato first; wheat only if audit passes; cotton calculators only.

## Token discipline (summary; full rules in CLAUDE_WORKFLOW.md)
- Grep/Glob before Read. Read line ranges, not whole files. Never re-read a file you just edited.
- Pipe long output through `head`/`tail`. No full test logs; show failures only.
- Use Explore subagent for broad searches. `/clear` between modules, `/compact` at ~60% context.
- Terse replies: result in 1-3 sentences. No restating the task, no plan recaps.
- Edit with diffs (Edit tool), not full-file rewrites. Keep every source file under ~300 lines.

## Production bar (applies to everything shipped)
Ambition = production-grade engineering on a scoped core, not more features. Ship P0+P1 to this bar before touching P2/P3.
- Typed, linted, tested code; CI green; no TODO in merged code.
- Migrations reversible; seed + one-command start; health/ready endpoints.
- Security checklist passed; secrets out of Git; ownership + approval paths 100% tested.
- Observability: structured logs, audit events, model monitoring.
- Backups restored once; rollback tested; demo video recorded.
- Docs match code (FEATURE_STATUS honest). Unfinished = labelled Proposed/Future, never faked.
Beyond-FYP items (real IoT, drones, marketplace) stay as documented architecture hooks, not claims.

## Definition of done (any feature)
Works from UI. Automatic test covers it. Errors shown clearly. Origin + units visible. Recorded in FEATURE_STATUS and PROGRESS.

## Commands (all verified 2026-11-23; Windows guide: docs/13-user-guides/WINDOWS_LOCAL_SETUP.md)
- Env check / DB init (safe, repeatable): `scripts\dev\check-environment.ps1`, `scripts\dev\init-database.ps1` (`-LocalCluster` = project-local PG on :54330)
- Start / status / stop: `scripts\dev\start.ps1` (API :8000 + worker + web :5173; `-ApiPort/-WebPort`), `status.ps1`, `stop.ps1` (only its own processes)
- Backend tests: `scripts\dev\test-backend.ps1` (isolated test cluster :54329; never DATABASE_URL)
- Backend lint: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Migrations only: `cd backend && uv run python scripts/init_db.py` (`--check` = read-only)
- Worker: `cd backend && uv run python -m app.jobs.worker`
- Frontend tests: `cd frontend && npm test -- --run`
- Frontend lint/types/build: `cd frontend && npm run lint && npx tsc -b && npm run build`
- E2E: `cd frontend && npx playwright test` (isolated stack, local Edge); `E2E_BASE_URL=<web url>` = against a running app
- Never: use port 54329 / `*_test` DBs for the app; print or commit backend/.env; kill processes start.ps1 did not start.

# PROJECT_STRUCTURE.md — repository layout (verified 2026-11-23)
Only directories that contain real files are described as "active". Nothing was moved in Phase 3.7: the working layout already matches the modular-monolith design, and moving code would only risk breaking imports, tests and CI.

## Active directories
```
AgriOS/
├─ .github/workflows/ci.yml   CI: backend (ruff, pytest on Postgres service), frontend (lint, tsc, vitest, build)
├─ .vscode/                   settings, tasks, debug configs, recommended extensions (single source of truth)
├─ AgriOS.code-workspace      opens the repo as one folder; config lives in .vscode/
├─ docker-compose.yml         optional PostgreSQL (db, db_test); not required on Windows
├─ scripts/dev/               Windows PowerShell workflow: check-environment, init-database, start, stop, status, test-backend
├─ backend/                   FastAPI modular monolith
│  ├─ app/
│  │  ├─ api/                 versioned router + health/ready
│  │  ├─ core/                config (anchored to backend/.env), errors, logging, security, pagination, rate limit, body limit
│  │  ├─ db/                  declarative base, session (engine from injected settings), model registry for Alembic
│  │  ├─ kernel/ units/       shared value types (data origin) and exact unit conversions
│  │  ├─ identity/ audit/     users, auth, roles; append-only audit log
│  │  ├─ farms/ dashboard/    farms, fields, crop registry, crop cycles; overview aggregate
│  │  ├─ crop_health/         Crop Doctor: cases, submissions, images, analysis handler
│  │  ├─ jobs/ mlops/ storage/ DB job queue + worker; model registry + predictor contract; private storage + signed links
│  ├─ alembic/versions/       0001 -> ... -> 0010 (single head)
│  ├─ scripts/                init_db, env_file, local_db, test_db, pg_tools (all Python, cross-platform)
│  ├─ tests/{unit,api,db}/    pytest; db tests only on TEST_DATABASE_URL
│  └─ var/ (ignored)          dev/test PostgreSQL data, uploads, model files
├─ frontend/                  React + TypeScript + Vite
│  ├─ src/{app,components,features,services,styles,utils}
│  ├─ tests/ (Vitest)  e2e/ (Playwright)
├─ docs/                      requirements, architecture, database, API, ML, data governance, security, QA, deployment, guides, proposal PDFs, progress
├─ backup/  _cleanup_review/  preserved, git-ignored, never modified
└─ var/ (ignored)             dev-run state and logs from scripts/dev
```

## Placeholder (empty) directories — candidates for removal (approval needed)
113 empty directories from the original scaffold. Git ignores empty directories, so they have no functional effect, but several duplicate the real layout and mislead readers:
| Group | Examples | Why remove |
|---|---|---|
| Backend duplicates | `backend/app/{models,repositories,schemas,services,workers,integrations/*,modules/*}` (16 under modules) | Real code is organised per module (`identity/`, `farms/`, `crop_health/`, `jobs/`); these imply a different architecture |
| Backend tests | `backend/tests/{integration,security}` | Tests live in `unit/ api/ db/` |
| Root placeholders | `agents/*`, `knowledge/*`, `shared/*`, `tests/*`, `infrastructure/*`, `scripts/{data,development,maintenance,setup}` | Agent/RAG code belongs in `backend/app/<module>` (ARCHITECTURE.md); create real folders when a phase needs them |
| Frontend | `src/{assets,hooks,lib,store,types}`, `src/components/{charts,dashboard,forms}`, 10 empty `src/features/*`, `public/{images,models}` | Features are added as real modules ship |
| ML / research | `ml/**` (25), `research/*` (5) | Recreate with the dataset audit and training work (Phase 4/ML track); data and weights stay git-ignored |
| Docs | `docs/01-project-overview`, `docs/08-agentic-ai`, `docs/09-rag-knowledge` | Keep: they are documented doc areas awaiting content |

## Unused source files (approval needed to delete)
| File | Evidence | Replaced by |
|---|---|---|
| `frontend/src/components/layout/navigation.ts` | 0 imports in src, tests, e2e or docs | `frontend/src/app/modules.ts` |
| `frontend/src/features/crop-health/pages/CropDoctorDashboardPage.tsx` | 0 references | `CropDoctorPage.tsx` |

## Current layout after cleanup (2026-11-23)
Empty scaffold folders, `_cleanup_review/` (empty placeholders), build output and caches were deleted with the owner's approval; list in `var/cleanup_deleted_20261123.txt`. Folders are created again only when they get real content.
| Path | Contents |
|---|---|
| `backend/` | FastAPI modular monolith: `app/{identity,farms,crop_health,soil,weather,irrigation,agents,economics,nutrients,knowledge,mlops,jobs,audit,storage,...}`, `alembic/` (0001-0010), `tests/{unit,db,api}`, `scripts/` |
| `frontend/` | React + TS + Vite: `src/{app,components,features,services,utils,styles}`, `tests/`, `e2e/` |
| `ml/` | `agrios_ml/` (data, train, evaluate, package, ood), `experiments/configs/`, `reports/`, `tests/`, `cache/` (resized images, git-ignored), `runs` -> D:\AgriOS-data\ml-runs |
| `datasets/` | `raw/archives/` zip, `raw/agri_foundation_v1` -> D:, `manifests/`, `reports/` (data git-ignored) |
| `docs/` | numbered doc sets + FEATURE_STATUS.md |
| `scripts/dev/` | Windows dev workflow (env check, DB init, start/status/stop, tests) |
| `var/` | runtime logs, verification outputs (git-ignored); `backend/var/` holds the local Postgres clusters and uploads — never delete |
| `backup/` | one dated docs backup (kept on purpose) |

## Added 2026-11-24 (overnight + post-overnight)
| Path | Contents |
|---|---|
| `backend/app/economics/` | FR10 expenses, harvest/sales, calc (migration 0008) |
| `backend/app/crop_health/review*.py` | FR12 expert review (migration 0009) |
| `backend/app/nutrients/` | FR6 refusal + dose engine (empty reviewed registries) |
| `backend/app/knowledge/` | FR8 source register, licence gate, FTS search, stats (migration 0010) |
| `backend/app/dashboard/{intelligence,analytics}.py` | overview module status; `/analytics` aggregates |
| `backend/scripts/{backup_db,set_role}.py` | pg_dump backup; audited role change |
| `frontend/src/components/charts/` | BarList, ColumnChart (no chart dependency) |
| `frontend/src/features/{economics,review,nutrients,knowledge,irrigation,offline,voice}/` | new pages / offline drafts / browser voice |
| `frontend/src/i18n/` | EN/UR catalogue + RTL document language |
| `frontend/e2e/sprint.spec.ts` | e2e for economics, soil, offline IndexedDB, refusals |
| `ml/scripts/{train_supervised.ps1,compare_val.py}` | RAM-supervised training; validation comparison from saved files |
| `ml/reports/{E2_*/val,E2_VALIDATION_COMPARISON.md}` | validation-only reports (no test data) |

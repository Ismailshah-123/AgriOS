# AgriOS

AI-powered smart agriculture and precision farm management platform.

## Technology
- Frontend: React, TypeScript, Vite
- Backend: FastAPI, Python
- Database: PostgreSQL
- AI/ML: PyTorch, scikit-learn, OpenCV
- Agentic AI and RAG: modular, provider-independent architecture

## Project status
Working FYP prototype (not production-validated). Current state, test results and limitations:
docs/15-progress/PROGRESS.md and docs/15-progress/FINALIZATION_AND_PRESENTATION_READINESS.md.
Feature labels (Proposed | Implemented | Evaluated | Future): docs/FEATURE_STATUS.md.

## Deployment
Render Blueprint (free plan): `render.yaml`; steps, limits and the model-package option in
docs/12-deployment/RENDER_DEPLOYMENT.md.

## Important
Do not commit raw datasets, secrets, private credentials or large model artifacts.

## Quick start (Windows, PowerShell, from the repo root)
Full guide with both database options and troubleshooting: **docs/13-user-guides/WINDOWS_LOCAL_SETUP.md**.
Requirements: [uv](https://docs.astral.sh/uv/), Node.js 24, PostgreSQL 15+ binaries. Docker is optional.

```powershell
cd backend; uv sync; cd ..; cd frontend; npm ci; cd ..
powershell -ExecutionPolicy Bypass -File scripts\dev\check-environment.ps1
# One time, pick ONE database option (see the guide):
#   A) your PostgreSQL: create role/db, put DATABASE_URL in backend\.env, then:
powershell -ExecutionPolicy Bypass -File scripts\dev\init-database.ps1
#   B) or a project-local database created for you:
powershell -ExecutionPolicy Bypass -File scripts\dev\init-database.ps1 -LocalCluster
# Every day:
powershell -ExecutionPolicy Bypass -File scripts\dev\start.ps1    # http://localhost:5173
powershell -ExecutionPolicy Bypass -File scripts\dev\stop.ps1
```
Then open the web app and **create an account** (there are no default accounts). In VS Code the same actions are tasks named "AgriOS: ...".

## Manual commands (any OS)
```bash
cd backend && uv run python scripts/init_db.py        # safe, repeatable migrations + checks
cd backend && uv run uvicorn app.main:app --port 8000 # API (docs at /api/v1/docs)
cd backend && uv run python -m app.jobs.worker        # background analysis worker
cd frontend && npm run dev                            # web app, proxies /api to :8000
```
Optional Docker database: `docker compose up -d db` (needs POSTGRES_PASSWORD in a root .env; not tested on the
development machine, where Docker is not installed).

### Tests
Database tests run only against an **isolated** database named `*test*` (`TEST_DATABASE_URL`);
without it they are reported as skipped, never redirected elsewhere.
```bash
powershell -ExecutionPolicy Bypass -File scripts\dev\test-backend.ps1     # Windows: starts the test cluster
cd backend && uv run python scripts/test_db.py start                     # other OS: then
TEST_DATABASE_URL="$(uv run python scripts/test_db.py url)" uv run pytest -W error
cd frontend && npm test -- --run && npm run lint && npx tsc -b && npm run build
cd frontend && npx playwright test                                       # browser tests (Edge)
# live-only specs (running app, real model, indexed library; photo = a genuine tomato leaf):
E2E_BASE_URL=http://localhost:5173 E2E_TOMATO_IMAGE=<photo.jpg> npx playwright test crop-doctor-model knowledge
```

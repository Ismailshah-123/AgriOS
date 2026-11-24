# LOCAL_ENVIRONMENT_AUDIT.md — Phase 3.7 audit (2026-11-23)
Method: commands were run on the developer machine; every finding below has evidence. Secrets were never printed (environment files were inspected by variable *name* only).

## Reproduction of the reported error
```
GET  /api/v1/ready       -> 503 {"status":"not_ready","checks":{"database":"not_configured"}}
POST /api/v1/auth/login  -> 503 {"error":{"code":"database_unavailable","message":"The database is not configured."}}
```
Same result directly on :8000 and through the Vite proxy on :5173.

## Root cause (traced, not guessed)
Login form -> `authApi.login` -> `POST /api/v1/auth/login` -> `get_db` -> `Database.session()` -> `Database(settings)` built with `settings.database_url = None` -> `AppError("database_unavailable", 503)`.
`database_url` was None because **no environment file exists** (`backend/.env`, root `.env`, `frontend/.env*` all missing) and `DATABASE_URL` is not set in the process environment. PostgreSQL itself is healthy (127.0.0.1:5432 accepting connections).

## Findings
| # | Severity | Finding | Evidence | Resolution (3.7.x) |
|---|---|---|---|---|
| F1 | Critical | Backend runs with no DATABASE_URL -> every DB endpoint 503 | reproduction above | 3.7.2: guided env setup + `init-database` |
| F2 | Critical | JWT_SECRET unset -> after F1, login would fail with `auth_not_configured` | no env file; config requires it for auth | 3.7.2: setup generates a random secret into the git-ignored `backend/.env` |
| F3 | High | `.env` is resolved from the *current directory*: starting uvicorn from the repo root silently ignores `backend/.env` | `SettingsConfigDict(env_file=".env")` | 3.7.2: anchor to `backend/.env` |
| F4 | High | No database initialization command; README says "edit values" but never how to create the role/database or run migrations safely | README, scripts/ empty | 3.7.2/3.7.4 |
| F5 | High | No safeguard against pointing the app at the test cluster (port 54329 / `*_test` databases) | config has no check | 3.7.2: init refuses test targets; app warns |
| F6 | High | No one-command start/stop/status on Windows; worker must be started separately and is undocumented in README | scripts/ empty | 3.7.4 |
| F7 | Medium | "Not configured" error text gives no hint how to fix it | message text | 3.7.2: point to `backend/.env` / setup guide (no secret details) |
| F8 | Medium | 113 empty scaffold directories; several duplicate real modules: `backend/app/{modules/*,models,repositories,schemas,services,workers,integrations}` vs real `identity/ farms/ crop_health/ jobs/ storage/ mlops/`; root `agents/ knowledge/* shared/ tests/ infrastructure/* scripts/*` empty; frontend `src/{hooks,lib,store,types,assets}` and 10 empty `features/*` | `find -type d -empty` | Reported in PROJECT_STRUCTURE.md; removal needs approval (git ignores empty dirs, so no functional impact) |
| F9 | Medium | Unused source files: `frontend/src/components/layout/navigation.ts` (superseded by `src/app/modules.ts`) and `frontend/src/features/crop-health/pages/CropDoctorDashboardPage.tsx` (superseded by `CropDoctorPage.tsx`) | 0 references in src/tests/e2e/docs | Safe to delete; awaiting approval |
| F10 | Medium | `.vscode/` empty; workspace file has no tasks, interpreter or debug config | ls | 3.7.3 |
| F11 | Low | `docs/01-project-overview`, `docs/08-agentic-ai`, `docs/09-rag-knowledge` are empty though referenced as doc areas | find | Reported; content belongs to later phases |
| F12 | Low | `frontend/dist/{images,models}` empty build leftovers | find | dist/ is git-ignored and regenerated |

## Verified OK
- Alembic chain linear `0001 -> 0002 -> 0003`, single head `0003`; models registered; drift test passes.
- App and Alembic read the same `DATABASE_URL` setting (Alembic only overrides it when the test harness passes a URL explicitly).
- Tests never use `DATABASE_URL`: they require `TEST_DATABASE_URL` whose name contains "test" and refuse if it equals `DATABASE_URL`.
- Frontend login handles the backend's actual response (`access_token`, `user`) and error envelope (covered by tests).
- Test cluster (54329, trust auth on loopback) is separate from the developer's PostgreSQL 18 (5432).

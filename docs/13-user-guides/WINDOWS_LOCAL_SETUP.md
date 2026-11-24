# WINDOWS_LOCAL_SETUP.md — run AgriOS on a Windows machine
Every command here was run on Windows 11 / PowerShell 5.1 during Phase 3.7 (2026-11-23). Run them from the repository root in PowerShell unless stated otherwise.

## 1. Prerequisites
| Tool | Check | Notes |
|---|---|---|
| uv (Python 3.12 is installed by uv) | `uv --version` | https://docs.astral.sh/uv/ |
| Node.js 24 + npm | `node --version` | |
| PostgreSQL 15+ server binaries | `C:\Program Files\PostgreSQL\<ver>\bin` | Needed for the database and the test suite. Docker is **not** required. |
| Git | `git --version` | |
| Microsoft Edge | installed with Windows | Used by the browser tests |

Install project dependencies once:
```powershell
cd backend; uv sync; cd ..
cd frontend; npm ci; cd ..
```
If PowerShell blocks scripts, run them as `powershell -ExecutionPolicy Bypass -File <script>` (all examples below work that way), or use the VS Code tasks ("AgriOS: ...").

## 2. Check the environment
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\check-environment.ps1
```
It lists missing tools, dependencies and settings by **name** only (secret values are never printed).

## 3. Configure `backend\.env`
`init-database.ps1` creates `backend\.env` if it is missing, with a random `JWT_SECRET` and safe development defaults. It never overwrites a value you have set. The file is git-ignored. All options are listed in `.env.example`.

## 4. Choose the database (one time)
**Option A: your existing PostgreSQL** (e.g. the PostgreSQL 18 service on port 5432). In a terminal, as a PostgreSQL superuser (you type your own password; AgriOS never needs it):
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -U postgres -d postgres
```
```sql
CREATE ROLE agrios LOGIN;
\password agrios
CREATE DATABASE agrios OWNER agrios;
\q
```
Then add one line to `backend\.env` (use the password you chose):
```
DATABASE_URL=postgresql+psycopg://agrios:<your-password>@127.0.0.1:5432/agrios
```
**Option B: a project-local database** (no password from you; nothing else on your machine is touched):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\init-database.ps1 -LocalCluster
```
This creates PostgreSQL data under `backend\var\dev-postgres` (git-ignored), listening on 127.0.0.1:54330 with a random password stored only in `backend\.env`.

Do **not** use port 54329 or a database whose name contains "test": that is the throwaway test cluster, and initialisation refuses it.

## 5. Initialise / migrate the database (safe to repeat)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\init-database.ps1
```
Expected ending: `OK: revision 0003 (head), 13 required tables present.` It only applies pending migrations; it never drops or resets data. Exit codes: 2 not configured, 3 refused test target, 4 cannot connect/authenticate, 5 database missing, 6 migration failed, 7 tables missing.

## 6-7. Start, check, stop
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\start.ps1     # API :8000, worker, web :5173
powershell -ExecutionPolicy Bypass -File scripts\dev\status.ps1
powershell -ExecutionPolicy Bypass -File scripts\dev\stop.ps1      # only what start.ps1 started
```
If 8000/5173 are busy, `start.ps1` refuses (it never kills other processes); use other ports:
`scripts\dev\start.ps1 -ApiPort 8010 -WebPort 5180`. Logs: `var\dev-run\logs\`. `stop.ps1 -Database` also stops the project-local database (Option B).

## 8. Register and sign in
Open the web URL printed by `start.ps1`, choose **Create an account** (password at least 10 characters). There are no default or demo accounts. Public registration always creates a farmer.

## 9. Tests
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\test-backend.ps1   # isolated test cluster, never your data
cd frontend; npm test -- --run; npm run lint; npx tsc -b; npm run build
npx playwright test                       # browser tests on an isolated stack (Edge)
$env:E2E_BASE_URL="http://localhost:5180"; npx playwright test   # against your running app
```
The browser suite registers about 13 users; against your running app start it with a higher limit for that session: `$env:REGISTER_LIMIT_PER_HOUR="200"` before `start.ps1` (default 10 per hour per IP).

## 10. Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| Login says "The database is not configured" | `DATABASE_URL` missing in `backend\.env` | Steps 4-5 |
| `/api/v1/ready` 503 `unavailable` | PostgreSQL not running / wrong host or port | `status.ps1`; start the PostgreSQL service or `init-database.ps1` (Option B) |
| init exit 4 "Authentication failed" | wrong password in `DATABASE_URL` | fix `backend\.env` |
| init exit 5 "does not exist" | database not created | Step 4 |
| "Authentication is not configured" | `JWT_SECRET` missing/short | `init-database.ps1` adds one |
| Crop Doctor stays "Waiting for analysis" | worker not running | use `start.ps1` (starts it) or `cd backend; uv run python -m app.jobs.worker` |
| "Too many attempts" on register | rate limit (10/hour per IP) | wait, or raise `REGISTER_LIMIT_PER_HOUR` for local testing only |
| Port already in use | another program on 8000/5173 | `start.ps1 -ApiPort ... -WebPort ...` |

# DEPLOYMENT_OPERATIONS.md — Docker, CI/CD, monitoring, backups, demo
Summary: how the system runs locally and on a free/low-cost host, how it is released, observed and recovered.

## Environments
- local: Docker Compose (api, db, worker optional, frontend dev).
- demo: Docker Compose host (free/low-cost tier or local laptop) + static frontend build; reverse proxy with TLS.
- hosted demo (chosen 2026-11-25): Render free plan from `render.yaml` (static site proxies `/api/*` to the API; embedded worker; migrations on start). See RENDER_DEPLOYMENT.md.
- Training: Colab/Kaggle only; artifacts copied after evaluation.

## Compose services
`api` (FastAPI + model volume), `db` (postgres15 + pgvector, volume), `worker` (optional: inference/reports), `proxy` (TLS), `frontend` (static build). Healthchecks on api and db. Non-root users. Pinned image tags.

## Config
`.env.example` documents: DB_URL, JWT_SECRET, LLM_PROVIDER/KEY (optional), WEATHER_API settings, STORAGE_PATH, MODEL_PATH, ALLOWED_ORIGINS, LOG_LEVEL. `LLM_ENABLED=false` must work.

## CI/CD (GitHub Actions)
On push: lint, tests, build. On tag: build images, run migration check, publish artifact. Deploy = pull images + `alembic upgrade head` + restart. Rollback = previous tag + `alembic downgrade` if needed.

## Model deployment
Model file not in Git. Download note + sha256 in `/ml/MODELS.md`. Startup verifies checksum and loads only the `active` registry version.

## Monitoring
Structured JSON logs (no PII). `/health` and `/ready`. Track: latency per endpoint, inference time, rejection rate, confidence distribution, expert disagreement, LLM/weather failures. Drift flag when confidence or rejection moves beyond set tolerance (documented). Simple admin page; Grafana not required.

## Backups
Nightly `pg_dump` + image volume copy, encrypted, kept off-host. Restore tested once before demo and timed. Runbook in `/docs/runbook.md`.

## Demo reliability
Local copy of full stack on laptop. Recorded backup video. Seed data loaded. Weather/LLM responses cached. Network-off demo rehearsed. Free hosting may fail: never depend on it alone.

## Production result checklist
[ ] one-command start (`docker compose up`)  [ ] fresh-clone README run works  [ ] migrations clean  [ ] HTTPS  [ ] backup+restore proven  [ ] health endpoints  [ ] CI green on main  [ ] demo seed script  [ ] rollback tested

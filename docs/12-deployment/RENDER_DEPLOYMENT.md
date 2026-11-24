# RENDER_DEPLOYMENT.md — demo deployment on Render (free plan)
Summary: how the AgriOS demo is deployed to Render from `render.yaml`, what the owner must do once, what works on the free plan and what does not. Status: **configuration prepared 2026-11-25; not yet applied** (needs the owner's Render login).

## Topology
| Render resource | Type | Purpose |
|---|---|---|
| `agrios-db` | PostgreSQL 15, free | Application database (internal connections only: `ipAllowList: []`) |
| `agrios-api` | Python web service, free | FastAPI + embedded job worker; migrations on every start |
| `agrios-web` | Static site | Built React app; rewrites `/api/*` to `agrios-api` (same-origin, so the SameSite=Strict refresh cookie keeps working) |

Region: Singapore (closest Render region to Pakistan).

## One-time setup (owner)
1. Render dashboard → **New → Blueprint** → connect GitHub → select `Ismailshah-123/AgriOS`, branch `main`. Render reads `render.yaml` and creates the three resources.
2. When prompted for unsynced variables, leave them **empty** unless you have them: `GROQ_API_KEY` (only with `LLM_PROVIDER=groq`; use a *rotated* key), `MODEL_PACKAGE_URL`, `MODEL_PACKAGE_SHA256`.
3. After the first deploy, check the two URLs Render assigned. If either is not exactly `https://agrios-api.onrender.com` / `https://agrios-web.onrender.com` (name already taken), edit `render.yaml` (rewrite destination) and the `ALLOWED_ORIGINS` env var of `agrios-api`, then redeploy.
4. Create the first admin: register in the web app, then in the `agrios-api` **Shell** tab: `.venv/bin/python scripts/set_role.py <email> admin`.

## Crop Doctor model on Render
Model files are never committed. To serve the real model:
1. Zip the registered package (on the dev PC): `Compress-Archive D:\AgriOS-data\packages\crop_doctor_tomato\1.0.0\* crop_doctor_tomato_1.0.0.zip` and `Get-FileHash crop_doctor_tomato_1.0.0.zip -Algorithm SHA256`.
2. Host the zip at an https URL you control (e.g. a GitHub Release asset) — an owner decision, since it publishes the weights.
3. Set `MODEL_PACKAGE_URL` and `MODEL_PACKAGE_SHA256` on `agrios-api`. On every start `scripts/fetch_model.py` downloads it, verifies the archive hash and the ONNX checksum in `package.json`, installs it, and registers + activates it once (audit events). Any failure → the API still starts and Crop Doctor reports `model_unavailable`.

## Free-plan limits (accepted for the demo; nothing switched to paid)
- `agrios-api` sleeps after ~15 min idle; the first request then takes ~1 min (cold start). Open the app a minute before a demo.
- 512 MB RAM: local embeddings are off (`EMBEDDING_PROVIDER=none`, lexical retrieval only).
- Ephemeral disk: **uploaded photos are lost on restart/redeploy** (database rows remain; images then show as missing). The model package is re-fetched on each start.
- Free PostgreSQL expires after the period Render states at creation (currently 30 days) and has 1 GB storage. Back it up with `pg_dump` before expiry if the data matters.
- The knowledge library starts **empty** on Render (source files are not in Git). Answers abstain until an admin imports licence-verified sources via Knowledge → Sources.
- No pgvector needed (full-text `tsvector` search only).

## Post-deploy checklist
`GET https://agrios-web.onrender.com/api/v1/health` (proxied) and `/api/v1/ready` → `ready`; `/api/v1/docs` loads; sign up / sign in; overview loads; create farm + field; Crop Doctor upload → prediction (model configured) or `model_unavailable`; knowledge question → cited answer or abstention; reload page → still signed in (refresh cookie); browser console free of errors.

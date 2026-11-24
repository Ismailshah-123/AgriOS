# PROGRESS.md — status, results, next tasks
Summary: the handoff file. Top section is read every session; keep it short. Update at end of each session (max 10 lines). Archive old entries to the Log section, summarise in batches.

## Current state
- Updated 2026-11-25 ~05:00. Resumed at the stalled Crop Doctor finalisation; report: docs/15-progress/FINALIZATION_AND_PRESENTATION_READINESS.md (section 0). First Git commit pushed to GitHub `main`.
- Crop Doctor model **registered + active**: crop_doctor_tomato 1.0.0 (E2 MobileNetV3, ONNX). Final eval ran once 2026-11-24 (test/external opened once): internal test macro-F1 0.991, **external field photos 0.350** (does not generalise). OOD unknown-crop rejection 0.925. No heatmap (head not GAP+linear; UI says so).
- Live (real UI + dev DB): upload -> real inference -> accepted / out-of-scope / unsupported crop shown honestly; GPS/EXIF stripped; persists; expert review 12/12; live_check 29/29.
- Tests 2026-11-25: BE 327/1 (+ parity 4/4 with package), ruff clean; FE 90/90, lint/tsc/build; ML 11/11; e2e isolated 17 passed/3 live-only skipped, live 3/3; npm audit 0, pip-audit 0. DB @ 0011 (head).
- Render: `render.yaml` + RENDER_DEPLOYMENT.md prepared; NOT deployed (needs owner's Render login).

## Next tasks
1. Owner: Render dashboard -> New -> Blueprint -> this repo (docs/12-deployment/RENDER_DEPLOYMENT.md); optionally host the model zip + set MODEL_PACKAGE_URL/SHA256; then run the post-deploy checklist
2. Owner: `cd backend; uv run python scripts/set_role.py <email> admin`; confirm source licences; rotate the Groq key
3. Owner decisions: E1 run, E3/E4/E6 (Pathway B), Pakistan sources/field photos, fertilizer table, Urdu review; then presentation

## Feature status
Authoritative list: docs/FEATURE_STATUS.md (this table is a summary).
| Feature | Status | Evidence |
|---|---|---|
| Farm management | Proposed | - |
| Crop Doctor model | Evaluated (offline; not field-validated) | ml/reports/MODEL_CARD.md |
| Multimodal fusion | Proposed (conditional) | - |
| Calibration + rejection | Evaluated (offline) | final/metrics.json, ood/ood_metrics.json |
| Irrigation/fertilizer calculators | Proposed | - |
| Verified RAG | Proposed | - |
| Crop Health Assistant agent | Proposed | - |
| Economics | Proposed | - |
| Expert review | Proposed | - |
| Offline PWA | Proposed | - |

## Results (fill only from saved run files)
| Exp | Macro F1 | Brier | ECE | Run file |
|---|---|---|---|---|
| E1 | PENDING | PENDING | PENDING | - |
| E2 (MobileNetV3, test / external) | 0.9909 / 0.3500 | 0.0137 / 0.8400 | 0.0042 / 0.2837 | ml/reports/E2_mobilenet_v3_large_tomato_v1/final/metrics.json |
| E3 | PENDING | n/a | PENDING | - |
| E4 | PENDING (A only) | PENDING | PENDING | - |
| E5 | PENDING | PENDING | PENDING | - |
| E7 | PENDING | n/a | PENDING | - |
| RAG S1/S2/S3 unsupported rate | PENDING | | | - |
| Agent approval compliance | PENDING | | | - |
| Calculator FAO 56 error (mm/day) | PENDING | | | - |
| Test pass rate | PENDING | | | - |

## Gates
G1 Day 5 [ ]  G2 Day 30 [ ]  G3 Day 50 [ ]  G4 Day 56 [ ]  G5 Day 60 [ ]

## Decisions
- 2026-11-22: P0 agent = Crop Health Assistant; Irrigation agent P1. Early stop on val macro F1. Freeze features Day 49.

## Log (newest first, one line per session)
- 2026-11-25 (resume): final eval had completed 11-24 but finalize script mis-read exit code (fixed) + relative log path (fixed); package/OOD/parity/register done; register_model FK import fix; crop_not_supported message, out-of-scope shortlist hidden, no-heatmap note; offline drafts query paused offline (fixed); stale e2e/voice tests updated; Render Blueprint + model fetch + DB URL driver fix. BE 327/1, FE 90, e2e 17+3.
- 2026-11-24 (finalization): migration 0011 + RAG v2 (ingestion pipeline, hybrid retrieval, grounded Groq generation w/ validation, Knowledge Ask/Sources/Analytics UI), 18 sources indexed, RAG eval runs, agent knowledge tool on real retrieval, SELECTION.md, finalize_crop_doctor.ps1 (RAM-gated), live_check.py 29/29. BE 310/1, FE 87, e2e 6/6.
- 2026-11-24 (post-overnight): MNv3 done + both E2 arms val-evaluated; /analytics + dashboard charts, economics/soil/agent/knowledge analytics, expert CAM, browser Urdu voice (mocked tests only), multi-crop audit (POST_OVERNIGHT_VERIFICATION.md). BE 290/1, FE 85.
- 2026-11-24 (overnight, checkpoint 00:34): MobileNetV3 E2 arm training under RAM supervisor (ml/scripts/train_supervised.ps1, owner-approved). FAO-56 Examples 24-26/28 tests found + fixed Eq. 66 off-by-one. Economics (0008) + expert review (0009) BE+FE; cycle-delete 500 -> 409; dev DB backed up (var/backups) then migrated 0007->0009. BE 278/1, FE 72, live 12/12. Matrix 55.05.
- 2026-11-23: Phase 5 audit + Phase C. Re-ran BE 252/1, FE 62 before changes. Found: static "Not connected" dashboard card (false), no soil edit/delete UI, Irrigation nav "planned" despite working ETc, agent history/catalogue unused, CAM stored but never exposed. Fixed all five (BE: dashboard/intelligence.py, crop_health/explanation.py; FE: IrrigationPage, ActionHistory, HeatmapPanel). BE 258/1, FE 67, live 14/14.
- 2026-11-23: Phase 3.6. E2E (Crop Doctor journey with real embedded worker, cross-user, disguised file, responsive, axe). Fixed: job queue mixed app/DB clocks (flaky claim; now DB clock only), register limit configurable (default 10/h), timeline labels. Pillow 12.3->13.0.0 (CVE-2026-128066). Docs: API_CONTRACTS Phase 3 section, STORAGE_AND_WORKER.md.
- 2026-11-23: Phase 3.3-3.5. Crop Doctor UI (overview, new assessment w/ XHR upload progress, history, detail, follow-up, retry). Worker + analysis handler: model_unavailable without predictions; failures roll back and retry; uncalibrated models never 'accepted'. 196/196 backend, 58/58 frontend.
- 2026-11-23: Phase 3.1-3.2. Migration 0003 (additive). Pillow intake pipeline, LocalFileStorage + signed links, body-size middleware, job queue (enqueue/claim/fail), model registry + Predictor contract (no loader shipped), crop_health API. Fixed: timeline ordering (DB vs app timestamps). 180/180.
- 2026-11-23: Phase 2.6. Playwright e2e on real API + isolated db in local Edge (8/8). Found+fixed: page overflow on phones from long names (global grid min-width rule), WCAG 2.5.3 label-in-name on account menu, visual polish (sidebar width, pill wrapping, 2-col stat tiles). pytest 8->9.2 (PYSEC-2026-1845). MODULE_CONTRACTS.md (Parts E/F design only).
- 2026-11-22: Phase 2.5. GET /overview (owner-scoped aggregate) + Overview UI (getting-started checklist, stat tiles, growing crops, upcoming dates labelled farmer_entered, recent changes, 'Not connected' intelligence panel). Fixed audit ordering: created_at now clock_timestamp() (now() = transaction start) - edited 0001 in place (never applied outside throwaway test DB).
- 2026-11-22: Phase 2.4. Frontend: tokens (warm neutral, AA-verified), Inter self-hosted, shadcn-style primitives (Radix dialog/menu), auth (memory token + cookie refresh), grouped nav from module registry, farms/fields/cycles pages, Crop Doctor preview, planned-module pages, settings, lazy routes. Fixed: post-login redirect lost destination; aria-controls on absent drawer; heading order. Notes: docs/03-architecture/DESIGN_NAVIGATION_NOTES.md.
- 2026-11-22: Phase 2.3. Migration 0002 (farms, fields, crop_definitions + 6 reference crop names, crop_cycles; RESTRICT deletes; CHECKs). Farms/fields/cycles/crops API, owner-scoped repository, cursor pagination, filters, audit. Caught + fixed a functional-index bug (lower('name') literal) before it shipped; regression test added. Verified 129/129 -W error.
- 2026-11-22: Phase 2.2. Migration 0001 (users, refresh_tokens, audit_events + append-only trigger). Auth API (register/login/refresh/logout/me, profile, password), Argon2id (pwdlib), PyJWT HS256, refresh rotation + reuse detection, httpOnly SameSite=Strict cookie, origin check, login rate limit (in-process), require_roles, audit service. Verified 65/65 -W error, 98% coverage.
- 2026-11-22: Phase 2.1. DB engine from injected settings; 503 database_unavailable (not 500); isolated test-DB harness + scripts/test_db.py; httpx->httpx2 (Starlette warning gone); alembic path_separator; JWT settings; .gitignore (backup, quarantine, data, weights); docker-compose (db, db_test); CI workflow; docs/FEATURE_STATUS.md created. Verified: 30/30 pytest -W error, ruff clean.
- 2026-11-22: Phase 1 re-verified (backend 21/21 pytest + ruff clean; frontend 13/13 Vitest, eslint, tsc). Architecture review vs proposal PDF written as draft: docs/03-architecture/ARCHITECTURE_ROADMAP_PROPOSAL.md (Proposed, awaiting approval). No code changed; nothing committed.
- 2026-11-22: Phase 1 foundation. FastAPI app factory, env config, error envelope, JSON logs, /health + /ready, Alembic scaffold (no tables). React/Vite/Tailwind v4 shell, API client, live status card, routing. Quarantine files were all 0 bytes; nothing restored, recreated fresh where needed.

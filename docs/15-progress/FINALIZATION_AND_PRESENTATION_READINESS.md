# Finalization and readiness report — 2026-11-24 (evening)
Summary: what is verified to work today, with evidence; what is blocked and the exact step that unblocks it. The presentation deck was deliberately **not** made (owner: "make presentation when everything is complete"). Section 0 = 2026-11-25 update (model finalised; first Git commit).

## 0. Update 2026-11-25 (resumed session) — supersedes sections 3, 4 and 8.1 where they differ
**Where work resumed.** The final evaluation had in fact run on 2026-11-24 21:59 (owner's one-time RAM exception, `ml/runs/RAM_EXCEPTION_20261124.md`) and written `final/metrics.json`, but `finalize_crop_doctor.ps1` logged it as failed: `Start-Process -PassThru` returns a null exit code unless the handle is cached. Fixed; the evaluation was **not** re-run (test sets opened once). Packaging/OOD then ran under the unchanged 8 GB gate (started at 8.31 GB). A second script bug (relative log path after `Push-Location`) and a `register_model.py` bug (audit FK metadata not loaded; it had never run against a real DB) were fixed; registration was dry-run (rolled back) before the real run.

**Crop Doctor model (Evaluated, offline only).** `crop_doctor_tomato` 1.0.0 = E2 MobileNetV3-Large, ONNX, registered and active (audit events). Preprocessing = training (resize 256 bicubic, crop 224, ImageNet mean/std, EXIF transpose); ONNX-Runtime CPU vs PyTorch golden logits match (atol 2e-3, 4/4).
| Set | n | Macro-F1 | Accuracy | ECE (calibrated) |
|---|---|---|---|---|
| Validation | 4,015 | 0.985 | 0.986 | 0.003 (in-sample) |
| Internal test (lab-style) | 4,011 | 0.991 | 0.992 | 0.004 |
| External field photos (PlantDoc + PlantWild) | 1,602 | **0.350** | 0.404 | 0.284 |
OOD (3,000 non-tomato leaves): energy AUROC 0.982, 92.5 % not accepted (potato 66 %); 4.6 % of in-distribution test images flagged out-of-scope. **The model does not generalise to field photos** — it is a lab-image classifier with honest rejection, not a field diagnostic. Heatmap: not provided by this model (MobileNetV3 head is not GAP+linear); the UI now says so instead of hiding it.

**Live end-to-end (real UI, dev DB, real model).** New Playwright spec `e2e/crop-doctor-model.spec.ts` (live only) + scripted expert check, all on train-split images (never test/external): PlantVillage early-blight photo -> *accepted*, Early blight 99.7 %, persists after reload; stored photo is WebP with no EXIF/GPS (upload carried a GPS tag); field-style PlantSeg late-blight photo -> *out of scope* (no diagnosis); wheat crop -> "installed model does not support this crop"; flat grey image -> no diagnosis; expert review request -> expert queue -> review -> farmer sees answer, model result unchanged, farmer 403 on queue (12/12; throwaway expert account demoted afterwards). Note: 3.5 % of a random 200 train images are flagged out-of-scope by design (95th-percentile threshold); one such image was hit first and is not a pipeline fault (original vs stored WebP identical).

**Defects found and fixed today.** (1) unsupported-crop cases said "No validated analysis model is installed" even with a model active; (2) out-of-scope results showed class percentages to farmers and seeded the assistant with them (now withheld; still stored for experts); (3) offline drafts list never loaded while offline (TanStack Query paused it; `networkMode: "always"`); (4) duplicate Urdu key broke `tsc -b`; (5) stale tests from the RAG v2 / Urdu UI changes (voice, knowledge refusal, knowledge skip guard).

**Tests (2026-11-25).** Backend 327 passed / 1 skipped (+ parity 4/4 with the package), ruff clean; frontend 90/90, eslint, tsc (app + e2e), build; ML 11/11; Playwright isolated 17 passed + 3 live-only skipped, live 3/3; `live_check.py` 29/29 (`var/live_check_20261125043959.json`); npm audit 0, pip-audit 0; DB at 0011 (head).

**Deployment.** `render.yaml` Blueprint + `docs/12-deployment/RENDER_DEPLOYMENT.md` prepared (free plan, Singapore). Not applied: needs the owner's Render login. Backend changes for hosting: psycopg driver pinned for `postgres://` URLs, opt-in API docs in production, opt-in checksum-verified model fetch at start (`scripts/fetch_model.py`).

## 1. Verified overall completion
Method: the weighted FYP_COMPLETION_MATRIX.md (100 points, acceptance criteria, planned work = 0). Changes today: row 12 (RAG) 30 → 75 % (V), row 5 (image model) 45 → 60 % (both E2 arms validation-evaluated, SELECTION.md), row 6 (calibration) 25 → 35 %.
| View | Completion |
|---|---|
| **Combined weighted** | **65.6 %** (was 59.95) |
| Software implementation (rows 1-3, 7, 9-20) | **70.9 %** |
| AI/ML core (dataset, model, calibration/OOD, explanation) | **56.4 %** |
| Strict verified-only | 31.7 % |
The project is above 50 % on every view except strict verified-only. When the Crop Doctor finalisation (section 4) runs, rows 3, 5, 6, 7, 8 can be re-scored from its run files.

## 2. Frontend / backend / database coverage (live, real dev DB)
`backend/scripts/live_check.py` → `var/live_check_20261124211357.json`: **29/29 passed** — auth, farms/fields (2.5 acre), crop cycle, ownership 404 (field + case), soil create/edit/delete/history with units, Open-Meteo forecast (fresh, attributed), FAO-56 ETc water demand, economics (profit 18,000.00 PKR = 30,000 − 12,000), fertilizer refusal, agent field report + approval-gated write rejected, Crop Doctor case → worker → `model_unavailable`, overview + analytics, knowledge stats, farm-context RAG answer using the user's own soil test, cross-user isolation, cited RAG answer.
Database: migration **0011** applied (additive, after verified backup `var/backups/agrios_20261124_201950.dump`, 24 table-data entries); 25 required tables; no data deleted. Restart persistence: the stack was restarted 6 times today; all records persisted.
Module-by-module detail: BACKEND_FRONTEND_COVERAGE_MATRIX.md (unchanged rows) + RAG matrix in docs/09-rag-knowledge/RAG_IMPLEMENTATION_STATUS.md.

## 3. Test results (all run 2026-11-24)
| Suite | Result |
|---|---|
| Backend pytest (isolated test cluster, `-W error`) | **310 passed, 1 skipped** (skip = ONNX parity test, needs a model package); ruff + format clean |
| Frontend Vitest (incl. axe) | **87/87** (one existing farms test flaked once under full-suite load, passed on re-run and in isolation); eslint, tsc, production build OK |
| ML pytest | 11/11 |
| Playwright (real Edge, live app) | 6/6: journey ×2, responsive 3 viewports + real-browser axe incl. contrast, Urdu RTL 360 px, knowledge journey (8 viewports 360–1920, no horizontal overflow) |
| Live smoke | 29/29 |
| RAG evaluation | run files in docs/09-rag-knowledge/eval/results (section 5) |

## 4. Crop Doctor — status and the one remaining blocker
- Trained: E2 EfficientNet-B0 (best epoch 5) and E2 MobileNetV3-Large (best epoch 14), same split. Validation macro-F1 (calibrated) 0.9873 vs 0.9853; CPU p50 14.0 vs 10.5 ms (ml/reports/E2_VALIDATION_COMPARISON.md). E1 custom CNN: not trained (no training today, per owner).
- **Selected (validation only, pre-registered rule): MobileNetV3-Large** — ml/reports/SELECTION.md, written before any test access. Test and external sets remain **unopened**.
- `onnx` installed in ml/.venv (runbook step 0 done).
- **Blocked: available RAM 5.1–6.1 GB < the owner's 8 GB rule** for ML jobs (browsers/VS Code open). Not overridden.
- Ready to run in one command: `ml\scripts\finalize_crop_doctor.ps1` (refuses < 8 GB or with the app running; watchdog; final evaluation once → ONNX package → OOD → parity test → register + activate).
- Until then the live system honestly returns `model_unavailable` ("No evaluated model has been activated") and offers expert escalation; no prediction is faked. Model-performance figures in the UI are therefore not shown yet.

## 5. Soil, weather, irrigation
Soil: CRUD + history + trends with units and methods; cited pH/ECe/salt-tolerance interpretation; missing parameters listed; no fertilizer advice (refusal). Weather: live Open-Meteo, cache/stale/unavailable states, attribution and licence note. Irrigation: FAO-56 Kc stage curve, ETc = Kc × ET0 from forecast ET0, worked examples 24–26 & 28 pass; effective rainfall and irrigation scheduling (net/gross depth) **not implemented** (disclosed on the page).

## 6. RAG and agentic AI
RAG (new today): hybrid retrieval over **18 licence-verified sources / 276 chunks** (Wikipedia CC BY-SA 4.0 + US EPA public domain; assistant-verified on the owner's instruction, owner to confirm; none expert-reviewed, none Pakistan-specific), grounded answers by Groq `openai/gpt-oss-120b` with citation/grounding/dose validation and quoted-passage fallback, abstention, follow-ups, Urdu/Roman Urdu, owner-scoped farm records, analytics. Dev-set (assistant-labelled) retrieval: hybrid hit@5 0.70 (0.74 with LLM rewrite), source-hit@5 0.96, MRR 0.49–0.52, 6/6 unanswerable abstained; generation 17/27 answered, 5 rejected as ungrounded, 4 declined, 1 rate-limited. Full detail: docs/09-rag-knowledge/*.
Agents: deterministic orchestrator (no LLM), allow-listed tools, approval gate for writes (live: pending → rejected), audit events; the knowledge tool now returns verified passages.

## 7. Responsive UI
Verified in real Edge at 360×800, 390×844, 430×932, 768×1024, 1024×768, 1280×800, 1440×900, 1920×1080 (knowledge page) and 360/768/1280 for all main routes: no horizontal overflow; axe (incl. contrast) clean; Urdu RTL shell mirrors at 360 px. Screenshots: frontend/test-results/screens/.

## 8. Remaining defects / limitations
1. Crop Doctor model not registered (RAM gate) — section 4.
2. Owner account is `farmer`: admin screens (source management, analytics) need `uv run python scripts/set_role.py <your email> admin` (the assistant was not permitted to change roles).
3. Knowledge library is general, not Pakistan-specific; licence decisions need owner confirmation; dev-set labels need review; no held-out RAG test set; groundedness check is lexical.
4. Groq free tier rate limits (HTTP 429) → automatic fallback model, then quoted passages. The Groq API key was pasted into a chat session: **rotate it after the demo**.
5. OCR for scanned PDFs and cross-encoder re-ranking not implemented. In-process rate limiter only.
6. Not done today (owner priorities): E1 baseline, E3/E4/E6 (Pathway B decision), heat-stress threshold, irrigation scheduling, Urdu string review, CI on a remote, Docker run, demo video, presentation.

## 9. Presentation readiness
Not started by instruction. Evidence for it exists: run files, screenshots, live check JSON, this report.

## 10. Local URLs and demo steps
- Web app http://localhost:5173 · API docs http://127.0.0.1:8000/api/v1/docs · health http://127.0.0.1:8000/api/v1/ready
- Start/stop/status: `scripts\dev\start.ps1` · `stop.ps1` · `status.ps1` (DB: project-local PostgreSQL :54330, started automatically)
- Demo: sign in → Overview (KPIs) → My Farms/Fields/Crop Cycles → Soil Intelligence (add a test, edit, history) → Weather → Smart Irrigation (ETc) → Farm Economics → AI Agents ("field report"; approve/reject a write) → Crop Doctor (upload → honest "model unavailable" until finalisation; then real prediction + heatmap) → Agricultural Knowledge: ask "Why are my tomato leaves developing yellow spots?", follow up "How does that disease spread?", ask in Urdu, open a cited source, ask "How much copper fungicide per acre?" (dose refused), ask "export price of mangoes" (abstains), ask "Summarise the soil test for my field" (own records).

# Phase 5 completion audit (verified 2026-11-23 23:30)
Summary: verified state of every module against code, tests, DB and artefacts; backend-to-frontend integration matrix; doc discrepancies; separate completion assessments; prioritized plan. Weighted totals stay in FYP_COMPLETION_MATRIX.md (unchanged by this audit).

## 1. Verification runs in this audit (re-run, not cited)
| Check | Result |
|---|---|
| Backend `scripts\dev\test-backend.ps1` | 252 passed, 1 skipped (ONNX package parity; no package exists) |
| Frontend `npm test -- --run` | 62/62 (10 files) |
| DB `init_db.py --check` (read-only) | `agrios` on 127.0.0.1:54330 (project-local PG 18.4), revision 0007 = head, 13 required tables |
| DB inspection | 24 FKs, 51 indexes, data persisted (users, farms, fields, cycles, soil, weather, agent runs/actions, audit) |
| Extensions available | pg_trgm, unaccent. **No pgvector** |
| Model registry | `model_versions` empty; `backend/var/models` absent; no package on disk |
| ML env | torch OK, sklearn OK, **onnx missing**, onnxruntime missing in ml (present in backend) |
| Runs on D: | only E2 EfficientNet-B0 seed42 (+ smoke run); no MobileNetV3, no E1, no eval reports |
| Resources at audit | 2.0 GB RAM free of 15.6 (VALORANT 2.1 GB, Chrome 3.0 GB, VS Code 2.7 GB); GPU 2.3/12 GB |
| Clusters listening | 5432 (system PG, not used by AgriOS), 54330 (dev), 54329 (test) |

## 2. Feature matrix (class per prompt: 1 tested · 2 untested · 3 partial · 4 BE only · 5 FE only · 6 integration incomplete · 7 not implemented · 8 blocked)
| Feature | BE | FE | DB | Tests | Class | Remaining | Evidence |
|---|---|---|---|---|---|---|---|
| Auth: register/login/refresh/logout/me/profile/password | Done | Done (login, register, settings) | 0001 | BE+FE+e2e | 1 | Expert-scoped access with FR12 | identity/, tests/db/test_auth_api.py |
| Farms/fields/crop cycles CRUD | Done | Done (list/detail/create/edit/delete) | 0002 | BE+FE+e2e | 1 | kanal/marla blocked (no official definition) | farms/, features/{farms,fields,crop-cycles} |
| Dashboard overview | Farm aggregate only | **Hardcoded "Not connected" card for weather/irrigation (false: both work)** | - | BE+FE | 6 | Real intelligence summary from DB | dashboard/router.py, features/dashboard/sections.tsx:177 |
| Crop Doctor intake/cases/worker/UI | Done | Done | 0003 | BE+FE+e2e (test-double predictor) | 3 | Real model; no diagnosis ever produced | crop_health/, features/crop-health |
| Crop Doctor explanation (CAM) | Computed + stored, **not exposed by API** | **Not rendered** | 0003 | none on real model | 4/8 | Endpoint + overlay; needs real model to verify | mlops/onnx_predictor.py |
| Model registry/ONNX serving | Done | Availability badge only | 0003 | unit; parity skipped | 2/8 | Package + register (blocked on training/eval) | mlops/, scripts/register_model.py |
| Soil observations | CRUD + summary + interpretation | List/create/summary; **no edit, no delete in UI** | 0005, 0007 | BE+FE | 6 | Edit + delete UI | soil/router.py, features/soil |
| Weather + risk indicators | Done (Open-Meteo, cache/stale) | Done | 0004 | BE+FE | 3 | Heat stress has no cited threshold (honestly "not evaluated") | weather/ |
| Irrigation ETc | Done (`/fields/{id}/water-demand`) | Card inside Weather page; **nav marks Irrigation "planned" and /irrigation shows a placeholder** | - | BE+FE; **no FAO-56 worked-example test** | 6 | Real /irrigation page; FAO-56 worked-example tests | irrigation/, app/modules.ts |
| Agents + approvals | Done (6 agents, 9 tools, catalogue) | Run, history, pending approvals; **no decided-action history, catalogue unused** | 0006 | BE+FE | 6 | Action history (approved/rejected/expired/executed) in UI | agents/router.py |
| Fertilizer FR6 | none | placeholder page | - | - | 7 (+8: no reviewed table) | Refusal path only until a reviewed table exists | - |
| RAG FR8 | none | placeholder page | - | - | 7 (+8: source licences need human review) | Sources, FTS retrieval, citations, eval | - |
| Economics FR10 (P1) | none | placeholder page | - | - | 7 | Deterministic expenses/harvest/margin | - |
| Expert queue FR12 (P1) | role only | none | - | - | 7 | Queue + corrected label | - |
| Offline PWA FR13 (P1) | - | none | - | - | 7 | SW + IndexedDB drafts | - |
| Urdu UI | - | option shown "being prepared" | - | - | 7 (+8: reviewed translations) | Strings + RTL | SettingsPage.tsx |
| Reports module | - | placeholder page | - | - | 7 | Not in FR list; keep Future | - |

## 3. Backend → frontend integration matrix (all 51 routes)
| Backend route(s) | FE service | FE page | Status |
|---|---|---|---|
| auth/*, users/me, users/me/password | platform.ts | Login, Register, Settings, UserMenu | OK |
| farms, fields, crop-cycles (CRUD), crops | platform.ts | Farms, FarmDetail, Fields, CropCycles | OK |
| overview | platform.ts | Overview | OK, but intelligence card static (gap) |
| cases (create/list/summary/detail/follow-ups/analysis/retry), files | cropHealth.ts | Crop Doctor pages | OK |
| models/availability | via cases/summary | Crop Doctor | OK (same data) |
| soil-observations GET/POST, soil-summary | intelligence.ts | Soil | OK |
| soil-observations PATCH, DELETE | DELETE in service only | none | **gap** |
| weather | intelligence.ts | Weather | OK |
| fields/{id}/water-demand | intelligence.ts | Weather (card) | OK; **/irrigation route is a placeholder** |
| agent runs (POST/GET/list), actions pending, approve, reject | agents.ts | Agents | OK |
| agent actions (non-pending), catalogue | partial | none | **gap** |
| health, ready | system.ts | Status card | OK |

## 4. Documentation discrepancies found
1. PROGRESS.md "Next tasks" and "Feature status" table are stale (Phase 2 items; everything "Proposed"). docs/FEATURE_STATUS.md is the accurate list.
2. PROJECT_STRUCTURE.md first block says migrations `0001 -> 0003`; actual 0001-0007 (later section correct).
3. PHASE5_IMPLEMENTATION_PLAN.md §1 says E2 "8 epochs"; run files show 10 epochs, best epoch 5.
4. `docs/09-rag-knowledge/` does not exist (removed in the approved cleanup); the prompt lists it.
5. MobileNetV3 config file is named `E3_…` but is the E2 comparison arm (proposal E3 = context-only tabular).
6. Unused files still present: `components/layout/navigation.ts`, `CropDoctorDashboardPage.tsx`.
7. modules.ts marks Irrigation "planned" although the ETc calculator is implemented and tested.

## 5. Blockers that code cannot remove
| Blocker | Affects | Needs |
|---|---|---|
| E3/E4/E6 are Pathway A (proposal + AI_ML_RESEARCH_PLAN): require paired image+context data; none exists | E3, E4, E6 | Owner decision: record as "not applicable (Pathway B)" with evidence, or a scenario-based E3 that makes no multimodal claim |
| RAM: 2 GB free while VALORANT/Chrome run; PC hung once during training | E1, E2-MobileNetV3, eval, OOD | Close games/browser before each training/eval run |
| `onnx` missing in ml venv | packaging → real Crop Doctor | `uv add onnx` (no training running) |
| No reviewed fertilizer table | FR6 doses | Reviewed, cited table (human) |
| RAG source licences | FR8 | Human licence check per document |
| Urdu translations | i18n | Human review of strings |
| No Git commits / remote; Docker absent | CI evidence, Compose | Owner decision on first commit/remote |

## 6. Separate completion assessments (verified, not weighted)
| Area | State |
|---|---|
| Backend | Auth, farms, crop health intake, soil, weather, irrigation, agents done + tested. Missing: explanation endpoint, intelligence overview, fertilizer refusal, RAG, economics, expert queue |
| Frontend | All implemented BE modules have pages. Gaps: static dashboard card, soil edit/delete, irrigation page, agent action history, CAM overlay |
| Database | Healthy, at head, persistent, additive migrations only |
| AI/ML | 1 of 3 image models trained (validation only). No evaluation report, calibration/OOD run, package, or registered model. E3/E4/E6 blocked by data |
| Integration | Crop Doctor ↔ real model: not integrated (no package). Agents ↔ soil/weather/irrigation: integrated |
| Testing | BE 252/1 skip, FE 62/62 re-run today; e2e 12/12 (Phase 3 only, older run); CI never run |
| Academic | Methodology checklist + model card drafts; results PENDING; no report/demo |

## 7. Prioritized plan (dependency order)
1-3. **DONE 2026-11-23 (Phase C)**: C1 dashboard intelligence from DB; C2 soil edit/delete UI; C3 real /irrigation page; C4 agent decision history + catalogue; C5 `GET /cases/{id}/explanation` + heatmap overlay (test double only; real-model check stays in D). Evidence: BE 258 passed/1 skipped, FE 67/67 + tsc + eslint + build, live 14/14 + restart persistence (`var/phase5c_live_verification.txt`, test account `live-check-1795459309@example.com`).
4. **D (needs closed apps, one job at a time)** onnx install → MobileNetV3 run (E2 arm, rename config id) → E1 run + majority baseline → val evaluation of all → SELECTION.md → final eval once → package → OOD → parity incl. upload WebP path → register → live case.
5. **E** FAO-56 worked-example tests; fertilizer refusal path; RAG MVP on PostgreSQL FTS (after licence review).
6. **F** e2e for Phase 4B pages + new pages; responsive/axe; security checklist pass.
7. **G** docs, matrix, PROGRESS, run stack and hand over.

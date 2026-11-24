# Overnight sprint — final report (2026-11-24)
Summary: what was done between 00:10 and the end of the session, with evidence. Start state: `OVERNIGHT_SPRINT_START.md`. Nothing was committed, staged or pushed. No dataset, checkpoint, junction, backup or cluster was deleted or moved.

## 1. Starting state
6.24 GB RAM available (Chrome 2.2 GB open) -> MobileNetV3 preflight FAILED; RAM watchdog from E2 missing. Owner closed Chrome, chose "start, keep AgriOS running" after a re-measured 8.22 GB and a tested new supervisor. DB `agrios` @54330 rev 0007; BE 258/1, FE 67 at start.

## 2. Completed (code + automated tests + live check)
| Item | Backend | Frontend | DB | Tests | Live |
|---|---|---|---|---|---|
| FAO-56 worked examples (Ex. 24-26 Eq. 58, Ex. 28 Eq. 66) + Table 11/12 transcription guard | tests only + **bug fix**: Kc interpolation was one day late (FAO i = d + 1) | — | — | tests/unit/test_fao56_examples.py (10) | — |
| Economics FR10 | app/economics (models, calc, schemas, service, router) | features/economics (page, dialogs), services/api/economics.ts | 0008 expenses, harvest_sales | unit 4 (hand-worked reconciliation), API 4, FE 2 | 12/12 (var/overnight_live_verification.txt) |
| Expert review FR12 | crop_health/review.py, review_router.py; scripts/set_role.py | features/review, crop-health/ExpertReview.tsx, role-filtered nav | 0009 expert_reviews | API 2, FE 3 | included in 12/12 |
| Cycle delete with dependents 500 -> 409 | farms/service.py | — | — | API test | live 409 |
| Analysis no longer pulls a case out of expert review | crop_health/analysis.py | — | — | covered by review tests | — |
| Fertilizer FR6 (refusal + engine) | app/nutrients | NutrientsPage (Preview) | — | unit 4 (synthetic table), API 1, FE 1 | live refusal |
| Knowledge FR8 retrieval v1 (no corpus) | app/knowledge (register, licence gate, FTS, citations) | KnowledgePage (Preview) | 0010 knowledge_sources, knowledge_chunks | API 3 (synthetic docs), FE 1 | live: empty verified library |
| Offline drafts FR13 (Crop Doctor) | uses existing client_id idempotency | features/offline (IndexedDB store, sync, sync center); client_id on every upload | — | FE 2 offline + 1 client_id assertion | not run in a browser |
| EN/UR foundation | — | src/i18n, shell/nav translated, RTL `dir`, logical CSS in shell | — | FE 2 | — |
| Coverage matrix | — | — | — | docs/15-progress/BACKEND_FRONTEND_COVERAGE_MATRIX.md | — |
| DB safety tooling | scripts/backup_db.py, init_db REQUIRED_TABLES now 23 | — | backups: var/backups/agrios_20261124_002547.dump, agrios_20261124_004317.dump | pg_restore --list readable | — |
| RAM supervisor for training | ml/scripts/train_supervised.ps1 | — | — | kill / normal / refusal verified on dummy | used for MobileNetV3 |

## 3. Partially completed
- FR6: refusal is the only live path; no reviewed requirement table or product composition source exists (human).
- FR8: infrastructure only; zero sources (no licence verified), no ingestion CLI, no S1-S3 evaluation, Knowledge agent still uses method citations.
- FR13: Crop Doctor new-case drafts only; no service worker; IndexedDB path not exercised in a real browser yet.
- Urdu: navigation/shell only; 31 strings pending native review (docs/03-architecture/I18N_REVIEW.md).
- Expert review: no per-expert assignment, no CAM in the expert view, no admin UI for roles.

## 4. Not started
Playwright e2e for the new pages (blocked during training: memory rule); full RTL pass of page content; reports module; irrigation scheduling (net/gross depth).

## 5. Database
Migrations 0008, 0009, 0010 (all additive; downgrade drops only their tables), each preceded by a pg_dump backup; dev DB now at 0010 with 23 required tables; upgrade/downgrade/drift tests pass on the test cluster. Existing data intact (test-account records added are labelled "live check (test data)").

## 6. Test results (final run)
Backend: 287 collected, 286 passed, 1 skipped (ONNX package parity; no package), 0 failed; ruff check + format clean.
Frontend: 78/78 (12 files), eslint clean, tsc clean, production build OK.
Live (through the Vite proxy, dev DB): 14/14 (Phase 5C) + 12/12 (economics, review) + 3/3 (fertilizer, knowledge) + restart persistence.

## 7. ML (validation only)
- E2 MobileNetV3-Large (runs/E2_mobilenet_v3_large_tomato_v1/seed42): epochs 0-11 completed; best validation macro-F1 0.9831 at epoch 10 (history.json); epoch 11 0.9808.
- 00:53:14 the RAM watchdog stopped training in epoch 12 (available 1.36 GB < 1.5 GB floor) after Chrome was reopened (7.6 GB). Checkpoints intact (best.pt = epoch 10, last.pt = epoch 11). Not resumed: 1.90 GB available afterwards. Details: RUN_NOTES.md in the run dir.
- Not done (need >= 8 GB free and no training): finish/early-stop the run, validation evaluation of both E2 arms (`agrios_ml.evaluate` without `--final`), comparison table (`ml/scripts/compare_val.py`), Playwright `e2e/sprint.spec.ts`.
- Test and external sets: not opened. No model selected, packaged or registered.

## 8. Completion (FYP_COMPLETION_MATRIX.md, evidence-based)
| View | Before sprint | After |
|---|---|---|
| Combined weighted | 50.90 | 59.95 |
| Software implementation (rows 1-3, 7, 9-20) | 52.9% | 66.3% |
| AI/ML core (rows 4-6, 8) | 47.8% | 47.8% (unchanged: validation results alone earn no row credit until selection + final evaluation) |

## 9. Outstanding owner decisions
1. E3/E4/E6 under Pathway B (docs/06-ai-ml-research/ML_NEXT_STEPS.md section 3) — with the supervisor.
2. Licence verification for each knowledge source (SOURCE_REGISTER.md); reviewed fertilizer table.
3. Native-speaker review of Urdu strings.
4. First Git commit (nothing committed yet).
5. Next supervised ML session: E1 run, validation evaluation, SELECTION.md, then one final evaluation.

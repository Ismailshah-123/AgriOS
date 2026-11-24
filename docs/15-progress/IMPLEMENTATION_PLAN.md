# IMPLEMENTATION_PLAN.md — phases, priorities, exit checks
Summary: 60-day plan with gates. Do phases in order. A phase is done only when its exit check passes. Track current day in PROGRESS.md.

## Phases
| Days | Work | Exit check |
|---|---|---|
| 1-5 | Dataset audit, literature gap check, crop/class decision, Pathway A/B, scope freeze, repo setup (G1 Day 5) | Audit doc + frozen scope |
| 6-12 | DB schema, auth+roles, farm/field/cycle/activities/soil, audit middleware, ownership tests, frontend shell | Farm flow works with tests |
| 13-22 | Clean/dedupe data, freeze splits (Day 15), E1 baseline, E2 transfer, error analysis | Baseline + model metrics saved |
| 23-30 | Calibration, thresholds, Grad-CAM, SHAP, E7; fusion only if Pathway A; integrate Crop Doctor; freeze model Day 30 (G2) | Model card + thresholds |
| 31-37 | Soil rules, irrigation (FAO 56), fertilizer, risk indicators, units, simulation | Calculators validated |
| 38-44 | Knowledge base, retrieval, citation verifier, RAG comparison, agent runtime, Crop Health Assistant (P0), Irrigation agent (P1) | Cited answers; audited agent run |
| 45-50 | Economics, harvest, expert queue, offline PWA, weather, sensor sim, integration; freeze Day 49, G3 Day 50 | End-to-end demo works |
| 51-56 | Final model eval, unit/API/security/offline/E2E tests, usability, backup test (G4 Day 56) | Test report complete |
| 57-60 | Report, slides, demo script, backup video, final package (G5 Day 60) | Submission ready |

## Build order inside the repo (start here)
1. Repo skeleton, Docker Compose, CI, `.env.example`, README.
2. DB models + Alembic + seed.
3. Auth + RBAC + audit middleware (+tests).
4. Farm/field/cycle/activity/soil APIs (+tests) -> frontend screens.
5. Dataset audit scripts (parallel, in /ml).
6. Calculators as pure functions with tests (can be built any time after step 1).
7. Crop Doctor API stub (returns "unsure") so the full flow exists early; swap in real model after Day 30.
8. Knowledge + RAG + verifier. 9. Agents. 10. Economics, expert, offline, polish.

## Weekly gate (Sundays)
Show working software or reproducible experiment. Update FEATURE_STATUS. If behind, apply cut order (see PRODUCT_REQUIREMENTS.md).

## Freezes
Splits Day 15. Model Day 30. Features Day 49. After Day 49 bug fixes only.

## Risks to watch
Paired data absent (use Pathway B). Free GPU loss (checkpoint). Feature creep. Unverified references (open every one, check title/authors/year/DOI).

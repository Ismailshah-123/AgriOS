# TESTING_QA.md — tests and quality gates
Summary: test levels, pass conditions, tools, CI gates, model testing, production-readiness checklist.

## Levels
| Level | Scope | Tool | Pass condition |
|---|---|---|---|
| Unit | calculators, unit conversion, decision rules, metrics | pytest | match hand/reference values |
| Integration | upload->model->decision->saved case; agent run with approval | pytest | correct records + audit |
| API | all endpoints, errors, ownership, roles | pytest + httpx | other user's data never returned |
| Security | bad/oversized files, wrong tokens, injection strings, rate limits | pytest + scripts | rejected safely |
| Frontend | components, i18n, RTL | Vitest | pass |
| E2E | register->farm->cycle->diagnose->calculate->ask->profit | Playwright | no manual fixes |
| Offline | create offline, reconnect, retry, conflict | Playwright (network off) | no loss, no duplicates |
| Model | frozen test, field photos, unknown inputs | ml scripts | metrics saved, failures logged |
| RAG/Agent | question set, tool errors, approvals, audit | scripted | metrics saved |
| Usability | 5-10 users, SUS | manual | report with small-sample caveat |

## Must-have specific tests
- FAO 56 worked examples reproduced (record abs error).
- Urea example: 100 kg N/ha at 46% N = 217.4 kg/ha.
- Units round-trip (acre, kanal, marla, ha, kg, maund, L).
- Fertilizer refuses without stored source.
- Ask returns "No verified guidance found" for unsupported question.
- Agent write without approval is impossible (test attempts bypass).
- Disable LLM adapter -> full suite still passes.
- Blurry image -> retake; non-plant -> out_of_scope.
- Same image twice with same model version -> same prediction.

## CI (GitHub Actions, every push)
ruff + mypy(optional), pytest -q, npm lint + Vitest, build frontend, pip-audit/npm audit (warn), contract snapshot. Playwright on main nightly or pre-demo.

## Coverage targets
Calculators/decision rules 95%, backend overall >= 80%, critical paths (auth, ownership, approval) 100% of branches tested.

## Model test discipline
Test set opened once per model family. Report macro F1, per-class results, calibration, selective risk, field-set results separately, failure cases. Keep PENDING until run files exist.

## Production-readiness gate (all must be true)
[ ] all P0 flows work from UI  [ ] CI green  [ ] E2E green incl. offline  [ ] security checklist done  [ ] calculators validated  [ ] model card + thresholds frozen  [ ] FEATURE_STATUS accurate  [ ] README works on clean machine  [ ] backup restore tested  [ ] demo video recorded  [ ] test report in /docs

## Phase 4B test inventory (executed 2026-11-23)
- Backend unit: `tests/unit/test_irrigation_and_risk.py` (Kc curve, ETc = Kc x ET0, missing ET0 stays None, IMD heavy rain, Beaufort wind, dry spell, accumulation, missing rain day not guessed).
- Backend DB: `tests/db/test_irrigation_api.py` (missing cycle/coords reported, ETc computed, owner-only), `tests/db/test_agents_api.py` (complete field report across modules, partial report names missing data, intents incl. Urdu, write needs approval then executes with audit, reject + expiry, tenant isolation incl. 401, catalogue schemas), `tests/db/test_soil_api.py` (+ micronutrients/CEC stored with units, not interpreted, bad method key 422), migration drift + up/down/up with 0006/0007.
- Frontend: `tests/features/intelligence.test.tsx` (weather stale + attribution + risks + missing day shown as missing, missing location prompt, soil validation + nulls for unmeasured values, agent report/tool timeline/approval + axe), routing nav statuses updated.
- Results (final run 20:37): backend 252 passed, 1 skipped (ONNX package parity test: no packaged model yet), ruff + format clean; frontend Vitest 62/62, tsc strict, eslint clean, production build OK.
- Live check against the running local stack (test accounts only): `var/phase4b_live_verification.json` — 9/9 checks passed (real Open-Meteo request, ETc, soil interpretation, field report, approval flow, cross-user 404).
- Weather tests never call the network (FakeProvider).

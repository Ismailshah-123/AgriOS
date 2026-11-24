# API_CONTRACTS.md — endpoints and rules
Summary: versioned REST API under `/api/v1`, error format, pagination, idempotency, endpoint groups with access. Schemas are Pydantic models in `backend/app/<module>/schemas.py`; OpenAPI is the generated contract.

## Global rules
- Validate every ID, unit, range, file server-side. No stack traces in errors.
- Error format: `{ "error": {"code": "string", "message": "string", "field": "optional"} }`.
- Other user's resource -> 404 (not 403).
- Pagination: `?limit=&cursor=`. Offline writes: `Idempotency-Key` header + `client_id`.
- Auth: JWT access (short) + refresh. Rate limit login and uploads.
- Every response with a recommendation includes `sources[]`, `assumptions[]`, `uncertainty`.
- Values carry `{value, unit, data_origin}`.

## Groups
| Group | Endpoints | Access |
|---|---|---|
| auth | POST /auth/register, /auth/login, /auth/refresh; GET /auth/me | public (rate-limited) / auth |
| farms | CRUD /farms, /fields, /crop-cycles, /activities | owner |
| soil/weather | CRUD /soil-observations; GET /weather?field_id= | owner |
| doctor | POST /cases (multipart image + optional context), GET /cases/{id}, POST /cases/{id}/feedback | owner, expert (assigned) |
| calculators | POST /irrigation/calc, /fertilizer/calc, /economics/calc, /units/convert | auth |
| knowledge | POST /ask; admin: POST /knowledge/sources, PATCH review status | auth / admin |
| agents | POST /agents/{name}/run, GET /agent-runs/{id}, POST /approvals/{id} | owner |
| experts | GET /review/queue, POST /review/{id} | expert |
| admin | GET /models, POST /models/{id}/activate, GET /audit, GET /users | admin |
| sync | POST /sync/batch (ordered drafts) | owner |

## Key response shapes (fields only)
- Case result: `status`(accepted|retake|unsure|out_of_scope), `prediction{class, calibrated_conf, shortlist[]}`, `ood_score`, `explanation{gradcam_url, shap[]}`, `context_used{full|partial|none}`, `guidance{answer, citations[]}`, `model_version`, `limits_note`.
- Irrigation: `et0, kc, etc, effective_rain, net_mm, gross_mm, volume_m3_per_ha, volume_m3_per_acre, assumptions[], source_refs[]`.
- Fertilizer: `nutrient_need, product_amount, cost, source_ref`; 422 `no_source` if table missing.
- Ask: `answer`, `citations[{doc_id, chunk_id, title, year}]` or `{"answer": null, "reason": "no_verified_guidance"}`.
- Agent run: `steps[{tool, args, result, status}]`, `pending_approval{id, preview}`.

## Upload limits
jpeg/png/webp, <= 8 MB, decode check, min/max dimensions, random filenames, private storage, no public URLs (signed, short-lived).

## Acceptance
OpenAPI exported to `docs/api_notes`. Every endpoint has tests for success, validation error, auth failure, ownership. Contract snapshot test prevents silent breaking changes.

## Phase 3 additions — Crop Doctor (implemented 2026-11-23; additive, nothing above changed)
Reviewed against the "doctor" row above. `POST /cases` and `GET /cases/{id}` are kept; the rest is added. `POST /cases/{id}/feedback` (expert loop) is not implemented yet.
| Endpoint | Purpose | Notes |
|---|---|---|
| POST /cases | multipart: `crop_cycle_id`, 1-5 `images`, optional `plant_part`, `symptoms[]`, `observed_on`, `notes`, `consent_training`, `client_id` | cycle must be owned and `active`; 201 case detail; `client_id` makes retries idempotent |
| GET /cases | list | filters `status`, `inference_status`, `crop_id`, `farm_id`, `field_id`, `crop_cycle_id`, `needs_follow_up`, `created_from/to`, `q`; cursor pagination |
| GET /cases/summary | real counts + `model_availability` | |
| GET /cases/{id} | detail: submissions (append-only), images (signed links), `analysis`, `timeline` | |
| POST /cases/{id}/follow-ups | multipart: 0-5 `images` + observations (at least one) | re-queues analysis when photos are added |
| GET /cases/{id}/analysis | `inference_status`, `model_availability`, `message`, `can_retry`, `result` | `result` only after a completed inference |
| POST /cases/{id}/analysis/retry | re-queue | only from `failed` or `model_unavailable`; else 409 |
| GET /models/availability | system model status | not_registered, not_installed, checksum_mismatch, loading, ready, error |
| GET /files/case-images/{id}/{full\|thumb}?exp&sig | private image bytes (WebP) | HMAC link bound to image, variant, owner and expiry (default 10 min); any failure is 404 |
Statuses: `status` keeps the documented case_status enum; `inference_status` (not_started, queued, running, completed, failed, model_unavailable) is separate; model availability is never stored per case.
Result shape (when completed): `decision` (accepted/unsure/out_of_scope), `predicted_class` (accepted only), `calibrated_confidence`, `ood_score`, `shortlist[]`, `model_name`, `model_version`, `analysed_at`, `limits_note`. Grad-CAM (`explanation`) is reserved, not generated.
Errors: 413 `payload_too_large` (streamed body limit), 422 `image_*` (`image_too_large`, `image_type_not_allowed`, `image_unreadable`, `image_dimensions_too_large`, `image_too_small`, `image_animated`, `image_count`), 422 `cycle_not_active`, 422 `storage_quota_exceeded`, 409 `case_closed`, 429 `rate_limited`, 503 `storage_unavailable`.

## Phase 4B: irrigation, agents, soil additions (all JWT, owner-scoped; another user's ids -> 404)
| Endpoint | Body / params | Notes |
|---|---|---|
| GET /fields/{id}/water-demand | - | FAO-56 ETc for the active cycle over forecast days: `status` ok/unavailable, `current_stage`, `daily[]` (kc_low/high, et0, etc_low/high, rain), `totals`, `missing_information[]`, `limitations[]`, `data_origin: inferred`, `effective_rainfall: not_applied`, `soil_moisture: not_measured` |
| POST /agent/runs | `{message (2-500), farm_id?, field_id?}` | 201 run: `intent`, `agents[]`, `status` completed/partial/failed, `response` (answer, sections[], report, suggested_actions[], missing_information[], evidence[], pending_actions[], limitations[], llm_used=false), `steps[]` (tool, mode, status, duration_ms), `actions[]` |
| GET /agent/runs | `limit`, `cursor` | conversation history (cursor pagination) |
| GET /agent/runs/{id} | - | full run with steps and actions |
| GET /agent/actions | `status?` | pending/approved/rejected/expired/executed/failed; expires due actions first |
| POST /agent/actions/{id}/approve | - | executes the write tool as the owner; 409 if not pending or expired; result `executed` or `failed` (+ error_code) |
| POST /agent/actions/{id}/reject | - | 409 if not pending |
| GET /agent/catalogue | - | agents (name, purpose) and tools (mode, permission, requires_approval, timeout, JSON input/output schemas) |
Soil observation create/update/out also accept `calcium_mg_kg, magnesium_mg_kg, sulfur_mg_kg, zinc_mg_kg, iron_mg_kg, boron_mg_kg, cec_cmol_kg` (decimal strings, null = not measured) and `nutrient_methods` ({measure: lab method label}). Weather indicators now include `time_window` and `limitations`.

## Phase 5C additions (2026-11-23; additive, existing shapes unchanged)
| Endpoint | Purpose | Rules |
|---|---|---|
| GET /overview -> `intelligence` | crop_health {cases, awaiting_analysis, needs_follow_up, model_availability}, soil {observations, fields_with_tests, latest_sampled_on}, weather {farms, farms_with_location}, irrigation {growing_cycles, cycles_with_estimate}, agents {runs, pending_approvals} | counts of the caller's own records only; no forecast or estimated values |
| GET /cases/{id}/explanation | `available`, `reason` (no_completed_analysis / out_of_scope / not_provided_by_model), method, target_class, note, maps[{image (signed links), grid (rows x cols, 0..1), crop_box [left, top, width, height] fractions}], model name/version, limits_note | owner-only (404 otherwise); only for a completed analysis; never for out_of_scope; `analysis.result.explanation_available` is false for out_of_scope |
| GET /agent/actions (no status) | all decided + pending proposals (newest 100) | already existed; now used by the UI decision history |
| GET /agent/catalogue | agents, typed tools (mode, requires_approval), llm_used | already existed; now shown in the UI |

## Overnight sprint additions (2026-11-24; additive)
| Endpoint | Purpose | Rules |
|---|---|---|
| GET /crop-cycles/{id}/economics; POST/PATCH/DELETE /expenses, /harvest-sales | FR10 records + summary | owner-only; PKR decimal strings; audited; cycle with records -> DELETE cycle 409 `cycle_not_empty` |
| POST /cases/{id}/expert-review | owner asks an expert | 409 if already with an expert or closed |
| GET /review/queue; GET/POST /review/cases/{id} | FR12 expert queue + outcome | expert/admin only (403); experts see only queued or previously reviewed cases (404 otherwise); label required for confirmed_model/diagnosed |
| GET /crop-cycles/{id}/fertilizer | FR6 | `refused / no_reviewed_source` + escalation; never numbers while no reviewed table exists |
| GET /knowledge/search?q=, GET /knowledge/sources | FR8 retrieval v1 | only licence_verified/content_reviewed sources searched; extractive cited passages or "No verified guidance found" |
| POST /cases `client_id` (form field) | offline/idempotent upload | frontend now always sends it; same id returns the first case |

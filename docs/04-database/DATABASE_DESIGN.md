# DATABASE_DESIGN.md — PostgreSQL schema
Summary: tables, key constraints, enums, migration rules. Source of truth = Alembic migrations; this file is the plan.

## Rules
- PostgreSQL 15+, SQLAlchemy 2, Alembic. UUID PKs. `created_at`, `updated_at` on all tables.
- FK on every ownership link. Soft delete only where audit requires.
- `data_origin` NOT NULL on all measurements. `is_simulated` NOT NULL on sensor_readings.
- `model_version_id` NOT NULL on predictions. Unique `client_id` for offline submissions.
- Store area in hectares internally; convert at the edge (acre 0.404686 ha; kanal/marla verified from official source, shown in app).
- Migrations apply cleanly on empty DB and are reversible. One migration per change.

## Enums
role: farmer|expert|admin. data_origin: measured|farmer_entered|retrieved|inferred|simulated. case_status: submitted|retake|unsure|accepted|out_of_scope|expert_review|closed. plan_status: proposed|approved|saved|rejected. model_status: candidate|active|retired. review_status (knowledge): pending|approved|rejected.

## Tables
| Group | Table | Key fields |
|---|---|---|
| Identity | users | id, email unique, password_hash, role, locale |
| | audit_events | id, actor_id, action, entity, entity_id, meta jsonb, time |
| Farm | farms | owner_id FK, name, region, location (coarse) |
| | fields | farm_id FK, area_ha, boundary_geojson |
| | crop_definitions | name, kc_by_stage jsonb, stage_lengths jsonb, source_ref |
| | crop_cycles | field_id FK, crop_id FK, variety, sowing_date, stage |
| | activities | cycle_id FK, type, date, notes, client_id |
| | input_applications | cycle_id FK, product, quantity, unit, source_ref |
| Observations | soil_observations | field_id FK, ph, ec, n, p, k, om, texture, moisture, date, data_origin |
| | weather_observations | field_id FK, date, t, rh, rain, rad, wind, data_origin |
| | sensor_readings | field_id FK, metric, value, unit, is_simulated |
| Doctor | diagnosis_cases | cycle_id FK, image_ref, status, consent_flag, client_id |
| | diagnosis_predictions | case_id FK, model_version_id FK, class, probs jsonb, calibrated_conf, ood_score, context_mask jsonb |
| | expert_reviews | case_id FK, expert_id FK, label, decision, note |
| | case_messages | case_id FK, sender_id, text |
| | model_versions | name, arch, data_hash, config, metrics_ref, temperature, threshold, checksum, status |
| Knowledge | knowledge_documents | title, publisher, year, url, licence, crop, topic, language, review_status |
| | knowledge_chunks | doc_id FK, text, embedding vector, crop, stage, topic |
| | citations | answer_id, chunk_id |
| Agents | agent_runs | user_id, agent, status |
| | tool_invocations | run_id FK, tool, args, result, approved_by, time |
| Economics | expenses, revenues, harvest_records | cycle_id FK, category, amount, qty, date |
| Plans | irrigation_plans, fertilizer_plans | cycle_id FK, inputs, outputs, source_ref, status |
| Tasks | tasks, reminders, notifications | user_id, due, status |

## Indexes
users.email; crop_cycles(field_id); diagnosis_cases(cycle_id,status); predictions(case_id); chunks vector (ivfflat/hnsw) + (crop,topic); audit_events(actor_id,time).

## Acceptance
Migrate up/down tested in CI. Ownership queries never return other users' rows. Seed script creates demo farmer, expert, admin, crop definitions with cited Kc.

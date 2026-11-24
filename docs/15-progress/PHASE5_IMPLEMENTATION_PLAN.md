# Phase 5-7 implementation plan (audit + plan only; nothing here is implemented yet)
Summary: verified current state, then checklists for Crop Doctor model integration (Phase 5), an agricultural RAG MVP (Phase 6) and the end-to-end workflow (Phase 7), with order, dependencies, risks, effort and the evidence needed for ~60% FYP completion. Written 2026-11-23 while E2 trains; no test data opened, no GPU work.

## 1. Audit — verified state (detail: FYP_COMPLETION_MATRIX.md, reconciled total 50.30 / 100)
| Class | Items |
|---|---|
| Implemented and tested (V) | Auth/roles/ownership/audit; farms, fields, crop cycles; Crop Doctor intake, cases, worker, decision rule, UI (with a test-double predictor); dataset audit + frozen split; soil intelligence + UI; weather + 7 risk indicators + UI; agents (orchestrator, 6 agents, 9 tools, approvals, field report, UI); security hardening |
| Implemented, not fully tested (U) | FAO-56 ETc (no worked-example test; ET0 from provider); ONNX predictor + registry + packager + register script (never run on a real model; parity test skipped); CAM computation (no trained model) |
| Partially implemented (P) | Trained model (E2: 8 epochs, validation only); calibration + OOD (code, no run file); CI (never run remotely); usability (no Urdu strings); documentation/results (tables PENDING) |
| Not implemented (N) | Verified RAG; fertilizer from cited tables; economics; expert review queue; offline PWA sync |

Genuine missing requirements for the core claim (CAAIE): an evaluated model, calibrated + rejecting serving, a visible explanation, RAG with cited answers.

Facts found in this audit:
- CAM maps are computed by `app/mlops/onnx_predictor.py` and stored in `diagnosis_predictions.explanation`, but the API exposes only `explanation_available` and the UI renders nothing.
- Stored uploads are WebP derivatives (max side 2048); training used JPEG q95 cache images (short side 256). The golden parity test feeds cache JPEGs only, so the upload path is untested.
- `onnx` is not installed in `ml/.venv` (needed by package.py's export).
- Local PostgreSQL 18 has **no pgvector** (`pg_available_extensions`), Docker is not installed; Compose uses pgvector images but has never run.
- `docs/09-rag-knowledge/` and `knowledge/` were empty and removed in the approved cleanup; no RAG code or documents exist.

## 2. Phase 5 — Crop Doctor model integration checklist
Order follows `docs/06-ai-ml-research/POST_TRAINING_RUNBOOK.md`. Owner of each artefact in brackets.
1. **Training completion** — E2 EfficientNet-B0 done (early stop, best epoch 5, validation only); E2 MobileNetV3-Large (config file named E3_…); E1 small CNN baseline if time. [ml]
2. **Environment** — `uv add onnx` in ml after training (not during). [ml]
3. **Validation-only evaluation** for each run → `reports/<exp>/val/metrics.json` (temperature, ECE/Brier, selective risk, latency). [ml]
4. **Selection** written to `ml/reports/SELECTION.md` before any test access (rule: best calibrated val macro-F1; within 0.005 prefer lower CPU latency). [ml]
5. **Final evaluation once** (`--final`): internal test + external (PlantDoc/PlantWild) with per-source breakdown. [ml]
6. **Packaging** — ONNX (`image` → `logits`, `features`), `cam_weights.npy`, golden vectors, `package.json` with labels, preprocessing, temperature, thresholds, split hash, checkpoint hash, environment, licence note. Versions immutable. [ml]
7. **Preprocessing parity** — keep the existing golden test (torch vs ONNX on cache JPEGs) and ADD an upload-path test: original image → `process_image` (EXIF, WebP 2048) → ONNX predictor vs torch eval on the original; report top-1 agreement and max logit delta on **validation** images. [backend test]
8. **Calibration** — temperature from validation (already in evaluate.py); thresholds from validation (package.py). Report ECE before/after. No threshold tuned on test. [ml]
9. **OOD / unknown rejection** — energy score; `ood.py` (other-crop leaves, `--workers 2`); add a small non-plant check set only from licensed images, or state the limitation. [ml]
10. **Registry + lifecycle** — `register_model.py --activate` (checksum, audit); availability states already implemented (not_registered / not_installed / checksum_mismatch / error / ready); one cached ONNX session per (artefact, checksum). Add a retire/rollback admin path test. [backend]
11. **API contract** — keep `PredictionOut`; add `GET /cases/{id}/explanation` (owner-only) returning CAM grids per image with `method`, `target_class`, `note`; never generated for `out_of_scope`. [backend]
12. **Error handling** — existing: retries with backoff, `failed` after last attempt, `model_unavailable` honest state. Add: corrupt package (checksum) and shape-mismatch tests on a real package. [backend]
13. **Frontend** — heatmap overlay on the case photo (opacity toggle, legend "regions that raised the score", limits note), calibrated confidence wording, shortlist for `unsure`, expert-review prompt. [frontend]
14. **End-to-end** — Playwright: upload a validation image (not test) → worker → result + heatmap; agent field report shows `crop_health: ok`. Run only with no training active. [e2e]
Exit criteria: packaged model registered; parity tests pass; final metrics + OOD JSON saved; UI shows result and heatmap; FEATURE_STATUS "Crop Doctor model" → Evaluated.

## 3. Phase 6 — Agricultural RAG MVP (plan)
Constraint-driven design (no pgvector, no Docker, 15.6 GB RAM, CPU only):
1. **Sources** — curated list in `knowledge_sources` with title, publisher, URL, date, licence, licence URL, language, region (Pakistan / international), review status. Candidate publishers to verify individually (licence recorded per document before ingestion, nothing ingested without a confirmed licence): FAO open-access publications (many CC BY-NC-SA 3.0 IGO; check each), FAO-56 itself (already cited), Pakistan provincial agriculture department advisories (permission/licence unknown → contact or exclude), university extension tomato guides (check terms). No document is written or summarised by an LLM.
2. **Ingestion** — PDF/HTML text extraction (pypdf / trafilatura-class tools, to be chosen and licence-checked), page numbers kept, checksum per file, raw files outside Git.
3. **Chunking** — heading-aware chunks (~300-500 tokens, overlap ~50), each with source id, page, section.
4. **Retrieval v1 (lexical)** — PostgreSQL full-text search (`tsvector`, `ts_rank_cd`) — available now, zero new infrastructure.
5. **Retrieval v2 (hybrid, only if v1 evaluation shows misses)** — CPU sentence embeddings via ONNX Runtime (small multilingual model, licence-checked), vectors stored as `REAL[]` with exact cosine in Python for a few thousand chunks; pgvector adapter when available. Fusion by reciprocal rank.
6. **Answering** — extractive: return top passages with citations (source, page, link); answer text = quoted passages + template. "No verified guidance found" when the best score is below a validated threshold. No doses unless from a reviewed table (hard rule 2).
7. **Evaluation** — question set written from the sources (with expected source pages), split dev/test; metrics: recall@k, MRR, unsupported-answer rate, refusal correctness (S1-S3 in AI_ML_RESEARCH_PLAN.md).
8. **Agent integration** — replace `search_method_references` with `search_knowledge` (read tool) used by the Knowledge agent; evidence entries carry chunk ids.
9. **Safety** — citation required for every statement; refusal path; dose-pattern filter; source review status shown; Urdu queries answered only from Urdu/English sources actually ingested.

## 4. Phase 7 — End-to-end workflow (plan)
Field report gains a Crop Doctor section and a knowledge section; every item carries its origin label:
| Item | Origin label | Source of truth |
|---|---|---|
| Disease prediction | inferred (model) | diagnosis_predictions + model version + calibrated confidence + CAM |
| Soil values | measured / farmer_entered | soil_observations |
| Weather | retrieved | weather_snapshots (+ provider, time) |
| Risk indicators, ETc | inferred (rule) | cited rule + inputs |
| Knowledge passages | retrieved (document) | knowledge chunk + citation |
| Suggested actions | agent-generated | links to the evidence items above + limitations |
Rules: a weather indicator never upgrades a prediction; a low-confidence prediction stays "no definitive diagnosis" with expert escalation; any record change remains an approval-gated action (existing mechanism); report coverage lists each missing source.

## 5. Recommended order, dependencies, effort
| # | Work | Depends on | Effort (focused dev) |
|---|---|---|---|
| 1 | Finish E2 EfficientNet-B0 → E2 MobileNetV3 (→ E1) training | GPU time, no RAM-heavy apps | 2-4 h machine time |
| 2 | onnx install, val evaluation, selection note | 1 | 1 h |
| 3 | Final evaluation + OOD + package + parity tests | 2 | 2-3 h |
| 4 | Register; explanation endpoint; heatmap UI; e2e | 3 | 4-6 h |
| 5 | Field report crop-health integration check | 4 | 1 h |
| 6 | RAG sources + licences (human review needed) | none (can start now, text only) | 3-5 h |
| 7 | RAG ingestion, FTS retrieval, evaluation set, agent tool | 6 | 6-10 h |
| 8 | Methodology checklist evidence + paper tables | 3, 7 | 3-4 h |

## 6. Risks
- RAM: training is interrupted by games/browsers (watchdog/supervisor mitigate; evaluation must also run alone). 
- Domain shift: internal test likely far above external (lab vs field images); report both, never only internal.
- Possible leakage via augmented copies (New Plant Diseases ← PlantVillage) beyond pHash grouping: internal test may be optimistic.
- External set lacks target_spot and has 2 spider_mites images: no external claim for those classes.
- Source licensing for RAG may block Pakistan-specific documents.
- No CI run and no Docker: reproducibility evidence is local only.
- Deadline: Phase 6 at production quality is unlikely before 2026-11-24; an MVP with honest evaluation is achievable after Phase 5.

## 7. Evidence needed for ~60% (from 52.30)
| Evidence (saved file) | Matrix rows | Expected gain |
|---|---|---|
| `reports/<selected>/final/metrics.json` (val + test + external) + MODEL_CARD filled | 5 | +4 to +5 |
| Temperature/ECE in that file + `reports/<selected>/ood/ood_metrics.json` | 6 | +3 to +4 |
| Package registered + parity tests passing + live Crop Doctor case completed | 7, 3 | +2 to +3 |
| Heatmap endpoint + UI test + check on real images | 8 | +1.5 to +2 |
| Total from Phase 5 alone | | **≈ +10 to +13 → 62-65%** |
RAG MVP with an evaluation file adds a further +3 to +4.

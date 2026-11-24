# ARCHITECTURE.md — system structure
Summary: modular monolith layout, module boundaries, ML serving, RAG, agents, adapters, degraded modes.

## Style
One FastAPI app, separate domain modules, explicit interfaces. No microservices. Worker container only for inference/reports if needed.

## Repo layout
```
/backend   app/{auth,farms,doctor,calculators,knowledge,agents,experts,monitoring,audit,adapters}, tests, migrations
/frontend  pages, components, i18n, service worker, offline store
/ml        data scripts, notebooks, train/eval code, configs, reports, models (not committed; checksum note)
/data      raw (read-only), interim, processed, splits  (not in Git; manifest + checksums)
/knowledge source register + reviewed sources
/docs      dataset_audit, dataset_card, model_card, api_notes, test_report, FEATURE_STATUS
root       docker-compose.yml, .env.example, README, LICENSE note, CLAUDE.md + 12 docs
```

## Module rules
- Each module exposes a service interface; no cross-module DB access except via service.
- Calculators and risk engine = pure functions (no I/O, no LLM). Unit-testable.
- Adapters (LLM, weather, satellite, sensor-sim) behind interfaces with cache + fallback.
- Inference service loads only the `active` model version. Every prediction stores `model_version_id`.

## Crop Doctor pipeline
file validate (type, size, decode, EXIF strip) -> quality check (blur, exposure, leaf area) -> context fetch + mask -> model (image-only or fusion) -> temperature scaling -> OOD score (max-prob + energy) -> decision (accept | retake | unsure | out-of-scope) -> Grad-CAM/SHAP -> RAG guidance (accepted only) -> persist case + audit.

## ML serving
CPU inference in backend container. Model file mounted volume; checksum verified at startup. Target single-image latency measured, not assumed.

## RAG
Ingest -> metadata (licence required) -> section chunks -> multilingual embedding -> pgvector -> filter (crop/topic/region) -> hybrid retrieve -> optional rerank -> grounded generation -> verifier (citation matches, no dosage without table source) -> answer or "No verified guidance found".

## Agents
Orchestrator -> permission check -> tool registry (allow-list) -> validate output/units -> consequential? -> approval gate -> commit -> audit (AgentRun, ToolInvocation). Retry once, then safe fallback. P0: Crop Health Assistant. P1: Irrigation Planning. P2: designs only.

## Degraded modes
LLM down -> templates. Weather down -> cache/manual entry (labelled). Inference fails -> queue for expert. Offline -> IndexedDB drafts.

## Out of scope
Kubernetes, microservices, paid GPUs, real sensors/drones, payments, marketplace, autonomous control.

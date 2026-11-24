# RAG architecture — AgriOS Knowledge Intelligence (2026-11-24)
Summary: how the knowledge platform is built, inside the existing modular monolith. No new services were added: PostgreSQL holds sources, chunks, vectors, conversations and telemetry; the existing DB job queue + worker runs ingestion; model providers sit behind replaceable adapters.

## 1. Components
```
React /knowledge (Ask · Sources · Analytics)
        │  REST /api/v1/knowledge/*
FastAPI app/knowledge
  router.py            ask, search, conversations, feedback, chunk viewer, stats, taxonomy (any user)
  router_admin.py      register / patch / review / upload / reprocess / delete / analytics (ADMIN; analytics ADMIN|EXPERT)
  answer.py            ask pipeline: understand → rewrite → retrieve → farm records → generate|quote → validate → persist
  query.py             language (en / ur / ur-Latn), Urdu+Roman-Urdu glossary, domain + crop lexicon, farm & dose intent
  retrieval.py         hybrid: PostgreSQL FTS (ts_rank_cd, GIN) + dense cosine (numpy over REAL[]), RRF fusion, thresholds, dedupe, context budget
  generation.py        prompts, citation normalisation + validation, groundedness, dose guard, extractive fallback, speech text
  farm_context.py      the asking user's own records (owner-scoped), units + origin labels, missing data listed
  ingestion.py         source lifecycle + worker job handler (knowledge.ingest)
  extract.py           PDF / DOCX / TXT / MD / HTML / CSV → (page, section, text); magic-byte checks
  service.py           section-aware chunking, licence-gated indexing, content hashes, embeddings
  providers.py         Embedder (none | fastembed ONNX) and ChatLLM (none | groq | xai | ollama | openai_compatible)
PostgreSQL 15 (migration 0011, additive)
  knowledge_sources (provenance, licence, review, file, version, ingest state/log)
  knowledge_chunks  (text, page, section, tsvector, embedding REAL[], model, hash, language, version)
  knowledge_conversations, knowledge_queries (answers, citations, telemetry, feedback)
Worker (app.jobs.worker) — HANDLERS: crop_health.analyse, knowledge.ingest
```

## 2. Knowledge domains (extensible)
`models.DOMAINS`: crop_science, plant_protection, soil_science, nutrient_management, irrigation_water, weather_climate, farm_operations, economics_business, livestock_allied, research_policy. A new domain = one value + lexicon entries in `query.py`; no schema change (domain is a string column). Sources also carry `crops[]`, `document_type`, `country`, `region`, `language`.

## 3. Provider choices (replaceable)
| Concern | Default | Why | Alternatives (config only) |
|---|---|---|---|
| Embeddings | `fastembed` + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-d, ONNX, CPU, ~220 MB) | runs locally (no per-query cost, no data leaves the PC); multilingual → Urdu questions match English passages (EN↔UR cosine 0.61 measured on a probe pair vs ≈0 unrelated) | `EMBEDDING_PROVIDER=none` (keyword only) |
| Vector store | `REAL[]` column + numpy cosine | no pgvector binary on this Windows host; corpus is small (276 chunks, p50 retrieval 36–49 ms) | pgvector HNSW when the corpus grows (same column semantics) |
| LLM | Groq free tier, `openai/gpt-oss-120b`, fallback `openai/gpt-oss-20b` on HTTP 429 | free for the demo, fast | `LLM_PROVIDER=ollama` (local llama3), `xai`, `openai_compatible`, or `none` |
Hard rule 8: with `LLM_PROVIDER=none` the system still answers (quoted passages with citations). Tests run with both providers disabled.

## 4. Data flow of one question
1. `query.analyse`: language, domains, crops, farm intent, dose intent, veterinary flag.
2. Conversation history (last 3 turns, owner-checked). If an LLM is configured and the question is a follow-up or not English → LLM rewrites it to one standalone English query (JSON). Otherwise: deterministic carry-over of the previous question + glossary terms.
3. Clarification: first question too short with no crop/domain → asks for detail (status `clarify`).
4. Hybrid retrieval with optional filters (domain, crop, source, document type).
5. Farm records added only for "my farm/field…" questions (or user setting), owner-scoped.
6. No evidence and no farm records → `abstained` ("No verified guidance found").
7. LLM answer from fenced passages → validation → `answered`, or fallback `extractive` (quoted sentences) when the LLM is off/failed/ungrounded. Doses redacted everywhere; dose questions get an explicit refusal + expert escalation.
8. Row in `knowledge_queries` (answer, citations, warnings, latency, tokens, provider/model).

## 5. What this is not
- Not a general chatbot: no answer without retrieved evidence or the user's own records.
- Not expert-reviewed content: every current source is `licence_verified`, none `content_reviewed`.
- No predictive claims: farm-record questions summarise recorded data only.

# RAG implementation status (updated 2026-11-24 evening)
Summary: the knowledge module is now an operational, cited RAG over a small licence-verified library (18 sources, 276 chunks). It is not a complete agricultural knowledge base: sources are general (Wikipedia + one US EPA page), none is Pakistan-specific or expert-reviewed.

Legend: **IT** implemented + tested · **IU** implemented, not fully tested · **P** partial · **N** not implemented · **B** blocked by data/approval

## Coverage matrix
| Capability | Backend | API | DB | Frontend | Status | Evidence |
|---|---|---|---|---|---|---|
| Source register with full provenance + licence | ingestion.py, router_admin.py | POST/PATCH/GET /knowledge/sources | knowledge_sources (0010+0011) | Sources tab: table, register dialog, details | IT | test_source_lifecycle…, knowledge.test.tsx |
| Licence review workflow (verify / content-reviewed / block, note required) | ingestion.review | POST …/review | verified_by/at, review_note | Sources tab actions | IT | test_source_lifecycle… |
| Upload PDF/DOCX/TXT/MD/HTML/CSV | extract.py | POST …/file | file_* columns | file input + progress | IT (PDF IU: no real PDF ingested yet) | test_knowledge_units, live 17 MD + 1 HTML |
| OCR (scanned PDFs) | — | — | — | — | N (fails with `no_text_layer`) | — |
| Background ingestion + status + log + retries | ingestion.handle (worker) | GET …/{id} | ingest_status/log, jobs | badges, auto-refresh, processing log | IT | test_source_lifecycle…, 36 jobs succeeded live |
| Reprocess / versioning / deactivate / delete + index cleanup | ingestion, router_admin | POST …/reprocess, PATCH, DELETE | version, is_active, FK cascade | buttons + confirm dialog | IT | test_source_lifecycle… |
| Duplicate detection | sha256 unique + chunk hash | 409 | uq index | error shown | IT | test |
| Section-aware chunking + page/section refs | service.chunk_sections | — | page, section | shown in citations | IT | unit + DB tests |
| Dense embeddings (multilingual, local ONNX) | providers.FastEmbedder | — | embedding REAL[] | stat tile "with semantic vectors" | IT (fake) + live | test_dense_retrieval_matches_urdu_question |
| Hybrid retrieval (FTS + dense + RRF, thresholds, dedupe, filters) | retrieval.py | GET /knowledge/search, POST /ask | GIN + REAL[] | filters: domain, crop | IT | DB tests, RAG_EVALUATION.md |
| Cross-encoder re-ranking | — | — | — | — | N | — |
| Query understanding (language, glossary, domain, crop, farm/dose/vet intent) | query.py | — | knowledge_queries.domain/crops | — | IT | unit tests |
| Multi-turn + follow-up rewriting | answer.py, generation.rewrite | conversation_id | knowledge_conversations | thread + history sidebar, delete | IT (deterministic) + live (LLM) | test_ask_extractive_abstain_followup… |
| Clarifying questions | answer.py | status `clarify` | — | "Needs more detail" | IU | — |
| Grounded generation with citations | generation.py | POST /ask | answer, citations | AnswerCard, [S#] chips | IT (fake LLM) + live Groq | test_llm_answer_is_validated, eval run |
| Citation validation, groundedness, abstention | generation.validate | meta.warnings, grounded_share | meta | warning list | IT | unit + DB tests |
| Dose guard + refusal + escalation (hard rule 2) | generation, answer | meta.escalate_to_expert | — | "Ask an expert" badge | IT | unit + DB tests, live copper question |
| Open cited source (passage + neighbours, original link, stored copy) | router.open_chunk, download_file | GET /chunks/{id}, GET …/file | — | "Open source" dialog | IT (API) + e2e | test + knowledge.spec.ts |
| Farm-specific context (owner-scoped) | farm_context.py | farm_context auto/on/off | reads farms/fields/cycles/soil/economics/crop doctor | "Your farm records used" panel | IT | test_farm_context_is_owner_scoped |
| Urdu / Roman Urdu questions, Urdu answers (RTL) | query, generation | language auto/en/ur | language | language select, RTL rendering | IT (dense) + live (Groq) | DB test, e2e screenshot |
| Voice-ready (speech text; TTS playback) | meta.speech_text | — | — | Listen button, mic input (browser) | IU (browser TTS mocked in tests) | voice.test.tsx |
| Copy / feedback | — | POST /queries/{id}/feedback | feedback_rating | buttons | IT | DB test |
| Knowledge dashboard metrics (real) | router.stats | GET /knowledge/stats | — | stat tiles + provider line | IT | DB test |
| Retrieval analytics (volume, outcome, domains, languages, latency p50/p95, no-result, source usage, feedback, ingestion, tokens) | router_admin.analytics | GET /knowledge/analytics | knowledge_queries | Analytics tab (admin/expert) | IT | DB + frontend tests |
| Agent integration | agents/tools._knowledge uses hybrid retrieval | /agent/run | — | Agents page | IT | test_agents_api.py |
| Evaluation framework (retrieval + generation) | scripts/rag_eval.py | — | read-only | — | IU (dev set, assistant labels) | eval/results/*.json |
| Provider abstraction (LLM none/groq/xai/ollama/compatible; embeddings none/fastembed) | providers.py | stats.providers | — | provider line | IT (fallback unit test) | — |
| Admin UI for roles | — | — | — | — | N (CLI `scripts/set_role.py`) | — |
| Pakistan-specific / expert-reviewed sources | — | — | — | — | B (licences/permission + expert time) | SOURCE_REGISTER.md |

## Acceptance criteria (owner brief)
| # | Criterion | Status |
|---|---|---|
| 1 | Admin registers a legitimate source | Done via UI (ADMIN) and audited CLI; 18 registered via CLI because no admin account was available to the assistant (role change needs the owner) |
| 2 | Provenance + licence recorded and verified | Done; verification by the assistant on the owner's instruction, **owner to confirm** |
| 3 | Ingested and indexed | Done: 18/18 indexed, 276 chunks, 276 vectors |
| 4–5 | Natural-language question → relevant passages | Done; dev-set hybrid hit@5 0.70–0.74, source-hit@5 0.96 |
| 6–7 | Grounded LLM answer with verifiable citations | Done (Groq gpt-oss-120b); 17/27 dev answers passed checks |
| 8 | User opens the cited source | Done (passage viewer + original URL) |
| 9 | Abstains on insufficient evidence | Done; 6/6 unanswerable dev questions abstained |
| 10 | Follow-up question | Done (LLM rewrite, deterministic fallback) |
| 11 | Farm retrieval respects tenant isolation | Done + tested |
| 12 | Urdu and English tested | Done for retrieval (tests) and generation (live); Urdu answer quality not human-reviewed |

## Deployment requirements
`EMBEDDING_PROVIDER=fastembed` (first run downloads ~220 MB to `backend/var/models/embeddings`), optional `LLM_PROVIDER` + `LLM_API_KEY` (+ `LLM_MODEL`, `LLM_FALLBACK_MODEL`), migration 0011, worker running. RAM: +~0.5 GB per process that loads the embedder (API and worker).

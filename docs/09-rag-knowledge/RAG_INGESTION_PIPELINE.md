# RAG ingestion pipeline (2026-11-24)
Summary: how a document becomes searchable, what is recorded, and what is not implemented.

## Lifecycle
`registered (unverified)` → file uploaded (stored, hashed; NOT indexed) → licence review (`licence_verified` / `content_reviewed` / `blocked`, note required) → job `knowledge.ingest` queued → worker: `processing` → `indexed` | `failed`.
A verified source with a file is queued automatically on verification; a new file = new `version` (chunks replaced atomically in one transaction; old file deleted).

## Steps (worker, `ingestion.handle`)
| # | Step | Implementation | Status |
|---|---|---|---|
| 1 | Upload | `POST /knowledge/sources/{id}/file` (ADMIN), ≤ `KNOWLEDGE_UPLOAD_MAX_BYTES` (20 MB) | Implemented + tested |
| 2 | Source registration + provenance | title, publisher, author, year/date, URL, retrieved_at, language, country/region, domain, crops, document type, licence + URL, commercial use, attribution, version | Implemented + tested |
| 3 | Type check | extension allow-list + magic bytes (`%PDF-`, ZIP for DOCX, no NUL in text formats) | Implemented + tested |
| 4 | Text extraction | pypdf (per page), python-docx (heading styles + tables), stdlib HTML parser (drops script/style/nav/footer), CSV rows as `column: value` | Implemented; PDF path not exercised on a real PDF yet |
| 5 | OCR for scanned PDFs | **Not implemented** — job fails with `no_text_layer` (never indexes nothing silently) | Not implemented |
| 6 | Table extraction | DOCX tables → `cell | cell` rows; CSV table-aware sections (40 rows, column names kept); PDF tables only as extracted text | Partial |
| 7 | Cleaning | NFKC, de-hyphenation across lines, control chars removed, whitespace normalised | Implemented + tested |
| 8 | Language detection | Arabic-script ratio → `ur`, else `en` (per chunk) | Implemented (heuristic) |
| 9 | Section-aware chunking | headings (markdown, numbered, ALL CAPS, DOCX/HTML headings) → sections; ≤220 words, 40-word overlap, never across page/section | Implemented + tested |
| 10 | Metadata enrichment | chunk: page, section, language, content hash, source version | Implemented |
| 11 | Embeddings | `"{source title} - {section}\n{text}"` (contextual header) → multilingual MiniLM, L2-normalised, stored with model name | Implemented + tested (fake embedder) and live |
| 12 | Indexing | tsvector (generated column, GIN) + REAL[] vectors | Implemented |
| 13 | Duplicate detection | file SHA-256 unique (409 `duplicate_document`); chunk content hash within a source | Implemented + tested |
| 14 | Status tracking | `ingest_status`, `ingest_error`, `ingest_log` (last 40 events), `chunk_count`, `indexed_at` | Implemented + tested |
| 15 | Failed-job recovery | DB queue retries with backoff (10 s, 60 s, 5 min); bad files fail immediately (no pointless retries); stale running jobs reclaimed | Implemented |
| 16 | Reprocessing | `POST …/reprocess` (ADMIN) or `scripts/knowledge_import.py --reindex-all` | Implemented + used (re-index after the contextual-header change) |
| 17 | Version tracking | `version` on source + `source_version` on chunks | Implemented + tested |
| 18 | Deletion + index cleanup | chunks by FK cascade, stored file deleted, audit event | Implemented + tested |

## Operator import (bulk)
`backend/scripts/knowledge_import.py <manifest.json> --files <dir>` registers each manifest entry (provenance + licence decision + review note), stores the file, records audit events (`via=cli`), applies the licence decision and queues indexing. Idempotent by file hash. Manifest: `docs/09-rag-knowledge/source_manifest.json` (metadata only; files in git-ignored `var/knowledge-sources/`).

## Library as of 2026-11-24
18 sources, 276 chunks, 276 embedded — see SOURCE_REGISTER.md. Retrieved with polite rate-limited requests (Wikipedia API honoured `Retry-After`).

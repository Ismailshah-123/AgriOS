# Knowledge source register (FR8) — updated 2026-11-24
Summary: what is in the verified library, under which licence, and who verified it. The machine-readable record is `source_manifest.json` (+ the `knowledge_sources` table, which also holds the review note and processing log).

## Licence verification note (owner must confirm)
All 18 sources were licence-checked on 2026-11-24 by the AI coding assistant **on the owner's explicit instruction** ("verify + note it"). Status is `licence_verified` (searchable). **None is `content_reviewed`**: no agronomist has reviewed the content. The owner should confirm the licence decisions before the viva.

## Indexed sources (18)
| Source | Publisher | Licence | Commercial use | Domain | Chunks |
|---|---|---|---|---|---|
| Phytophthora infestans; Alternaria solani; Septoria lycopersici; Corynespora cassiicola; Bacterial leaf spot of peppers and tomato; Tomato yellow leaf curl virus; Tomato mosaic virus; Tetranychus urticae; Helicoverpa armigera; Wheat leaf rust; Integrated pest management | Wikipedia (Wikimedia Foundation), specific revisions (`?oldid=` URLs in the manifest) | CC BY-SA 4.0 | allowed with attribution + share-alike | plant_protection | see Sources tab |
| Soil salinity; Soil pH | Wikipedia | CC BY-SA 4.0 | allowed | soil_science | |
| Drip irrigation; Surface irrigation; Evapotranspiration | Wikipedia | CC BY-SA 4.0 | allowed | irrigation_water | |
| Crop rotation | Wikipedia | CC BY-SA 4.0 | allowed | crop_science | |
| Integrated Pest Management (IPM) Principles | US EPA | public domain (US federal work, 17 U.S.C. §105) | allowed | plant_protection | |
Total 276 chunks. Excluded: "Passalora fulva" (tomato leaf mould) — 22-word stub, not enough content.
Attribution is stored per source and shown in the passage viewer. Text is a plain extract (references section removed).

## Limits of this library (say this in the demo)
- General, global encyclopaedic/agency content; **not Pakistan-specific**, no local varieties, calendars or recommendations.
- No doses: AgriOS strips any rate from answers by design.
- Coverage gaps: leaf mould, nutrient management, economics, weather risk, livestock domains have no source yet.

## Candidates still unverified (not ingested)
| Title | Publisher | Note |
|---|---|---|
| FAO Irrigation and Drainage Paper 56 | FAO, 1998 | © FAO; licence for reuse not verified |
| FAO open-access publications (CC BY-NC-SA 3.0 IGO) | FAO | verify each; non-commercial only |
| Punjab / Sindh agriculture department advisories | provincial governments | permission likely needed |
| University extension guides | various | usually copyrighted; check terms |

## How to add a source
UI (ADMIN): Agricultural Knowledge → Sources → Register source → open it → upload file → write the licence evidence → Verify licence (indexing starts automatically).
CLI: add an entry to `source_manifest.json`, put the file under `var/knowledge-sources/`, run `cd backend; uv run python scripts/knowledge_import.py ../docs/09-rag-knowledge/source_manifest.json --files ../var/knowledge-sources`.

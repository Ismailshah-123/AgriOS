# DATA_GOVERNANCE.md — provenance, consent, retention
Summary: how data is sourced, documented, labelled, protected and retired.

## Dataset provenance
Per dataset: name, version/download date, source URL, licence text, checksum, counts per class, intended use, restrictions. Prefer original source over re-uploads (licences differ). Exclude anything lacking licence permitting academic use + derived models. Dataset card in `/docs` (template: proposal Appendix F).

## Data classes
| Class | Examples | Rule |
|---|---|---|
| Public datasets | PlantVillage, PlantDoc | Read-only raw; not in Git |
| Farmer data | farms, activities, costs, photos | Consent; owner-only access |
| Retrieved | NASA POWER, Open-Meteo, SoilGrids | Label `retrieved`/`inferred`; cache; note gridded |
| Expert labels | corrected labels | Credit reviewer; used only as stated |
| Simulated | sensors | `is_simulated=true`, visible label |
| Knowledge sources | FAO, PARC, provincial | Licence + provenance recorded or not ingested |

## Consent and privacy
- Photos/records not used for training without recorded `consent_flag`.
- Strip EXIF/location from uploads. Store coarse farm location only.
- Minimal personal data. No personal data in logs beyond need.
- User study: supervisor-approved consent, anonymised, voluntary.

## Retention
Images: retention period set in config (default 12 months, documented); deletion on user request removes image + derived artifacts; audit events keep ids not content. Backups encrypted, restore tested before demo.

## Labelling of values
Every stored measurement: `data_origin`, unit, date, source. Never impute silently.

## Retraining rule
Documented trigger only (drift signal + enough consented expert-labelled data). Never automatic. New model = new immutable version.

## Checklist before any dataset enters the repo pipeline
[ ] licence read and recorded  [ ] classes verified  [ ] checksum  [ ] duplicates grouped  [ ] split file frozen  [ ] dataset card written

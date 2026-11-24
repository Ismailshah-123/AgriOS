# PRODUCT_REQUIREMENTS.md — features, roles, acceptance
Summary: priorities P0-P3, roles, functional requirements with acceptance criteria, non-functional targets, explicit non-claims.

## Priorities
- P0: farm records; Crop Doctor (independent model, confidence, explanation); focused soil intelligence; irrigation + fertilizer calculators; verified RAG; one real agent; model + system evaluation.
- P1: risk indicators, economics, expert review, offline foundation, weather integration, Irrigation agent.
- P2: NDVI prototype, small knowledge graph, simulator, extra agents.
- P3 future: real IoT, drones, marketplace, all-crop coverage, autonomous control.
Cut order if late: Sindhi speech, full offline sync, satellite/drone, marketplace, dashboard polish, extra crops. Never cut: dataset records, honest evaluation, uncertainty handling, citations, access control, tests.

## Roles
Farmer (own data), Expert (assigned cases only), Admin (users, sources, models, audit).

## Functional requirements + acceptance
| ID | Requirement | Pri | Accept when |
|---|---|---|---|
| FR1 | Register/login/roles | P0 | RBAC tests pass; other users' data returns 404 |
| FR2 | Farm, field, crop cycle CRUD | P0 | Ownership enforced; units acre/kanal/marla/ha round-trip |
| FR3 | Upload image -> diagnosis or abstention | P0 | 4 result states reachable; model version stored |
| FR4 | Grad-CAM + SHAP with limits note | P0 | Rendered; limits text shown |
| FR5 | Irrigation ETc=Kc*ET0, show inputs/assumptions | P0 | Matches FAO 56 worked examples |
| FR6 | Fertilizer from cited table | P0 | Refuses if no source stored; hand cases pass |
| FR7 | Soil tests + pH/EC flags | P0 | Boundary tests pass |
| FR8 | Cited Q&A or "No verified guidance found" | P0 | Verifier tests pass |
| FR9 | Agent with tools, approval, audit | P0 | 100% writes approved + logged |
| FR10 | Expenses/harvest/profit/break-even | P1 | Reconciles with spreadsheet |
| FR11 | Heat/water/drought/disease-weather indicators | P1 | Labelled "indicator", never "diagnosis" |
| FR12 | Expert queue + corrected label | P1 | Outcome recorded |
| FR13 | Offline drafts + sync + conflict | P1 | No loss, no duplicates |
| FR14 | Weather adapter | P1 | Cache + fallback |
| FR15-17 | Map/NDVI, simulator, sensor sim | P2 | Simulated labelled |

## Non-functional
Security per SECURITY.md. Privacy: coarse location, consent flag for image reuse. Reliability: works with LLM disabled. Usability: mobile-first, EN/UR. Reproducibility: seeds, configs, hashes, immutable model versions. Transparency: sources, assumptions, uncertainty on every recommendation.

## Must NOT claim
Detects all crops/diseases; field accuracy = lab accuracy; sensors/drones connected; yield/income improvement; multimodal gain without paired data.

## Demo flow (10 steps)
Register + farm/field/cycle -> log activity -> clear tomato photo (suggestion, Grad-CAM, cited guidance) -> blurry photo (retake) -> non-plant (refuse) -> expert review -> irrigation + fertilizer calc -> cited Q&A + unsupported question -> agent run + approval + audit log -> profit summary + offline sync.

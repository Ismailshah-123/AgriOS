# Analytics coverage matrix (2026-11-24)
Summary: every KPI and chart in the UI, its API source, and its test status. Rule: a figure is shown only when it is a count or sum of stored records (or a cited calculation); anything the system does not record is listed as "not available", never estimated. Charts follow the dataviz rules: single-series, one brand hue, zero-based, value text on every mark, hover/focus tooltip, no dual axes.

Status: **IT** implemented + automated test · **I** implemented, not yet browser-verified · **NA** not available (data not recorded) · **NI** not implemented.

| Page | KPI / chart | Source API | Status | Test |
|---|---|---|---|---|
| Overview | Farms, fields, area, growing, planned (tiles) | GET /overview counts | IT | overview.test |
| Overview | Module status card (cases, soil tests, weather-ready farms, ETc-ready cycles, agent approvals) | GET /overview intelligence | IT | overview.test, BE test_overview_api |
| Overview | Growing area, recorded costs + revenue, profit/loss, cases with an expert (tiles) | GET /analytics | IT | overview.test, BE test_analytics_api |
| Overview | Growing area by crop (bars) | GET /analytics area_by_crop | IT | overview.test |
| Overview | Crop Doctor cases per month, last 6 months (columns) | GET /analytics cases.by_month | IT | overview.test |
| Overview | Cases by status (bars) | GET /analytics cases.by_status | IT | overview.test |
| Overview | Costs by category (bars), profit by crop cycle (table) | GET /analytics economics | IT | overview.test |
| Overview | Weather alerts count | — | NA: weather is fetched per farm on demand; no stored alert history | — |
| Overview | Date / farm filters | — | NI: analytics are all-time per account; filters need query params on /analytics | — |
| Crop Doctor | Case counts, awaiting, follow-up (tiles) | GET /cases/summary | IT | crop-doctor.test |
| Crop Doctor | Diagnosis distribution, confidence distribution | — | NA: no model registered, so no predictions exist | — |
| Crop Doctor | CAM heatmap (owner + expert) | GET /cases/{id}/explanation, /review/cases/{id}/explanation | IT (test double only) | crop-doctor.test, BE tests |
| Soil | Latest values, interpretation, any-measure trend (pH, EC, OM, OC, P, K) | GET /fields/{id}/soil-summary | IT | intelligence.test |
| Soil | Cross-field comparison | — | NI | — |
| Weather | Current, temperature range + rainfall charts, risk indicators | GET /weather | IT | intelligence.test |
| Irrigation | Daily ETc range chart + table (stage, Kc, ET0, rain) | GET /fields/{id}/water-demand | IT | intelligence.test, BE FAO-56 tests |
| Economics | Cost, revenue, profit/loss, cost per acre, break-even (tiles) | GET /crop-cycles/{id}/economics | IT | economics-review.test |
| Economics | Costs by category (bars) | same | I | covered by page render tests |
| Economics | Financial trend over time | — | NI (dates exist; needs a monthly series) | — |
| Agents | Requests by type (last 20), proposals by outcome (bars) | GET /agent/runs, /agent/actions | IT | intelligence.test |
| Knowledge | Registered, verified, awaiting review, indexed passages (tiles) | GET /knowledge/stats | IT | economics-review.test, BE test_knowledge_api |
| Knowledge | Search volume, no-result rate, latency, ingestion jobs | — | NA: not recorded (shown as "Not tracked yet") | — |
| Expert review | Queue size and waiting-since | GET /review/queue | IT | economics-review.test |
| Expert review | Turnaround statistics | — | NI (timestamps exist: request audit event + review created_at) | — |

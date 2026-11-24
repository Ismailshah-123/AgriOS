# Frontend SaaS transformation audit (2026-11-24)
Summary: page-by-page state of the React app after the overnight sprint and this session, with the backend data each page uses, what was added, and what is still missing. Status: **IT** implemented + automated tests · **I** implemented, browser check pending · **P** partial · **NI** not implemented.

## Design system (existing, reused — no second component library)
Tokens (warm neutral surfaces, forest-green primary, AA-verified), Inter, shadcn-style primitives (button, card, badge, dialog, confirm-dialog, form-field, input, empty-state, feedback/skeleton/error, origin-badge, stat-tile). Added this session: `components/charts/BarList` and `ColumnChart` (single-series, zero-based, value text on every mark, hover/focus tooltip, no new dependency). Shell uses logical CSS for RTL.

## Page matrix
| Page | Backend data | Existing before | Added (2026-11-23/24) | Still missing | Status |
|---|---|---|---|---|---|
| Overview | /overview, /analytics | counts, growing crops, upcoming dates, recent changes | live module-status card; analytics: KPI tiles, area by crop, cases/month, cases by status, costs by category, profit by cycle | date/farm filters; weather alert history (not stored) | IT |
| Farms / Fields / Cycles | /farms, /fields, /crop-cycles | full CRUD | cycle delete 409 message when it has records | per-farm statistics page, activity timeline | IT |
| Crop Doctor | /cases*, /review* | upload, history, detail, follow-up, retry | CAM overlay, Ask an expert + outcome, offline drafts (IndexedDB) + sync centre, client_id idempotency, voice for notes | diagnosis/confidence distributions (no model yet) | IT (offline IndexedDB: browser test pending) |
| Expert review | /review/* | — | queue, case view with photos/model output/heatmap, decision form; nav only for expert/admin | assignment, turnaround stats | IT |
| Soil | /soil-observations*, soil-summary | list, create, interpretation, pH chart | edit/delete, any-measure trend selector | cross-field comparison | IT |
| Weather | /weather | current, charts, indicators | — | stored alert history | IT |
| Irrigation | /fields/{id}/water-demand | card inside Weather | own page: daily ETc chart + table + exclusions | scheduling (net/gross depth) | IT |
| Nutrients (Preview) | /crop-cycles/{id}/fertilizer | placeholder | refusal page (no dose without reviewed table) | reviewed tables (human) | IT |
| Economics | /crop-cycles/{id}/economics, /expenses, /harvest-sales | placeholder | full page: tiles, records CRUD, costs-by-category chart, definitions | monthly trend, CSV export, what-if | IT |
| AI Agents | /agent/* | run, steps, approvals, history | decision history, catalogue, activity charts, voice input, listen-to-answer | tool-usage per step (needs runs' steps aggregated server-side) | IT |
| Knowledge (Preview) | /knowledge/* | placeholder | search + cited passages, register, library tiles, voice, listen | real corpus (licences), filters by crop/topic, telemetry | IT |
| Settings | /users/me | profile, password, language | Urdu hint updated | — | IT |
| Reports | — | placeholder (Planned) | — | not in FR list | NI |

## Cross-cutting
| Item | State |
|---|---|
| Urdu | navigation/shell + voice strings (39, pending native review); page content English |
| Voice | browser Web Speech (ur-PK / en-US): mic on Crop Doctor notes, Agents, Knowledge; listen on agent answers and passages; fallbacks tested with mocks; real-device testing not done |
| Responsive | see RESPONSIVE_UI_AUDIT.md (8 viewports x 14 routes + RTL) |
| Tests | frontend 85/85 (13 files) at 01:15; backend see POST_OVERNIGHT_VERIFICATION.md |

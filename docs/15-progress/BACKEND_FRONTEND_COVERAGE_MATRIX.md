# Backend -> frontend coverage matrix (verified 2026-11-24 00:30)
Summary: every route in the live OpenAPI spec (64 + the hidden signed-file route; 61 at the first pass, +fertilizer, +2 knowledge) mapped to its frontend service, page, workflow and test. Source: `GET /api/v1/openapi.json` from the running API at revision 0009. Status: **OK** = reachable from the UI with an automated test · **Indirect** = data reaches the UI through another endpoint by design · **Service only** = typed client exists, no page needs it.

| Capability | Backend API | FE service | FE page | User workflow | Test | Status |
|---|---|---|---|---|---|---|
| Health / readiness | GET /health, /ready | system.ts | Status card (Settings) | see service state | SystemStatusCard.test | OK |
| Register / login / refresh / logout / me | POST /auth/*, GET /auth/me | platform.ts | Login, Register, UserMenu | sign up, sign in, stay signed in, sign out | auth.test, e2e | OK |
| Profile, password | PATCH /users/me, POST /users/me/password | platform.ts | Settings | edit name/locale, change password | auth.test | OK |
| Farms CRUD | /farms (5 routes) | platform.ts | Farms, FarmDetail, FarmFormDialog | create/list/edit/delete | farms.test, e2e | OK |
| Fields CRUD | /fields (5) | platform.ts | Fields, FarmDetail | create/list/edit/delete | fields-cycles.test | OK (GET /fields/{id}: service only) |
| Crop registry | GET /crops | platform.ts | CycleFormDialog | pick crop | fields-cycles.test | OK |
| Crop cycles CRUD | /crop-cycles (5) | platform.ts | CropCycles | create/list/edit/delete; 409 when it has cases/economics records | fields-cycles.test; BE test_economics_api | OK (GET /crop-cycles/{id}: list carries all fields) |
| Overview + intelligence | GET /overview | platform.ts | Overview | counts, growing crops, upcoming dates, module status | overview.test | OK |
| Crop Doctor cases | POST/GET /cases, /cases/summary, /cases/{id}, follow-ups, retry | cropHealth.ts | Crop Doctor overview, New assessment, History, Case detail | upload, track, follow up, retry | crop-doctor.test, e2e | OK |
| Analysis state | GET /cases/{id}/analysis | — | Case detail (embedded in case) | — | crop-doctor.test | Indirect |
| Model availability | GET /models/availability | — | Crop Doctor (via /cases/summary) | — | crop-doctor.test | Indirect |
| Explanation (CAM) | GET /cases/{id}/explanation | cropHealth.ts | Case detail heatmap | view heatmap | crop-doctor.test (test double) | OK, no real model yet |
| Case photos | GET /files/case-images/... (signed) | URLs in responses | all photo views | view photos | e2e | OK |
| Expert review: farmer | POST /cases/{id}/expert-review | cropHealth.ts reviewApi | Case detail ExpertPanel | ask an expert, see outcome | economics-review.test | OK |
| Expert review: expert | GET /review/queue, GET/POST /review/cases/{id} | cropHealth.ts reviewApi | /review, /review/cases/:id (nav for expert/admin only) | triage, decide, label, note | economics-review.test; BE test_expert_review_api | OK |
| Weather + risks | GET /weather | intelligence.ts | Weather | forecast, risk indicators, provider/stale states | intelligence.test | OK |
| Soil CRUD + summary | /soil-observations (5), /fields/{id}/soil-summary | intelligence.ts | Soil | add/edit/delete test, interpretation, trends | intelligence.test | OK (GET by id: service only) |
| Water demand (FAO-56) | GET /fields/{id}/water-demand | intelligence.ts | Irrigation, Weather card | daily ETc | intelligence.test; BE FAO-56 examples | OK |
| Agents | /agent/runs (3), /agent/actions (+approve/reject), /agent/catalogue | agents.ts | AI Agents | ask, see steps, approve/reject, decision history, catalogue | intelligence.test | OK |
| Economics | /crop-cycles/{id}/economics, /expenses (3), /harvest-sales (3) | economics.ts | Farm Economics | add/edit/delete costs and harvests, PKR summary | economics-review.test; BE test_economics_api | OK |
| Fertilizer (FR6) | GET /crop-cycles/{id}/fertilizer | inline (NutrientsPage) | Nutrient Management (Preview) | see refusal + escalation, never a dose | economics-review.test; BE test_fertilizer_api | OK (refusal only) |
| Knowledge (FR8) | GET /knowledge/search, /knowledge/sources | inline (KnowledgePage) | Agricultural Knowledge (Preview) | search, cited passages, source register | economics-review.test; BE test_knowledge_api | OK (empty verified library) |

## Gaps found in this pass and their state
| Gap | State |
|---|---|
| Static "Not connected" dashboard card | Fixed 2026-11-23 (Phase 5C) |
| Soil edit/delete, irrigation page, agent history/catalogue, CAM | Fixed 2026-11-23 (Phase 5C) |
| Economics had no backend or UI | Fixed 2026-11-24 (this sprint) |
| Expert review had no backend or UI | Fixed 2026-11-24 |
| Deleting a cycle with cases returned 500 | Fixed: 409 `cycle_not_empty` |
| Expert view shows no CAM heatmap (explanation endpoint is owner-only) | Fixed 2026-11-24: GET /review/cases/{id}/explanation (expert/admin, same visibility rule) + overlay in the expert case view |
| Nutrients (FR6), Knowledge (FR8) pages | Now real pages (Preview): refusal / empty verified library until reviewed tables and licensed sources exist. Reports stays Planned (not in the FR list) |
| No admin UI for roles; expert accounts via `backend/scripts/set_role.py` (audited) | Documented limitation |

# DESIGN.md — AgriOS UI/UX: professional, farmer-friendly, every feature
Summary: complete design spec. Direction, tokens, navigation, shared components, then one section per feature (screen, states, labels, acceptance), plus expert/admin consoles, offline, i18n/RTL, motion, accessibility, performance, and a release checklist. Build UI only from this file plus API_CONTRACTS.md.

## 1. Direction
- Look: professional agri-tech. Calm, confident, premium; deep green + warm neutrals, crisp cards, real crop photography on hero/empty states, subtle depth. Not toy-like, not generic admin template.
- Farmer-friendly: big targets, icon + short text, one primary action per screen, plain Urdu/English, minimal typing (pickers, steppers, camera), optional voice with text fallback.
- Honest: every value has origin badge + unit; confidence is worded, never absolute; no dose without citation.
- Cinematic polish (demo landing, dashboards, transitions) must never hurt speed or readability on a low-end phone.
- Mobile-first 360px. Tablet 768. Desktop 1280 (expert/admin primary).

## 2. Tokens (Tailwind theme + CSS vars)
- Color: primary `#1F7A3E`, primary-dark `#14532D`, accent gold `#C9A227`, ink `#0F1A14`, muted `#5B6B61`, surface `#F6F8F5`, card `#FFFFFF`, dark-bg `#0B120E`, dark-card `#121C16`, success `#1F7A3E`, warning `#B7791F`, danger `#B42318`, info `#1D5FA8`.
- Origin badges: measured green, farmer_entered blue, retrieved purple, inferred amber, simulated grey dashed + "SIMULATED".
- Type: Inter (EN), Noto Nastaliq Urdu (UR; line-height 1.9). Base 16px, scale 1.2, headings 600. Min body 16px, min control text 16px.
- Radius 14 cards, 10 inputs, full pills for chips. 4px spacing grid. Elevation: 2 levels only.
- Icons: lucide, 24px, always with label on primary nav.
- Dark mode + high-sun (extra-contrast) mode for outdoor use.

## 3. Navigation
- Farmer (bottom bar, 5): Home, Fields, **Doctor** (raised center), Tools, More. Top bar: farm switcher, offline chip, language toggle, bell.
- Expert / Admin: left sidebar on desktop, drawer on mobile.
- Back always visible. Max 3 taps to any core action. Breadcrumb on desktop.
- Global: command search (desktop), floating "Ask" button on Home/Fields/Tools.

## 4. Shared components (shadcn/ui base)
OriginBadge, UnitInput (unit picker + validation), ConfidenceMeter (words + bar), ResultCard (4 states), GradCamOverlay, ShapBar, SourceCitation (chip -> drawer), OfflineBanner, SyncChip, ApprovalDialog, AgentStepTimeline, AuditTable, StatTile, TrendChart (Recharts), MapView (GeoJSON), PhotoCapture, StageStepper, EmptyState (photo + one CTA), ErrorState (cause + retry), Skeleton, Toast, ConfirmSheet, LanguageToggle, ConsentSwitch, LimitsNote.
Rules: forms use steppers/pickers/segmented controls first; keyboard last. Number fields show unit inside field. Destructive actions need confirm sheet.

## 5. Screens by feature

### 5.1 Onboarding, auth, profile (FR1)
Splash -> language (Urdu/English, big cards) -> register/login (email/phone + password; show/hide) -> role fixed farmer -> short consent screen (photo reuse switch, off by default, plain text) -> create first farm wizard (3 steps).
States: wrong password, rate-limited (countdown), expired session (silent refresh then login).
Profile/Settings: language, units default (acre/kanal/marla/ha), text size, high-sun mode, consent toggles, data export, delete account/images.

### 5.2 Home (farmer)
Top: farm + current crop cycle card (crop photo, stage stepper, day count). Row of StatTiles: next task, water need today (simulated/estimated label), risk indicator, balance (profit so far). Primary tiles: "Check my crop" (opens Doctor), "Irrigation today", "Add activity", "Ask a question". Alerts strip (weather risk indicators, pending approvals, unsynced items). Recent activity feed.
Empty: no farm -> wizard CTA.

### 5.3 Farms and fields (FR2)
List of farms -> farm detail -> fields. Field card: name, area (user unit + ha), crop, stage chip. Add/edit field: name, area with unit picker (live conversion shown), optional boundary (draw on map or paste GeoJSON). Map shows boundary; coarse location notice "stored approximately for privacy".
Validation inline; duplicate names warned.

### 5.4 Crop cycle and activities (FR2)
Cycle creation: crop picker (cards with photo), variety (optional), sowing date (calendar), auto stage template. Timeline view: vertical, stages with dates, activities pinned, diagnoses and inputs as events. Add activity: type grid (sowing, irrigation, fertilizer, spray, weeding, harvest, note) -> quantity+unit -> date -> photo optional -> save (works offline). Edit history visible.

### 5.5 Soil records (FR7)
Add soil test: pH, EC, N, P, K, organic carbon, texture (picker), moisture, date, source (lab / farmer-entered / retrieved SoilGrids labelled "estimate, not a lab test"). Result view: value + range bar + flag chips (pH too low/high, EC high/salinity risk) with cited threshold source. Trend chart per field.

### 5.6 Weather and risk indicators (FR11, FR14)
Weather card: today + 7-day, source and retrieval time shown, "cached" badge when stale. Risk panel: Heat stress, Water stress, Drought, Disease-favourable weather. Each = level chip + inputs + threshold source. Wording: "Conditions favour…", never "disease present". No yield forecast.

### 5.6b Crop Doctor (FR3, FR4) — flagship
Flow: select field/cycle -> PhotoCapture (guide overlay: "one leaf, fill frame, daylight, steady") -> live quality hints (blur, light, leaf area) -> optional context card (stage prefilled, recent weather/soil shown with origin badges, editable) -> Analyse (progress, works offline = queued draft).
Result states (mandatory):
| State | UI |
|---|---|
| Accepted | Class name (EN/UR), ConfidenceMeter with words (likely/very likely), Grad-CAM toggle, context factors used (full/partial/none), cited guidance, LimitsNote, buttons: Save to cycle, Ask expert, Add to timeline |
| Retake | Reason + example good photo, big Retake button |
| Unsure | "No definitive diagnosis", shortlist with percentages, ask-more fields, Send to expert |
| Out of scope | "Not a supported crop or problem", supported list link, Send to expert |
Grad-CAM caption always: "Shows where the model looked. Not proof." Model version + date in footer (tap for model card summary). Feedback: "Was this right?" + expert outcome shown when ready. History list with filters. Guidance never shows dose unless cited; else "Ask an expert".

### 5.7 Irrigation (FR5)
Inputs prefilled from field/cycle/weather: ET0 (source), Kc (stage, source), effective rain (assumption text), efficiency (picker: flood/drip etc. with default). Output: big "Water needed" in mm and m3 per acre/ha/field, schedule calendar, formula drawer showing every step and assumption, Save plan (approval dialog if via agent). Label: estimate, not measured. Compare strategies (P1 simulation): fixed vs rule vs weather vs soil-moisture, chart marked SIMULATED.

### 5.8 Fertilizer (FR6)
Choose crop + target area + product (urea, DAP, etc. with nutrient %). Requirement comes only from a stored cited table; show source chip. Output: nutrient need, product kg (per acre and field), cost with editable price. If no source: card "No verified requirement stored" + expert CTA, no number. Show arithmetic drawer.

### 5.9 Economics (FR10)
Expenses (category grid, amount, date, field/cycle), revenue/harvest entry (quantity in maund/kg, price). Summary: cost per acre, revenue, profit/loss, break-even yield and price. What-if sliders (price, input cost) with assumptions panel; all labelled "estimate". Charts: cost breakdown donut, cumulative profit line. Export CSV/PDF.

### 5.10 Unit converter (shared)
Acre, kanal, marla, hectare, kg, maund, litre. Source of definitions shown. Reusable inline in every UnitInput.

### 5.11 Ask a question (FR8, RAG)
Chat-style input (text, voice optional). Answer card: short answer, SourceCitation chips (title, publisher, year) -> drawer with passage. No support: "No verified guidance found" + Ask an expert. Suggested questions by crop/stage. Language follows UI; sources may be English (label). Never shows a dose without table citation.

### 5.12 Agents (FR9)
Entry: "Assistant" cards (Crop Health Assistant P0, Irrigation Planner P1). Run screen: AgentStepTimeline (plan, tool calls with inputs/outputs summarised, validation), live status. Approval: ApprovalDialog shows exact change preview (e.g., irrigation plan or reminder), Approve/Reject, nothing commits before. History of runs with audit link. Errors: "Couldn't complete, nothing was changed".

### 5.13 Tasks, reminders, notifications
Task list grouped Today/This week/Overdue, stage-based suggestions marked "suggested". Reminders created only after approval. Notification center with types (case reply, approval needed, sync done, weather indicator). Push optional.

### 5.14 Offline and sync (FR13)
OfflineBanner: "You're offline. Saved on this phone, not yet uploaded." SyncChip per item (pending, syncing, synced, conflict). Sync center: queue list, retry, export backup. Conflict sheet: both versions side by side, pick one. Photos queued with size shown. Service worker caches shell + last data.

### 5.15 Language and voice
EN/UR toggle anywhere; layout mirrors (RTL) fully. Urdu numerals optional. Voice input (browser speech) with text always editable; show "voice may misrecognise farm terms". Sindhi = future (do not show).

### 5.16 Map, NDVI, simulator, sensors (P2, clearly marked)
Field map with boundary; NDVI time series only if implemented, labelled "satellite-derived, retrieved". Decision simulator: transparent sliders, "assumption-based, not a validated model". Sensors: show only with SIMULATED badge on every value and chart.

## 6. Expert console (FR12) — desktop first
Queue table: priority, crop, age, status, assignee, filters. Case detail split view: image (zoom, pan, Grad-CAM overlay toggle) | prediction, calibrated confidence, OOD score, shortlist, SHAP, context with origin badges | response panel: corrected label (dropdown + other), decision, note, "use for training" shows consent state, Submit. Keyboard shortcuts (J/K next/prev, 1-9 label). Case chat with farmer. Outcome recorded + audit event. Cinematic dark theme allowed here.

## 7. Admin console
| Area | Content |
|---|---|
| Users | table, role change, deactivate, last login |
| Knowledge sources | upload, metadata (publisher, year, licence required), review status, ingest status, chunk preview |
| Model versions | list, metrics link, calibration temperature, threshold, checksum, status, Activate (confirm) |
| Monitoring | confidence distribution, rejection rate, expert disagreement per version, drift flag, latency, errors |
| Audit log | filter by actor/action/date/entity, expandable JSON, export |
| System health | api/db/model/LLM/weather adapter status |

## 8. Demo/marketing landing (cinematic)
Full-bleed field footage/photography hero, short value line, 3 pillars (Records, Crop Doctor, Cited advice), live demo button, honest "what it does not do" strip, VertexData/FYP credits. Lazy-load media; respects reduced motion; Lighthouse perf >= 85 mobile.

## 9. Interaction rules
- Loading: skeletons, never blank. Inference shows steps ("checking photo, analysing, checking confidence").
- Errors: say what happened + what to do + retry; never stack traces.
- Empty states: real photo + one CTA.
- Confirm only destructive actions. Undo toast for deletes (5s).
- Autosave drafts on all forms.
- Every number: unit + origin + date where relevant.

## 10. Motion
150-250ms ease-out; page transitions slide 8px + fade; result card reveal staggered; map/chart draw-in. Heavy effects only on landing and desktop dashboards. Honour prefers-reduced-motion.

## 11. Accessibility
WCAG AA contrast, 48px targets, visible focus, labels on every input, alt text, no color-only meaning (icons + text), screen-reader order, text scales to 200%, voice optional.

## 12. Content style
Short sentences, grade-6 reading level, farmer words first (e.g., "leaf spots"), term + explanation on first use. Uncertainty words: likely / possible / not sure. Never "diagnosis is certain". Error and safety copy stored in i18n files (EN+UR), reviewed by a native speaker.

## 13. Performance
Initial JS <= 200KB gz for farmer shell, route-level code splitting, images responsive + WebP, camera upload compressed client-side (EXIF stripped server-side too), 60fps scroll on low-end Android, works on 3G (core flows <= 5s after load).

## 14. Acceptance (release checklist)
[ ] Every feature in section 5-8 has a screen with loading/empty/error/offline states
[ ] All screens verified EN and UR (RTL), light/dark/high-sun
[ ] Origin badges + units on every value; simulated values labelled
[ ] No dose anywhere without citation
[ ] Crop Doctor 4 result states reachable and tested (Playwright)
[ ] Approval dialog precedes every agent write
[ ] Offline: create, reconnect, sync, conflict all demonstrated
[ ] Lighthouse mobile perf >= 85, a11y >= 95
[ ] Usability pass with 5-10 users, SUS recorded

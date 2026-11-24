# DESIGN_NAVIGATION_NOTES.md — Phase 2 navigation and design decisions
Summary: where the Phase 2 frontend follows DESIGN.md, and where it deviates and why. DESIGN.md itself is unchanged; fold these into it once reviewed.
Status: Proposed for review (2026-11-22).

## Information architecture
| Area | DESIGN.md | Phase 2 implementation | Reason |
|---|---|---|---|
| Desktop navigation | Left sidebar (expert/admin primary) | Left sidebar for all roles, grouped: Overview · Farm · Intelligence · Planning · AI & Knowledge; Settings in the account menu | 14 modules need grouping to stay scannable; groups mirror backend module boundaries |
| Phone navigation | Bottom bar: Home, Fields, **Doctor**, Tools, More | Bottom bar: Home, Fields, Doctor, **Cycles**, More | "Tools" would open only unavailable calculators today; Crop Cycles is the core working flow. Restore "Tools" when irrigation/nutrient calculators ship |
| Module status | not specified | Every unbuilt module has an entry page with a **Planned** or **Preview** pill, a description of what it will do (taken from the proposal), and no inputs, numbers or fake actions | Honest status without hiding the product scope (FEATURE_STATUS rule) |
| Home | Farm + crop cycle card, stat tiles, alerts | Overview built from real API data only (Phase 2.5); weather/water/finance tiles say "not connected yet" instead of showing values | CLAUDE.md hard rules 1 and 4 |

## Visual tokens
| Token | DESIGN.md | Now | Reason |
|---|---|---|---|
| surface | #F6F8F5 (green-grey) | #F7F6F2 (warm neutral) | Requested warm neutral surfaces; muted text keeps 5.22:1 |
| border | #E2E8E3 | #E6E3DC (+ strong #D4D0C6 for inputs) | Matches warm surface; inputs need a visible edge |
| warning | #B7791F | #8A5A12 | #B7791F on its soft background is 3.38:1 (fails WCAG AA); new value 5.41:1 |
| accent gold | #C9A227 | unchanged, decoration only | 2.42:1 on white: never used for text |
| Font | Inter | Inter Variable, self-hosted (@fontsource) | Was referenced but never loaded; no CDN, so it works offline (PWA) |

## Not yet done (tracked)
Urdu/RTL interface, dark and high-sun modes, offline PWA, the 200%-text audit, and a usability pass. The language preference is stored but the UI is English only and says so.

# EN/UR translation review register (created 2026-11-24)
Summary: what the Urdu UI covers, how it works, and which strings need human review before any claim of Urdu support.

## Implemented (foundation only)
- `frontend/src/i18n/messages.ts` (UR catalogue), `useT()` (English fallback for every missing key), `useDocumentLanguage()` sets `<html lang dir>` (`ur` + `rtl`).
- Language comes from the saved profile (`users.locale`, Settings page).
- Covered: navigation labels, nav group headers, status pills, mobile bottom bar, menu open/close labels. Shell layout uses logical CSS (`start-0`, `ms-*`, `border-e`) so it mirrors in RTL.
- NOT covered: page content, forms, errors, Crop Doctor/soil/weather/agent text, backend messages. These remain English. Many components still use physical classes (`ml-*`, `pl-*`) and are not yet RTL-checked.

## Review status
All 39 Urdu strings (31 navigation/shell + 8 voice) in `messages.ts` were drafted by the development assistant: **PENDING native-speaker review**. Strings marked `*` in the file (crop cycles, soil, irrigation, nutrients) also need an agronomist. No agronomic advice is ever machine-translated.

| Reviewer | Date | Result |
|---|---|---|
| (pending) | | |

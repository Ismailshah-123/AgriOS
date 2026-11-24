# Urdu voice interaction — audit and plan (2026-11-24; nothing implemented yet)
Summary: what exists, the provider options with cost and privacy trade-offs, and the smallest real implementation. Decision needed from the owner on the provider before building.

## Audit
No speech code exists: no SpeechRecognition, speechSynthesis, getUserMedia or audio upload anywhere in frontend/src or backend/app (searched 2026-11-24). The text paths a voice layer would feed already exist: Crop Doctor observations (notes), AI Agents message box, Knowledge search box; text answers to read aloud exist for agents, knowledge passages, weather indicators and Crop Doctor status/limits.

## Provider options
| Option | Urdu speech-to-text | Urdu text-to-speech | Cost | Privacy / offline | Notes |
|---|---|---|---|---|---|
| A. Browser Web Speech API | `SpeechRecognition` with `lang="ur-PK"` in Chrome and Edge (Android + desktop); NOT Firefox; Safari partial | `speechSynthesis` uses voices installed on the device; Urdu voice availability varies by device/OS | Free to AgriOS | Chrome sends audio to Google, Edge to Microsoft (must be disclosed); needs internet for recognition | Smallest real implementation; no backend change |
| B. Cloud STT/TTS via backend (e.g. Azure Speech, Google Cloud) | ur-PK supported by both (verify current docs before choosing) | Neural Urdu voices | Paid per minute/character; needs keys and budget (project budget PKR 10-15k) | Audio leaves the device to the vendor; keys server-side | More consistent quality; adds an adapter, secrets, cost controls |
| C. Self-hosted (e.g. Whisper for STT) | Whisper supports Urdu | needs a separate TTS model | Free licence, but CPU/GPU load on the server | Audio stays local | Heavy for the 15.6 GB dev PC; latency on CPU |

## Recommended first step (Option A, with honest fallbacks)
1. `useSpeechInput(lang)` hook + `MicButton`: shows Listening / Stopped states, a permission-denied message, and "Voice input is not supported in this browser; please type" when the API is missing. Recognised text is placed in the text box for the farmer to check (never auto-submitted).
2. `SpeakButton`: reads a given text with the best `ur-PK` voice; Play / Stop / Repeat; if no Urdu voice exists, says so instead of reading Urdu with an English voice.
3. Wire into: Crop Doctor notes, AI Agents message, Knowledge search; speak buttons on agent answers, knowledge passages (quoted text only, citations kept on screen), weather indicators, Crop Doctor status.
4. Language follows the profile locale (ur default for Urdu users; English optional).
5. Tests: unit tests with a mocked SpeechRecognition/speechSynthesis (states, fallbacks, permission errors). Real Urdu recognition and voice quality can only be verified manually on real Android/desktop browsers; results must be recorded per device, not claimed from automated tests.

## Limitations to state in the UI and report
- Recognition quality for rural accents, Punjabi/Saraiki-influenced Urdu and farm terms is unknown until tested with users.
- Speaking an answer does not make its content more reliable; model and knowledge limits still apply and citations remain on screen.
- Option A does not work offline.

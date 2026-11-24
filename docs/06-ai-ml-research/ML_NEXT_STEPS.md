# ML next steps after the overnight sprint (2026-11-24)
Summary: what is ready, the exact supervised runbook for the remaining runs, the E3/E4/E6 decision for the owner and supervisor, and the Crop Doctor integration checklist. Experiment IDs follow the proposal: E1 custom CNN vs majority, E2 EfficientNet-B0 + MobileNetV3, E3 context-only tabular, E4 fusion, E5 calibration, E6 ablations, E7 OOD/rejection.

## 1. Safety tooling (new)
`ml/scripts/train_supervised.ps1` — starts ONE job; refuses below 8 GB available RAM or if another `agrios_ml.train/evaluate/ood` job runs; kills the whole process tree below a 1.5 GB floor (last.pt allows resume); `-WatchPid` attaches a second, detached watchdog to a running job. Kill, normal-exit and refusal paths verified on a dummy process (2026-11-24 00:11).

## 1b. Done 2026-11-24
- E2 MobileNetV3-Large trained (early stop after epoch 18, best epoch 14) and BOTH E2 arms evaluated on validation only: `ml/reports/E2_VALIDATION_COMPARISON.md` (EffB0 val macro-F1 0.9873, MNv3 0.9853; CPU p50 14.0 vs 10.5 ms). The pre-registered rule would prefer MobileNetV3 (gap 0.002 < 0.005, lower latency) — owner/supervisor to confirm in SELECTION.md; single seed caveat.

## 2. Runbook for the next supervised session (one job at a time, validation only)
| Step | Command (from `ml/`) | Pre-checks | Output |
|---|---|---|---|
| 0 | close games/browsers; `Get-CimInstance Win32_OperatingSystem` | >= 8 GB available; `nvidia-smi` no other job; D: free > 20 GB | — |
| 1 E1 | `.\scripts\train_supervised.ps1 -Config experiments\configs\E1_small_cnn_tomato_v1.json` | run dir absent | runs/E1_small_cnn_tomato_v1/seed42 |
| 2 E1 baseline | majority-class row from the validation split class counts (no training) | — | in the E1 report |
| 3 val eval | `.venv\Scripts\python.exe -m agrios_ml.evaluate runs\<exp>\seed42 --report-dir reports\<exp>\val` for each of E1, E2-EffB0, E2-MNv3 | no training running | metrics.json (val + temperature-calibrated val, ECE/Brier), confusion matrix, reliability, curves |
| 4 select | write `ml/reports/SELECTION.md` BEFORE any test access (rule: best calibrated val macro-F1; within 0.005 prefer lower CPU latency) | — | decision note |
| 5 env | `uv add onnx` (no job running) | — | ml/.venv |
| 6 final (once) | `evaluate ... --final` for the selected model only | SELECTION.md exists | test + external metrics |
| 7 package/OOD/parity/register | POST_TRAINING_RUNBOOK.md steps 5-8, plus an upload-path parity test (original -> WebP 2048 -> ONNX vs torch on validation images) | — | package, ood_metrics.json, registered model |
Safe stop at any point: the supervisor kills the tree; re-running the same config resumes from last.pt. Never delete a run directory.

## 3. E3 / E4 / E6 — decision needed (owner + supervisor; not taken here)
The proposal and AI_ML_RESEARCH_PLAN define E3 (context-only tabular), E4 (fusion) and E6 (context ablations) as Pathway A experiments that need PAIRED image + context records. None exist (dataset audit: public leaf-image datasets carry no field context).
- Option 1 — record as not applicable: E3/E4/E6 marked "blocked: no paired data (Pathway B)", with the dataset audit as evidence; no multimodal claim. Needs supervisor sign-off.
- Option 2 — separately labelled scenario study: a context-rule evaluation on hand-written scenarios (e.g. the existing weather/soil indicators vs expected flags), explicitly NOT E3/E4/E6 and making no claim that context improves diagnosis. Only if the supervisor accepts it as a methodology substitute.
Nothing is trained for E3/E4/E6 until this is decided. No paired data may be synthesised.

## 4. Crop Doctor real-model integration checklist
| Item | State 2026-11-24 |
|---|---|
| Model registry + versions, checksum, availability states | Implemented + tested (no model registered) |
| Canonical preprocessing (Resize short 256 + CenterCrop 224, ImageNet norm) | In package.json contract; ONNX preprocess implemented |
| WebP 2048 upload path vs JPEG q95 training parity | NOT tested (needs the package) |
| Real inference (ONNX Runtime, CPU) | Code + unit tests; never run on a trained model |
| Class mapping | tomato_v1_classes.json (10 classes) -> package labels |
| Calibrated confidence (temperature from val) | evaluate.py computes; package.py stores; not yet run |
| OOD rejection (energy, threshold from val) | ood.py ready; not yet run |
| Grad-CAM (CAM for GAP+linear) | Computed in predictor; endpoint + overlay done; not verified on real images |
| Explanation endpoint / frontend overlay | Done (test double) |
| Persistence, error handling, model-unavailable state | Done + live-verified (model_unavailable) |
| Expert escalation | Done (FR12) |
No real diagnosis may be claimed until a registered package processes a real image end to end.

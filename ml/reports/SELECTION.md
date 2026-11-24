# Model selection — tomato_v1 (written 2026-11-24, BEFORE any test or external-set access)

**Selected: `E2_mobilenet_v3_large_tomato_v1` (seed 42, best epoch 14).**

## Rule applied (pre-registered in docs/06-ai-ml-research/POST_TRAINING_RUNBOOK.md §3)
Highest calibrated validation macro-F1; if candidates are within 0.005, prefer the lower CPU
latency / smaller model (serving is CPU ONNX Runtime).

## Evidence (validation split only; ml/reports/E2_VALIDATION_COMPARISON.md and each arm's val/metrics.json)
| candidate | val macro-F1 (temperature-calibrated) | CPU p50 batch-1 | checkpoint |
|---|---|---|---|
| E2_efficientnet_b0_tomato_v1 | 0.9873 | 14.0 ms | 16.4 MB |
| E2_mobilenet_v3_large_tomato_v1 | 0.9853 | 10.5 ms | 17.1 MB |

Gap 0.0020 < 0.005, so the rule selects the lower-latency candidate: MobileNetV3-Large.

## Not candidates
- E1 (custom CNN baseline): not trained (no run directory). Owner instructed on 2026-11-24 not to
  start new training today; E1 remains PENDING and is not part of this selection.

## Caveats (carry into every report)
- Single seed; the 0.002 difference is within plausible seed noise — the rule is a tie-break.
- Temperature fitted on the same validation set (in-sample calibration); E5 must report test calibration.
- Validation is in-distribution (lab-style leaf images). Field-photo performance is only measured
  by the external set (PlantDoc/PlantWild) in the single final evaluation.

## Authorisation
Owner request of 2026-11-24 ("select the best candidate using validation evidence ... if the
selected model has not yet been evaluated on the internal test set, conduct that evaluation
according to the documented runbook"). The selection was written by the AI coding assistant by
applying the pre-registered rule; no hyper-parameter was changed and nothing was tuned on test data.

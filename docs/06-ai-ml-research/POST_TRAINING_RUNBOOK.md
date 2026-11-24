# Post-training runbook: select → evaluate once → package → register
Summary: exact order of steps after the tomato_v1 training runs finish. Rules protect the test set (opened once) and the 15.6 GB dev PC (one heavy job at a time). All commands from `ml/` unless stated; PowerShell.

## Rules
- One GPU/RAM-heavy job at a time. No game, app stack (`scripts\dev\start.ps1`) or browser automation during training or evaluation. Run with the RAM watchdog.
- Model selection uses **validation only**. The internal test split and the external set (PlantDoc + PlantWild) are evaluated **once**, for the single selected model. `ood.py` also reads the test split, so it belongs to the same final step.
- Never overwrite a run directory, report directory or package version (package.py refuses existing versions).
- Results enter PROGRESS.md / MODEL_CARD.md only from the saved `metrics.json` files.

## 0. Environment fix (once, with no training running)
`onnx` is not installed in `ml/.venv`; `torch.onnx.export` in package.py needs it.
```
$env:UV_CACHE_DIR = "D:\AgriOS-data\uv-cache"; uv add onnx
```

## 1. Finish training (sequential)
```
.venv\Scripts\python.exe -m agrios_ml.train experiments/configs/E2_efficientnet_b0_tomato_v1.json   # resumes from last.pt
.venv\Scripts\python.exe -m agrios_ml.train experiments/configs/E3_mobilenet_v3_large_tomato_v1.json   # E2 MobileNetV3 arm (file name predates the proposal-ID check)
.venv\Scripts\python.exe -m agrios_ml.train experiments/configs/E1_small_cnn_tomato_v1.json          # baseline, if time
```
Each writes `runs/<exp_id>/seed42/{best.pt,last.pt,history.json,train_summary.json,val_logits.npy}`.

## 2. Validation-only evaluation (every candidate)
```
.venv\Scripts\python.exe -m agrios_ml.evaluate runs/E2_efficientnet_b0_tomato_v1/seed42 --report-dir reports/E2_efficientnet_b0_tomato_v1/val
```
Produces `metrics.json` (val, val_calibrated, temperature, selective risk, latency), confusion matrix, reliability diagram and learning curves.

## 3. Select (write the decision down BEFORE step 4)
Rule: highest calibrated validation macro-F1; if within 0.005, prefer the lower CPU latency / smaller model (serving is CPU ONNX). Record the choice and reason in `ml/reports/SELECTION.md`.

## 4. Final evaluation — once, selected model only
```
.venv\Scripts\python.exe -m agrios_ml.evaluate runs/<selected>/seed42 --report-dir reports/<selected>/final --final
```
Adds `test` and `external_test` (with per-source breakdown) to `metrics.json`. Macro-F1 is averaged over classes present in each split (external has 0 target_spot, 2 spider_mites).

## 5. Package
```
.venv\Scripts\python.exe -m agrios_ml.package runs/<selected>/seed42 --metrics reports/<selected>/final/metrics.json --version 1.0.0 --out D:\AgriOS-data\packages
```
Thresholds come from validation logits (accept threshold for 0.99 accepted-set accuracy; OOD energy at the 95th percentile). Writes `model.onnx`, `cam_weights.npy`, `golden/`, `package.json`.

## 6. Out-of-scope evaluation (part of the final step; reads the test split)
```
.venv\Scripts\python.exe -m agrios_ml.ood runs/<selected>/seed42 --package D:\AgriOS-data\packages\crop_doctor_tomato\1.0.0 --manifest ..\datasets\reports\dataset_manifest.csv --raw-root ..\datasets\raw\agri_foundation_v1 --cache D:\AgriOS-data\interim\ood_cache --out reports/<selected>/ood --workers 2
```
`--workers` must stay small: every Windows spawn worker re-imports torch (~0.7 GB RAM each).

## 7. Serving parity test (backend, CPU)
```
cd ..\backend; $env:AGRIOS_TEST_MODEL_PACKAGE = "D:\AgriOS-data\packages\crop_doctor_tomato\1.0.0"; uv run pytest tests/unit/test_onnx_predictor.py -q
```
Must pass before registration (ONNX Runtime logits match the torch golden logits).

## 8. Register and activate (dev DB)
```
cd ..\backend; uv run python scripts/register_model.py D:\AgriOS-data\packages\crop_doctor_tomato\1.0.0 --activate --notes "tomato_v1, <selected>, final eval <date>"
```
Copies the package into MODEL_PATH, verifies the checksum, inserts `model_versions` (audited). Then (no training running): `scripts\dev\start.ps1`, create a Crop Doctor case, confirm `inference_status=completed`; ask the agents for a field report and confirm `crop_health` coverage is `ok`.

## 9. Record
Update `ml/reports/MODEL_CARD.md` results table, PROGRESS.md results (E1–E3 rows), FEATURE_STATUS (Crop Doctor model → Evaluated), from the saved files only.

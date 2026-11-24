# Model card: crop_doctor_tomato
Summary: what the Crop Doctor image model is, what it was trained on, how it decides, and where it must not be trusted. Metrics are copied only from saved run files; PENDING means no such file exists yet.

## Status
- Feature status: **Evaluated** (offline, on public datasets only; no field or farmer validation). Selected on validation only (`SELECTION.md`): E2 MobileNetV3-Large, best epoch 14.
- Final evaluation ran **once** on 2026-11-24 (internal test + external sets opened once; not re-run). Packaged 2026-11-25 as `crop_doctor_tomato` **1.0.0** (ONNX, sha256 `a7352f47…1d56`), OOD-evaluated, ONNX-vs-PyTorch serving parity passed (golden logits, atol 2e-3), registered and **activated** in the dev DB (`backend/scripts/register_model.py`, audit events).
- Heatmap: **not provided** by 1.0.0 (`cam_weights_file: null` — MobileNetV3's two-layer head is not GAP+linear, so CAM would not be exact). The UI says so; no heatmap is faked.

## Intended use
- Decision support for **tomato leaf** disease triage in AgriOS Crop Doctor. Output is a shortlist plus a decision (`accepted` | `unsure` | `out_of_scope`); unsure and out-of-scope cases go to an expert.
- Not intended for: other crops (refused as `crop_not_supported`), fruit/stem symptoms, diagnosis without human review, or any pesticide/fertiliser dose (doses come only from reviewed tables, never from this model).

## Data (origin: retrieved)
- Source: agri_foundation_v1 (Agri-Foundation-145k aggregate); audit and split in `docs/07-datasets/DATASET_AUDIT_TOMATO_V1.md`.
- 10 classes (class map `ml/experiments/configs/tomato_v1_classes.json`, version tomato_v1).
- Train 18,711 / val 4,015 / internal test 4,011 images (PlantVillage, New Plant Diseases, PlantSeg, Tomato Leaf). External test 1,602 in-the-wild images (PlantDoc, PlantWild) never used for training, calibration or thresholds.
- Split frozen by SHA-256 `2b4fa89e…a2b4`; near-duplicate families never cross splits.

## Model and training
- Candidates (configs in `ml/experiments/configs/`): E1 small CNN (from scratch), E2 EfficientNet-B0, E2 MobileNetV3-Large (config file named E3_…) (ImageNet-1k pretrained, 1 head-only epoch then full fine-tuning).
- AdamW, cosine schedule with warmup, inverse-sqrt class weights, AMP, grad clip 1.0; early stopping on **validation macro-F1** (patience 4); seed 42.
- Input: RGB, resize short side 256 (bicubic), center crop 224, ImageNet mean/std. Serving uses the same geometry (`backend/app/mlops/onnx_predictor.py`); uploads are EXIF-transposed at ingest.

## Decision rule (backend `app/mlops/predictor.py::decide`)
1. Temperature-scaled softmax (temperature fitted on validation only).
2. Energy score above `ood_threshold` → `out_of_scope` (no class shown).
3. Else calibrated confidence ≥ `threshold` → `accepted`; otherwise `unsure` (shortlist only, expert escalation).
- Both thresholds are chosen on validation only (`ml/agrios_ml/package.py`): `threshold` = lowest confidence whose accepted-set val accuracy reaches 0.99; `ood_threshold` = 95th percentile of val energy.
- A model without thresholds can run but can never return `accepted`.

## Explainability
- Class activation maps from the real model (last feature map × classifier weights; equal to Grad-CAM for GAP+linear heads). Labelled in the UI as an aid, not proof of cause.

## Results (fill only from saved run files)
| Metric | Validation | Internal test | External test (PlantDoc+PlantWild) | Run file |
|---|---|---|---|---|
| Accuracy | 0.9861 | 0.9915 | 0.4045 | `ml/reports/E2_mobilenet_v3_large_tomato_v1/final/metrics.json` |
| Macro-F1 | 0.9853 | 0.9909 | 0.3500 | `ml/reports/E2_mobilenet_v3_large_tomato_v1/final/metrics.json` |
| ECE (15 bins), calibrated (T = 2.420) | 0.0033 (in-sample) | 0.0042 | 0.2837 | `ml/reports/E2_mobilenet_v3_large_tomato_v1/final/metrics.json` |
| Brier, calibrated | 0.0199 | 0.0137 | 0.8400 | `ml/reports/E2_mobilenet_v3_large_tomato_v1/final/metrics.json` |
| Unknown-crop rejection (3,000 non-tomato leaves; energy AUROC 0.982) | n/a | 0.925 (potato only 0.663) | n/a | `ml/reports/E2_mobilenet_v3_large_tomato_v1/ood/ood_metrics.json` |
| In-distribution flagged out-of-scope (internal test) | n/a | 0.046 | n/a | same file |
| CPU latency (ms/image, p50 batch 1, dev PC) | 10.5 | | | `ml/reports/E2_VALIDATION_COMPARISON.md` |

## Known limitations and risks
- Internal data is mostly lab-style single leaves; internal-test scores are expected to overstate field performance. The external test is the generalisation number to quote.
- **Measured**: external (in-the-wild) macro-F1 **0.350** vs internal 0.991, with external ECE 0.284 — the model does **not** generalise to field photos and its confidence is badly over-stated there. Many field photos are (correctly) returned as out-of-scope; a field-style PlantSeg train photo was flagged out-of-scope in the live check. Do not present Crop Doctor as a field diagnostic.
- Only other-crop leaf images were used for OOD; non-plant images are not evaluated (a flat grey image was not given a diagnosis in the live check, n = 1).
- New Plant Diseases is an augmented PlantVillage derivative; arbitrary-angle or cropped copies may survive near-duplicate grouping (internal test may be optimistic).
- External test has 2 spider_mites and 0 target_spot images: no external claim for those classes.
- No images from Pakistani fields; no paired context data (Pathway B: image-only).
- Pretrained weights: torchvision ImageNet-1k (code BSD-3-Clause; ImageNet terms are non-commercial research). Commercial use needs separate licence review. Dataset card states CC-BY-SA-4.0; per-source licences not yet independently verified.

# FYP methodology and results — evidence checklist
Summary: what the thesis/presentation can claim today, with the file that proves it, and what is still planned. Status: **Completed** (saved evidence exists) · **In progress** · **Planned**. Experiment IDs follow the proposal (Tables 18/39): E1 lightweight CNN, E2 transfer learning (EfficientNet-B0 AND MobileNetV3), E3 context-only tabular, E4 fusion, E5 calibration, E6 ablations, E7 unknown inputs. No number may be quoted unless its file is listed here. State on 2026-11-23 22:00 (reconciled).

## A. Data
| Item | Status | Evidence / note |
|---|---|---|
| Dataset provenance (archive, checksum, extraction) | Completed | `datasets/reports/extraction_record.json` (MD5 verified, 144,753 members) |
| Licensing | In progress | Dataset card states CC-BY-SA-4.0; per-source licences (PlantVillage, PlantDoc, PlantWild, PlantSeg, New Plant Diseases, Tomato Leaf) NOT independently verified — must be done before publication or weight release |
| Audit (integrity, duplicates, label conflicts, quality) | Completed | `datasets/reports/dataset_inventory.json`, `corrupt_images.csv`, `duplicate_groups.csv`, `excluded_samples.csv`; `docs/07-datasets/DATASET_AUDIT_TOMATO_V1.md` |
| Class mapping | Completed | `ml/experiments/configs/tomato_v1_classes.json` (10 classes, merges, excluded black_spot) |
| Split methodology (leakage control) | Completed | pHash (≤4, 8 dihedral variants) families, family-level split, seed 42, external sources held out; `datasets/manifests/tomato_v1/tomato_v1_split_summary.json` (SHA-256 recorded); 0 families across splits (verified 2026-11-23) |
| Split frozen | Completed | split SHA-256 `2b4fa89e…a2b4` in summary + packaged into every model package |

## B. Models and training
| Item | Status | Evidence / note |
|---|---|---|
| Architectures | Completed (code) | `ml/agrios_ml/nets.py`: E1 lightweight CNN (scratch); E2 EfficientNet-B0 and MobileNetV3-Large (ImageNet-1k pretrained, torchvision). The MobileNetV3 config is still FILE-named `E3_mobilenet_v3_large_tomato_v1.json` — it belongs to E2 (rename planned in Phase 5) |
| Training configuration | Completed | `ml/experiments/configs/E{1,2,3}_*.json`; per-run `config.json` (+ `config_epochs0-5.json` for E2) |
| Preprocessing | Completed | cache: EXIF transpose, RGB, short side 256, JPEG q95 (`ml/agrios_ml/data/cache.py`); eval: resize 256 bicubic + center crop 224 + ImageNet mean/std (`dataset.py`, identical in `onnx_predictor.py`) |
| Augmentation | Completed | RandomResizedCrop(0.5-1), flips, rotation ±20°, mild colour jitter, no hue shift, no cutout (rationale in `dataset.py`) |
| Imbalance handling | Completed | inverse-sqrt class weights (`train.py`) |
| Optimisation | Completed | AdamW, 1 head-only epoch then full fine-tune, warm-up + cosine, AMP, grad clip 1.0, early stop on val macro-F1 (patience 4) |
| Hardware/software environment | Completed | `ml/reports/environment/cuda_verification.txt` (RTX 3060 12 GB, torch 2.14.1+cu130, CUDA 13.0, cuDNN 9.24, Python 3.12.10); Windows 11, 15.6 GB RAM |
| Reproducibility caveats | Completed (documented) | `cudnn.benchmark=True` (not bit-exact); E2 resumed several times and data loader worker count changed — `D:\AgriOS-data\ml-runs\E2_efficientnet_b0_tomato_v1\seed42\RESUME_NOTES.md` |
| E2 EfficientNet-B0 training | Completed (training only) | 10-class tomato_v1 subset; early stop at epoch 9, best epoch 5; `history.json`, `train_summary.json`, `best.pt`, `RESUME_NOTES.md` (interruptions + loader changes) |
| E2 MobileNetV3-Large training | Planned | config only |
| E1 lightweight CNN + majority-class baseline | Planned | config + smoke test only |
| HOG + SVM traditional CV baseline (not in proposal; added on request) | Planned | no code |
| OpenCV preprocessing / quality checks | In progress | quality checks exist without OpenCV (PIL/NumPy) in `imagestats.py`; no blur/exposure gate at upload |
| E3 context-only tabular / E4 fusion / E6 ablations | Planned / not applicable | Pathway B: no paired image+context data |

## C. Evaluation (results)
| Item | Status | Evidence / note |
|---|---|---|
| Validation metrics during training | Completed (E2 only) | E2 `history.json` (val accuracy, val macro-F1 per epoch) — a model-selection signal, not a final result |
| Validation evaluation report (calibration, selective risk, confusion, curves) | Planned | `reports/<exp>/val/metrics.json` |
| Model selection record | Planned | `ml/reports/SELECTION.md` written before test access |
| Internal test results | Planned (test not opened) | `reports/<selected>/final/metrics.json` |
| External field-image results (PlantDoc + PlantWild) | Planned (not opened) | same file, `external_test` + `per_source` |
| Calibration (temperature, ECE, Brier, reliability) | Planned | same files + `reliability_val.png` |
| OOD / unsupported-crop rejection | Planned | `reports/<selected>/ood/ood_metrics.json` (other-crop leaves only; non-plant images not covered unless a licensed set is added) |
| Explainability check (CAM on real images) | Planned | qualitative figure set + note that CAM is an aid, not causal |
| Latency / size (CPU ONNX) | Planned | `metrics.json` `model` block + parity test output |
| Serving parity (torch vs ONNX, upload path) | Planned | backend `test_onnx_predictor.py` with `AGRIOS_TEST_MODEL_PACKAGE` + upload-path test |

## D. System evaluation
| Item | Status | Evidence / note |
|---|---|---|
| Automated tests (incl. all Phase 4B modules) | Completed | 2026-11-23 20:37: backend 252 passed / 1 skipped, frontend 62/62 (incl. axe), ML 11/11; ruff/eslint/tsc/build clean |
| Phase 4B live integration check | Completed | `var/phase4b_live_verification.json` (9/9: real Open-Meteo, ETc, soil, field report, approval flow, cross-user 404) |
| E2E browser tests | In progress | Playwright 12/12 recorded for Phase 3 flows; Phase 4B pages not yet in e2e |
| Agentic AI evaluation (H6) | In progress | functional tests: every write path requires approval and writes audit events (`tests/db/test_agents_api.py`, 7 tests); no scored evaluation set (intent accuracy, approval-compliance rate over a scenario set) yet |
| RAG retrieval evaluation | Planned | no RAG implementation |
| Security checks | In progress | upload hardening, signed links, audit tests; dependency audits recorded in Phase 3; formal checklist not yet signed off |
| CI | Planned | workflow file exists; never run (no remote) |

## E. Limitations and threats to validity (to state in the thesis)
1. Internal data are mostly lab-style single-leaf images; field performance must be judged on the external set.
2. Possible residual leakage: augmented copies (New Plant Diseases ← PlantVillage) beyond pHash grouping may survive the split.
3. External set has 0 target_spot and 2 spider_mites images.
4. No Pakistan field images; no paired image+context data (Pathway B, image-only).
5. Single seed (42) per experiment; no variance estimate unless more seeds are run.
10. Only the 10-class tomato subset of the 215-class release is modelled; no claim about other crops.
6. E2 run was interrupted and resumed (documented); loader worker count changed mid-run.
7. ImageNet-pretrained weights carry non-commercial research terms.
8. Weather indicators and Kc values are general international guidance, not locally validated.
9. Agents are rule-based (keyword intents); no user study.

## F. Rules
Quote numbers only from the files in sections C-D. Keep PROGRESS.md and MODEL_CARD.md result tables PENDING until those files exist. Validation numbers are never presented as test results.

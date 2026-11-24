# AI_ML_RESEARCH_PLAN.md — ML, CV, multimodal, RAG evaluation
Summary: datasets, pathway decision, experiments E1-E7, training recipe, calibration/OOD, statistics, RAG/agent evaluation, result-recording rules. All numbers come from saved run files; none are assumed.

## Research question
Does structured context improve crop-health diagnosis over image-only? Testable only under Pathway A (valid paired data). Default expectation: Pathway B (image-only + separate scenario-based context evaluation, NO multimodal claim). Null result is valid.

## Datasets (audit first, Days 1-5; record licence + classes in docs/dataset_audit)
- PlantVillage (tomato primary, lab images). PlantDoc (field-style eval + extra tomato). Own phone photos (consent, expert label) = small real test set.
- Wheat/cotton: only if audit passes (licence, classes, labels, duplicates).
- Context: NASA POWER, Open-Meteo, SoilGrids/HWSD (coarse, labelled retrieved/inferred), FAO 56 tables.
- Forbidden: attaching random weather/soil to images and calling it multimodal.
- Audit score 0-2 on: licence, classes, image quality, labels, duplicates/groups, paired context, Pakistan relevance. Pick crop by score; need healthy + >=2 disease classes.

## Data pipeline rules
Raw read-only. Manifest+checksums. Class mapping file. pHash duplicate grouping. Split by group (leaf/plant/source), not by image. Freeze splits Day 15. Class weights on train only. Augment train only. Field photos reported separately.

## Experiments
| ID | What | Pathway |
|---|---|---|
| E1 | Small CNN baseline | A,B |
| E2 | MobileNetV3 / EfficientNet-B0 transfer | A,B |
| E3 | Context-only tabular (LR, RF, XGBoost, MLP) | A |
| E4 | Image+context fusion (late first, then early) | A |
| E5 | Calibration + rejection | A,B |
| E6 | Context ablations | A |
| E7 | Unknown/non-plant/other-crop rejection | A,B |

## Training recipe (tune on validation only)
224x224, ImageNet norm, identical preprocessing train/infer. Head first, then unfreeze last blocks, low LR. AdamW + cosine. Early stop on val macro F1. CE + class weights. >=3 seeds, report mean +- spread. Save per run: config, seed, split file, checkpoint, metrics.json, curves, git commit. Checkpoint every epoch (Colab/Kaggle may die). Smaller model before cutting evaluation.

## Confidence, rejection, explanation
Temperature scaling on val logits. Report Brier, ECE, reliability diagram before/after. Reject using calibrated max-prob + energy score. Report coverage vs selective risk at several thresholds. Grad-CAM (image), SHAP (context). Keep a failure-case folder with notes.

## Context handling
Features: crop/variety/stage, weather, soil, history, coarse region. Missing -> mask vector + modality dropout. Report full/partial/no-context results. Scale with train statistics only.

## Statistics
Same frozen test set for all models. McNemar for paired accuracy; bootstrap CIs for macro F1 and ECE. Overlapping CIs = "no clear difference". Never write "proven".

## Other ML
Soil: rule baseline vs ML only if suitable data. Risk: rule baselines with sourced thresholds; indicator never = diagnosis. Crop-recommendation Kaggle data: demo only, state not representative.

## RAG evaluation
40-60 question set with source-checked references. Compare S1 general LLM, S2 standard RAG, S3 structured retrieval + verifier. Metrics: retrieval relevance, citation correctness, factual accuracy, unsupported-recommendation rate, completeness. Single rater = stated limitation.

## Agent evaluation
Task completion, tool error rate, approval compliance (target 100%), audit completeness (target 100%), unsafe-output rate (target 0).

## Recording results
`ml/reports/<exp_id>/<run_id>/metrics.json`. Result tables in docs are generated from these files by script. Missing file => cell says PENDING. Model card per version (intended use, out-of-scope, data, per-class metrics, calibration, rejection, failures).

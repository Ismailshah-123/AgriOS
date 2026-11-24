# Post-overnight verification (2026-11-24)
Summary: verification-only audit of the overnight sprint, plus the multi-crop dataset audit and expansion proposal. Every number cites a saved file or a command run in this session. No new features were built for this report.

## 1. MobileNetV3 (E2 comparison arm)
- Run: `ml/runs/E2_mobilenet_v3_large_tomato_v1/seed42` (D:\AgriOS-data\ml-runs). Config `E2_mobilenet_v3_large_tomato_v1.json` = the E3-named file with only `exp_id` changed (diff verified).
- History: 00:12 start; 00:53:14 RAM watchdog stop in epoch 12 (Chrome reopened, 1.36 GB available); 00:58:55 resumed from last.pt (epoch 11) with 8.89 GB available, Chrome closed (RUN_NOTES.md).
- RESULTS: see section 7 (filled from saved files after the run ends).

## 2. Protocol fairness EffB0 vs MNv3 (verified by config diff)
Identical: split file (sha256 2b4fa89e…), class map, cache (28,340 files), img 224, batch 64, epochs 20, head 1 epoch, LRs, wd, warmup, inverse-sqrt class weights, augment medium, patience 4 on val macro-F1, grad clip, AMP, seed 42. Different: arch (intended), exp_id, DataLoader workers (EffB0 epochs 6-9 used 0 workers after interruptions; MNv3 uses 2) — affects augmentation RNG streams only. Both runs were interrupted and resumed once or more.

## 3. Database and application
| Check | Result (2026-11-24 ~00:59) |
|---|---|
| Revision | 0010 (head), 23 required tables (`init_db.py --check`) |
| Data | users 18, farms 12, fields 8, crop_cycles 7, soil 1, cases 4, expenses 1, harvest_sales 1, expert_reviews 1, knowledge_sources 0, knowledge_chunks 0, model_versions 0, audit_events 84 |
| Backups | var/backups/agrios_20261124_002547.dump (19 table-data entries), agrios_20261124_004317.dump (22); both readable by pg_restore --list |
| Services | API health/ready 200, worker running, Vite 200 (status.ps1) |
| End-to-end (live, dev DB) | economics + expert review 12/12, fertilizer + knowledge 3/3 (var/overnight_live_verification.txt) |

## 4. Multi-crop dataset audit (agri_foundation_v1, 215 classes)
Source: `datasets/reports/class_distribution.csv`, `source_provenance.csv`, `dataset_inventory.json` (audit run 2026-11-23). Field-type = PlantDoc/PlantWild/PlantSeg photos; lab-type = PlantVillage, New Plant Diseases (an AUGMENTED derivative of PlantVillage: near-duplicate leakage risk), TomatoLeaf.

| crop | classes | healthy classes | images | min / median / max per class | classes < 200 | field-type imgs | lab-type imgs | other single-source |
|---|---|---|---|---|---|---|---|---|
| tomato | 14 | 1 | 29,219 | 2 / 2,485 / 5,348 | 3 | 2,586 | 26,633 | 0 |
| cassava | 5 | 1 | 21,397 | 1,087 / 2,386 / 13,158 | 0 | 0 | 0 | 21,397 |
| unknown (118 non-target crop labels) | 118 | 0 | 12,197 | 1 / 64 / 588 | 100 | 12,197 | 0 | 0 |
| apple | 6 | 1 | 11,354 | 178 / 2,427 / 3,034 | 1 | 1,650 | 9,704 | 0 |
| corn (maize) | 10 | 2 | 10,592 | 156 / 317 / 2,385 | 2 | 1,447 | 9,145 | 0 |
| grape | 8 | 1 | 10,202 | 67 / 1,270 / 2,641 | 3 | 1,175 | 9,027 | 0 |
| potato | 3 | 1 | 8,026 | 2,528 / 2,748 / 2,750 | 0 | 898 | 7,128 | 0 |
| wheat | 5 | 1 | 6,308 | 1,171 / 1,250 / 1,336 | 0 | 0 | 0 | 6,308 |
| pepper | 10 | 2 | 5,589 | 27 / 238 / 1,478 | 5 | 712 | 4,877 | 0 |
| peach | 7 | 1 | 5,225 | 8 / 170 / 2,427 | 4 | 768 | 4,457 | 0 |
| cherry | 5 | 2 | 5,057 | 108 / 338 / 2,282 | 1 | 671 | 4,386 | 0 |
| strawberry | 3 | 1 | 4,959 | 98 / 2,292 / 2,569 | 1 | 461 | 4,498 | 0 |
| soybean | 7 | 1 | 3,562 | 61 / 117 / 2,827 | 5 | 1,035 | 2,527 | 0 |
| squash | 2 | 1 | 2,968 | 407 / 1,484 / 2,561 | 0 | 798 | 2,170 | 0 |
| blueberry | 6 | 1 | 2,938 | 36 / 44 / 2,662 | 5 | 668 | 2,270 | 0 |
| raspberry | 5 | 1 | 2,645 | 18 / 36 / 2,522 | 4 | 419 | 2,226 | 0 |
| orange | 1 | 0 | 2,513 | 2,513 | 0 | 0 | 2,513 | 0 |
Totals: 144,751 images, 215 classes, 17 crop values. 0 decode failures, 0 exact duplicates, 620 low-information images flagged; smallest classes are scrape artefacts (e.g. `cabbage_cabbage_black_rot_bing_-_copy` 1, `tomato_two_spotted_spider_mites` 2).

Findings that matter for expansion:
1. Pakistan's major crops are mostly ABSENT: no cotton, rice, sugarcane or mango; orange has ONE class (citrus greening) and no healthy class, so it cannot train a classifier.
2. Wheat (5 classes, balanced ~1.2-1.3k) comes from ONE source only: label and source are confounded, and there is no field-type external set; `blackpoint` (grain) and `fusarium foot rot` (stem base) are not leaf diseases, so photo protocol differs by class.
3. Maize labels are split by source: lab labels `corn_(maize)_common_rust` (2,384, NPD only) vs field labels `corn_rust` (342), likewise northern blight / gray spot / healthy. A class map must merge them (as done for tomato) or every model learns source, not disease.
4. Potato is the cleanest candidate: 3 balanced classes (early blight, late blight, healthy), 898 field-type images across 3 field sources for an external set.
5. Licences: the release states CC-BY-SA-4.0, but per-source licences (PlantVillage, PlantDoc, PlantWild, PlantSeg, NPD, Cassava, Wheat, TomatoLeaf) are NOT independently verified; commercial use of weights is unresolved.
6. Leakage: NPD is augmented PlantVillage; any multi-crop split must use the same pHash family grouping (8 dihedral variants) used for tomato_v1.
7. The 118 `unknown` labels (12,197 field images of other crops) are a ready source for E7 other-crop OOD evaluation.

## 5. Crop-wise expansion proposal (NOT started; needs owner + supervisor approval)
| Order | Crop | Why | Before training |
|---|---|---|---|
| 1 | Potato (3 classes) | Balanced, healthy class, 3 field sources for external test; grown in Punjab | per-source licence check; family-grouped split; external = PlantDoc/PlantWild/PlantSeg potato |
| 2 | Maize (merged 4-5 classes) | Major Pakistani crop; enough data after merging lab + field labels | class map merging source-specific labels; check per-class field counts; external from field sources |
| 3 | Wheat (leaf classes only) | Pakistan's main crop | single source: needs an independent field set (none in the release) before any claim; separate leaf vs grain classes |
| — | Cotton, rice, sugarcane, mango, citrus | Not in the release | new licensed data required; out of FYP scope unless sourced |
Approach: one model per crop (keeps the tomato pipeline, simpler per-crop OOD) rather than one 215-class model, which would mix lab-source artefacts across crops.

## 6. Responsive frontend
See section 8 (browser results filled after the run).

## 7. Final MobileNetV3 results (VALIDATION ONLY)
Training ended normally 01:22:39 (early stop after epoch 18; supervisor exit 0; min available RAM 2.92 GB). Best epoch 14. Evaluated with `agrios_ml.evaluate` without `--final` (reports carry `final_evaluation: false`; test/external never opened). Table generated by `ml/scripts/compare_val.py` -> `ml/reports/E2_VALIDATION_COMPARISON.md`:

| exp | best epoch | val acc | val macro-F1 | ECE15 raw -> T | Brier raw -> T | T | params | ckpt MB | CPU ms (p50) | GPU ms |
|---|---|---|---|---|---|---|---|---|---|---|
| EfficientNet-B0 | 5 | 0.9880 | 0.9873 | 0.0048 -> 0.0043 | 0.0193 -> 0.0197 | 1.326 | 4,020,358 | 16.4 | 14.0 | 6.0 |
| MobileNetV3-Large | 14 | 0.9861 | 0.9853 | 0.0103 -> 0.0033 | 0.0231 -> 0.0199 | 2.420 | 4,214,842 | 17.1 | 10.5 | 4.5 |
Per-class precision/recall for both models: in the comparison file (lowest MNv3 recall: early_blight 0.966, bacterial_spot 0.970, leaf_mold 0.971).

What the pre-registered rule (POST_TRAINING_RUNBOOK §3) yields — NOT yet adopted: calibrated val macro-F1 differs by 0.0020 (< 0.005), so the rule prefers the lower CPU latency, i.e. MobileNetV3. Caveats before the owner/supervisor writes SELECTION.md: one seed each (0.002 is within plausible seed variance); calibration numbers are in-sample on val; EffB0 epochs 6-9 and MNv3 used different DataLoader worker counts after interruptions; latency measured once on this PC with other apps running. No test or external evaluation until SELECTION.md exists.

## 8. Responsive test coverage
(pending browser run)

# Dataset audit: agri_foundation_v1 → tomato_v1
Summary: what was extracted, audited and split for the tomato-first Crop Doctor model. Every number here is copied from a saved report file (listed per section). Nothing is estimated.

## 1. Source archive (origin: retrieved)
Evidence: `datasets/reports/extraction_record.json`, `D:\AgriOS-data\extract.log`
- Archive `agri_foundation_v1.zip`, 10,409,588,214 bytes, MD5 `bcaa3137f722a8f7de4a1e1a6e1bbee4` (matches expected).
- Extracted 2026-11-23T13:29:29Z to `D:\AgriOS-data\agri_foundation_v1` (HDD); 144,753 members, 0 verification failures. Repo access via junction `datasets/raw/agri_foundation_v1`.
- 144,754 `.cache/` members skipped (Hugging Face upload stubs, not dataset content).
- Licence as stated by the dataset card: CC-BY-SA-4.0. Per-source licences (PlantVillage, PlantDoc, PlantWild, PlantSeg, New Plant Diseases, Tomato Leaf, Cassava, Wheat) are **not yet independently verified**; that is required before any redistribution of images or model weights.

## 2. Whole-release audit
Evidence: `datasets/reports/dataset_inventory.json`, `dataset_manifest.csv`, `corrupt_images.csv`, `duplicate_groups.csv`, `excluded_samples.csv`, `source_provenance.csv`
| Check | Result |
|---|---|
| metadata rows vs files on disk | 144,751 / 144,751; 0 missing, 0 unlisted |
| decode failures | 0 |
| exact (SHA-256) duplicate groups | 0 |
| conflicting-label duplicates | 0 |
| folder/label mismatches | 0 |
| low-information images flagged | 620 (action: review, not removed) |
| classes / crops | 215 / 17 |
| image size (min/median/max) | width 36/256/8256 px, height 39/256/6000 px |
| formats | JPEG 144,705; PNG 36; MPO 9; GIF 1 |

Known issues for non-tomato crops (out of scope now): extreme class imbalance (largest `cassava_mosaic_disease` 13,158; smallest `cabbage_cabbage_black_rot_bing_-_copy` 1, an unmerged scrape label); 12,197 PlantSeg/PlantWild images have crop `unknown`.

## 3. Tomato class map
Evidence: `ml/experiments/configs/tomato_v1_classes.json`
- 10 classes: bacterial_spot, early_blight, healthy, late_blight, leaf_mold, mosaic_virus, septoria_leaf_spot, spider_mites, target_spot, yellow_leaf_curl_virus.
- Merges: three spider-mite spellings; PlantDoc "leaf yellow virus" → yellow_leaf_curl_virus.
- Excluded label: `tomato_black_spot` (108 images, single source `tomatoleaf`; label confounded with source).

## 4. Split tomato_v1 (frozen artefact)
Evidence: `datasets/manifests/tomato_v1/tomato_v1_split_summary.json` (split SHA-256 `2b4fa89eaca49c5e3f18d621707d4bd9564334cf5aefbdf628926d3ecff8a2b4`, seed 42)
- Leakage control: images grouped into families by pHash Hamming ≤ 4 against all 8 dihedral (flip/90° rotation) variants; a whole family goes to one split. 29,111 images → 21,681 families; 15,133 near-duplicate pairs, 6,929 of them cross-source.
- Verified 2026-11-23: 0 families span more than one split.

| Split | Images | Sources |
|---|---|---|
| train | 18,711 | plantvillage 11,113; new_plant_diseases 6,728; plantseg 589; tomatoleaf 281 |
| val | 4,015 | plantvillage 2,421; new_plant_diseases 1,406; plantseg 124; tomatoleaf 64 |
| test (internal, opened once) | 4,011 | plantvillage 2,399; new_plant_diseases 1,442; plantseg 108; tomatoleaf 62 |
| external_test | 1,602 | plantdoc 657; plantwild 945 |
| excluded: conflicting family labels | 719 | - |
| excluded: external overlaps internal | 53 | - |
| excluded pre-split (black_spot) | 108 | tomatoleaf |

- PlantDoc and PlantWild are **external only**: never used for training, validation, calibration or threshold selection.
- External test has almost no spider_mites (2) and no target_spot (0): external per-class metrics for those two classes cannot be reported.
- 117 tomato low-information images are still in the split (train 71, val 16, test 22, external 8); flagged for review, not removed.

## 5. Residual risks (stated, not measured)
- New Plant Diseases is derived from PlantVillage with offline augmentation. pHash families catch flips and 90° rotations, but not arbitrary-angle rotations, crops or colour shifts. Internal test scores may therefore be optimistic; the external test (in-the-wild photos) is the honest generalisation number.
- Internal sources are mostly lab-style single-leaf images; field photos from Pakistan are not represented.

## 6. Training cache
Evidence: `ml/cache/tomato_v1_s256/cache_info.json`
- 28,339 images (all non-excluded split rows), short side 256 px, JPEG q95, 917,830,189 bytes; coverage check 2026-11-23: 0 missing. Raw originals are never modified.

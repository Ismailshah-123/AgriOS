# Overnight sprint — start checkpoint (2026-11-24 ~00:10)
Summary: measured state before any work; MobileNetV3 (E2 comparison arm) training preflight; work queue. Nothing changed, started or stopped to produce this file.

## 1. System state (measured)
| Item | Reading |
|---|---|
| RAM | 6.24 GB available of 15.61 GB; commit free 13.37 GB |
| Largest consumers | chrome 28 processes 2.18 GB (still running), VS Code 1.46 GB, Steam + Edge running; VALORANT closed (Vanguard tray only) |
| GPU | RTX 3060, 801 MiB used / 11,313 MiB free, 1 % util, 57 °C; no training process |
| Disk | C: 26.7 GB free, D: 687.9 GB free |
| AgriOS services | API :8000 health 200 / ready 200, worker running, Vite :5173 200 (start.ps1-owned, ~0.4 GB total) |
| Database | `agrios` @ 127.0.0.1:54330, revision 0007 (head), 13 required tables |
| Git | branch master, no commits; 13 untracked top-level entries (nothing staged) |
| Junctions | `ml/runs` -> D:\AgriOS-data\ml-runs; `datasets/raw/agri_foundation_v1` -> D:\AgriOS-data\agri_foundation_v1 |
| E2 EfficientNet-B0 | best.pt present (sha256 6E7AFEB33E25E2CB…), last.pt, history, val logits — untouched |

## 2. MobileNetV3 (E2 arm) preflight — RESULT: DO NOT START
| Condition (owner's rules) | Result |
|---|---|
| >= 8 GB available RAM | **FAIL: 6.24 GB** (Chrome still open, 2.18 GB) |
| GPU memory for batch 64 @224, AMP | PASS (11.3 GB free; EffB0 ran on the same card at this batch) |
| No other training job | PASS |
| Conservative workers | PASS: config num_workers 2 / val 0; `train.check_worker_memory` refuses unsafe counts (needs 3.0 + 0.7/worker GB RAM) |
| Dataset/split/class map/cache verified | PASS: split sha256 2B4FA89EACA49C5E…, class map present, cache 28,340 files |
| Unique output directory | PASS: run dir does not exist yet |
| Automatic RAM stop (watchdog/supervisor) | **MISSING**: the supervisor used for E2 is not in the repo or on D: (it lived in a previous session scratchpad). Unattended training would have no automatic stop if RAM collapses |

### Protocol fairness (config diff vs the E2 EfficientNet-B0 run)
Identical: split, class map, cache, img 224, batch 64, epochs 20, head 1 epoch, LRs, weight decay, warmup, inverse-sqrt class weights, augment medium, patience 4 on val macro-F1, grad clip, AMP, seed 42.
Differs: `arch` (mobilenet_v3_large, intended); `exp_id` (file says `E3_…`, but the proposal's E3 = context-only tabular, so a run dir named E3 would mislabel the experiment); `num_workers` (EffB0 epochs 0-5 used 2, epochs 6-9 used 0 after interruptions; RESUME_NOTES.md says only augmentation RNG streams differ).

### Prepared command (not run)
Proposed (owner decision): keep the E3-named file untouched and add an identical copy with `exp_id` = `E2_mobilenet_v3_large_tomato_v1`, so the run lands in `runs/E2_mobilenet_v3_large_tomato_v1/seed42`.
```
cd ml
.venv\Scripts\python.exe -m agrios_ml.train experiments/configs/E2_mobilenet_v3_large_tomato_v1.json
```
Preconditions to re-check immediately before: >= 8 GB available, no other training, a RAM watchdog running (to be re-created and tested on a dummy process first).

## 3. Work queue for the sprint (software only; no GPU work)
1. FAO-56 worked-example tests (from the FAO-56 text, values transcribed with page/example ids)
2. Backend/frontend coverage matrix + small gaps
3. Expert review queue; economics
4. Offline drafts; Urdu/RTL foundation
5. RAG infrastructure (FTS, source register, synthetic test docs only); fertilizer reference structure without doses
6. e2e for new pages (only with enough RAM, sequential); full suites
7. Docs, ML runbook, decision report

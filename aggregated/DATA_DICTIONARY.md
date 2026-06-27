# DATA DICTIONARY
## FL-Blockchain-EVM Dataset: New Aggregated Data from Federated Learning Training

**Version:** 2.0  
**Date:** June 2026  
**Authors:** see paper  
**Dataset Type:** New aggregated metrics from Flower federated learning experiments

**IMPORTANT:** This is NOT the original MHEALTH or UCI-HAR datasets. This is **new data** — aggregated performance metrics, device telemetry, and blockchain overhead logs generated from federated learning training experiments that USED those source datasets.

All values in this document are derived directly from the raw experiment output files. No value has been estimated or filled in manually.

---

## Overview

This dataset comprises new aggregated results from 40 federated learning (FL) sessions conducted using the Flower framework. The experiments were designed to train activity recognition models in a federated manner across two different source datasets:
- **MHEALTH dataset experiments** (12 activity classes, 10 subjects, 23 sensor channels)
- **UCI-HAR dataset experiments** (6 activity classes, 30 subjects, 9 sensor channels)

Each FL session runs on 10 physical Raspberry Pi 4 edge devices with 10 aggregation rounds and a 1-D SE-ResNet model. Every round writes three blocks to a smart contract (FLBL2) deployed on Base mainnet (chain ID 8453) and pins artefacts to IPFS via Pinata.

Two operational variants were tested:

- **baseline** — synchronous IPFS uploads, fresh gas estimation per transaction, chain verification per round.
- **optimized** — asynchronous IPFS uploads (background thread), cached gas parameters, verification skipped per round.

Each dataset has 10 baseline sessions and 10 optimized sessions (20 sessions per dataset, 40 total).

---

## File structure per session

Each session directory (e.g. `baseline_20260424_201227`) contains:

| File | Present in | Description |
|---|---|---|
| `results.json` | all sessions | NDJSON file; one record per line; three record types (see §2) |
| `experiment_config.json` | all sessions | JSON; session configuration at start time |
| `perf_<session_id>.log` | all sessions | Plain-text performance log; one event per line |
| `cm_round_N.png` | all sessions | Confusion matrix image for round N (N = 0 to 10); 11 files per session |

---

## 1. results.json

NDJSON format (one JSON value per line). Three distinct record types share the same file, identified by the `type` field. Client evaluation records are wrapped in a JSON array (one array per round).

---

### 1.1 Global record (`"type": "global"`)

Written once per aggregation round, including round 0 (initial model broadcast before any training). 11 records per session (rounds 0–10).

| Key | JSON type | Description |
|---|---|---|
| `type` | string | Always `"global"` |
| `round` | int | Round index. 0 = initial model; 1–10 = trained rounds |
| `timestamp` | string | ISO-8601 datetime when this record was written |
| `variant` | string | `"baseline"` or `"optimized"` |
| `accuracy` | float | Macro-averaged test accuracy on the held-out test set |
| `loss` | float | Cross-entropy test loss |
| `f1_macro` | float | Macro-averaged F1 score |
| `f1_weighted` | float | Weighted-averaged F1 score |
| `precision_macro` | float | Macro-averaged precision |
| `recall_macro` | float | Macro-averaged recall |
| `specificity_macro` | float | Macro-averaged specificity |
| `auc_macro` | float | Macro-averaged one-vs-rest AUC |
| `per_class_f1` | float[] | Per-class F1; length 12 (MHEALTH) or 6 (UCI-HAR) |
| `per_class_precision` | float[] | Per-class precision |
| `per_class_recall` | float[] | Per-class recall |
| `per_class_auc` | float[] | Per-class one-vs-rest AUC |
| `per_class_support` | int[] | Number of test samples per class |
| `optimal_thresholds` | float[] | Per-class decision thresholds (from ROC optimisation) |
| `confusion_matrix` | int[][] | Row = true class, column = predicted class; shape N×N |
| `superclass_names` | string[] | Ordered class label strings used as confusion matrix axes (see §5) |
| `num_samples` | int | Total test samples used for evaluation (514 MHEALTH; 2947 UCI-HAR) |
| `num_classes` | int | Number of classes (12 MHEALTH; 6 UCI-HAR) |
| `blockchain_blocks` | int | Number of on-chain blocks written this round (0 in round 0 for optimized variant) |
| `model_payload_bytes` | int | Size in bytes of the serialised global model artefact sent to IPFS |
| `round_wall_time_s` | float | **Rounds 1–10:** elapsed wall-clock time in seconds for this round. **Round 0:** the session-start Unix timestamp in seconds (a recording artifact — exclude round 0 when computing timing statistics) |
| `ipfs_cids.model_cid` | string | IPFS CID of the serialised global model |
| `ipfs_cids.metrics_cid` | string | IPFS CID of the round metrics JSON |
| `ipfs_cids.local_cid` | string | IPFS CID of client-update summaries (empty string in round 0) |
| `ipfs_cids.vote_cid` | string | IPFS CID of per-client loss votes (empty string in round 0) |

**Note:** `confusion_matrix`, `per_class_auc`, `per_class_precision`, `per_class_recall`, `per_class_support`, `optimal_thresholds`, and `superclass_names` are present in `results.json` but are not flattened into the aggregated CSVs. Per-class F1 values are flattened as `f1_class_0` … `f1_class_N` in `all_rounds_*.csv`.

---

### 1.2 Device training record (`"type": "device_training"`)

Written once per training round (rounds 1–10). Contains an embedded `devices` array with one entry per participating client. 10 records per session.

| Key | JSON type | Description |
|---|---|---|
| `type` | string | Always `"device_training"` |
| `round` | int | Round index (1–10) |
| `devices` | array | Array of per-client training metrics (see below) |

Each element of `devices`:

| Key | JSON type | Description |
|---|---|---|
| `client_id` | int | Client identifier (0-indexed) |
| `train_loss` | float | Final local training loss after all local epochs |
| `num_examples` | int | Number of training samples used this round |
| `training_time` | float | Wall-clock time in seconds for local training (all epochs) on this device. Note: the raw key is `training_time`; the CSV column is named `training_time_s` |
| `active_classes` | int | Number of distinct activity classes present in this client's local shard |
| `cpu_percent` | float | Mean CPU utilisation (%) during local training |
| `ram_used_mb` | float | Peak RAM used in MB during local training |
| `cpu_temp_c` | float | Mean CPU die temperature in °C during local training |

---

### 1.3 Client evaluation record (`"type": "client_eval"`)

Written once per training round (rounds 1–10). Each line in `results.json` is a JSON **array** containing one evaluation record per participating client. Array length is 10 in both datasets; all 10 clients take part in every round.

| Key | JSON type | Description |
|---|---|---|
| `type` | string | Always `"client_eval"` |
| `round` | int | Round index (1–10) |
| `timestamp` | string | ISO-8601 datetime of this evaluation |
| `client_id` | int | Client identifier (0-indexed) |
| `eval_loss` | float | Cross-entropy loss on this client's local held-out data |
| `eval_acc` | float | Accuracy on local held-out data |
| `eval_f1` | float | Macro-F1 on local held-out data |
| `eval_auc` | float | Macro one-vs-rest AUC on local held-out data |
| `num-examples` | int | Number of local evaluation samples. **Note: the JSON key uses a hyphen** (`num-examples`); the aggregated CSV normalises this to `num_examples` |
| `eval_time_seconds` | float | Wall-clock time in seconds for the local evaluation pass |
| `cpu_percent` | float | Mean CPU utilisation (%) during evaluation |
| `ram_used_mb` | float | Peak RAM used in MB during evaluation |
| `cpu_temp_c` | float | Mean CPU die temperature in °C during evaluation |

---

## 2. experiment_config.json

One file per session. All fields below are present in every session.

| Key | JSON type | Description |
|---|---|---|
| `variant` | string | `"baseline"` or `"optimized"` |
| `run_timestamp` | string | Session timestamp string in `YYYYMMDD_HHMMSS` format |
| `output_dir` | string | Relative path to the session output directory |
| `blockchain_optimized` | bool | `true` if optimized variant, `false` if baseline |
| `ipfs_backend` | string | IPFS provider (`"pinata"` in all sessions) |
| `pinata_account` | string | Pinata account alias used for this session (not a secret) |
| `hardware_note` | string | Free-text description of the physical hardware setup |
| `num_rounds` | int | Number of FL aggregation rounds (10 in all sessions) |
| `num_clients` | int | Number of FL clients configured (10 in all sessions) |
| `local_epochs` | int | Local training epochs per round (5 for MHEALTH; 3 for UCI-HAR) |
| `batch_size` | int | Mini-batch size for local training (64 in all sessions) |
| `lr` | float | Base learning rate (0.002 for MHEALTH; 0.001 for UCI-HAR) |
| `started_at` | string | ISO-8601 datetime of session start |

---

## 3. perf_*.log (all sessions)

Plain-text file; one event per line. All 40 sessions (20 MHEALTH and 20 UCI-HAR) have a log file. The earlier May 2026 UCI-HAR sessions carried no perf log; the June 2026 UCI-HAR re-run records one for every session, so both datasets now have full timing logs.

The log header lines (lines containing `===`, `Mode`, `Started`, `File`) should be skipped when parsing.

Event lines follow this general format:  
`HH:MM:SS.ffffff  EVENT_TYPE  KEY=VALUE ...`

### Event types

| `event_type` (CSV) | Log keyword | `block_type` | `duration_ms` meaning | `extra_key` | `extra_value` |
|---|---|---|---|---|---|
| `ipfs_upload` | `ipfs_global` / `ipfs_local` / `ipfs_vote` | `GLOBAL` / `LOCAL` / `VOTE` | Upload duration to IPFS | — | — |
| `gas_estimate` | `gas_limit` | `GLOBAL` / `LOCAL` / `VOTE` | RPC duration for gas estimation | `estimated_gas` | Estimated gas units |
| `gas_price_fetch` | `gas_price` | — | RPC duration for gas price fetch | `fetched_gwei` | Gas price in Gwei |
| `tx_send` | `tx_sent` | `GLOBAL` / `LOCAL` / `VOTE` | Time from send call to RPC acknowledgement | — | — |
| `tx_confirm` | `confirmed` | — | Time from send to on-chain confirmation (submit_to_confirm_ms) | `block_number` | Block number where TX landed |
| `chain_verify` | `verify_chain` | — | Duration of `verifyChain()` RPC call | `valid` | `True` or `False` |
| `round_overhead` | `--- ROUND N end` | — | Total non-training blockchain + IPFS overhead for this round | — | — |

**Event counts — same in `perf_timings_mhealth.csv` and `perf_timings_ucihar.csv` (2,560 rows each):**

| event_type | n | Note |
|---|---|---|
| `tx_confirm` | 620 | 20 sessions × 31 TX per session (1 GLOBAL round-0 + 3 per round × 10 rounds) |
| `tx_send` | 620 | Same scope as tx_confirm |
| `gas_estimate` | 340 | baseline=310 (3 per round × 10 rounds × 10 sessions + 10 round-0), optimized=30 (one per block type, first use only) |
| `gas_price_fetch` | 320 | baseline=310, optimized=10 (one fetch per session start) |
| `ipfs_upload` | 310 | Baseline only; optimized async uploads are not captured in the synchronous log path |
| `round_overhead` | 220 | 20 sessions × 11 rounds (0–10) |
| `chain_verify` | 130 | Baseline: 10 sessions × 11 rounds = 110; optimized: 10 sessions × 1 (initial only) = ~20 |

---

## 4. cm_round_N.png

PNG confusion matrix for round N. 11 files per session (N = 0 to 10). Axes correspond to the `superclass_names` order in `results.json` (see §5). These images are included in the raw zip files for visual inspection but are not part of the aggregated CSVs.

---

## 5. Class label mappings

Labels are taken directly from the `superclass_names` field in `results.json`. Index order matches `per_class_f1`, `confusion_matrix`, and all per-class arrays.

### MHEALTH (12 classes)

| Index | Label in data |
|---|---|
| 0 | STANDING |
| 1 | SITTING |
| 2 | LYING |
| 3 | WALKING |
| 4 | CLIMBING_STAIRS |
| 5 | WAIST_BENDS |
| 6 | ARM_ELEVATION |
| 7 | KNEES_BENDING |
| 8 | CYCLING |
| 9 | JOGGING |
| 10 | RUNNING |
| 11 | JUMP_FRONT_BACK |

### UCI-HAR (6 classes)

| Index | Label in data |
|---|---|
| 0 | WALKING |
| 1 | WALKING_UPSTAIRS |
| 2 | WALKING_DOWNSTAIRS |
| 3 | SITTING |
| 4 | STANDING |
| 5 | LAYING |

---

## 6. Aggregated CSV files

All 12 CSV files in `aggregated/` are produced by `aggregate_metrics.py` (rounds, devices, evals, summaries) and `extract_perf_timings.py` (perf timings, both datasets). The `tx_pin_map_flowertrained_*.csv` files are copied from `outputs/tx_pin_map.csv` and `outputs_ucihar/tx_pin_map.csv`. Every value is read directly from the raw files; no value is imputed or estimated.

---

### 6.1 all_rounds_mhealth.csv / all_rounds_ucihar.csv

One row per aggregation round per session. **220 rows** per file (20 sessions × 11 rounds).  
34 columns (MHEALTH) / 28 columns (UCI-HAR).

| Column | Type | Source field | Description |
|---|---|---|---|
| `session_id` | string | directory name | Session directory name (e.g. `baseline_20260424_201227`) |
| `variant` | string | `experiment_config.json` → `variant` | `"baseline"` or `"optimized"` |
| `dataset` | string | derived | `"MHEALTH"` or `"UCIHAR"` |
| `round` | int | `round` | Round index (0–10) |
| `accuracy` | float | `accuracy` | Macro-averaged test accuracy |
| `loss` | float | `loss` | Cross-entropy test loss |
| `f1_macro` | float | `f1_macro` | Macro-averaged F1 |
| `f1_weighted` | float | `f1_weighted` | Weighted-averaged F1 |
| `precision_macro` | float | `precision_macro` | Macro-averaged precision |
| `recall_macro` | float | `recall_macro` | Macro-averaged recall |
| `specificity_macro` | float | `specificity_macro` | Macro-averaged specificity |
| `auc_macro` | float | `auc_macro` | Macro one-vs-rest AUC |
| `num_samples` | int | `num_samples` | Test set size (514 MHEALTH; 2947 UCI-HAR) |
| `num_classes` | int | `num_classes` | Number of classes (12 or 6) |
| `blockchain_blocks` | int | `blockchain_blocks` | On-chain blocks written this round |
| `round_wall_time_s` | float | `round_wall_time_s` | Round wall time in seconds (rounds 1–10); Unix session-start timestamp for round 0 — see §1.1 note |
| `model_payload_bytes` | int | `model_payload_bytes` | Serialised model size in bytes (3,439,144 MHEALTH; 3,420,320 UCI-HAR) |
| `ipfs_model_cid` | string | `ipfs_cids.model_cid` | IPFS CID of global model |
| `ipfs_metrics_cid` | string | `ipfs_cids.metrics_cid` | IPFS CID of metrics JSON |
| `ipfs_local_cid` | string | `ipfs_cids.local_cid` | IPFS CID of local update summaries (empty in round 0) |
| `ipfs_vote_cid` | string | `ipfs_cids.vote_cid` | IPFS CID of vote artefact (empty in round 0) |
| `timestamp` | string | `timestamp` | ISO-8601 datetime of this record |
| `f1_class_0` … `f1_class_11` | float | `per_class_f1[i]` | Per-class F1 (12 columns for MHEALTH, 6 for UCI-HAR) |

---

### 6.2 all_devices_mhealth.csv / all_devices_ucihar.csv

One row per client per training round. **2,000 rows** per file for both datasets (20 sessions × 10 rounds × 10 clients).  
12 columns.

| Column | Type | Source field | Description |
|---|---|---|---|
| `session_id` | string | directory name | Session directory name |
| `variant` | string | `experiment_config.json` | `"baseline"` or `"optimized"` |
| `dataset` | string | derived | `"MHEALTH"` or `"UCIHAR"` |
| `round` | int | `round` | Training round index (1–10) |
| `client_id` | int | `devices[].client_id` | Client identifier (0-indexed) |
| `train_loss` | float | `devices[].train_loss` | Final local training loss |
| `num_examples` | int | `devices[].num_examples` | Training samples used |
| `training_time_s` | float | `devices[].training_time` | Local training wall time in seconds (raw JSON key is `training_time`) |
| `active_classes` | int | `devices[].active_classes` | Distinct activity classes in this client's shard |
| `cpu_percent` | float | `devices[].cpu_percent` | Mean CPU utilisation (%) during training |
| `ram_used_mb` | float | `devices[].ram_used_mb` | Peak RAM used in MB |
| `cpu_temp_c` | float | `devices[].cpu_temp_c` | Mean CPU die temperature in °C |

---

### 6.3 all_client_evals_mhealth.csv / all_client_evals_ucihar.csv

One row per client per evaluation round. **2,000 rows** per file for both datasets (20 sessions × 10 rounds × 10 clients).  
15 columns.

| Column | Type | Source field | Description |
|---|---|---|---|
| `session_id` | string | directory name | Session directory name |
| `variant` | string | `experiment_config.json` | `"baseline"` or `"optimized"` |
| `dataset` | string | derived | `"MHEALTH"` or `"UCIHAR"` |
| `round` | int | `round` | Evaluation round index (1–10) |
| `client_id` | int | `client_id` | Client identifier (0-indexed) |
| `eval_loss` | float | `eval_loss` | Cross-entropy loss on local held-out data |
| `eval_acc` | float | `eval_acc` | Accuracy on local held-out data |
| `eval_f1` | float | `eval_f1` | Macro-F1 on local held-out data |
| `eval_auc` | float | `eval_auc` | Macro one-vs-rest AUC on local held-out data |
| `num_examples` | int | `num-examples` | Local evaluation sample count (raw JSON key uses a hyphen) |
| `eval_time_seconds` | float | `eval_time_seconds` | Evaluation wall time in seconds |
| `cpu_percent` | float | `cpu_percent` | Mean CPU utilisation (%) during evaluation |
| `ram_used_mb` | float | `ram_used_mb` | Peak RAM used in MB during evaluation |
| `cpu_temp_c` | float | `cpu_temp_c` | Mean CPU die temperature in °C during evaluation |
| `timestamp` | string | `timestamp` | ISO-8601 datetime of this record |

---

### 6.4 perf_timings_mhealth.csv / perf_timings_ucihar.csv

One row per timing event parsed from the 20 `perf_*.log` files of each dataset. **2,560 rows per file.**  
8 columns. Both files share the same schema and event counts; the duration statistics differ between datasets (tables below).

| Column | Type | Description |
|---|---|---|
| `session_id` | string | Session directory name |
| `variant` | string | `"baseline"` or `"optimized"` |
| `round` | int | Aggregation round (0–10) |
| `event_type` | string | One of: `ipfs_upload`, `gas_estimate`, `gas_price_fetch`, `tx_send`, `tx_confirm`, `chain_verify`, `round_overhead` |
| `block_type` | string | `"GLOBAL"`, `"LOCAL"`, `"VOTE"`, or `""` (where not applicable) |
| `duration_ms` | float | Event duration in milliseconds |
| `extra_key` | string | Supplementary field name (`"estimated_gas"`, `"fetched_gwei"`, `"block_number"`, `"valid"`, or `""`) |
| `extra_value` | string | Supplementary field value as a string; parse to numeric where needed |

**Verified statistics — MHEALTH (`perf_timings_mhealth.csv`):**

| event_type | n | mean (ms) | std (ms) |
|---|---|---|---|
| `tx_confirm` | 620 | 47,913 | 55,248 |
| `tx_send` | 620 | 320 | 144 |
| `gas_estimate` | 340 | 526 | 248 |
| `gas_price_fetch` | 320 | 175 | 101 |
| `ipfs_upload` (GLOBAL) | 110 | 29,773 | 46,166 |
| `ipfs_upload` (LOCAL) | 100 | 1,804 | 580 |
| `ipfs_upload` (VOTE) | 100 | 897 | 174 |
| `chain_verify` | 130 | 532 | 232 |
| `round_overhead` (baseline) | 110 | 1,820 | 740 |
| `round_overhead` (optimized) | 110 | 1,079 | 510 |

**Verified statistics — UCI-HAR (`perf_timings_ucihar.csv`):**

| event_type | n | mean (ms) | std (ms) |
|---|---|---|---|
| `tx_confirm` | 620 | 44,197 | 36,892 |
| `tx_send` | 620 | 323 | 81 |
| `gas_estimate` | 340 | 489 | 103 |
| `gas_price_fetch` | 320 | 169 | 43 |
| `ipfs_upload` (GLOBAL) | 110 | 11,819 | 10,176 |
| `ipfs_upload` (LOCAL) | 100 | 2,845 | 2,254 |
| `ipfs_upload` (VOTE) | 100 | 1,094 | 1,369 |
| `chain_verify` | 130 | 513 | 78 |
| `round_overhead` (baseline) | 110 | 1,700 | 319 |
| `round_overhead` (optimized) | 110 | 3,190 | 23,092 |

The UCI-HAR `round_overhead` for the optimized variant carries one extreme outlier (a single round with a very long network stall), which inflates the mean and std; the median better represents that cell.

---

### 6.5 session_summary_mhealth.csv / session_summary_ucihar.csv

One row per session. **20 rows** per file.  
15 columns. All numeric fields are computed from the raw `results.json` global records. Wall times exclude round 0 (see §1.1 note).

| Column | Type | Description |
|---|---|---|
| `session_id` | string | Session directory name |
| `variant` | string | `"baseline"` or `"optimized"` |
| `dataset` | string | `"MHEALTH"` or `"UCIHAR"` |
| `num_rounds` | int | Total global records including round 0 (always 11) |
| `final_accuracy` | float | Test accuracy at round 10 |
| `final_f1_macro` | float | Macro-F1 at round 10 |
| `final_auc_macro` | float | Macro AUC at round 10 |
| `final_loss` | float | Test loss at round 10 |
| `peak_accuracy` | float | Highest test accuracy across all 11 rounds |
| `mean_accuracy` | float | Mean test accuracy across all 11 rounds (0–10) |
| `peak_f1_macro` | float | Highest macro-F1 across all 11 rounds |
| `mean_round_wall_time_s` | float | Mean round wall time in seconds over rounds 1–10 (round 0 excluded) |
| `total_wall_time_s` | float | Sum of round wall times for rounds 1–10 in seconds |
| `num_samples` | int | Test set size (514 MHEALTH; 2,947 UCI-HAR) |
| `model_payload_bytes` | int | Serialised model size in bytes |

---

### 6.6 tx_pin_map_flowertrained_mhealth.csv / tx_pin_map_flowertrained_ucihar.csv

One row per IPFS pin and its on-chain transaction. **840 rows** per file = 20 sessions × 42 pins per session. Per session: round 0 writes 2 GLOBAL pins (model + metrics); rounds 1–10 each write 4 pins (2 GLOBAL + 1 LOCAL + 1 VOTE), so 2 + 10 × 4 = 42. These 42 pins map to **31 distinct transactions** per session, because the model and metrics pins inside each GLOBAL block share one transaction.  
12 columns. Copied without modification from `outputs/tx_pin_map.csv` and `outputs_ucihar/tx_pin_map.csv`.

**Pin success rates (verified):**
- MHEALTH: 816 / 840 = 97.1%
- UCI-HAR: 840 / 840 = 100.0%

| Column | Type | Description |
|---|---|---|
| `run` | string | Session directory name |
| `variant` | string | `"baseline"` or `"optimized"` |
| `pinata_account` | string | Pinata account alias number used |
| `fl_round` | int | FL round index (0–10) |
| `block_type` | string | `"GLOBAL"`, `"LOCAL"`, or `"VOTE"` |
| `expected_pin` | string | Descriptive name of the expected pin (e.g. `round_0_global_model`) |
| `pin_status` | string | `"success"` if confirmed in Pinata; `"failed"` otherwise |
| `tx_hash` | string | Ethereum transaction hash on Base mainnet |
| `basescan_url` | string | Full URL to view the transaction on Basescan |
| `ipfs_hash` | string | IPFS CID confirmed from the Pinata API |
| `pinata_account_actual` | string | Pinata account that holds the pin (e.g. `account_1`) |
| `date_pinned` | string | ISO-8601 datetime when the pin was confirmed |

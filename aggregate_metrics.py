#!/usr/bin/env python3
"""
aggregate_metrics.py
====================
Reads all 40 FL experiment session results.json files (MHEALTH: outputs/,
UCI-HAR: outputs_ucihar/) and produces flat CSV tables suitable for
the Data in Brief companion paper.

Outputs written to aggregated/:
  all_rounds_mhealth.csv        – one row per global record (200 rows)
  all_rounds_ucihar.csv         – one row per global record (200 rows)
  all_devices_mhealth.csv       – one row per device per round (~2 000 rows)
  all_devices_ucihar.csv        – one row per device per round (~1 800 rows)
  all_client_evals_mhealth.csv  – one row per client evaluation record
  all_client_evals_ucihar.csv   – one row per client evaluation record
  session_summary_mhealth.csv   – per-session aggregate statistics
  session_summary_ucihar.csv    – per-session aggregate statistics

Usage:
  python aggregate_metrics.py
"""

import json
import os
import re
import sys
from pathlib import Path
import csv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).parent
OUT_MHEALTH = REPO_ROOT / "outputs"
OUT_UCIHAR  = REPO_ROOT / "outputs_ucihar"
AGG_DIR     = REPO_ROOT / "aggregated"
AGG_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def session_dirs(base: Path):
    """Return sorted list of session directories inside *base*, skipping broken symlinks."""
    result = []
    for d in base.iterdir():
        try:
            if d.is_dir() and re.match(r"(baseline|optimized)_\d{8}_\d{6}$", d.name):
                result.append(d)
        except (PermissionError, OSError):
            pass
    return sorted(result)


def safe_get(d, *keys, default=""):
    """Nested dict access with a safe default."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
        if d == default:
            return default
    return d


def parse_results_ndjson(fpath: Path):
    """
    Parse a results.json NDJSON file.
    Returns three lists: global_records, device_training_records, client_eval_records.
    Each line is either a single JSON object or (for client_eval) a JSON array.
    """
    globals_      = []
    device_train  = []
    client_evals  = []

    with open(fpath, "r") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"  WARNING: JSON error in {fpath}:{lineno} — {exc}", file=sys.stderr)
                continue

            # client_eval records are wrapped in a JSON array
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict) and item.get("type") == "client_eval":
                        client_evals.append(item)
            elif isinstance(obj, dict):
                rec_type = obj.get("type", "")
                if rec_type == "global":
                    globals_.append(obj)
                elif rec_type == "device_training":
                    device_train.append(obj)
                elif rec_type == "client_eval":
                    client_evals.append(obj)
                else:
                    # Some round-0 records may lack explicit type field; check keys
                    if "accuracy" in obj and "round" in obj:
                        globals_.append(obj)
                    elif "devices" in obj:
                        device_train.append(obj)

    return globals_, device_train, client_evals


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------
def extract_global_row(rec, session_id, variant, dataset):
    ipfs = rec.get("ipfs_cids") or {}
    row = {
        "session_id":            session_id,
        "variant":               variant,
        "dataset":               dataset,
        "round":                 rec.get("round", ""),
        "accuracy":              rec.get("accuracy", ""),
        "loss":                  rec.get("loss", ""),
        "f1_macro":              rec.get("f1_macro", ""),
        "f1_weighted":           rec.get("f1_weighted", ""),
        "precision_macro":       rec.get("precision_macro", ""),
        "recall_macro":          rec.get("recall_macro", ""),
        "specificity_macro":     rec.get("specificity_macro", ""),
        "auc_macro":             rec.get("auc_macro", ""),
        "num_samples":           rec.get("num_samples", ""),
        "num_classes":           rec.get("num_classes", ""),
        "blockchain_blocks":     rec.get("blockchain_blocks", ""),
        "round_wall_time_s":     rec.get("round_wall_time_s", ""),
        "model_payload_bytes":   rec.get("model_payload_bytes", ""),
        "ipfs_model_cid":        ipfs.get("model_cid", ""),
        "ipfs_metrics_cid":      ipfs.get("metrics_cid", ""),
        "ipfs_local_cid":        ipfs.get("local_cid", ""),
        "ipfs_vote_cid":         ipfs.get("vote_cid", ""),
        "timestamp":             rec.get("timestamp", ""),
    }
    # Append per-class F1 values for traceability
    per_class_f1 = rec.get("per_class_f1", [])
    for i, v in enumerate(per_class_f1):
        row[f"f1_class_{i}"] = v
    return row


def extract_device_rows(rec, session_id, variant, dataset):
    rows = []
    rnd = rec.get("round", "")
    for dev in rec.get("devices", []):
        rows.append({
            "session_id":      session_id,
            "variant":         variant,
            "dataset":         dataset,
            "round":           rnd,
            "client_id":       dev.get("client_id", ""),
            "train_loss":      dev.get("train_loss", ""),
            "num_examples":    dev.get("num_examples", ""),
            "training_time_s": dev.get("training_time", ""),
            "active_classes":  dev.get("active_classes", ""),
            "cpu_percent":     dev.get("cpu_percent", ""),
            "ram_used_mb":     dev.get("ram_used_mb", ""),
            "cpu_temp_c":      dev.get("cpu_temp_c", ""),
        })
    return rows


def extract_eval_rows(rec, session_id, variant, dataset):
    return [{
        "session_id":       session_id,
        "variant":          variant,
        "dataset":          dataset,
        "round":            rec.get("round", ""),
        "client_id":        rec.get("client_id", ""),
        "eval_loss":        rec.get("eval_loss", ""),
        "eval_acc":         rec.get("eval_acc", ""),
        "eval_f1":          rec.get("eval_f1", ""),
        "eval_auc":         rec.get("eval_auc", ""),
        "num_examples":     rec.get("num-examples", rec.get("num_examples", "")),
        "eval_time_seconds":rec.get("eval_time_seconds", ""),
        "cpu_percent":      rec.get("cpu_percent", ""),
        "ram_used_mb":      rec.get("ram_used_mb", ""),
        "cpu_temp_c":       rec.get("cpu_temp_c", ""),
        "timestamp":        rec.get("timestamp", ""),
    }]


# ---------------------------------------------------------------------------
# Session summary
# ---------------------------------------------------------------------------
def compute_session_summary(global_records, session_id, variant, dataset):
    """Compute per-session summary statistics from global records."""
    if not global_records:
        return {}

    # Final-round record (highest round number)
    final = max(global_records, key=lambda r: r.get("round", 0))
    # Peak accuracy across all rounds
    accs = [r.get("accuracy", 0) for r in global_records if isinstance(r.get("accuracy"), (int, float))]
    f1s  = [r.get("f1_macro", 0) for r in global_records if isinstance(r.get("f1_macro"), (int, float))]
    # Round 0 stores the session-start Unix timestamp in round_wall_time_s, not a duration.
    # Exclude round 0 so mean/total only reflect actual training round durations (rounds 1-10).
    wall = [r.get("round_wall_time_s") for r in global_records
            if r.get("round", 0) > 0 and isinstance(r.get("round_wall_time_s"), (int, float))]

    def safe_float(lst, func):
        try:
            return func(lst)
        except Exception:
            return ""

    return {
        "session_id":              session_id,
        "variant":                 variant,
        "dataset":                 dataset,
        "num_rounds":              len(global_records),
        "final_accuracy":          final.get("accuracy", ""),
        "final_f1_macro":          final.get("f1_macro", ""),
        "final_auc_macro":         final.get("auc_macro", ""),
        "final_loss":              final.get("loss", ""),
        "peak_accuracy":           safe_float(accs, max),
        "mean_accuracy":           safe_float(accs, lambda l: sum(l)/len(l)) if accs else "",
        "peak_f1_macro":           safe_float(f1s, max),
        "mean_round_wall_time_s":  safe_float(wall, lambda l: sum(l)/len(l)) if wall else "",
        "total_wall_time_s":       safe_float(wall, sum) if wall else "",
        "num_samples":             final.get("num_samples", ""),
        "model_payload_bytes":     final.get("model_payload_bytes", ""),
    }


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------
def write_csv(rows, path: Path):
    if not rows:
        print(f"  WARNING: no rows to write for {path.name}", file=sys.stderr)
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows):>6} rows → {path.name}")


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def process_dataset(base_path: Path, dataset_label: str):
    """Process all sessions under *base_path* for the given dataset label."""
    all_globals     = []
    all_devices     = []
    all_evals       = []
    all_summaries   = []

    sessions = session_dirs(base_path)
    if not sessions:
        print(f"  ERROR: no session directories found under {base_path}", file=sys.stderr)
        return [], [], [], []

    print(f"\nProcessing {dataset_label}: {len(sessions)} sessions under {base_path.name}/")

    for sdir in sessions:
        session_id = sdir.name
        rjson = sdir / "results.json"
        cfgjson = sdir / "experiment_config.json"

        if not rjson.exists():
            print(f"  SKIP {session_id}: results.json not found", file=sys.stderr)
            continue

        # Determine variant from experiment_config.json (canonical source)
        variant = "unknown"
        if cfgjson.exists():
            try:
                with open(cfgjson) as fh:
                    cfg = json.load(fh)
                variant = cfg.get("variant", session_id.split("_")[0])
            except Exception:
                variant = session_id.split("_")[0]
        else:
            variant = session_id.split("_")[0]

        g_recs, d_recs, e_recs = parse_results_ndjson(rjson)

        for rec in g_recs:
            all_globals.append(extract_global_row(rec, session_id, variant, dataset_label))

        for rec in d_recs:
            all_devices.extend(extract_device_rows(rec, session_id, variant, dataset_label))

        for rec in e_recs:
            all_evals.extend(extract_eval_rows(rec, session_id, variant, dataset_label))

        summary = compute_session_summary(g_recs, session_id, variant, dataset_label)
        if summary:
            all_summaries.append(summary)

        print(f"  {session_id}: {len(g_recs)} global | {len(d_recs)} device_training | {len(e_recs)} client_eval records")

    return all_globals, all_devices, all_evals, all_summaries


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("aggregate_metrics.py — FL-Blockchain-EVM dataset aggregator")
    print("=" * 60)

    # MHEALTH
    mh_globals, mh_devices, mh_evals, mh_summaries = process_dataset(OUT_MHEALTH, "MHEALTH")
    write_csv(mh_globals,   AGG_DIR / "all_rounds_mhealth.csv")
    write_csv(mh_devices,   AGG_DIR / "all_devices_mhealth.csv")
    write_csv(mh_evals,     AGG_DIR / "all_client_evals_mhealth.csv")
    write_csv(mh_summaries, AGG_DIR / "session_summary_mhealth.csv")

    # UCI-HAR
    uh_globals, uh_devices, uh_evals, uh_summaries = process_dataset(OUT_UCIHAR, "UCIHAR")
    write_csv(uh_globals,   AGG_DIR / "all_rounds_ucihar.csv")
    write_csv(uh_devices,   AGG_DIR / "all_devices_ucihar.csv")
    write_csv(uh_evals,     AGG_DIR / "all_client_evals_ucihar.csv")
    write_csv(uh_summaries, AGG_DIR / "session_summary_ucihar.csv")

    # Verification summary
    print("\n" + "=" * 60)
    print("Verification summary")
    print("=" * 60)
    print(f"  MHEALTH  global records : {len(mh_globals)}")
    print(f"  MHEALTH  device records : {len(mh_devices)}")
    print(f"  MHEALTH  eval   records : {len(mh_evals)}")
    print(f"  UCI-HAR  global records : {len(uh_globals)}")
    print(f"  UCI-HAR  device records : {len(uh_devices)}")
    print(f"  UCI-HAR  eval   records : {len(uh_evals)}")

    # Basic sanity checks
    ok = True
    if len(mh_globals) != 220:
        print(f"  WARNING: expected 220 MHEALTH global records (11 rounds × 20 sessions), got {len(mh_globals)}", file=sys.stderr)
        ok = False
    if len(uh_globals) != 220:
        print(f"  WARNING: expected 220 UCI-HAR global records (11 rounds × 20 sessions), got {len(uh_globals)}", file=sys.stderr)
        ok = False
    if ok:
        print("  All row-count checks passed.")

    print(f"\nOutput files written to: {AGG_DIR}/")


if __name__ == "__main__":
    main()

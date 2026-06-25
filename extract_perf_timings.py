#!/usr/bin/env python3
"""
extract_perf_timings.py
=======================
Parses the per-session performance log files (perf_*.log) from the MHEALTH
and UCI-HAR experiment sessions and produces flat CSV tables of blockchain
and IPFS timing events suitable for the Data in Brief companion paper.

NOTE: The original May 2026 UCI-HAR sessions do not contain perf_*.log files.
      After the re-run (June 2026) UCI-HAR sessions will have perf logs and
      this script will process them automatically.

Outputs written to aggregated/:
  perf_timings_mhealth.csv  – timing events from outputs/
  perf_timings_ucihar.csv   – timing events from outputs_ucihar/
                              (empty/skipped if no perf logs present)

Column schema:
  session_id      – session directory name (e.g. baseline_20260424_201227)
  variant         – baseline | optimized
  round           – FL round index (0-based)
  event_type      – see EVENT TYPES below
  block_type      – GLOBAL | LOCAL | VOTE | "" (where not applicable)
  duration_ms     – numeric duration in milliseconds (float)
  extra_key       – supplementary field name (e.g. "estimated", "block")
  extra_value     – supplementary field value (string)

EVENT TYPES:
  ipfs_upload         – IPFS CID upload (all block types)
  gas_estimate        – gas-limit RPC call
  gas_price_fetch     – gas-price RPC call
  tx_send             – transaction submission
  tx_confirm          – transaction confirmation (submit → confirm)
  chain_verify        – verifyChain() call
  round_overhead      – total non-training overhead for the round

Usage:
  python extract_perf_timings.py
"""

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
# Regex patterns for each log event type
# ---------------------------------------------------------------------------
# ipfs_global / ipfs_local / ipfs_vote
RE_IPFS = re.compile(
    r"ipfs_(global|local|vote)\s+.*?upload_ms=([\d.]+)",
    re.IGNORECASE
)

# gas_limit  type=X  estimated=N  estimate_ms=N
RE_GAS_LIMIT = re.compile(
    r"gas_limit\s+type=(\w+)\s+estimated=(\d+)\s+estimate_ms=([\d.]+)",
    re.IGNORECASE
)

# gas_price  fetched=N  fetch_ms=N
RE_GAS_PRICE = re.compile(
    r"gas_price\s+fetched=(\d+)\s+fetch_ms=([\d.]+)",
    re.IGNORECASE
)

# tx_sent  type=X  hash=...  send_ms=N
RE_TX_SENT = re.compile(
    r"tx_sent\s+type=(\w+)\s+.*?send_ms=([\d.]+)",
    re.IGNORECASE
)

# confirmed  idx=N  block=N  submit_to_confirm_ms=N
RE_CONFIRMED = re.compile(
    r"confirmed\s+idx=(\d+)\s+block=(\d+)\s+submit_to_confirm_ms=([\d.]+)",
    re.IGNORECASE
)

# verify_chain  valid=True/False  ms=N
RE_VERIFY = re.compile(
    r"verify_chain\s+valid=(\w+)\s+ms=([\d.]+)",
    re.IGNORECASE
)

# --- ROUND N end  total_overhead_ms=N
RE_ROUND_END = re.compile(
    r"---\s*ROUND\s+(\d+)\s+end\s+total_overhead_ms=([\d.]+)",
    re.IGNORECASE
)

# --- ROUND N start  mode=X
RE_ROUND_START = re.compile(
    r"---\s*ROUND\s+(\d+)\s+start",
    re.IGNORECASE
)

BLOCK_TYPE_MAP = {
    "global": "GLOBAL",
    "local":  "LOCAL",
    "vote":   "VOTE",
}


def _is_session_dir(d: Path) -> bool:
    try:
        return d.is_dir() and re.match(r"(baseline|optimized)_\d{8}_\d{6}$", d.name)
    except (PermissionError, OSError):
        return False


# ---------------------------------------------------------------------------
# Log parser
# ---------------------------------------------------------------------------
def parse_perf_log(fpath: Path, session_id: str, variant: str):
    """
    Parse a single perf_*.log file.
    Returns a list of event dicts.
    """
    events   = []
    cur_round = 0  # default; updated on ROUND N start/end lines

    with open(fpath, "r", errors="replace") as fh:
        for line in fh:
            # Update current round from ROUND N start marker
            m = RE_ROUND_START.search(line)
            if m:
                cur_round = int(m.group(1))
                continue

            # --- ROUND N end
            m = RE_ROUND_END.search(line)
            if m:
                cur_round = int(m.group(1))
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "round_overhead",
                    "block_type":  "",
                    "duration_ms": float(m.group(2)),
                    "extra_key":   "",
                    "extra_value": "",
                })
                continue

            # ipfs_upload
            m = RE_IPFS.search(line)
            if m:
                btype = BLOCK_TYPE_MAP.get(m.group(1).lower(), m.group(1).upper())
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "ipfs_upload",
                    "block_type":  btype,
                    "duration_ms": float(m.group(2)),
                    "extra_key":   "",
                    "extra_value": "",
                })
                continue

            # gas_estimate
            m = RE_GAS_LIMIT.search(line)
            if m:
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "gas_estimate",
                    "block_type":  m.group(1).upper(),
                    "duration_ms": float(m.group(3)),
                    "extra_key":   "estimated_gas",
                    "extra_value": m.group(2),
                })
                continue

            # gas_price_fetch
            m = RE_GAS_PRICE.search(line)
            if m:
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "gas_price_fetch",
                    "block_type":  "",
                    "duration_ms": float(m.group(2)),
                    "extra_key":   "fetched_gwei",
                    "extra_value": m.group(1),
                })
                continue

            # tx_send
            m = RE_TX_SENT.search(line)
            if m:
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "tx_send",
                    "block_type":  m.group(1).upper(),
                    "duration_ms": float(m.group(2)),
                    "extra_key":   "",
                    "extra_value": "",
                })
                continue

            # tx_confirm
            m = RE_CONFIRMED.search(line)
            if m:
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "tx_confirm",
                    "block_type":  "",
                    "duration_ms": float(m.group(3)),
                    "extra_key":   "block_number",
                    "extra_value": m.group(2),
                })
                continue

            # chain_verify
            m = RE_VERIFY.search(line)
            if m:
                events.append({
                    "session_id":  session_id,
                    "variant":     variant,
                    "round":       cur_round,
                    "event_type":  "chain_verify",
                    "block_type":  "",
                    "duration_ms": float(m.group(2)),
                    "extra_key":   "valid",
                    "extra_value": m.group(1),
                })
                continue

    return events


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
FIELDNAMES = ["session_id", "variant", "round", "event_type",
              "block_type", "duration_ms", "extra_key", "extra_value"]


def process_dataset(base_path: Path, dataset_label: str, output_csv: Path):
    """Process all perf logs under base_path, write output_csv. Returns events list."""
    all_events     = []
    sessions_found = 0

    dirs = sorted([d for d in base_path.iterdir() if _is_session_dir(d)])
    print(f"\nFound {len(dirs)} {dataset_label} session directories")

    for sdir in dirs:
        session_id = sdir.name
        variant    = session_id.split("_")[0]

        perf_logs = list(sdir.glob("perf_*.log"))
        if not perf_logs:
            print(f"  SKIP {session_id}: no perf_*.log found", file=sys.stderr)
            continue

        events = parse_perf_log(perf_logs[0], session_id, variant)
        all_events.extend(events)
        sessions_found += 1

        n_overhead = sum(1 for e in events if e["event_type"] == "round_overhead")
        n_ipfs     = sum(1 for e in events if e["event_type"] == "ipfs_upload")
        n_tx       = sum(1 for e in events if e["event_type"] == "tx_send")
        n_confirm  = sum(1 for e in events if e["event_type"] == "tx_confirm")
        print(f"  {session_id}: {len(events)} events "
              f"(round_end={n_overhead}, ipfs={n_ipfs}, tx={n_tx}, confirm={n_confirm})")

    if all_events:
        with open(output_csv, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_events)
        print(f"\n  Wrote {len(all_events):>6} rows → {output_csv.name}")
    else:
        print(f"  No perf events found for {dataset_label} — CSV not written", file=sys.stderr)

    return all_events, sessions_found


def print_summary(label: str, events: list):
    if not events:
        return
    print(f"\n{label} ({len(events)} events total):")
    by_type = {}
    for ev in events:
        by_type[ev["event_type"]] = by_type.get(ev["event_type"], 0) + 1
    for etype, count in sorted(by_type.items()):
        print(f"    {etype:<25}: {count}")

    for variant_label, variant_key in [("Baseline", "baseline"), ("Optimized", "optimized")]:
        oh = [e["duration_ms"] for e in events
              if e["event_type"] == "round_overhead" and e["variant"] == variant_key]
        if oh:
            print(f"  {variant_label} round_overhead: mean={sum(oh)/len(oh):.0f} ms, n={len(oh)}")

    ipfs_base = [e["duration_ms"] for e in events
                 if e["event_type"] == "ipfs_upload" and e["variant"] == "baseline"]
    if ipfs_base:
        print(f"  Baseline IPFS upload:   mean={sum(ipfs_base)/len(ipfs_base):.0f} ms, n={len(ipfs_base)}")


def main():
    print("=" * 60)
    print("extract_perf_timings.py — blockchain/IPFS timing extractor")
    print("=" * 60)

    mh_events, mh_sessions = process_dataset(
        OUT_MHEALTH, "MHEALTH", AGG_DIR / "perf_timings_mhealth.csv"
    )
    uc_events, uc_sessions = process_dataset(
        OUT_UCIHAR, "UCI-HAR", AGG_DIR / "perf_timings_ucihar.csv"
    )

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  MHEALTH sessions processed : {mh_sessions}")
    print(f"  UCI-HAR sessions processed : {uc_sessions}")
    print_summary("MHEALTH", mh_events)
    print_summary("UCI-HAR", uc_events)


if __name__ == "__main__":
    main()

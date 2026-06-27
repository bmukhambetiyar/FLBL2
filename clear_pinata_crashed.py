"""clear_pinata_crashed.py — Remove pins AND local directories for crashed UCI-HAR sessions.

Reads outputs_ucihar/tx_pin_map.csv to find which CIDs belong to crashed sessions,
unpins them from Pinata, then deletes the local session directories.

Usage:
    python clear_pinata_crashed.py          # dry-run (shows what would be deleted)
    python clear_pinata_crashed.py --delete  # actually unpins and removes dirs
"""

import csv
import sys
import time
import shutil
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=Path(__file__).parent / '.env')

DRY_RUN = "--delete" not in sys.argv

# ── Crashed / incomplete sessions to remove ───────────────────────────────────
CRASHED_SESSIONS = {
    # June 26-27 2026 re-run — dropped tx / nonce conflict
    "baseline_20260626_200129",   # 7/10 rounds (tx dropped at round 7)
    "baseline_20260626_204757",   # 0 rounds (nonce conflict)
    "baseline_20260626_204905",   # 0 rounds (nonce conflict)
    "optimized_20260626_204728",  # 0 rounds (nonce conflict)
    "optimized_20260626_204834",  # 0 rounds (nonce conflict)
}

TX_PIN_MAP = Path("outputs_ucihar/tx_pin_map.csv")
UCIHAR_DIR = Path("outputs_ucihar")

JWTS = {
    "account_1": os.getenv("PINATA_JWT", ""),
    "account_2": os.getenv("PINATA_JWT_2", ""),
}


def collect_cids():
    """Read tx_pin_map.csv and collect CIDs belonging to crashed sessions."""
    if not TX_PIN_MAP.exists():
        print(f"WARNING: {TX_PIN_MAP} not found — skipping pin deletion.")
        return {}

    to_delete = {}  # cid → account_label
    for row in csv.DictReader(open(TX_PIN_MAP, newline="")):
        if row["run"] not in CRASHED_SESSIONS:
            continue
        if row.get("pin_status") != "success":
            continue
        cid = row.get("ipfs_hash", "").strip()
        if cid:
            to_delete[cid] = row.get("pinata_account_actual", "account_1")
    return to_delete


def delete_pins(to_delete: dict):
    by_account: dict[str, list] = {}
    for cid, acct in to_delete.items():
        by_account.setdefault(acct, []).append(cid)

    total_ok = total_fail = 0
    for acct_label, cids in by_account.items():
        if not cids:
            continue
        jwt = JWTS.get(acct_label, "")
        if not jwt:
            print(f"  WARNING: No JWT for {acct_label}, skipping {len(cids)} CIDs")
            continue
        print(f"\n  Unpinning {len(cids)} CIDs from {acct_label} ...")
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {jwt}"
        ok = fail = 0
        for i, cid in enumerate(cids, 1):
            r = s.delete(f"https://api.pinata.cloud/pinning/unpin/{cid}", timeout=30)
            if r.status_code == 200:
                ok += 1
            else:
                fail += 1
                print(f"    [WARN] Failed to unpin {cid} (HTTP {r.status_code})")
            if i % 20 == 0:
                print(f"    {i}/{len(cids)} done...")
            time.sleep(0.05)
        print(f"  Done — {ok} unpinned, {fail} failed")
        total_ok += ok
        total_fail += fail
    return total_ok, total_fail


def main():
    print("=" * 60)
    if DRY_RUN:
        print("DRY RUN — pass --delete to actually remove pins and dirs")
    else:
        print("DELETE MODE — removing pins and directories")
    print("=" * 60)

    # ── 1. Collect CIDs ──────────────────────────────────────────────────────
    to_delete = collect_cids()

    print(f"\nCrashed sessions     : {len(CRASHED_SESSIONS)}")
    print(f"Pinata CIDs to unpin : {len(to_delete)}")

    if to_delete:
        by_session: dict[str, int] = {}
        for row in csv.DictReader(open(TX_PIN_MAP, newline="")):
            if row["run"] in CRASHED_SESSIONS and row.get("ipfs_hash", "").strip():
                by_session[row["run"]] = by_session.get(row["run"], 0) + 1
        print("\nPins per session:")
        for sess in sorted(CRASHED_SESSIONS):
            n = by_session.get(sess, 0)
            d = UCIHAR_DIR / sess
            print(f"  {sess}  pins={n}  dir={'exists' if d.exists() else 'missing'}")

    print(f"\nDirectories to delete:")
    for sess in sorted(CRASHED_SESSIONS):
        d = UCIHAR_DIR / sess
        print(f"  {d}  {'EXISTS' if d.exists() else '(already gone)'}")

    if DRY_RUN:
        print("\nDry run complete. Pass --delete to proceed.")
        return

    # ── 2. Unpin from Pinata ─────────────────────────────────────────────────
    if to_delete:
        ok, fail = delete_pins(to_delete)
        print(f"\nTotal pins removed: {ok}  failed: {fail}")
    else:
        print("\nNo pins to remove.")

    # ── 3. Delete local directories ──────────────────────────────────────────
    print("\nDeleting local directories...")
    for sess in sorted(CRASHED_SESSIONS):
        d = UCIHAR_DIR / sess
        if d.exists():
            shutil.rmtree(d)
            print(f"  Deleted {d}")
        else:
            print(f"  Already gone: {d}")

    print("\nDone. Ready to re-run:")
    print("  N_SESSIONS=5 ./fl.sh train-ucihar")


if __name__ == "__main__":
    main()

"""clear_pinata_ucihar.py — Wipe all pins from the two UCI-HAR Pinata accounts.

Run this BEFORE the UCI-HAR re-run to free up storage.
Both accounts are dedicated to UCI-HAR only — safe to wipe entirely.

Usage:
    python clear_pinata_ucihar.py          # dry-run: shows what would be deleted
    python clear_pinata_ucihar.py --delete  # actually deletes all pins
"""

import sys
import time
import requests

DRY_RUN = "--delete" not in sys.argv

ACCOUNTS = {
    "account_1 (talgar.bayan@gmail.com)": (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiJkNzI1MzQyMC04NTM3LTRiMWUtOGMwMi1mMjZjZTQwODJiYzQi"
        "LCJlbWFpbCI6InRhbGdhci5iYXlhbkBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwicGluX3Bv"
        "bGljeSI6eyJyZWdpb25zIjpbeyJkZXNpcmVkUmVwbGljYXRpb25Db3VudCI6MSwiaWQiOiJGUkExIn0seyJk"
        "ZXNpcmVkUmVwbGljYXRpb25Db3VudCI6MSwiaWQiOiJOWUMxIn1dLCJ2ZXJzaW9uIjoxfSwibWZhX2VuYWJs"
        "ZWQiOmZhbHNlLCJzdGF0dXMiOiJBQ1RJVkUifSwiYXV0aGVudGljYXRpb25UeXBlIjoic2NvcGVkS2V5Iiwi"
        "c2NvcGVkS2V5S2V5IjoiMjVhYTZiYTRmNGVlYjRjNzQ3MjUiLCJzY29wZWRLZXlTZWNyZXQiOiJhOTgzZWVj"
        "MjRiNTRhMDY5MWJjMmI2YjY2ZDA5YWQ3MjA2MmYyNTBlMDEyMjg5Y2YwYTFkNWUxZjY2MzIwN2U0IiwiZXhw"
        "IjoxODExMjI4NjE3fQ.kyz9ox5ZT30mnFM3Ra5jEc6i6MoMs0n10Cdt6gUbfnA"
    ),
    "account_2 (bilmeimin2@gmail.com)": (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiIzOWFlMTcyYS0xODBlLTQ4OGUtYmUzNS1hYzg2ZWIxMWZhMjUi"
        "LCJlbWFpbCI6ImJpbG1laW1pbjJAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsInBpbl9wb2xp"
        "Y3kiOnsicmVnaW9ucyI6W3siZGVzaXJlZFJlcGxpY2F0aW9uQ291bnQiOjEsImlkIjoiRlJBMSJ9LHsiZGVz"
        "aXJlZFJlcGxpY2F0aW9uQ291bnQiOjEsImlkIjoiTllDMSJ9XSwidmVyc2lvbiI6MX0sIm1mYV9lbmFibGVk"
        "IjpmYWxzZSwic3RhdHVzIjoiQUNUSVZFIn0sImF1dGhlbnRpY2F0aW9uVHlwZSI6InNjb3BlZEtleSIsInNj"
        "b3BlZEtleUtleSI6ImQ1YzYyMjRhZjcwNDI2MzhkMDQ1Iiwic2NvcGVkS2V5U2VjcmV0IjoiNTFkMDEyNmM2"
        "NzNhNzFlYjg2YTY0MzM3ZDkzNDQ4MDdhYmJiN2VkYzU5YjgwOGVjNzY3NTk4ZjU2YTg4ODFhYiIsImV4cCI6"
        "MTgxMTI2MDc2Mn0.bQk72ckBw2eISfNOi6BUnPUgXmjGvXYIXrhSDjKrqbo"
    ),
}

def fetch_all_pins(session):
    """Fetch every pinned CID from the account (handles pagination)."""
    cids = []
    offset = 0
    page = 1000
    while True:
        r = session.get(
            "https://api.pinata.cloud/data/pinList",
            params={"status": "pinned", "pageLimit": page, "pageOffset": offset},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("rows", [])
        cids.extend(row["ipfs_pin_hash"] for row in rows)
        if len(rows) < page:
            break
        offset += page
    return cids


def unpin(session, cid):
    """Unpin a single CID. Returns True on success."""
    r = session.delete(
        f"https://api.pinata.cloud/pinning/unpin/{cid}",
        timeout=30,
    )
    return r.status_code == 200


def process_account(label, jwt):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {jwt}"

    # Check usage first
    usage = s.get("https://api.pinata.cloud/data/userPinnedDataTotal", timeout=15).json()
    pin_count = usage.get("pin_count", 0)
    size_gb   = usage.get("pin_size_total", 0) / 1e9
    print(f"  Current pins : {pin_count}")
    print(f"  Current size : {size_gb:.2f} GB")

    if pin_count == 0:
        print("  Nothing to delete.")
        return

    print(f"\n  Fetching all CIDs...")
    cids = fetch_all_pins(s)
    print(f"  Found {len(cids)} pinned CIDs")

    if DRY_RUN:
        print(f"\n  DRY RUN — would delete {len(cids)} pins.")
        print(f"  Run with --delete to actually remove them.")
        return

    print(f"\n  Deleting {len(cids)} pins...")
    ok = fail = 0
    for i, cid in enumerate(cids, 1):
        if unpin(s, cid):
            ok += 1
        else:
            fail += 1
            print(f"    [WARN] Failed to unpin {cid}")
        if i % 50 == 0:
            print(f"    {i}/{len(cids)} done...")
        time.sleep(0.05)   # stay under rate limit

    print(f"\n  Done — {ok} unpinned, {fail} failed.")

    # Verify
    usage2 = s.get("https://api.pinata.cloud/data/userPinnedDataTotal", timeout=15).json()
    print(f"  Remaining pins: {usage2.get('pin_count', '?')}")


if DRY_RUN:
    print("DRY RUN MODE — pass --delete to actually remove pins\n")
else:
    print("DELETE MODE — removing all pins from both UCI-HAR accounts\n")

for label, jwt in ACCOUNTS.items():
    try:
        process_account(label, jwt)
    except Exception as e:
        print(f"  ERROR on {label}: {e}")

print("\nDone.")

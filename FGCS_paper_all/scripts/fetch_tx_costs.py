#!/usr/bin/env python3
"""Recover the measured on-chain cost of every FLBL2 audit transaction.

Reads the transaction hashes already recorded in the tx/pin maps and fetches each
receipt from Base mainnet, giving the gas actually used and the price actually
paid. Nothing is re-run and no transaction is sent: this only reads state that
has been on chain since the experiments.

All FLBL2 experiments ran on Base mainnet. The RPC endpoint comes from the
BASE_SEPOLIA_RPC_URL entry in .env, a leftover name from early testing that
holds the Base mainnet URL.

Covers both datasets: 20 sessions each (10 baseline, 10 optimised), 10 rounds per
session, 620 transactions per dataset, 1,240 in total.

Writes FGCS_paper_all/data/tx_costs.csv, one row per unique transaction.

Usage:  venv/bin/python FGCS_paper_all/scripts/fetch_tx_costs.py [--eth-usd 2300]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "FGCS_paper_all" / "data" / "tx_costs.csv"
SOURCES = {
    "mhealth": ROOT / "aggregated" / "tx_pin_map_flowertrained_mhealth.csv",
    "ucihar": ROOT / "aggregated" / "tx_pin_map_flowertrained_ucihar.csv",
}
CONTRACT = "0xbe3feac76293711c5d32426860303afe24cdf527"  # lowercase for compare

BATCH = 25          # JSON-RPC batch size
PAUSE = 0.6         # seconds between batches; sustained bursts hit the CU cap
RETRIES = 6


def load_rows():
    """Unique tx hashes with the metadata already known from the pin maps."""
    seen: dict[str, dict] = {}
    for dataset, path in SOURCES.items():
        if not path.exists():
            sys.exit(f"missing input: {path}")
        for r in csv.DictReader(path.open()):
            h = (r.get("tx_hash") or "").strip()
            if not h or h in seen:
                continue
            seen[h] = {
                "tx_hash": h,
                "dataset": dataset,
                "run": r.get("run", ""),
                "variant": r.get("variant", ""),
                "fl_round": r.get("fl_round", ""),
                "block_type": r.get("block_type", ""),
            }
    return list(seen.values())


def rpc_batch(url: str, hashes: list[str]) -> dict[str, dict]:
    """eth_getTransactionReceipt for a batch of hashes -> {hash: receipt}."""
    payload = [
        {"jsonrpc": "2.0", "id": i, "method": "eth_getTransactionReceipt", "params": [h]}
        for i, h in enumerate(hashes)
    ]
    last = None
    for attempt in range(RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 429:
                last = "rate limited (HTTP 429)"
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            body = resp.json()
            if isinstance(body, dict):  # endpoint returned a single error object
                raise RuntimeError(body.get("error", body))
            out = {}
            for item in body:
                idx = item.get("id")
                if idx is None or not (0 <= idx < len(hashes)):
                    continue
                out[hashes[idx]] = item.get("result")
            return out
        except Exception as exc:  # noqa: BLE001 - retry on any transport error
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"batch failed after {RETRIES} attempts: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eth-usd", type=float, default=2300.0,
                    help="ETH price used for the USD column (default 2300)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.getenv("BASE_SEPOLIA_RPC_URL", "").strip()
    if not url:
        sys.exit("no RPC endpoint found in .env")

    rows = load_rows()
    print(f"unique transactions to fetch: {len(rows)}")

    by_hash = {r["tx_hash"]: r for r in rows}
    hashes = list(by_hash)
    fetched: dict[str, dict] = {}

    for i in range(0, len(hashes), BATCH):
        chunk = hashes[i:i + BATCH]
        fetched.update(rpc_batch(url, chunk))
        done = min(i + BATCH, len(hashes))
        print(f"  {done}/{len(hashes)}", end="\r", flush=True)
        time.sleep(PAUSE)
    print()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["tx_hash", "dataset", "run", "variant", "fl_round", "block_type",
              "status", "block_number", "gas_used", "effective_gas_price_wei",
              "fee_wei", "fee_eth", "fee_usd", "to_contract_match"]

    missing = 0
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for h in hashes:
            meta = dict(by_hash[h])
            rec = fetched.get(h)
            if not rec:
                missing += 1
                for k in fields:
                    meta.setdefault(k, "")
                meta["status"] = "NOT_FOUND"
                w.writerow(meta)
                continue
            gas_used = int(rec["gasUsed"], 16)
            price = int(rec.get("effectiveGasPrice") or "0x0", 16)
            fee_wei = gas_used * price
            meta.update({
                "status": "success" if int(rec["status"], 16) == 1 else "failed",
                "block_number": int(rec["blockNumber"], 16),
                "gas_used": gas_used,
                "effective_gas_price_wei": price,
                "fee_wei": fee_wei,
                "fee_eth": f"{fee_wei / 1e18:.18f}",
                "fee_usd": f"{fee_wei / 1e18 * args.eth_usd:.8f}",
                "to_contract_match": str((rec.get("to") or "").lower() == CONTRACT),
            })
            w.writerow(meta)

    print(f"wrote {OUT}  ({len(hashes)} rows, {missing} not found)")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

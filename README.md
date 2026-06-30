# FLBL2: Real-World Layer-2 Blockchain Auditing for Federated Learning on Edge Hardware

Federated learning across ten Raspberry Pi 4 devices, with every training round committed on-chain to Base mainnet (an Ethereum Layer-2) through a Solidity smart contract and archived on IPFS.

**Dataset (Mendeley Data):** [10.17632/dgmjr3ngtv.2](https://data.mendeley.com/datasets/dgmjr3ngtv/2) · **Contract:** [`0xBE3FeAC76293711C5D32426860303AfE24cdf527`](https://basescan.org/address/0xBE3FeAC76293711C5D32426860303AfE24cdf527) on Base mainnet (chain ID 8453)

---

## What this is

FLBL2 trains a 1-D Squeeze-and-Excitation ResNet for human activity recognition, distributed across ten physical Raspberry Pi 4 clients with [Flower](https://flower.ai). After each aggregation round the server writes three on-chain records (LOCAL, VOTE, GLOBAL) and pins the model and metric artefacts to IPFS via Pinata; any change to a stored artefact or to the on-chain record sequence is detectable with `verifyChain()`.

Two middleware variants are compared:

- **baseline** — synchronous IPFS uploads, per-transaction gas estimation, chain verification every round.
- **optimised** — asynchronous IPFS uploads (background thread), cached gas parameters, verification deferred to the end of the session.

The repository contains the complete raw output of **40 sessions** run on Base mainnet across two benchmarks.

| | MHEALTH | UCI-HAR |
|---|---|---|
| Sessions (10 baseline + 10 optimised) | 20 | 20 |
| Rounds (10 per session) | 200 | 200 |
| On-chain transactions | 620 | 620 |
| IPFS pins | 840 | 840 |
| Peak accuracy (baseline / optimised) | 0.986 / 0.972 | 0.922 / 0.922 |
| `verifyChain()` violations | 0 / 20 | 0 / 20 |

Totals: **40 sessions, 400 rounds, 1,240 transactions, 1,680 pins.** On-chain cost is a small fraction of a US dollar per round at the Base L2 gas prices observed during the experiment.

---

## Repository layout

```
fl_blockchain_evm/
├── client_app.py          # Flower ClientApp (train + evaluate)
├── server_app.py          # Flower ServerApp (aggregation, blockchain writes)
├── task.py / utils.py     # Flower helpers and shared utilities
├── core/
│   ├── model.py           # SE-ResNet (~860k params)
│   ├── data.py            # Dataset dispatcher (selects loader by FL_DATASET)
│   ├── data_mhealth.py    # MHEALTH loader  (12 classes, 23 ch, 256-sample windows)
│   ├── data_ucihar.py     # UCI-HAR loader  (6 classes, 9 ch, 128-sample windows)
│   ├── data_pamap2.py     # PAMAP2 loader   (12 classes, 27 ch, 512-sample windows)
│   ├── training.py        # train() / evaluate()
│   └── constants.py       # Per-dataset class labels and window sizes
├── infra/
│   ├── blockchain.py      # web3.py wrapper — baseline and optimised modes (class EVMBlockchain)
│   └── ipfs_storage.py    # Pinata HTTP pinning API
├── strategy/medical_fedavg.py   # Equal-weight FedAvg aggregation
└── dashboard/             # Live FastAPI dashboard

contracts/
├── FLBL2.sol              # Solidity 0.8.20 audit contract (OpenZeppelin v5.0.2)
└── FLBL2_abi.json         # Contract ABI

data/                      # Source datasets — download separately (not redistributed)
fl.sh                      # Orchestrator for the 10-Pi testbed
aggregate_metrics.py       # Build the round / device / eval / summary CSVs
extract_perf_timings.py    # Build the performance-timing CSVs
gather_tx_pin_map.py       # Build the transaction–pin audit map
outputs/                   # 20 raw MHEALTH session directories (committed)
outputs_ucihar/            # 20 raw UCI-HAR session directories (committed)
aggregated/                # Flat CSV tables + data dictionary (the Mendeley deposit)
pyproject.toml             # Flower config and hyperparameters
.env                       # Secrets — never commit
```

---

## Setup

### Requirements

- Python 3.11
- Flower 1.29.0, PyTorch 2.7.1, web3.py 7.x (`requirements-pi.txt` pins the client side)
- A Base mainnet wallet with a small amount of ETH (≈ 0.001 ETH per 10-round session)
- A Pinata account with a JWT token (free tier is sufficient)

```bash
git clone https://github.com/bmukhambetiyar/FLBL2.git
cd FLBL2
python -m venv .venv && source .venv/bin/activate
pip install -e .                       # coordinator / laptop
# on each Raspberry Pi 4:
pip install -r requirements-pi.txt
```

### Source datasets

The raw activity-recognition datasets are **not redistributed**; download them and place them under `data/`:

- **MHEALTH** — [UCI repository](https://archive.ics.uci.edu/dataset/319/mhealth+dataset); put the ten `mHealth_subject*.log` files under `data/MHEALTHDATASET/`. Split: subjects 1–8 across the training clients, subjects 9–10 as a fixed held-out test set (514 windows).
- **UCI-HAR** — [UCI repository](https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones); standard split, 21 training subjects across the clients and 9 test subjects (2,947 windows).

Windowing and normalisation run at load time — no manual preprocessing is needed.

### Environment variables

Create `.env` in the project root:

```env
BASE_SEPOLIA_RPC_URL=https://mainnet.base.org
PRIVATE_KEY=0x<YOUR_WALLET_PRIVATE_KEY>
CONTRACT_ADDRESS=0xBE3FeAC76293711C5D32426860303AfE24cdf527
IPFS_BACKEND=pinata
PINATA_JWT=<YOUR_PINATA_JWT_TOKEN>
```

To deploy your own contract, compile `contracts/FLBL2.sol` with Solidity 0.8.20 (OpenZeppelin v5.0.2) on Base mainnet (chain ID 8453), then set `CONTRACT_ADDRESS` and update `contracts/FLBL2_abi.json`.

---

## Reproducing the experiments

The dataset is selected by the training command (not by a flag); the variant, session count and hyperparameters are passed as environment variables. Batch size is 64 for both datasets, and every round writes three transactions to Base mainnet.

**UCI-HAR (20 sessions → `outputs_ucihar/`):** `train-ucihar` runs `N_SESSIONS` baseline + `N_SESSIONS` optimised sessions in one invocation, alternating the two variants automatically.

```bash
./fl.sh setup-ucihar                                   # one-time: sync data + deps to the Pis
N_SESSIONS=10 LOCAL_EPOCHS=3 LR=0.001 ./fl.sh train-ucihar
```

**MHEALTH (→ `outputs/`):** `train` runs a single MHEALTH session; the variant is taken from the environment. Run it ten times for each variant:

```bash
# baseline  (repeat 10×)
EXPERIMENT_VARIANT=baseline  BLOCKCHAIN_OPTIMIZED=0 FL_DATASET=mhealth LOCAL_EPOCHS=5 LR=0.002 ./fl.sh train
# optimised (repeat 10×)
EXPERIMENT_VARIANT=optimized BLOCKCHAIN_OPTIMIZED=1 FL_DATASET=mhealth LOCAL_EPOCHS=5 LR=0.002 ./fl.sh train
```

For a single local session without the Pi fleet:

```bash
FL_DATASET=ucihar flwr run .
```

Live dashboard (optional): `python -m fl_blockchain_evm.dashboard.server`, then open `http://localhost:8000`.

---

## Data aggregation

After the sessions finish, three scripts flatten the raw session directories into the deposited CSV tables under `aggregated/`. They read the raw files without modifying any value.

```bash
python aggregate_metrics.py        # all_rounds / all_devices / all_client_evals / session_summary (both datasets)
python extract_perf_timings.py     # perf_timings_*  (millisecond blockchain/IPFS timings, both datasets)
python gather_tx_pin_map.py        # tx_pin_map (transaction hash ↔ IPFS CID ↔ pin status); needs the Pinata API
```

This produces the twelve CSV files described in `aggregated/DATA_DICTIONARY.md`. The `tx_pin_map` files are written under `outputs/` and `outputs_ucihar/` and copied into `aggregated/` as `tx_pin_map_flowertrained_{mhealth,ucihar}.csv`.

**Reading `results.json`** (newline-delimited JSON, one object per round event):

```python
import json
with open("outputs/<run_folder>/results.json") as f:
    records = [json.loads(line) for line in f if line.strip()]
for r in (x for x in records if x.get("type") == "global"):
    print(r["round"], r["accuracy"], r["f1_macro"])
```

---

## Model

SE-ResNet for 1-D time series, ≈ 860k trainable parameters (859,786 for MHEALTH, 855,080 for UCI-HAR; the difference is only the first convolution's input channels).

```
Input: (B, C, L)   — C = 23 ch × 256 samples (MHEALTH) or 9 ch × 128 samples (UCI-HAR), 50 Hz
  Stage 1: Conv1d(C→32,  k=7) → BN → ReLU → MaxPool → 2× SEResBlock(32)
  Stage 2: Conv1d(32→64, k=5) → BN → ReLU → MaxPool → 2× SEResBlock(64)
  Stage 3: Conv1d(64→128,k=3) → BN → ReLU → MaxPool → 2× SEResBlock(128)
  Stage 4: Conv1d(128→256,k=3)→ BN → ReLU → MaxPool → 1× SEResBlock(256)
  GlobalAvgPool → Dropout(0.3) → Linear(256→num_classes)
```

Loss: Focal Loss (γ = 2). Optimiser: AdamW (weight decay 1e-4) with a cosine learning-rate schedule. Augmentation (training only): Mixup (α = 0.3), additive Gaussian noise, and amplitude jitter. Gzip-serialised checkpoint: 3,439,144 bytes (MHEALTH) / 3,420,320 bytes (UCI-HAR), bit-identical across rounds within a session.

---

## On-chain records and IPFS

Round 0 writes a single GLOBAL block; rounds 1–10 each write LOCAL, VOTE, and GLOBAL blocks — 31 transactions per session. The contract stores only a keccak-256 content hash and the previous-block hash for each record, forming a hash chain that `verifyChain()` re-checks end to end. The artefacts themselves (model weights, round metrics, client summaries, votes) live on IPFS; only their content identifiers are committed on-chain, so any later modification is detectable.

The two middleware variants write the same transactions and the same on-chain data; only timing differs. Per-operation latencies are in the `perf_timings_*` CSVs and in Table 2 of the data article.

---

## Citation

If you use this code or data, please cite the data article and the dataset:

```
T. Bayan, B. Mukhambetiyar, A. Boranbayev, A. Yazici. Dataset of Round-Level Federated
Learning and Layer-2 Blockchain Overhead from Ten Raspberry Pi Edge Clients. Data in Brief.

Dataset: Mendeley Data, DOI 10.17632/dgmjr3ngtv.2.
```

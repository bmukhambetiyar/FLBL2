"""plot_tx_pin_map.py — Bar chart of TX hashes vs IPFS pin outcomes per variant."""

import csv, os
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# LaTeX-paper style: use a serif font that matches Computer Modern
plt.rcParams.update({
    "font.family":      "serif",
    "font.size":        9,
    "axes.titlesize":   9,
    "axes.labelsize":   9,
    "xtick.labelsize":  9,
    "ytick.labelsize":  9,
    "legend.fontsize":  8.5,
    "figure.dpi":       150,
})

# ── Load data ─────────────────────────────────────────────────────────────────
data = defaultdict(lambda: {"tx_hashes": set(), "success": 0, "failed": 0})
with open("outputs/tx_pin_map.csv") as f:
    for row in csv.DictReader(f):
        v = row["variant"]
        data[v]["tx_hashes"].add(row["tx_hash"])
        if row["pin_status"] == "success":
            data[v]["success"] += 1
        else:
            data[v]["failed"] += 1

variants   = ["baseline", "optimized"]
labels     = ["Baseline", "Optimized"]
unique_tx  = [len(data[v]["tx_hashes"]) for v in variants]
successful = [data[v]["success"]         for v in variants]
failed     = [data[v]["failed"]          for v in variants]

# ── Plot ──────────────────────────────────────────────────────────────────────
x     = np.arange(len(labels))
width = 0.20

fig, ax = plt.subplots(figsize=(5.5, 3.4))

b1 = ax.bar(x - width,  unique_tx,  width, color="#4472C4", label="Unique TX hashes",    zorder=3)
b2 = ax.bar(x,          successful, width, color="#ED7D31", label="Successful IPFS pins", zorder=3)
b3 = ax.bar(x + width,  failed,     width, color="#A5A5A5", label="Failed pins",          zorder=3)

# Labels just above each bar
for bar in list(b1) + list(b2) + list(b3):
    h = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        h + 3,
        str(int(h)),
        ha="center", va="bottom",
        fontsize=8.5,
    )

# Axes styling to match the reference figure
ax.set_ylabel("Count")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(0, 470)
ax.yaxis.set_major_locator(ticker.MultipleLocator(200))

# Dashed horizontal gridlines, behind bars
ax.yaxis.grid(True, linestyle="--", linewidth=0.7, color="#BBBBBB", zorder=0)
ax.set_axisbelow(True)

# Light gray box around the plot area (all 4 spines, thin gray)
for spine in ax.spines.values():
    spine.set_visible(True)
    spine.set_edgecolor("#AAAAAA")
    spine.set_linewidth(0.8)

ax.tick_params(axis="both", length=0)  # no tick marks, matches reference

# Legend centred below plot, no frame, coloured square markers
ax.legend(
    loc="upper center",
    bbox_to_anchor=(0.5, -0.14),
    ncol=3,
    frameon=False,
    handlelength=1.2,
    handleheight=0.8,
    columnspacing=1.0,
)

fig.tight_layout()
os.makedirs("figures", exist_ok=True)
out = "figures/tx_pin_map_bar.png"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"Saved → {out}")

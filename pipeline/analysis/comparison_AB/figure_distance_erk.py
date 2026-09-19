"""
figure_distance_erk.py — Dve ločeni sliki razdalje potovanj, Model A vs B (Velenje),
pripravljeni za tiskan članek (2-stolpčni format, ~8cm širine, 300 dpi).

Uporablja OBSTOJEČE surove rezultate iz raw_runs/ (Modela A in B nista bila
ponovno pognana — glej INSTRUCTIONS_compare_AB.md, pravilo "ne poganjaj Modela A
na novo", in isto načelo je bilo uporabljeno za B, ker je zadnji shranjen
raw_runs/B_velenje/B_velenje_N25_4trips.parquet že v isti konfiguraciji
(N=25, 4 potovanja/vozilo, Velenje) kot ta primerjava zahteva.

Izhod:
  figures_erk/distance_distribution.png — histogram + KS test + SURS 2025 pas
  figures_erk/distance_ecdf.png         — ECDF krivulji (isti stil/barve)
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

RUN_DIR = os.path.join(os.path.dirname(__file__), "raw_runs")
OUT_DIR = os.path.join(os.path.dirname(__file__), "figures_erk")
os.makedirs(OUT_DIR, exist_ok=True)

# Ista barvna shema kot figure_velenje_1to1.py (A=modra, B=zelena)
COLOR_A = "#2166ac"
COLOR_B = "#1a9641"
DPI = 300

# Fizična velikost slike za 2-stolpčni tiskan članek (~8 cm širine)
CM = 1 / 2.54
FIG_W = 8.5 * CM
FIG_H_HIST = 6.6 * CM
FIG_H_ECDF = 6.2 * CM

SURS_LO, SURS_HI = 13.7, 16.6  # SURS 2025 realno območje povprečne razdalje na potovanje (km)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 8.5,
    "axes.titlesize": 8.5,
    "axes.labelsize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 6.8,
    "axes.linewidth": 0.7,
    "figure.dpi": DPI,
})


def load():
    a = pd.read_parquet(os.path.join(RUN_DIR, "A_N25_4trips.parquet"))
    b = pd.read_parquet(os.path.join(RUN_DIR, "B_velenje", "B_velenje_N25_4trips.parquet"))
    return a["distance_km"].dropna().values, b["distance_km"].dropna().values


def fig_distribution(da, db):
    ks_stat, ks_p = stats.ks_2samp(da, db)
    p_str = "p < 0,001" if ks_p < 0.001 else f"p = {ks_p:.3f}".replace(".", ",")

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H_HIST))

    bins = np.linspace(0, max(da.max(), db.max()) * 1.02, 22)

    ax.axvspan(SURS_LO, SURS_HI, color="#999999", alpha=0.22, zorder=0,
               label=f"SURS 2025 ({SURS_LO:.1f}–{SURS_HI:.1f} km)".replace(".", ","))

    ax.hist(da, bins=bins, density=True, color=COLOR_A, alpha=0.55,
            edgecolor=COLOR_A, linewidth=0.6, zorder=2,
            label=f"Model A (μ={da.mean():.1f} km)".replace(".", ","))
    ax.hist(db, bins=bins, density=True, color=COLOR_B, alpha=0.55,
            edgecolor=COLOR_B, linewidth=0.6, zorder=2,
            label=f"Model B (μ={db.mean():.1f} km)".replace(".", ","))

    ax.axvline(da.mean(), color=COLOR_A, linestyle="--", linewidth=1.1, zorder=3)
    ax.axvline(db.mean(), color=COLOR_B, linestyle="--", linewidth=1.1, zorder=3)

    ax.set_xlabel("Razdalja potovanja (km)")
    ax.set_ylabel("Gostota verjetnosti")
    ax.set_title(f"Porazdelitev razdalje potovanja — Velenje\nKS = {ks_stat:.3f}, {p_str}",
                 fontweight="bold")
    ax.legend(loc="upper right", frameon=True, framealpha=0.9, handlelength=1.4,
              borderpad=0.4, labelspacing=0.3)
    ax.grid(True, alpha=0.25, linewidth=0.5)
    ax.set_xlim(0, bins[-1])

    fig.tight_layout(pad=0.6)
    path = os.path.join(OUT_DIR, "distance_distribution.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path}  (KS={ks_stat:.4f}, p={ks_p:.4g})")
    return ks_stat, ks_p


def fig_ecdf(da, db):
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H_ECDF))

    for d, color, label in [(da, COLOR_A, "Model A"), (db, COLOR_B, "Model B")]:
        xs = np.sort(d)
        ys = np.arange(1, len(xs) + 1) / len(xs)
        ax.step(xs, ys, color=color, linewidth=1.6, alpha=0.9, where="post", label=label)

    ax.set_xlabel("Razdalja potovanja (km)")
    ax.set_ylabel("Kumulativna verjetnost")
    ax.set_title("ECDF razdalje potovanja — Velenje", fontweight="bold")
    ax.legend(loc="lower right", frameon=True, framealpha=0.9, handlelength=1.4,
              borderpad=0.4, labelspacing=0.3)
    ax.grid(True, alpha=0.25, linewidth=0.5)
    ax.set_xlim(0, max(da.max(), db.max()) * 1.02)
    ax.set_ylim(0, 1.02)

    fig.tight_layout(pad=0.6)
    path = os.path.join(OUT_DIR, "distance_ecdf.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path}")


def run():
    da, db = load()
    print(f"Model A: n={len(da)}, mean={da.mean():.2f} km, median={np.median(da):.2f} km")
    print(f"Model B: n={len(db)}, mean={db.mean():.2f} km, median={np.median(db):.2f} km")
    fig_distribution(da, db)
    fig_ecdf(da, db)


if __name__ == "__main__":
    run()

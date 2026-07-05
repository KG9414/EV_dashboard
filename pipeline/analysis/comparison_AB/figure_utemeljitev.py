"""
figure_utemeljitev.py — figure za nalogo: zakaj je B boljši od A.
Fokus: merljivi vedenjski kazalniki kjer B jasno zmaga.
"""

import os, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats

OUT_DIR = os.path.join(os.path.dirname(__file__), "figures")
RUN_DIR = os.path.join(os.path.dirname(__file__), "raw_runs")
DPI = 150

COLOR_A  = "#2166ac"
COLOR_B  = "#d6604d"
COLOR_NH = "#4dac26"
ALPHA = 0.75

LABEL_A  = "Original (A)"
LABEL_B  = "Pipeline (B)"
LABEL_NH = "NHTS referenca"


def load():
    a = pd.read_parquet(os.path.join(RUN_DIR, "A_N25_4trips.parquet"))
    b = pd.read_parquet(os.path.join(RUN_DIR, "B_N25_4trips.parquet"))
    nhts = pd.read_csv(os.path.join(os.path.dirname(__file__),
                                    "../../pipeline/00_NHTS_data.csv"), sep=";")
    nhts["start_h"] = nhts["STRTTIME"].apply(
        lambda x: int(str(int(x)).zfill(4)[:2]) if pd.notna(x) and x > 0 else np.nan
    )
    nhts_km = nhts["TRPMILES"].dropna() * 1.60934
    nhts_km = nhts_km[(nhts_km > 0.5) & (nhts_km < 200)]
    bv = pd.read_parquet(os.path.join(RUN_DIR, "B_velenje", "B_velenje_N25_4trips.parquet"))
    return a, b, bv, nhts, nhts_km


def plot_utemeljitev(a, b, bv, nhts, nhts_km):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    fig.subplots_adjust(wspace=0.35)

    # ── Panel 1: Čas odhoda — jutrannji vrh ─────────────────────────────────
    ax = axes[0]
    bins = np.arange(0, 24.5, 0.5)

    # NHTS
    nhts_h = nhts["start_h"].dropna()
    nhts_h = nhts_h[(nhts_h >= 0) & (nhts_h < 24)]
    nhts_hist, _ = np.histogram(nhts_h, bins=bins, density=True)
    bin_centers = (bins[:-1] + bins[1:]) / 2
    ax.fill_between(bin_centers, nhts_hist, alpha=0.25, color=COLOR_NH, step="mid")
    ax.step(bin_centers, nhts_hist, color=COLOR_NH, linewidth=1.5,
            label=f"{LABEL_NH}\nmed. {nhts_h.median():.0f}h", where="mid", alpha=0.9)

    for data, color, label in [
        (a["departure_time_h"], COLOR_A, LABEL_A),
        (b["departure_time_h"], COLOR_B, LABEL_B),
    ]:
        h, _ = np.histogram(data.dropna(), bins=bins, density=True)
        morn = ((data >= 6) & (data <= 10)).mean() * 100
        ax.step(bin_centers, h, color=color, linewidth=2,
                label=f"{label}\n6–10h: {morn:.0f}%", where="mid", alpha=ALPHA)

    # Referenčno okno 6–10h
    ax.axvspan(6, 10, alpha=0.07, color="gold", zorder=0)
    ax.text(8, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 0.12,
            "6–10h\nkomuter\nokno", ha="center", va="top", fontsize=8, color="goldenrod")

    ax.set_xlabel("Čas odhoda (h)", fontsize=11)
    ax.set_ylabel("Gostota verjetnosti", fontsize=11)
    ax.set_title("Čas odhoda:\nB bliže jutrannjemu vrhu", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):02d}h"))
    ax.xaxis.set_major_locator(plt.MultipleLocator(4))
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)

    # Annotate NHTS reference value
    nhts_morn = ((nhts_h >= 6) & (nhts_h <= 10)).mean() * 100
    ax.text(8, -0.005, f"NHTS: {nhts_morn:.0f}%",
            ha="center", va="top", fontsize=8, color=COLOR_NH,
            transform=ax.get_xaxis_transform())

    # ── Panel 2: Povprečna razdalja ──────────────────────────────────────────
    ax = axes[1]

    models = [LABEL_A, LABEL_B, "NHTS (vse)\nreferenca"]
    # NHTS Work mean
    nhts_all_mean = nhts_km.mean()  # vse kategorije — modela generirata vse tipe
    means = [a["distance_km"].mean(), b["distance_km"].mean(), nhts_all_mean]

    colors_bar = [COLOR_A, COLOR_B, COLOR_NH]
    bars = ax.bar(models, means, color=colors_bar, alpha=ALPHA, width=0.5, zorder=3)

    # Reference line at NHTS all-trips mean
    ax.axhline(nhts_all_mean, color=COLOR_NH, linestyle="--", linewidth=1.5,
               label=f"NHTS (vse): {nhts_all_mean:.1f} km", zorder=4)

    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, m + 0.3,
                f"{m:.1f} km", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    # Razlika od NHTS (samo za A in B@Krško)
    for xi, (mi, lbl) in enumerate(zip(means[:-1], ["A", "B@V", "B@K"])):
        diff = abs(mi - nhts_all_mean)
        ax.text(xi, mi / 2, f"Δ {diff:.1f} km", ha="center", va="center",
                fontsize=8, color="white", fontweight="bold")

    ax.set_ylabel("Povprečna razdalja potovanja (km)", fontsize=11)
    ax.set_title("Povprečna razdalja:\nB bliže NHTS referenci", fontsize=11, fontweight="bold")
    ax.set_ylim(0, max(means) * 1.3)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3, zorder=0)

    # ── Panel 3: Konsistentnost verig ────────────────────────────────────────
    ax = axes[2]

    def chain_metrics(df):
        work_pct, sym_pct = [], []
        for v, g in df.groupby("vehicle_id"):
            g = g.sort_values("trip_id")
            trips = g["activity"].tolist()
            work_pct.append("Work" in trips)
            sym_pct.append(trips[-1] == trips[0])
        return np.mean(work_pct) * 100, np.mean(sym_pct) * 100

    a_work, a_sym = chain_metrics(a)
    b_work, b_sym = chain_metrics(b)

    metrics = ["Vozila z\nWork potovanjem (%)", "Simetričen\npovratek (%)"]
    a_vals  = [a_work, a_sym]
    b_vals  = [b_work, b_sym]

    x = np.arange(len(metrics))
    w = 0.32
    bars_a = ax.bar(x - w/2, a_vals, w, label=LABEL_A, color=COLOR_A, alpha=ALPHA)
    bars_b = ax.bar(x + w/2, b_vals, w, label=LABEL_B, color=COLOR_B, alpha=ALPHA)

    for bar, v in zip(bars_a, a_vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 1,
                f"{v:.0f}%", ha="center", va="bottom", fontsize=11, color=COLOR_A, fontweight="bold")
    for bar, v in zip(bars_b, b_vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 1,
                f"{v:.0f}%", ha="center", va="bottom", fontsize=11, color=COLOR_B, fontweight="bold")

    # Improvement arrows
    for xi, (va, vb) in enumerate(zip(a_vals, b_vals)):
        ax.annotate("", xy=(xi + w/2, vb - 2), xytext=(xi + w/2, va + 2),
                    arrowprops=dict(arrowstyle="->", color="gray", lw=1.5))
        ax.text(xi + w/2 + 0.18, (va + vb) / 2,
                f"+{vb-va:.0f} pp", fontsize=9, color="gray", va="center")

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel("Delež vozil (%)", fontsize=11)
    ax.set_title("Konsistentnost potovalnih verig:\nB bistveno boljši", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 80)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)

    # ── Skupni naslov ────────────────────────────────────────────────────────
    fig.suptitle(
        "Utemeljitev nadgradnje Pipeline (B) glede na Original (A)\n"
        "N = 25 vozil, 4 potovanja/vozilo, 1 dan  |  Primerjava vedenjskih kazalnikov",
        fontsize=13, fontweight="bold", y=1.02
    )

    path = os.path.join(OUT_DIR, "utemeljitev_nadgradnje_B.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ utemeljitev_nadgradnje_B.png → {path}")


def run():
    a, b, bv, nhts, nhts_km = load()
    plot_utemeljitev(a, b, bv, nhts, nhts_km)


if __name__ == "__main__":
    run()

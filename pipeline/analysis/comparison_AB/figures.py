"""
figures.py — vse primerjalne grafike A vs B, oznake v slovenščini.
Shranjuje PNG (≥150 dpi) v figures/.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from scipy import stats

OUT_DIR  = os.path.join(os.path.dirname(__file__), "figures")
RUN_DIR  = os.path.join(os.path.dirname(__file__), "raw_runs")
MET_DIR  = os.path.join(os.path.dirname(__file__), "metrics")
os.makedirs(OUT_DIR, exist_ok=True)

DPI = 150

# ── style ────────────────────────────────────────────────────────────────────
COLOR_A  = "#2166ac"   # modra — Original
COLOR_B  = "#d6604d"   # rdeča — Pipeline
COLOR_NH = "#4dac26"   # zelena — NHTS referenca
ALPHA    = 0.7

LABEL_A  = "Original (Velenje)"
LABEL_B  = "Pipeline (Krško)"
LABEL_NH = "NHTS (referenca)"

def _save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {name}")


# ── data ─────────────────────────────────────────────────────────────────────
def load():
    prim  = pd.read_parquet(os.path.join(RUN_DIR, "combined_primary.parquet"))
    a_sec = pd.read_parquet(os.path.join(RUN_DIR, "A_N100_4trips_step1only.parquet"))
    b_sec = pd.read_parquet(os.path.join(RUN_DIR, "B_N100_2trips.parquet"))
    nhts  = pd.read_csv(os.path.join(os.path.dirname(__file__), "../../pipeline/00_NHTS_data.csv"))
    return prim, a_sec, b_sec, nhts


# ── 1. ECDF overlays ─────────────────────────────────────────────────────────
def ecdf(x):
    x = np.sort(np.asarray(x, dtype=float))
    y = np.arange(1, len(x) + 1) / len(x)
    return x, y


def plot_ecdf_trio(prim, nhts):
    """Three ECDF panels: departure time, duration, distance."""
    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # -- Čas odhoda
    ax = axes[0]
    for data, color, label in [(A["departure_time_h"], COLOR_A, LABEL_A),
                                (B["departure_time_h"], COLOR_B, LABEL_B)]:
        x, y = ecdf(data.dropna())
        ax.step(x, y, color=color, label=label, linewidth=2, alpha=ALPHA)
    ax.set_xlabel("Čas odhoda (h)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title("ECDF — čas odhoda", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):02d}:00"))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # -- Trajanje
    ax = axes[1]
    for data, color, label in [(A["duration_min"], COLOR_A, LABEL_A),
                                (B["duration_min"], COLOR_B, LABEL_B)]:
        x, y = ecdf(data.dropna())
        ax.step(x, y, color=color, label=label, linewidth=2, alpha=ALPHA)
    ax.set_xlabel("Trajanje potovanja (min)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title("ECDF — trajanje", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # -- Razdalja
    ax = axes[2]
    for data, color, label in [(A["distance_km"], COLOR_A, LABEL_A),
                                (B["distance_km"], COLOR_B, LABEL_B)]:
        x, y = ecdf(data.dropna())
        ax.step(x, y, color=color, label=label, linewidth=2, alpha=ALPHA)
    ax.set_xlabel("Razdalja (km)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title("ECDF — razdalja", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.suptitle("Porazdelitve: Original vs Pipeline  (N=25, 4 potovanja/vozilo)",
                 fontsize=13, fontweight="bold", y=1.02)
    _save(fig, "ecdf_cas_trajanje_razdalja.png")


# ── 2. KDE / Histogram overlays ──────────────────────────────────────────────
def plot_kde_trio(prim):
    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    specs = [
        ("departure_time_h", "Čas odhoda (h)",       "Gostota", 0, 24),
        ("duration_min",     "Trajanje (min)",        "Gostota", 0, 120),
        ("distance_km",      "Razdalja (km)",         "Gostota", 0, 90),
    ]

    for ax, (col, xlabel, ylabel, xmin, xmax) in zip(axes, specs):
        for data, color, label in [(A[col].dropna(), COLOR_A, LABEL_A),
                                    (B[col].dropna(), COLOR_B, LABEL_B)]:
            ax.hist(data, bins=20, density=True, alpha=0.35, color=color)
            kde = stats.gaussian_kde(data)
            xs  = np.linspace(max(xmin, data.min()), min(xmax, data.max()), 300)
            ax.plot(xs, kde(xs), color=color, linewidth=2, label=label)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xlim(xmin, xmax)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    axes[0].set_title("Gostota — čas odhoda",  fontsize=12, fontweight="bold")
    axes[1].set_title("Gostota — trajanje",     fontsize=12, fontweight="bold")
    axes[2].set_title("Gostota — razdalja",     fontsize=12, fontweight="bold")

    fig.suptitle("Gostota porazdelitev: Original vs Pipeline  (N=25, 4 pot./voz.)",
                 fontsize=13, fontweight="bold", y=1.02)
    _save(fig, "kde_cas_trajanje_razdalja.png")


# ── 3. Activity shares ───────────────────────────────────────────────────────
def plot_activity_shares(prim, a_sec, b_sec):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, (a_data, b_data, title, note) in zip(axes, [
        (prim[prim["model"]=="A"]["activity"],
         prim[prim["model"]=="B"]["activity"],
         "N = 25 vozil, 4 potovanja",
         ""),
        (a_sec["activity"],
         b_sec["activity"],
         "N = 100 vozil",
         "(A: 4 pot./voz.; B: 2 pot./voz.)"),
    ]):
        all_acts = sorted(set(a_data) | set(b_data))
        a_pct = [(a_data == act).mean() * 100 for act in all_acts]
        b_pct = [(b_data == act).mean() * 100 for act in all_acts]

        x = np.arange(len(all_acts))
        w = 0.35
        bars_a = ax.bar(x - w/2, a_pct, w, label=LABEL_A, color=COLOR_A, alpha=ALPHA)
        bars_b = ax.bar(x + w/2, b_pct, w, label=LABEL_B, color=COLOR_B, alpha=ALPHA)

        ax.set_xticks(x)
        ax.set_xticklabels(all_acts, rotation=30, ha="right", fontsize=10)
        ax.set_ylabel("Delež potovanj (%)", fontsize=11)
        ax.set_title(f"Tipi aktivnosti — {title}\n{note}", fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, axis="y", alpha=0.3)

        for bar in bars_a:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.0f}%",
                        ha="center", va="bottom", fontsize=7.5, color=COLOR_A)
        for bar in bars_b:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.0f}%",
                        ha="center", va="bottom", fontsize=7.5, color=COLOR_B)

    fig.suptitle("Deleži tipov aktivnosti: Original vs Pipeline",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    _save(fig, "deleži_aktivnosti.png")


# ── 4. Trips per vehicle ─────────────────────────────────────────────────────
def plot_trips_per_vehicle(prim):
    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]

    a_counts = A.groupby("vehicle_id")["trip_id"].count()
    b_counts = B.groupby("vehicle_id")["trip_id"].count()

    fig, ax = plt.subplots(figsize=(6, 5))
    labels = [LABEL_A, LABEL_B]
    means  = [a_counts.mean(), b_counts.mean()]
    colors = [COLOR_A, COLOR_B]

    bars = ax.bar(labels, means, color=colors, alpha=ALPHA, width=0.5)
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, m + 0.05, f"{m:.2f}",
                ha="center", va="bottom", fontsize=12, fontweight="bold")

    ax.set_ylabel("Povprečno število potovanj / vozilo / dan", fontsize=11)
    ax.set_title("Potovanja na vozilo na dan", fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(means) * 1.25)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, "poti_na_vozilo.png")


# ── 5. Departure time histogram (fine-grained) ───────────────────────────────
def plot_departure_hist(prim):
    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]

    fig, ax = plt.subplots(figsize=(12, 5))
    bins = np.arange(0, 24.25, 0.25)  # 15-min bins
    ax.hist(A["departure_time_h"], bins=bins, alpha=0.55, color=COLOR_A,
            label=LABEL_A, density=True)
    ax.hist(B["departure_time_h"], bins=bins, alpha=0.55, color=COLOR_B,
            label=LABEL_B, density=True)

    ax.set_xlabel("Čas odhoda", fontsize=11)
    ax.set_ylabel("Gostota", fontsize=11)
    ax.set_title("Porazdelitev časov odhodov (15-min razredi)", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):02d}:00"))
    ax.xaxis.set_major_locator(plt.MultipleLocator(2))
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    _save(fig, "ecdf_cas_odhoda.png")


# ── 6. Duration + distance Q-Q plots ────────────────────────────────────────
def plot_qq(prim):
    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, col, label in [
        (axes[0], "duration_min", "Trajanje (min)"),
        (axes[1], "distance_km",  "Razdalja (km)"),
    ]:
        a_q = np.quantile(A[col].dropna(), np.linspace(0, 1, 50))
        b_q = np.quantile(B[col].dropna(), np.linspace(0, 1, 50))
        mn, mx = min(a_q.min(), b_q.min()), max(a_q.max(), b_q.max())

        ax.scatter(a_q, b_q, color=COLOR_B, alpha=0.8, s=40, zorder=3)
        ax.plot([mn, mx], [mn, mx], color="gray", linewidth=1.5,
                linestyle="--", label="y = x (enakost)")
        ax.set_xlabel(f"Original — {label}", fontsize=11)
        ax.set_ylabel(f"Pipeline — {label}", fontsize=11)
        ax.set_title(f"Q–Q: {label}", fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    fig.suptitle("Q–Q primerjava: Original vs Pipeline  (N=25, 4 pot./voz.)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    _save(fig, "qq_trajanje_razdalja.png")


# ── 7. Spatial maps ──────────────────────────────────────────────────────────
def plot_spatial(prim):
    A = prim[(prim["model"] == "A") & prim["end_lat"].notna()]
    B = prim[(prim["model"] == "B") & prim["end_lat"].notna()]

    for df, name, city, color, center in [
        (A, "prostorska_A_velenje.png", "Velenje", COLOR_A, (46.36, 15.12)),
        (B, "prostorska_B_krsko.png",   "Krško",   COLOR_B, (45.96, 15.49)),
    ]:
        fig, ax = plt.subplots(figsize=(8, 7))

        # Hex density map of end destinations
        hb = ax.hexbin(df["end_lon"], df["end_lat"], gridsize=12,
                       cmap="Blues" if color == COLOR_A else "Reds",
                       mincnt=1, alpha=0.85)
        fig.colorbar(hb, ax=ax, label="Število destinacij v celici")

        # Home locations (start of trip 1 = home)
        homes = df[df["trip_id"] == 1]
        ax.scatter(homes["start_lon"], homes["start_lat"],
                   color="black", s=40, zorder=5, label="Domovi", marker="^", alpha=0.7)

        # City center marker
        ax.scatter(center[1], center[0], color="gold", s=150, zorder=6,
                   marker="*", edgecolors="black", linewidths=0.5, label="Središče mesta")

        ax.set_xlabel("Geografska dolžina", fontsize=11)
        ax.set_ylabel("Geografska širina", fontsize=11)
        ax.set_title(
            f"Prostorska porazdelitev destinacij\nModel {'A — Original' if 'A' in name else 'B — Pipeline'}  |  {city}",
            fontsize=12, fontweight="bold"
        )
        ax.legend(fontsize=9, loc="lower right")
        ax.grid(True, alpha=0.3)

        note = ("Opomba: A je bil zagnan za Velenje, B za Krško.\n"
                "Prostorski vzorci niso neposredno primerljivi med seboj.")
        ax.text(0.01, 0.01, note, transform=ax.transAxes, fontsize=8,
                color="gray", va="bottom", style="italic")

        _save(fig, name)


# ── 8. Summary multi-panel ───────────────────────────────────────────────────
def plot_summary(prim):
    """Small-multiples summary panel: ECDF for 3 quantities + activity bar."""
    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]
    all_acts = sorted(set(A["activity"]) | set(B["activity"]))

    fig = plt.figure(figsize=(16, 10))
    gs  = GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    # Top row: ECDFs
    for i, (col, xlabel) in enumerate([
        ("departure_time_h", "Čas odhoda (h)"),
        ("duration_min",     "Trajanje (min)"),
        ("distance_km",      "Razdalja (km)"),
    ]):
        ax = fig.add_subplot(gs[0, i])
        for data, color, label in [(A[col].dropna(), COLOR_A, LABEL_A),
                                    (B[col].dropna(), COLOR_B, LABEL_B)]:
            x, y = ecdf(data)
            ax.step(x, y, color=color, label=label, linewidth=1.8, alpha=ALPHA)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel("F(x)", fontsize=10)
        ax.set_title(f"ECDF — {xlabel}", fontsize=10, fontweight="bold")
        if i == 0:
            ax.set_xlim(0, 24)
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):02d}h"))
        ax.legend(fontsize=7.5)
        ax.grid(True, alpha=0.3)

    # Bottom row: activity bar (spans 2 cols) + chain metrics
    ax_act = fig.add_subplot(gs[1, :2])
    x = np.arange(len(all_acts))
    w = 0.35
    a_pct = [(A["activity"] == act).mean() * 100 for act in all_acts]
    b_pct = [(B["activity"] == act).mean() * 100 for act in all_acts]
    ax_act.bar(x - w/2, a_pct, w, label=LABEL_A, color=COLOR_A, alpha=ALPHA)
    ax_act.bar(x + w/2, b_pct, w, label=LABEL_B, color=COLOR_B, alpha=ALPHA)
    ax_act.set_xticks(x)
    ax_act.set_xticklabels(all_acts, rotation=25, ha="right", fontsize=9)
    ax_act.set_ylabel("Delež (%)", fontsize=10)
    ax_act.set_title("Tipi aktivnosti", fontsize=10, fontweight="bold")
    ax_act.legend(fontsize=8)
    ax_act.grid(True, axis="y", alpha=0.3)

    # Bottom-right: key metrics text box
    ax_txt = fig.add_subplot(gs[1, 2])
    ax_txt.axis("off")
    met = pd.read_csv(os.path.join(MET_DIR, "01_distribucijske_metrike.csv"))
    chain = pd.read_csv(os.path.join(MET_DIR, "04_veljavnost_verig.csv"))
    lines = ["Ključne metrike (N=25, 4 pot.)\n"]
    for _, row in met.iterrows():
        lines.append(f"{row['metric'][:20]}:\n"
                     f"  KS={row['KS_stat']:.3f}  W={row['Wasserstein']:.2f}\n")
    lines.append("\nVeljavnost verig:")
    for _, row in chain.iterrows():
        lbl = "A" if "A" in row["model"] else "B"
        lines.append(f"  {lbl}: Work {row['ima_work_%']:.0f}%,"
                     f" simetr. {row['simetricen_povratek_%']:.0f}%")
    ax_txt.text(0.05, 0.95, "\n".join(lines), transform=ax_txt.transAxes,
                fontsize=9, va="top", family="monospace",
                bbox=dict(boxstyle="round", facecolor="#f0f0f0", alpha=0.7))

    fig.suptitle("Povzetek primerjave: Original vs Pipeline",
                 fontsize=14, fontweight="bold")
    _save(fig, "povzetek_porazdelitve.png")


# ── main ─────────────────────────────────────────────────────────────────────
def run():
    prim, a_sec, b_sec, nhts = load()

    print("Generiranje grafik...")
    plot_ecdf_trio(prim, nhts)
    plot_kde_trio(prim)
    plot_activity_shares(prim, a_sec, b_sec)
    plot_trips_per_vehicle(prim)
    plot_departure_hist(prim)
    plot_qq(prim)
    plot_spatial(prim)
    plot_summary(prim)
    print(f"\nVse grafike shranjene v: {OUT_DIR}")


if __name__ == "__main__":
    run()

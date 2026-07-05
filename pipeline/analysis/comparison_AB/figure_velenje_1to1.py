"""
figure_velenje_1to1.py — 1:1 primerjava A (isochrone) vs B (gravity) na ISTEM mestu (Velenje).

Isti domovi, isti parametri potovanj (N=25, 4t, 1 dan).
Edina spremenljivka: metoda izbire destinacije.

Grafike:
  1. velenje_1to1_razdalje.png     — ECDF + KDE + boxplot razdalj (3 paneli)
  2. velenje_1to1_aktivnosti.png   — stolpčni diagram deležev aktivnosti
  3. velenje_1to1_prostorsko.png   — hex density destinacij + scatter overlay
  4. velenje_1to1_ring_limit.png   — polmer ringa vs A dejanske razdalje (diagnostika)
  5. velenje_1to1_povzetek.png     — small-multiples povzetek vseh kazalnikov
"""

import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../pipeline"))
from Functions_step_2 import haversine

A_ROOT  = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/OneDrive_1_2-25-2026"
RUN_DIR = os.path.join(os.path.dirname(__file__), "raw_runs")
MET_DIR = os.path.join(os.path.dirname(__file__), "metrics")
OUT_DIR = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(MET_DIR, exist_ok=True)

COLOR_A  = "#2166ac"   # modra — A isochrone
COLOR_BV = "#1a9641"   # zelena — B gravity @ Velenje
ALPHA    = 0.75
DPI      = 150

LABEL_A  = "A — Isochrone (ORS)\nVelenje"
LABEL_BV = "B — Gravity (Haversine)\nVelenje"


# ── naloži podatke ────────────────────────────────────────────────────────────

def load():
    a = pd.read_parquet(os.path.join(RUN_DIR, "A_N25_4trips.parquet"))
    bv = pd.read_parquet(os.path.join(RUN_DIR, "B_velenje", "B_velenje_N25_4trips.parquet"))
    homes = gpd.read_file(
        os.path.join(A_ROOT, "02_Trips", "02_Trips_25_EVs_4_trips_1_days_ROS.shp")
    )
    step3 = pd.read_excel(
        os.path.join(A_ROOT, "03_Vehicle_parameters",
                     "03_Vehicle_trip_parameters_25_EVs_4_trips_1_days.xlsx")
    )
    return a, bv, homes, step3


# ── 1. Razdalje: ECDF + KDE + boxplot ────────────────────────────────────────

def fig_razdalje(a, bv):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    da = a["distance_km"].dropna().values
    db = bv["distance_km"].dropna().values

    ks_stat, ks_p = stats.ks_2samp(da, db)
    wass = stats.wasserstein_distance(da, db)

    # ECDF
    ax = axes[0]
    for d, color, label in [(da, COLOR_A, LABEL_A), (db, COLOR_BV, LABEL_BV)]:
        xs = np.sort(d)
        ys = np.arange(1, len(xs)+1) / len(xs)
        ax.step(xs, ys, color=color, linewidth=2.2, label=f"{label}\nmed={np.median(d):.1f}km",
                alpha=ALPHA, where="post")
    ax.set_xlabel("Razdalja potovanja (km)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title(f"ECDF razdalj\nKS={ks_stat:.3f}, p={ks_p:.3f}", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # KDE
    ax = axes[1]
    for d, color, label in [(da, COLOR_A, LABEL_A), (db, COLOR_BV, LABEL_BV)]:
        kde = stats.gaussian_kde(d, bw_method=0.4)
        xs = np.linspace(0, max(da.max(), db.max()) * 1.05, 300)
        ax.fill_between(xs, kde(xs), alpha=0.2, color=color)
        ax.plot(xs, kde(xs), color=color, linewidth=2, label=label, alpha=ALPHA)
        ax.axvline(np.mean(d), color=color, linestyle="--", linewidth=1.2, alpha=0.8)
    ax.set_xlabel("Razdalja potovanja (km)", fontsize=11)
    ax.set_ylabel("Gostota verjetnosti", fontsize=11)
    ax.set_title(f"KDE razdalj\nWasserstein = {wass:.2f} km", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Boxplot
    ax = axes[2]
    bp = ax.boxplot([da, db], patch_artist=True, widths=0.5,
                    tick_labels=["A\nIsochrone", "B\nGravity"])
    for patch, color in zip(bp["boxes"], [COLOR_A, COLOR_BV]):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    for med in bp["medians"]:
        med.set_color("white")
        med.set_linewidth(2)
    for xi, (d, color) in enumerate([(da, COLOR_A), (db, COLOR_BV)], 1):
        ax.text(xi, np.mean(d) + 0.5, f"μ={np.mean(d):.1f}", ha="center",
                fontsize=9, color=color, fontweight="bold")
    ax.set_ylabel("Razdalja (km)", fontsize=11)
    ax.set_title("Porazdelitev razdalj\n(mediana + kvartili)", fontsize=11, fontweight="bold")
    ax.grid(True, axis="y", alpha=0.3)

    fig.suptitle(
        "Primerjava razdalj potovanj: A (Isochrone) vs B (Gravity)  |  ISTI domovi, Velenje, N=25, 4t",
        fontsize=13, fontweight="bold"
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "velenje_1to1_razdalje.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ velenje_1to1_razdalje.png")

    return {"KS_stat": round(ks_stat,4), "KS_p": round(ks_p,4),
            "Wasserstein_km": round(wass,2),
            "A_mean_km": round(da.mean(),2), "A_median_km": round(np.median(da),2),
            "BV_mean_km": round(db.mean(),2), "BV_median_km": round(np.median(db),2)}


# ── 2. Deleži aktivnosti ──────────────────────────────────────────────────────

def fig_aktivnosti(a, bv):
    acts = sorted(set(a["activity"]) | set(bv["activity"]))
    a_pct  = [(a["activity"] == act).mean()*100 for act in acts]
    bv_pct = [(bv["activity"] == act).mean()*100 for act in acts]

    x = np.arange(len(acts))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars_a  = ax.bar(x - w/2, a_pct,  w, label=LABEL_A,  color=COLOR_A,  alpha=ALPHA)
    bars_bv = ax.bar(x + w/2, bv_pct, w, label=LABEL_BV, color=COLOR_BV, alpha=ALPHA)

    for bar, v in zip(bars_a, a_pct):
        if v > 1:
            ax.text(bar.get_x() + bar.get_width()/2, v + 0.3,
                    f"{v:.0f}%", ha="center", va="bottom", fontsize=9, color=COLOR_A)
    for bar, v in zip(bars_bv, bv_pct):
        if v > 1:
            ax.text(bar.get_x() + bar.get_width()/2, v + 0.3,
                    f"{v:.0f}%", ha="center", va="bottom", fontsize=9, color=COLOR_BV)

    ax.set_xticks(x)
    ax.set_xticklabels(acts, fontsize=11)
    ax.set_ylabel("Delež potovanj (%)", fontsize=11)
    ax.set_title(
        "Deleži tipov aktivnosti: A vs B  |  Velenje, N=25, 4t\n"
        "(Isti parametri potovanj — razlika kaže vpliv metode destinacij)",
        fontsize=12, fontweight="bold"
    )
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "velenje_1to1_aktivnosti.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ velenje_1to1_aktivnosti.png")


# ── 3. Prostorska porazdelitev destinacij ─────────────────────────────────────

def fig_prostorsko(a, bv, homes):
    fig, axes = plt.subplots(1, 3, figsize=(18, 7))

    panels = [
        (axes[0], a,   COLOR_A,  "Blues",  LABEL_A),
        (axes[1], bv,  COLOR_BV, "Greens", LABEL_BV),
    ]

    all_lons = list(a["end_lon"].dropna()) + list(bv["end_lon"].dropna())
    all_lats = list(a["end_lat"].dropna()) + list(bv["end_lat"].dropna())
    lon_lo, lon_hi = min(all_lons) - 0.05, max(all_lons) + 0.05
    lat_lo, lat_hi = min(all_lats) - 0.03, max(all_lats) + 0.03

    for ax, df, color, cmap, title in panels:
        lat_ok = df["end_lat"].dropna()
        lon_ok = df["end_lon"].dropna()
        hb = ax.hexbin(lon_ok, lat_ok, gridsize=12, mincnt=1, cmap=cmap, alpha=0.85,
                       extent=(lon_lo, lon_hi, lat_lo, lat_hi))
        fig.colorbar(hb, ax=ax, label="N destinacij")
        ax.scatter(homes.geometry.x, homes.geometry.y,
                   color="black", s=40, zorder=5, marker="^", label="Domovi", alpha=0.85)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel("Geografska dolžina")
        ax.set_ylabel("Geografska širina")
        ax.set_xlim(lon_lo, lon_hi)
        ax.set_ylim(lat_lo, lat_hi)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.25)

    # Overlay panel
    ax = axes[2]
    ax.scatter(a["end_lon"], a["end_lat"], color=COLOR_A, alpha=0.55, s=30,
               label=f"A — Isochrone ({len(a)})", zorder=3)
    ax.scatter(bv["end_lon"], bv["end_lat"], color=COLOR_BV, alpha=0.55, s=30,
               marker="s", label=f"B — Gravity ({len(bv)})", zorder=4)
    ax.scatter(homes.geometry.x, homes.geometry.y,
               color="black", s=45, zorder=6, marker="^", label="Domovi")
    ax.set_title("Prekrivanje obeh metod\nVelenje", fontsize=11, fontweight="bold")
    ax.set_xlabel("Geografska dolžina")
    ax.set_xlim(lon_lo, lon_hi)
    ax.set_ylim(lat_lo, lat_hi)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.25)

    fig.suptitle(
        "Prostorska porazdelitev destinacij: A (Isochrone) vs B (Gravity)  |  Velenje",
        fontsize=13, fontweight="bold"
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "velenje_1to1_prostorsko.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ velenje_1to1_prostorsko.png")


# ── 4. Ring limit diagnostika ─────────────────────────────────────────────────

def fig_ring_limit(a, step3):
    dur = step3["Actual duration"].dropna().values
    radii = dur * 30 / 60   # polmer ringa pri 30 km/h
    dist_a = step3["Actual distance"].dropna().values

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    # Panel 1: polmer ringa vs A dejanska razdalja (scatter)
    ax = axes[0]
    n = min(len(radii), len(dist_a))
    ax.scatter(radii[:n], dist_a[:n], color=COLOR_A, alpha=0.6, s=40, label="Potovanje")
    lim = max(radii.max(), dist_a.max()) * 1.05
    ax.plot([0, lim], [0, lim], "k--", linewidth=1, label="Ring = A razdalja")
    ax.fill_between([0, lim], [0, lim], [0, 0], alpha=0.07, color="orange",
                    label="A znotraj ringa")
    ax.fill_between([0, lim], [lim, lim], [0, lim], alpha=0.07, color="red",
                    label="A IZVEN ringa")
    pct_out = (dist_a[:n] > radii[:n]).mean() * 100
    ax.text(0.97, 0.97, f"{pct_out:.0f}% A potovanj\nizven B-ringa",
            transform=ax.transAxes, ha="right", va="top", fontsize=11,
            color="darkred", fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="darkred", alpha=0.8, boxstyle="round"))
    ax.set_xlabel("Polmer B-ringa (km)  [trajanje × 30 km/h / 60]", fontsize=11)
    ax.set_ylabel("A dejanska razdalja (km)", fontsize=11)
    ax.set_title("Haversine ring limit:\nkoliko A potovanj B ne bi dosegel?", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Panel 2: ECDF polmerov ringa vs A razdalj
    ax = axes[1]
    for d, color, label in [
        (np.sort(radii), "#e6ab02", "B polmer ringa (km)"),
        (np.sort(dist_a), COLOR_A, "A dejanska razdalja (km)"),
    ]:
        ys = np.arange(1, len(d)+1) / len(d)
        ax.step(d, ys, color=color, linewidth=2.2, label=label, alpha=ALPHA, where="post")
    ax.set_xlabel("Razdalja (km)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title("ECDF: B ring vs A razdalje\n(kjer se krivulji razideta → ring premajhen)",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Diagnostika: Haversine ring (B) vs ORS isochrone (A)  |  Velenje",
        fontsize=13, fontweight="bold"
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "velenje_1to1_ring_limit.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ velenje_1to1_ring_limit.png")


# ── 5. Povzetek — small multiples ─────────────────────────────────────────────

def fig_povzetek(a, bv, step3, dist_metrics):
    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 4, hspace=0.42, wspace=0.38)

    da = a["distance_km"].dropna().values
    db = bv["distance_km"].dropna().values
    dur_a = a["duration_min"].dropna().values
    dur_b = bv["duration_min"].dropna().values
    dep_a = a["departure_time_h"].dropna().values
    dep_b = bv["departure_time_h"].dropna().values

    # Skupne aktivnosti
    acts = sorted(set(a["activity"]) | set(bv["activity"]))
    a_pct  = np.array([(a["activity"] == act).mean()*100 for act in acts])
    bv_pct = np.array([(bv["activity"] == act).mean()*100 for act in acts])

    def ecdf_pair(ax, da, db, xlabel, title):
        for d, color, label in [(da, COLOR_A, "A"), (db, COLOR_BV, "B")]:
            xs = np.sort(d)
            ys = np.arange(1, len(xs)+1) / len(xs)
            ax.step(xs, ys, color=color, linewidth=2, label=label, alpha=ALPHA, where="post")
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel("CDF", fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # R1C1: ECDF razdalje
    ax = fig.add_subplot(gs[0, 0])
    ecdf_pair(ax, da, db, "Razdalja (km)", "Razdalje\n(ECDF)")

    # R1C2: ECDF trajanja
    ax = fig.add_subplot(gs[0, 1])
    ecdf_pair(ax, dur_a, dur_b, "Trajanje (min)", "Trajanje\n(ECDF)")

    # R1C3: ECDF čas odhoda
    ax = fig.add_subplot(gs[0, 2])
    ecdf_pair(ax, dep_a, dep_b, "Čas odhoda (h)", "Čas odhoda\n(ECDF)")

    # R1C4: povprečne razdalje
    ax = fig.add_subplot(gs[0, 3])
    vals = [dist_metrics["A_mean_km"], dist_metrics["BV_mean_km"]]
    bars = ax.bar(["A\nIsochrone", "B\nGravity"], vals,
                  color=[COLOR_A, COLOR_BV], alpha=ALPHA, width=0.55)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x()+bar.get_width()/2, v+0.2, f"{v:.1f}km",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("Povp. razdalja (km)", fontsize=9)
    ax.set_title("Povprečna razdalja", fontsize=10, fontweight="bold")
    ax.grid(True, axis="y", alpha=0.3)

    # R2C1-2: aktivnosti (2 stolpca)
    ax = fig.add_subplot(gs[1, :2])
    x = np.arange(len(acts))
    w = 0.38
    ax.bar(x - w/2, a_pct,  w, color=COLOR_A,  alpha=ALPHA, label="A — Isochrone")
    ax.bar(x + w/2, bv_pct, w, color=COLOR_BV, alpha=ALPHA, label="B — Gravity")
    ax.set_xticks(x)
    ax.set_xticklabels(acts, fontsize=9)
    ax.set_ylabel("Delež (%)", fontsize=9)
    ax.set_title("Tipi aktivnosti", fontsize=10, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)

    # R2C3: diagnostika ring (% izven ringa)
    ax = fig.add_subplot(gs[1, 2])
    dur_raw = step3["Actual duration"].dropna().values
    radii   = dur_raw * 30 / 60
    dist_raw = step3["Actual distance"].dropna().values
    n = min(len(radii), len(dist_raw))
    inside = (dist_raw[:n] <= radii[:n]).sum()
    outside = n - inside
    ax.pie([inside, outside], labels=[f"Znotraj ringa\n({inside})", f"Izven ringa\n({outside})"],
           colors=["#b8e186", "#f4a582"], autopct="%1.0f%%", startangle=90,
           textprops={"fontsize": 9})
    ax.set_title("A potovanja vs B ring\n(Velenje)", fontsize=10, fontweight="bold")

    # R2C4: metrične številke
    ax = fig.add_subplot(gs[1, 3])
    ax.axis("off")
    ks_stat, ks_p = stats.ks_2samp(da, db)
    wass = stats.wasserstein_distance(da, db)
    rows = [
        ["Metrika", "Vrednost"],
        ["A povp. razdalja", f"{dist_metrics['A_mean_km']:.1f} km"],
        ["B povp. razdalja", f"{dist_metrics['BV_mean_km']:.1f} km"],
        ["Razmerje A/B", f"{dist_metrics['A_mean_km']/dist_metrics['BV_mean_km']:.1f}×"],
        ["KS statistika", f"{ks_stat:.3f}"],
        ["KS p-vrednost", f"{ks_p:.4f}"],
        ["Wasserstein", f"{wass:.2f} km"],
        ["Fallback (B)", f"43/100 (43%)"],
    ]
    tbl = ax.table(cellText=rows[1:], colLabels=rows[0],
                   cellLoc="center", loc="center", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2166ac")
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#f7f7f7")
    ax.set_title("Ključne metrike", fontsize=10, fontweight="bold")

    fig.suptitle(
        "Povzetek 1:1 primerjave — A (Isochrone ORS) vs B (Gravity Haversine)  |  Velenje, N=25, 4t",
        fontsize=13, fontweight="bold", y=1.01
    )
    path = os.path.join(OUT_DIR, "velenje_1to1_povzetek.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ velenje_1to1_povzetek.png")


# ── main ─────────────────────────────────────────────────────────────────────

def run():
    print("=== 1:1 primerjava A vs B — Velenje ===\n")
    a, bv, homes, step3 = load()
    print(f"A: {len(a)} potovanj, BV: {len(bv)} potovanj")

    dist_metrics = fig_razdalje(a, bv)
    fig_aktivnosti(a, bv)
    fig_prostorsko(a, bv, homes)
    fig_ring_limit(a, step3)
    fig_povzetek(a, bv, step3, dist_metrics)

    # Shrani metrične številke
    pd.DataFrame([dist_metrics]).to_csv(
        os.path.join(MET_DIR, "08_velenje_1to1_metrike.csv"), index=False
    )
    print(f"\n✓ 08_velenje_1to1_metrike.csv")
    print("\nVse grafike shranjene v figures/")


if __name__ == "__main__":
    run()

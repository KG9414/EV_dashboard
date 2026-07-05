"""
figure_si_referenca.py — Primerjava modelov z razpoložljivimi referenčnimi podatki.

Viri:
  - Eurostat tran_hv_psmod: modalni delež OS, SI=86.1%, EU27=83.6% (2022)
  - Eurostat road_tf_vehmov: VKM osebnih avtomobilov SI=16.801 mrd km (2022)
  - SURS: populacija SI ≈ 2.107M (2022)
  - EU mobility survey (ERSO): povp. potovanj/dan ≈ 2.9–3.5 (EU avg)
  - NHTS 2017 (US): mean=13.12 km, median=5.94 km (vse kategorije)

Grafike:
  1. si_referenca_modal.png     — modalni delež SI vs EU vs modeli
  2. si_referenca_razdalja.png  — razdalje modelov vs NHTS vs SI ocena
  3. si_referenca_povzetek.png  — skupni panel
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

RUN_DIR = os.path.join(os.path.dirname(__file__), "raw_runs")
OUT_DIR = os.path.join(os.path.dirname(__file__), "figures")
MET_DIR = os.path.join(os.path.dirname(__file__), "metrics")
os.makedirs(OUT_DIR, exist_ok=True)

DPI = 150
COLOR_A   = "#2166ac"
COLOR_B   = "#d6604d"
COLOR_BV  = "#1a9641"
COLOR_NH  = "#4dac26"
COLOR_SI  = "#8856a7"
COLOR_EU  = "#e6ab02"

# ── Referenčne vrednosti ──────────────────────────────────────────────────────

# Eurostat (zanesljivo, direktno merjeno)
SI_MODAL_CAR  = 86.1   # % pkm z OS, 2022
EU_MODAL_CAR  = 83.6   # % pkm z OS, EU27, 2022

# Izpeljano iz Eurostat VKM + SURS populacija (groba ocena, z negotovostjo)
# VKM = 16.801 mrd km, pop = 2.107M, 365 dni, ~3.2 potovanj/dan (EU avg)
SI_VKM_MRD     = 16.801
SI_POP          = 2_107_000
SI_KM_PER_YEAR = (SI_VKM_MRD * 1e9) / SI_POP          # ~7974 km/leto/osebo
SI_KM_PER_DAY  = SI_KM_PER_YEAR / 365                  # ~21.8 km/dan/osebo
# Negotovost: EU ankete kažejo 2.9–3.5 potovanj/dan z avtom
SI_TRIP_LOW    = SI_KM_PER_DAY / 3.5   # ~6.2 km/potovanje
SI_TRIP_HIGH   = SI_KM_PER_DAY / 2.9   # ~7.5 km/potovanje
SI_TRIP_EST    = SI_KM_PER_DAY / 3.2   # ~6.8 km/potovanje (srednja ocena)

# NHTS 2017 (ZDA, primerjalna referenca)
NHTS_MEAN   = 13.12
NHTS_MEDIAN =  5.94


def load_models():
    a  = pd.read_parquet(os.path.join(RUN_DIR, "A_N25_4trips.parquet"))
    b  = pd.read_parquet(os.path.join(RUN_DIR, "B_N25_4trips.parquet"))
    bv = pd.read_parquet(os.path.join(RUN_DIR, "B_velenje", "B_velenje_N25_4trips.parquet"))
    return a, b, bv


# ── 1. Modalni delež ─────────────────────────────────────────────────────────

def fig_modal():
    fig, ax = plt.subplots(figsize=(9, 5.5))

    categories = ["Slovenija\n(Eurostat 2022)", "EU-27\n(Eurostat 2022)",
                  "Model A\n(samo OS)", "Model B\n(samo OS)"]
    values     = [SI_MODAL_CAR, EU_MODAL_CAR, 100, 100]
    colors     = [COLOR_SI, COLOR_EU, COLOR_A, COLOR_B]
    hatches    = ["", "", "///", "///"]

    bars = ax.bar(categories, values, color=colors, alpha=0.8, width=0.55)
    for bar, h in zip(bars, hatches):
        bar.set_hatch(h)

    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.8,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=12, fontweight="bold")

    # Referenčna linija pri SI vrednosti
    ax.axhline(SI_MODAL_CAR, color=COLOR_SI, linestyle="--", linewidth=1.5,
               alpha=0.7, label=f"SI referenca: {SI_MODAL_CAR}%")

    ax.set_ylabel("Modalni delež (%)", fontsize=12)
    ax.set_ylim(0, 115)
    ax.set_title(
        "Modalni delež osebnih avtomobilov\nSlovenija vs EU vs modeli (A in B simulirata samo OS)",
        fontsize=12, fontweight="bold"
    )
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)

    # Opomba
    ax.text(0.5, -0.18,
            "Vir: Eurostat tran_hv_psmod, 2022  |  Modela A in B simulirata izključno osebne avtomobile (100% modal delež po definiciji)",
            transform=ax.transAxes, ha="center", fontsize=8, color="gray", style="italic")

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "si_referenca_modal.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ si_referenca_modal.png")


# ── 2. Razdalje: modeli vs NHTS vs SI ocena ──────────────────────────────────

def fig_razdalje(a, b, bv):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Panel 1: povprečne razdalje z referenčnimi črtami
    ax = axes[0]
    model_labels = ["A — Isochrone\n(Velenje)", "B — Gravity\n(Krško)", "B — Gravity\n(Velenje)"]
    model_means  = [a["distance_km"].mean(), b["distance_km"].mean(), bv["distance_km"].mean()]
    model_colors = [COLOR_A, COLOR_B, COLOR_BV]

    bars = ax.bar(model_labels, model_means, color=model_colors, alpha=0.78, width=0.5, zorder=3)
    for bar, v in zip(bars, model_means):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.2,
                f"{v:.1f} km", ha="center", va="bottom", fontsize=11, fontweight="bold")

    # NHTS referenca (ZDA)
    ax.axhline(NHTS_MEAN, color=COLOR_NH, linestyle="-", linewidth=2,
               label=f"NHTS (ZDA, 2017): mean = {NHTS_MEAN:.1f} km", zorder=4)
    ax.axhline(NHTS_MEDIAN, color=COLOR_NH, linestyle=":", linewidth=2,
               label=f"NHTS (ZDA, 2017): median = {NHTS_MEDIAN:.1f} km", zorder=4)

    # SI ocena (izpeljana, z intervalom negotovosti)
    ax.axhspan(SI_TRIP_LOW, SI_TRIP_HIGH, alpha=0.12, color=COLOR_SI, zorder=0)
    ax.axhline(SI_TRIP_EST, color=COLOR_SI, linestyle="--", linewidth=2,
               label=f"SI ocena* (Eurostat VKM/pop): ~{SI_TRIP_EST:.1f} km", zorder=4)
    ax.text(2.7, SI_TRIP_EST + 0.15, f"SI ocena*\n{SI_TRIP_LOW:.1f}–{SI_TRIP_HIGH:.1f} km",
            ha="right", va="bottom", fontsize=8, color=COLOR_SI)

    ax.set_ylabel("Povprečna razdalja potovanja (km)", fontsize=11)
    ax.set_title("Povprečna razdalja: modeli vs reference", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8.5, loc="upper right")
    ax.set_ylim(0, max(model_means) * 1.35)
    ax.grid(True, axis="y", alpha=0.3, zorder=0)

    # Panel 2: ECDF vseh treh modelov + referenčni točki
    ax = axes[1]
    for data, color, label in [
        (a["distance_km"].dropna(), COLOR_A,  "A — Isochrone (Velenje)"),
        (b["distance_km"].dropna(), COLOR_B,  "B — Gravity (Krško)"),
        (bv["distance_km"].dropna(), COLOR_BV, "B — Gravity (Velenje)"),
    ]:
        xs = np.sort(data.values)
        ys = np.arange(1, len(xs)+1) / len(xs)
        ax.step(xs, ys, color=color, linewidth=2.2, label=label, alpha=0.8, where="post")

    # NHTS referenčni točki
    ax.axvline(NHTS_MEDIAN, color=COLOR_NH, linestyle=":", linewidth=1.8,
               label=f"NHTS median {NHTS_MEDIAN:.1f} km", alpha=0.9)
    ax.axvline(NHTS_MEAN, color=COLOR_NH, linestyle="-", linewidth=1.8,
               label=f"NHTS mean {NHTS_MEAN:.1f} km", alpha=0.9)

    # SI interval
    ax.axvspan(SI_TRIP_LOW, SI_TRIP_HIGH, alpha=0.12, color=COLOR_SI,
               label=f"SI ocena* {SI_TRIP_LOW:.1f}–{SI_TRIP_HIGH:.1f} km")

    ax.set_xlabel("Razdalja potovanja (km)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title("ECDF razdalj: modeli + referenčne vrednosti", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 60)

    fig.suptitle(
        "Primerjava modelov z referenčnimi podatki\n"
        "*SI ocena izpeljana iz Eurostat VKM (16.8 mrd km) / populacija / ~3.2 potovanj/dan  |  ni direktna anketa",
        fontsize=11, fontweight="bold"
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "si_referenca_razdalja.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ si_referenca_razdalja.png")


# ── 3. Povzetek — skupni panel ────────────────────────────────────────────────

def fig_povzetek(a, b, bv):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: modalni delež (horizontalni)
    ax = axes[0]
    labels = ["SI (Eurostat)", "EU-27 (Eurostat)", "Model A\n(samo OS)", "Model B\n(samo OS)"]
    vals   = [SI_MODAL_CAR, EU_MODAL_CAR, 100, 100]
    colors = [COLOR_SI, COLOR_EU, COLOR_A, COLOR_B]
    bars   = ax.barh(labels, vals, color=colors, alpha=0.78, height=0.5)
    for bar, v in zip(bars, vals):
        ax.text(v + 0.5, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=11, fontweight="bold")
    ax.axvline(SI_MODAL_CAR, color=COLOR_SI, linestyle="--", linewidth=1.5, alpha=0.7)
    ax.set_xlabel("Modalni delež OS (%)", fontsize=11)
    ax.set_title("Modalni delež\nosebnih avtomobilov", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 115)
    ax.grid(True, axis="x", alpha=0.3)
    ax.text(0.5, -0.14, "Vir: Eurostat tran_hv_psmod, 2022",
            transform=ax.transAxes, ha="center", fontsize=8, color="gray", style="italic")

    # Panel 2: povprečne razdalje
    ax = axes[1]
    bar_labels = ["A\nVelenje", "B\nKrško", "B\nVelenje", "NHTS\nZDA", "SI\nocena*"]
    bar_vals   = [a["distance_km"].mean(), b["distance_km"].mean(), bv["distance_km"].mean(),
                  NHTS_MEAN, SI_TRIP_EST]
    bar_colors = [COLOR_A, COLOR_B, COLOR_BV, COLOR_NH, COLOR_SI]
    bar_alphas = [0.78, 0.78, 0.78, 0.78, 0.5]
    bar_hatch  = ["", "", "", "", "//"]

    bars = ax.bar(bar_labels, bar_vals, color=bar_colors, alpha=0.78, width=0.55, zorder=3)
    for bar, v, h in zip(bars, bar_vals, bar_hatch):
        bar.set_hatch(h)
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.2,
                f"{v:.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    # SI interval
    ax.axhspan(SI_TRIP_LOW, SI_TRIP_HIGH, alpha=0.1, color=COLOR_SI, zorder=0,
               label=f"SI interval ({SI_TRIP_LOW:.1f}–{SI_TRIP_HIGH:.1f} km)")
    ax.legend(fontsize=8)
    ax.set_ylabel("Povp. razdalja (km)", fontsize=11)
    ax.set_title("Povprečna razdalja potovanja\n(modeli + reference)", fontsize=11, fontweight="bold")
    ax.set_ylim(0, max(bar_vals) * 1.35)
    ax.grid(True, axis="y", alpha=0.3, zorder=0)
    ax.text(0.5, -0.14, "Vir: NHTS 2017 (US DOT)  |  *SI iz Eurostat VKM/pop/3.2pot",
            transform=ax.transAxes, ha="center", fontsize=8, color="gray", style="italic")

    # Panel 3: tabela - kaj je zanesljivo, kaj ocena
    ax = axes[2]
    ax.axis("off")
    rows = [
        ["Indikator", "Vrednost", "Vir", "Zanesljivost"],
        ["Modalni delež\nOS (SI)", "86.1 %", "Eurostat\n2022", "✓✓ Direktno"],
        ["Modalni delež\nOS (EU)", "83.6 %", "Eurostat\n2022", "✓✓ Direktno"],
        ["VKM OS (SI)", "16.8 mrd km", "Eurostat\n2022", "✓✓ Direktno"],
        ["Avg razdalja\n(NHTS, ZDA)", "13.1 km", "NHTS\n2017", "✓ Tuja ref."],
        ["Avg razdalja\n(SI, ocena)", "~6.8 km", "Izpeljano\niz VKM", "~ Groba ocena"],
        ["Model A mean", "15.8 km", "Simulacija\nVelenje", "— Model"],
        ["Model B mean\n(Krško)", "13.2 km", "Simulacija\nKrško", "— Model"],
        ["Model B mean\n(Velenje)", "5.0 km", "Simulacija\nVelenje", "— Model"],
    ]

    colors_tbl = [["#2166ac"]*4] + [
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#d4edda"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#d4edda"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#d4edda"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#fff3cd"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#fce4d6"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#ddeeff"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#ddeeff"],
        ["#f7f7f7", "#f7f7f7", "#f7f7f7", "#ddeeff"],
    ]

    tbl = ax.table(cellText=rows[1:], colLabels=rows[0],
                   cellLoc="center", loc="center", bbox=[0, 0, 1, 1],
                   cellColours=colors_tbl[1:])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2166ac")
            cell.set_text_props(color="white", fontweight="bold")
        cell.set_edgecolor("#cccccc")

    ax.set_title("Pregled referenčnih podatkov\nin zanesljivosti", fontsize=11, fontweight="bold")

    fig.suptitle(
        "Modela A in B v kontekstu razpoložljivih referenčnih podatkov za Slovenijo in mednarodnih primerjav\n"
        "Direktni slovensko specifični podatki o razdalji potovanj niso bili dostopni prek API-jev (Eurostat, SURS)",
        fontsize=11, fontweight="bold"
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "si_referenca_povzetek.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ si_referenca_povzetek.png")

    # Shrani razširjeno CSV
    ref_df = pd.DataFrame([
        {"indikator": "Modalni delež OS (SI)", "vrednost": 86.1, "enota": "%",
         "vir": "Eurostat tran_hv_psmod", "leto": 2022, "zanesljivost": "direktno"},
        {"indikator": "Modalni delež OS (EU27)", "vrednost": 83.6, "enota": "%",
         "vir": "Eurostat tran_hv_psmod", "leto": 2022, "zanesljivost": "direktno"},
        {"indikator": "VKM osebnih avtomobilov (SI)", "vrednost": 16801, "enota": "mio km",
         "vir": "Eurostat road_tf_vehmov", "leto": 2022, "zanesljivost": "direktno"},
        {"indikator": "Povp. razdalja/potovanje SI (ocena)", "vrednost": round(SI_TRIP_EST, 1),
         "enota": "km", "vir": "Izpeljano: Eurostat VKM / SURS pop / 3.2 pot/dan",
         "leto": 2022, "zanesljivost": "izpeljano (~±20%)"},
        {"indikator": "NHTS mean razdalja (ZDA)", "vrednost": NHTS_MEAN, "enota": "km",
         "vir": "NHTS 2017 (US DOT)", "leto": 2017, "zanesljivost": "tuja referenca"},
        {"indikator": "NHTS median razdalja (ZDA)", "vrednost": NHTS_MEDIAN, "enota": "km",
         "vir": "NHTS 2017 (US DOT)", "leto": 2017, "zanesljivost": "tuja referenca"},
        {"indikator": "Model A mean (Velenje)", "vrednost": round(a["distance_km"].mean(), 1),
         "enota": "km", "vir": "Simulacija A, N=25", "leto": 2025, "zanesljivost": "model"},
        {"indikator": "Model B mean (Krško)", "vrednost": round(b["distance_km"].mean(), 1),
         "enota": "km", "vir": "Simulacija B, N=25", "leto": 2025, "zanesljivost": "model"},
        {"indikator": "Model B mean (Velenje)", "vrednost": round(bv["distance_km"].mean(), 1),
         "enota": "km", "vir": "Simulacija B@Velenje, N=25", "leto": 2025, "zanesljivost": "model"},
    ])
    ref_df.to_csv(os.path.join(MET_DIR, "07_slovenska_referenca.csv"), index=False)
    print(f"✓ 07_slovenska_referenca.csv (posodobljeno)")


# ── main ─────────────────────────────────────────────────────────────────────

def run():
    print("=== Primerjava z referenčnimi podatki ===\n")
    print(f"SI ocena razdalje: {SI_TRIP_EST:.1f} km (interval: {SI_TRIP_LOW:.1f}–{SI_TRIP_HIGH:.1f} km)")
    print(f"  Osnova: VKM={SI_VKM_MRD} mrd km / pop={SI_POP/1e6:.3f}M / 365d / 3.2 pot/dan\n")
    a, b, bv = load_models()
    fig_modal()
    fig_razdalje(a, b, bv)
    fig_povzetek(a, b, bv)
    print("\nVse grafike shranjene v figures/")


if __name__ == "__main__":
    run()

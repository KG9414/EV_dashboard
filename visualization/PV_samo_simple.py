"""
PV-samozadostnost.py
─────────────────────────────────────────────────────────────────────────────
Samooskrba EV parkirišča s PV sistemom.

Graf prikazuje za vsako uro dneva:
  - ZELENA črta = koliko kWh naredi PV sistem (solarni paneli)
  - MODRA črta  = koliko kWh potrebujejo EV-ji za polnjenje @ parking

Samooskrba % = PV pokrije / EV skupaj × 100
  → 100% = paneli v tistem trenutku pokrije vso porabo
  → < 100% = razliko vzamemo iz omrežja
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ═══════════════════════════════════════════════════════════
# NASTAVITVE
# ═══════════════════════════════════════════════════════════

#P_KWP      = 12.20   # moč PV sistema [kWp]

P_KWP      = 100

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════
# PREBERI PVGIS CSV
# ═══════════════════════════════════════════════════════════

def load_pvgis(filename):
    rows = []
    filepath = os.path.join(SCRIPT_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if len(line) >= 5 and line[2] == ":" and line[:2].isdigit():
                parts = [p for p in line.split("\t") if p.strip() != ""]
                try:
                    hour  = int(parts[0].split(":")[0])
                    g_i   = float(parts[1])
                    gcs_i = float(parts[4])
                    rows.append({"hour": hour, "G_i": g_i, "Gcs_i": gcs_i})
                except (ValueError, IndexError):
                    pass
    return pd.DataFrame(rows).set_index("hour")

def find_file(keyword, ext):
    """Najde datoteko ki vsebuje keyword — neobčutljivo na velike/male črke."""
    files = [f for f in os.listdir(SCRIPT_DIR)
             if f.lower().endswith(ext) and keyword.lower() in f.lower()]
    if not files:
        raise FileNotFoundError(
            f"Ne najdem datoteke z '{keyword}' v imenu.\n"
            f"Datoteke v mapi: {[f for f in os.listdir(SCRIPT_DIR)]}"
        )
    return files[0]

# ═══════════════════════════════════════════════════════════
# PREBERI EV PODATKE
# ═══════════════════════════════════════════════════════════

# file_2 = "03_Vehicle_trip_parameters_100_EVs_2_trips_1_days.xlsx"
# file_4 = "03_Vehicle_trip_parameters_20_EVs_4_trips_1_days.xlsx"

file_2 = "03_Vehicle_trip_parameters_100_EVs_2_trips_1_days_fix.xlsx"
file_4 = "03_Vehicle_trip_parameters_25_EVs_4_trips_1_days.xlsx"

def ev_work_energy_hourly(df):
    """
    Calculates the charging energy demand per 15-min interval at the workplace.
    For each vehicle, during Work parking, spreads the required charging energy
    (energy spent in inbound trip + energy needed for future trips) uniformly
    over the parking duration.
    
    Returns: array (24,) with energy (kWh) per hour.
    """
    nv  = df["Vehicle ID"].nunique()
    intervals = 96
    DT_H = 0.25  # hours per interval
    
    # Matrix to hold charging energy per interval (kWh per 15-min)
    eng_charge = np.zeros((nv, intervals))
    
    home_loc = (
        df[df["Trip ID"] == 1]
        .groupby("Vehicle ID")[["Start_lon", "Start_lat"]]
        .first()
    )
    
    for vid in range(1, nv + 1):
        vt = df[df["Vehicle ID"] == vid].sort_values("Trip ID").reset_index(drop=True)
        
        for idx, trip in vt.iterrows():
            if trip["Trip type"] != "Work":
                continue
            
            park_start = int(trip["End"])
            later_trips = vt[vt["Trip ID"] > trip["Trip ID"]]
            
            if later_trips.empty:
                continue
            
            park_end = int(later_trips.iloc[0]["Start"])
            park_intervals = park_end - park_start
            if park_intervals <= 0:
                continue
            
            # Energy spent in inbound trip
            e_inbound = float(trip["Energy_kWh"])
            # Energy needed for future trips
            e_future = float(later_trips["Energy_kWh"].sum()) if not later_trips.empty else 0.0
            e_total = e_inbound + e_future
            
            # Spread uniformly over parking intervals (kWh per 15-min)
            e_per_interval = e_total / park_intervals
            eng_charge[vid-1, park_start:park_end] = e_per_interval
    
    # Sum across all vehicles for each interval
    ev_demand_15min = eng_charge.sum(axis=0)
    
    # Aggregate to hourly
    ev_hourly = np.array([ev_demand_15min[h*4:(h+1)*4].sum() for h in range(24)])
    return ev_hourly


# ═══════════════════════════════════════════════════════════
# SAMOOSKRBA
# ═══════════════════════════════════════════════════════════

def samooskrba(pv, ev):
    """
    Calculates self-sufficiency metrics.
    
    Self-sufficiency = (PV used locally / total consumption) * 100%
    Where PV used locally = sum(min(pv[t], ev[t]) for each timestep t)
    
    Returns: (percentage, covered_energy, surplus_energy, deficit_energy)
    """
    # Element-wise minimum to get PV used locally per timestep
    pv_used_locally = np.minimum(pv, ev)
    
    # Totals
    total_consumption = ev.sum()
    total_pv_production = pv.sum()
    covered_energy = pv_used_locally.sum()  # PV energy actually used
    surplus_energy = np.maximum(pv - ev, 0).sum()  # Excess PV
    deficit_energy = np.maximum(ev - pv, 0).sum()  # Needs grid
    
    # Self-sufficiency percentage
    self_sufficiency = (covered_energy / total_consumption * 100) if total_consumption > 0 else 0
    
    return self_sufficiency, covered_energy, surplus_energy, deficit_energy


_cached_pv_data = None

def load_pv_and_ev_data():
    jan_file = find_file("JANUARY", ".csv")
    jun_file = find_file("JUNE",    ".csv")

    jan = load_pvgis(jan_file)
    jun = load_pvgis(jun_file)

    hours = np.arange(24)
    pv_jan = jan["G_i"].reindex(hours, fill_value=0).values / 1000 * P_KWP
    pv_jun = jun["G_i"].reindex(hours, fill_value=0).values / 1000 * P_KWP

    df_2 = pd.read_excel(os.path.join(SCRIPT_DIR, file_2))
    df_4 = pd.read_excel(os.path.join(SCRIPT_DIR, file_4))
    df_2.columns = df_2.columns.str.strip()
    df_4.columns = df_4.columns.str.strip()

    ev_total = ev_work_energy_hourly(df_2) + ev_work_energy_hourly(df_4)

    pct_jan, pok_jan, pre_jan, def_jan = samooskrba(pv_jan, ev_total)
    pct_jun, pok_jun, pre_jun, def_jun = samooskrba(pv_jun, ev_total)

    return {
        "hours": hours,
        "consumption": ev_total,
        "pv_production_jan": pv_jan,
        "pv_production_jun": pv_jun,
        "pv_used_jan": np.minimum(pv_jan, ev_total),
        "pv_used_jun": np.minimum(pv_jun, ev_total),
        "self_sufficiency_jan": pct_jan,
        "self_sufficiency_jun": pct_jun,
        "total_pv_jan": pv_jan.sum(),
        "total_pv_jun": pv_jun.sum(),
        "covered_energy_jan": pok_jan,
        "covered_energy_jun": pok_jun,
        "surplus_energy_jan": pre_jan,
        "surplus_energy_jun": pre_jun,
        "deficit_energy_jan": def_jan,
        "deficit_energy_jun": def_jun,
    }


def get_pv_self_sufficiency_data():
    global _cached_pv_data
    if _cached_pv_data is None:
        _cached_pv_data = load_pv_and_ev_data()
    return _cached_pv_data


def build_pv_plot():
    data = get_pv_self_sufficiency_data()

    plt.rcParams.update({
        "figure.facecolor":  "#F7F9FC",
        "axes.facecolor":    "#FFFFFF",
        "axes.edgecolor":    "#D0D7E3",
        "axes.grid":         True,
        "grid.color":        "#E8ECF4",
        "grid.linewidth":    0.8,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "font.family":       "DejaVu Sans",
    })

    C_PV  = "#16A34A"   # zelena — PV
    C_EV  = "#2563EB"   # modra  — EV
    C_OK  = "#BBF7D0"   # zeleno ozadje — PV > EV (presežek)
    C_NOK = "#FEE2E2"   # rdeče ozadje  — EV > PV (deficit)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    fig.patch.set_alpha(0.0)
    fig.suptitle(
        f"EV car-park self-sufficiency, Krško  |  PV {P_KWP} kWp",
        fontsize=13, fontweight="bold", color="#1E293B", y=1.01,
    )

    def plot_month(ax, pv, ev, title, pct, pok, pre, def_):
        h = np.arange(24)
        ax.fill_between(h, pv, ev, where=(pv >= ev),
                        color=C_OK,  alpha=0.55, step="mid",
                        interpolate=True, label="PV surplus (to grid)")
        ax.fill_between(h, pv, ev, where=(pv < ev),
                        color=C_NOK, alpha=0.55, step="mid",
                        interpolate=True, label="Deficit — from grid")
        ax.step(h, pv, where="mid", color=C_PV, lw=2.8,
                label=f"PV production  ({pv.sum():.1f} kWh/day)")
        ax.step(h, ev, where="mid", color=C_EV, lw=2.8,
                label=f"EV demand @ parking  ({ev.sum():.1f} kWh/day)")
        ax.set_xlim(0, 23)
        ax.set_xticks(range(0, 24, 2))
        ax.set_xticklabels([f"{h:02d}h" for h in range(0, 24, 2)], fontsize=9)
        ax.set_xlabel("Hour of day", fontsize=10)
        ax.set_ylabel("Energy (kWh)", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.legend(fontsize=9, loc="upper left", framealpha=0.95)
        barva = "#16A34A" if pct >= 50 else "#EA580C" if pct >= 20 else "#DC2626"
        ax.text(0.98, 0.97,
                f"Self-sufficiency\n{pct:.1f} %",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=15, fontweight="bold", color=barva,
                bbox=dict(boxstyle="round,pad=0.5", fc="white",
                          ec=barva, lw=2, alpha=0.95))
        ax.text(0.5, -0.15,
                f"PV covers: {pok:.1f} kWh  │  "
                f"PV surplus: {pre:.1f} kWh  │  "
                f"From grid: {def_:.1f} kWh",
                transform=ax.transAxes, ha="center", va="top",
                fontsize=9, color="#475569",
                bbox=dict(boxstyle="round,pad=0.4", fc="#F1F5F9", ec="#CBD5E1"))

    plot_month(ax1, data["pv_production_jan"], data["consumption"],
               "January  (winter, average day)",
               data["self_sufficiency_jan"], data["covered_energy_jan"],
               data["surplus_energy_jan"], data["deficit_energy_jan"])
    plot_month(ax2, data["pv_production_jun"], data["consumption"],
               "June  (summer, average day)",
               data["self_sufficiency_jun"], data["covered_energy_jun"],
               data["surplus_energy_jun"], data["deficit_energy_jun"])
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    return fig


if __name__ == "__main__":
    fig = build_pv_plot()
    out = os.path.join(SCRIPT_DIR, "PV_samooskrba.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"\nGraf shranjen: {out}")
    plt.show()
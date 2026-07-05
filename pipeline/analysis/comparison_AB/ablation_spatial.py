"""
ablation_spatial.py — prostorska ablacija na istem mestu (Velenje).

Enaki domovi (A ROS.shp), enaki tipi potovanj (A Step3).
Dve metodi vzorčenja destinacij:
  - A_iso : ORS isochrone (obstoječe koordinate iz A Step2)
  - B_grav: Haversine ring + gravitacijski model na Velenje OSM (B metoda, B koda)

Ugotavlja: ali B-jeva metoda izbira boljše / bolj realistične destinacije?
"""

import os, sys, time
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Point

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../pipeline"))
from Functions_step_2 import haversine, sample_destination, haversine_ring_filter

A_ROOT  = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/OneDrive_1_2-25-2026"
OUT_DIR = os.path.join(os.path.dirname(__file__), "figures")
MET_DIR = os.path.join(os.path.dirname(__file__), "metrics")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(MET_DIR, exist_ok=True)

VELENJE_PLACE = "Velenje, Slovenia"
AVG_SPEED_KMH = 30
BETA = 2
DPI  = 150

COLOR_A   = "#2166ac"
COLOR_B_V = "#1a9641"   # zelena za B-gravity@Velenje
ALPHA     = 0.7


# ── 1. Naloži A-jeve vhodne podatke (Velenje) ────────────────────────────────

def load_a_velenje():
    """Vrne (homes_gdf, trips_df)."""
    homes = gpd.read_file(
        os.path.join(A_ROOT, "02_Trips", "02_Trips_25_EVs_4_trips_1_days_ROS.shp")
    )
    step3 = pd.read_excel(
        os.path.join(A_ROOT, "03_Vehicle_parameters",
                     "03_Vehicle_trip_parameters_25_EVs_4_trips_1_days.xlsx")
    )
    step2 = pd.read_excel(
        os.path.join(A_ROOT, "02_Trips", "02_Trips_25_EVs_4_trips_1_days.xlsx")
    )
    # Spoji Step3 + Step2 za A-jeve dejanske destinacije
    step3 = step3.copy()
    step3["end_lat"] = step2["End location lat"].values
    step3["end_lon"] = step2["End location lon"].values
    step3["start_lat"] = step2["Start location lat"].values
    step3["start_lon"] = step2["Start location lon"].values
    return homes, step3


# ── 2. Pridobi Velenje OSM podatke (enaka logika kot B za Krško) ─────────────

def fetch_velenje_osm():
    print("Pridobivam Velenje OSM podatke...")
    t0 = time.time()
    tags = {"landuse": True, "leisure": True, "amenity": True,
            "building": True, "shop": True}
    gdf = ox.features_from_place(VELENJE_PLACE, tags=tags)
    print(f"  → {len(gdf)} objektov ({time.time()-t0:.1f}s)")
    return gdf


def build_init_data(gdf):
    """Replicira B-jevo init() za Velenje — vrne (work, business, edu, shop, leisure, building)."""
    def _filter(col, values):
        if col not in gdf.columns:
            return gdf.iloc[0:0]
        if values is None:
            return gdf[gdf[col].notna()].copy()
        return gdf[gdf[col].isin(values)].copy()

    work     = _filter("building", {"office","commercial","industrial","retail","warehouse"})
    business = _filter("building", {"office","commercial","industrial","retail"})
    edu      = _filter("amenity",  {"school","college","university","kindergarten","music_school"})
    shop     = _filter("shop",     None)
    leisure  = _filter("leisure",  None)
    building = _filter("building", None)

    print(f"  OSM sloji: work={len(work)}, edu={len(edu)}, shop={len(shop)}, "
          f"leisure={len(leisure)}, building={len(building)}")
    return work, business, edu, shop, leisure, building


# ── 3. B-gravity vzorčenje destinacij za vsako potovanje ─────────────────────

def sample_b_gravity(trips_df, homes_gdf, init_data, seed=42):
    """
    Za vsako potovanje iz trips_df vzorči destinacijo z B-jevo gravity metodo.
    Vrne DataFrame z (vehicle_id, trip_id, end_lat, end_lon, method='B_gravity').
    """
    np.random.seed(seed)
    results = []

    for _, row in trips_df.iterrows():
        vid      = int(row["Vehicle ID"])
        trip_id  = int(row["Trip ID"])
        ttype    = row["Trip type"]
        duration = float(row["Actual duration"]) if pd.notna(row.get("Actual duration")) else 20.0

        # Določi izhodišče: trip 1 = dom, ostali = konec prejšnjega potovanja
        home_row = homes_gdf.iloc[(vid - 1) % len(homes_gdf)]
        start_lat = home_row.geometry.y
        start_lon = home_row.geometry.x

        if trip_id > 1:
            prev = [r for r in results if r["vehicle_id"] == vid and r["trip_id"] == trip_id - 1]
            if prev:
                start_lat = prev[-1]["end_lat"]
                start_lon = prev[-1]["end_lon"]

        candidates = haversine_ring_filter(
            init_data, ttype, start_lat, start_lon, duration, AVG_SPEED_KMH
        )

        if not candidates:
            # Fallback: gravitacija brez ring filtra (celoten nabor tipa)
            type_map = {
                'WORK': init_data[0], 'BUSINESS': init_data[1],
                'EDUCATION': init_data[2], 'SHOPPING': init_data[3],
                'LEISURE': init_data[4],
            }
            fallback_gdf = type_map.get(ttype.upper(), init_data[5])
            if fallback_gdf.empty:
                fallback_gdf = init_data[5]
            if not fallback_gdf.empty:
                row_sample = fallback_gdf.sample(1).iloc[0]
                pt = row_sample.geometry.centroid
                results.append({"vehicle_id": vid, "trip_id": trip_id,
                                 "activity": ttype, "method": "B_gravity_fallback",
                                 "end_lat": pt.y, "end_lon": pt.x})
                continue
            else:
                results.append({"vehicle_id": vid, "trip_id": trip_id,
                                 "activity": ttype, "method": "B_gravity_no_candidate",
                                 "end_lat": start_lat, "end_lon": start_lon})
                continue

        dest = sample_destination((start_lat, start_lon), candidates, beta=BETA)
        results.append({
            "vehicle_id": vid, "trip_id": trip_id, "activity": ttype,
            "method": "B_gravity",
            "end_lat": dest["coords"][0], "end_lon": dest["coords"][1],
        })

    df = pd.DataFrame(results)
    n_fallback = (df["method"] != "B_gravity").sum()
    if n_fallback:
        print(f"  Fallback destinacije (ring prazen): {n_fallback}/{len(df)}")
    return df


# ── 4. Prostorske metrike ─────────────────────────────────────────────────────

def spatial_metrics(lat, lon, label):
    from shapely.geometry import MultiPoint
    coords = list(zip(lon, lat))
    pts = MultiPoint(coords)
    lat_m = np.mean(lat)
    x = np.array(lon) * 111 * np.cos(np.radians(lat_m))
    y = np.array(lat) * 111
    pts_km = MultiPoint(list(zip(x, y)))
    hull_area = pts_km.convex_hull.area

    # Povprečna medsebojna razdalja (subsample za hitrost)
    n = len(lat)
    if n > 50:
        idx = np.random.choice(n, 50, replace=False)
        lat_s, lon_s = lat[idx], lon[idx]
    else:
        lat_s, lon_s = lat, lon
    dists = []
    for i in range(len(lat_s)):
        for j in range(i+1, len(lat_s)):
            dists.append(haversine(lon_s[i], lat_s[i], lon_s[j], lat_s[j]))

    return {
        "metoda": label,
        "n_destinacij": n,
        "konveksna_km2": round(hull_area, 1),
        "povp_meddestin_km": round(np.mean(dists), 2) if dists else np.nan,
        "std_meddestin_km":  round(np.std(dists),  2) if dists else np.nan,
    }


# ── 5. Grafike ────────────────────────────────────────────────────────────────

def plot_comparison(a_df, b_df, homes_gdf):
    """Side-by-side + overlay: A isochrone vs B gravity, obe za Velenje."""

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))

    panels = [
        (axes[0], a_df,  COLOR_A,   "A — Isochrone (ORS)\nVelenje"),
        (axes[1], b_df,  COLOR_B_V, "B — Gravity (Haversine)\nVelenje"),
    ]

    for ax, df, color, title in panels:
        end_lat = df["end_lat"].values
        end_lon = df["end_lon"].values

        hb = ax.hexbin(end_lon, end_lat, gridsize=10, mincnt=1,
                       cmap="Blues" if color == COLOR_A else "Greens", alpha=0.85)
        fig.colorbar(hb, ax=ax, label="N dest.")

        ax.scatter(homes_gdf.geometry.x, homes_gdf.geometry.y,
                   color="black", s=35, zorder=5, marker="^", label="Domovi", alpha=0.8)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Geografska dolžina")
        ax.set_ylabel("Geografska širina")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # Overlay panel (obe metodi skupaj)
    ax = axes[2]
    ax.scatter(a_df["end_lon"], a_df["end_lat"],
               color=COLOR_A, alpha=0.55, s=30, label="A — Isochrone", zorder=3)
    ax.scatter(b_df["end_lon"], b_df["end_lat"],
               color=COLOR_B_V, alpha=0.55, s=30, label="B — Gravity", zorder=4, marker="s")
    ax.scatter(homes_gdf.geometry.x, homes_gdf.geometry.y,
               color="black", s=40, zorder=6, marker="^", label="Domovi")
    ax.set_title("Prekrivanje — obe metodi\nVelenje", fontsize=12, fontweight="bold")
    ax.set_xlabel("Geografska dolžina")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Ablacija: Isochrone (A) vs Gravity (B)  —  ISTI domovi, ISTO mesto (Velenje)\n"
        "N=25 vozil, 4 potovanja/vozilo",
        fontsize=13, fontweight="bold"
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "ablacija_velenje_isochrone_vs_gravity.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ ablacija_velenje_isochrone_vs_gravity.png")


def plot_activity_split(a_df, b_df):
    """Destinacije po tipu aktivnosti — kako se prostorsko razlikujeta?"""
    activities = sorted(set(a_df["activity"]) | set(b_df["activity"]))
    n_act = len(activities)
    cols = 4
    rows = (n_act + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 4.5))
    axes = axes.flatten()

    for i, act in enumerate(activities):
        ax = axes[i]
        a_sub = a_df[a_df["activity"] == act]
        b_sub = b_df[b_df["activity"] == act]

        if not a_sub.empty:
            ax.scatter(a_sub["end_lon"], a_sub["end_lat"],
                       color=COLOR_A, alpha=0.7, s=40, label=f"A ({len(a_sub)})", zorder=3)
        if not b_sub.empty:
            ax.scatter(b_sub["end_lon"], b_sub["end_lat"],
                       color=COLOR_B_V, alpha=0.7, s=40, marker="s",
                       label=f"B gravity ({len(b_sub)})", zorder=4)

        ax.set_title(act, fontsize=11, fontweight="bold")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("lon", fontsize=8)
        ax.set_ylabel("lat", fontsize=8)

    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    fig.suptitle("Destinacije po aktivnosti: A Isochrone vs B Gravity  (Velenje)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "ablacija_velenje_po_aktivnosti.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("✓ ablacija_velenje_po_aktivnosti.png")


def plot_distance_from_home(a_df, b_df, homes_gdf):
    """Porazdelitev razdalj destinacija–dom: A vs B gravity."""
    def dist_from_home(df, homes):
        dists = []
        for _, row in df.iterrows():
            vid = int(row["vehicle_id"])
            home = homes.iloc[(vid - 1) % len(homes)]
            d = haversine(home.geometry.x, home.geometry.y,
                          row["end_lon"], row["end_lat"])
            dists.append(d)
        return np.array(dists)

    d_a = dist_from_home(a_df, homes_gdf)
    d_b = dist_from_home(b_df, homes_gdf)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # ECDF
    ax = axes[0]
    for d, color, label in [(d_a, COLOR_A, "A — Isochrone"), (d_b, COLOR_B_V, "B — Gravity")]:
        xs = np.sort(d)
        ys = np.arange(1, len(xs) + 1) / len(xs)
        ax.step(xs, ys, color=color, linewidth=2, label=label, alpha=ALPHA)
    ax.set_xlabel("Razdalja dom–destinacija (km)", fontsize=11)
    ax.set_ylabel("Kumulativna verjetnost", fontsize=11)
    ax.set_title("ECDF razdalje dom–destinacija\n(Velenje)", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Box plot
    ax = axes[1]
    bp = ax.boxplot([d_a, d_b], labels=["A — Isochrone", "B — Gravity"],
                    patch_artist=True, widths=0.5)
    for patch, color in zip(bp["boxes"], [COLOR_A, COLOR_B_V]):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Razdalja (km)", fontsize=11)
    ax.set_title("Razdalja dom–destinacija\n(Velenje, mediana + kvartili)", fontsize=11, fontweight="bold")
    ax.grid(True, axis="y", alpha=0.3)

    fig.suptitle("Razdalja od doma do destinacije: Isochrone vs Gravity  (Velenje)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "ablacija_velenje_razdalja_od_doma.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("✓ ablacija_velenje_razdalja_od_doma.png")


# ── main ─────────────────────────────────────────────────────────────────────

def run():
    print("=== Ablacija: Isochrone (A) vs Gravity (B) — Velenje ===\n")

    print("1. Nalagam A-jeve podatke (Velenje)...")
    homes_gdf, trips_df = load_a_velenje()
    print(f"   Domovi: {len(homes_gdf)}, Potovanja: {len(trips_df)}")

    print("\n2. Pridobivam Velenje OSM podatke...")
    osm_gdf   = fetch_velenje_osm()
    init_data = build_init_data(osm_gdf)

    print("\n3. Vzorčim destinacije z B-jevo metodo (gravity)...")
    b_gravity_df = sample_b_gravity(trips_df, homes_gdf, init_data, seed=42)
    print(f"   → {len(b_gravity_df)} destinacij")
    b_gravity_df.to_csv(os.path.join(MET_DIR, "ablacija_B_gravity_velenje.csv"), index=False)

    # A-jeve destinacije (obstoječe)
    a_iso_df = pd.DataFrame({
        "vehicle_id": trips_df["Vehicle ID"],
        "trip_id":    trips_df["Trip ID"],
        "activity":   trips_df["Trip type"],
        "method":     "A_isochrone",
        "end_lat":    trips_df["end_lat"],
        "end_lon":    trips_df["end_lon"],
    }).reset_index(drop=True)

    print("\n4. Prostorske metrike...")
    met_a = spatial_metrics(
        a_iso_df["end_lat"].values, a_iso_df["end_lon"].values, "A — Isochrone"
    )
    met_b = spatial_metrics(
        b_gravity_df["end_lat"].values, b_gravity_df["end_lon"].values, "B — Gravity"
    )
    met_df = pd.DataFrame([met_a, met_b])
    met_df.to_csv(os.path.join(MET_DIR, "ablacija_prostorske_metrike.csv"), index=False)
    print(met_df.to_string(index=False))

    # Primerjava razdalj od doma
    def dist_from_home_series(df, homes):
        dists = []
        for _, row in df.iterrows():
            vid  = int(row["vehicle_id"])
            home = homes.iloc[(vid - 1) % len(homes)]
            dists.append(haversine(home.geometry.x, home.geometry.y,
                                   float(row["end_lon"]), float(row["end_lat"])))
        return np.array(dists)

    d_a = dist_from_home_series(a_iso_df, homes_gdf)
    d_b = dist_from_home_series(b_gravity_df, homes_gdf)
    from scipy import stats
    ks_stat, ks_p = stats.ks_2samp(d_a, d_b)
    wass = stats.wasserstein_distance(d_a, d_b)
    print(f"\n  Razdalja dom–destinacija:")
    print(f"  A mediana={np.median(d_a):.2f} km, B mediana={np.median(d_b):.2f} km")
    print(f"  KS={ks_stat:.3f}, p={ks_p:.4f}, Wasserstein={wass:.2f} km")

    dist_met = pd.DataFrame([{
        "A_mediana_km": round(np.median(d_a), 2),
        "B_mediana_km": round(np.median(d_b), 2),
        "A_max_km": round(d_a.max(), 2),
        "B_max_km": round(d_b.max(), 2),
        "KS_stat": round(ks_stat, 4),
        "KS_p": round(ks_p, 4),
        "Wasserstein_km": round(wass, 2),
    }])
    dist_met.to_csv(os.path.join(MET_DIR, "ablacija_razdalja_dom_destinacija.csv"), index=False)

    print("\n5. Generiranje grafik...")
    plot_comparison(a_iso_df, b_gravity_df, homes_gdf)
    plot_activity_split(a_iso_df, b_gravity_df)
    plot_distance_from_home(a_iso_df, b_gravity_df, homes_gdf)

    print("\n=== Ablacija končana ===")
    print(f"Grafike: {OUT_DIR}")
    print(f"Metrike: {MET_DIR}")


if __name__ == "__main__":
    run()

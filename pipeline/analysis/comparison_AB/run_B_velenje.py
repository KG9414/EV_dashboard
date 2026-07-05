"""
run_B_velenje.py — Zažene B-jevo pipeline za Velenje.

Vhod:
  - A-jevi domovi (ROS.shp) in parametri potovanj (Step3 Excel)
  - Velenje OSM (pridobljeno z osmnx)

Metoda (v2 — usklajeno s pravo produkcijsko verigo iz Step_2_prod.py):
  - Primarno: ORS isochrone (ors_isochrone_filter) — ista metoda kot Model A
  - Fallback (ko isochrone vrne 0 kandidatov): Haversine-KNN ring
    (haversine_ring_filter_knn) — distance-aware fallback z diagnozo
    too-close/too-far, NE uniformno naključen POI brez omejitve razdalje
  - Zadnji resort (ko tudi fallback ne najde nič): potovanje se izpusti
    (skipped=True), enako kot Step_2_prod.py "Skipping trip"
  - ORS routing za dejanske razdalje (route_parameters)

Prejšnja verzija (v1, glej git history) je uporabljala haversine_ring_filter
neposredno (brez ORS isochrone) in se ob prazni ring vrnitvi zatekla k
popolnoma naključnemu POI kjerkoli v mestu — to je preveč optimistična
ocena B-jeve metode, ki ne ustreza dejanski produkcijski kodi.

Izhod:
  raw_runs/B_velenje/B_velenje_N25_4trips.parquet
"""

import os, sys, time
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../pipeline"))
from Functions_step_2 import (haversine, sample_destination, route_parameters,
                               ors_isochrone_filter, haversine_ring_filter_knn)

A_ROOT  = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/OneDrive_1_2-25-2026"
OUT_DIR = os.path.join(os.path.dirname(__file__), "raw_runs", "B_velenje")
os.makedirs(OUT_DIR, exist_ok=True)

VELENJE_PLACE  = "Velenje, Slovenia"
AVG_SPEED_KMH  = 30
BETA           = 2
SLEEP_BETWEEN_ORS = 0.0  # route_parameters že dela time.sleep(1.5)


# ── 1. Naloži A-jeve vhodne podatke ──────────────────────────────────────────

def load_inputs():
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
    step3 = step3.copy()
    step3["start_lat_A"] = step2["Start location lat"].values
    step3["start_lon_A"] = step2["Start location lon"].values
    return homes, step3


# ── 2. Pridobi Velenje OSM podatke ───────────────────────────────────────────

def fetch_osm():
    print("Pridobivam Velenje OSM podatke...")
    t0 = time.time()
    tags = {"landuse": True, "leisure": True, "amenity": True,
            "building": True, "shop": True}
    gdf = ox.features_from_place(VELENJE_PLACE, tags=tags)
    print(f"  → {len(gdf)} objektov ({time.time()-t0:.1f}s)")
    return gdf


def build_init_data(gdf):
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


# ── 3. Vzorčenje destinacij + ORS routing ────────────────────────────────────

def run_b_velenje(trips_df, homes_gdf, init_data, seed=42):
    np.random.seed(seed)
    records = []
    n_total = len(trips_df)

    for i, (_, row) in enumerate(trips_df.iterrows()):
        vid      = int(row["Vehicle ID"])
        trip_id  = int(row["Trip ID"])
        ttype    = row["Trip type"]
        duration = float(row["Actual duration"]) if pd.notna(row.get("Actual duration")) else 20.0
        start_tp = int(row["Start"]) if pd.notna(row.get("Start")) else 0
        end_tp   = int(row["End"])   if pd.notna(row.get("End"))   else 0

        home_row  = homes_gdf.iloc[(vid - 1) % len(homes_gdf)]
        home_lat  = home_row.geometry.y
        home_lon  = home_row.geometry.x

        # Izhodišče: trip 1 = dom, ostali = konec prejšnjega (ali zadnje veljavne
        # lokacije, če je bilo prejšnje potovanje izpuščeno — glej skipped spodaj)
        if trip_id == 1:
            start_lat, start_lon = home_lat, home_lon
        else:
            prev = [r for r in records if r["vehicle_id"] == vid and r["trip_id"] == trip_id - 1]
            if prev:
                start_lat = prev[-1]["end_lat"]
                start_lon = prev[-1]["end_lon"]
            else:
                start_lat, start_lon = home_lat, home_lon

        # Destinacija — primarno ORS isochrone (ista metoda kot Step_2_prod.py
        # in Model A), fallback na Haversine-KNN ring (distance-aware) šele
        # če isochrone ne vrne kandidatov.
        fallback_used = False
        skipped = False
        try:
            candidates = ors_isochrone_filter(init_data, ttype, start_lat, start_lon, duration)
        except Exception as e:
            print(f"  [isochrone error trip {i+1}/{n_total} v{vid} t{trip_id}]: {e} — poskušam Haversine-KNN")
            candidates = None

        if not candidates:
            duration_ext = min(duration + 10, 60)
            candidates, fallback_used = haversine_ring_filter_knn(
                init_data, ttype, start_lat, start_lon, duration_ext, AVG_SPEED_KMH
            )

        if candidates:
            dest = sample_destination((start_lat, start_lon), candidates, beta=BETA)
            end_lat = dest["coords"][0]
            end_lon = dest["coords"][1]
        else:
            # Zadnji resort: brez kandidatov niti po fallbacku — izpusti potovanje
            # (enako kot Step_2_prod.py "Skipping trip"), NE naključen POI kjerkoli.
            skipped = True
            end_lat, end_lon = start_lat, start_lon

        # ORS routing za dejansko razdaljo
        dist_km = np.nan
        dur_routed = np.nan
        if not skipped:
            try:
                dist_km, dur_routed, _ = route_parameters(start_lat, start_lon, end_lat, end_lon)
                if dist_km == 0:
                    dist_km, dur_routed = np.nan, np.nan
            except Exception as e:
                print(f"  [ORS routing error trip {i+1}/{n_total} v{vid} t{trip_id}]: {e}")

        flags = []
        if fallback_used: flags.append("fallback")
        if skipped: flags.append("SKIPPED")
        print(f"  [{i+1}/{n_total}] v{vid} t{trip_id} {ttype:10s} "
              f"dist={dist_km:.2f}km {flags}")

        records.append({
            "model":             "B_velenje",
            "city":              "Velenje",
            "vehicle_id":        vid,
            "day_type":          row.get("Day Type", "Workday"),
            "trip_id":           trip_id,
            "activity":          ttype,
            "departure_time_h":  start_tp * 15 / 60,
            "arrival_time_h":    end_tp   * 15 / 60,
            "duration_min":      duration,
            "distance_km":       np.nan if skipped else (
                dist_km if not np.isnan(dist_km) else haversine(start_lon, start_lat, end_lon, end_lat)
            ),
            "distance_km_routed": dist_km,
            "duration_min_routed": dur_routed,
            "start_lat":         start_lat,
            "start_lon":         start_lon,
            "end_lat":           end_lat,
            "end_lon":           end_lon,
            "profile":           "unknown",
            "energy_kwh":        np.nan,
            "fallback":          fallback_used,
            "skipped":           skipped,
        })

    return pd.DataFrame(records)


# ── main ─────────────────────────────────────────────────────────────────────

def run():
    print("=== B pipeline za Velenje v2 (ORS isochrone primary + Haversine-KNN fallback) ===\n")

    print("1. Nalagam A-jeve vhodne podatke...")
    homes_gdf, trips_df = load_inputs()
    print(f"   Domovi: {len(homes_gdf)}, Potovanja: {len(trips_df)}")

    print("\n2. Pridobivam Velenje OSM...")
    osm_gdf   = fetch_osm()
    init_data = build_init_data(osm_gdf)

    print(f"\n3. Vzorčim destinacije + ORS routing ({len(trips_df)} potovanj)...")
    df = run_b_velenje(trips_df, homes_gdf, init_data, seed=42)

    out_path = os.path.join(OUT_DIR, "B_velenje_N25_4trips.parquet")
    df.to_parquet(out_path, index=False)
    print(f"\n✓ Shranjeno: {out_path}")
    print(f"  N potovanj: {len(df)}")
    print(f"  ORS isochrone uspel (brez fallbacka): {(~df['fallback'] & ~df['skipped']).sum()}/{len(df)}")
    print(f"  Haversine-KNN fallback uporabljen: {df['fallback'].sum()}/{len(df)}")
    print(f"  Izpuščeno (skipped, brez kandidatov niti po fallbacku): {df['skipped'].sum()}/{len(df)}")
    print(f"  Povp. razdalja (brez skipped): {df['distance_km'].mean():.2f} km")
    print(f"  ORS routing uspešnih: {df['distance_km_routed'].notna().sum()}/{len(df)}")

    # Kratek CSV povzetek
    summary = df.groupby("activity").agg(
        n=("trip_id", "count"),
        dist_mean=("distance_km", "mean"),
        dur_mean=("duration_min", "mean"),
    ).round(2)
    summary.to_csv(os.path.join(OUT_DIR, "B_velenje_aktivnosti_povzetek.csv"))
    print("\nPovzetek po aktivnostih:")
    print(summary)


if __name__ == "__main__":
    run()

"""
run_B_velenje_v2.py — Zažene POSODOBLJENO B-jevo pipeline za Velenje.

Razlika od run_B_velenje.py (prejšnja verzija):
  - Primarna prostorska metoda je ORS izokrone (ors_isochrone_filter), enako
    kot trenutni produkcijski Step_2_prod.py — NE haversine ring.
  - Fallback hierarhija je enaka produkciji: ORS izokrona → haversine ring
    (razširjeno trajanje +10 min) → naključna izbira (zadnji resort).
  - Vse drugo (A-jevi domovi, A-jeva trajanja potovanj, gravitacijski beta=2)
    je nespremenjeno — primerjava A vs B ostaja kontrolirana (ista mesta,
    ista trajanja, edina razlika je metoda izbire destinacije).

Namen: pravična, METODOLOŠKO TRENUTNA primerjava Model A vs Model B na ISTEM
mestu (Velenje), kjer je Golubović (2025) izvedel svojo originalno validacijo.

Izhod:
  raw_runs/B_velenje/B_velenje_v2_N25_4trips.parquet
"""

import os, sys, time
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../pipeline"))
from Functions_step_2 import (haversine, sample_destination, haversine_ring_filter,
                               ors_isochrone_filter, route_parameters)

A_ROOT  = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/OneDrive_1_2-25-2026"
OUT_DIR = os.path.join(os.path.dirname(__file__), "raw_runs", "B_velenje")
os.makedirs(OUT_DIR, exist_ok=True)

VELENJE_PLACE  = "Velenje, Slovenia"
AVG_SPEED_KMH  = 30
BETA           = 2


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


def fetch_osm():
    print("Pridobivam Velenje OSM podatke...")
    t0 = time.time()
    tags = {"landuse": True, "leisure": True, "amenity": True,
            "building": True, "shop": True}
    gdf = ox.features_from_place(VELENJE_PLACE, tags=tags)
    print(f"  -> {len(gdf)} objektov ({time.time()-t0:.1f}s)")
    return gdf


def build_init_data(gdf):
    def _filter(col, values):
        if col not in gdf.columns:
            return gdf.iloc[0:0]
        if values is None:
            return gdf[gdf[col].notna()].copy()
        return gdf[gdf[col].isin(values)].copy()

    work     = _filter("building", {"office", "commercial", "industrial", "retail", "warehouse"})
    business = _filter("building", {"office", "commercial", "industrial", "retail"})
    edu      = _filter("amenity",  {"school", "college", "university", "kindergarten", "music_school"})
    shop     = _filter("shop",     None)
    leisure  = _filter("leisure",  None)
    building = _filter("building", None)

    print(f"  OSM sloji: work={len(work)}, edu={len(edu)}, shop={len(shop)}, "
          f"leisure={len(leisure)}, building={len(building)}")
    return work, business, edu, shop, leisure, building


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

        if trip_id == 1:
            start_lat, start_lon = home_lat, home_lon
        else:
            prev = [r for r in records if r["vehicle_id"] == vid and r["trip_id"] == trip_id - 1]
            if prev:
                start_lat = prev[-1]["end_lat"]
                start_lon = prev[-1]["end_lon"]
            else:
                start_lat, start_lon = home_lat, home_lon

        # --- Destinacija: ORS izokrona (primarno) -> haversine ring (fallback) -> naključno (zadnji resort) ---
        method_used = "ors_isochrone"
        candidates = ors_isochrone_filter(init_data, ttype, start_lat, start_lon, duration)
        if not candidates:
            method_used = "haversine_fallback"
            duration_ext = min(duration + 10, 60)
            candidates = haversine_ring_filter(init_data, ttype, start_lat, start_lon, duration_ext, AVG_SPEED_KMH)

        fallback_used = False
        if not candidates:
            method_used = "random_last_resort"
            fallback_used = True
            type_map = {
                'WORK': init_data[0], 'BUSINESS': init_data[1],
                'EDUCATION': init_data[2], 'SHOPPING': init_data[3],
                'LEISURE': init_data[4],
            }
            cands_gdf = type_map.get(ttype.upper(), init_data[5])
            if cands_gdf.empty:
                cands_gdf = init_data[5]
            row_s = cands_gdf.sample(1).iloc[0]
            pt = row_s.geometry.centroid
            end_lat, end_lon = pt.y, pt.x
        else:
            dest = sample_destination((start_lat, start_lon), candidates, beta=BETA)
            end_lat = dest["coords"][0]
            end_lon = dest["coords"][1]

        dist_km = np.nan
        dur_routed = np.nan
        try:
            dist_km, dur_routed, _ = route_parameters(start_lat, start_lon, end_lat, end_lon)
            if dist_km == 0:
                dist_km, dur_routed = np.nan, np.nan
        except Exception as e:
            print(f"  [ORS error trip {i+1}/{n_total} v{vid} t{trip_id}]: {e}")

        print(f"  [{i+1}/{n_total}] v{vid} t{trip_id} {ttype:10s} method={method_used:18s} "
              f"dist={dist_km:.2f}km")

        records.append({
            "model":             "B_velenje_v2",
            "city":              "Velenje",
            "vehicle_id":        vid,
            "day_type":          row.get("Day Type", "Workday"),
            "trip_id":           trip_id,
            "activity":          ttype,
            "departure_time_h":  start_tp * 15 / 60,
            "arrival_time_h":    end_tp   * 15 / 60,
            "duration_min":      duration,
            "distance_km":       dist_km if not np.isnan(dist_km) else haversine(start_lon, start_lat, end_lon, end_lat),
            "distance_km_routed": dist_km,
            "duration_min_routed": dur_routed,
            "start_lat":         start_lat,
            "start_lon":         start_lon,
            "end_lat":           end_lat,
            "end_lon":           end_lon,
            "profile":           "unknown",
            "energy_kwh":        np.nan,
            "method_used":       method_used,
            "fallback":          fallback_used,
        })

    return pd.DataFrame(records)


def run():
    print("=== B pipeline za Velenje v2 (ORS izokrone, dosledno s Step_2_prod.py) ===\n")

    print("1. Nalagam A-jeve vhodne podatke...")
    homes_gdf, trips_df = load_inputs()
    print(f"   Domovi: {len(homes_gdf)}, Potovanja: {len(trips_df)}")

    print("\n2. Pridobivam Velenje OSM...")
    osm_gdf   = fetch_osm()
    init_data = build_init_data(osm_gdf)

    print(f"\n3. Vzorcim destinacije (ORS izokrone) + ORS routing ({len(trips_df)} potovanj)...")
    df = run_b_velenje(trips_df, homes_gdf, init_data, seed=42)

    out_path = os.path.join(OUT_DIR, "B_velenje_v2_N25_4trips.parquet")
    df.to_parquet(out_path, index=False)
    print(f"\n=== Shranjeno: {out_path} ===")
    print(f"  N potovanj: {len(df)}")
    print(f"  Metoda - ORS izokrona: {(df['method_used']=='ors_isochrone').sum()}")
    print(f"  Metoda - haversine fallback: {(df['method_used']=='haversine_fallback').sum()}")
    print(f"  Metoda - naključno (zadnji resort): {(df['method_used']=='random_last_resort').sum()}")
    print(f"  Povp. razdalja: {df['distance_km'].mean():.2f} km")
    print(f"  ORS routing uspešnih: {df['distance_km_routed'].notna().sum()}/{len(df)}")

    summary = df.groupby("activity").agg(
        n=("trip_id", "count"),
        dist_mean=("distance_km", "mean"),
        dist_std=("distance_km", "std"),
        dur_mean=("duration_min", "mean"),
    ).round(2)
    summary.to_csv(os.path.join(OUT_DIR, "B_velenje_v2_aktivnosti_povzetek.csv"))
    print("\nPovzetek po aktivnostih:")
    print(summary)


if __name__ == "__main__":
    run()

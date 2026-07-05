"""
harmonize.py — load Model A and B outputs, produce a common tidy schema.

Common schema columns:
  model, city, vehicle_id, day_type, trip_id, activity,
  departure_time_h, arrival_time_h, duration_min, distance_km,
  start_lat, start_lon, end_lat, end_lon, profile, energy_kwh
"""

import os
import pandas as pd
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

A_ROOT = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/OneDrive_1_2-25-2026"
B_ROOT = os.path.join(REPO_ROOT, "pipeline")

ENERGY_KWH_PER_KM = 0.18  # imputed for A


def _index_to_hours(idx):
    """Convert 15-min interval index (0–95) to fractional hours (0–24)."""
    return idx * 15 / 60


def load_A_primary():
    """
    N=25, trips=4: joins Step3 (temporal + distance) with Step2 (lat/lon).
    A Step3 has no lat/lon — Step2 rows align 1:1 with Step3 rows.
    """
    step3 = pd.read_excel(
        os.path.join(A_ROOT, "03_Vehicle_parameters",
                     "03_Vehicle_trip_parameters_25_EVs_4_trips_1_days.xlsx")
    )
    step2 = pd.read_excel(
        os.path.join(A_ROOT, "02_Trips", "02_Trips_25_EVs_4_trips_1_days.xlsx")
    )

    # Step2 and Step3 rows correspond 1:1 (same order: vehicle × trip)
    assert len(step3) == len(step2), (
        f"A Step3/Step2 row count mismatch: {len(step3)} vs {len(step2)}"
    )

    df = pd.DataFrame({
        "model":            "A",
        "city":             "Velenje",
        "vehicle_id":       step3["Vehicle ID"],
        "day_type":         step3["Day Type"],
        "trip_id":          step3["Trip ID"],
        "activity":         step3["Trip type"],
        "departure_time_h": _index_to_hours(step3["Start"]),
        "arrival_time_h":   _index_to_hours(step3["End"]),
        "duration_min":     step3["Actual duration"],
        "distance_km":      step3["Actual distance"],
        "start_lat":        step2["Start location lat"].values,
        "start_lon":        step2["Start location lon"].values,
        "end_lat":          step2["End location lat"].values,
        "end_lon":          step2["End location lon"].values,
        "profile":          np.nan,
        "energy_kwh":       step3["Actual distance"] * ENERGY_KWH_PER_KM,
    })
    return df.reset_index(drop=True)


def load_B_primary():
    """N=25, trips=4: B Step3 has all columns including lat/lon."""
    step3 = pd.read_excel(
        os.path.join(B_ROOT, "03_Vehicle_parameters",
                     "03_Vehicle_trip_parameters_25_EVs_4_trips_1_days.xlsx")
    )
    df = pd.DataFrame({
        "model":            "B",
        "city":             "Krško",
        "vehicle_id":       step3["Vehicle ID"],
        "day_type":         step3["Day Type"],
        "trip_id":          step3["Trip ID"],
        "activity":         step3["Trip type"],
        "departure_time_h": _index_to_hours(step3["Start"]),
        "arrival_time_h":   _index_to_hours(step3["End"]),
        "duration_min":     step3["Actual duration"],
        "distance_km":      step3["Actual distance"],
        "start_lat":        step3["Start_lat"],
        "start_lon":        step3["Start_lon"],
        "end_lat":          step3["End_lat"],
        "end_lon":          step3["End_lon"],
        "profile":          step3["Profile"],
        "energy_kwh":       step3["Energy_kWh"],
    })
    return df.reset_index(drop=True)


def load_A_secondary():
    """N=100, trips=4: Step1 only — no actual distances or lat/lon."""
    step1 = pd.read_excel(
        os.path.join(A_ROOT, "01_Trips_parameters_100_EVs_4_trips_1_days.xlsx")
    )
    df = pd.DataFrame({
        "model":            "A",
        "city":             "Velenje",
        "vehicle_id":       step1["Vehicle ID"],
        "day_type":         step1["Day Type"],
        "trip_id":          step1["Trip ID"],
        "activity":         step1["Trip type"],
        "departure_time_h": _index_to_hours(step1["Start"]),
        "arrival_time_h":   _index_to_hours(step1["End"]),
        "duration_min":     step1["Duration"],
        "distance_km":      np.nan,
        "start_lat":        np.nan,
        "start_lon":        np.nan,
        "end_lat":          np.nan,
        "end_lon":          np.nan,
        "profile":          np.nan,
        "energy_kwh":       np.nan,
    })
    return df.reset_index(drop=True)


def load_B_secondary():
    """N=100, trips=2: B Step3."""
    step3 = pd.read_excel(
        os.path.join(B_ROOT, "03_Vehicle_parameters",
                     "03_Vehicle_trip_parameters_100_EVs_2_trips_1_days.xlsx")
    )
    df = pd.DataFrame({
        "model":            "B",
        "city":             "Krško",
        "vehicle_id":       step3["Vehicle ID"],
        "day_type":         step3["Day Type"],
        "trip_id":          step3["Trip ID"],
        "activity":         step3["Trip type"],
        "departure_time_h": _index_to_hours(step3["Start"]),
        "arrival_time_h":   _index_to_hours(step3["End"]),
        "duration_min":     step3["Actual duration"],
        "distance_km":      step3["Actual distance"],
        "start_lat":        step3["Start_lat"],
        "start_lon":        step3["Start_lon"],
        "end_lat":          step3["End_lat"],
        "end_lon":          step3["End_lon"],
        "profile":          step3["Profile"],
        "energy_kwh":       step3["Energy_kWh"],
    })
    return df.reset_index(drop=True)


def load_nhts():
    """Load raw NHTS data for reference overlay."""
    path = os.path.join(B_ROOT, "00_NHTS_data.csv")
    return pd.read_csv(path)


def build_and_save():
    out_dir = os.path.join(os.path.dirname(__file__), "raw_runs")
    os.makedirs(out_dir, exist_ok=True)

    print("Loading A primary (N=25, trips=4)...")
    a_prim = load_A_primary()
    a_prim.to_parquet(os.path.join(out_dir, "A_N25_4trips.parquet"), index=False)
    print(f"  → {len(a_prim)} rows")

    print("Loading B primary (N=25, trips=4)...")
    b_prim = load_B_primary()
    b_prim.to_parquet(os.path.join(out_dir, "B_N25_4trips.parquet"), index=False)
    print(f"  → {len(b_prim)} rows")

    print("Loading A secondary (N=100, trips=4, Step1 only)...")
    a_sec = load_A_secondary()
    a_sec.to_parquet(os.path.join(out_dir, "A_N100_4trips_step1only.parquet"), index=False)
    print(f"  → {len(a_sec)} rows")

    print("Loading B secondary (N=100, trips=2)...")
    b_sec = load_B_secondary()
    b_sec.to_parquet(os.path.join(out_dir, "B_N100_2trips.parquet"), index=False)
    print(f"  → {len(b_sec)} rows")

    # Combined primary dataset
    combined = pd.concat([a_prim, b_prim], ignore_index=True)
    combined.to_parquet(os.path.join(out_dir, "combined_primary.parquet"), index=False)
    print(f"\nCombined primary: {len(combined)} rows total")
    print(combined.groupby("model")[["duration_min", "distance_km"]].describe().round(2))

    return a_prim, b_prim, a_sec, b_sec


if __name__ == "__main__":
    build_and_save()

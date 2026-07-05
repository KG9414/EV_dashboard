"""
Step_4_analysis.py
Upgrade #17 — Spatial concentration of EV activity by zone.

Input : the trip file produced by Step_2_prod.py
        e.g. "02_Trips/02_Trips_1030_EVs_2_trips_1_days.xlsx"
Output: "04_Spatial/spatial_activity_summary.xlsx"
        + console table of top zones by arrivals / energy
"""

import os
import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt

# ── Configuration ───────────────────────────────────────────────────────────
TRIPS_FILE = "02_Trips/02_Trips_1030_EVs_2_trips_1_days.xlsx"  # adjust as needed
GRID_SIZE_KM = 0.5          # spatial resolution of grid cells
OUTPUT_DIR  = "04_Spatial"

# Krško bounding box (WGS-84)
LAT_MIN, LAT_MAX = 45.92, 46.00
LON_MIN, LON_MAX = 15.45, 15.58

# ── Helpers ──────────────────────────────────────────────────────────────────
def haversine(lon1, lat1, lon2, lat2):
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * 6371 * asin(sqrt(a))

def assign_grid_cell(lat, lon, lat_min, lon_min, grid_km):
    """Return (row, col) grid index for a coordinate."""
    row = int(haversine(lon, lat_min, lon, lat) / grid_km)
    col = int(haversine(lon_min, lat, lon, lat) / grid_km)
    return (row, col)

def cell_label(row, col, lat_min, lon_min, grid_km):
    """Human-readable label: approximate centre lat/lon of cell."""
    centre_lat = lat_min + (row + 0.5) * grid_km / 111.0
    centre_lon = lon_min + (col + 0.5) * grid_km / (111.0 * cos(radians(lat_min)))
    return f"{centre_lat:.4f}N, {centre_lon:.4f}E"

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_excel(TRIPS_FILE)

required = ['Start location lat', 'Start location lon',
            'End location lat',   'End location lon',
            'Consumption_kWh',    'Distance']
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing columns in trip file: {missing}")

df = df.dropna(subset=required)

# ── Assign grid cells ────────────────────────────────────────────────────────
df['start_cell'] = df.apply(
    lambda r: assign_grid_cell(r['Start location lat'], r['Start location lon'],
                                LAT_MIN, LON_MIN, GRID_SIZE_KM), axis=1)
df['end_cell'] = df.apply(
    lambda r: assign_grid_cell(r['End location lat'], r['End location lon'],
                                LAT_MIN, LON_MIN, GRID_SIZE_KM), axis=1)

# ── Aggregate ────────────────────────────────────────────────────────────────
departures = (df.groupby('start_cell')
                .agg(departures=('Distance', 'count'),
                     total_distance_km=('Distance', 'sum'))
                .reset_index()
                .rename(columns={'start_cell': 'cell'}))

arrivals = (df.groupby('end_cell')
              .agg(arrivals=('Distance', 'count'),
                   total_energy_kWh=('Consumption_kWh', 'sum'))
              .reset_index()
              .rename(columns={'end_cell': 'cell'}))

summary = pd.merge(departures, arrivals, on='cell', how='outer').fillna(0)
summary['net_flow'] = summary['arrivals'] - summary['departures']
summary['cell_label'] = summary['cell'].apply(
    lambda c: cell_label(c[0], c[1], LAT_MIN, LON_MIN, GRID_SIZE_KM))
summary = summary.sort_values('total_energy_kWh', ascending=False)

# ── Print top 10 ─────────────────────────────────────────────────────────────
print("\n=== TOP 10 ZONES BY ENERGY DEMAND (kWh) ===")
print(summary[['cell_label', 'arrivals', 'departures',
               'net_flow', 'total_energy_kWh']].head(10).to_string(index=False))

# ── Export ───────────────────────────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
out_path = os.path.join(OUTPUT_DIR, "spatial_activity_summary.xlsx")
summary.to_excel(out_path, index=False)
print(f"\nSaved: {out_path}")

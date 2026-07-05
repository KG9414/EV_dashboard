"""
Step_4_prod.py
--------------
Step 4 of the V2G model: given per-trip parameters produced by Step 3,
simulate State-of-Charge (SoC) over the day for each vehicle and compute
positive and negative flexibility at every 15-min interval.

Inputs  : 03_Vehicle_parameters/03_Vehicle_trip_parameters_{N}_EVs_{T}_trips_{D}_days.xlsx
          - Must contain columns: Vehicle ID, Trip ID, Start, End, Energy_kWh
          - Optional: Initial_SoC (one value per vehicle, repeated on its
            trip rows). If missing, a uniform sample in [75, 90] is used.

Outputs : 04_SoC_flexibility/
            04_SoC_flex_{N}_EVs_{T}_trips_{D}_days.xlsx
                Same per-trip rows as input, with four columns appended at
                the end: SoC_at_Start, SoC_at_End, Pos_flex_kWh, Neg_flex_kWh.
            04_SoC_flex_timeseries_{N}_EVs_{T}_trips_{D}_days.xlsx
                Long-format (Time x Vehicle) table for downstream plotting.

"""

import os
import pandas as pd
import numpy as np

from Functions_step_4 import (
    DEFAULT_BATTERY_CAPACITY_KWH,
    build_battery_capacity_array,
    #extract_initial_soc,
    build_energy_per_interval,
    simulate_soc,
    compute_flexibility,
    summarize_per_trip,
    build_timeseries_long,
)


# ------------------------------ Input parameters ------------------------------ #

print('Insert number of vehicles (any):')
number_of_vehicles = int(input())

print('Insert number of trips (2/4):')
number_of_trips = int(input())

print('Insert number of days (1/7):')
number_of_days = int(input())


# ------------------------------ Load trip parameters ------------------------------ #

in_folder = "03_Vehicle_parameters"
in_file   = (f"03_Vehicle_trip_parameters_{number_of_vehicles}_EVs_"
             f"{number_of_trips}_trips_{number_of_days}_days.xlsx")
in_path   = os.path.join(in_folder, in_file)

df = pd.read_excel(in_path)
print(f"Loaded {in_path}: {df.shape[0]} rows, {df.shape[1]} columns")


# ------------------------------ Build simulation inputs ------------------------------ #

# Battery capacity — uniform 72 kWh today, per-vehicle-ready.
# To switch to per-vehicle capacities later, pass an array of length
# number_of_vehicles as `capacity_kwh=...` (see Functions_step_4 docstring).
battery_capacity_kwh = build_battery_capacity_array(
    number_of_vehicles, capacity_kwh=DEFAULT_BATTERY_CAPACITY_KWH
)

# Initial SoC (%), read from the Initial_SoC column in the
# trip-parameters file. Falls back to U[75, 90] if the column is missing.
# KAKŠEN RANGE??? V 1.0 sem dal 65-85, da dobim več fleksibilnosti, ampak je vprašanje, če je to realno.


rng = np.random.default_rng(seed=42)

# OMEJITEV RANGE za SoC
initial_soc_pct = rng.uniform(
    low=60.0,
    high=80.0,
    size=number_of_vehicles,
)

print(f"Initial SoC: min={initial_soc_pct.min():.1f}%  "
      f"max={initial_soc_pct.max():.1f}%  "
      f"mean={initial_soc_pct.mean():.1f}%")      

# Energy drawn from the battery per 15-min interval, per vehicle.
energy_per_interval = build_energy_per_interval(
    df, number_of_vehicles, number_of_trips, number_of_days
)


# ------------------------------ Run simulation ------------------------------ #

soc_matrix = simulate_soc(energy_per_interval,
                          battery_capacity_kwh,
                          initial_soc_pct)

pos_flex, neg_flex = compute_flexibility(soc_matrix, battery_capacity_kwh)


# ------------------------------ Per-trip summary ------------------------------ #

summary = summarize_per_trip(df, soc_matrix, pos_flex, neg_flex,
                             initial_soc_pct,
                             number_of_trips, number_of_days)
df_out = df.copy()
for col, vals in summary.items():
    df_out[col] = vals


# ------------------------------ Export ------------------------------ #

out_folder = "04_SoC_flexibility"
os.makedirs(out_folder, exist_ok=True)

# zaokroževanje na dve decimalki
df_out['SoC_at_Start'] = df_out['SoC_at_Start'].round(2)
df_out['SoC_at_End'] = df_out['SoC_at_End'].round(2)

out_file_per_trip = os.path.join(
    out_folder,
    f"04_SoC_flex_{number_of_vehicles}_EVs_"
    f"{number_of_trips}_trips_{number_of_days}_days.xlsx"
)
df_out.to_excel(out_file_per_trip, index=False)
print(f"Wrote per-trip summary   -> {out_file_per_trip}")

ts_df = build_timeseries_long(soc_matrix, pos_flex, neg_flex)
out_file_timeseries = os.path.join(
    out_folder,
    f"04_SoC_flex_timeseries_{number_of_vehicles}_EVs_"
    f"{number_of_trips}_trips_{number_of_days}_days.xlsx"
)
ts_df.to_excel(out_file_timeseries, index=False)
print(f"Wrote time-series (long) -> {out_file_timeseries}")


# ------------------------------ Sanity prints ------------------------------ #

print("\n=== Sanity check (first vehicle) ===")
print(f"Initial SoC : {initial_soc_pct[0]:8.2f} %")
print(f"Final SoC   : {soc_matrix[0, -1]:8.2f} %")
print(f"SoC range   : {soc_matrix[0].min():8.2f} %  .. {soc_matrix[0].max():8.2f} %")
print(f"Pos_flex    : {pos_flex [0].min():8.2f} kWh .. {pos_flex [0].max():8.2f} kWh")
print(f"Neg_flex    : {neg_flex [0].min():8.2f} kWh .. {neg_flex [0].max():8.2f} kWh")

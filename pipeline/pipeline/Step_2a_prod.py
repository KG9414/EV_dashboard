import os
import pickle
import pandas as pd
import numpy as np
import geopandas as gpd
from Functions_step_2 import (poi_home_search, init, haversine, sample_destination,
                               haversine_ring_filter)

MAX_HOME_RADIUS_KM = 15.0

# ------------------------------ Input parameters ------------------------------ #

print('Insert number of vehicles (any):')
number_of_vehicles = int(input())

print('Insert number of trips (2/4):')
number_of_trips = int(input())

print('Insert number of days (1/7):')
number_of_days = int(input())

print('Do you want to add restriction to the home search? (Yes/No):')
home_search_limit = input()

# ------------------------------ Load trip parameters ------------------------------ #

trip_file_path = f"01_Trips_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"
trip_df = pd.read_excel(trip_file_path)
trip_df['Duration'] = trip_df['Duration'].apply(lambda x: x if x < 60 else 59.9)

# ------------------------------ Load local spatial data (no API calls) ------------------------------ #

area_id = 3601685729
init_data = init(area_id)
center_lon, center_lat = 15.4917, 45.9591

# ------------------------------ Sample home locations ------------------------------ #

residential_objects_no_limit = poi_home_search('building')

residential_objects_no_limit['distance_km'] = residential_objects_no_limit.geometry.apply(
    lambda geom: haversine(geom.x, geom.y, center_lon, center_lat)
)
residential_objects_no_limit = residential_objects_no_limit[
    residential_objects_no_limit['distance_km'] <= MAX_HOME_RADIUS_KM
]

count_before = len(residential_objects_no_limit)

if home_search_limit == 'Yes':
    shp_path = os.path.join("02_Trips",
        f"02_Trips_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days_ROS.shp")
    if os.path.exists(shp_path):
        sampled_home = gpd.read_file(shp_path)
        residential_objects_all = gpd.overlay(residential_objects_no_limit, sampled_home, how='difference')
        print(f"Home restriction applied: {count_before} → {len(residential_objects_all)} candidates")
    else:
        print(f"Warning: restriction file not found at {shp_path}, using full pool.")
        residential_objects_all = residential_objects_no_limit
else:
    residential_objects_all = residential_objects_no_limit

if len(residential_objects_all) == 0:
    raise ValueError("No residential objects found after filtering. Cannot sample homes.")

print(f"Available home candidates: {len(residential_objects_all)}")

residential_objects_sampled = residential_objects_all.sample(n=number_of_vehicles, replace=True)
residential_objects_sampled = residential_objects_sampled.reset_index(drop=True)

# Save homes shapefile
folder_path = "02_Trips"
os.makedirs(folder_path, exist_ok=True)
shp_out = os.path.join(folder_path,
    f"02_Trips_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days_ROS.shp")
residential_objects_sampled.to_file(shp_out, index=False)
print(f"Homes shapefile saved: {shp_out}")

# Build homes dict (vehicle_id is 1-indexed)
homes = {}
for idx, home in residential_objects_sampled.iterrows():
    vehicle_id = idx + 1
    homes[vehicle_id] = {
        'name': f"{home['name']} ({idx})",
        'lat': home.geometry.y,
        'lon': home.geometry.x,
    }

# ------------------------------ Assign permanent work destination per vehicle ------------------------------ #

print(f"\nAssigning work destinations for {number_of_vehicles} vehicles...")

fallback_work = {'name': 'Work_Krsko', 'coords': (45.944111, 15.510083), 'mass': 100.0}
work_assignments = {}

for vehicle_id in range(1, number_of_vehicles + 1):
    home = homes[vehicle_id]
    home_lat, home_lon = home['lat'], home['lon']

    # Use the actual work trip duration from trip_df if available
    vehicle_trips = trip_df[trip_df['Vehicle ID'] == vehicle_id]
    work_trips = vehicle_trips[vehicle_trips['Trip type'] == 'Work']
    work_duration = float(work_trips['Duration'].iloc[0]) if not work_trips.empty else 30.0

    # Search with expanding radius until candidates are found
    candidates = None
    for dur in range(int(work_duration), 60, 5):
        candidates = haversine_ring_filter(init_data, 'Work', home_lat, home_lon, dur)
        if candidates:
            break

    if candidates:
        work_dest = sample_destination((home_lat, home_lon), candidates, beta=2)
        work_assignments[vehicle_id] = work_dest
    else:
        work_assignments[vehicle_id] = fallback_work

    if vehicle_id % 100 == 0:
        print(f"  {vehicle_id}/{number_of_vehicles} vehicles processed...")

fallback_count = sum(1 for w in work_assignments.values() if w['name'] == fallback_work['name'])
print(f"Work destinations assigned: {number_of_vehicles - fallback_count} sampled, {fallback_count} fallback")

# ------------------------------ Save precomp file ------------------------------ #

precomp = {
    'metadata': {
        'number_of_vehicles': number_of_vehicles,
        'number_of_trips': number_of_trips,
        'number_of_days': number_of_days,
    },
    'homes': homes,
    'work_assignments': work_assignments,
}

precomp_path = f"precomp_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.pkl"
with open(precomp_path, 'wb') as f:
    pickle.dump(precomp, f)

unique_homes = len(set((h['lat'], h['lon']) for h in homes.values()))
print(f"\nPre-computation complete.")
print(f"  Vehicles:             {number_of_vehicles}")
print(f"  Unique home locations:{unique_homes}")
print(f"  API calls made:       0")
print(f"  Saved to:             {precomp_path}")
print(f"\nRun Step_2_prod.py next.")

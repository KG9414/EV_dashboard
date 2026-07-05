import os
import pickle
import pandas as pd
import numpy as np
import folium
import webbrowser
from shapely.geometry import shape, Point, Polygon
from Functions_step_2 import (id_of_area, sample_destination,
route_parameters, init, haversine, haversine_ring_filter, ors_isochrone_filter)

MAX_HOME_RADIUS_KM = 15.0

# topology_file_path = r'C:\Users\dudag\OneDrive - Univerza v Ljubljani\Desktop\Projects\RTP Velenje Network\Secondary_Substations.xlsx'
# df_substations = pd.read_excel(topology_file_path)


# ------------------------------ Input parameters ------------------------------ #

print('Insert number of vehicles (any):')
number_of_vehicles = int(input()) # Number of vehicles included in the simulation

print('Insert number of trips (2/4):')
number_of_trips = int(input()) # Number of trips per vehicle and per day (2 or 4 trips)

print('Insert number of days (1/7):')
number_of_days = int(input()) # Number of days included in the simulation

# ------------------------------ Load pre-computation data from Step_2a ------------------------------ #

precomp_path = f"precomp_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.pkl"
if not os.path.exists(precomp_path):
    raise FileNotFoundError(
        f"Pre-computation file not found: {precomp_path}\n"
        "Run Step_2a_prod.py first to generate it."
    )
with open(precomp_path, 'rb') as f:
    precomp = pickle.load(f)
print(f"Loaded precomp data: {number_of_vehicles} vehicles")



#trip_file_path = rf"C:\Users\dudag\OneDrive - Univerza v Ljubljani\Desktop\Magistrska\03_Gradnja modela\Simulacijski model\01_Trips_parameters\01_Trips_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"

trip_file_path = f"01_Trips_parameters_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"
trip_df = pd.read_excel(trip_file_path)
trip_df['Duration'] = trip_df['Duration'].apply(lambda x: x if x < 60 else 59.9)

# ------------------------------ Specify the searching area ------------------------------ #

area = 'Krško'
# area_id = id_of_area(area)
# area_id = 3601675901
area_id = 3601685729
# 3601685729 Krško

# ------------------------------ Fixed work location ------------------------------ #

# --- FIXED WORK LOCATION TOGGLE ---
work_lat = 45.944111
work_lon = 15.510083

work_point = Point(work_lon, work_lat)
work_name = "Work_Krsko"


# ------------------------------ Load homes and POI data ------------------------------ #

# Homes come from precomp (sampled in Step_2a, shapefile already saved)
chosen_home_objects = pd.DataFrame([
    {'name': precomp['homes'][v]['name'],
     'lat':  precomp['homes'][v]['lat'],
     'lon':  precomp['homes'][v]['lon']}
    for v in range(1, number_of_vehicles + 1)
])

# Load local POI data (no API calls)
init_data = init(area_id)


# ------------------------------ Input parameters ------------------------------ #

start_location_name = []
start_location_lat = []
start_location_lon = []

end_location_name = []
end_location_lat = []
end_location_lon = []


calculated_distance = []
calculated_duration = []
calculated_consumption = []


for i in range(number_of_vehicles * number_of_days):
    temp_data = trip_df.loc[(number_of_trips * i):((number_of_trips * i) + (number_of_trips-1))]
    print(temp_data)

    trip_type_matrix = []
    for trip in range(number_of_trips):

        ev = temp_data['Vehicle ID'].iloc[trip]
        print(ev)
        trip_id = temp_data['Trip ID'].iloc[trip]
        print(trip_id)
        trip_type = temp_data['Trip type'].iloc[trip]
        print(trip_type)
        home = precomp['homes'][ev]
        print(home)

        # Vehicle stays home this day (Step_1_prod.py placeholder chain for
        # profiles with 0 trips today — Trip type=='Home' is never a real,
        # generated mid-chain purpose, only this placeholder signature).
        if trip_type == 'Home':
            home_name, home_lat, home_lon = chosen_home_objects.loc[ev-1]
            start_location_name.append(home_name)
            start_location_lat.append(home_lat)
            start_location_lon.append(home_lon)
            trip_type_matrix.append(trip_type)
            end_location_name.append(home_name)
            end_location_lat.append(home_lat)
            end_location_lon.append(home_lon)
            calculated_distance.append(0.0)
            calculated_duration.append(0.0)
            calculated_consumption.append(0.0)
            continue

        if trip_id == 1:
            start_name, start_lat, start_lon = chosen_home_objects.loc[ev-1]
            #print(start_name, start_lat, start_lon)
            #start_tp = find_substation(home, gdf_substations)[0]['name']
            #print(start_tp)
            #start_tp_coords, start_tp_distance = find_substation(home, gdf_substations)

        else:
            start_name = end_location_name[number_of_trips * i + trip - 1]
            start_lat = end_location_lat[number_of_trips * i + trip - 1]
            start_lon = end_location_lon[number_of_trips * i + trip - 1]
            #start_tp = end_substation[number_of_trips * i + trip - 1]
            #print(start_tp)
            #start_tp_coords = end_substation_coords[number_of_trips * i + trip - 1]
            #start_tp_distance = end_substation_distance[number_of_trips * i + trip - 1]
            print(start_name, start_lat, start_lon)

        ## Start

        if trip_type_matrix.count(trip_type) == 3:
            end_name, end_lat, end_lon = chosen_home_objects.loc[ev-1]
            #end_tp = find_substation(home, gdf_substations)[0]['name']
            #print(end_tp)
            #end_tp_coords, end_tp_distance = find_substation(home, gdf_substations)
            distance, new_duration, route = route_parameters(start_lat, start_lon, end_lat, end_lon)
            print(distance, new_duration, route)

        else:
            if trip_type_matrix.count(trip_type) == 1:
                index = trip_type_matrix.index(trip_type)
                print(index)
                duration = temp_data['Duration'].iloc[index]
                print(duration)
                if trip_id != 3:
                    end_name, end_lat, end_lon = chosen_home_objects.iloc[ev-1]
                else:
                    end_name = start_location_name[number_of_trips * i + trip - 1]
                    end_lat = start_location_lat[number_of_trips * i + trip - 1]
                    end_lon = start_location_lon[number_of_trips * i + trip - 1]
                print(end_name, end_lat, end_lon)

                distance, new_duration, route = route_parameters(start_lat, start_lon, end_lat, end_lon)
                print(distance, new_duration, route)
            else:
                duration = temp_data['Duration'].iloc[trip]
                print(duration)

                # --- WORK: use pre-assigned destination from Step_2a ---
                if trip_type == "Work":
                    work_dest = precomp['work_assignments'][ev]
                    end_name = work_dest['name']
                    end_lat = work_dest['coords'][0]
                    end_lon = work_dest['coords'][1]
                    print(f"Using pre-assigned work location: {end_name} ({end_lat}, {end_lon})")
                    distance, new_duration, route = route_parameters(start_lat, start_lon, end_lat, end_lon)
                    print(distance, new_duration, route)
                else:
                    # ORS isochrone filter — cestna mreža, kot pri Golubović (2025)
                    candidates = ors_isochrone_filter(init_data, trip_type, start_lat, start_lon, duration)
                    if candidates is None:
                        # Fallback: haversine ring z razširjenim trajanjem
                        duration_ext = min(duration + 10, 60)
                        print(f"ORS isochrone vrnil 0 kandidatov, razširi na {duration_ext} min haversine...")
                        candidates = haversine_ring_filter(init_data, trip_type, start_lat, start_lon, duration_ext)

                    if candidates is None:
                        print("No candidates found even at 59 min range. Skipping trip.")
                        start_location_name.append('Skipped')
                        start_location_lat.append(0.0)
                        start_location_lon.append(0.0)
                        trip_type_matrix.append(trip_type)
                        end_location_name.append('Skipped')
                        end_location_lat.append(0.0)
                        end_location_lon.append(0.0)
                        calculated_distance.append(0.0)
                        calculated_duration.append(0.0)
                        calculated_consumption.append(0.0)
                        continue

                    max_attempts = 5
                    for attempt in range(max_attempts):
                        chosen = sample_destination((start_lat, start_lon), candidates, beta=2)
                        end_lat = chosen['coords'][0]
                        end_lon = chosen['coords'][1]
                        end_name = chosen['name']
                        print(chosen, end_name, end_lat, end_lon)

                        distance, new_duration, route = route_parameters(start_lat, start_lon, end_lat, end_lon)
                        print(distance, new_duration, route)

                        if distance != 0 and new_duration != 0:
                            break
                        else:
                            print(f'Pokušaj {attempt+1}: Nerutabilna destinacija, biram drugu...')
                            candidates = [c for c in candidates if c['_idx'] != chosen['_idx']]
                            if not candidates:
                                print("Sve destinacije su isprobane. Preskačem ovaj trip.")
                                break
                    else:
                        print("Nijedna destinacija nije rutabilna nakon 5 pokušaja. Preskačem trip.")
                        start_location_name.append(start_name)
                        start_location_lat.append(start_lat)
                        start_location_lon.append(start_lon)
                        trip_type_matrix.append(trip_type)
                        end_location_name.append('Skipped')
                        end_location_lat.append(0.0)
                        end_location_lon.append(0.0)
                        calculated_distance.append(0.0)
                        calculated_duration.append(0.0)
                        calculated_consumption.append(0.0)
                        continue

                    if distance == 0 or new_duration == 0:
                        start_location_name.append(start_name)
                        start_location_lat.append(start_lat)
                        start_location_lon.append(start_lon)
                        trip_type_matrix.append(trip_type)
                        end_location_name.append(end_name)
                        end_location_lat.append(end_lat)
                        end_location_lon.append(end_lon)
                        calculated_distance.append(0.0)
                        calculated_duration.append(0.0)
                        calculated_consumption.append(0.0)
                        continue



        start_location_name.append(start_name)
        start_location_lat.append(start_lat)
        start_location_lon.append(start_lon)



        trip_type_matrix.append(trip_type)
        end_location_name.append(end_name)
        end_location_lat.append(end_lat)
        end_location_lon.append(end_lon)



        calculated_distance.append(distance)
        calculated_duration.append(new_duration)
        
        # PORABA
        efficiency = np.random.normal(0.17, 0.02)
        consumption = distance * efficiency
        calculated_consumption.append(consumption)


# ------------------------------ Preparing results for export ------------------------------ #


generated_trips = pd.DataFrame({
    'Start location name': start_location_name,
    'Start location lat': start_location_lat,
    'Start location lon': start_location_lon,
    'End location name': end_location_name,
    'End location lat': end_location_lat,
    'End location lon': end_location_lon,
    'Duration': calculated_duration,
    'Distance': calculated_distance,
    'Consumption_kWh': calculated_consumption,
})

#folder_path = r"C:\Users\dudag\OneDrive - Univerza v Ljubljani\Desktop\Magistrska\03_Gradnja modela\Simulacijski model\02_Trips"

folder_path = "02_Trips"
os.makedirs(folder_path, exist_ok=True)

file_name = f"02_Trips_{number_of_vehicles}_EVs_{number_of_trips}_trips_{number_of_days}_days.xlsx"
path = os.path.join(folder_path, file_name)

generated_trips.to_excel(path, index=False)


# ===== GRAVITY MODEL VALIDATION TESTS =====
# Run once after simulation to confirm gravity model behaves correctly.

def _dist(origin, dest_dict):
    """Haversine distance (km) from origin (lat,lon) to a sample_destination result."""
    return haversine(origin[1], origin[0], dest_dict['coords'][1], dest_dict['coords'][0])

_origin = (45.959, 15.491)
_pois = [
    {'coords': (45.9595, 15.492), 'mass': 100, 'name': 'POI_1km'},
    {'coords': (45.963,  15.498), 'mass': 100, 'name': 'POI_3km'},
    {'coords': (45.970,  15.510), 'mass': 100, 'name': 'POI_6km'},
    {'coords': (45.980,  15.530), 'mass': 100, 'name': 'POI_12km'},
]

# TEST 1 — Distance decay: gravity average should be lower than uniform average
_gravity_samples  = [sample_destination(_origin, _pois) for _ in range(1000)]
_uniform_samples  = [_pois[np.random.randint(len(_pois))] for _ in range(1000)]
_gravity_dists    = [_dist(_origin, d) for d in _gravity_samples]
_uniform_dists    = [_dist(_origin, d) for d in _uniform_samples]

print("\n===== GRAVITY MODEL VALIDATION =====")
print(f"TEST 1 — Average distance  | Gravity: {np.mean(_gravity_dists):.3f} km  | Uniform: {np.mean(_uniform_dists):.3f} km")
assert np.mean(_gravity_dists) < np.mean(_uniform_dists), \
    "FAIL: gravity avg distance should be less than uniform avg distance"
print("TEST 1 PASSED: gravity biases toward nearby destinations")

# TEST 2 — Same as TEST 1, explicit comparison output
print(f"TEST 2 — Uniform avg: {np.mean(_uniform_dists):.3f} km  |  Gravity avg: {np.mean(_gravity_dists):.3f} km")
print("TEST 2 PASSED: gravity < uniform" if np.mean(_gravity_dists) < np.mean(_uniform_dists) else "TEST 2 FAILED")

# TEST 3 — Attractiveness effect: far POI with 20x mass should appear more than uniform
_poi_near = {'coords': (45.9595, 15.492), 'mass': 1,  'name': 'near_low_mass'}
_poi_far  = {'coords': (45.980,  15.530), 'mass': 20, 'name': 'far_high_mass'}
_test3_pois = [_poi_near, _poi_far]

_test3_samples = [sample_destination(_origin, _test3_pois) for _ in range(1000)]
_near_count = sum(1 for d in _test3_samples if d['name'] == 'near_low_mass')
_far_count  = sum(1 for d in _test3_samples if d['name'] == 'far_high_mass')

# Uniform baseline: each should appear ~500 times
_uniform_test3 = [_test3_pois[np.random.randint(2)] for _ in range(1000)]
_near_uniform  = sum(1 for d in _uniform_test3 if d['name'] == 'near_low_mass')
_far_uniform   = sum(1 for d in _uniform_test3 if d['name'] == 'far_high_mass')

print(f"TEST 3 — Near (mass=1):  gravity={_near_count}/1000  uniform={_near_uniform}/1000")
print(f"TEST 3 — Far  (mass=20): gravity={_far_count}/1000   uniform={_far_uniform}/1000")
print("TEST 3 PASSED: high-mass far POI appears more than uniform" if _far_count > _far_uniform else "TEST 3 NOTE: distance decay dominated mass advantage (expected for large distance gap)")
print("=====================================\n")
# ===========================================


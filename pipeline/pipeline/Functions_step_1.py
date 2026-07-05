import functools
import os
import sys

import pandas as pd
import numpy as np
import geopandas as gpd

import random
import math

# Support both direct-run (cd pipeline && python ...) and package import (from pipeline.X)
sys.path.insert(0, os.path.dirname(__file__))
from spatial_config import get_krsko_boundary, get_krsko_landuse, STATE_TO_LANDUSE_RULE

location_group_map = {
    -9: 'unknown', -8: 'unknown', -7: 'unknown',
    1: 'Home',
    2: 'Work', 3: 'Work', 4: 'Business',
    5: 'Business', 6: 'Transport', 7: 'Transport',
    8: 'Education', 9: 'Education', 10: 'Personal',
    11: 'Shopping', 12: 'Personal', 13: 'Leisure', 14: 'Personal',
    15: 'Leisure', 16: 'Leisure', 17: 'Leisure',
    18: 'Personal', 19: 'Personal', 97: 'Leisure'
}

states = ['Home', 'Work', 'Business', 'Education', 'Shopping', 'Transport', 'Leisure', 'Personal', 'unknown']

_KRSKO_CENTER = (15.4917, 45.9591)


@functools.lru_cache(maxsize=None)
def _compute_centroids_and_masses():
    boundary_4326 = get_krsko_boundary()
    gdf = get_krsko_landuse()

    # Clip features to the municipality boundary so centroids stay inside
    boundary_metric = gpd.GeoSeries([boundary_4326], crs=4326).to_crs(3857).iloc[0]
    gdf_metric = gdf.to_crs(epsg=3857).clip(boundary_metric)

    centroids_result = {}
    raw_masses = {}

    for state in states:
        col, allowed = STATE_TO_LANDUSE_RULE[state]

        if col not in gdf_metric.columns:
            filtered = gdf_metric.iloc[0:0]
        elif allowed is None:
            filtered = gdf_metric[gdf_metric[col].notna()]
        else:
            filtered = gdf_metric[gdf_metric[col].isin(allowed)]

        if filtered.empty:
            centroids_result[state] = _KRSKO_CENTER
            raw_masses[state] = 0.0
            continue

        # Centroid of the union of all matching features
        union = filtered.geometry.unary_union
        centroid_gs = gpd.GeoSeries([union.centroid], crs=3857).to_crs(epsg=4326)
        centroids_result[state] = (centroid_gs.iloc[0].x, centroid_gs.iloc[0].y)

        # Mass = total polygon footprint area in m²
        is_poly = filtered.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
        raw_masses[state] = float(filtered.loc[is_poly, "geometry"].area.sum())

    # Scale so maximum mass = 5000; states with no polygon area fall back to 500
    max_raw = max((m for m in raw_masses.values() if m > 0), default=1.0)
    scale = 5000.0 / max_raw

    masses_result = {}
    for state in states:
        m = raw_masses.get(state, 0.0)
        masses_result[state] = round(m * scale) if m > 0 else 500

    return centroids_result, masses_result


centroids, masses = _compute_centroids_and_masses()

def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance between two points in km."""
    dlon = np.radians(lon2 - lon1)
    dlat = np.radians(lat2 - lat1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371  # Radius of earth in km
    return c * r


def map_location(df):
    return df.map(lambda x: location_group_map.get(int(x), 'unknown') if pd.notna(x) else x)


def string_to_index(value):
    hour, minutes = value.split(':')
    hour = int(hour)
    minutes = int(minutes)
    value_index = 4 * hour + minutes//15
    return value_index


def next_state(interval, state, profiles_df):
    current_states = profiles_df.iloc[:, interval]
    previous_states = profiles_df.iloc[:, interval - 1]

    # Map codes to state strings
    current_states = current_states.apply(lambda x: x if pd.notna(x) and x in states else location_group_map.get(int(float(x)) if pd.notna(x) and str(x).replace('.', '').isdigit() else -9, 'unknown') if pd.notna(x) else 'unknown')
    previous_states = previous_states.apply(lambda x: x if pd.notna(x) and x in states else location_group_map.get(int(float(x)) if pd.notna(x) and str(x).replace('.', '').isdigit() else -9, 'unknown') if pd.notna(x) else 'unknown')

    transition_matrix = pd.DataFrame(0, index=states, columns=states)

    for prev_state, curr_state in zip(previous_states, current_states):
        if prev_state in states and curr_state in states:
            if prev_state == curr_state:
                transition_matrix.loc[prev_state, curr_state] = 0
            else:
                transition_matrix.loc[prev_state, curr_state] += 1

    prob_matrix = transition_matrix.div(transition_matrix.sum(axis=1), axis=0).fillna(0)

    # Apply gravity weighting
    # ALPHA controls blend: 0 = pure Markov, 1 = pure gravity
    ALPHA = 0.3
    MIN_DIST_KM = 0.1  # floor to guard against identical centroids

    lon1, lat1 = centroids[state]
    gravity_weights = {}
    for dest in states:
        if dest == state:
            gravity_weights[dest] = 0.0
        else:
            lon2, lat2 = centroids[dest]
            d = max(haversine(lon1, lat1, lon2, lat2), MIN_DIST_KM)
            gravity_weights[dest] = masses[dest] / d**2

    # Normalise gravity scores into a valid probability distribution
    gw_values = np.array([gravity_weights[dest] for dest in states])
    gw_sum = gw_values.sum()
    gw_probs = gw_values / gw_sum if gw_sum > 0 else np.zeros(len(states))

    # Markov probabilities row for current state
    markov_probs = np.array([
        prob_matrix.loc[state, dest] if dest in prob_matrix.columns else 0.0
        for dest in states
    ])

    # Convex blend: (1-ALPHA)*Markov + ALPHA*Gravity — both components sum to 1
    final_probs = (1 - ALPHA) * markov_probs + ALPHA * gw_probs
    total = final_probs.sum()

    if total > 0:
        probability = pd.Series(final_probs / total, index=states)
        next_trip = np.random.choice(probability.index, p=probability.values)
    else:
        probability = pd.Series(np.zeros(len(states)), index=states)
        next_trip = 'None'

    return probability, next_trip


def value_to_index(value):
    hour = int(value)
    minute = (value - hour)*60
    index = 4*hour + np.ceil(minute/15)
    return index


def sample_departure_time(min_after_previous, previous_end_time, distribution, max_attempts=100, shift_h=0.0):
    attempts = 0
    iteration = 2
    x = np.linspace(0, 23.75, 96)
    rnd_departure_time = min(np.random.choice(x, p=distribution / sum(distribution)) + shift_h, 23.75)

    while not ((rnd_departure_time - previous_end_time) % 24 >= min_after_previous):
        rnd_departure_time = min(np.random.choice(x, p=distribution / sum(distribution)) + shift_h, 23.75)
        print(f'Randomly sampled departure time in {iteration}. iteration: {rnd_departure_time}')
        iteration += 1
        attempts += 1

        if attempts >= max_attempts:
            raise Exception("Previše pokušaja za 4. putovanje – restartujem generaciju")

    return rnd_departure_time


def sample_initial_soc(profile):
    """
    Sample initial State of Charge (SoC) for a vehicle based on driver profile.
    Returns a percentage value. Does NOT simulate charging or depletion.

    Ranges:
        Commuter:     Uniform(30, 70) — charged overnight, departs near-full
        Retired:      Uniform(30, 60) — moderate usage
        Nonccommuter: Uniform(10, 40) — irregular charging habits

    Args:
        profile: object with .name attribute, or plain string

    Returns:
        float: Initial SoC in [0, 100]
    """
    SOC_RANGES = {
        'Commuter':     (83, 87),
        'Retired':      (83, 87),
        'Nonccommuter': (83, 87),
    }
    profile_name = profile.name if hasattr(profile, 'name') else str(profile)
    low, high = SOC_RANGES.get(profile_name, (83, 87))

    soc = random.uniform(low, high)   # npr. 54.745...
    soc = math.ceil(soc) 

    return soc

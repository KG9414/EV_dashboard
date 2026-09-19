"""Local (offline) analogue of Functions_step_2.ors_isochrone_filter.

Replaces the ORS isochrone API with drive-time reachability on the cached
OSMnx road network (cache/krsko_drive.graphml, travel_time from OSMnx edge
speeds). The candidate cascade is kept identical to ors_isochrone_filter:
  1. annular zone [floor(d), ceil(d)] minutes, widened by 1..4 min each side
  2. full upper zone [0, upper] minutes
  3. any building within the upper zone
Candidate masses (footprint area, median for points) are computed the same way.
Each POI is represented by the drive time from the start node to the POI's
nearest road-network node.
"""
import math
import numpy as np
import pandas as pd
import networkx as nx
import osmnx as ox
from Functions_step_2 import _get_krsko_graph

_NODE_CACHE = {}   # id(gdf) -> (nearest node array, centroids, masses)
_SSSP_CACHE = {}   # start node -> {node: seconds}
MAX_WIDEN = 4

# Calibration of OSMnx free-flow travel times to ORS driving times.
# Median ORS/local duration ratio over 3,718 identical OD pairs from the
# ORS-based 10 % runs (1344x2T + 336x4T): 1.644 (IQR 1.41-2.00). ORS mean
# speed 36.2 km/h vs. OSMnx 56.8 km/h. Route distances agree (median
# local/ORS ratio 0.96, r = 0.955), so only time is rescaled.
TIME_FACTOR = 1.644


def _prep(gdf):
    key = id(gdf)
    if key not in _NODE_CACHE:
        G = _get_krsko_graph()
        cent = gpd_centroids(gdf)
        nodes = ox.distance.nearest_nodes(G, cent.x.values, cent.y.values)
        gdf_m = gdf.to_crs(epsg=3857)
        is_poly = gdf_m.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
        areas = gdf_m.geometry.area
        median_mass = float(areas[is_poly].median()) if is_poly.any() else 100.0
        masses = np.where(is_poly.values, areas.values, median_mass).astype(float)
        names = gdf['name'].where(gdf['name'].notna(), 'Unknown').values if 'name' in gdf.columns else np.array(['Unknown'] * len(gdf))
        _NODE_CACHE[key] = (np.asarray(nodes), cent.y.values, cent.x.values, masses, names, list(gdf.index))
    return _NODE_CACHE[key]


def gpd_centroids(gdf):
    geoms = gdf.geometry
    return geoms.apply(lambda g: g if g.geom_type == 'Point' else g.centroid)


def _times_from(start_lat, start_lon):
    G = _get_krsko_graph()
    n = ox.distance.nearest_nodes(G, start_lon, start_lat)
    if n not in _SSSP_CACHE:
        _SSSP_CACHE[n] = nx.single_source_dijkstra_path_length(G, n, cutoff=60 * 60 / TIME_FACTOR + 1, weight='travel_time')
    return _SSSP_CACHE[n]


def _candidates(prep, t_min, lo, hi):
    nodes, lat, lon, masses, names, idx = prep
    sel = np.where((t_min >= lo) & (t_min <= hi))[0]
    return [{'name': names[i], 'coords': (lat[i], lon[i]), 'mass': float(masses[i]), '_idx': idx[i]} for i in sel]


def local_isochrone_filter(init_data, trip_type, start_lat, start_lon, duration_min):
    data_work, data_business, data_education, data_shopping, data_leisure, data_building = init_data
    type_map = {
        'WORK': data_work, 'BUSINESS': data_business, 'EDUCATION': data_education,
        'SHOPPING': data_shopping, 'LEISURE': data_leisure,
        'PERSONAL': data_building, 'TRANSPORT': data_building,
    }
    gdf = type_map.get(trip_type.upper(), data_building)
    if gdf.empty:
        gdf = data_building
    if gdf.empty:
        return None

    d = max(1.0, min(float(duration_min), 60.0))
    lower0, upper0 = math.floor(d), math.ceil(d)
    times = _times_from(start_lat, start_lon)

    prep = _prep(gdf)
    t_min = np.array([times.get(n, np.inf) for n in prep[0]]) * TIME_FACTOR / 60.0

    cands = []
    upper = upper0
    for widen in range(MAX_WIDEN + 1):
        lower = max(0, lower0 - widen)
        upper = min(60, upper0 + widen)
        cands = _candidates(prep, t_min, lower, upper)
        if cands:
            if widen > 0:
                print(f"Annular zone widened by {widen} min for {trip_type} — found {len(cands)} candidates")
            break

    if not cands:
        print(f"Annular zone empty for {trip_type} even after widening ±{MAX_WIDEN} min — trying full upper zone")
        cands = _candidates(prep, t_min, 0, upper)

    if not cands:
        print(f"No typed POI in zone for {trip_type} — using all buildings")
        prep_b = _prep(data_building)
        t_b = np.array([times.get(n, np.inf) for n in prep_b[0]]) * TIME_FACTOR / 60.0
        cands = _candidates(prep_b, t_b, 0, upper)

    return cands if cands else None

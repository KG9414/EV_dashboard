# data_loader.py — Preserved from Krsko-heatmap-v2.py
# All computation logic is unchanged; only global state → pure functions.

import warnings
import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union


# ─── Constants (preserved from Krsko-heatmap-v2) ────────────────────────────

MAX_CHARGER_KW = 11.0
DT_H = 0.25

ZONE_COLORS = {
    "Residential": "#AEC6CF",
    "Commercial":  "#F4A460",
    "Industrial":  "#CD5C5C",
    "Leisure":     "#90EE90",
}

LANDUSE_TO_ZONE = {
    "residential":       "Residential",
    "family_garden":     "Residential",
    "village_green":     "Residential",
    "commercial":        "Commercial",
    "retail":            "Commercial",
    "office":            "Commercial",
    "industrial":        "Industrial",
    "brownfield":        "Industrial",
    "quarry":            "Industrial",
    "landfill":          "Industrial",
    "farmyard":          "Industrial",
    "park":              "Leisure",
    "leisure":           "Leisure",
    "recreation_ground": "Leisure",
    "garden":            "Leisure",
    "pitch":             "Leisure",
    "stadium":           "Leisure",
    "sports_centre":     "Leisure",
    "swimming_pool":     "Leisure",
    "forest":            "Leisure",
    "grassland":         "Leisure",
    "meadow":            "Leisure",
    "orchard":           "Leisure",
    "nature_reserve":    "Leisure",
}

TRIP_TYPE_TO_ZONE = {
    "Work":      "Industrial",
    "Home":      "Residential",
    "Shopping":  "Commercial",
    "Leisure":   "Leisure",
    "Education": "Residential",
    "Business":  "Commercial",
    "Personal":  "Commercial",
    "Transport": "",
    "Driving":   "",
}

TRIP_TYPE_COLORS = {
    "Work":      "#2563EB",
    "Shopping":  "#DC2626",
    "Leisure":   "#16A34A",
    "Education": "#EA580C",
    "Business":  "#7C3AED",
    "Home":      "#374151",
    "Driving":   "#64748B",
}

_ZONE_ORDER = list(ZONE_COLORS.keys())
_ENERGY_ZONE_ORDER = [z for z in _ZONE_ORDER if z != "Transport"]

_BUILDING_TAG_COLOR = {
    "yes":                "#2c7bb6",
    "house":              "#2c7bb6",
    "detached":           "#2c7bb6",
    "semidetached_house": "#2c7bb6",
    "apartments":         "#2c7bb6",
    "residential":        "#2c7bb6",
    "bungalow":           "#2c7bb6",
    "terrace":            "#2c7bb6",
    "dormitory":          "#2c7bb6",
    "farm":               "#2c7bb6",
    "commercial":         "#fdae61",
    "retail":             "#fdae61",
    "office":             "#fdae61",
    "supermarket":        "#fdae61",
    "kiosk":              "#fdae61",
    "hotel":              "#fdae61",
    "industrial":         "#d7191c",
    "warehouse":          "#d7191c",
    "storage_tank":       "#d7191c",
    "factory":            "#d7191c",
    "school":             "#984ea3",
    "university":         "#984ea3",
    "college":            "#984ea3",
    "kindergarten":       "#984ea3",
    "church":             "#bdbdbd",
    "chapel":             "#bdbdbd",
    "cathedral":          "#bdbdbd",
    "monastery":          "#bdbdbd",
    "farm_auxiliary":     "#bdbdbd",
    "shed":               "#bdbdbd",
    "hut":                "#bdbdbd",
    "roof":               "#bdbdbd",
    "garage":             "#bdbdbd",
    "garages":            "#bdbdbd",
    "carport":            "#bdbdbd",
    "parking":            "#bdbdbd",
}
_BUILDING_TAG_COLOR_DEFAULT = "#bdbdbd"
_NEIGHBOURHOOD_BUFFER_M = 50


# ─── GIS data — cached for the app lifetime ──────────────────────────────────

@st.cache_resource(show_spinner="Loading OSM map data...")
def load_gis_data():
    """Fetch OSM clusters, landuse, buildings once and keep in memory."""
    from krsko_osm_clusters import get_krsko_clusters, get_residential_zones
    from spatial_config import get_krsko_landuse

    clusters, landuse_gdf = get_krsko_clusters()
    buildings = get_krsko_landuse({"building": True}).to_crs(3857)

    if "building" in buildings.columns:
        buildings["color"] = (
            buildings["building"]
            .map(_BUILDING_TAG_COLOR)
            .fillna(_BUILDING_TAG_COLOR_DEFAULT)
        )
    else:
        buildings["color"] = _BUILDING_TAG_COLOR_DEFAULT

    zones_by_type = _create_urban_zones(landuse_gdf)

    return {
        "clusters":       clusters,
        "landuse_gdf":    landuse_gdf,
        "buildings":      buildings,
        "zones_by_type":  zones_by_type,
    }


def _create_urban_zones(landuse_gdf):
    """Aggregate OSM landuse polygons into zone types. Preserved from Krsko-heatmap-v2."""
    zones_by_type = {z: {"centroid": None, "radius_m": 0, "areas": []}
                     for z in ZONE_COLORS}

    # Project to EPSG:3857 so centroids are in metres and area is in m²
    lz = landuse_gdf.to_crs(epsg=3857)

    for _, row in lz.iterrows():
        landuse = row.get("landuse") or row.get("leisure") or row.get("amenity")
        if not landuse:
            continue
        zone_type = LANDUSE_TO_ZONE.get(landuse)
        if not zone_type:
            continue
        zones_by_type[zone_type]["areas"].append(row.geometry)

    for zone_type, data in zones_by_type.items():
        if not data["areas"]:
            continue
        union_geom = unary_union(data["areas"])
        centroid = union_geom.centroid
        data["centroid"] = (centroid.x, centroid.y)   # EPSG:3857 metres
        area_m2 = union_geom.area
        data["radius_m"] = np.sqrt(area_m2 / np.pi) if area_m2 > 0 else 500

    return zones_by_type


# ─── Trip data — cached per file pair ────────────────────────────────────────

@st.cache_data(show_spinner="Building matrices from trip data...")
def load_trip_data(file_2trips: str, file_4trips: str, _landuse_gdf):
    """
    Load Excel files and build all matrices and aggregated metrics.
    _landuse_gdf uses underscore prefix → excluded from Streamlit cache key.
    Preserved logic from Krsko-heatmap-v2.py.
    """
    warnings.filterwarnings("ignore")

    df_2 = pd.read_excel(file_2trips)
    df_4 = pd.read_excel(file_4trips)
    df_2.columns = df_2.columns.str.strip()
    df_4.columns = df_4.columns.str.strip()

    max_end = max(int(df_2["End"].max()), int(df_4["End"].max()))
    intervals = max(96, max_end + 1)

    pos2, types2, eng_min2, eng_max2, home2, work_loc2, n2 = _build_matrices(df_2, intervals)
    pos4, types4, eng_min4, eng_max4, home4, work_loc4, n4 = _build_matrices(df_4, intervals)

    soc2      = _build_soc_matrix(df_2, intervals)
    soc4      = _build_soc_matrix(df_4, intervals)
    profiles2 = _get_vehicle_profiles(df_2, n2)
    profiles4 = _get_vehicle_profiles(df_4, n4)

    eng_min_all2, eng_max_all2 = _build_all_parking_eng(df_2, intervals)
    eng_min_all4, eng_max_all4 = _build_all_parking_eng(df_4, intervals)

    e_min2, e_max2 = eng_min2.sum(axis=0), eng_max2.sum(axis=0)
    e_min4, e_max4 = eng_min4.sum(axis=0), eng_max4.sum(axis=0)

    parked2 = np.array([int(np.sum(types2[:, t] == "Work")) for t in range(intervals)])
    parked4 = np.array([int(np.sum(types4[:, t] == "Work")) for t in range(intervals)])
    parked_total = parked2 + parked4
    max_park_tot = int(parked_total.max())

    arr2, dep2 = _compute_work_flow(types2, n2, intervals)
    arr4, dep4 = _compute_work_flow(types4, n4, intervals)
    arr_hist2 = _build_hist(arr2, intervals)
    dep_hist2 = _build_hist(dep2, intervals)
    arr_hist4 = _build_hist(arr4, intervals)
    dep_hist4 = _build_hist(dep4, intervals)
    arr_hist_total = arr_hist2 + arr_hist4
    dep_hist_total = dep_hist2 + dep_hist4

    cum_poz2, cum_neg2 = _build_flex_timeline(df_2, types2, n2, intervals)
    cum_poz4, cum_neg4 = _build_flex_timeline(df_4, types4, n4, intervals)
    cum_poz_total = cum_poz2 + cum_poz4
    cum_neg_total = cum_neg2 + cum_neg4

    trip_chain2 = _get_trip_chain(df_2, vid=1)
    # vid=9 preserved from original (shows all-Home ring when fleet < 9 vehicles)
    trip_chain4 = _get_trip_chain(df_4, vid=9)

    # All individual vehicle chains — used for click-to-show-trip-chain feature
    all_chains_2 = {vid: _get_trip_chain(df_2, vid=vid) for vid in range(1, n2 + 1)}
    all_chains_4 = {vid: _get_trip_chain(df_4, vid=vid) for vid in range(1, n4 + 1)}

    zone_matrix2 = _build_zone_assignment(pos2, types2, n2, intervals, _landuse_gdf)
    zone_matrix4 = _build_zone_assignment(pos4, types4, n4, intervals, _landuse_gdf)
    zone_count2  = _build_zone_count_matrix(zone_matrix2, _ZONE_ORDER, intervals)
    zone_count4  = _build_zone_count_matrix(zone_matrix4, _ZONE_ORDER, intervals)
    zone_count_combined = zone_count2 + zone_count4
    zone_count_max = max(int(zone_count_combined.max()), 1)

    zone_energy2 = _build_zone_energy_matrix(
        zone_matrix2, eng_min_all2, _ENERGY_ZONE_ORDER, intervals
    )
    zone_energy4 = _build_zone_energy_matrix(
        zone_matrix4, eng_min_all4, _ENERGY_ZONE_ORDER, intervals
    )
    zone_energy_combined = zone_energy2 + zone_energy4

    zone_hourly_data = _compute_zone_hourly_data(
        zone_matrix2, zone_matrix4,
        eng_min_all2, eng_min_all4,
        eng_max_all2, eng_max_all4,
        intervals,
    )

    # ── Per-zone flexibility potential (15-min resolution) ────────────────────
    vflex_pos2, vflex_neg2 = _build_vehicle_flex_timeseries(df_2, n2, intervals)
    vflex_pos4, vflex_neg4 = _build_vehicle_flex_timeseries(df_4, n4, intervals)
    zone_flex_pos = (
        _build_zone_flex_matrix(zone_matrix2, vflex_pos2, _ENERGY_ZONE_ORDER, intervals)
        + _build_zone_flex_matrix(zone_matrix4, vflex_pos4, _ENERGY_ZONE_ORDER, intervals)
    )
    zone_flex_neg = (
        _build_zone_flex_matrix(zone_matrix2, vflex_neg2, _ENERGY_ZONE_ORDER, intervals)
        + _build_zone_flex_matrix(zone_matrix4, vflex_neg4, _ENERGY_ZONE_ORDER, intervals)
    )

    # ── Availability filter data: SoC at arrival to each Work parking window,
    # forward-filled across that window (NaN outside Work). Point 1. ──────────
    arrival_soc_at_work2 = _build_arrival_soc_at_work(df_2, intervals)
    arrival_soc_at_work4 = _build_arrival_soc_at_work(df_4, intervals)

    home_gdf, missing_residential_buffers = _validate_home_residential_coverage(
        [home2, home4], _landuse_gdf
    )

    center_lon = float(pd.concat([df_2["Start_lon"], df_4["Start_lon"]]).mean())
    center_lat = float(pd.concat([df_2["Start_lat"], df_4["Start_lat"]]).mean())
    fleet_max  = float((e_max2 + e_max4).max())

    return {
        "intervals":    intervals,
        "n2": n2, "n4": n4, "n_total": n2 + n4,
        "pos2": pos2, "pos4": pos4,
        "types2": types2, "types4": types4,
        "eng_min2": eng_min2, "eng_max2": eng_max2,
        "eng_min4": eng_min4, "eng_max4": eng_max4,
        "e_min2": e_min2, "e_max2": e_max2,
        "e_min4": e_min4, "e_max4": e_max4,
        "parked_total": parked_total, "max_park_tot": max_park_tot,
        "arr_hist2": arr_hist2, "dep_hist2": dep_hist2,
        "arr_hist4": arr_hist4, "dep_hist4": dep_hist4,
        "arr_hist_total": arr_hist_total, "dep_hist_total": dep_hist_total,
        "cum_poz_total": cum_poz_total, "cum_neg_total": cum_neg_total,
        "trip_chain2": trip_chain2, "trip_chain4": trip_chain4,
        "zone_count_combined": zone_count_combined, "zone_count_max": zone_count_max,
        "zone_energy_combined": zone_energy_combined,
        "zone_flex_pos": zone_flex_pos,
        "zone_flex_neg": zone_flex_neg,
        "zone_matrix2": zone_matrix2, "zone_matrix4": zone_matrix4,
        "zone_hourly_data": zone_hourly_data,
        "work_loc": work_loc2,
        "center_lon": center_lon, "center_lat": center_lat,
        "missing_residential_buffers": missing_residential_buffers,
        "fleet_max": fleet_max,
        "all_chains_2": all_chains_2,
        "all_chains_4": all_chains_4,
        "df_2": df_2,
        "df_4": df_4,
        "soc2": soc2,
        "soc4": soc4,
        "profiles2": profiles2,
        "profiles4": profiles4,
        "arrival_soc_at_work2": arrival_soc_at_work2,
        "arrival_soc_at_work4": arrival_soc_at_work4,
    }


# ─── Private helpers (preserved logic from Krsko-heatmap-v2) ─────────────────

def _build_matrices(df, intervals):
    """Build pos, typ, eng_min, eng_max matrices. Preserved from Krsko-heatmap-v2."""
    work_trip     = df[df["Trip type"] == "Work"].iloc[0]
    work_location = (work_trip["End_lon"], work_trip["End_lat"])
    home_locations = (
        df[df["Trip ID"] == 1]
        .groupby("Vehicle ID")[["Start_lon", "Start_lat"]]
        .first()
    )
    nv      = df["Vehicle ID"].nunique()
    pos     = np.zeros((nv, intervals, 2))
    typ     = np.full((nv, intervals), "Home", dtype=object)
    eng_min = np.zeros((nv, intervals))
    eng_max = np.zeros((nv, intervals))

    for vid in range(1, nv + 1):
        vt = df[df["Vehicle ID"] == vid].sort_values("Trip ID").reset_index(drop=True)
        hc = (home_locations.loc[vid]["Start_lon"],
              home_locations.loc[vid]["Start_lat"])
        cc, ct = hc, 0

        # pass 1: build pos / typ
        for idx, trip in vt.iterrows():
            s, e  = int(trip["Start"]), int(trip["End"])
            dc    = (trip["End_lon"], trip["End_lat"])
            ttype = trip["Trip type"]

            pos[vid-1, ct:s, :] = cc
            typ[vid-1, ct:s]    = "Home"

            for t in range(s, e):
                a = (t - s) / (e - s)
                pos[vid-1, t, :] = (
                    cc[0]*(1-a) + dc[0]*a + np.random.normal(0, 0.00005),
                    cc[1]*(1-a) + dc[1]*a + np.random.normal(0, 0.00005),
                )
                typ[vid-1, t] = "Driving"

            pos[vid-1, e, :] = dc
            nt = vt[vt["Trip ID"] > trip["Trip ID"]]
            if not nt.empty:
                ns = int(nt.iloc[0]["Start"])
                pos[vid-1, e:ns, :] = dc
                typ[vid-1, e:ns]    = ttype
                ct = ns
            else:
                ct = e
            cc = dc

        pos[vid-1, ct:, :] = hc
        typ[vid-1, ct:]    = "Home"

        # pass 2: assign charging power at Work parking
        BATTERY_KWH = 72.0
        for idx, trip in vt.iterrows():
            if trip["Trip type"] != "Work":
                continue
            park_start  = int(trip["End"])
            later_trips = vt[vt["Trip ID"] > trip["Trip ID"]]
            if later_trips.empty:
                continue
            park_end       = int(later_trips.iloc[0]["Start"])
            park_dur_steps = max(park_end - park_start, 1)
            park_hours     = park_dur_steps * DT_H
            soc_arrival_pct = float(trip["SoC_at_End"])

            e_min_energy = float(later_trips["Energy_kWh"].sum())
            e_max_energy = max(BATTERY_KWH * (100.0 - soc_arrival_pct) / 100.0, 0.0)

            p_min = e_min_energy / park_hours
            p_max = e_max_energy / park_hours
            if MAX_CHARGER_KW is not None:
                p_min = min(p_min, MAX_CHARGER_KW)
                p_max = min(p_max, MAX_CHARGER_KW)

            typ[vid-1, park_start:park_end] = "Work"
            eng_min[vid-1, park_start:park_end] = p_min
            eng_max[vid-1, park_start:park_end] = p_max

    return pos, typ, eng_min, eng_max, home_locations, work_location, nv


def _build_all_parking_eng(df, intervals):
    """Compute eng_min_all / eng_max_all for every parking window. Preserved."""
    BATTERY_KWH = 72.0
    nv = df["Vehicle ID"].nunique()
    eng_min_all = np.zeros((nv, intervals))
    eng_max_all = np.zeros((nv, intervals))

    for vid in range(1, nv + 1):
        vt = (df[df["Vehicle ID"] == vid]
              .sort_values("Start")
              .reset_index(drop=True))

        for i in range(len(vt)):
            trip       = vt.iloc[i]
            park_start = int(trip["End"])
            park_end   = int(vt.iloc[i + 1]["Start"]) if i + 1 < len(vt) else intervals
            if park_end <= park_start:
                continue
            park_hours      = (park_end - park_start) * DT_H
            soc_arrival_pct = float(trip["SoC_at_End"])
            later           = vt.iloc[i + 1:]
            e_min           = float(later["Energy_kWh"].sum()) if len(later) > 0 else 0.0
            e_max           = max(BATTERY_KWH * (100.0 - soc_arrival_pct) / 100.0, 0.0)
            p_min           = e_min / park_hours
            p_max           = e_max / park_hours
            if MAX_CHARGER_KW is not None:
                p_min = min(p_min, MAX_CHARGER_KW)
                p_max = min(p_max, MAX_CHARGER_KW)
            eng_min_all[vid - 1, park_start:park_end] = p_min
            eng_max_all[vid - 1, park_start:park_end] = p_max

    return eng_min_all, eng_max_all


def _compute_work_flow(typ, nv, intervals):
    arr, dep = [], []
    for v in range(nv):
        for t in range(1, intervals):
            if typ[v, t-1] == "Driving" and typ[v, t] == "Work":
                arr.append(t * 0.25)
            if typ[v, t-1] == "Work" and typ[v, t] == "Driving":
                dep.append(t * 0.25)
    return arr, dep


def _build_hist(hours, intervals):
    h = np.zeros(intervals)
    for hr in hours:
        idx = int(hr / 0.25)
        if 0 <= idx < intervals:
            h[idx] += 1
    return h


def _build_flex_timeline(df, types, nv, intervals):
    """Build fleet flexibility timelines. Preserved from Krsko-heatmap-v2."""
    poz_delta = np.zeros(intervals + 1)
    neg_delta = np.zeros(intervals + 1)

    for vid in range(1, nv + 1):
        vt = (df[df["Vehicle ID"] == vid]
              .sort_values(["Start", "End", "Trip ID"])
              .reset_index(drop=True))

        for _, trip in vt.iterrows():
            if trip["Trip type"] != "Work":
                continue
            park_start  = int(trip["End"])
            later_trips = vt[vt["Start"] > trip["End"]]
            if later_trips.empty:
                continue
            park_end = int(later_trips.iloc[0]["Start"])
            if park_end <= park_start:
                continue
            park_hours = (park_end - park_start) * DT_H

            pos_flex_kw = abs(float(trip["Pos_flex_kWh"])) / park_hours
            neg_flex_kw = abs(float(trip["Neg_flex_kWh"])) / park_hours
            if MAX_CHARGER_KW is not None:
                pos_flex_kw = min(pos_flex_kw, MAX_CHARGER_KW)
                neg_flex_kw = min(neg_flex_kw, MAX_CHARGER_KW)

            poz_delta[park_start] += pos_flex_kw
            poz_delta[park_end]   -= pos_flex_kw
            neg_delta[park_start] += neg_flex_kw
            neg_delta[park_end]   -= neg_flex_kw

    return (
        np.cumsum(poz_delta)[:intervals],
        np.cumsum(neg_delta)[:intervals],
    )


def _build_vehicle_flex_timeseries(df, nv, intervals):
    """Per-vehicle positive and negative flexibility (kW) at each 15-min timestep.

    Positive flex = charging headroom (vehicle can absorb more power → V1G / smart charging).
    Negative flex = discharge potential (vehicle can export power → V2G).

    Returns two arrays of shape (nv, intervals).
    """
    pos_flex = np.zeros((nv, intervals))
    neg_flex = np.zeros((nv, intervals))

    for vid in range(1, nv + 1):
        vt = (df[df["Vehicle ID"] == vid]
              .sort_values(["Start", "End", "Trip ID"])
              .reset_index(drop=True))

        for _, trip in vt.iterrows():
            if trip["Trip type"] != "Work":
                continue
            park_start = int(trip["End"])
            later = vt[vt["Start"] > trip["End"]]
            if later.empty:
                continue
            park_end = int(later.iloc[0]["Start"])
            if park_end <= park_start:
                continue
            park_end = min(park_end, intervals)

            park_hours = (park_end - park_start) * DT_H
            if park_hours <= 0:
                continue

            pf_kw = abs(float(trip["Pos_flex_kWh"])) / park_hours
            nf_kw = abs(float(trip["Neg_flex_kWh"])) / park_hours
            if MAX_CHARGER_KW is not None:
                pf_kw = min(pf_kw, MAX_CHARGER_KW)
                nf_kw = min(nf_kw, MAX_CHARGER_KW)

            v_idx = vid - 1
            pos_flex[v_idx, park_start:park_end] += pf_kw
            neg_flex[v_idx, park_start:park_end] += nf_kw

    return pos_flex, neg_flex


def _build_zone_flex_matrix(zone_matrix, flex_per_vehicle, zone_order, intervals):
    """Aggregate per-vehicle flex (kW) by zone → shape (n_zones, intervals)."""
    zm  = np.asarray(zone_matrix, dtype=object)
    fm  = np.asarray(flex_per_vehicle, dtype=float)
    out = np.zeros((len(zone_order), intervals), dtype=float)
    for zi, zone in enumerate(zone_order):
        mask    = (zm == zone)
        out[zi] = (fm * mask).sum(axis=0)
    return out


def _build_arrival_soc_at_work(df, intervals):
    """SoC (%) at the moment a vehicle arrives at a Work parking window,
    forward-filled across that whole window (NaN outside Work windows).

    Uses the same Work-window definition as `_build_all_parking_eng` /
    `_build_vehicle_flex_timeseries` (Trip type == 'Work', window =
    [trip End, next trip Start)), so the availability filter (point 1) lines
    up with the flexibility figures already shown elsewhere.
    """
    nv = df["Vehicle ID"].nunique()
    arrival_soc = np.full((nv, intervals), np.nan)

    for vid in range(1, nv + 1):
        vt = (df[df["Vehicle ID"] == vid]
              .sort_values(["Start", "End", "Trip ID"])
              .reset_index(drop=True))

        for i in range(len(vt)):
            trip = vt.iloc[i]
            if trip["Trip type"] != "Work":
                continue
            park_start = int(trip["End"])
            later = vt[vt["Start"] > trip["End"]]
            if later.empty:
                continue
            park_end = int(later.iloc[0]["Start"])
            if park_end <= park_start:
                continue
            park_end = min(park_end, intervals)

            arrival_soc[vid - 1, park_start:park_end] = float(trip["SoC_at_End"])

    return arrival_soc


# ─── Zone flex/demand traffic-light signal (point 3) ─────────────────────────

SIGNAL_RED_MAX   = 0.8
SIGNAL_GREEN_MIN = 1.2

SIGNAL_COLORS = {
    "red":    [220, 38, 38, 220],
    "yellow": [245, 158, 11, 220],
    "green":  [22, 163, 74, 220],
}


def compute_zone_signal(data):
    """Per-zone, per-timestep flex/demand traffic-light signal.

    ratio = zone_flex_pos[zone, t] (kW, instantaneous positive/V1G headroom)
            / zone demand (kW at that timestep).

    `zone_energy_combined` is stored as kWh accumulated over each 15-min step
    (kW * DT_H), so it is divided back by DT_H here to recover kW before the
    ratio is taken — otherwise the two quantities are not comparable.

    ratio >= 1.2       -> "green"  (ample headroom vs. demand)
    0.8 <= ratio < 1.2 -> "yellow" (roughly balanced)
    ratio < 0.8        -> "red"    (headroom falls short of demand)
    Zero demand at that zone/timestep -> ratio = +inf -> "green" (no risk).

    Returns: dict zone -> {"ratio": np.ndarray(intervals), "signal": np.ndarray(intervals, dtype=object)}
    """
    zone_flex_pos = data["zone_flex_pos"]
    demand_kw = data["zone_energy_combined"] / DT_H

    out = {}
    for zi, zone in enumerate(_ENERGY_ZONE_ORDER):
        flex = zone_flex_pos[zi]
        dem = demand_kw[zi]
        ratio = np.where(dem > 1e-9, flex / np.maximum(dem, 1e-9), np.inf)

        signal = np.full(ratio.shape, "yellow", dtype=object)
        signal[ratio >= SIGNAL_GREEN_MIN] = "green"
        signal[ratio < SIGNAL_RED_MAX] = "red"

        out[zone] = {"ratio": ratio, "signal": signal}
    return out


def _get_trip_chain(df, vid=1):
    vt = df[df["Vehicle ID"] == vid].sort_values(["Start", "End", "Trip ID"])
    return [
        {"start": row["Start"] * 0.25, "end": row["End"] * 0.25, "type": row["Trip type"]}
        for _, row in vt.iterrows()
    ]


def _build_zone_assignment(pos, typ_matrix, nv, intervals, landuse_gdf):
    """Assign each vehicle/timestep to a zone. Preserved from Krsko-heatmap-v2."""
    lz = landuse_gdf.copy()
    lz["zone_type"] = lz.apply(
        lambda r: LANDUSE_TO_ZONE.get(
            r.get("landuse") or r.get("leisure") or r.get("amenity"), ""
        ),
        axis=1,
    )
    lz = lz[lz["zone_type"] != ""][["zone_type", "geometry"]].reset_index(drop=True)

    if lz.empty:
        zone_spatial = np.full((nv, intervals), "", dtype=object)
    else:
        pos_flat = pos.reshape(-1, 2)
        gdf_pts  = gpd.GeoDataFrame(
            {"flat_idx": np.arange(len(pos_flat))},
            geometry=[Point(lon, lat) for lon, lat in pos_flat],
            crs="EPSG:4326",
        ).to_crs(lz.crs)

        joined = gpd.sjoin(gdf_pts, lz, how="left", predicate="within")
        joined = joined[~joined.index.duplicated(keep="first")]

        zone_spatial = (
            joined.set_index("flat_idx")["zone_type"]
            .reindex(np.arange(len(pos_flat)))
            .fillna("")
            .to_numpy(dtype=object)
            .reshape(nv, intervals)
        )

    unmatched = zone_spatial == ""
    if unmatched.any():
        fallback = np.vectorize(lambda t: TRIP_TYPE_TO_ZONE.get(t, ""))(typ_matrix)
        zone_spatial[unmatched] = fallback[unmatched]

    work_mask = (np.asarray(typ_matrix, dtype=object) == "Work")
    if work_mask.any():
        zone_spatial[work_mask] = TRIP_TYPE_TO_ZONE["Work"]

    return zone_spatial


def _build_zone_count_matrix(zone_matrix, zone_order, intervals):
    zm    = np.asarray(zone_matrix, dtype=object)
    count = np.zeros((len(zone_order), intervals), dtype=int)
    for zi, zone in enumerate(zone_order):
        count[zi] = np.sum(zm == zone, axis=0)
    return count


def _build_zone_energy_matrix(zone_matrix, eng_min, zone_order, intervals):
    zm     = np.asarray(zone_matrix, dtype=object)
    em     = np.asarray(eng_min, dtype=float)
    energy = np.zeros((len(zone_order), intervals), dtype=float)
    for zi, zone in enumerate(zone_order):
        mask = (zm == zone)
        energy[zi] = (em * mask).sum(axis=0) * DT_H
    return energy


def _compute_zone_hourly_data(
    zone_matrix2, zone_matrix4,
    eng_min_all2, eng_min_all4,
    eng_max_all2, eng_max_all4,
    intervals,
):
    """Aggregate per-zone metrics by hour. Preserved from Krsko-heatmap-v2."""
    zone_all = np.concatenate([zone_matrix2, zone_matrix4], axis=0)
    neg_all  = np.concatenate([eng_min_all2, eng_min_all4], axis=0) * DT_H
    pos_all  = np.concatenate([
        np.maximum(eng_max_all2 - eng_min_all2, 0.0),
        np.maximum(eng_max_all4 - eng_min_all4, 0.0),
    ], axis=0) * DT_H

    t_hours = (np.arange(intervals) * 15) // 60

    rows = []
    for zone in _ZONE_ORDER:
        zmask = (zone_all == zone)
        for h in range(24):
            tmask   = (t_hours == h)
            n_steps = int(tmask.sum())
            neg_sum = float((neg_all * zmask)[:, tmask].sum())
            pos_sum = float((pos_all * zmask)[:, tmask].sum())
            n_veh   = float(zmask[:, tmask].sum()) / n_steps if n_steps > 0 else 0.0
            rows.append({"Hour": h, "Zone": zone,
                         "Total_Neg_flex": neg_sum,
                         "Total_Pos_flex": pos_sum,
                         "NumVehicles":    n_veh})
    return pd.DataFrame(rows)


def _build_soc_matrix(df, intervals):
    """SoC (%) at each 15-min interval per vehicle (nv × intervals)."""
    nv = df["Vehicle ID"].nunique()
    soc = np.full((nv, intervals), 100.0)
    has_soc_start = "SoC_at_Start" in df.columns

    for vid in range(1, nv + 1):
        vt = df[df["Vehicle ID"] == vid].sort_values("Trip ID").reset_index(drop=True)
        if vt.empty:
            continue

        first_row = vt.iloc[0]
        if has_soc_start and not pd.isna(first_row["SoC_at_Start"]):
            init_soc = float(first_row["SoC_at_Start"])
        elif "Initial_SoC" in df.columns:
            init_soc = float(first_row["Initial_SoC"])
        else:
            init_soc = 100.0

        soc[vid-1, :] = init_soc
        prev_end_soc = init_soc

        for i in range(len(vt)):
            row = vt.iloc[i]
            s = int(row["Start"])
            e = int(row["End"])
            soc_e = float(row["SoC_at_End"])
            soc_s = (float(row["SoC_at_Start"])
                     if has_soc_start and not pd.isna(row["SoC_at_Start"])
                     else prev_end_soc)

            s_c = min(s, intervals - 1)
            e_c = min(e, intervals - 1)
            dur = max(e - s, 1)

            if e_c > s_c:
                tt = np.arange(s_c, e_c + 1)
                soc[vid-1, s_c:e_c + 1] = soc_s + (tt - s) / dur * (soc_e - soc_s)
            elif e_c == s_c:
                soc[vid-1, s_c] = soc_e

            park_end_c = min(
                int(vt.iloc[i + 1]["Start"]) if i + 1 < len(vt) else intervals,
                intervals
            )
            if park_end_c > e_c + 1:
                soc[vid-1, e_c + 1:park_end_c] = soc_e

            prev_end_soc = soc_e

        final_e = min(int(vt.iloc[-1]["End"]), intervals - 1)
        soc[vid-1, final_e:] = float(vt.iloc[-1]["SoC_at_End"])

    return soc


def _get_vehicle_profiles(df, nv):
    """Profile label per vehicle (1-indexed) → list[str] (0-indexed)."""
    if "Profile" not in df.columns:
        return ["Unknown"] * nv
    out = []
    for vid in range(1, nv + 1):
        vt = df[df["Vehicle ID"] == vid]
        out.append(str(vt.iloc[0]["Profile"]) if not vt.empty else "Unknown")
    return out


def _validate_home_residential_coverage(home_dataframes, landuse_gdf, buffer_m=50):
    """Validate home location coverage. Preserved from Krsko-heatmap-v2."""
    from krsko_osm_clusters import get_residential_zones

    home_df  = pd.concat(home_dataframes).reset_index()
    home_gdf = gpd.GeoDataFrame(
        home_df,
        geometry=gpd.points_from_xy(home_df["Start_lon"], home_df["Start_lat"]),
        crs="EPSG:4326",
    ).to_crs(epsg=3857)

    residential_zones = get_residential_zones(landuse_gdf, target_crs=3857, merge_buffer=10.0)
    try:
        residential_union = residential_zones.union_all() if not residential_zones.empty else None
    except AttributeError:
        residential_union = residential_zones.unary_union if not residential_zones.empty else None

    inside = home_gdf.geometry.apply(
        lambda p: p.within(residential_union) if residential_union is not None else False
    )
    missing = home_gdf[~inside]

    if missing.empty:
        return home_gdf, gpd.GeoDataFrame(geometry=[], crs=home_gdf.crs)

    missing_buffer = gpd.GeoDataFrame(
        geometry=missing.geometry.buffer(buffer_m),
        crs=home_gdf.crs,
    )
    return home_gdf, missing_buffer

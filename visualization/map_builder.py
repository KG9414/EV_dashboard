# map_builder.py — deck.gl map for the Streamlit dashboard
#
# Static GIS layers (buildings, neighbourhood fills) are pre-computed once
# and cached.  All 96 animation frames are serialised to JSON and embedded
# directly inside an HTML string passed to st.components.v1.html() — no file
# serving, no component registry, no caching possible.

import json
import hashlib
from pathlib import Path

import numpy as np
import geopandas as gpd
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components
from shapely.geometry import Point

from data_loader import (
    ZONE_COLORS, TRIP_TYPE_COLORS, _NEIGHBOURHOOD_BUFFER_M,
    compute_zone_signal, SIGNAL_COLORS, _ENERGY_ZONE_ORDER, _ZONE_ORDER,
)


def _soc_color(soc_val: float):
    """Map SoC percentage to an RGBA colour (red → amber → blue → green)."""
    if soc_val < 20:
        return [220, 38, 38, 230]
    elif soc_val < 50:
        return [245, 158, 11, 230]
    elif soc_val < 80:
        return [59, 130, 246, 230]
    return [22, 163, 74, 230]


def _hex_to_rgba(hex_color: str, alpha: int = 255):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return [r, g, b, alpha]


def _polygon_rings(geom):
    """Yield exterior coordinate rings (lon, lat) for a Polygon/MultiPolygon."""
    if geom is None or geom.is_empty:
        return
    geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for g in geoms:
        yield [list(c) for c in g.exterior.coords]


# ─── Pre-compute static layers (cached once per GIS load) ────────────────────

@st.cache_resource
def get_static_layers(_gis_data):
    """
    Convert static GIS layers to pydeck-ready polygon/point records.
    Called once; _gis_data uses underscore prefix to skip Streamlit hashing.
    """
    buildings     = _gis_data["buildings"]       # EPSG:3857
    zones_by_type = _gis_data["zones_by_type"]   # centroids in EPSG:3857

    # ── Neighbourhood fill (buffer + dissolve per color) ──────────────────────
    neigh_records = []
    zone_colors_to_fill = [c for c in buildings["color"].unique() if c != "#bdbdbd"]
    for zcolor in zone_colors_to_fill:
        subset = buildings[buildings["color"] == zcolor]
        if subset.empty:
            continue
        buffered = subset.geometry.buffer(_NEIGHBOURHOOD_BUFFER_M)
        try:
            dissolved = buffered.union_all()
        except AttributeError:
            dissolved = buffered.unary_union
        gdf_tmp = gpd.GeoDataFrame(geometry=[dissolved], crs=buildings.crs).to_crs(4326)
        fill = _hex_to_rgba(zcolor, 46)  # ~0.18 opacity
        for geom in gdf_tmp.geometry:
            for ring in _polygon_rings(geom):
                neigh_records.append({"polygon": ring, "fill_color": fill})

    # ── Individual building footprints ────────────────────────────────────────
    bld_wgs84 = buildings.to_crs(4326)
    bld_records = []
    bld_point_records = []
    for _, row in bld_wgs84.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        fill = _hex_to_rgba(row["color"], 153)  # ~0.60 opacity
        if geom.geom_type == "Point":
            bld_point_records.append({"position": [geom.x, geom.y], "fill_color": fill})
        else:
            for ring in _polygon_rings(geom):
                bld_records.append({"polygon": ring, "fill_color": fill})

    # ── Zone centroids — convert centroid from EPSG:3857 → WGS84 ─────────────
    zone_circles = {}
    for zone_type, zone_data in zones_by_type.items():
        if zone_data["centroid"] is None:
            continue
        cx_m, cy_m = zone_data["centroid"]
        pt_wgs = gpd.GeoSeries([Point(cx_m, cy_m)], crs="EPSG:3857").to_crs(4326).iloc[0]
        radius_m = zone_data["radius_m"] * 0.8
        zone_circles[zone_type] = {"lat": pt_wgs.y, "lon": pt_wgs.x, "radius_m": radius_m}

    neigh_layer = pdk.Layer(
        "PolygonLayer", data=neigh_records,
        get_polygon="polygon", get_fill_color="fill_color",
        stroked=False, pickable=False,
    )
    bld_layer = pdk.Layer(
        "PolygonLayer", data=bld_records,
        get_polygon="polygon", get_fill_color="fill_color",
        stroked=False, pickable=False,
    )
    bld_point_layer = pdk.Layer(
        "ScatterplotLayer", data=bld_point_records,
        get_position="position", get_radius=6, radius_min_pixels=2,
        get_fill_color="fill_color", stroked=False, pickable=False,
    )

    return {
        # pydeck layers (used by build_pydeck_map fallback)
        "neigh_layer":        neigh_layer,
        "bld_layer":          bld_layer,
        "bld_point_layer":    bld_point_layer,
        "zone_circles":       zone_circles,
        # raw records for the JS component
        "raw": {
            "neigh":    neigh_records,
            "bld":      bld_records,
            "bld_pts":  bld_point_records,
        },
    }


# ─── Build pydeck Deck for a given time step ──────────────────────────────────

def build_pydeck_map(gis_data, data, t, map_height=600, vis2=None, vis4=None,
                     view_state=None, show_3d=False, col_mode="occ", columns=None):
    """
    Build and return a pydeck.Deck for time step t.

    Static layers are pre-built and cached (see get_static_layers); only the
    vehicle scatter, zone-signal dots and (optional) 3D columns are rebuilt per
    frame — cheap data diffs, no map/DOM teardown.

    This is the single-frame renderer used by the server-rendered map: Python's
    clock (``st.session_state.t_idx``) picks ``t`` and the same frame drives the
    charts/KPIs, so map and analytics share one clock.

    Parameters
    ----------
    view_state : dict | pdk.ViewState | None
        Camera. If a dict, must hold latitude/longitude/zoom (+ optional
        pitch/bearing). Driven by the on-map pan/zoom buttons via session_state.
    show_3d : bool
        When True, add extruded per-zone ColumnLayer and tilt the camera.
    col_mode : {"occ", "dem"}
        Column height metric: vehicle occupancy or charging demand.
    columns : dict | None
        Pre-computed column payload from ``_build_columns`` (cached by the
        caller so the k-means home clustering isn't redone every animation tick).
    """
    static = get_static_layers(gis_data)

    # ── Missing residential buffers (home location validation) ────────────────
    layers = [static["neigh_layer"], static["bld_layer"], static["bld_point_layer"]]

    missing = data.get("missing_residential_buffers")
    if missing is not None and not missing.empty:
        missing_wgs = missing.to_crs(4326)
        missing_records = []
        for geom in missing_wgs.geometry:
            for ring in _polygon_rings(geom):
                missing_records.append({"polygon": ring, "fill_color": [174, 198, 207, 56]})
        if missing_records:
            layers.append(pdk.Layer(
                "PolygonLayer", data=missing_records,
                get_polygon="polygon", get_fill_color="fill_color",
                stroked=False, pickable=False,
            ))

    # ── Vehicle scatter ────────────────────────────────────────────────────────
    pos2, pos4       = data["pos2"], data["pos4"]
    types2, types4   = data["types2"], data["types4"]
    soc2, soc4       = data.get("soc2"), data.get("soc4")
    profiles2        = data.get("profiles2", [])
    profiles4        = data.get("profiles4", [])
    t_s              = min(t, data["intervals"] - 1)

    vehicle_records = []
    for v in range(data["n2"]):
        if vis2 is not None and not vis2[v]:
            continue
        lon, lat = float(pos2[v, t_s, 0]), float(pos2[v, t_s, 1])
        vtype    = types2[v, t_s]
        soc_val  = float(soc2[v, t_s]) if soc2 is not None else None
        profile  = profiles2[v] if profiles2 else "?"
        color    = _soc_color(soc_val) if soc_val is not None else _hex_to_rgba(TRIP_TYPE_COLORS.get(vtype, "#64748B"))
        tip = (f"2-trip V{v + 1}: {vtype} | {profile} | SoC {soc_val:.0f}%"
               if soc_val is not None else f"2-trip V{v + 1}: {vtype}")
        vehicle_records.append({
            "position": [lon, lat], "fill_color": color, "radius": 30,
            "trip_class": 2, "vid": v + 1, "tooltip": tip,
        })

    for v in range(data["n4"]):
        if vis4 is not None and not vis4[v]:
            continue
        lon, lat = float(pos4[v, t_s, 0]), float(pos4[v, t_s, 1])
        vtype    = types4[v, t_s]
        soc_val  = float(soc4[v, t_s]) if soc4 is not None else None
        profile  = profiles4[v] if profiles4 else "?"
        color    = _soc_color(soc_val) if soc_val is not None else _hex_to_rgba(TRIP_TYPE_COLORS.get(vtype, "#64748B"))
        tip = (f"4-trip V{v + 1}: {vtype} | {profile} | SoC {soc_val:.0f}%"
               if soc_val is not None else f"4-trip V{v + 1}: {vtype}")
        vehicle_records.append({
            "position": [lon, lat], "fill_color": color, "radius": 30,
            "trip_class": 4, "vid": v + 1, "tooltip": tip,
        })

    layers.append(pdk.Layer(
        "ScatterplotLayer", data=vehicle_records,
        get_position="position", get_radius="radius",
        radius_min_pixels=5,
        get_fill_color="fill_color", get_line_color=[255, 255, 255, 200],
        line_width_min_pixels=1, stroked=True, pickable=True, id="vehicles",
    ))

    # ── Zone flex/demand traffic-light signal (point 3) ───────────────────────
    zone_circles = static["zone_circles"]
    signal_data = compute_zone_signal(data)
    signal_records = []
    for zone in _ENERGY_ZONE_ORDER:
        zc = zone_circles.get(zone)
        if zc is None:
            continue
        sig = signal_data[zone]["signal"][t_s]
        signal_records.append({
            "position": [zc["lon"], zc["lat"]],
            "fill_color": SIGNAL_COLORS[sig],
        })
    if signal_records:
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=signal_records,
            get_position="position", get_radius=90, radius_min_pixels=14,
            get_fill_color="fill_color", get_line_color=[255, 255, 255, 220],
            line_width_min_pixels=2, stroked=True, pickable=False, id="zone_signal",
        ))

    # ── 3D columns (occupancy or charging demand at the current frame) ────────
    if show_3d and columns and columns.get("column_pos"):
        t_s = min(t, data["intervals"] - 1)
        if col_mode == "dem":
            elev_frames, scale = columns["column_elev_dem"], columns["column_scale_dem"]
            metric_label = " — charging demand"
        else:
            elev_frames, scale = columns["column_elev_occ"], columns["column_scale_occ"]
            metric_label = " — vehicles"
        elev = elev_frames[t_s] if t_s < len(elev_frames) else []
        col_records = []
        for i, pos in enumerate(columns["column_pos"]):
            c = columns["column_colors"][i]
            col_records.append({
                "position":   pos,
                "fill_color": [c[0], c[1], c[2], 200],
                "elev":       float(elev[i]) if i < len(elev) else 0.0,
                "tooltip":    columns["column_names"][i] + metric_label,
            })
        layers.append(pdk.Layer(
            "ColumnLayer", data=col_records,
            get_position="position", get_elevation="elev",
            elevation_scale=scale, radius=110, disk_resolution=20,
            get_fill_color="fill_color", extruded=True, pickable=True, id="columns",
        ))

    # ── Camera ────────────────────────────────────────────────────────────────
    if view_state is None:
        view_state = pdk.ViewState(
            latitude=45.9540, longitude=15.4950, zoom=12.2,
            pitch=45 if show_3d else 0, bearing=-15 if show_3d else 0,
        )
    elif isinstance(view_state, dict):
        vs = dict(view_state)
        vs.setdefault("pitch", 45 if show_3d else 0)
        vs.setdefault("bearing", -15 if show_3d else 0)
        view_state = pdk.ViewState(**vs)

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider="carto",
        map_style="light",
        tooltip={"html": "{tooltip}", "style": {"backgroundColor": "#1E293B", "color": "white"}},
    )


# ─── Client-side animated map component ──────────────────────────────────────

def serialize_vehicle_frames_compact(data, vis2_full, vis4_full):
    """
    Compact frame serialisation for the JS animation component.

    Returns a dict:
      {
        "positions": list[list[float]]   — per frame: [lon0,lat0, lon1,lat1, ...]
        "colors":    list[list[int]]     — per frame: [r0,g0,b0,a0, r1,g1,b1,a1, ...]
        "meta":      list[dict]          — per vehicle (tooltip, vid, trip_class) — static
      }

    vMeta is built from the FIRST frame's visible set (filter is frame-invariant for profile
    and SoC-band filters; vehicles that are filtered out at t=0 stay filtered all day, which
    is the intended behaviour for profile/zone toggles).  The tooltip is the vehicle's
    day-level label; SoC-in-tooltip comes from each frame's color band.
    """
    intervals  = data["intervals"]
    pos2, pos4 = data["pos2"], data["pos4"]
    types2, types4 = data["types2"], data["types4"]
    soc2, soc4 = data.get("soc2"), data.get("soc4")
    profiles2  = data.get("profiles2", [])
    profiles4  = data.get("profiles4", [])

    # Build a stable vehicle index from time-0 visibility
    vis2_0 = vis2_full[:, 0]
    vis4_0 = vis4_full[:, 0]

    # For SoC/zone filters that vary per frame, take the union across all frames
    # (a vehicle is included if it's visible at ANY timestep)
    vis2_any = vis2_full.any(axis=1)
    vis4_any = vis4_full.any(axis=1)

    idx2 = [v for v in range(data["n2"]) if vis2_any[v]]
    idx4 = [v for v in range(data["n4"]) if vis4_any[v]]

    # Static metadata (tooltip uses profile only; SoC shown via colour)
    meta = []
    for v in idx2:
        profile = profiles2[v] if profiles2 else "?"
        meta.append({"vid": v + 1, "trip_class": 2,
                     "tooltip": f"2-trip V{v+1} | {profile}"})
    for v in idx4:
        profile = profiles4[v] if profiles4 else "?"
        meta.append({"vid": v + 1, "trip_class": 4,
                     "tooltip": f"4-trip V{v+1} | {profile}"})

    nV = len(meta)

    all_pos = []
    all_col = []

    for t in range(intervals):
        pos_flat = []
        col_flat = []

        for i, v in enumerate(idx2):
            visible = vis2_full[v, t]
            if visible:
                lon, lat = float(pos2[v, t, 0]), float(pos2[v, t, 1])
            else:
                # Park off-screen (NaN → deck.gl skips; use 0,0 or last pos)
                lon, lat = float(pos2[v, t, 0]), float(pos2[v, t, 1])
            soc_val = float(soc2[v, t]) if soc2 is not None else None
            vtype   = types2[v, t]
            color   = (_soc_color(soc_val) if soc_val is not None
                       else _hex_to_rgba(TRIP_TYPE_COLORS.get(vtype, "#64748B")))
            if not visible:
                color = [0, 0, 0, 0]  # transparent = invisible
            pos_flat += [round(lon, 6), round(lat, 6)]
            col_flat += color

        for i, v in enumerate(idx4):
            visible = vis4_full[v, t]
            lon, lat = float(pos4[v, t, 0]), float(pos4[v, t, 1])
            soc_val = float(soc4[v, t]) if soc4 is not None else None
            vtype   = types4[v, t]
            color   = (_soc_color(soc_val) if soc_val is not None
                       else _hex_to_rgba(TRIP_TYPE_COLORS.get(vtype, "#64748B")))
            if not visible:
                color = [0, 0, 0, 0]
            pos_flat += [round(lon, 6), round(lat, 6)]
            col_flat += color

        all_pos.append(pos_flat)
        all_col.append(col_flat)

    return {"positions": all_pos, "colors": all_col, "meta": meta}


# ─── Live-synced bidirectional component (map is the master clock) ───────────

_LIVE_COMPONENT = None


def _get_live_component():
    """Declare (once) the bidirectional ev_map_live component."""
    global _LIVE_COMPONENT
    if _LIVE_COMPONENT is None:
        _dir = str(Path(__file__).parent / "components" / "ev_map_live")
        _LIVE_COMPONENT = components.declare_component("ev_map_live", path=_dir)
    return _LIVE_COMPONENT


def _build_signal_payload(gis_data, data):
    """Zone traffic-light positions + per-frame colours (filter-independent)."""
    static = get_static_layers(gis_data)
    zone_circles = static["zone_circles"]
    signal_zones = [z for z in _ENERGY_ZONE_ORDER if z in zone_circles]
    signal_positions = [
        [zone_circles[z]["lon"], zone_circles[z]["lat"]] for z in signal_zones
    ]
    signal_data = compute_zone_signal(data) if signal_zones else {}
    signal_colors_per_frame = []
    for t in range(data["intervals"]):
        frame_colors = []
        for z in signal_zones:
            frame_colors += SIGNAL_COLORS[signal_data[z]["signal"][t]]
        signal_colors_per_frame.append(frame_colors)
    return signal_positions, signal_colors_per_frame


def _stack_fleet(data, key2, key4):
    """Vertically stack the 2-trip and 4-trip arrays for a given field."""
    arrs = []
    for k in (key2, key4):
        a = data.get(k)
        if a is not None and len(np.asarray(a)):
            arrs.append(np.asarray(a))
    return np.vstack(arrs) if arrs else None


def _build_columns(data, zone_circles=None, res_k=8, zone_k=2):
    """3D column payload — every column sits at a data-driven position, never
    hand-placed:

    * **Residential** → up to ``res_k`` (8) k-means clusters of vehicle HOME
      locations. Height = vehicles currently at Home in that cluster; demand 0
      (the model has no home charging).
    * **Every other energy zone** (Commercial / Industrial / Leisure …) → up to
      ``zone_k`` (2) sub-clusters of the ACTUAL positions vehicles occupy while
      they are in that zone. Height(occupancy) = real vehicle count in that
      sub-cluster; height(demand) = summed ``eng_min`` of those vehicles. So the
      two sub-columns of a zone add up exactly to that zone's totals used
      elsewhere in the dashboard — the split just shows *where inside the zone*
      the load sits. Denser sub-areas (often nearer the centre) get taller
      columns.

    ``zone_circles`` is accepted for signature compatibility but no longer
    needed — positions come from the vehicles themselves."""
    nT = data["intervals"]
    positions, colors, names = [], [], []
    elev_dem = [[] for _ in range(nT)]
    elev_occ = [[] for _ in range(nT)]

    POS = _stack_fleet(data, "pos2", "pos4")          # (N, T, 2)
    TYP = _stack_fleet(data, "types2", "types4")      # (N, T)
    ZM  = _stack_fleet(data, "zone_matrix2", "zone_matrix4")  # (N, T)
    ENG = _stack_fleet(data, "eng_min2", "eng_min4")  # (N, T)

    def _add_column(lon, lat, rgb, name, occ, dem):
        positions.append([float(lon), float(lat)])
        colors.append(rgb)
        names.append(name)
        for t in range(nT):
            elev_occ[t].append(float(occ[t]))
            elev_dem[t].append(float(dem[t]))

    # ── Residential: cluster home locations ──────────────────────────────────
    if POS is not None and TYP is not None:
        res_color = _hex_to_rgba(ZONE_COLORS.get("Residential", "#AEC6CF"))[:3]
        H = POS[:, 0, :]
        home_mask = (TYP == "Home")
        centroids, labels = _kmeans_np(H, min(res_k, H.shape[0]))
        for c in range(centroids.shape[0]):
            m = labels == c
            if not m.any():
                continue
            occ_c = home_mask[m].sum(axis=0).astype(float)
            _add_column(centroids[c, 0], centroids[c, 1], res_color,
                        f"Residential {c + 1}", occ_c, np.zeros(nT))

    # ── Other zones: 2 sub-clusters from in-zone vehicle positions ───────────
    if POS is not None and ZM is not None:
        for z in [zz for zz in _ENERGY_ZONE_ORDER if zz != "Residential"]:
            present = (ZM == z)                      # (N, T) bool
            veh_has = present.any(axis=1)
            if not veh_has.any():
                continue                             # zone never occupied
            idx = np.where(veh_has)[0]
            # representative position = mean position while in this zone
            reps = np.array([POS[v][present[v]].mean(axis=0) for v in idx])
            cents, labs = _kmeans_np(reps, min(zone_k, reps.shape[0]))
            zcolor = _hex_to_rgba(ZONE_COLORS.get(z, "#64748B"))[:3]
            for c in range(cents.shape[0]):
                mm = labs == c
                if not mm.any():
                    continue
                members = idx[mm]
                occ_c = present[members].sum(axis=0).astype(float)
                if ENG is not None:
                    dem_c = (ENG[members] * present[members]).sum(axis=0)
                else:
                    dem_c = np.zeros(nT)
                _add_column(cents[c, 0], cents[c, 1], zcolor,
                            f"{z} {c + 1}", occ_c, dem_c)

    def _scale(elev):
        cmax = max((max(f) for f in elev if f), default=0.0) or 1.0
        return 900.0 / cmax

    return {
        "column_pos": positions, "column_colors": colors, "column_names": names,
        "column_elev_dem": elev_dem, "column_elev_occ": elev_occ,
        "column_scale_dem": _scale(elev_dem), "column_scale_occ": _scale(elev_occ),
    }


def render_animated_map(gis_data, data, vis2_full, vis4_full, height: int = 430):
    """
    Render the animated EV map as a bidirectional Streamlit component.

    The JavaScript map is the single master clock: it animates itself and, on
    every frame (and on scrub / vehicle click), posts its current time step back
    to Python via setComponentValue.  Python stores that in ``st.session_state
    .t_idx`` so every chart, KPI and traffic-light table redraws for the same
    instant — the map and the analytics stay locked together.

    Heavy payloads (frames / static geometry / signal colours) are large, and
    Streamlit re-sends *all* component args on every rerun.  To avoid shipping
    ~1000 vehicles × 96 frames twice a second, they are sent only while the
    filter/scenario *version* differs from what the frontend has acknowledged
    (via the ``v`` field it echoes back).  On plain clock-reruns the heavy args
    are ``None`` and the frontend keeps what it already loaded.

    Returns the component value: ``{"t": int, "selected": {...}|None, "v": str}``
    or ``None`` before the frontend has reported for the first time.
    """
    static = get_static_layers(gis_data)

    # Version signature of the current filter/scenario state.
    version = hashlib.md5(
        vis2_full.tobytes() + vis4_full.tobytes()
        + repr((data["n2"], data["n4"], data["intervals"])).encode()
    ).hexdigest()

    # Send heavy data until the frontend acknowledges this exact version.
    acked = st.session_state.get("_map_acked_version")
    send_heavy = (acked != version)

    if send_heavy:
        frames_arg = serialize_vehicle_frames_compact(data, vis2_full, vis4_full)
        static_arg = static["raw"]
        sig_pos, sig_cols = _build_signal_payload(gis_data, data)
        cols = _build_columns(data, static["zone_circles"])
    else:
        frames_arg = static_arg = sig_pos = sig_cols = None
        cols = {}

    value = _get_live_component()(
        frames_compact=frames_arg,
        static=static_arg,
        signal_pos=sig_pos,
        signal_colors=sig_cols,
        column_pos=cols.get("column_pos"),
        column_colors=cols.get("column_colors"),
        column_names=cols.get("column_names"),
        column_elev_dem=cols.get("column_elev_dem"),
        column_elev_occ=cols.get("column_elev_occ"),
        column_scale_dem=cols.get("column_scale_dem"),
        column_scale_occ=cols.get("column_scale_occ"),
        initialT=int(st.session_state.get("t_idx", 0)),
        playing=True,
        version=version,
        default=None,
        key="ev_live_map",
    )

    # Record acknowledgement so we stop re-sending the heavy payload.
    if isinstance(value, dict) and value.get("v") == version:
        st.session_state["_map_acked_version"] = version

    return value


def _kmeans_np(points, k, iters=25, seed=0):
    """Tiny dependency-free k-means for splitting home locations into clusters."""
    pts = np.asarray(points, dtype=float)
    k = int(min(k, len(pts)))
    rng = np.random.default_rng(seed)
    cent = pts[rng.choice(len(pts), size=k, replace=False)].copy()
    labels = np.zeros(len(pts), dtype=int)
    for _ in range(iters):
        d = ((pts[:, None, :] - cent[None, :, :]) ** 2).sum(axis=2)
        labels = d.argmin(axis=1)
        for c in range(k):
            m = labels == c
            if m.any():
                cent[c] = pts[m].mean(axis=0)
    return cent, labels


def render_animated_map_legacy(gis_data, data, vis2_full, vis4_full,
                               height: int = 430, show_3d: bool = False):
    """
    Fallback: render the animated EV map using st.components.v1.html().

    Self-animating in JS, no report-back — the charts do NOT follow this map.
    Kept as a one-line fallback if the live-synced component misbehaves.

    All frame data is serialised to JSON and embedded directly in the HTML
    string — no file serving, no component registry, no browser caching.
    Scroll-wheel zoom, pan, and double-click zoom all work out of the box.
    """
    static  = get_static_layers(gis_data)
    compact = serialize_vehicle_frames_compact(data, vis2_full, vis4_full)

    # ── Zone flex/demand traffic-light signal, per frame (point 3) ───────────
    zone_circles = static["zone_circles"]
    signal_zones = [z for z in _ENERGY_ZONE_ORDER if z in zone_circles]
    signal_positions = [
        [zone_circles[z]["lon"], zone_circles[z]["lat"]] for z in signal_zones
    ]
    signal_data = compute_zone_signal(data) if signal_zones else {}
    signal_colors_per_frame = []
    for t in range(data["intervals"]):
        frame_colors = []
        for z in signal_zones:
            frame_colors += SIGNAL_COLORS[signal_data[z]["signal"][t]]
        signal_colors_per_frame.append(frame_colors)

    # ── 3D columns (only when show_3d) — single source of truth is
    # _build_columns: 8 residential home clusters + 2 sub-clusters per other
    # zone, occupancy + charging-demand per frame, toggled in the map. ────────
    _nT = data["intervals"]
    if show_3d:
        _cols = _build_columns(data)
        column_positions  = _cols["column_pos"]
        column_colors     = _cols["column_colors"]
        column_names      = _cols["column_names"]
        column_elev_dem   = _cols["column_elev_dem"]
        column_elev_occ   = _cols["column_elev_occ"]
        column_scale_dem  = _cols["column_scale_dem"]
        column_scale_occ  = _cols["column_scale_occ"]
    else:
        column_positions, column_colors, column_names = [], [], []
        column_elev_dem = [[] for _ in range(_nT)]
        column_elev_occ = [[] for _ in range(_nT)]
        column_scale_dem = column_scale_occ = 1.0

    _pitch   = 45 if show_3d else 0
    _bearing = -15 if show_3d else 0

    # Serialise to JSON — will be embedded verbatim in a <script> block
    frames_json = json.dumps(compact["positions"])
    colors_json = json.dumps(compact["colors"])
    meta_json   = json.dumps(compact["meta"])
    static_json = json.dumps(static["raw"])
    signal_pos_json    = json.dumps(signal_positions)
    signal_colors_json = json.dumps(signal_colors_per_frame)
    column_pos_json      = json.dumps(column_positions)
    column_colors_json   = json.dumps(column_colors)
    column_names_json    = json.dumps(column_names)
    column_elev_dem_json = json.dumps(column_elev_dem)
    column_elev_occ_json = json.dumps(column_elev_occ)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; width:100%; height:100%; overflow:hidden; background:#e8e8e8; }}
#deck-container {{ width:100%; height:100%; position:relative; }}
canvas {{ outline:none; display:block; }}

/* ── Playback controls ── */
#controls {{
  position:absolute; bottom:10px; left:50%; transform:translateX(-50%);
  z-index:100; background:rgba(20,30,50,0.88); color:white;
  border-radius:10px; padding:7px 14px;
  font-family:system-ui,-apple-system,sans-serif; font-size:13px;
  display:flex; align-items:center; gap:10px;
  user-select:none; white-space:nowrap;
  box-shadow:0 2px 8px rgba(0,0,0,0.45);
  pointer-events:all;
}}
#controls button {{
  background:#3b82f6; color:white; border:none; border-radius:6px;
  padding:3px 11px; cursor:pointer; font-size:15px;
}}
#controls button:hover {{ background:#2563eb; }}
#slider {{ width:180px; cursor:pointer; accent-color:#3b82f6; }}
#timeLabel {{ min-width:40px; font-weight:700; font-size:14px; }}
#countLabel {{ opacity:0.7; font-size:11px; }}

/* ── Vehicle info panel ── */
#vinfo {{
  display:none;
  position:absolute; top:10px; right:10px;
  z-index:200;
  background:rgba(15,23,42,0.92); color:#f1f5f9;
  border-radius:10px; padding:12px 14px;
  font-family:system-ui,-apple-system,sans-serif; font-size:12px;
  min-width:180px; max-width:240px;
  box-shadow:0 4px 16px rgba(0,0,0,0.5);
  pointer-events:all;
}}
#vinfo-close {{
  float:right; cursor:pointer; font-size:16px; line-height:1;
  color:#94a3b8; margin-left:8px;
}}
#vinfo-close:hover {{ color:white; }}
#vinfo-title {{ font-weight:700; font-size:13px; margin-bottom:6px; }}
#vinfo-soc {{
  display:inline-block; border-radius:12px; padding:2px 10px;
  font-size:11px; font-weight:600; margin-bottom:6px;
}}
#vinfo-body {{ color:#cbd5e1; line-height:1.6; }}
</style>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css">
</head>
<body>
<div id="deck-container"></div>

<!-- Playback bar -->
<div id="controls">
  <button id="playBtn">⏸</button>
  <input type="range" id="slider" min="0" max="95" value="0" step="1">
  <span id="timeLabel">00:00</span>
  <span id="countLabel"></span>
  <button id="colBtn" title="Toggle 3D column metric">Occupancy</button>
</div>

<!-- Vehicle info panel (shown on click) -->
<div id="vinfo">
  <span id="vinfo-close">✕</span>
  <div id="vinfo-title"></div>
  <div id="vinfo-soc"></div>
  <div id="vinfo-body"></div>
</div>

<script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
<script src="https://unpkg.com/deck.gl@8.9.34/dist.min.js"></script>
<script>
// ── Embedded data ─────────────────────────────────────────────────────────
const RAW_POSITIONS = {frames_json};
const RAW_COLORS    = {colors_json};
const VMETA         = {meta_json};
const STATIC_DATA   = {static_json};
const ZONE_SIGNAL_POSITIONS   = {signal_pos_json};
const ZONE_SIGNAL_COLORS_ALL  = {signal_colors_json};
const COLUMN_POS       = {column_pos_json};
const COLUMN_COLORS    = {column_colors_json};
const COLUMN_NAMES     = {column_names_json};
const COLUMN_ELEV_DEM  = {column_elev_dem_json};
const COLUMN_ELEV_OCC  = {column_elev_occ_json};
const COLUMN_SCALE_DEM = {column_scale_dem};
const COLUMN_SCALE_OCC = {column_scale_occ};
let   columnMode = 'occ';   // 'occ' = vehicle occupancy | 'dem' = charging demand

const positions = RAW_POSITIONS.map(a => new Float32Array(a));
const colors    = RAW_COLORS.map(a => new Uint8Array(a));

const TIME_LABELS = Array.from({{length:96}},(_,i)=>
  String(Math.floor(i*15/60)).padStart(2,'0')+':'+String((i*15)%60).padStart(2,'0'));

const {{ DeckGL, ScatterplotLayer, PolygonLayer, ColumnLayer }} = deck;

let currentT  = 0;
let playing   = true;
let deckInst  = null;
let animTimer = null;

// ── SoC colour → label ────────────────────────────────────────────────────
function socLabel(r, g, b) {{
  if (r > 180 && g < 80)  return {{ label:'Critical < 20%',  bg:'#DC2626' }};
  if (r > 180 && g > 100) return {{ label:'Caution 20–50%',  bg:'#F59E0B' }};
  if (b > 180 && r < 100) return {{ label:'Normal 50–80%',   bg:'#3B82F6' }};
  return                         {{ label:'High > 80%',      bg:'#16A34A' }};
}}

// ── Vehicle info panel ────────────────────────────────────────────────────
function showVInfo(obj) {{
  const panel = document.getElementById('vinfo');
  const pos   = positions[currentT];
  const col   = colors[currentT];

  // Find index in VMETA
  const idx = VMETA.findIndex(m => m.vid === obj.vid && m.trip_class === obj.trip_class);
  const r = idx >= 0 ? col[idx*4]   : obj.fill_color[0];
  const g = idx >= 0 ? col[idx*4+1] : obj.fill_color[1];
  const b = idx >= 0 ? col[idx*4+2] : obj.fill_color[2];
  const soc = socLabel(r, g, b);

  document.getElementById('vinfo-title').textContent =
    (obj.trip_class === 2 ? '2-poti' : '4-poti') + ' · Vozilo ' + obj.vid;
  const socEl = document.getElementById('vinfo-soc');
  socEl.textContent = soc.label;
  socEl.style.background = soc.bg;
  document.getElementById('vinfo-body').innerHTML =
    'Time: <b>' + (TIME_LABELS[currentT] || '00:00') + '</b><br>' +
    'Profile: <b>' + (obj.tooltip.split('|')[1] || '—').trim() + '</b>';

  panel.style.display = 'block';
}}

document.getElementById('vinfo-close').addEventListener('click', () => {{
  document.getElementById('vinfo').style.display = 'none';
}});

// ── Build vehicle data for current frame ──────────────────────────────────
function buildVehicleData() {{
  if (!positions.length) return [];
  const pos = positions[currentT];
  const col = colors[currentT];
  const out = [];
  for (let i = 0; i < VMETA.length; i++) {{
    if (col[i*4+3] === 0) continue;
    out.push({{
      position:   [pos[i*2], pos[i*2+1]],
      fill_color: [col[i*4], col[i*4+1], col[i*4+2], col[i*4+3]],
      vid:        VMETA[i].vid,
      trip_class: VMETA[i].trip_class,
      tooltip:    VMETA[i].tooltip,
    }});
  }}
  return out;
}}

// ── Zone flex/demand signal (point 3) ─────────────────────────────────────
function buildZoneSignalData() {{
  if (!ZONE_SIGNAL_POSITIONS.length) return [];
  const col = ZONE_SIGNAL_COLORS_ALL[currentT] || [];
  return ZONE_SIGNAL_POSITIONS.map((pos, i) => ({{
    position:   pos,
    fill_color: [col[i*4], col[i*4+1], col[i*4+2], col[i*4+3]],
  }}));
}}

// ── 3D demand columns per zone (height = charging demand at current frame) ─
function buildColumnData() {{
  return COLUMN_POS.map((p, i) => ({{
    position: p,
    color:    COLUMN_COLORS[i],
    idx:      i,
    tooltip:  COLUMN_NAMES[i] + (columnMode === 'occ' ? ' — vehicles' : ' — charging demand'),
  }}));
}}

// ── Layers ────────────────────────────────────────────────────────────────
function buildLayers() {{
  const layers = [];
  if (STATIC_DATA.neigh && STATIC_DATA.neigh.length)
    layers.push(new PolygonLayer({{
      id:'neigh', data:STATIC_DATA.neigh,
      getPolygon:d=>d.polygon, getFillColor:d=>d.fill_color,
      stroked:false, pickable:false,
    }}));
  if (STATIC_DATA.bld && STATIC_DATA.bld.length)
    layers.push(new PolygonLayer({{
      id:'bld', data:STATIC_DATA.bld,
      getPolygon:d=>d.polygon, getFillColor:d=>d.fill_color,
      stroked:false, pickable:false,
    }}));
  if (STATIC_DATA.bld_pts && STATIC_DATA.bld_pts.length)
    layers.push(new ScatterplotLayer({{
      id:'bld_pts', data:STATIC_DATA.bld_pts,
      getPosition:d=>d.position, getRadius:6, radiusMinPixels:2,
      getFillColor:d=>d.fill_color, stroked:false, pickable:false,
    }}));
  if (ZONE_SIGNAL_POSITIONS.length)
    layers.push(new ScatterplotLayer({{
      id:'zone_signal', data:buildZoneSignalData(),
      getPosition:     d => d.position,
      getRadius:       90,
      radiusMinPixels: 14,
      getFillColor:    d => d.fill_color,
      getLineColor:    [255,255,255,220],
      lineWidthMinPixels: 2,
      stroked: true, pickable: false,
      updateTriggers: {{ getFillColor: currentT }},
    }}));
  if (COLUMN_POS.length)
    layers.push(new ColumnLayer({{
      id:'demand_columns', data:buildColumnData(),
      diskResolution: 20, radius: 110, extruded: true,
      elevationScale: (columnMode === 'occ' ? COLUMN_SCALE_OCC : COLUMN_SCALE_DEM),
      getPosition:  d => d.position,
      getFillColor: d => [d.color[0], d.color[1], d.color[2], 200],
      getElevation: d => (((columnMode === 'occ' ? COLUMN_ELEV_OCC : COLUMN_ELEV_DEM)[currentT] || [])[d.idx] || 0),
      updateTriggers: {{ getElevation: currentT + ':' + columnMode, elevationScale: columnMode }},
      pickable: true,
    }}));
  layers.push(new ScatterplotLayer({{
    id:'vehicles', data:buildVehicleData(),
    getPosition:   d => d.position,
    getRadius:     30,
    radiusMinPixels: 5,
    getFillColor:  d => d.fill_color,
    getLineColor:  [255,255,255,180],
    lineWidthMinPixels: 1,
    stroked:       true,
    pickable:      true,
    autoHighlight: true,
    highlightColor:[255,255,255,80],
    updateTriggers:{{ getPosition:currentT, getFillColor:currentT }},
    onClick: info => {{
      if (info.object) {{
        stopAnim();
        showVInfo(info.object);
      }}
    }},
  }}));
  return layers;
}}

// ── Deck init ─────────────────────────────────────────────────────────────
function initDeck() {{
  deckInst = new DeckGL({{
    parent: document.getElementById('deck-container'),
    mapStyle: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    maplibregl: maplibregl,
    initialViewState: {{ latitude:45.9540, longitude:15.4950, zoom:12.2, pitch:{_pitch}, bearing:{_bearing} }},
    controller: {{
      scrollZoom: true,
      doubleClickZoom: true,
      dragPan: true,
      dragRotate: true,
      touchRotate: true,
      keyboard: true,
    }},
    layers: buildLayers(),
    getTooltip: ({{object}}) => object && {{
      html: object.tooltip,
      style: {{ backgroundColor:'#1E293B', color:'white', fontSize:'12px',
                padding:'6px 10px', borderRadius:'6px' }},
    }},
  }});
}}

// After deck.gl + MapLibre finish loading, explicitly enable scroll zoom on the
// underlying MapLibre map instance (poll until ready).
function enableScrollZoom() {{
  try {{
    const mlMap = deckInst && deckInst.getMapboxMap();
    if (mlMap && mlMap.scrollZoom) {{
      mlMap.scrollZoom.enable();
      return;   // done
    }}
  }} catch(e) {{}}
  setTimeout(enableScrollZoom, 500);
}}

function updateLayers() {{
  if (deckInst) deckInst.setProps({{ layers:buildLayers() }});
}}

// ── Animation ─────────────────────────────────────────────────────────────
function startAnim() {{
  if (animTimer) return;
  playing = true;
  animTimer = setInterval(() => {{
    currentT = (currentT + 1) % (positions.length || 1);
    updateLayers(); updateUI();
  }}, 600);   // 600 ms per step ≈ comfortable to follow
  document.getElementById('playBtn').textContent = '⏸';
}}

function stopAnim() {{
  if (animTimer) {{ clearInterval(animTimer); animTimer = null; }}
  playing = false;
  document.getElementById('playBtn').textContent = '▶';
}}

function updateUI() {{
  document.getElementById('slider').value = currentT;
  document.getElementById('timeLabel').textContent = TIME_LABELS[currentT] || '00:00';
  document.getElementById('countLabel').textContent =
    VMETA.length ? VMETA.length + ' vehicles' : '';
}}

document.getElementById('playBtn').addEventListener('click', () => {{
  if (playing) stopAnim(); else startAnim();
}});
document.getElementById('slider').addEventListener('input', e => {{
  stopAnim();
  currentT = parseInt(e.target.value, 10);
  updateLayers(); updateUI();
}});
document.getElementById('colBtn').addEventListener('click', () => {{
  columnMode = (columnMode === 'occ') ? 'dem' : 'occ';
  document.getElementById('colBtn').textContent =
    (columnMode === 'occ') ? 'Occupancy' : 'Demand';
  updateLayers();
}});

document.getElementById('slider').max = (positions.length - 1) || 95;
if (!COLUMN_POS.length) document.getElementById('colBtn').style.display = 'none';
initDeck();
enableScrollZoom();   // polls until MapLibre is ready, then enables scroll zoom
startAnim();
updateUI();
</script>
</body>
</html>"""

    components.html(html, height=height)

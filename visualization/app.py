# app.py — Streamlit wrapper for the Krško EV Commuting Dashboard
# Run with: streamlit run app.py

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from data_loader import (
    load_gis_data, load_trip_data, DT_H, ZONE_COLORS, TRIP_TYPE_COLORS,
    compute_zone_signal, _ENERGY_ZONE_ORDER,
)
from chart_functions import (
    create_trip_clock_figure,
    create_single_vehicle_clock_figure,
    create_arrivals_figure,
    create_arrivals_plotly,
    create_pv_figure,
    create_zone_vehicle_hm_figure,
    create_zone_energy_hm_figure,
    create_zone_flex_figure,
    create_zone_flex_heatmap_figure,
)
from map_builder import (
    render_animated_map, render_animated_map_legacy,
    build_pydeck_map, get_static_layers, _build_columns,
)

# Live (report-back) map did not mount reliably in this environment.
#
# USE_SERVER_MAP=True → map is rendered server-side one frame at a time via
# pydeck, driven by Python's clock (st.session_state.t_idx). The map, charts,
# KPIs and traffic-light all read that same t_idx, so there is a SINGLE clock.
# Playback / zoom / pan are Streamlit buttons that drive session_state.
#
# Set USE_SERVER_MAP=False to fall back to the self-animating legacy HTML map
# (smooth JS animation but map + charts run on separate timers → two clocks).
USE_SERVER_MAP = True
USE_LIVE_MAP = False


# ─── SoC legend items ─────────────────────────────────────────────────────────

_SOC_LEGEND = [
    ("#DC2626", "Critical  < 20%"),
    ("#F59E0B", "Caution  20–50%"),
    ("#3B82F6", "Normal  50–80%"),
    ("#16A34A", "High  > 80%"),
]

_PROFILE_MAP = {
    "f_commuter":     "Commuter",
    "f_retired":      "Retired",
    "f_nonccommuter": "Nonccommuter",
}

_SOC_OPTIONS = [
    "All",
    "Critical < 20%",
    "Caution < 50%",
    "High > 80%",
]

_ALL_ZONES = list(ZONE_COLORS.keys())


# ─── Vehicle info panel ───────────────────────────────────────────────────────

def _render_vehicle_info(df: pd.DataFrame, vid: int, t: int, label: str) -> None:
    vt = df[df["Vehicle ID"] == vid].sort_values("Trip ID").reset_index(drop=True)
    if vt.empty:
        st.warning(f"No data for {label}.")
        return

    # ── Current status badge ─────────────────────────────────────────────────
    t_h = t * 0.25
    current_type = "Home"
    for _, row in vt.iterrows():
        s, e = row["Start"] * 0.25, row["End"] * 0.25
        if s <= t_h < e:
            current_type = "Driving"
            break
        if t_h >= e:
            later = vt[vt["Start"] * 0.25 > e]
            next_start = later.iloc[0]["Start"] * 0.25 if not later.empty else 24.0
            if t_h < next_start:
                current_type = row["Trip type"]
                break

    badge_color = TRIP_TYPE_COLORS.get(current_type, "#64748B")
    st.markdown(
        f'<div style="display:inline-flex;align-items:center;gap:8px;'
        f'margin-bottom:8px;">'
        f'<b style="font-size:14px;">{label}</b>'
        f'<span style="background:{badge_color};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:12px;font-weight:600;">'
        f'{current_type}</span></div>',
        unsafe_allow_html=True,
    )

    # ── Trip table ───────────────────────────────────────────────────────────
    rows = []
    for _, row in vt.iterrows():
        s_min = int(row["Start"]) * 15
        e_min = int(row["End"])   * 15
        dur_h = (int(row["End"]) - int(row["Start"])) * 0.25
        soc   = row.get("SoC_at_End", float("nan"))
        enrg  = row.get("Energy_kWh", float("nan"))
        pf    = row.get("Pos_flex_kWh", None)
        nf    = row.get("Neg_flex_kWh", None)
        entry = {
            "#":              int(row["Trip ID"]),
            "Type":           row["Trip type"],
            "Departure":      f"{s_min // 60:02d}:{s_min % 60:02d}",
            "Arrival":        f"{e_min // 60:02d}:{e_min % 60:02d}",
            "Duration":       f"{dur_h:.2f} h",
            "Energy kWh":     f"{enrg:.2f}" if pd.notna(enrg) else "—",
            "SoC end %":      f"{soc:.1f}"  if pd.notna(soc)  else "—",
        }
        if pf is not None and pd.notna(pf):
            entry["+Flex kWh"] = f"{float(pf):.2f}"
            entry["−Flex kWh"] = f"{float(nf):.2f}" if (nf is not None and pd.notna(nf)) else "—"
        rows.append(entry)

    trip_df = pd.DataFrame(rows)
    st.dataframe(trip_df, hide_index=True, use_container_width=True, height=150)

    # ── Summary metrics ──────────────────────────────────────────────────────
    total_energy = vt["Energy_kWh"].sum() if "Energy_kWh" in vt.columns else 0.0
    n_trips      = len(vt)
    work_rows    = vt[vt["Trip type"] == "Work"]

    work_park_h = 0.0
    for _, wr in work_rows.iterrows():
        later = vt[vt["Trip ID"] > wr["Trip ID"]]
        if not later.empty:
            work_park_h += (later.iloc[0]["Start"] - wr["End"]) * 0.25

    pos_flex_total = (
        vt["Pos_flex_kWh"].sum()
        if "Pos_flex_kWh" in vt.columns else 0.0
    )

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Trips",         n_trips)
    mc2.metric("Total energy",  f"{total_energy:.1f} kWh")
    mc3.metric("Parking",       f"{work_park_h:.1f} h")
    mc4.metric("Flexibility",   f"{pos_flex_total:.1f} kWh")


# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EV Dashboard — Krško",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 2rem !important;
    }
    /* Cohesive cards (st.container(border=True)) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        padding: 4px 4px;
    }
    /* Card titles */
    div[data-testid="stVerticalBlockBorderWrapper"] h3 {
        font-size: 1.02rem !important;
        color: #1E293B;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    /* Tighter captions */
    div[data-testid="stCaptionContainer"] { color: #64748B; margin-top: -4px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Session state defaults ────────────────────────────────────────────────────

if "t_idx" not in st.session_state:
    st.session_state.t_idx = 0
if "t_display" not in st.session_state:
    st.session_state.t_display = 0
if "playing" not in st.session_state:
    st.session_state.playing = True
if "selected_vehicle" not in st.session_state:
    st.session_state.selected_vehicle = None
if "_slider_sync" not in st.session_state:
    st.session_state._slider_sync = False
# Server-rendered map camera (driven by the on-map zoom / pan buttons).
if "view_zoom" not in st.session_state:
    st.session_state.view_zoom = 12.2
if "view_lat" not in st.session_state:
    st.session_state.view_lat = 45.9540
if "view_lon" not in st.session_state:
    st.session_state.view_lon = 15.4950


# ─── File discovery ────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
if not DATA_DIR.exists():
    st.error(f"Data folder not found: {DATA_DIR}")
    st.stop()

# ─── Scenario definitions ──────────────────────────────────────────────────────

_SCENARIOS = [
    {
        "label":    "Scenario 1 — Test (25 + 100 EV)",
        "desc":     "25 EV × 4 trips  |  100 EV × 2 trips",
        "file_4t":  "04_SoC_flex_25_EVs_4_trips_1_days.xlsx",
        "file_2t":  "04_SoC_flex_100_EVs_2_trips_1_days.xlsx",
        "available": True,
    },
    {
        "label":    "Scenario 2 — 6 % EV (206 + 824 EV)",
        "desc":     "206 EV × 4 trips  |  824 EV × 2 trips",
        "file_4t":  "04_SoC_flex_206_EVs_4_trips_1_days.xlsx",
        "file_2t":  "04_SoC_flex_824_EVs_2_trips_1_days.xlsx",
        "available": True,
    },
    {
        "label":    "Scenario 3 — 20 % EV",
        "desc":     "Data not yet available.",
        "file_4t":  None,
        "file_2t":  None,
        "available": False,
    },
    {
        "label":    "Scenario 4 — 50 % EV",
        "desc":     "Data not yet available.",
        "file_4t":  None,
        "file_2t":  None,
        "available": False,
    },
    {
        "label":    "Scenario 5 — 100 % EV",
        "desc":     "Data not yet available.",
        "file_4t":  None,
        "file_2t":  None,
        "available": False,
    },
]

_TIME_LABELS = [f"{(i * 15) // 60:02d}:{(i * 15) % 60:02d}" for i in range(96)]

# The time-of-day slider is the single master clock (manual scrub). Seed its
# widget value once; thereafter it owns t_idx (applied right after data load).
if "time_slider_widget" not in st.session_state:
    st.session_state.time_slider_widget = _TIME_LABELS[
        min(st.session_state.get("t_idx", 0), len(_TIME_LABELS) - 1)
    ]

if st.session_state._slider_sync:
    st.session_state.time_slider_widget = _TIME_LABELS[st.session_state.t_idx]
    st.session_state._slider_sync = False


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── Krško banner (drop an image at assets/krsko.png to show it) ───────────
    _banner = Path(__file__).parent / "assets" / "krsko.png"
    if _banner.exists():
        st.image(str(_banner), use_container_width=True)
    st.title("EV Dashboard")
    st.caption("Krško · commuter EV fleet")
    st.divider()

    # ── Scenario ─────────────────────────────────────────────────────────────
    st.subheader("Scenario")
    scenario_labels = [s["label"] for s in _SCENARIOS]
    sel_scenario_label = st.radio(
        "Select scenario",
        options=scenario_labels,
        index=0,
        key="scenario_radio",
        label_visibility="collapsed",
    )
    sel_scenario = next(s for s in _SCENARIOS if s["label"] == sel_scenario_label)

    if sel_scenario["available"]:
        st.caption(sel_scenario["desc"])
        path_2trips = str(DATA_DIR / sel_scenario["file_2t"])
        path_4trips = str(DATA_DIR / sel_scenario["file_4t"])
        # Verify files exist
        for fp in [path_2trips, path_4trips]:
            if not Path(fp).exists():
                st.error(f"File does not exist: {Path(fp).name}")
                st.stop()
    else:
        st.info(f"⏳ {sel_scenario['desc']}")
        st.stop()

    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────
    st.subheader("Filters")

    st.markdown("**Vehicle profile**")
    fp1, fp2, fp3 = st.columns(3)
    with fp1:
        show_commuter     = st.toggle("Commuter",     value=True, key="f_commuter")
    with fp2:
        show_retired      = st.toggle("Retired",      value=True, key="f_retired")
    with fp3:
        show_nonccommuter = st.toggle("Non-commuter", value=True, key="f_nonccommuter")

    st.markdown("**Battery state (SoC)**")
    soc_filter = st.radio(
        "SoC filter",
        options=_SOC_OPTIONS,
        index=0,
        key="soc_radio",
        label_visibility="collapsed",
    )

    st.markdown("**Location (zone)**")
    zone_filter = st.multiselect(
        "Zone",
        options=_ALL_ZONES,
        default=_ALL_ZONES,
        key="zone_filter",
        label_visibility="collapsed",
        help="Shows only vehicles that are in the selected zone at the selected time.",
    )

    st.markdown("**Availability for V2G service**")
    avail_enabled = st.toggle(
        "Apply availability filter",
        value=False,
        key="avail_enabled",
        help="When enabled, shows only vehicles that are parked CONTINUOUSLY at "
             "the workplace throughout the time window below and have at least "
             "the selected SoC on arrival.",
    )
    avail_window = st.select_slider(
        "Availability time window",
        options=_TIME_LABELS,
        value=(_TIME_LABELS[40], _TIME_LABELS[56]),  # 10:00–14:00 (midday: most
        # commuters are parked at work, so the filter usually matches vehicles)
        key="avail_window",
        disabled=not avail_enabled,
    )
    min_arrival_soc = st.slider(
        "Min. SoC on arrival at work (%)",
        min_value=0, max_value=100, value=0, step=5,
        key="min_arrival_soc",
        disabled=not avail_enabled,
    )

    show_2trips = True
    show_4trips = True

    st.divider()
    st.caption("Fleet data loads below.")


# ─── Load data ────────────────────────────────────────────────────────────────

gis_data = load_gis_data()
data = load_trip_data(path_2trips, path_4trips, gis_data["landuse_gdf"])

intervals = data["intervals"]

# Time slider drives the shared clock. Its stored widget value (set on the last
# scrub) is applied here so every panel — map, charts, KPIs — uses the same t.
_slider_label = st.session_state.get("time_slider_widget", _TIME_LABELS[0])
st.session_state.t_idx = min(_TIME_LABELS.index(_slider_label), intervals - 1)
t = st.session_state.t_idx


def _compute_vis_masks_full(data):
    """Profile + SoC + location(zone) filter masks across the whole day.

    Returns (vis2_full, vis4_full): bool arrays shaped (n_vehicles, intervals).
    Slicing column t gives the per-frame mask (used by the map); summing/
    masking with the full array lets charts and KPIs reflect the same filter
    across all 96 timesteps, not just the currently displayed one.
    """
    active_profiles = set()
    if st.session_state.get("f_commuter",     True): active_profiles.add("Commuter")
    if st.session_state.get("f_retired",      True): active_profiles.add("Retired")
    if st.session_state.get("f_nonccommuter", True): active_profiles.add("Nonccommuter")

    profile_mask2 = np.array(
        [p in active_profiles for p in data["profiles2"]], dtype=bool
    )[:, None]
    profile_mask4 = np.array(
        [p in active_profiles for p in data["profiles4"]], dtype=bool
    )[:, None]

    soc2, soc4 = data["soc2"], data["soc4"]
    soc_opt = st.session_state.get("soc_radio", "All")
    if soc_opt == "Critical < 20%":
        soc_mask2, soc_mask4 = soc2 < 20.0, soc4 < 20.0
    elif soc_opt == "Caution < 50%":
        soc_mask2, soc_mask4 = soc2 < 50.0, soc4 < 50.0
    elif soc_opt == "High > 80%":
        soc_mask2, soc_mask4 = soc2 > 80.0, soc4 > 80.0
    else:
        soc_mask2 = np.ones_like(soc2, dtype=bool)
        soc_mask4 = np.ones_like(soc4, dtype=bool)

    selected_zones = st.session_state.get("zone_filter", _ALL_ZONES)
    if len(selected_zones) >= len(_ALL_ZONES):
        zone_mask2 = np.ones_like(data["zone_matrix2"], dtype=bool)
        zone_mask4 = np.ones_like(data["zone_matrix4"], dtype=bool)
    else:
        zone_mask2 = np.isin(data["zone_matrix2"], selected_zones)
        zone_mask4 = np.isin(data["zone_matrix4"], selected_zones)

    if st.session_state.get("avail_enabled", False):
        t0_label, t1_label = st.session_state.get(
            "avail_window", (_TIME_LABELS[60], _TIME_LABELS[72])
        )
        t0, t1 = sorted([_TIME_LABELS.index(t0_label), _TIME_LABELS.index(t1_label)])
        min_soc = st.session_state.get("min_arrival_soc", 0)
        avail_mask2 = _availability_mask(
            data["types2"], data["arrival_soc_at_work2"], t0, t1, min_soc
        )
        avail_mask4 = _availability_mask(
            data["types4"], data["arrival_soc_at_work4"], t0, t1, min_soc
        )
    else:
        avail_mask2 = np.ones((data["n2"], 1), dtype=bool)
        avail_mask4 = np.ones((data["n4"], 1), dtype=bool)

    vis2_full = profile_mask2 & soc_mask2 & zone_mask2 & avail_mask2
    vis4_full = profile_mask4 & soc_mask4 & zone_mask4 & avail_mask4
    return vis2_full, vis4_full


def _availability_mask(types, arrival_soc, t0, t1, min_soc):
    """Day-level (nv, 1) mask: True for vehicle v if it is parked continuously
    at Work for every timestep in [t0, t1] (inclusive) AND its SoC at arrival
    to that Work window is >= min_soc. Point 1 — availability filter."""
    window = types[:, t0:t1 + 1] == "Work"
    continuously_parked = window.all(axis=1)
    arrival_at_t0 = arrival_soc[:, t0]
    soc_ok = np.where(np.isnan(arrival_at_t0), False, arrival_at_t0 >= min_soc)
    return (continuously_parked & soc_ok)[:, None]


def _filtered_arrival_departure_hist(types, vis_full, intervals):
    """Arrival/departure histogram gated by the filter mask at the relevant
    stationary timestep (t for arrivals — just landed at Work; t-1 for
    departures — still parked at Work right before leaving)."""
    nv = types.shape[0]
    arr_hist = np.zeros(intervals)
    dep_hist = np.zeros(intervals)
    for v in range(nv):
        for t in range(1, intervals):
            if types[v, t - 1] == "Driving" and types[v, t] == "Work" and vis_full[v, t]:
                arr_hist[t] += 1
            if types[v, t - 1] == "Work" and types[v, t] == "Driving" and vis_full[v, t - 1]:
                dep_hist[t] += 1
    return arr_hist, dep_hist


# ─── Fleet + KPIs in sidebar (post-load) ─────────────────────────────────────

with st.sidebar:
    st.subheader("Fleet")
    c1, c2 = st.columns(2)
    c1.metric("2-trip", data["n2"])
    c2.metric("4-trip", data["n4"])

    # ── Availability filter feedback (point 5) ────────────────────────────────
    # The matching logic is unchanged; this only surfaces how many vehicles it
    # currently keeps, so an empty result no longer looks like a broken filter.
    if st.session_state.get("avail_enabled", False):
        _t0l, _t1l = st.session_state.get(
            "avail_window", (_TIME_LABELS[40], _TIME_LABELS[56])
        )
        _t0, _t1 = sorted([_TIME_LABELS.index(_t0l), _TIME_LABELS.index(_t1l)])
        _msoc = st.session_state.get("min_arrival_soc", 0)
        _am2 = _availability_mask(
            data["types2"], data["arrival_soc_at_work2"], _t0, _t1, _msoc
        )
        _am4 = _availability_mask(
            data["types4"], data["arrival_soc_at_work4"], _t0, _t1, _msoc
        )
        _n_avail = int(_am2.sum()) + int(_am4.sum())
        if _n_avail == 0:
            st.warning(
                f"No vehicles are parked at work continuously {_t0l}–{_t1l} "
                f"with SoC ≥ {_msoc}%. Try a midday window or a lower SoC."
            )
        else:
            st.success(f"{_n_avail} vehicles available for V2G in this window.")
    st.divider()

    # ── Vehicle selector ──────────────────────────────────────────────────────
    st.subheader("Vehicle")
    _veh_options_2 = [f"2-trip V{v+1}" for v in range(data["n2"])]
    _veh_options_4 = [f"4-trip V{v+1}" for v in range(data["n4"])]
    _veh_all = ["— none —"] + _veh_options_2 + _veh_options_4
    _cur_sel = st.session_state.selected_vehicle
    if _cur_sel is not None:
        _tc, _v0 = _cur_sel
        _cur_label = f"{'2-trip' if _tc == 2 else '4-trip'} V{_v0 + 1}"
        _cur_idx = _veh_all.index(_cur_label) if _cur_label in _veh_all else 0
    else:
        _cur_idx = 0
    _sel_label = st.selectbox(
        "Select vehicle for details",
        _veh_all, index=_cur_idx, key="vehicle_selector",
        label_visibility="collapsed",
    )
    if _sel_label == "— none —":
        st.session_state.selected_vehicle = None
    else:
        _parts = _sel_label.split(" ")   # e.g. ["2-trip", "V3"]
        _tc_sel = 2 if _parts[0] == "2-trip" else 4
        _vid_sel = int(_parts[1][1:]) - 1
        st.session_state.selected_vehicle = (_tc_sel, _vid_sel)
    st.divider()
    # KPI — current time: rendered inside the tab_main fragment below.


# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab_main, tab_pv, tab_zone_veh, tab_zone_egy, tab_zone_flex, tab_energy_snapshot = st.tabs([
    "Map & charts",
    "PV Self-sufficiency",
    "Zone: Vehicles",
    "Zone: Energy",
    "Zone: Flexibility",
    "Energy snapshot",
])


# ─── Tab 1: Main dashboard (fragment-scoped so the animation tick only ───────
# re-renders this tab, not the sidebar, data load, or the other 5 tabs) ───────

def _prepare_dashboard_data():
    """Heavy compute — runs only on a full rerun (filter/scenario change), NOT on
    the animation tick. Caches the filtered day-level histograms/curves and the
    visibility masks so the light auto-refreshing fragments stay cheap."""
    vis2_full, vis4_full = _compute_vis_masks_full(data)

    filt_arr2, filt_dep2 = _filtered_arrival_departure_hist(data["types2"], vis2_full, intervals)
    filt_arr4, filt_dep4 = _filtered_arrival_departure_hist(data["types4"], vis4_full, intervals)
    filtered_data = dict(data)
    filtered_data["e_min2"] = (data["eng_min2"] * vis2_full).sum(axis=0)
    filtered_data["e_max2"] = (data["eng_max2"] * vis2_full).sum(axis=0)
    filtered_data["e_min4"] = (data["eng_min4"] * vis4_full).sum(axis=0)
    filtered_data["e_max4"] = (data["eng_max4"] * vis4_full).sum(axis=0)
    filtered_data["arr_hist2"] = filt_arr2
    filtered_data["dep_hist2"] = filt_dep2
    filtered_data["arr_hist4"] = filt_arr4
    filtered_data["dep_hist4"] = filt_dep4
    filtered_data["arr_hist_total"] = filt_arr2 + filt_arr4
    filtered_data["dep_hist_total"] = filt_dep2 + filt_dep4
    st.session_state["_filtered_data"] = filtered_data
    return vis2_full, vis4_full


@st.cache_resource
def _columns_payload(_gis_data, _data, sig):
    """3D column payload (k-means home clusters + zone centroids), cached per
    scenario so the clustering isn't recomputed on every 0.6 s animation tick."""
    zc = get_static_layers(_gis_data)["zone_circles"]
    return _build_columns(_data, zc)


def _pan_step():
    """Pan distance in degrees — smaller as you zoom in, so one press moves a
    sensible amount at any zoom."""
    z = st.session_state.get("view_zoom", 12.2)
    return 0.12 / (2 ** (z - 11))


def _render_map_canvas(vis2_full, vis4_full, columns):
    """Server-rendered single frame at the shared clock ``t_idx`` (set by the
    time slider). Renders once per scrub — no 0.6 s auto-refresh, so no gray
    flicker. Map, charts and KPIs all read the same ``t_idx`` → one clock. The
    camera comes from session_state (pan/zoom buttons) and stays put."""
    t = min(st.session_state.get("t_idx", 0), intervals - 1)
    show3d = st.session_state.get("show_3d_cols", False)
    view = {
        "latitude":  st.session_state.get("view_lat", 45.9540),
        "longitude": st.session_state.get("view_lon", 15.4950),
        "zoom":      st.session_state.get("view_zoom", 12.2),
        "pitch":     45 if show3d else 0,
        "bearing":   -15 if show3d else 0,
    }
    col_mode = ("occ" if st.session_state.get("col_mode_radio", "Occupancy") == "Occupancy"
                else "dem")
    deck = build_pydeck_map(
        gis_data, data, t,
        vis2=vis2_full[:, t], vis4=vis4_full[:, t],
        view_state=view, show_3d=show3d, col_mode=col_mode, columns=columns,
    )
    st.pydeck_chart(deck, use_container_width=True, height=440)


def _render_map_panel(vis2_full, vis4_full, n_vis, columns):
    """Server-rendered map card: fleet counts, 3D toggle (below the data),
    playback + zoom/pan button bar, legends, then the auto-advancing pydeck
    canvas. Controls live in normal flow (stable — not inside the 0.6 s
    fragment); only the canvas re-renders on the clock."""
    with st.container(border=True):
        # ── Fleet counts ─────────────────────────────────────────────────────
        st.markdown(
            f"**{data['n2']} × 2-trip &nbsp;|&nbsp; {data['n4']} × 4-trip &nbsp;|&nbsp; "
            f"total {data['n_total']} &nbsp;|&nbsp; shown: {n_vis}**",
            unsafe_allow_html=True,
        )

        # ── 3D toggle — moved below the data, enlarged, no emoji ─────────────
        st.toggle(
            "3D columns", key="show_3d_cols",
            help="Show extruded per-zone columns (occupancy or charging demand).",
        )
        show3d = st.session_state.get("show_3d_cols", False)
        if show3d:
            st.radio(
                "Column metric", ["Occupancy", "Demand"],
                key="col_mode_radio", horizontal=True, label_visibility="collapsed",
            )

        # ── Time slider — the master clock. Scrubbing reruns once (no gray
        # flicker from a 0.6 s auto-refresh) and moves the map + all charts. ──
        st.select_slider(
            "Time of day", options=_TIME_LABELS, key="time_slider_widget",
            help="Drag to pick the 15-minute snapshot shown on the map and charts.",
        )

        # ── Zoom / pan bar (buttons drive the persisted camera) ──────────────
        b = st.columns(6)
        if b[0].button("−", key="zoom_out", help="Zoom out", use_container_width=True):
            st.session_state.view_zoom = max(9.0, st.session_state.get("view_zoom", 12.2) - 0.5)
        if b[1].button("+", key="zoom_in", help="Zoom in", use_container_width=True):
            st.session_state.view_zoom = min(17.0, st.session_state.get("view_zoom", 12.2) + 0.5)
        _step = _pan_step()
        if b[2].button("◀", key="pan_left", help="Pan west", use_container_width=True):
            st.session_state.view_lon -= _step
        if b[3].button("▲", key="pan_up", help="Pan north", use_container_width=True):
            st.session_state.view_lat += _step
        if b[4].button("▼", key="pan_down", help="Pan south", use_container_width=True):
            st.session_state.view_lat -= _step
        if b[5].button("▶", key="pan_right", help="Pan east", use_container_width=True):
            st.session_state.view_lon += _step

        # ── Legends ──────────────────────────────────────────────────────────
        leg_col1, leg_col2 = st.columns([1, 2])
        with leg_col1:
            st.markdown("**Urban zones & buildings**")
            _LEGEND_ZONES = {**ZONE_COLORS, "Education": "#984ea3"}
            st.markdown("".join(
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                f'<div style="width:14px;height:14px;border-radius:50%;background:{color};'
                f'flex-shrink:0;"></div>'
                f'<span style="font-size:12px;">{zone}</span></div>'
                for zone, color in _LEGEND_ZONES.items()
            ), unsafe_allow_html=True)
        with leg_col2:
            st.markdown("**Battery state (SoC)**")
            st.markdown("".join(
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                f'<div style="width:10px;height:10px;border-radius:50%;background:{color};'
                f'flex-shrink:0;"></div>'
                f'<span style="font-size:12px;">{label}</span></div>'
                for color, label in _SOC_LEGEND
            ), unsafe_allow_html=True)

        # ── Canvas (renders the slider's frame; no auto-refresh) ─────────────
        _render_map_canvas(vis2_full, vis4_full, columns)

    # ── 3D explanation — only when 3D is on (hidden otherwise) ───────────────
    if show3d:
        with st.container(border=True):
            st.subheader("3D columns — what they show")
            st.markdown(
                "Each column rises from a zone; use the **Occupancy / Demand** toggle "
                "above the map to switch what the height means.\n\n"
                "- **Occupancy** — number of vehicles in the zone at the current time. "
                "Residential is split into up to **8 home clusters**, and Commercial / "
                "Industrial / Leisure into **2 sub-locations each**, spread across the map so "
                "you can see where the fleet actually sits. Every column stands at the "
                "*centroid* (mean position) of one group of vehicles, so denser areas — often "
                "nearer the town centre — get their own column. A cluster with nobody there at "
                "the current instant is flat, so you may see fewer at once.\n"
                "- **Demand** — charging power drawn in the zone (the two sub-columns of a "
                "zone add up to that zone's total). Only workplace zones rise, because this "
                "model charges vehicles **at work only** (no home charging), so Residential / "
                "Leisure columns are ~zero in this mode.\n\n"
                "Heights are comparable **within** a metric. Use the pan / zoom buttons to "
                "move the tilted 3D view."
            )


@st.fragment
def _render_map_fragment(vis2_full, vis4_full, n_vis):
    """Legacy fallback map panel (USE_SERVER_MAP=False). With the self-animating
    map (USE_LIVE_MAP=False) the 3D columns are toggled by a Streamlit checkbox
    and the charts run on their own timer. With the live report-back map the
    toggle and the clock live in the map and are reported back."""
    with st.container(border=True):
        hc1, hc2 = st.columns([3, 1])
        with hc1:
            st.markdown(
                f"**{data['n2']} × 2-trip &nbsp;|&nbsp; {data['n4']} × 4-trip &nbsp;|&nbsp; "
                f"total {data['n_total']} &nbsp;|&nbsp; shown: {n_vis}**",
                unsafe_allow_html=True,
            )
        with hc2:
            if not USE_LIVE_MAP:
                st.checkbox("🧊 3D columns", key="show_3d_cols",
                            help="Show extruded per-zone columns on the map.")
        leg_col1, leg_col2 = st.columns([1, 2])
        with leg_col1:
            st.markdown("**Urban zones & buildings**")
            _LEGEND_ZONES = {**ZONE_COLORS, "Education": "#984ea3"}
            st.markdown("".join(
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                f'<div style="width:14px;height:14px;border-radius:50%;background:{color};'
                f'flex-shrink:0;"></div>'
                f'<span style="font-size:12px;">{zone}</span></div>'
                for zone, color in _LEGEND_ZONES.items()
            ), unsafe_allow_html=True)
        with leg_col2:
            st.markdown("**Battery state (SoC)**")
            st.markdown("".join(
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                f'<div style="width:10px;height:10px;border-radius:50%;background:{color};'
                f'flex-shrink:0;"></div>'
                f'<span style="font-size:12px;">{label}</span></div>'
                for color, label in _SOC_LEGEND
            ), unsafe_allow_html=True)

        if USE_LIVE_MAP:
            value = render_animated_map(gis_data, data, vis2_full, vis4_full, height=420)
        else:
            render_animated_map_legacy(gis_data, data, vis2_full, vis4_full, height=420,
                                       show_3d=st.session_state.get("show_3d_cols", False))
            value = None

    # Apply the map's reported time + 3D state (only in live mode).
    if isinstance(value, dict):
        if isinstance(value.get("t"), int):
            st.session_state.t_idx = max(0, min(value["t"], intervals - 1))
        st.session_state["_show3d"] = bool(value.get("show3d", False))

    show3d_on = (st.session_state.get("_show3d", False) if USE_LIVE_MAP
                 else st.session_state.get("show_3d_cols", False))
    if show3d_on:
        with st.container(border=True):
            st.subheader("3D columns — what they show")
            st.markdown(
                "Each column rises from a zone; use the **Occupancy / Demand** button "
                "on the map to switch what the height means.\n\n"
                "- **Occupancy** — number of vehicles in the zone at the current time. "
                "Residential is split into up to **4 home clusters** spread across the map, "
                "so you can see where the fleet parks.\n"
                "- **Demand** — charging power drawn in the zone. Only workplace zones rise, "
                "because this model charges vehicles **at work only** (no home charging), so "
                "Residential / Leisure columns are ~zero in this mode.\n\n"
                "Heights are comparable **within** a metric. The map tilts for 3D — drag with "
                "the right mouse button to rotate."
            )


def _render_clock_card():
    """Trip-chain clock / selected-vehicle panel for the slider's frame.
    Sits directly under the map; the clock is centred so it reads as a card."""
    t = min(st.session_state.get("t_idx", 0), intervals - 1)
    sel = st.session_state.get("selected_vehicle")
    with st.container(border=True):
        st.subheader("Trip chain clock")
        if sel is not None:
            _tc, _v0 = sel
            sel_vid_1 = _v0 + 1
            if _tc == 2:
                sel_chain = data["all_chains_2"].get(sel_vid_1)
                sel_df_v, sel_label = data["df_2"], f"2-trip V{sel_vid_1}"
            else:
                sel_chain = data["all_chains_4"].get(sel_vid_1)
                sel_df_v, sel_label = data["df_4"], f"4-trip V{sel_vid_1}"
            _cc = st.columns([1, 2, 1])
            with _cc[1]:
                if sel_chain is not None:
                    st.pyplot(create_single_vehicle_clock_figure(sel_chain, t, sel_label),
                              use_container_width=True)
            _render_vehicle_info(sel_df_v, sel_vid_1, t, sel_label)
        else:
            _cc = st.columns([1, 2, 1])
            with _cc[1]:
                st.pyplot(create_trip_clock_figure(data, t), use_container_width=True)


def _render_arrivals_card():
    """Interactive work arrivals / departures chart (Plotly) for the slider's
    frame — sits under the clock, full card width."""
    t = min(st.session_state.get("t_idx", 0), intervals - 1)
    fd = st.session_state.get("_filtered_data")
    if fd is None:
        return
    with st.container(border=True):
        st.subheader("Work arrivals / departures")
        st.plotly_chart(
            create_arrivals_plotly(fd, t, show_2trips, show_4trips),
            use_container_width=True, config={"displayModeBar": False},
        )


with tab_main:
    vis2_full, vis4_full = _prepare_dashboard_data()
    _t0 = min(st.session_state.t_idx, intervals - 1)
    _n_vis = int(vis2_full[:, _t0].sum()) + int(vis4_full[:, _t0].sum())

    # Vertical stack — the map is the centrepiece (full width), the trip-chain
    # clock sits directly beneath it, and the arrivals/departures chart beneath
    # the clock.
    if USE_SERVER_MAP and not USE_LIVE_MAP:
        _columns = _columns_payload(
            gis_data, data, f"{data['n2']}-{data['n4']}-{intervals}"
        )
        _render_map_panel(vis2_full, vis4_full, _n_vis, _columns)
    else:
        _render_map_fragment(vis2_full, vis4_full, _n_vis)
    _render_clock_card()
    _render_arrivals_card()


# ─── Sidebar KPIs — reflect the slider's current frame ───────────────────────

def _render_kpis():
    t_now = min(st.session_state.get("t_idx", 0), intervals - 1)
    vis2_full, vis4_full = _compute_vis_masks_full(data)
    vis2_t, vis4_t = vis2_full[:, t_now], vis4_full[:, t_now]

    parked_now = (
        int(np.sum((data["types2"][:, t_now] == "Work") & vis2_t))
        + int(np.sum((data["types4"][:, t_now] == "Work") & vis4_t))
    )
    e_now = float(
        (data["eng_min2"][:, t_now] * vis2_t).sum()
        + (data["eng_min4"][:, t_now] * vis4_t).sum()
    )

    with st.container(border=True):
        st.subheader("KPI — current time")
        k1, k2 = st.columns(2)
        k1.metric("Parked at work", parked_now,
                  help=f"Daily max: {data['max_park_tot']}")
        k2.metric("Charging demand", f"{e_now:.0f} kW",
                  help=f"Fleet peak: {data['fleet_max']:.0f} kW")


with st.sidebar:
    _render_kpis()


# ─── Sidebar — zone flex/demand traffic-light semafor (point 3) ─────────────

_SIGNAL_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴"}


def _render_zone_signal_table():
    t_now = min(st.session_state.get("t_idx", 0), intervals - 1)
    signal_data = compute_zone_signal(data)

    rows = []
    for zone in _ENERGY_ZONE_ORDER:
        ratio = signal_data[zone]["ratio"][t_now]
        signal = signal_data[zone]["signal"][t_now]
        ratio_str = "∞" if np.isinf(ratio) else f"{ratio:.2f}"
        rows.append({
            "Zone":      zone,
            "Signal":    _SIGNAL_EMOJI[signal],
            "Ratio":     ratio_str,
        })

    with st.container(border=True):
        st.subheader("Flexibility traffic light")
        st.caption("Ratio: V1G potential (kW) / charging demand (kW) per zone.")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


with st.sidebar:
    _render_zone_signal_table()


# ─── Tab 2: PV self-sufficiency ───────────────────────────────────────────────

with tab_pv:
    with st.container(border=True):
        st.subheader("PV self-sufficiency")
        st.caption("PV self-sufficiency rate at the workplace.")
        fig_pv = create_pv_figure()
        st.pyplot(fig_pv, use_container_width=True)
        plt.close(fig_pv)


# ─── Tab 3: Zone vehicle-count heatmap ───────────────────────────────────────

with tab_zone_veh:
    with st.container(border=True):
        st.subheader("Fleet distribution by zone")
        st.caption("Vehicle count per zone over 24 hours.")
        fig_zhm = create_zone_vehicle_hm_figure(data, t)
        st.pyplot(fig_zhm, use_container_width=True)
        plt.close(fig_zhm)


# ─── Tab 4: Zone energy demand heatmap ───────────────────────────────────────

with tab_zone_egy:
    with st.container(border=True):
        st.subheader("Energy demand by zone")
        st.caption("Charging energy demand (kWh) per zone over 24 hours.")
        fig_ze = create_zone_energy_hm_figure(data, t)
        st.pyplot(fig_ze, use_container_width=True)
        plt.close(fig_ze)


# ─── Tab 5: Zone flexibility dashboard ────────────────────────────────────────

with tab_zone_flex:
    with st.container(border=True):
        st.subheader("Zone flexibility analysis")
        st.caption("Current overview and V1G / V2G potential per zone.")
        fig_zf = create_zone_flex_figure(data, t)
        st.pyplot(fig_zf, use_container_width=True)
        plt.close(fig_zf)

    with st.container(border=True):
        st.subheader("V1G / V2G potential over the day")
        st.caption(
            "V1G (charging potential): vehicles parked at work could absorb extra energy — "
            "upward flexibility.  \n"
            "V2G (discharge potential): vehicles could export energy back to the grid — "
            "downward flexibility."
        )
        fig_fhm = create_zone_flex_heatmap_figure(data)
        st.pyplot(fig_fhm, use_container_width=True)
        plt.close(fig_fhm)


# ─── Tab 6: Energy Snapshot ───────────────────────────────────────────────────

with tab_energy_snapshot:
    import plotly.graph_objects as go
    from data_loader import ZONE_COLORS, _ENERGY_ZONE_ORDER

    zones  = _ENERGY_ZONE_ORDER
    zone_colors_snap = [ZONE_COLORS[z] for z in zones]

    # Daily total energy per zone (sum over all 96 timesteps × DT_H to get kWh)
    energy_daily = data["zone_energy_combined"].sum(axis=1) * DT_H
    values_daily = [float(energy_daily[i]) for i in range(len(zones))]

    # Peak (max over day) for context
    energy_peak  = data["zone_energy_combined"].max(axis=1)
    values_peak  = [float(energy_peak[i]) for i in range(len(zones))]

    fig_snap = go.Figure()
    fig_snap.add_trace(go.Barpolar(
        r=values_daily,
        theta=zones,
        name="Total energy (kWh)",
        marker_color=zone_colors_snap,
        marker_line_color="white",
        marker_line_width=1.5,
        opacity=0.85,
        hovertemplate="<b>%{theta}</b><br>Total: %{r:.1f} kWh<extra></extra>",
    ))
    fig_snap.add_trace(go.Barpolar(
        r=values_peak,
        theta=zones,
        name="Peak demand (kW)",
        marker_color=zone_colors_snap,
        marker_line_color="white",
        marker_line_width=1.5,
        opacity=0.35,
        hovertemplate="<b>%{theta}</b><br>Peak: %{r:.1f} kW<extra></extra>",
    ))

    max_r = max(max(values_daily), max(values_peak)) if values_daily else 1

    fig_snap.update_layout(
        title=dict(
            text="Total daily energy demand per zone",
            x=0.5,
            font=dict(size=16),
        ),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_r * 1.15],
                ticksuffix=" kWh",
                tickfont=dict(size=10),
                gridcolor="rgba(0,0,0,0.12)",
            ),
            angularaxis=dict(
                tickfont=dict(size=13),
                gridcolor="rgba(0,0,0,0.08)",
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=True,
        legend=dict(x=0.85, y=1.1),
        height=520,
        margin=dict(t=80, b=40, l=60, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    with st.container(border=True):
        st.subheader("Energy snapshot")
        st.caption("Total daily energy demand per zone (radial view).")
        st.plotly_chart(fig_snap, use_container_width=True)


# The map and charts are driven by the time-of-day slider (single manual clock);
# there is no auto-advance loop — scrubbing the slider reruns and redraws once.

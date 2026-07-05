"""
DomCenter — V2G mobility visualiser (Streamlit entry point).

Reads a pre-baked scenario xlsx from `data/scenarios/` and an optional OSM
snapshot from `data/osm/`, then renders one animated Plotly dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data_loader import (
    list_scenarios,
    load_scenario,
    load_osm_clusters,
    load_landuse_layers,
    osm_cache_ready,
)
from app.simulation import build_simulation
from app.charts import build_dashboard_figure


st.set_page_config(
    page_title="DomCenter — V2G Mobility",
    # page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .small-note { color: #666; font-size: 0.85em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar — scenario picker
# ----------------------------------------------------------------------------

st.sidebar.title("EV mobility simulation")
st.sidebar.caption("Electric mobility simulation viewer")

scenarios = list_scenarios()
if not scenarios:
    st.sidebar.error("No scenario files found in `data/scenarios/`.")
    st.stop()

# ----------------------- EN SCENARIJ
#if "scenario_idx" not in st.session_state:
#    st.session_state.scenario_idx = 0
#
#st.sidebar.subheader("Scenarios")
#for i, (label, _path) in enumerate(scenarios):
#    is_active = i == st.session_state.scenario_idx
#    if st.sidebar.button(("● " if is_active else "○ ") + label,
#                          key=f"sc_{i}", use_container_width=True):
#        st.session_state.scenario_idx = i
#        st.rerun()

# ----------------------- EN SCENARIJ

# ----------------------- VEČ SCENARIJEV
st.sidebar.subheader("Scenarios")

scenario_labels = [label for label, _ in scenarios]

selected_labels = st.sidebar.multiselect(
    "Select scenarios",
    scenario_labels,
    default=[scenario_labels[0]],
)
# ----------------------- VEČ SCENARIJEV


st.sidebar.divider()
st.sidebar.subheader("Display")
show_osm = st.sidebar.checkbox("Show OSM zones", value=True)
show_clusters = st.sidebar.checkbox("Show cluster markers", value=False)
show_heatmap = st.sidebar.checkbox(
    "Show vehicle heatmap", value=False,
    help="Overlay a density heatmap of vehicle positions on the map.",
)

st.sidebar.divider()
with st.sidebar.expander("About"):
    st.markdown(
        "Master's thesis project on Vehicle-to-Grid (V2G) load flexibility. "
    )

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

# ----------------------- EN SCENARIJ
#scenario_label, scenario_path = scenarios[st.session_state.scenario_idx]
#
#st.title("V2G mobility — Krško, Slovenia")
#st.caption(f"Active scenario: **{scenario_label}**")
#
#df = load_scenario(str(scenario_path))
#sim = build_simulation(df)
# ----------------------- EN SCENARIJ

# ----------------------- VEČ SCENARIJEV
selected_scenarios = [
    (label, path)
    for label, path in scenarios
    if label in selected_labels
]

st.title("V2G mobility — Krško, Slovenia")

if selected_labels:
    st.caption(
        "Active scenarios: "
        + ", ".join([f"**{x}**" for x in selected_labels])
    )

dfs = []

vehicle_offset = 0

for _, path in selected_scenarios:
    temp = load_scenario(str(path)).copy()

    temp["Vehicle ID"] += vehicle_offset

    vehicle_offset = temp["Vehicle ID"].max()

    dfs.append(temp)

df = pd.concat(dfs, ignore_index=True)

sim = build_simulation(df)

# ----------------------- VEČ SCENARIJEV


# KPI strip
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vehicles", sim.n_vehicles)
c2.metric("Peak charging demand", f"{sim.charging_max_total.max():.1f} kW")
c3.metric("Work arrivals", int(sim.arrivals_hist.sum()))
if sim.has_flex:
    c4.metric("Peak pos. flexibility", f"{sim.cum_pos_flex.max():.1f} kWh")
else:
    c4.metric("SoC flexibility", "—")

st.divider()

landuse_layers = load_landuse_layers() if show_osm else None
osm_clusters = load_osm_clusters() if show_clusters else None

if show_osm and not landuse_layers:
    st.info(
        "OSM zone overlay is empty. Run `python scripts/build_osm_cache.py` "
        "from the project root to generate `data/osm/`.",
        icon="ℹ️",
    )

fig = build_dashboard_figure(
    sim,
    landuse_layers=landuse_layers,
    osm_clusters=osm_clusters,
    show_heatmap=show_heatmap,
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Show raw scenario data"):
    st.dataframe(df, use_container_width=True)

st.markdown(
    '<p class="small-note">Tip: hit ▶ Play to animate the 24-hour day, or '
    "drag the slider to scrub. The three charts redraw progressively in sync "
    "with the map.</p>",
    unsafe_allow_html=True,
)

if not osm_cache_ready():
    st.markdown(
        '<p class="small-note">OSM snapshot not built yet. Without it the '
        "basemap shows plain CartoDB-Positron tiles. To enable zone shading "
        "and cluster markers, run the build script locally.</p>",
        unsafe_allow_html=True,
    )

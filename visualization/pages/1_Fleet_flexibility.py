"""Fleet flexibility by penetration scenario (aggregated view).

This page does not animate individual vehicles. It reads small pre-computed
summaries produced by `pipeline/pipeline/flex_aggregation.py` (copied to
`visualization/data/flex/` as parquet), so it stays fast for all five
scenarios, up to 16,803 vehicles.

Bounds (decision: option C, dual bounds):
  upper = all parked vehicles (home, work, other)  -> charger everywhere
  lower = vehicles parked at work only             -> charger at work only
Vehicles that are driving are not counted.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

FLEX_DIR = Path(__file__).resolve().parent.parent / "data" / "flex"

SCENARIO_LABELS = {
    "06_13pct": "6.13 % · 1,030 EV",
    "10pct": "10 % · 1,680 EV",
    "20pct": "20 % · 3,360 EV",
    "50pct": "50 % · 8,401 EV",
    "100pct": "100 % · 16,803 EV",
}
CATEGORY_LABELS = {
    "stanovanjsko": "Residential",
    "industrijsko": "Industrial",
    "poslovno": "Commercial",
    "izobrazevalno": "Education",
    "zelene_povrsine": "Parks / green",
    "delovno_neopredeljeno": "Work (untagged building)",
    "drugo_neopredeljeno": "Other (untagged building)",
    "stavba_brez_oznake": "Untagged building",
    "brez_podatka": "No data",
}
HOUR_TICKS = [f"{h:02d}:00" for h in range(0, 24, 2)]


@st.cache_data(show_spinner=False)
def _read(name: str) -> pd.DataFrame:
    return pd.read_parquet(FLEX_DIR / f"{name}.parquet")


def _available() -> list[str]:
    return [k for k in SCENARIO_LABELS if (FLEX_DIR / f"flex_timeline_{k}.parquet").exists()]


st.set_page_config(page_title="Fleet flexibility", layout="wide")
st.title("Fleet flexibility by scenario")
st.caption(
    "Upper bound: all parked vehicles (charger everywhere). "
    "Lower bound: vehicles parked at work only. Driving vehicles are not counted."
)

scenarios = _available()
if not scenarios:
    st.warning(
        "No flexibility summaries in `visualization/data/flex/`. Run "
        "`pipeline/pipeline/flex_aggregation.py` and convert its output to parquet.",
        icon="⚠️",
    )
    st.stop()

with st.sidebar:
    selected = st.multiselect(
        "Scenarios", scenarios, default=scenarios[:1],
        format_func=lambda s: SCENARIO_LABELS.get(s, s),
    )
    direction = st.radio(
        "Flexibility direction", ["pos", "neg"],
        format_func=lambda m: "Discharge to grid (Pos, V2G)" if m == "pos" else "Charge from grid (Neg)",
    )

if not selected:
    st.info("Select at least one scenario in the sidebar.")
    st.stop()

# ── KPIs ───────────────────────────────────────────────────────────────────────
summary = _read("flex_summary")
row = summary[summary["scenarij"] == selected[-1]].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vehicles", f"{int(row['vozila']):,}")
c2.metric("Upper bound peak (Pos)", f"{row['pos_zgornja_max_kWh'] / 1000:,.1f} MWh")
c3.metric("Lower bound peak (Pos)", f"{row['pos_spodnja_max_kWh'] / 1000:,.1f} MWh")
c4.metric("Share parked (daily mean)", f"{row['delez_parkiranih_povp'] * 100:.1f} %")
st.caption(f"KPIs refer to {SCENARIO_LABELS[selected[-1]]}.")

# ── Timeline ───────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("Over the day")
    fig = go.Figure()
    for s in selected:
        tl = _read(f"flex_timeline_{s}")
        fig.add_trace(go.Scatter(x=tl["Cas"], y=tl[f"{direction}_flex_kWh_zgornja"] / 1000,
                                 name=f"{SCENARIO_LABELS[s]} — upper", mode="lines"))
        fig.add_trace(go.Scatter(x=tl["Cas"], y=tl[f"{direction}_flex_kWh_spodnja"] / 1000,
                                 name=f"{SCENARIO_LABELS[s]} — lower", mode="lines",
                                 line=dict(dash="dot")))
    fig.update_layout(height=420, hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10),
                      yaxis_title="Flexibility [MWh]", xaxis_title="Time of day",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    fig.update_xaxes(tickmode="array", tickvals=HOUR_TICKS)
    st.plotly_chart(fig, use_container_width=True)

# ── By zone type ───────────────────────────────────────────────────────────────
zone_scenario = st.selectbox("Scenario for zone views", selected,
                             format_func=lambda s: SCENARIO_LABELS.get(s, s))

with st.container(border=True):
    st.subheader("By zone type (upper bound)")
    kat = _read(f"flex_by_landuse_{zone_scenario}")
    kat["zone"] = kat["kategorija"].map(CATEGORY_LABELS).fillna(kat["kategorija"])
    col = f"{direction}_zgornja"
    area = kat.pivot_table(index="Cas", columns="zone", values=col, aggfunc="sum").fillna(0).sort_index()
    fig2 = px.area(area / 1000, labels={"value": "Flexibility [MWh]", "Cas": "Time of day", "zone": "Zone"})
    fig2.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10),
                       legend=dict(orientation="h", yanchor="bottom", y=1.02))
    fig2.update_xaxes(tickmode="array", tickvals=HOUR_TICKS)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Zone type comes from the vehicle state (home / work / other) and OSM tags. "
        "Most buildings in Krško are tagged only `building=yes`; where no usable tag exists "
        "the zone is shown as untagged."
    )

# ── Grid map ───────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("By 0.5 km grid cell (upper bound)")
    cells = _read(f"flex_by_cell_{zone_scenario}")
    hours = sorted(cells["Cas"].unique())
    hour = st.select_slider("Time of day", options=hours, value="12:00" if "12:00" in hours else hours[0])
    snap = cells[cells["Cas"] == hour].copy()
    snap["flex_MWh"] = snap[f"{direction}_zgornja"] / 1000
    kwargs = dict(lat="sredisce_lat", lon="sredisce_lon", size="flex_MWh", color="flex_MWh",
                  hover_data={"celica": True, "vozila_zgornja": True, "flex_MWh": ":.2f",
                              "sredisce_lat": False, "sredisce_lon": False},
                  color_continuous_scale="Viridis", size_max=28, zoom=10, height=520)
    # plotly >= 6: scatter_map, older: scatter_mapbox
    if hasattr(px, "scatter_map"):
        fig3 = px.scatter_map(snap, map_style="carto-positron", **kwargs)
    else:
        fig3 = px.scatter_mapbox(snap, mapbox_style="carto-positron", **kwargs)
    fig3.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)

with st.expander("Summary table, all scenarios"):
    st.dataframe(summary, use_container_width=True)

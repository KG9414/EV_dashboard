"""Agregirana prožnost flote po scenarijih penetracije.

Ta stran ne animira posameznih vozil — bere povzetke, ki jih pripravi
`pipeline/flex_aggregation.py`, zato deluje tudi pri 16.803 vozilih.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.aggregates import (
    SCENARIO_LABELS,
    available_scenarios,
    flex_data_ready,
    load_by_cell,
    load_by_landuse,
    load_summary,
    load_timeline,
)

st.set_page_config(page_title="Prožnost scenarijev", layout="wide")

st.title("Prožnost flote po scenarijih")
st.caption(
    "Zgornja meja šteje vsa parkirana vozila (polnilnica povsod), "
    "spodnja meja samo vozila na delovnem mestu. Vozila med vožnjo se ne štejejo."
)

if not flex_data_ready():
    st.warning(
        "Povzetkov prožnosti ni v `data/flex/`. Poženi "
        "`python pipeline/flex_aggregation.py` in kopiraj mapo `05_Flexibility` "
        "v `data/flex/`.",
        icon="⚠️",
    )
    st.stop()

scenarios = available_scenarios()
selected = st.sidebar.multiselect(
    "Scenariji",
    scenarios,
    default=scenarios[:1],
    format_func=lambda s: SCENARIO_LABELS.get(s, s),
)
if not selected:
    st.info("Izberi vsaj en scenarij v stranski vrstici.")
    st.stop()

metric = st.sidebar.radio(
    "Smer prožnosti",
    ["pos", "neg"],
    format_func=lambda m: "Oddaja v omrežje (Pos)" if m == "pos" else "Sprejem iz omrežja (Neg)",
)
unit_div, unit = (1000.0, "MWh")

# ---------------------------------------------------------------- povzetek

summary = load_summary()
if summary is not None:
    sel_sum = summary[summary["scenarij"].isin(selected)]
    if not sel_sum.empty:
        row = sel_sum.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Vozila", f"{int(row['vozila']):,}".replace(",", "."))
        c2.metric("Najvišja zgornja meja", f"{row['pos_zgornja_max_kWh'] / unit_div:,.1f} {unit}")
        c3.metric("Najvišja spodnja meja", f"{row['pos_spodnja_max_kWh'] / unit_div:,.1f} {unit}")
        c4.metric("Povprečno parkiranih", f"{row['delez_parkiranih_povp'] * 100:.1f} %")
        st.caption(f"Vrednosti veljajo za scenarij {SCENARIO_LABELS.get(row['scenarij'], row['scenarij'])}.")

# ---------------------------------------------------------------- časovni potek

st.subheader("Potek čez dan")

fig = go.Figure()
for s in selected:
    tl = load_timeline(s)
    label = SCENARIO_LABELS.get(s, s)
    fig.add_trace(go.Scatter(
        x=tl["Cas"], y=tl[f"{metric}_flex_kWh_zgornja"] / unit_div,
        name=f"{label} — zgornja", mode="lines",
    ))
    fig.add_trace(go.Scatter(
        x=tl["Cas"], y=tl[f"{metric}_flex_kWh_spodnja"] / unit_div,
        name=f"{label} — spodnja", mode="lines", line=dict(dash="dot"),
    ))
fig.update_layout(
    height=420, hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10),
    yaxis_title=f"Prožnost [{unit}]", xaxis_title="Ura",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
fig.update_xaxes(tickmode="array", tickvals=[f"{h:02d}:00" for h in range(0, 24, 2)])
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- po območjih

st.subheader("Razporeditev po tipu območja (zgornja meja)")

zone_scenario = st.selectbox(
    "Scenarij za prikaz po območjih",
    selected,
    format_func=lambda s: SCENARIO_LABELS.get(s, s),
)
by_kat = load_by_landuse(zone_scenario)
col = "pos_zgornja" if metric == "pos" else "neg_zgornja"
area = by_kat.pivot_table(index="Cas", columns="kategorija_naziv", values=col, aggfunc="sum").fillna(0)
area = area.sort_index()
fig2 = px.area(area / unit_div, labels={"value": f"Prožnost [{unit}]", "Cas": "Ura", "kategorija_naziv": "Območje"})
fig2.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10),
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
fig2.update_xaxes(tickmode="array", tickvals=[f"{h:02d}:00" for h in range(0, 24, 2)])
st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "Kategorija izhaja iz stanja vozila (doma, delo, drugo) in oznak OSM. "
    "Oznaki »brez oznake« pomenita stavbo brez uporabne oznake v OSM."
)

# ---------------------------------------------------------------- zemljevid celic

st.subheader("Prožnost po celicah mreže 0,5 km")

cells = load_by_cell(zone_scenario)
hour = st.select_slider("Ura", options=sorted(cells["Cas"].unique()), value="12:00")
snap = cells[cells["Cas"] == hour].copy()
snap["prožnost_MWh"] = snap["pos_zgornja"] / unit_div

map_kwargs = dict(
    lat="sredisce_lat", lon="sredisce_lon",
    size="pos_zgornja", color="prožnost_MWh",
    hover_data={"celica": True, "vozila_zgornja": True, "prožnost_MWh": ":.2f",
                "sredisce_lat": False, "sredisce_lon": False, "pos_zgornja": False},
    color_continuous_scale="Viridis", size_max=28, zoom=10, height=520,
)
# plotly >= 6 uporablja scatter_map, starejše različice scatter_mapbox
if hasattr(px, "scatter_map"):
    fig3 = px.scatter_map(snap, map_style="carto-positron", **map_kwargs)
else:
    fig3 = px.scatter_mapbox(snap, mapbox_style="carto-positron", **map_kwargs)
fig3.update_layout(margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig3, use_container_width=True)

with st.expander("Tabela celic ob izbrani uri"):
    st.dataframe(
        snap[["celica", "sredisce_lat", "sredisce_lon", "vozila_zgornja", "pos_zgornja", "neg_zgornja"]]
        .sort_values("pos_zgornja", ascending=False),
        use_container_width=True,
    )

with st.expander("Povzetek vseh scenarijev"):
    if summary is not None:
        st.dataframe(summary, use_container_width=True)

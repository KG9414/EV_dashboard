"""
One animated Plotly figure that replaces the matplotlib dashboard:

  ┌──────────────────────────────────────┐
  │              MAP                     │     row 1 (mapbox)
  ├───────────────┬──────────┬───────────┤
  │ Charging      │ Work     │ SoC       │     row 2 (3 line/bar plots)
  │ demand (min/  │ arrivals/│ flexibil. │
  │  max)         │ departs  │ (±)       │
  └───────────────┴──────────┴───────────┘

A single slider + Play/Pause control drives every subplot. Each frame is a
"draw up to t" snapshot — that's the live-drawing effect.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import pydeck as pdk

from .simulation import (
    Simulation,
    TRIP_TYPE_COLORS,
    WORK_COLOR,
    DT_H,
)


# ----------------------------------------------------------------------------
# OSM landuse layer helper
# ----------------------------------------------------------------------------

# (category-name, fill-colour, fill-opacity)
LANDUSE_STYLE = {
    "residential": ("#2c7bb6", 0.18),
    "industrial":  ("#d7191c", 0.18),
    "commercial":  ("#fdae61", 0.22),
    "parks":       ("#1a9641", 0.22),
    "education":   ("#984ea3", 0.25),
}


def _mapbox_layers(landuse_layers: Optional[dict]) -> list[dict]:
    """Translate per-category GeoJSON dicts into mapbox.layers entries."""
    if not landuse_layers:
        return []
    layers = []
    for cat, geojson in landuse_layers.items():
        if not geojson or "features" not in geojson or not geojson["features"]:
            continue
        color, opacity = LANDUSE_STYLE.get(cat, ("#888", 0.15))
        layers.append(
            dict(
                sourcetype="geojson",
                source=geojson,
                type="fill",
                color=color,
                opacity=opacity,
                below="traces",
            )
        )
    return layers


# ----------------------------------------------------------------------------
# Per-frame trace builders
# ----------------------------------------------------------------------------

def _vehicle_trace(sim: Simulation, frame: int) -> go.Scattermapbox:
    lons = sim.positions[:, frame, 0]
    lats = sim.positions[:, frame, 1]
    colors = [TRIP_TYPE_COLORS.get(sim.trip_types[i, frame], "#64748B")
              for i in range(sim.n_vehicles)]
    labels = [f"V{i+1} · {sim.trip_types[i, frame]}" for i in range(sim.n_vehicles)]
    return go.Scattermapbox(
        lon=lons, lat=lats,
        mode="markers",
        marker=dict(size=11, color=colors),
        text=labels, hoverinfo="text",
        name="Vehicles",
        showlegend=False,
    )


def _heatmap_trace(sim: Simulation, frame: int) -> go.Densitymapbox:
    """
    Improved urban-density heatmap.
    """

    lons = sim.positions[:, frame, 0]
    lats = sim.positions[:, frame, 1]

    # Parked vehicles dominate the heatmap
    weights = np.where(
        sim.trip_types[:, frame] == "Driving",
        0.05,
        2.5,
    )

    return go.Densitymapbox(
        lon=lons,
        lat=lats,
        z=weights,

        radius=55,

        opacity=0.90,

        colorscale=[
            [0.00, "rgba(0,0,0,0)"],
            [0.10, "rgba(120,0,255,0.45)"],
            [0.25, "rgba(0,80,255,0.60)"],
            [0.45, "rgba(0,220,255,0.75)"],
            [0.65, "rgba(255,220,0,0.85)"],
            [0.82, "rgba(255,120,0,0.92)"],
            [1.00, "rgba(255,0,0,0.98)"],
        ],

        showscale=False,

        hoverinfo="skip",

        name="Density",
    )

def _work_glow_trace(sim: Simulation, frame: int) -> go.Scattermapbox:
    if sim.work_location is None:
        return go.Scattermapbox(lon=[], lat=[], mode="markers", showlegend=False)
    n_work = sim.vehicles_at_work(frame)
    base = 18 + 4 * n_work
    return go.Scattermapbox(
        lon=[sim.work_location[0]],
        lat=[sim.work_location[1]],
        mode="markers",
        marker=dict(size=base, color=WORK_COLOR, opacity=0.85),
        text=[f"Workplace · {n_work} vehicles"], hoverinfo="text",
        name="Workplace",
        showlegend=False,
    )


def _progressive(arr: np.ndarray, frame: int, t_axis: np.ndarray):
    """Return (x[:frame+1], arr[:frame+1])."""
    return t_axis[: frame + 1], arr[: frame + 1]


# ----------------------------------------------------------------------------
# Main figure builder
# ----------------------------------------------------------------------------

def build_dashboard_figure(
    sim: Simulation,
    *,
    landuse_layers: Optional[dict] = None,
    osm_clusters: Optional[dict] = None,
    show_heatmap: bool = False,
    zoom: float = 13.2,
    map_height: int = 520,
    chart_height: int = 240,
) -> go.Figure:

    t_axis = sim.time_axis_hours
    e_min = sim.charging_min_total
    e_max = sim.charging_max_total

    # ----- subplot grid: -----
    fig = make_subplots(
        rows=3,
        cols=2,

        specs=[
            [{"type": "xy"}, {"type": "mapbox", "rowspan": 3}],
            [{"type": "xy"}, None],
            [{"type": "xy"}, None],
        ],

        column_widths=[0.38, 0.62],

        row_heights=[0.33, 0.33, 0.34],

        vertical_spacing=0.08,
        horizontal_spacing=0.04,

        subplot_titles=(
            "Workplace charging demand (kW)",
            "",
            "Work arrivals / departures",
            "Cumulative SoC flexibility (kWh)",
        ),
    )

    # ----- base traces at frame 0 -----
    # Heatmap goes *first* so vehicle markers + glow render on top of it.
    if show_heatmap:
        fig.add_trace(_heatmap_trace(sim, 0), row=1, col=2)
    fig.add_trace(_vehicle_trace(sim, 0), row=1, col=2)
    fig.add_trace(_work_glow_trace(sim, 0), row=1, col=2)

    # OSM cluster centroids (static, all frames)
    if osm_clusters:
        cluster_pts = [(name, lon, lat) for name, (lon, lat) in osm_clusters.items() if lon and lat]
        if cluster_pts:
            fig.add_trace(
                go.Scattermapbox(
                    lon=[p[1] for p in cluster_pts],
                    lat=[p[2] for p in cluster_pts],
                    mode="markers+text",
                    marker=dict(size=8, color="rgba(50,50,50,0.65)"),
                    text=[p[0] for p in cluster_pts],
                    textposition="top right",
                    textfont=dict(size=10, color="#333"),
                    hoverinfo="text",
                    name="OSM clusters",
                    showlegend=False,
                ),
                row=1, col=2,
            )

    # Charging demand: min line + max line (we'll fake fill via 'tonexty')
    x0, y0 = _progressive(e_min, 0, t_axis)
    fig.add_trace(
        go.Scatter(x=x0, y=y0, mode="lines",
                   line=dict(color="#2563EB", width=2),
                   name="Min charging power", showlegend=False),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=_progressive(e_max, 0, t_axis)[0], y=_progressive(e_max, 0, t_axis)[1],
                   mode="lines", line=dict(color="#2563EB", width=1, dash="dot"),
                   fill="tonexty", fillcolor="rgba(37,99,235,0.18)",
                   name="Max charging power", showlegend=False),
        row=1, col=1,
    )

    # Arrivals + departures: bars
    fig.add_trace(
        go.Bar(x=t_axis, y=np.zeros_like(t_axis),
               marker_color="#EA580C", name="Arrivals", showlegend=False),
        row=2, col=1,
    )
    fig.add_trace(
        go.Bar(x=t_axis, y=np.zeros_like(t_axis),
               marker_color="#2563EB", name="Departures", showlegend=False),
        row=2, col=1,
    )

    # SoC flexibility — plot cumsum(-raw) directly (matches flexibility_plot.py
    # convention: positive flex above zero, negative below).
    pos_plot = sim.cum_pos_flex
    neg_plot = sim.cum_neg_flex
    fig.add_trace(
        go.Scatter(x=t_axis[:1], y=pos_plot[:1], mode="lines",
                   line=dict(color="#2563EB", width=2), name="Positive flex",
                   showlegend=False),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(x=t_axis[:1], y=neg_plot[:1], mode="lines",
                   line=dict(color="#DC2626", width=2), name="Negative flex",
                   showlegend=False),
        row=3, col=1,
    )

    # Indices of the traces we want frames to update.
    # Order on the figure: [heatmap?] vehicles, work-glow, [clusters static], charts...
    heatmap_offset = 1 if show_heatmap else 0
    veh_idx       = 0 + heatmap_offset
    glow_idx      = 1 + heatmap_offset
    has_clusters  = bool(osm_clusters and any(v for v in osm_clusters.values()))
    cluster_offset = 1 if has_clusters else 0
    base_offset   = heatmap_offset + cluster_offset
    charging_min_idx = 2 + base_offset
    charging_max_idx = 3 + base_offset
    arr_idx          = 4 + base_offset
    dep_idx          = 5 + base_offset
    flex_pos_idx     = 6 + base_offset
    flex_neg_idx     = 7 + base_offset

    # ----- animation frames -----
    frames = []
    for f in range(sim.n_intervals):
        # Mask out arrivals/departures past frame
        arr_y = sim.arrivals_hist.copy()
        dep_y = sim.departures_hist.copy()
        arr_y[f + 1 :] = 0
        dep_y[f + 1 :] = 0

        emin_x, emin_y = _progressive(e_min, f, t_axis)
        emax_x, emax_y = _progressive(e_max, f, t_axis)
        pos_x, pos_y = _progressive(pos_plot, f, t_axis)
        neg_x, neg_y = _progressive(neg_plot, f, t_axis)

        frame_traces = []
        trace_indices = []

        if show_heatmap:
            frame_traces.append(_heatmap_trace(sim, f))
            trace_indices.append(0)

        frame_traces.extend([
            _vehicle_trace(sim, f),
            _work_glow_trace(sim, f),
            go.Scatter(x=emin_x, y=emin_y, mode="lines",
                       line=dict(color="#2563EB", width=2)),
            go.Scatter(x=emax_x, y=emax_y, mode="lines",
                       line=dict(color="#2563EB", width=1, dash="dot"),
                       fill="tonexty", fillcolor="rgba(37,99,235,0.18)"),
            go.Bar(x=t_axis, y=arr_y, marker_color="#EA580C"),
            go.Bar(x=t_axis, y=dep_y, marker_color="#2563EB"),
            go.Scatter(x=pos_x, y=pos_y, mode="lines",
                       line=dict(color="#2563EB", width=2)),
            go.Scatter(x=neg_x, y=neg_y, mode="lines",
                       line=dict(color="#DC2626", width=2)),
        ])
        # Frame trace indices in figure (skip cluster markers which are static).
        trace_indices.extend([veh_idx, glow_idx,
                              charging_min_idx, charging_max_idx,
                              arr_idx, dep_idx,
                              flex_pos_idx, flex_neg_idx])

        hh = (f * 15) // 60
        mm = (f * 15) % 60
        frames.append(go.Frame(data=frame_traces, traces=trace_indices,
                               name=f"{hh:02d}:{mm:02d}"))
    fig.frames = frames

    # ----- mapbox config -----
    center_lon = float(np.mean(sim.positions[:, 0, 0]))
    center_lat = float(np.mean(sim.positions[:, 0, 1]))
    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center=dict(lon=center_lon, lat=center_lat),
            zoom=zoom,
            layers=_mapbox_layers(landuse_layers),
        ),
    )

    # ----- axes for the three charts -----
    fig.update_xaxes(title_text="Time (h)", range=[0, 24], dtick=3, row=1, col=1)
    fig.update_yaxes(title_text="kW",
                     range=[0, max(float(e_max.max()) * 1.2, 1)],
                     row=1, col=1)

    fig.update_xaxes(title_text="Time (h)", range=[0, 24], dtick=3, row=2, col=1)
    max_bar = max(float((sim.arrivals_hist + sim.departures_hist).max()), 1)
    fig.update_yaxes(title_text="Vehicles", range=[0, max_bar * 1.4 + 1],
                     row=2, col=1)

    fig.update_xaxes(title_text="Time (h)", range=[0, 24], dtick=3, row=3, col=1)
    if sim.has_flex:
        all_vals = np.concatenate([pos_plot, neg_plot])
        lo = float(min(all_vals.min(), 0) * 1.2)
        hi = float(max(all_vals.max(), 0) * 1.2) or 1.0
        fig.update_yaxes(title_text="kWh", range=[lo, hi], row=3, col=1)
    else:
        fig.update_yaxes(title_text="kWh", range=[-1, 1], row=3, col=1)
        fig.add_annotation(
            xref="x3 domain", yref="y3 domain",
            x=0.5, y=0.5, showarrow=False,
            text="No SoC-flex columns in this scenario",
            font=dict(size=12, color="#888"),
            row=3, col=1,
        )

    # Bars overlap; group them.
    fig.update_layout(barmode="relative")

    # ----- player & slider -----
    fig.update_layout(
        height=950,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#F7F9FC",
        font=dict(family="DejaVu Sans, sans-serif", color="#1f2330"),
        showlegend=False,
        updatemenus=[
            dict(
                type="buttons", direction="left",
                x=0.02, y=-0.05, xanchor="left", yanchor="top",
                pad=dict(t=0, r=10),
                showactive=False,
                bgcolor="rgba(255,255,255,0.9)",
                buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=400, redraw=True),
                                          fromcurrent=True,
                                          transition=dict(duration=0))]),
                    dict(label="❚❚ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False),
                                            mode="immediate",
                                            transition=dict(duration=0))]),
                ],
            )
        ],
        sliders=[
            dict(
                active=0,
                x=0.08, y=-0.05, len=0.9,
                pad=dict(t=10, b=5),
                currentvalue=dict(prefix="Time: ", font=dict(size=14)),
                steps=[
                    dict(method="animate", label=fr.name,
                         args=[[fr.name],
                               dict(mode="immediate",
                                    frame=dict(duration=0, redraw=True),
                                    transition=dict(duration=0))])
                    for fr in frames
                ],
            )
        ],
    )

    return fig

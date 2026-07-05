# chart_functions.py — Preserved from Krsko-heatmap-v2.py
# All chart types, colors, axis labels, and visual logic are unchanged.
# Global state removed: functions accept data dict + time step t.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Circle, Wedge, FancyBboxPatch
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from data_loader import (
    ZONE_COLORS, TRIP_TYPE_COLORS, _ZONE_ORDER, _ENERGY_ZONE_ORDER,
    DT_H,
)

# ─── Global style (preserved from Krsko-heatmap-v2) ─────────────────────────

C_BLUE   = "#2563EB"
C_ORANGE = "#EA580C"
C_GREEN  = "#16A34A"
C_RED    = "#DC2626"
C_PURPLE = "#7C3AED"
C_GRAY   = "#64748B"
C_PANEL  = "#EEF2FF"

# Card-blended theme: transparent figure + axes so charts sit *inside* the
# white Streamlit cards instead of looking like a screenshot pasted on a grey
# panel. Spines are dropped to a single soft baseline and the grid is faint.
_RCPARAMS = {
    "figure.facecolor":  "none",
    "savefig.facecolor": "none",
    "axes.facecolor":    "none",
    "axes.edgecolor":    "#CBD5E1",
    "axes.linewidth":    0.8,
    "axes.grid":         True,
    "axes.grid.axis":    "y",
    "grid.color":        "#EEF2F7",
    "grid.linewidth":    0.8,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.spines.left":  False,
    "text.color":        "#1E293B",
    "axes.labelcolor":   "#475569",
    "xtick.color":       "#64748B",
    "ytick.color":       "#64748B",
    "font.family":       "DejaVu Sans",
    "axes.titlesize":    11,
    "axes.titleweight":  "bold",
    "axes.titlecolor":   "#1E293B",
    "axes.labelsize":    9,
    "xtick.labelsize":   8.5,
    "ytick.labelsize":   8.5,
    "legend.fontsize":   8,
    "legend.framealpha": 0.0,
    "legend.edgecolor":  "none",
}


# ─── Plotly theming (main-tab interactive charts) ────────────────────────────

def _plotly_card_layout(fig, height=260, title=None):
    """Apply the transparent, card-blended look to a Plotly figure so it sits
    inside a Streamlit card like the reference dashboard (no chrome, soft grid,
    legend on top, tight margins)."""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=38 if title else 14, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif",
                  size=12, color="#475569"),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right",
                    x=1.0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#1E293B", font_size=12, font_color="white"),
        bargap=0.15,
    )
    if title:
        fig.update_layout(title=dict(text=title, x=0.0, xanchor="left",
                                     font=dict(size=15, color="#1E293B")))
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False,
                     ticks="outside", tickcolor="#CBD5E1", color="#64748B")
    fig.update_yaxes(showgrid=True, gridcolor="#EEF2F7", zeroline=False,
                     showline=False, color="#64748B")
    return fig


def create_arrivals_plotly(data, t, show_2trips=True, show_4trips=True):
    """Interactive work arrivals / departures chart (Plotly, card-blended).

    Full-day distribution as stacked bars (arrivals + departures) with a dotted
    marker at the current time. Replaces the matplotlib version on the main tab
    so it matches the site's card aesthetic and supports hover."""
    import plotly.graph_objects as go

    intervals = data["intervals"]
    t = min(t, intervals - 1)
    if show_2trips and not show_4trips:
        ha, hd = data["arr_hist2"], data["dep_hist2"]
    elif show_4trips and not show_2trips:
        ha, hd = data["arr_hist4"], data["dep_hist4"]
    elif show_2trips or show_4trips:
        ha, hd = data["arr_hist_total"], data["dep_hist_total"]
    else:
        ha = hd = np.zeros(intervals)

    hours = np.arange(intervals) * DT_H
    fig = go.Figure()
    fig.add_bar(x=hours, y=ha, name="Arrivals", marker_color=C_ORANGE,
                marker_line_width=0, width=DT_H * 0.85,
                hovertemplate="%{x:.2f} h<br>Arrivals: %{y:.0f}<extra></extra>")
    fig.add_bar(x=hours, y=hd, name="Departures", marker_color=C_BLUE,
                marker_line_width=0, width=DT_H * 0.85,
                hovertemplate="%{x:.2f} h<br>Departures: %{y:.0f}<extra></extra>")
    fig.add_vline(x=t * DT_H, line_dash="dot", line_color=C_RED,
                  line_width=1.5, opacity=0.6)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(range=[0, 24], tickvals=list(range(0, 25, 3)),
                     ticktext=[f"{h:02d}h" for h in range(0, 25, 3)],
                     title_text="Time of day")
    fig.update_yaxes(title_text="Vehicles", rangemode="tozero")
    return _plotly_card_layout(fig, height=260)


# ─── Main left-panel figure (4 charts stacked) ───────────────────────────────

def create_main_charts(data, t, show_2trips=True, show_4trips=True):
    """
    Create the 4-subplot figure shown in the left column of the main dashboard.
    Matches the original layout: charging demand, trip clock, arrivals, flexibility.
    Returns a matplotlib Figure.
    """
    plt.rcParams.update(_RCPARAMS)

    intervals = data["intervals"]
    t = min(t, intervals - 1)
    nf = t + 1
    t_axis = np.arange(intervals) * 0.25
    x_t    = np.arange(nf) * 0.25

    fig = plt.figure(figsize=(11, 9))
    fig.patch.set_alpha(0.0)
    gs = gridspec.GridSpec(
        2, 2, figure=fig,
        hspace=0.55, wspace=0.38,
        left=0.09, right=0.97, top=0.96, bottom=0.07,
    )
    ax_energy   = fig.add_subplot(gs[0, 0])
    ax_clock    = fig.add_subplot(gs[0, 1])
    ax_arrivals = fig.add_subplot(gs[1, 0])
    ax_flex     = fig.add_subplot(gs[1, 1])

    ax_clock.set_facecolor("none")

    _draw_charging_demand(ax_energy,   data, t, nf, x_t, show_2trips, show_4trips)
    _draw_trip_clock(     ax_clock,    data, t)
    _draw_arrivals(       ax_arrivals, data, t, nf, intervals, show_2trips, show_4trips)
    _draw_flexibility(    ax_flex,     data, t, nf, x_t, t_axis)

    return fig


# ─── Charging demand ──────────────────────────────────────────────────────────

def _draw_charging_demand(ax, data, t, nf, x_t, show_2trips, show_4trips):
    """Workplace parking charging demand. Preserved from Krsko-heatmap-v2."""
    e_min2, e_max2 = data["e_min2"], data["e_max2"]
    e_min4, e_max4 = data["e_min4"], data["e_max4"]

    y2_min = e_min2[:nf] if show_2trips else np.zeros(nf)
    y4_min = e_min4[:nf] if show_4trips else np.zeros(nf)
    y2_max = e_max2[:nf] if show_2trips else np.zeros(nf)
    y4_max = e_max4[:nf] if show_4trips else np.zeros(nf)

    total_min = y2_min + y4_min
    total_max = y2_max + y4_max

    ax.plot(x_t, total_min, lw=2, color=C_BLUE,   label="Minimum demand")
    ax.plot(x_t, total_max, lw=2, color=C_ORANGE, label="Maximum demand")

    if nf > 1:
        ax.fill_between(x_t, total_min, total_max, alpha=0.18, color="#94A3B8")

    ymax = max(float(total_max.max()), 1) if len(total_max) > 0 else 1
    t_now = t * 0.25
    ax.plot([t_now, t_now], [0, ymax * 1.15], color=C_RED, lw=1, ls=":", alpha=0.6)

    ax.legend(ncol=2, loc="upper right", fontsize=6.5, frameon=True, borderpad=0.4)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, ymax * 1.15)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)])
    ax.set_title("Workplace Parking Charging Demand", pad=6)
    ax.set_ylabel("kW")


# ─── Trip chain clock ─────────────────────────────────────────────────────────

def _draw_trip_clock(ax, data, t):
    """Circular trip chain clock. Preserved from Krsko-heatmap-v2."""
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("Trip Chain Clock", pad=4)

    # Outer ring
    circ_outer = Circle((0, 0), 1.18, fill=False, linewidth=6, color="#E2E8F0", zorder=1)
    ax.add_patch(circ_outer)

    # Hour labels + tick marks
    for h in range(0, 24, 6):
        ang = np.pi/2 - 2*np.pi*h/24
        ax.text(1.27*np.cos(ang), 1.27*np.sin(ang),
                f"{h:02d}h", ha="center", va="center",
                fontsize=7.5, color=C_GRAY, fontweight="bold")
    for h in range(24):
        ang = np.pi/2 - 2*np.pi*h/24
        r0, r1 = (1.07, 1.15) if h % 6 == 0 else (1.10, 1.15)
        ax.plot([r0*np.cos(ang), r1*np.cos(ang)],
                [r0*np.sin(ang), r1*np.sin(ang)],
                color="#CBD5E1", lw=1.5 if h % 6 == 0 else 0.8, zorder=2)

    # Trip chain rings (preserved)
    _draw_full_ring(ax, data["trip_chain4"], 0.44, 0.69)
    _draw_full_ring(ax, data["trip_chain2"], 0.72, 0.97)

    ax.text(0, 0.845, "2t", ha="center", va="center",
            fontsize=6, color="white", fontweight="bold", zorder=5)
    ax.text(0, 0.565, "4t", ha="center", va="center",
            fontsize=6, color="white", fontweight="bold", zorder=5)

    ax.add_patch(Circle((0, 0), 0.40, color="white", zorder=5))

    # Clock hand at current time
    hours   = (t * 15) // 60
    minutes = (t * 15) % 60
    t_now   = t * 0.25
    ang = np.pi/2 - 2*np.pi * t_now / 24
    ax.plot([0, 0.62*np.cos(ang)], [0, 0.62*np.sin(ang)],
            color="#1E293B", lw=1.5, solid_capstyle="round", zorder=7, alpha=0.7)
    ax.add_patch(Circle((0, 0), 0.035, color="#1E293B", zorder=8))

    ax.text(0, 0.05, f"{hours:02d}:{minutes:02d}",
            ha="center", va="center",
            fontsize=13, color="#1E293B", fontweight="bold", zorder=6)
    ax.text(0, -0.18, "time", ha="center", va="center",
            fontsize=7, color=C_GRAY, zorder=6)


def _draw_full_ring(ax, chain, r_inner, r_outer, n_steps=1440):
    """
    Draw a full 24-hour trip-chain ring.

    Coloring rules (per user spec):
      • 00:00 → first trip departure  : Home
      • trip departure → arrival       : Driving
      • arrival → next departure       : destination type of THIS trip (seg["type"])
      • after last trip's arrival      : Home  (vehicle returned home)
    """
    # Start everything as Home; the loop will overwrite the relevant windows.
    seg_types = ["Home"] * n_steps

    for i, seg in enumerate(chain):
        i_start = int(seg["start"] / 24 * n_steps)  # departure step
        i_end   = int(seg["end"]   / 24 * n_steps)  # arrival step

        # Window A — vehicle is en route (Driving)
        for j in range(i_start, min(i_end, n_steps)):
            seg_types[j] = "Driving"

        # Window B — vehicle is parked at the destination of this trip
        if i < len(chain) - 1:
            # Colour = destination of this trip until the NEXT trip departs
            parking_type = seg["type"]
            next_depart  = int(chain[i + 1]["start"] / 24 * n_steps)
        else:
            # After the last trip the vehicle is home for the rest of the day
            parking_type = "Home"
            next_depart  = n_steps

        for j in range(i_end, min(next_depart, n_steps)):
            seg_types[j] = parking_type

    # Group consecutive same-type steps into arcs and draw Wedge patches
    groups, cur_type, cur_start = [], seg_types[0], 0
    for i in range(1, n_steps):
        if seg_types[i] != cur_type:
            groups.append((cur_start, i, cur_type))
            cur_type, cur_start = seg_types[i], i
    groups.append((cur_start, n_steps, cur_type))

    for g_start, g_end, gtype in groups:
        color     = TRIP_TYPE_COLORS.get(gtype, "#999999")
        ang_start = 90 - (g_start / n_steps) * 360
        ang_end   = 90 - (g_end   / n_steps) * 360
        ax.add_patch(Wedge(
            (0, 0), r_outer, ang_end, ang_start,
            width=r_outer - r_inner,
            facecolor=color, edgecolor="none", alpha=0.9, zorder=3,
        ))
    ax.add_patch(Circle((0, 0), r_inner, fill=False,
                        linewidth=1.5, color="white", zorder=4))


# ─── Arrivals / departures ────────────────────────────────────────────────────

def _draw_arrivals(ax, data, t, nf, intervals, show_2trips, show_4trips):
    """Work arrivals / departures bar chart. Preserved from Krsko-heatmap-v2."""
    bin_edges   = np.arange(0, intervals * DT_H + DT_H, DT_H)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bw = 0.22
    mv = np.arange(intervals) <= t

    if show_2trips and not show_4trips:
        ha = data["arr_hist2"] * mv
        hd = data["dep_hist2"] * mv
    elif show_4trips and not show_2trips:
        ha = data["arr_hist4"] * mv
        hd = data["dep_hist4"] * mv
    elif show_2trips or show_4trips:
        ha = data["arr_hist_total"] * mv
        hd = data["dep_hist_total"] * mv
    else:
        ha = hd = np.zeros(intervals)

    ax.bar(bin_centers, ha, width=bw, color=C_ORANGE, alpha=0.85, label="Arrivals")
    ax.bar(bin_centers, hd, width=bw, color=C_BLUE,   alpha=0.85, label="Departures",
           bottom=ha)

    max_bar = max(float((ha + hd).max()), 1)
    t_now = t * 0.25
    ax.plot([t_now, t_now], [0, max_bar * 1.5 + 1],
            color=C_RED, lw=1, ls=":", alpha=0.6)

    ax.legend(ncol=2, loc="upper right", fontsize=6.5, frameon=True, borderpad=0.4)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, max_bar * 1.5 + 1)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)])
    ax.set_title("Work Arrivals / Departures (All vehicles)", pad=6)
    ax.set_ylabel("Vehicles")


# ─── SoC Flexibility ──────────────────────────────────────────────────────────

def _draw_flexibility(ax, data, t, nf, x_t, t_axis):
    """SoC Flexibility chart. Preserved from Krsko-heatmap-v2."""
    current_pos = -data["cum_poz_total"][:nf]
    current_neg =  data["cum_neg_total"][:nf]

    ax.plot(x_t, current_pos, lw=2, color=C_ORANGE, label="Positive flexibility (+)")
    ax.plot(x_t, current_neg, lw=2, color=C_BLUE,   label="Negative flexibility (-)")

    if nf > 1:
        ax.fill_between(x_t, current_pos, 0, alpha=0.15, color=C_ORANGE)
        ax.fill_between(x_t, current_neg, 0, alpha=0.15, color=C_BLUE)

    ax.axhline(0, color="#94A3B8", lw=0.8, ls="--", alpha=0.6)

    flex_now = np.concatenate([current_pos, current_neg]) if nf > 0 else np.array([0])
    fmin = float(flex_now.min())
    fmax = float(flex_now.max())
    if abs(fmax - fmin) < 1:
        fmin -= 0.5
        fmax += 0.5
    lower_margin = max(0.5, abs(fmin) * 0.20)
    upper_margin = max(0.5, abs(fmax) * 0.30)

    ax.set_xlim(0, 24)
    ax.set_ylim(fmin - lower_margin, fmax + upper_margin)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)])
    ax.set_title("SoC Flexibility", pad=6)
    ax.set_ylabel("kWh")
    ax.legend(loc="lower right", fontsize=6.5, frameon=True)


# ─── PV self-sufficiency ──────────────────────────────────────────────────────

def create_pv_figure():
    """
    PV self-sufficiency figure.
    Delegates to PV_samo_simple.build_pv_plot() to preserve exact visuals.
    """
    plt.rcParams.update(_RCPARAMS)
    try:
        import PV_samo_simple as pv
        return pv.build_pv_plot()
    except Exception as e:
        fig, ax = plt.subplots(figsize=(12, 4))
        fig.patch.set_alpha(0.0)
        ax.text(0.5, 0.5, f"PV data unavailable: {e}",
                ha="center", va="center", transform=ax.transAxes, color=C_RED)
        ax.set_axis_off()
        return fig


# ─── Zone vehicle-count heatmap ───────────────────────────────────────────────

def create_zone_vehicle_hm_figure(data, t):
    """Zone × time vehicle count heatmap. Preserved from Krsko-heatmap-v2."""
    plt.rcParams.update(_RCPARAMS)
    fig, ax = plt.subplots(figsize=(14, 4))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    combined = data["zone_count_combined"]
    n_zones  = len(_ZONE_ORDER)
    intervals = data["intervals"]
    t_end    = intervals * DT_H

    im = ax.imshow(
        combined,
        aspect="auto",
        origin="upper",
        cmap="Blues",
        extent=[0, t_end, n_zones - 0.5, -0.5],
        interpolation="nearest",
        vmin=0,
    )
    ax.set_xticks(range(0, int(t_end) + 1, 3))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, int(t_end) + 1, 3)], fontsize=8)
    ax.set_yticks(range(n_zones))
    ax.set_yticklabels(_ZONE_ORDER, fontsize=8)
    ax.set_xlabel("Time of day", fontsize=9)
    ax.set_ylabel("Zone", fontsize=9)
    ax.set_title("Fleet Distribution by Zone", fontsize=10, fontweight="bold", pad=8)
    plt.colorbar(im, ax=ax, label="Vehicle count", shrink=0.85)

    # Time indicator line at current t
    ax.axvline(t * DT_H, color="red", lw=1.5, ls="--", alpha=0.8, label="Current time")
    ax.legend(loc="upper right", fontsize=7)

    fig.tight_layout()
    return fig


# ─── Zone energy demand heatmap ───────────────────────────────────────────────

def create_zone_energy_hm_figure(data, t):
    """Zone × time energy demand heatmap. Preserved from Krsko-heatmap-v2."""
    plt.rcParams.update(_RCPARAMS)
    fig, ax = plt.subplots(figsize=(14, 4))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    n_zones   = len(_ENERGY_ZONE_ORDER)
    intervals = data["intervals"]
    t_end     = intervals * DT_H

    im = ax.imshow(
        data["zone_energy_combined"],
        aspect="auto",
        origin="upper",
        cmap="YlOrRd",
        extent=[0, t_end, n_zones - 0.5, -0.5],
        interpolation="nearest",
        vmin=0,
    )
    ax.set_xticks(range(0, int(t_end) + 1, 3))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, int(t_end) + 1, 3)], fontsize=8)
    ax.set_yticks(range(n_zones))
    ax.set_yticklabels(_ENERGY_ZONE_ORDER, fontsize=8)
    ax.set_xlabel("Time of day", fontsize=9)
    ax.set_ylabel("Zone", fontsize=9)
    ax.set_title("Energy Demand by Zone", fontsize=10, fontweight="bold", pad=8)
    plt.colorbar(im, ax=ax, label="Energy demand (kWh)", shrink=0.85)

    ax.axvline(t * DT_H, color="steelblue", lw=1.5, ls="--", alpha=0.8, label="Current time")
    ax.legend(loc="upper right", fontsize=7)

    fig.tight_layout()
    return fig


# ─── Zone flexibility dashboard ───────────────────────────────────────────────

def create_zone_flex_figure(data, t):
    """
    Zone flexibility analysis dashboard (2×3 subplots).
    Preserved from Krsko-heatmap-v2 _draw_zone_flex_figure().
    """
    plt.rcParams.update(_RCPARAMS)
    fig = plt.figure(figsize=(14, 7))
    fig.patch.set_alpha(0.0)
    fig.suptitle("Zone-Specific Energy Flexibility Analysis",
                 fontsize=13, fontweight="bold", color="#1E293B")

    zone_hourly_data     = data["zone_hourly_data"]
    zone_energy_combined = data["zone_energy_combined"]
    intervals            = data["intervals"]

    gs_z = gridspec.GridSpec(2, 3, figure=fig, hspace=0.50, wspace=0.32,
                             left=0.07, right=0.97, top=0.92, bottom=0.08)
    ax_ind  = fig.add_subplot(gs_z[0, 0])
    ax_com  = fig.add_subplot(gs_z[0, 1])
    ax_res  = fig.add_subplot(gs_z[0, 2])
    ax_veh  = fig.add_subplot(gs_z[1, 0])
    ax_egy  = fig.add_subplot(gs_z[1, 1])
    ax_peak = fig.add_subplot(gs_z[1, 2])

    def _zone_hourly(zone):
        sub = (zone_hourly_data[zone_hourly_data["Zone"] == zone]
               .set_index("Hour")
               .reindex(range(24), fill_value=0))
        return sub.index, sub["Total_Neg_flex"], sub["Total_Pos_flex"]

    def _draw_zone_ax(ax, zone):
        color = ZONE_COLORS.get(zone, "#64748B")
        hours, neg, pos = _zone_hourly(zone)
        ax.plot(hours, neg,  color=C_BLUE,   lw=2, label="Neg flex (demand)")
        ax.fill_between(hours, neg,  0, color=C_BLUE,   alpha=0.18)
        ax.plot(hours, -pos, color=C_ORANGE, lw=2, label="Pos flex (headroom)")
        ax.fill_between(hours, -pos, 0, color=C_ORANGE, alpha=0.18)
        ax.axhline(0, color="#94A3B8", lw=0.8, ls="--", alpha=0.6)
        ax.axvline(t * DT_H, color="red", lw=1.5, ls="--", alpha=0.8)
        ax.set_title(f"{zone} Zone", fontweight="bold",
                     color=color if color != "#64748B" else "#1E293B")
        ax.set_xlabel("Hour of day")
        ax.set_ylabel("kWh")
        ax.set_xlim(0, 23)
        ax.legend(fontsize=7, loc="best")
        ax.grid(True, alpha=0.3)

    _draw_zone_ax(ax_ind, "Industrial")
    _draw_zone_ax(ax_com, "Commercial")
    _draw_zone_ax(ax_res, "Residential")

    # Vehicle count lines
    zone_colors = [ZONE_COLORS.get(z, "#64748B") for z in _ZONE_ORDER]
    p_veh = (
        zone_hourly_data
        .pivot_table(index="Hour", columns="Zone", values="NumVehicles", aggfunc="mean")
        .reindex(columns=_ZONE_ORDER, fill_value=0)
    )
    for zone, color in zip(_ZONE_ORDER, zone_colors):
        ax_veh.plot(p_veh.index, p_veh[zone], label=zone, color=color,
                    lw=2, marker="o", ms=3)
    ax_veh.axvline(t * DT_H, color="red", lw=1.5, ls="--", alpha=0.8)
    ax_veh.set_title("Avg Vehicles per Zone", fontweight="bold")
    ax_veh.set_xlabel("Hour of day")
    ax_veh.set_ylabel("Vehicles (avg)")
    ax_veh.set_xlim(0, 23)
    ax_veh.legend(fontsize=7)
    ax_veh.grid(True, alpha=0.3)

    # Hourly energy demand by zone (grouped bars)
    t_h      = (np.arange(intervals) * 15) // 60
    n_zones_e = len(_ENERGY_ZONE_ORDER)
    bar_w    = 0.8 / max(n_zones_e, 1)
    offsets  = np.linspace(-0.4 + bar_w/2, 0.4 - bar_w/2, n_zones_e)
    for zi, (zone, color) in enumerate(
            zip(_ENERGY_ZONE_ORDER,
                [ZONE_COLORS.get(z, "#64748B") for z in _ENERGY_ZONE_ORDER])):
        hourly = np.array([
            float(zone_energy_combined[zi, t_h == h].sum()) for h in range(24)
        ])
        ax_egy.bar(np.arange(24) + offsets[zi], hourly,
                   width=bar_w, color=color, alpha=0.80, label=zone)
    ax_egy.axvline(t * DT_H, color="red", lw=1.5, ls="--", alpha=0.8)
    ax_egy.set_title("Energy Demand by Zone (kWh)", fontweight="bold")
    ax_egy.set_xlabel("Hour of day")
    ax_egy.set_ylabel("kWh")
    ax_egy.set_xticks(range(0, 24, 3))
    ax_egy.set_xticklabels([f"{h:02d}h" for h in range(0, 24, 3)])
    ax_egy.legend(fontsize=7)
    ax_egy.grid(True, alpha=0.3, axis="y")

    # Peak hours summary (horizontal bar)
    peak_rows = []
    for zone in _ZONE_ORDER:
        sub = zone_hourly_data[zone_hourly_data["Zone"] == zone]
        if sub.empty or sub["Total_Neg_flex"].max() == 0:
            continue
        best = sub.loc[sub["Total_Neg_flex"].idxmax()]
        peak_rows.append({"Zone": zone,
                          "Total_Neg_flex": best["Total_Neg_flex"],
                          "Hour": best["Hour"]})
    if peak_rows:
        peak_df    = pd.DataFrame(peak_rows).sort_values("Total_Neg_flex")
        bar_colors = [ZONE_COLORS.get(z, "#64748B") for z in peak_df["Zone"]]
        ax_peak.barh(peak_df["Zone"], peak_df["Total_Neg_flex"],
                     color=bar_colors, alpha=0.80)
        for i, (_, row) in enumerate(peak_df.iterrows()):
            ax_peak.text(row["Total_Neg_flex"], i,
                         f"  {int(row['Hour']):02d}:00", va="center", fontsize=7)
    ax_peak.set_title("Peak Charging Demand by Zone", fontweight="bold")
    ax_peak.set_xlabel("Peak kWh")
    ax_peak.grid(True, axis="x", alpha=0.3)

    return fig


# ─── Individual standalone chart figures ─────────────────────────────────────
# Used by the main dashboard tab: each chart is its own st.pyplot call so it
# fills the full column width and can be sized independently.
#
# These are called once per animation tick (every ~0.3s while playing), so we
# keep a persistent Figure/Axes per chart type instead of creating a new
# plt.figure() each call — ax.clear() + redraw is cheaper than tearing down
# and reallocating the whole Figure/canvas every frame.

_FIGURE_CACHE = {}


def _get_cached_axes(key, figsize):
    """Return a persistent (fig, ax) pair for `key`, clearing ax for reuse.

    Transparent backgrounds so the figure blends into the Streamlit theme
    instead of looking like a pasted photo on a light panel."""
    cached = _FIGURE_CACHE.get(key)
    if cached is None:
        fig, ax = plt.subplots(figsize=figsize)
        _FIGURE_CACHE[key] = (fig, ax)
    else:
        fig, ax = cached
        ax.clear()
    fig.patch.set_alpha(0.0)        # transparent figure background
    ax.patch.set_alpha(0.0)         # transparent axes background
    return fig, ax


def create_charging_demand_figure(data, t, show_2trips=True, show_4trips=True):
    """Standalone Workplace Charging Demand figure (persistent Figure/Axes)."""
    plt.rcParams.update(_RCPARAMS)
    intervals = data["intervals"]
    t = min(t, intervals - 1)
    nf = t + 1
    x_t = np.arange(nf) * 0.25

    fig, ax = _get_cached_axes("charging_demand", (6, 2.2))
    _draw_charging_demand(ax, data, t, nf, x_t, show_2trips, show_4trips)
    fig.tight_layout(pad=0.8)
    return fig


def create_trip_clock_figure(data, t):
    """Standalone Trip Chain Clock figure (persistent Figure/Axes)."""
    plt.rcParams.update(_RCPARAMS)
    t = min(t, data["intervals"] - 1)

    fig, ax = _get_cached_axes("trip_clock", (3.4, 3.4))
    _draw_trip_clock(ax, data, t)
    fig.tight_layout(pad=0.2)
    return fig


def create_single_vehicle_clock_figure(chain, t, label=""):
    """
    Trip chain clock for a single vehicle (one ring only).
    chain: list of trip segment dicts (same format as _get_trip_chain output)
    t:     current time step (0-95)
    label: display label, e.g. "2-trip V3"
    """
    plt.rcParams.update(_RCPARAMS)

    fig, ax = _get_cached_axes("single_vehicle_clock", (2.9, 2.9))

    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(f"Trip Chain: {label}", pad=4, fontsize=9)

    # Outer ring decoration
    ax.add_patch(Circle((0, 0), 1.18, fill=False, linewidth=6, color="#E2E8F0", zorder=1))

    for h in range(0, 24, 6):
        ang = np.pi/2 - 2*np.pi*h/24
        ax.text(1.27*np.cos(ang), 1.27*np.sin(ang),
                f"{h:02d}h", ha="center", va="center",
                fontsize=7.5, color=C_GRAY, fontweight="bold")
    for h in range(24):
        ang = np.pi/2 - 2*np.pi*h/24
        r0, r1 = (1.07, 1.15) if h % 6 == 0 else (1.10, 1.15)
        ax.plot([r0*np.cos(ang), r1*np.cos(ang)],
                [r0*np.sin(ang), r1*np.sin(ang)],
                color="#CBD5E1", lw=1.5 if h % 6 == 0 else 0.8, zorder=2)

    # Single vehicle ring (wider, centred in the clock face)
    _draw_full_ring(ax, chain, 0.44, 0.97)

    ax.add_patch(Circle((0, 0), 0.40, color="white", zorder=5))

    # Clock hand at current time
    hours   = (t * 15) // 60
    minutes = (t * 15) % 60
    t_now   = t * 0.25
    ang = np.pi/2 - 2*np.pi * t_now / 24
    ax.plot([0, 0.62*np.cos(ang)], [0, 0.62*np.sin(ang)],
            color="#1E293B", lw=1.5, solid_capstyle="round", zorder=7, alpha=0.7)
    ax.add_patch(Circle((0, 0), 0.035, color="#1E293B", zorder=8))

    ax.text(0, 0.05, f"{hours:02d}:{minutes:02d}",
            ha="center", va="center",
            fontsize=13, color="#1E293B", fontweight="bold", zorder=6)
    ax.text(0, -0.18, "time", ha="center", va="center",
            fontsize=7, color=C_GRAY, zorder=6)

    fig.tight_layout(pad=0.3)
    return fig


def create_arrivals_figure(data, t, show_2trips=True, show_4trips=True):
    """Standalone Work Arrivals / Departures figure (persistent Figure/Axes)."""
    plt.rcParams.update(_RCPARAMS)
    intervals = data["intervals"]
    t = min(t, intervals - 1)
    nf = t + 1

    fig, ax = _get_cached_axes("arrivals", (5, 1.7))
    _draw_arrivals(ax, data, t, nf, intervals, show_2trips, show_4trips)
    fig.tight_layout(pad=0.4)
    return fig


def create_zone_flex_heatmap_figure(data):
    """
    Two-panel heatmap of per-zone V2G flexibility potential over 24 h.

    Left panel  — Positive flex (kW): charging headroom / V1G smart-charging potential.
                  Vehicle is parked at Work and could absorb MORE power than minimum.
    Right panel — Negative flex (kW): discharge / V2G potential.
                  Vehicle could export power back to the grid while parked.

    X axis: 15-min timesteps (0–24 h)
    Y axis: zones in _ENERGY_ZONE_ORDER
    Colour:  kW aggregated across all vehicles in that zone at that time.
    """
    plt.rcParams.update(_RCPARAMS)

    zone_flex_pos = data["zone_flex_pos"]   # (n_zones, intervals)
    zone_flex_neg = data["zone_flex_neg"]
    intervals     = data["intervals"]
    n_zones       = len(_ENERGY_ZONE_ORDER)

    t_hours  = np.arange(intervals) * DT_H   # 0 … 23.75
    t_labels = [f"{int(h):02d}h" for h in range(0, 25, 3)]
    t_ticks  = [i for i in range(0, intervals + 1, 12)]   # every 3 h

    fig, axes = plt.subplots(1, 2, figsize=(13, 3.6))
    fig.patch.set_alpha(0.0)
    fig.suptitle("V1G / V2G flexibility potential per zone (kW)",
                 fontsize=12, fontweight="bold", color="#1E293B", y=1.01)

    panels = [
        (zone_flex_pos, "V1G — charging potential (kW)", "YlOrBr"),
        (zone_flex_neg, "V2G — discharge potential (kW)", "Blues"),
    ]

    for ax, (matrix, title, cmap) in zip(axes, panels):
        vmax = float(matrix.max()) if matrix.max() > 0 else 1.0
        im   = ax.imshow(
            matrix,
            aspect="auto",
            origin="lower",
            extent=[0, intervals, -0.5, n_zones - 0.5],
            cmap=cmap,
            vmin=0,
            vmax=vmax,
            interpolation="nearest",
        )
        cbar = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.035)
        cbar.set_label("kW", fontsize=9)
        cbar.ax.tick_params(labelsize=8)

        ax.set_yticks(range(n_zones))
        ax.set_yticklabels(_ENERGY_ZONE_ORDER, fontsize=9)
        ax.set_xticks(t_ticks)
        ax.set_xticklabels(t_labels, fontsize=8)
        ax.set_xlabel("Time of day", fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold", pad=6)
        ax.grid(False)

        # Zone-colour ticks on y axis
        for yi, zone in enumerate(_ENERGY_ZONE_ORDER):
            color = ZONE_COLORS.get(zone, "#64748B")
            ax.get_yticklabels()[yi].set_color(color)

    fig.tight_layout(pad=1.0)
    return fig

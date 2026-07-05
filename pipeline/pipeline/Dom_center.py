import matplotlib
# matplotlib.use("TkAgg")   # uncomment if running outside VS Code / Jupyter

from krsko_osm_clusters import get_krsko_clusters

import warnings
import pandas as pd
import numpy as np
import geopandas as gpd
import contextily as ctx          # type: ignore
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch, Circle, Wedge
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter
from shapely.geometry import Point
from shapely.ops import unary_union


# ═══════════════════════════════════════════════════════════
# GLOBAL STYLE  (identical to Krsko-heatmap)
# ═══════════════════════════════════════════════════════════

plt.rcParams.update({
    "figure.facecolor":  "#F7F9FC",
    "axes.facecolor":    "#FFFFFF",
    "axes.edgecolor":    "#D0D7E3",
    "axes.grid":         True,
    "grid.color":        "#E8ECF4",
    "grid.linewidth":    0.7,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "font.family":       "DejaVu Sans",
    "axes.titlesize":    9,
    "axes.labelsize":    8,
    "xtick.labelsize":   7,
    "ytick.labelsize":   7,
    "legend.fontsize":   7,
    "legend.framealpha": 0.9,
    "legend.edgecolor":  "#D0D7E3",
})

C_BLUE   = "#2563EB"
C_ORANGE = "#EA580C"
C_GREEN  = "#16A34A"
C_RED    = "#DC2626"
C_PURPLE = "#7C3AED"
C_GRAY   = "#64748B"
C_PANEL  = "#EEF2FF"

MAX_CHARGER_KW = 11.0   # AC Type-2 cap; set None to remove


# ═══════════════════════════════════════════════════════════
# URBAN ZONES LAYER  (from Krsko-heatmap)
# ═══════════════════════════════════════════════════════════

ZONE_COLORS = {
    "Residential":  "#AEC6CF",
    "Commercial":   "#F4A460",
    "Industrial":   "#CD5C5C",
    "Transport":    "#D3D3D3",
    "Leisure":      "#90EE90",
}

LANDUSE_TO_ZONE = {
    "residential": "Residential", "family_garden": "Residential",
    "village_green": "Residential",
    "commercial": "Commercial", "retail": "Commercial", "office": "Commercial",
    "industrial": "Industrial", "brownfield": "Industrial",
    "quarry": "Industrial", "landfill": "Industrial", "farmyard": "Industrial",
    "railway": "Transport", "parking": "Transport", "construction": "Transport",
    "park": "Leisure", "leisure": "Leisure", "recreation_ground": "Leisure",
    "garden": "Leisure", "pitch": "Leisure", "stadium": "Leisure",
    "sports_centre": "Leisure", "swimming_pool": "Leisure",
    "forest": "Leisure", "grassland": "Leisure", "meadow": "Leisure",
    "orchard": "Leisure", "nature_reserve": "Leisure",
}


def plot_landuse_layers(ax, landuse_gdf):
    """Plot OSM landuse polygons on *ax* (expects EPSG:3857 axes / basemap)."""
    lz = landuse_gdf.to_crs(epsg=3857)
    mapping = {
        "residential": ("#2c7bb6", 0.25),
        "industrial":  ("#d7191c", 0.25),
        "commercial":  ("#fdae61", 0.25),
        "retail":      ("#fdae61", 0.25),
    }
    for tag, (color, alpha) in mapping.items():
        sub = lz[lz["landuse"] == tag]
        if not sub.empty:
            sub.plot(ax=ax, color=color, alpha=alpha, zorder=2)
    parks = lz[lz["leisure"].isin(["park", "recreation_ground"])]
    if not parks.empty:
        parks.plot(ax=ax, color="#1a9641", alpha=0.25, zorder=2)
    edu = lz[lz["amenity"].isin(["school", "college", "university"])]
    if not edu.empty:
        edu.plot(ax=ax, color="#984ea3", alpha=0.30, zorder=2)


def get_residential_zones(landuse_gdf, target_crs=3857, merge_buffer=10.0):
    lz = landuse_gdf.to_crs(epsg=target_crs)
    res = lz[lz["landuse"] == "residential"].copy()
    if res.empty:
        return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{target_crs}")
    res["geometry"] = res.geometry.buffer(merge_buffer)
    merged = gpd.GeoDataFrame(geometry=[unary_union(res.geometry)],
                               crs=f"EPSG:{target_crs}")
    return merged


def create_urban_zones(landuse_gdf):
    zones_by_type = {z: {"centroid": None, "radius_m": 0, "areas": []}
                     for z in ZONE_COLORS}
    for _, row in landuse_gdf.iterrows():
        tag = row.get("landuse") or row.get("leisure") or row.get("amenity")
        zone_type = LANDUSE_TO_ZONE.get(tag)
        if zone_type:
            zones_by_type[zone_type]["areas"].append(row.geometry)
    for zone_type, data in zones_by_type.items():
        if not data["areas"]:
            continue
        ug = unary_union(data["areas"])
        c  = ug.centroid
        data["centroid"] = (c.x, c.y)
        data["radius_m"] = np.sqrt(ug.area / np.pi) if ug.area > 0 else 500
    return zones_by_type


# ═══════════════════════════════════════════════════════════
# LOAD OSM + EXCEL DATA
# ═══════════════════════════════════════════════════════════

clusters, landuse_gdf = get_krsko_clusters()
zones_by_type = create_urban_zones(landuse_gdf)

# ── Change this path to match your output file ──────────────────────────────
#file_path = "03_Vehicle_trip_parameters_100_EVs_2_trips_1_days.xlsx"
file_path = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/MagistrskaNaloga/DomCenter/pipeline/04_SoC_flexibility/04_SoC_flex_100_EVs_2_trips_1_days.xlsx"

# ─────────────────────────────────────────────────────────────────────────────

df = pd.read_excel(file_path)
df.columns = df.columns.str.strip()

max_end  = int(df["End"].max())
intervals = max(98246, max_end + 1)
DT_H     = 0.25


# ═══════════════════════════════════════════════════════════
# BUILD POSITION / TYPE / CHARGING MATRICES
# (mirrors Krsko-heatmap build_matrices; single-fleet version)
# ═══════════════════════════════════════════════════════════

BATTERY_KWH = 72.0

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

    # pass 1: positions & trip types
    for _, trip in vt.iterrows():
        s, e   = int(trip["Start"]), int(trip["End"])
        dc     = (trip["End_lon"], trip["End_lat"])
        ttype  = trip["Trip type"]

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

    # pass 2: charging demand at Work parking windows
    for _, trip in vt.iterrows():
        if trip["Trip type"] != "Work":
            continue
        park_start  = int(trip["End"])
        later_trips = vt[vt["Trip ID"] > trip["Trip ID"]]
        if later_trips.empty:
            continue
        park_end   = int(later_trips.iloc[0]["Start"])
        park_dur   = max(park_end - park_start, 1)
        park_hours = park_dur * DT_H

        e_min_energy = float(later_trips["Energy_kWh"].sum())

        # SoC column may be named differently depending on Step output
        soc_col = next((c for c in ["SoC_at_End", "SoC", "Initial_SoC"] if c in trip.index), None)
        soc_arrival = float(trip[soc_col]) if soc_col else 85.0
        e_max_energy = max(BATTERY_KWH * (100.0 - soc_arrival) / 100.0, 0.0)

        p_min = e_min_energy / park_hours
        p_max = e_max_energy / park_hours
        if MAX_CHARGER_KW is not None:
            p_min = min(p_min, MAX_CHARGER_KW)
            p_max = min(p_max, MAX_CHARGER_KW)

        typ[vid-1, park_start:park_end] = "Work"
        eng_min[vid-1, park_start:park_end] = p_min
        eng_max[vid-1, park_start:park_end] = p_max


# ═══════════════════════════════════════════════════════════
# HOME VALIDATION  (from Krsko-heatmap)
# ═══════════════════════════════════════════════════════════

def validate_home_residential_coverage(home_df_list, landuse_gdf, buffer_m=50):
    home_df = pd.concat(home_df_list).reset_index()
    home_gdf = gpd.GeoDataFrame(
        home_df,
        geometry=gpd.points_from_xy(home_df["Start_lon"], home_df["Start_lat"]),
        crs="EPSG:4326"
    ).to_crs(epsg=3857)
    res_zones = get_residential_zones(landuse_gdf, target_crs=3857, merge_buffer=10.0)
    res_union = res_zones.union_all() if not res_zones.empty else None
    inside    = home_gdf.geometry.apply(
        lambda p: p.within(res_union) if res_union is not None else False
    )
    missing = home_gdf[~inside]
    if missing.empty:
        print("Home validation: all vehicles start inside residential clusters.")
        return home_gdf, gpd.GeoDataFrame(geometry=[], crs=home_gdf.crs)
    print(f"Home validation: {len(missing)} home locations outside residential clusters.")
    missing_buf = gpd.GeoDataFrame(
        geometry=missing.geometry.buffer(buffer_m), crs=home_gdf.crs)
    return home_gdf, missing_buf

home_gdf, missing_residential_buffers = validate_home_residential_coverage(
    [home_locations], landuse_gdf
)


# ═══════════════════════════════════════════════════════════
# PRE-COMPUTE fleet curves
# ═══════════════════════════════════════════════════════════

e_min_total = eng_min.sum(axis=0)   # kW per interval
e_max_total = eng_max.sum(axis=0)

def parked_counts(typ_arr):
    return np.array([int(np.sum(typ_arr[:, t] == "Work")) for t in range(intervals)])

parked      = parked_counts(typ)
max_park    = int(parked.max())
_fleet_max  = float(e_max_total.max())

def compute_work_flow(typ_arr, nv_):
    arr_hist = np.zeros(intervals)
    dep_hist = np.zeros(intervals)
    for v in range(nv_):
        for t in range(1, intervals):
            if typ_arr[v, t-1] == "Driving" and typ_arr[v, t] == "Work":
                arr_hist[t] += 1
            if typ_arr[v, t-1] == "Work" and typ_arr[v, t] == "Driving":
                dep_hist[t] += 1
    return arr_hist, dep_hist

arr_hist, dep_hist = compute_work_flow(typ, nv)
t_axis = np.arange(intervals) * DT_H

# trip-chain clock for vehicle 1
def get_trip_chain(df_, vid=1):
    vt = df_[df_["Vehicle ID"] == vid].sort_values(["Start", "End", "Trip ID"])
    return [{"start": r["Start"]*0.25, "end": r["End"]*0.25, "type": r["Trip type"]}
            for _, r in vt.iterrows()]

trip_chain_clock = get_trip_chain(df, vid=1)


# ═══════════════════════════════════════════════════════════
# DISPLAY STATE
# ═══════════════════════════════════════════════════════════

show_heatmap   = True
show_zones     = True
show_work_only = False

trip_type_colors = {
    "Work":      C_BLUE,
    "Shopping":  C_RED,
    "Leisure":   C_GREEN,
    "Education": C_ORANGE,
    "Business":  C_PURPLE,
    "Home":      "#374151",
    "Driving":   C_GRAY,
}


# ═══════════════════════════════════════════════════════════
# FIGURE LAYOUT  (mirrors Krsko-heatmap 3×3 grid)
# ═══════════════════════════════════════════════════════════

fig = plt.figure(figsize=(24, 12))
fig.patch.set_facecolor("#F7F9FC")

ax_header = fig.add_axes([0.02, 0.97, 0.96, 0.03])
ax_header.set_axis_off()
header_text = ax_header.text(
    0.5, 0.5, "",
    ha="center", va="center", fontsize=9, fontweight="bold", color="#1E293B"
)
ax_header.text(
    0.01, 0.5,
    f"Fleet: {nv} vehicles  |  Single-day simulation",
    ha="left", va="center", fontsize=9, color=C_GRAY
)

# Time display box (top-right)
ax_time_display = fig.add_axes([0.86, 0.95, 0.12, 0.045])
ax_time_display.set_axis_off()
ax_time_display.add_patch(FancyBboxPatch(
    (0.02, 0.05), 0.96, 0.90,
    boxstyle="round,pad=0.01", transform=ax_time_display.transAxes,
    edgecolor="black", facecolor="white", linewidth=1, alpha=0.95, zorder=1
))
time_display_text = ax_time_display.text(
    0.5, 0.5, "00:00",
    ha="center", va="center", fontsize=20, fontweight="bold",
    color="black", transform=ax_time_display.transAxes, zorder=2
)

gs = gridspec.GridSpec(
    3, 3, figure=fig,
    left=0.02, right=0.99, top=0.95, bottom=0.12,
    wspace=0.10, hspace=0.55,
    width_ratios=[1, 1, 2.6],
    height_ratios=[0.7, 1, 1],
)

ax_kpi1     = fig.add_subplot(gs[0, 0])
ax_kpi2     = fig.add_subplot(gs[0, 1])
ax_energy   = fig.add_subplot(gs[1, 0])
ax_clock    = fig.add_subplot(gs[1, 1])
ax_arrivals = fig.add_subplot(gs[2, 0])
ax_flex     = fig.add_subplot(gs[2, 1])
ax_map      = fig.add_subplot(gs[:, 2])

for a in [ax_kpi1, ax_kpi2]:
    a.set_facecolor(C_PANEL)
ax_clock.set_facecolor("#F7F9FC")


# ─── TOGGLE BUTTONS ──────────────────────────────────────────────────────────

BTN_Y, BTN_H, BTN_W, GAP = 0.02, 0.045, 0.09, 0.01

btn_specs = [
    ("Heatmap",  0.02),
    ("Zones",    0.02 + (BTN_W + GAP)),
    ("Work only",0.02 + 2*(BTN_W + GAP)),
]

btn_states = {"Heatmap": True, "Zones": True, "Work only": False}
BTN_ON_COLOR  = "#93C5FD"
BTN_OFF_COLOR = "#F1F5F9"
BTN_ON_TEXT, BTN_OFF_TEXT = "white", "#374151"

btn_axes, btn_objs = {}, {}
for label, left in btn_specs:
    bax = fig.add_axes([left, BTN_Y, BTN_W, BTN_H])
    on  = btn_states[label]
    b   = Button(bax, label,
                 color=BTN_ON_COLOR if on else BTN_OFF_COLOR,
                 hovercolor="#BFDBFE" if on else "#CBD5E1")
    b.label.set_fontsize(7)
    b.label.set_color(BTN_ON_TEXT if on else BTN_OFF_TEXT)
    btn_axes[label] = bax
    btn_objs[label] = b

# Legend strip  (after buttons)
leg_x = 0.02 + 3*(BTN_W + GAP) + 0.005
ax_leg = fig.add_axes([leg_x, BTN_Y, 0.25, BTN_H])
ax_leg.set_axis_off()
patches = [mpatches.Patch(color=c, label=t) for t, c in trip_type_colors.items()]
ax_leg.legend(handles=patches, loc="center", ncol=4,
              fontsize=7.5, frameon=True, title="Trip type")


def make_toggle(label):
    def _cb(event):
        global show_heatmap, show_zones, show_work_only
        btn_states[label] = not btn_states[label]
        on = btn_states[label]
        b  = btn_objs[label]
        b.color      = BTN_ON_COLOR  if on else BTN_OFF_COLOR
        b.hovercolor = "#1D4ED8"     if on else "#CBD5E1"
        b.label.set_color(BTN_ON_TEXT if on else BTN_OFF_TEXT)
        b.ax.set_facecolor(BTN_ON_COLOR if on else BTN_OFF_COLOR)
        fig.canvas.draw_idle()
        if   label == "Heatmap":   show_heatmap   = on
        elif label == "Zones":     show_zones     = on
        elif label == "Work only": show_work_only = on
    return _cb

for label, _ in btn_specs:
    btn_objs[label].on_clicked(make_toggle(label))


# ─── KPI PANELS ──────────────────────────────────────────────────────────────

def style_kpi(ax, title):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_axis_off()
    ax.set_facecolor(C_PANEL)
    ax.text(0.5, 0.92, title, ha="center", va="top",
            fontsize=8, color=C_GRAY, fontweight="bold",
            transform=ax.transAxes)

style_kpi(ax_kpi1, "PARKIRANI TRENUTNO")
style_kpi(ax_kpi2, "CHARGING DEMAND (kW)")

kpi1_val = ax_kpi1.text(0.5, 0.52, "–", ha="center", va="center",
                         fontsize=22, color=C_BLUE, fontweight="bold",
                         transform=ax_kpi1.transAxes)
ax_kpi1.text(0.5, 0.18, f"max {max_park}", ha="center", va="bottom",
             fontsize=8, color=C_GRAY, transform=ax_kpi1.transAxes)

kpi2_val = ax_kpi2.text(0.5, 0.52, "– kW", ha="center", va="center",
                         fontsize=18, color=C_ORANGE, fontweight="bold",
                         transform=ax_kpi2.transAxes)
ax_kpi2.text(0.5, 0.18, f"peak max {_fleet_max:.0f} kW",
             ha="center", va="bottom", fontsize=8, color=C_GRAY,
             transform=ax_kpi2.transAxes)


# ─── CHARGING DEMAND CHART ───────────────────────────────────────────────────

energy_line_min, = ax_energy.plot([], [], lw=2, color=C_BLUE,   label="Min demand")
energy_line_max, = ax_energy.plot([], [], lw=2, color=C_ORANGE, label="Max demand")
fill_band = ax_energy.fill_between([], [], [])   # placeholder; rebuilt each frame

ax_energy.legend(ncol=2, loc="upper right", fontsize=6.5, frameon=True, borderpad=0.4)
ax_energy.set_xlim(0, 24)
ax_energy.set_xticks(range(0, 25, 3))
ax_energy.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)])
ax_energy.set_title("Workplace Parking Charging Demand", pad=22)
ax_energy.set_ylabel("kW")
vline_e, = ax_energy.plot([0, 0], [0, 1e6], color=C_RED, lw=1, ls=":", alpha=0.6, zorder=10)


# ─── TRIP CHAIN CLOCK ────────────────────────────────────────────────────────

ax_clock.set_xlim(-1.35, 1.35)
ax_clock.set_ylim(-1.35, 1.35)
ax_clock.set_aspect("equal")
ax_clock.set_axis_off()
ax_clock.set_title("Trip Chain Clock  (Vehicle 1)", pad=4)

ax_clock.add_patch(Circle((0, 0), 1.18, fill=False, linewidth=6, color="#E2E8F0", zorder=1))
for h in range(0, 24, 6):
    ang = np.pi/2 - 2*np.pi*h/24
    ax_clock.text(1.27*np.cos(ang), 1.27*np.sin(ang),
                  f"{h:02d}h", ha="center", va="center",
                  fontsize=7.5, color=C_GRAY, fontweight="bold")
for h in range(24):
    ang = np.pi/2 - 2*np.pi*h/24
    r0, r1 = (1.07, 1.15) if h % 6 == 0 else (1.10, 1.15)
    ax_clock.plot([r0*np.cos(ang), r1*np.cos(ang)],
                  [r0*np.sin(ang), r1*np.sin(ang)],
                  color="#CBD5E1", lw=1.5 if h % 6 == 0 else 0.8, zorder=2)


def draw_full_ring(chain, r_inner, r_outer, n_steps=1440):
    seg_types = ["Home"] * n_steps
    for i, seg in enumerate(chain):
        i_start = int(seg["start"] / 24 * n_steps)
        i_end   = int(seg["end"]   / 24 * n_steps)
        for j in range(i_start, min(i_end, n_steps)):
            seg_types[j] = "Driving"
        next_start = int(chain[i+1]["start"] / 24 * n_steps) if i < len(chain)-1 else n_steps
        stay_type  = seg["type"] if i < len(chain)-1 else "Home"
        for j in range(i_end, min(next_start, n_steps)):
            seg_types[j] = stay_type

    groups, cur_type, cur_start = [], seg_types[0], 0
    for i in range(1, n_steps):
        if seg_types[i] != cur_type:
            groups.append((cur_start, i, cur_type))
            cur_type, cur_start = seg_types[i], i
    groups.append((cur_start, n_steps, cur_type))

    for g_start, g_end, gtype in groups:
        color     = trip_type_colors.get(gtype, "#999999")
        ang_start = 90 - (g_start / n_steps) * 360
        ang_end   = 90 - (g_end   / n_steps) * 360
        ax_clock.add_patch(Wedge(
            (0, 0), r_outer, ang_end, ang_start,
            width=r_outer - r_inner,
            facecolor=color, edgecolor="none", alpha=0.9, zorder=3
        ))
    ax_clock.add_patch(Circle((0, 0), r_inner, fill=False,
                               linewidth=1.5, color="white", zorder=4))

draw_full_ring(trip_chain_clock, 0.55, 0.97)   # single ring (no dual)
ax_clock.add_patch(Circle((0, 0), 0.50, color="white", zorder=5))
clock_text = ax_clock.text(0, 0.05, "00:00", ha="center", va="center",
                            fontsize=13, color="#1E293B", fontweight="bold", zorder=6)
ax_clock.text(0, -0.18, "čas", ha="center", va="center",
              fontsize=7, color=C_GRAY, zorder=6)
clock_hand, = ax_clock.plot([0, 0], [0, 0.95], color="#1E293B",
                              lw=1.5, solid_capstyle="round", zorder=7, alpha=0.7)
ax_clock.add_patch(Circle((0, 0), 0.035, color="#1E293B", zorder=8))


# ─── ARRIVALS / DEPARTURES ───────────────────────────────────────────────────

bin_edges   = np.arange(0, intervals * DT_H + DT_H, DT_H)
bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
bw = 0.22

bars_arr = ax_arrivals.bar(bin_centers, np.zeros(intervals),
                            width=bw, color=C_ORANGE, alpha=0.85, label="Arrivals")
bars_dep = ax_arrivals.bar(bin_centers, np.zeros(intervals),
                            width=bw, color=C_BLUE, alpha=0.85, label="Departures",
                            bottom=np.zeros(intervals))

ax_arrivals.legend(ncol=2, loc="upper right", fontsize=6.5, frameon=True, borderpad=0.4)
ax_arrivals.set_xlim(0, 24)
ax_arrivals.set_xticks(range(0, 25, 3))
ax_arrivals.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)])
ax_arrivals.set_title("Work Arrivals / Departures", pad=22)
ax_arrivals.set_ylabel("Vehicles")
vline_arr, = ax_arrivals.plot([0, 0], [0, 1e6], color=C_RED, lw=1, ls=":", alpha=0.6, zorder=10)


# ─── VEHICLES BY STATE (bottom-right, replaces flex which needs SoC columns) ─

ALL_STATES  = ["Home", "Work", "Driving", "Shopping", "Leisure", "Education", "Business"]
state_colors_stack = {
    "Home":      "#94A3B8",
    "Work":      C_BLUE,
    "Driving":   "#78909C",
    "Shopping":  C_RED,
    "Leisure":   C_GREEN,
    "Education": C_ORANGE,
    "Business":  C_PURPLE,
}

state_counts = {s: np.array([int(np.sum(typ[:, t] == s)) for t in range(intervals)])
                for s in ALL_STATES}

# Stacked area chart — drawn once, masked each frame via x-clipping
state_line_plots = {}
bottoms = np.zeros(intervals)
for s in ALL_STATES:
    if state_counts[s].max() == 0:
        continue
    state_line_plots[s], = ax_flex.plot([], [], lw=1.8,
                                         color=state_colors_stack[s],
                                         label=s)

ax_flex.set_xlim(0, 24)
ax_flex.set_xticks(range(0, 25, 3))
ax_flex.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)])
ax_flex.set_ylim(0, nv * 1.15)
ax_flex.set_title("Vehicles by State", pad=22)
ax_flex.set_ylabel("Vehicles")
ax_flex.legend(loc="upper right", fontsize=6, frameon=True, ncol=2)
vline_flex, = ax_flex.plot([0, 0], [0, nv * 1.15], color=C_RED, lw=1, ls=":", alpha=0.6, zorder=10)


# ─── MAP ─────────────────────────────────────────────────────────────────────

center_lon = df["Start_lon"].mean()
center_lat = df["Start_lat"].mean()
gdf_c  = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)],
                            crs="EPSG:4326").to_crs(epsg=3857)
cx_m, cy_m = float(gdf_c.geometry.x[0]), float(gdf_c.geometry.y[0])
buf = 5000
ax_map.set_xlim(cx_m - buf, cx_m + buf)
ax_map.set_ylim(cy_m - buf, cy_m + buf)
ax_map.set_aspect("equal")

plot_landuse_layers(ax_map, landuse_gdf)
if not missing_residential_buffers.empty:
    missing_residential_buffers.plot(ax=ax_map, color="#aec6cf",
                                      alpha=0.22, edgecolor="none", zorder=2)
ctx.add_basemap(ax_map, source=ctx.providers.CartoDB.Positron)
ax_map.set_axis_off()

# Zone circles
zone_patches = []
zone_type_to_patch = {}
for zone_type, zone_data in zones_by_type.items():
    if zone_data["centroid"] is None:
        continue
    zx, zy = zone_data["centroid"]
    zr = zone_data["radius_m"] * 0.8
    patch = Circle(
        (zx, zy), zr,
        color=ZONE_COLORS[zone_type], alpha=0.25,
        edgecolor=ZONE_COLORS[zone_type], linewidth=1.0,
        linestyle="--", zorder=2, label=zone_type
    )
    zone_patches.append(patch)
    zone_type_to_patch[zone_type] = patch
    ax_map.add_patch(patch)

# Workplace marker
work_pt = gpd.GeoSeries([Point(work_location)], crs="EPSG:4326").to_crs(epsg=3857)
work_x  = float(work_pt.geometry.x.iloc[0])
work_y  = float(work_pt.geometry.y.iloc[0])
ax_map.scatter([work_x], [work_y], color="#10B981", s=400,
               edgecolor="#1E293B", linewidth=2.5, zorder=9, marker="o")
ax_map.scatter([work_x], [work_y], color="none", s=500,
               edgecolor="#10B981", linewidth=2.0, zorder=8, alpha=0.5)
ax_map.text(work_x + 350, work_y + 350, "⊕ WORKPLACE",
            ha="left", va="bottom", fontsize=9, fontweight="bold", color="#10B981",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#10B981", linewidth=1.5), zorder=10)

scatter_pts = ax_map.scatter([], [], s=28, edgecolor="white",
                              linewidth=0.4, zorder=5, marker="o")

# Heatmap colourmap (identical to Krsko-heatmap)
_hm_colors = [
    (0.0,  (0.0, 0.0, 0.0, 0.0)),
    (0.15, (0.5, 0.0, 0.8, 0.55)),
    (0.35, (0.0, 0.3, 1.0, 0.70)),
    (0.55, (0.0, 0.9, 0.9, 0.80)),
    (0.72, (1.0, 0.85, 0.0, 0.88)),
    (1.0,  (1.0, 0.1, 0.0, 0.95)),
]
_hm_cmap = LinearSegmentedColormap.from_list(
    "heatmap_rgba", [(v, c) for v, c in _hm_colors], N=256
)
heatmap = ax_map.imshow(np.zeros((300, 300, 4)), origin="lower",
                         zorder=6, interpolation="bilinear")
heatmap.set_visible(False)


# ═══════════════════════════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════════════════════════

energy_hist_min = []
energy_hist_max = []


# ═══════════════════════════════════════════════════════════
# SCATTER UPDATE HELPER  (from Krsko-heatmap)
# ═══════════════════════════════════════════════════════════

def _update_scatter(frame):
    xmin, xmax = ax_map.get_xlim()
    ymin, ymax = ax_map.get_ylim()
    ll  = pos[:, frame, :]
    gdf = gpd.GeoDataFrame(
        geometry=[Point(lon, lat) for lon, lat in ll], crs="EPSG:4326"
    ).to_crs(epsg=3857)

    tmask = (typ[:, frame] == "Work") if show_work_only else np.ones(nv, dtype=bool)
    vmask = (
        (gdf.geometry.x >= xmin) & (gdf.geometry.x <= xmax) &
        (gdf.geometry.y >= ymin) & (gdf.geometry.y <= ymax)
    ) & tmask

    vpts = gdf[vmask]
    if vpts.empty:
        scatter_pts.set_offsets(np.empty((0, 2)))
        return gdf.geometry.x.values[tmask], gdf.geometry.y.values[tmask]

    scatter_pts.set_offsets(np.c_[vpts.geometry.x, vpts.geometry.y])
    colors = np.array([trip_type_colors.get(typ[i, frame], C_GRAY)
                       for i in range(nv)])[vmask]
    scatter_pts.set_color(colors)
    sizes = 28 + eng_min[:, frame] * 10
    scatter_pts.set_sizes(sizes[vmask])
    return gdf.geometry.x.values[tmask], gdf.geometry.y.values[tmask]


# ═══════════════════════════════════════════════════════════
# UPDATE FUNCTION
# ═══════════════════════════════════════════════════════════

fill_band_ref = [ax_energy.fill_between([], [], [])]   # mutable container

def update(frame):
    global energy_hist_min, energy_hist_max

    if frame == 0:
        energy_hist_min.clear()
        energy_hist_max.clear()

    hours   = (frame * 15) // 60
    minutes = (frame * 15) % 60
    t_now   = frame * DT_H

    # ── scatter + heatmap ────────────────────────────────
    xa, ya = _update_scatter(frame)

    xmin, xmax = ax_map.get_xlim()
    ymin, ymax = ax_map.get_ylim()

    if show_heatmap and len(xa) > 0:
        bins  = 200
        dens, _, _ = np.histogram2d(xa, ya, bins=bins,
                                    range=[[xmin, xmax], [ymin, ymax]])
        n_pts  = len(xa)
        sigma  = max(3, min(10, 6 + n_pts * 0.12))
        dens   = gaussian_filter(dens, sigma=sigma)
        dn     = (dens / dens.max()) ** 1.2 if dens.max() > 0 else dens
        heatmap.set_data(_hm_cmap(dn.T))
        heatmap.set_visible(True)
        heatmap.set_extent([xmin, xmax, ymin, ymax])
    else:
        heatmap.set_visible(False)

    for patch in zone_patches:
        patch.set_visible(show_zones)

    # ── charging demand ───────────────────────────────────
    energy_hist_min.append(e_min_total[frame])
    energy_hist_max.append(e_max_total[frame])
    nf  = frame + 1
    x_t = np.arange(nf) * DT_H

    energy_line_min.set_data(x_t, energy_hist_min)
    energy_line_max.set_data(x_t, energy_hist_max)

    try:
        fill_band_ref[0].remove()
    except Exception:
        pass
    if nf > 1:
        fill_band_ref[0] = ax_energy.fill_between(
            x_t, energy_hist_min, energy_hist_max,
            alpha=0.18, color="#94A3B8"
        )

    ymax_e = max(float(e_max_total[:nf].max()), 1)
    ax_energy.set_xlim(0, 24)
    ax_energy.set_ylim(0, ymax_e * 1.15)
    vline_e.set_xdata([t_now, t_now])
    vline_e.set_ydata([0, ymax_e * 1.15])

    # ── arrivals / departures ─────────────────────────────
    mv = np.arange(intervals) <= frame
    ha = arr_hist * mv
    hd = dep_hist * mv
    for bar, v in zip(bars_arr, ha):
        bar.set_height(v)
    for bar, v, b in zip(bars_dep, hd, ha):
        bar.set_height(v)
        bar.set_y(b)
    max_bar = max(float((ha + hd).max()), 1)
    ax_arrivals.set_ylim(0, max_bar * 1.5 + 1)
    vline_arr.set_xdata([t_now, t_now])
    vline_arr.set_ydata([0, max_bar * 1.5 + 1])

    # ── vehicles by state ─────────────────────────────────
    for s, line in state_line_plots.items():
        line.set_data(t_axis[:nf], state_counts[s][:nf])
    vline_flex.set_xdata([t_now, t_now])

    # ── clock hand ────────────────────────────────────────
    ang = np.pi/2 - 2*np.pi * t_now / 24
    clock_hand.set_xdata([0, 0.62 * np.cos(ang)])
    clock_hand.set_ydata([0, 0.62 * np.sin(ang)])
    clock_text.set_text(f"{hours:02d}:{minutes:02d}")
    time_display_text.set_text(f"{hours:02d}:{minutes:02d}")

    # ── KPI ───────────────────────────────────────────────
    c_park = int(parked[frame])
    e_now  = e_min_total[frame]
    kpi1_val.set_text(str(c_park))
    kpi2_val.set_text(f"{e_now:.0f} kW")

    header_text.set_text(
        f"Parked @ work: {c_park}  │  "
        f"Min demand: {e_now:.0f} kW  │  "
        f"Max demand: {e_max_total[frame]:.0f} kW  │  "
        f"{hours:02d}:{minutes:02d}"
    )

    return (scatter_pts, energy_line_min, energy_line_max, clock_hand)


# ═══════════════════════════════════════════════════════════
# SCROLL ZOOM + PAN  (identical to Krsko-heatmap)
# ═══════════════════════════════════════════════════════════

ZOOM_FACTOR = 1.25
_pan = {}

def on_scroll(event):
    if event.inaxes is not ax_map: return
    xmin, xmax = ax_map.get_xlim(); ymin, ymax = ax_map.get_ylim()
    cx_, cy_ = event.xdata, event.ydata
    if cx_ is None: return
    sc  = 1/ZOOM_FACTOR if event.button == "up" else ZOOM_FACTOR
    nhx = (xmax-xmin)/2*sc; nhy = (ymax-ymin)/2*sc
    ncx = cx_ + ((xmin+xmax)/2 - cx_)*sc
    ncy = cy_ + ((ymin+ymax)/2 - cy_)*sc
    ax_map.set_xlim(ncx-nhx, ncx+nhx)
    ax_map.set_ylim(ncy-nhy, ncy+nhy)
    ax_map.set_aspect("equal"); fig.canvas.draw_idle()

def on_press(event):
    if event.inaxes is not ax_map or event.button != 3: return
    _pan.update(x=event.xdata, y=event.ydata,
                xl=ax_map.get_xlim(), yl=ax_map.get_ylim())

def on_motion(event):
    if event.inaxes is not ax_map or event.button != 3 or not _pan: return
    if event.xdata is None: return
    dx = event.xdata - _pan["x"]; dy = event.ydata - _pan["y"]
    x0, x1 = _pan["xl"]; y0, y1 = _pan["yl"]
    ax_map.set_xlim(x0-dx, x1-dx); ax_map.set_ylim(y0-dy, y1-dy)
    fig.canvas.draw_idle()

fig.canvas.mpl_connect("scroll_event",        on_scroll)
fig.canvas.mpl_connect("button_press_event",  on_press)
fig.canvas.mpl_connect("motion_notify_event", on_motion)


# ═══════════════════════════════════════════════════════════
# ANIMATION
# ═══════════════════════════════════════════════════════════

ani = FuncAnimation(fig, update, frames=intervals, interval=900, blit=False)
plt.show(block=True)

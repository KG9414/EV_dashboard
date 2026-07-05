import matplotlib
matplotlib.use("TkAgg")

from krsko_osm_cone import (
    get_krsko_clusters,
    plot_landuse_layers,
    build_zone_glow,
    precompute_zone_counts,
    GLOW_ZONES,
)

import pandas as pd
import numpy as np
import geopandas as gpd
import contextily as ctx  # type: ignore
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from shapely.geometry import Point
from matplotlib.animation import FuncAnimation
from scipy.ndimage import gaussian_filter
from matplotlib.widgets import CheckButtons
import matplotlib.patches as mpatches


# ===============================
# LOAD OSM DATA
# ===============================

clusters, landuse_gdf = get_krsko_clusters()


# ===============================
# LOAD EXCEL FILES
# ===============================

file_2trips = "03_Vehicle_trip_parameters_100_EVs_2_trips_1_days.xlsx"
file_4trips = "03_Vehicle_trip_parameters_20_EVs_4_trips_1_days.xlsx"

df_2 = pd.read_excel(file_2trips)
df_4 = pd.read_excel(file_4trips)

df_2.columns = df_2.columns.str.strip()
df_4.columns = df_4.columns.str.strip()

intervals = 96   # 96 × 15 min = 24 h


# ===============================
# HELPER: BUILD MATRICES
# ===============================

def build_matrices(df):

    work_trip     = df[df["Trip type"] == "Work"].iloc[0]
    work_location = (work_trip["End_lon"], work_trip["End_lat"])

    home_locations = (
        df[df["Trip ID"] == 1]
        .groupby("Vehicle ID")[["Start_lon", "Start_lat"]]
        .first()
    )

    number_of_vehicles = df["Vehicle ID"].nunique()
    positions          = np.zeros((number_of_vehicles, intervals, 2))
    trip_types_matrix  = np.full((number_of_vehicles, intervals), "Home", dtype=object)
    energy_matrix      = np.zeros((number_of_vehicles, intervals))

    for vid in range(1, number_of_vehicles + 1):

        vehicle_trips = df[df["Vehicle ID"] == vid].sort_values("Trip ID")
        home_coords   = (
            home_locations.loc[vid]["Start_lon"],
            home_locations.loc[vid]["Start_lat"],
        )
        current_coords = home_coords
        current_time   = 0

        for _, trip in vehicle_trips.iterrows():

            start       = int(trip["Start"])
            end         = int(trip["End"])
            dest_coords = (trip["End_lon"], trip["End_lat"])
            trip_type   = trip["Trip type"]
            energy      = trip["Energy_kWh"]

            positions[vid - 1, current_time:start, :] = current_coords
            trip_types_matrix[vid - 1, current_time:start] = "Home"

            for t in range(start, end):
                alpha = (t - start) / (end - start)
                lon   = current_coords[0] * (1 - alpha) + dest_coords[0] * alpha
                lat   = current_coords[1] * (1 - alpha) + dest_coords[1] * alpha
                lon  += np.random.normal(0, 0.00005)
                lat  += np.random.normal(0, 0.00005)
                positions[vid - 1, t, :]      = (lon, lat)
                trip_types_matrix[vid - 1, t] = "Driving"
                energy_matrix[vid - 1, t]     = energy

            positions[vid - 1, end, :] = dest_coords
            next_trip = vehicle_trips[vehicle_trips["Trip ID"] > trip["Trip ID"]]

            if not next_trip.empty:
                next_start = int(next_trip.iloc[0]["Start"])
                positions[vid - 1, end:next_start, :]      = dest_coords
                trip_types_matrix[vid - 1, end:next_start] = trip_type
                energy_matrix[vid - 1, end:next_start]     = energy
                current_time = next_start
            else:
                current_time = end

            current_coords = dest_coords

        positions[vid - 1, current_time:, :]      = home_coords
        trip_types_matrix[vid - 1, current_time:] = "Home"

    return positions, trip_types_matrix, energy_matrix, home_locations, work_location, number_of_vehicles


# ===============================
# BUILD MATRICES
# ===============================

(pos2, types2, energy2, home2, work_loc2, n2) = build_matrices(df_2)
(pos4, types4, energy4, home4, work_loc4, n4) = build_matrices(df_4)


# ===============================
# PRE-COMPUTE ARRIVAL / DEPARTURE TIMES
# Za vsako vozilo poiščemo točen frame prihoda in odhoda z dela
# → kumulativni histogram (gladek, "stohastičen" prikaz porazdelitve)
# ===============================

def compute_work_flow_times(types_matrix, n_vehicles):
    """
    Vrne arrival_frames in departure_frames — seznam frame-ov (0..95)
    kdaj vsako vozilo pride / odide z dela.
    Upošteva samo prehode Driving→Work in Work→Driving.
    """
    arrivals   = []
    departures = []
    for vid in range(n_vehicles):
        for t in range(1, intervals):
            prev = types_matrix[vid, t - 1]
            curr = types_matrix[vid, t]
            if prev == "Driving" and curr == "Work":
                arrivals.append(t)
            if prev == "Work" and curr == "Driving":
                departures.append(t)
    return arrivals, departures


arr_frames2, dep_frames2 = compute_work_flow_times(types2, n2)
arr_frames4, dep_frames4 = compute_work_flow_times(types4, n4)

# Pretvori v ure (float)
def frames_to_hours(frames):
    return [f * 0.25 for f in frames]

arr_hours2 = frames_to_hours(arr_frames2)
dep_hours2 = frames_to_hours(dep_frames2)
arr_hours4 = frames_to_hours(arr_frames4)
dep_hours4 = frames_to_hours(dep_frames4)


# ===============================
# PRE-COMPUTE MAX ENERGY (za energijski graf)
# Min  = trenutna poraba pri parkiranju (Energy_kWh tista pot)
# Max  = min × 2  (avto potrebuje še toliko za pot domov)
# ===============================

def compute_energy_range(types_matrix, energy_matrix, n_vehicles):
    """
    Za vsak frame: min (dejanska poraba) in max (×2 rezerva za pot domov).
    Vrne matriki oblike (intervals,).
    """
    e_min = np.zeros(intervals)
    e_max = np.zeros(intervals)
    for t in range(intervals):
        mask    = types_matrix[:, t] == "Work"
        e_vals  = energy_matrix[mask, t]
        e_min[t] = np.sum(e_vals)
        e_max[t] = np.sum(e_vals) * 2.0
    return e_min, e_max

e_min2, e_max2 = compute_energy_range(types2, energy2, n2)
e_min4, e_max4 = compute_energy_range(types4, energy4, n4)


# ===============================
# DISPLAY STATE
# ===============================

show_heatmap    = True
show_energy     = False
show_2trips     = True
show_4trips     = True
show_work_only  = False
show_zone_glow  = False


# ===============================
# TRIP TYPE COLORS & LEGEND
# ===============================

trip_type_colors = {
    "Work":      "#1565C0",
    "Shopping":  "#C62828",
    "Leisure":   "#2E7D32",
    "Education": "#E65100",
    "Business":  "#6A1B9A",
    "Home":      "#212121",
    "Driving":   "#78909C",
}

legend_patches = [
    mpatches.Patch(color=color, label=trip)
    for trip, color in trip_type_colors.items()
]


# ===============================
# FIGURE LAYOUT
# -----------------------------------------------
# Levo (37 %):  vrstica 0 = energy graf
#               vrstica 1 = parking/flow graf
#               vrstica 2 = legenda trip-type barv
#               pod gs    = checkbox widget
# Desno (63 %): zemljevid čez vse 3 vrstice
# ===============================

fig = plt.figure(figsize=(22, 10))

gs = gridspec.GridSpec(
    nrows=3,
    ncols=2,
    figure=fig,
    left=0.03,
    right=0.99,
    top=0.93,
    bottom=0.26,
    wspace=0.06,
    hspace=0.55,
    width_ratios=[1, 2.4],        # levo : desno — zemljevid zdaj 2.4x širši
    height_ratios=[1, 1, 0.55],
)

ax_graph_energy  = fig.add_subplot(gs[0, 0])
ax_graph_parking = fig.add_subplot(gs[1, 0])
ax_legend        = fig.add_subplot(gs[2, 0])
ax_legend.set_axis_off()

# Zemljevid — desno, čez vse vrstice gs
ax = fig.add_subplot(gs[:, 1])

# ── Legenda trip-type barv ── v spodnjem levem pasu (nad checkboxi)
ax_leg2 = fig.add_axes([0.01, 0.13, 0.28, 0.11])
ax_leg2.set_axis_off()
ax_leg2.legend(
    handles=legend_patches,
    loc="center",
    fontsize=8,
    frameon=True,
    title="Trip type colors",
    title_fontsize=8,
    ncol=4,
)

# ── CheckButtons ── pod legendo (5 možnosti zdaj)
rax = fig.add_axes([0.01, 0.01, 0.28, 0.13])
check = CheckButtons(
    rax,
    ["Heatmap", "Energy colors", "2 trips", "4 trips",
     "Only Work vehicles", "Zone glow"],
    [True,       False,           True,       True,
     False,                       False],
)

def toggle_display(label):
    global show_heatmap, show_energy, show_2trips, show_4trips
    global show_work_only, show_zone_glow
    if label == "Heatmap":
        show_heatmap = not show_heatmap
    elif label == "Energy colors":
        show_energy = not show_energy
    elif label == "2 trips":
        show_2trips = not show_2trips
    elif label == "4 trips":
        show_4trips = not show_4trips
    elif label == "Only Work vehicles":
        show_work_only = not show_work_only
    elif label == "Zone glow":
        show_zone_glow = not show_zone_glow

check.on_clicked(toggle_display)


# ===============================
# MAP CENTER & LIMITS
# ===============================

center_lon = pd.concat([df_2["Start_lon"], df_4["Start_lon"]]).mean()
center_lat = pd.concat([df_2["Start_lat"], df_4["Start_lat"]]).mean()

center_point = Point(center_lon, center_lat)
gdf_center   = gpd.GeoDataFrame(geometry=[center_point], crs="EPSG:4326").to_crs(epsg=3857)
center_x     = gdf_center.geometry.x[0]
center_y     = gdf_center.geometry.y[0]

buffer = 5000
ax.set_xlim(center_x - buffer, center_x + buffer)
ax.set_ylim(center_y - buffer, center_y + buffer)
ax.set_aspect("equal")


# ===============================
# LANDUSE + BASEMAP
# ===============================

plot_landuse_layers(ax, landuse_gdf)
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

# ===============================
# ZONE GLOW SETUP
# — narišemo cone kot PathCollection z alpha=0 (nevidno)
# — predobdelamo število vozil na cono za vsak frame (enkrat pred animacijo)
# ===============================

print("Pripravljam zone glow — preračunam položaje vozil v conah ...")
zone_dict   = build_zone_glow(landuse_gdf, ax)
zone_counts = precompute_zone_counts(
    zone_dict,
    [pos2, pos4],
    [types2, types4],
    [n2, n4],
    intervals,
)

# Maksimalno število vozil v katerikoli coni (za normalizacijo alpha)
zone_max = {
    k: max(int(zone_counts[k].max()), 1)
    for k in zone_dict
}
print(f"Zone glow pripravljeno. Cone: {list(zone_dict.keys())}")


# ===============================
# WORK MARKER
# ===============================

work_point = gpd.GeoSeries([Point(work_loc2)], crs="EPSG:4326").to_crs(epsg=3857)
ax.scatter(
    work_point.x, work_point.y,
    color="yellow", alpha=0.7, s=140,
    edgecolor="black", linewidth=1.2, zorder=6,
)
ax.set_axis_off()


# ===============================
# SCATTER — vozila
# ===============================

scatter2 = ax.scatter([], [], s=40, edgecolor="black", linewidth=0.5,
                      zorder=5, marker="o")
scatter4 = ax.scatter([], [], s=40, edgecolor="black", linewidth=0.5,
                      zorder=5, marker="^")


# ===============================
# COLORBAR
# ===============================

energy_colorbar = plt.colorbar(scatter2, ax=ax, fraction=0.025, pad=0.01)
energy_colorbar.set_label("Energy consumption (kWh)", fontsize=8)
energy_colorbar.ax.set_visible(False)


# ===============================
# HEATMAP
# ===============================

heatmap = ax.imshow(
    np.zeros((300, 300)),
    cmap="turbo", alpha=0.35,
    origin="lower", zorder=1,
)
heatmap.set_interpolation("gaussian")


# ===============================
# ENERGY GRAPH  (levo zgoraj)
# — polna črta = min (dejanska poraba pri parkiranju)
# — zasenčeno območje = pas do max (×2, rezerva za pot domov)
# ===============================

_t_all = np.arange(intervals) * 0.25   # 0 .. 23.75 h

energy_line2,  = ax_graph_energy.plot([], [], lw=2, color="steelblue",  label="2 trips (min)")
energy_line4,  = ax_graph_energy.plot([], [], lw=2, color="darkorange", label="4 trips (min)")

# fill_between objekti — ustvarimo z praznimi podatki, zamenjamo v update()
fill2 = ax_graph_energy.fill_between(
    [], [], [],
    alpha=0.18, color="steelblue", label="2 trips (max ×2)"
)
fill4 = ax_graph_energy.fill_between(
    [], [], [],
    alpha=0.18, color="darkorange", label="4 trips (max ×2)"
)

ax_graph_energy.legend(fontsize=7, ncol=2)
ax_graph_energy.set_xlim(0, 24)
ax_graph_energy.set_xticks(range(0, 25, 3))
ax_graph_energy.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)], fontsize=7)
ax_graph_energy.set_ylim(0, 1)
ax_graph_energy.set_title("Parking energy demand — min / max×2 (kWh)", fontsize=9)
ax_graph_energy.set_xlabel("Time", fontsize=8)
ax_graph_energy.set_ylabel("Energy (kWh)", fontsize=8)
ax_graph_energy.grid(True, alpha=0.4)
ax_graph_energy.tick_params(axis="y", labelsize=7)


# ===============================
# ARRIVALS / DEPARTURES GRAPH  (levo sredina)
# histogram — bar chartm ki se gradi postopoma med animacijo.
# X os = ura dneva (0-24), bins po 15 min
# Prikazuje: koliko vozil je prišlo / odšlo z DELA do tega trenutka.
# ===============================

bin_edges = np.arange(0, 24.25, 0.25)   # 97 robov → 96 košev
bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
bar_width = 0.22   # uri

# 2 trips — prihodi (oranžna) in odhodi (modra)
bars_arr2  = ax_graph_parking.bar(bin_centers, np.zeros(intervals),
                                   width=bar_width, color="orange",    alpha=0.75,
                                   label="Arr. 2t", align="center")
bars_dep2  = ax_graph_parking.bar(bin_centers, np.zeros(intervals),
                                   width=bar_width, color="steelblue", alpha=0.75,
                                   label="Dep. 2t", align="center",
                                   bottom=np.zeros(intervals))   # offset za stacking

# 4 trips — prihodi (rdeča) in odhodi (mornarsko modra), malo zamaknjeni
bars_arr4  = ax_graph_parking.bar(bin_centers + bar_width, np.zeros(intervals),
                                   width=bar_width, color="red",  alpha=0.75,
                                   label="Arr. 4t", align="center", linestyle="--",
                                   edgecolor="darkred", linewidth=0.4)
bars_dep4  = ax_graph_parking.bar(bin_centers + bar_width, np.zeros(intervals),
                                   width=bar_width, color="navy", alpha=0.75,
                                   label="Dep. 4t", align="center",
                                   edgecolor="midnightblue", linewidth=0.4,
                                   bottom=np.zeros(intervals))

ax_graph_parking.legend(fontsize=7, ncol=2)
ax_graph_parking.set_xlim(0, 24)
ax_graph_parking.set_xticks(range(0, 25, 3))
ax_graph_parking.set_xticklabels([f"{h:02d}h" for h in range(0, 25, 3)], fontsize=7)
ax_graph_parking.set_ylim(0, max(n2, n4) + 2)
ax_graph_parking.set_title(
    "Work arrivals / departures", # (samo delovna lokacija, kumulativni histogram)
    fontsize=8,
)
ax_graph_parking.set_xlabel("Time", fontsize=8)
ax_graph_parking.set_ylabel("Vehicles", fontsize=8)
ax_graph_parking.grid(True, alpha=0.3, axis="y")
ax_graph_parking.tick_params(axis="y", labelsize=7)

# Vnaprej izračunaj histograme za vse čase
# arr_hist2[t] = koliko vozil je prišlo v košu t (0-indexed)
def build_hist(hour_list):
    h = np.zeros(intervals)
    for hr in hour_list:
        idx = int(hr / 0.25)
        if 0 <= idx < intervals:
            h[idx] += 1
    return h

arr_hist2 = build_hist(arr_hours2)
dep_hist2 = build_hist(dep_hours2)
arr_hist4 = build_hist(arr_hours4)
dep_hist4 = build_hist(dep_hours4)


# ===============================
# HISTORY LISTS (za energy graf — gradi se sproti)
# ===============================

parking_energy_history2 = []
parking_energy_history4 = []


# ===============================
# HELPER: scatter update
# ===============================

def _update_scatter(scatter_obj, positions, types_matrix, energy_matrix,
                    n_vehicles, frame, show):

    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    lon_lat = positions[:, frame, :]
    gdf = gpd.GeoDataFrame(
        geometry=[Point(lon, lat) for lon, lat in lon_lat],
        crs="EPSG:4326",
    ).to_crs(epsg=3857)

    if not show:
        scatter_obj.set_offsets(np.empty((0, 2)))
        scatter_obj.set_visible(False)
        return np.array([]), np.array([])

    scatter_obj.set_visible(True)

    # Filter: samo vozila z Work tipom (če je vklopljeno)
    vehicle_mask = np.ones(n_vehicles, dtype=bool)
    if show_work_only:
        vehicle_mask = types_matrix[:, frame] == "Work"

    visible_mask = (
        (gdf.geometry.x >= xmin) & (gdf.geometry.x <= xmax) &
        (gdf.geometry.y >= ymin) & (gdf.geometry.y <= ymax)
    ) & vehicle_mask

    visible_points = gdf[visible_mask]

    if visible_points.empty:
        scatter_obj.set_offsets(np.empty((0, 2)))
        return np.array([]), np.array([])

    scatter_obj.set_offsets(
        np.c_[visible_points.geometry.x, visible_points.geometry.y]
    )

    colors = np.array([
        trip_type_colors.get(types_matrix[i, frame], "gray")
        for i in range(n_vehicles)
    ])

    if show_energy:
        scatter_obj.set_array(energy_matrix[:, frame][visible_mask])
        scatter_obj.set_cmap("plasma")
    else:
        scatter_obj.set_color(colors[visible_mask])

    sizes = 30 + energy_matrix[:, frame] * 12
    scatter_obj.set_sizes(sizes[visible_mask])

    # Za heatmap vedno vrni vse koordinate (ne samo work), razen če work_only
    if show_work_only:
        return gdf.geometry.x.values[vehicle_mask], gdf.geometry.y.values[vehicle_mask]
    return gdf.geometry.x.values, gdf.geometry.y.values


# ===============================
# UPDATE FUNCTION
# ===============================

def update(frame):

    global parking_energy_history2, parking_energy_history4
    global fill2, fill4

    if frame == 0:
        parking_energy_history2.clear()
        parking_energy_history4.clear()

    # ── scatter ──────────────────────────────────────────────────────
    x2, y2 = _update_scatter(scatter2, pos2, types2, energy2, n2, frame, show_2trips)
    x4, y4 = _update_scatter(scatter4, pos4, types4, energy4, n4, frame, show_4trips)

    energy_colorbar.ax.set_visible(show_energy)

    # ── heatmap ──────────────────────────────────────────────────────
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    if show_2trips and show_4trips:
        x_all = np.concatenate([x2, x4])
        y_all = np.concatenate([y2, y4])
    elif show_2trips:
        x_all, y_all = x2, y2
    elif show_4trips:
        x_all, y_all = x4, y4
    else:
        x_all, y_all = np.array([]), np.array([])

    if show_heatmap and len(x_all) > 0:
        density, _, _ = np.histogram2d(
            x_all, y_all, bins=250,
            range=[[xmin, xmax], [ymin, ymax]],
        )
        sigma   = min(3 + density.max() * 1.5, 15)
        density = gaussian_filter(density, sigma=sigma)
        heatmap.set_data(density.T)
        if density.max() > 0:
            heatmap.set_clim(vmin=0, vmax=density.max())
    else:
        heatmap.set_data(np.zeros((250, 250)))

    heatmap.set_extent([xmin, xmax, ymin, ymax])

    # ── zone glow ─────────────────────────────────────────────────────
    # Alpha = 0 če izklopljeno; sicer proporcionalno številu vozil v coni.
    # Min alpha (vsaj malo vidno): 0.05  Max alpha: 0.75
    ALPHA_MIN = 0.05
    ALPHA_MAX = 0.75

    for k, zinfo in zone_dict.items():
        if not show_zone_glow:
            zinfo["collection"].set_alpha(0.0)
            continue
        cnt      = zone_counts[k][frame]
        norm     = cnt / zone_max[k]          # 0.0 – 1.0
        alpha    = ALPHA_MIN + norm * (ALPHA_MAX - ALPHA_MIN)
        r, g, b, _ = zinfo["color"]
        zinfo["collection"].set_facecolor((r, g, b, alpha))

    # ── čas ──────────────────────────────────────────────────────────
    hours   = (frame * 15) // 60
    minutes = (frame * 15) % 60

    # ── work energy (min) ────────────────────────────────────────────
    parking_energy_history2.append(e_min2[frame] if show_2trips else 0)
    parking_energy_history4.append(e_min4[frame] if show_4trips else 0)

    n_frames = frame + 1
    x_t      = np.arange(n_frames) * 0.25

    # min linije
    energy_line2.set_data(x_t, parking_energy_history2[:n_frames])
    energy_line4.set_data(x_t, parking_energy_history4[:n_frames])
    energy_line2.set_visible(show_2trips)
    energy_line4.set_visible(show_4trips)

    # max fill_between — odstrani stari, nariši novega
    global fill2, fill4
    fill2.remove()
    fill4.remove()

    if show_2trips and n_frames > 1:
        fill2 = ax_graph_energy.fill_between(
            x_t,
            parking_energy_history2[:n_frames],
            e_max2[:n_frames],
            alpha=0.18, color="steelblue",
        )
    else:
        fill2 = ax_graph_energy.fill_between([], [], [], alpha=0.18, color="steelblue")

    if show_4trips and n_frames > 1:
        fill4 = ax_graph_energy.fill_between(
            x_t,
            parking_energy_history4[:n_frames],
            e_max4[:n_frames],
            alpha=0.18, color="darkorange",
        )
    else:
        fill4 = ax_graph_energy.fill_between([], [], [], alpha=0.18, color="darkorange")

    ax_graph_energy.set_xlim(0, 24)
    max_e = max(
        np.max(e_max2) if show_2trips else 0,
        np.max(e_max4) if show_4trips else 0,
        1,
    )
    ax_graph_energy.set_ylim(0, max_e * 1.1)

    # ── kumulativni histogram (arrivals/departures) ───────────────────
    # Prikaži samo koše do trenutnega frame-a; ostale postavi na 0
    mask_visible = np.arange(intervals) <= frame

    h_arr2 = arr_hist2 * mask_visible if show_2trips else np.zeros(intervals)
    h_dep2 = dep_hist2 * mask_visible if show_2trips else np.zeros(intervals)
    h_arr4 = arr_hist4 * mask_visible if show_4trips else np.zeros(intervals)
    h_dep4 = dep_hist4 * mask_visible if show_4trips else np.zeros(intervals)

    for bar, val in zip(bars_arr2, h_arr2):
        bar.set_height(val)
    for bar, val, bot in zip(bars_dep2, h_dep2, h_arr2):
        bar.set_height(val)
        bar.set_y(bot)   # stack nad prihodi
    for bar, val in zip(bars_arr4, h_arr4):
        bar.set_height(val)
    for bar, val, bot in zip(bars_dep4, h_dep4, h_arr4):
        bar.set_height(val)
        bar.set_y(bot)

    max_bar = max(
        np.max(h_arr2 + h_dep2) if (show_2trips) else 0,
        np.max(h_arr4 + h_dep4) if (show_4trips) else 0,
        1,
    )
    ax_graph_parking.set_ylim(0, max_bar * 1.4 + 1)

    # ── naslov zemljevida ─────────────────────────────────────────────
    e2 = parking_energy_history2[-1] if parking_energy_history2 else 0
    e4 = parking_energy_history4[-1] if parking_energy_history4 else 0
    c2 = int(np.sum(types2[:, frame] == "Work"))
    c4 = int(np.sum(types4[:, frame] == "Work"))

    ax.set_title(
        f"Čas:  {hours:02d}:{minutes:02d}"
        f"     |     2 trips → {c2} vozil @ {e2:.1f} kWh  (max {e_max2[frame]:.1f} kWh)"
        f"     |     4 trips → {c4} vozil @ {e4:.1f} kWh  (max {e_max4[frame]:.1f} kWh)",
        fontsize=9,
        pad=6,
    )

    return (scatter2, scatter4, energy_line2, energy_line4)


# ===============================
# SCROLL ZOOM + PAN NA ZEMLJEVIDU
# ===============================

ZOOM_FACTOR = 1.25   # kako agresiven je zoom (> 1)

def on_scroll(event):
    """Zoom in/out z miškino kolesce — samo nad zemljevidom."""
    if event.inaxes is not ax:
        return
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    cx, cy = event.xdata, event.ydata
    if cx is None or cy is None:
        return
    scale = 1.0 / ZOOM_FACTOR if event.button == "up" else ZOOM_FACTOR
    new_half_x = (xmax - xmin) / 2 * scale
    new_half_y = (ymax - ymin) / 2 * scale
    cur_cx = (xmin + xmax) / 2
    cur_cy = (ymin + ymax) / 2
    new_cx = cx + (cur_cx - cx) * scale
    new_cy = cy + (cur_cy - cy) * scale
    ax.set_xlim(new_cx - new_half_x, new_cx + new_half_x)
    ax.set_ylim(new_cy - new_half_y, new_cy + new_half_y)
    ax.set_aspect("equal")
    fig.canvas.draw_idle()

# Pan z desnim gumbom miške (klik + vleci)
_pan_start = {}

def on_press(event):
    if event.inaxes is not ax or event.button != 3:
        return
    _pan_start["x"]    = event.xdata
    _pan_start["y"]    = event.ydata
    _pan_start["xlim"] = ax.get_xlim()
    _pan_start["ylim"] = ax.get_ylim()

def on_motion(event):
    if event.inaxes is not ax or event.button != 3:
        return
    if not _pan_start or event.xdata is None:
        return
    dx = event.xdata - _pan_start["x"]
    dy = event.ydata - _pan_start["y"]
    x0, x1 = _pan_start["xlim"]
    y0, y1 = _pan_start["ylim"]
    ax.set_xlim(x0 - dx, x1 - dx)
    ax.set_ylim(y0 - dy, y1 - dy)
    fig.canvas.draw_idle()

fig.canvas.mpl_connect("scroll_event",        on_scroll)
fig.canvas.mpl_connect("button_press_event",  on_press)
fig.canvas.mpl_connect("motion_notify_event", on_motion)


# ===============================
# ANIMATION
# ===============================

ani = FuncAnimation(
    fig,
    update,
    frames=intervals,
    interval=900,
    blit=False,
)

plt.show()
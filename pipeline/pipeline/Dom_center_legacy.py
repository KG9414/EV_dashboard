import matplotlib
matplotlib.use("TkAgg")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from krsko_osm_clusters import get_krsko_clusters
from spatial_config import get_krsko_landuse

import pandas as pd
import numpy as np
import geopandas as gpd
import contextily as ctx # type: ignore
import matplotlib.pyplot as plt

from shapely.geometry import Point
from matplotlib.animation import FuncAnimation
from scipy.ndimage import gaussian_filter

from matplotlib.widgets import Button, Slider, CheckButtons
import matplotlib.patches as mpatches


# ===============================
# LOAD OSM DATA
# ===============================

clusters, landuse_gdf = get_krsko_clusters()


# ===============================
# LOAD EXCEL
# ===============================

#file_path = "03_Vehicle_trip_parameters_20_EVs_2_trips_1_days.xlsx"
file_path = "03_Vehicle_trip_parameters_5_EVs_2_trips_1_days.xlsx"


df = pd.read_excel(file_path)

df.columns = df.columns.str.strip()

# ===============================
# WORK LOCATION
# ===============================

work_trip = df[df["Trip type"] == "Work"].iloc[0]

work_location = (
    work_trip["End_lon"],
    work_trip["End_lat"]
)


# ===============================
# HOME LOCATIONS
# ===============================

home_locations = (
    df[df["Trip ID"] == 1]
    .groupby("Vehicle ID")[["Start_lon", "Start_lat"]]
    .first()
)

number_of_vehicles = df["Vehicle ID"].nunique()
intervals = 96


# ===============================
# STORAGE MATRICES
# ===============================

parking_energy_history = []
time_history = []

parking_count_history = []
work_arrival_history = []
work_departure_history = []

positions = np.zeros((number_of_vehicles, intervals, 2))

trip_types_matrix = np.full(
    (number_of_vehicles, intervals),
    "Home",
    dtype=object
)

energy_matrix = np.zeros((number_of_vehicles, intervals))


# ===============================
# GENERATE MOVEMENTS
# ===============================

for vid in range(1, number_of_vehicles + 1):

    vehicle_trips = df[df["Vehicle ID"] == vid].sort_values("Trip ID")

    home_coords = (
        home_locations.loc[vid]["Start_lon"],
        home_locations.loc[vid]["Start_lat"]
    )

    current_coords = home_coords
    current_time = 0

    for _, trip in vehicle_trips.iterrows():

        start = int(trip["Start"])
        end = int(trip["End"])

        dest_coords = (
            trip["End_lon"],
            trip["End_lat"]
        )

        trip_type = trip["Trip type"]
        energy = trip["Energy_kWh"]

        # mirovanje do start
        positions[vid-1, current_time:start, :] = current_coords
        trip_types_matrix[vid-1, current_time:start] = "Home"

        # vožnja
        for t in range(start, end):

            alpha = (t - start) / (end - start)

            lon = current_coords[0]*(1-alpha) + dest_coords[0]*alpha
            lat = current_coords[1]*(1-alpha) + dest_coords[1]*alpha

            lon += np.random.normal(0, 0.00005)
            lat += np.random.normal(0, 0.00005)

            positions[vid-1, t, :] = (lon, lat)

            # med vožnjo ni Work
            trip_types_matrix[vid-1, t] = "Driving"
            
            energy_matrix[vid-1, t] = energy

        
        # arrival exactly at destination
        positions[vid-1, end, :] = dest_coords

        # poiščemo naslednji trip (TripID2)
        next_trip = vehicle_trips[vehicle_trips["Trip ID"] > trip["Trip ID"]]

        if not next_trip.empty:

            next_start = int(next_trip.iloc[0]["Start"])

            # avto ostane na destinaciji do naslednjega tripa
            positions[vid-1, end:next_start, :] = dest_coords
            trip_types_matrix[vid-1, end:next_start] = trip_type

            # energija potrebna na parkirišču
            energy_matrix[vid-1, end:next_start] = energy

            current_time = next_start

        else:

            current_time = end

        current_coords = dest_coords

    # po zadnjem tripu vsi doma
    positions[vid-1, current_time:, :] = home_coords
    trip_types_matrix[vid-1, current_time:] = "Home"


# ===============================
# BARVE GLEDE NA TIP
# ===============================

trip_type_colors = {
    "Work": "blue",
    "Shopping": "red",
    "Leisure": "green",
    "Education": "orange",
    "Business": "purple",
    "Home": "black"
}

legend_patches = [
    mpatches.Patch(color=color, label=trip)
    for trip, color in trip_type_colors.items()
]


# ===============================
# PLOT
# ===============================

# fig, ax = plt.subplots(figsize=(10,10))
fig, (ax, ax_graph_energy, ax_graph_parking) = plt.subplots(
    3,
    1,
    figsize=(10,14),
    gridspec_kw={"height_ratios":[4,1,1]}
    #gridspec_kw={"height_ratios":[5,1.2,1.2]}
    #constrained_layout=True
)

#plt.subplots_adjust(top=0.92, bottom=0.1)

# ===============================
# DISPLAY TOGGLES
# ===============================

show_heatmap = True
show_energy = False

rax = plt.axes([0.02, 0.4, 0.15, 0.15])

check = CheckButtons(
    rax,
    ["Heatmap", "Energy colors"],
    [True, False]
)

# ===============================
# MAP CENTER
# ===============================

center_lon = df["Start_lon"].mean()
center_lat = df["Start_lat"].mean()

center_point = Point(center_lon, center_lat)

gdf_center = gpd.GeoDataFrame(
    geometry=[center_point],
    crs="EPSG:4326"
).to_crs(epsg=3857)

center_x = gdf_center.geometry.x[0]
center_y = gdf_center.geometry.y[0]

buffer = 5000

ax.set_xlim(center_x-buffer, center_x+buffer)
ax.set_ylim(center_y-buffer, center_y+buffer)

ax.set_aspect('equal')


# ===============================
# LANDUSE COLORS
# ===============================

landuse_gdf_3857 = landuse_gdf.to_crs(epsg=3857)

residential = landuse_gdf_3857[
    landuse_gdf_3857["landuse"]=="residential"
]

industrial = landuse_gdf_3857[
    landuse_gdf_3857["landuse"]=="industrial"
]

commercial = landuse_gdf_3857[
    landuse_gdf_3857["landuse"].isin(["commercial","retail"])
]

parks = landuse_gdf_3857[
    landuse_gdf_3857["leisure"].isin(["park","recreation_ground"])
]

education = landuse_gdf_3857[
    landuse_gdf_3857["amenity"].isin(["school","college","university"])
]


residential.plot(ax=ax,color="#2c7bb6",alpha=0.3,zorder=2)
industrial.plot(ax=ax,color="#d7191c",alpha=0.3,zorder=2)
commercial.plot(ax=ax,color="#fdae61",alpha=0.3,zorder=2)
parks.plot(ax=ax,color="#1a9641",alpha=0.3,zorder=2)
education.plot(ax=ax,color="#984ea3",alpha=0.4,zorder=2)


# ===============================
# BUILDING LAYER (Task 6)
# ===============================

buildings = get_krsko_landuse({"building": True}).to_crs(3857)

# Spatial-join buildings to landuse zones to inherit category
joined = gpd.sjoin(
    buildings,
    landuse_gdf_3857[["geometry", "landuse", "leisure", "amenity"]],
    how="left",
    predicate="within",
)

_building_style = {
    "residential": ("#2c7bb6", ("landuse", {"residential"})),
    "industrial":  ("#d7191c", ("landuse", {"industrial"})),
    "commercial":  ("#fdae61", ("landuse", {"commercial", "retail"})),
    "parks":       ("#1a9641", ("leisure", {"park", "recreation_ground"})),
    "education":   ("#984ea3", ("amenity", {"school", "college", "university", "kindergarten"})),
}

def _building_color(row):
    for _cat, (color, (col, vals)) in _building_style.items():
        val = row.get(col)
        if pd.notna(val) and val in vals:
            return color
    return "#bdbdbd"

joined["color"] = joined.apply(_building_color, axis=1)

joined.plot(ax=ax, color=joined["color"], alpha=0.6, linewidth=0, zorder=3)

legend_patches.append(
    mpatches.Patch(color="#bdbdbd", label="unzoned building")
)


ctx.add_basemap(ax,source=ctx.providers.OpenStreetMap.Mapnik)

# ===============================
# WORK MARKER
# ===============================

work_point = gpd.GeoSeries(
    [Point(work_location)],
    crs="EPSG:4326"
).to_crs(epsg=3857)

ax.scatter(
    work_point.x,
    work_point.y,
    color="yellow",
    alpha=0.25,
    s=80,
    edgecolor="black",
    zorder=6,
    label="Work"
)

work_energy_text = ax.text(
    work_point.x.values[0] + 120,
    work_point.y.values[0] + 120,
    "",
    fontsize=11,
    color="black",
    weight="bold",
    zorder=7
)

ax.set_axis_off()

ax.legend(handles=legend_patches,loc="lower left")


# ===============================
# VEHICLE SCATTER
# ===============================

scatter = ax.scatter(
    [],
    [],
    s=40,
    edgecolor="black",
    linewidth=0.5,
    zorder=5
)

# ===============================
# ENERGIJA
# ===============================

energy_colorbar = plt.colorbar(
    scatter,
    ax=ax,
    fraction=0.03,
    pad=0.02
)

energy_colorbar.set_label("Energy consumption (kWh)")
energy_colorbar.ax.set_visible(False)


# ===============================
# VEHICLE ID LABELS
# ===============================

labels = []

for vid in range(1, number_of_vehicles + 1):

    txt = ax.text(
        0,
        0,
        str(vid),
        fontsize=8,
        color="black",
        zorder=6
    )

    labels.append(txt)


# ===============================
# HEATMAP
# ===============================

heatmap = ax.imshow(
    np.zeros((300,300)),
    cmap="turbo",
    alpha=0.35,
    origin="lower",
    zorder=1
)

heatmap.set_interpolation("gaussian")


# ===============================
# ENERGY GRAPH
# ===============================

energy_line, = ax_graph_energy.plot([], [], linewidth=2, color="blue")

ax_graph_energy.set_xlim(0, 24)
ax_graph_energy.set_xticks(range(0,25,2))
ax_graph_energy.set_xticklabels([f"{h:02d}" for h in range(0,25,2)])

ax_graph_energy.set_ylim(0, np.max(energy_matrix)*number_of_vehicles)

ax_graph_energy.set_title("Parking energy demand", fontsize=10)
ax_graph_energy.set_xlabel("Time (hours)")
ax_graph_energy.set_ylabel("Energy (kWh)")
ax_graph_energy.grid(True)

# ===============================
# PARKING GRAPH
# ===============================


#parking_line, = ax_graph_parking.plot([], [], linewidth=2, color="green")
arrival_line, = ax_graph_parking.plot([], [], linewidth=2, color="orange", label="Arrival")
departure_line, = ax_graph_parking.plot([], [], linewidth=2, color="blue", label="Departure")
ax_graph_parking.legend()

ax_graph_parking.set_xlim(0, 24)
ax_graph_parking.set_xticks(range(0,25,2))
ax_graph_parking.set_xticklabels([f"{h:02d}" for h in range(0,25,2)])

ax_graph_parking.set_ylim(0, number_of_vehicles)

#ax_graph_parking.set_title("Number of parked vehicles")
ax_graph_parking.set_title("Workplace arrivals / departures")
ax_graph_parking.set_xlabel("Time (hours)")
ax_graph_parking.set_ylabel("Vehicles")

ax_graph_parking.grid(True)

# ===============================
# PREKLOP FUNCTION
# ===============================

def toggle_display(label):

    global show_heatmap, show_energy

    if label == "Heatmap":
        show_heatmap = not show_heatmap

    elif label == "Energy colors":
        show_energy = not show_energy

check.on_clicked(toggle_display)

# ===============================
# UPDATE FUNCTION
# ===============================

def update(frame):

    global parking_energy_history, time_history

    parked_mask = trip_types_matrix[:, frame] != "Driving"
    cars_parked = np.sum(parked_mask)

    # reset graph when new animation cycle starts
    if frame == 0:
        parking_energy_history.clear()
        work_arrival_history.clear()
        work_departure_history.clear()
    
    lon_lat = positions[:,frame,:]

    gdf = gpd.GeoDataFrame(
        geometry=[Point(lon,lat) for lon,lat in lon_lat],
        crs="EPSG:4326"
    ).to_crs(epsg=3857)

    # ===============================
    # MAP LIMITS
    # ===============================

    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    # ===============================
    # VISIBLE VEHICLES
    # ===============================

    visible_mask = (
        (gdf.geometry.x >= xmin) &
        (gdf.geometry.x <= xmax) &
        (gdf.geometry.y >= ymin) &
        (gdf.geometry.y <= ymax)
    )

    visible_points = gdf[visible_mask]

    scatter.set_offsets(
        np.c_[visible_points.geometry.x, visible_points.geometry.y]
    )

    # ===============================
    # COLORS
    # ===============================

    colors = np.array([
        trip_type_colors.get(trip_types_matrix[i,frame],"gray")
        for i in range(number_of_vehicles)
    ])

    if show_energy:

        scatter.set_array(energy_matrix[:,frame][visible_mask])
        scatter.set_cmap("plasma")
        energy_colorbar.ax.set_visible(True)

    else:

        colors_visible = colors[visible_mask]
        scatter.set_color(colors_visible)
        energy_colorbar.ax.set_visible(False)

    # ===============================
    # LABELS
    # ===============================

    for i, label in enumerate(labels):

        x = gdf.geometry.x.iloc[i]
        y = gdf.geometry.y.iloc[i]

        if xmin <= x <= xmax and ymin <= y <= ymax:
            label.set_position((x, y))
            label.set_visible(True)
        else:
            label.set_visible(False)

    # ===============================
    # HEATMAP
    # ===============================

    x_vals = gdf.geometry.x.values
    y_vals = gdf.geometry.y.values

    density,_,_ = np.histogram2d(
        x_vals,
        y_vals,
        bins=250,
        range=[[xmin,xmax],[ymin,ymax]]
    )

    max_density = density.max()

    sigma = 3 + max_density * 1.5
    sigma = min(sigma, 15)

    density = gaussian_filter(density, sigma=sigma)

    if show_heatmap:
        heatmap.set_data(density.T)
    else:
        heatmap.set_data(np.zeros_like(density.T))

    heatmap.set_extent([xmin,xmax,ymin,ymax])

    if density.max() > 0:
        heatmap.set_clim(vmin=0,vmax=density.max())

    # ===============================
    # TIME
    # ===============================

    hours = (frame*15)//60
    minutes = (frame*15)%60

    # ===============================
    # WORK ENERGY
    # ===============================

    cars_at_work = np.sum(trip_types_matrix[:, frame] == "Work")

    work_mask = trip_types_matrix[:, frame] == "Work"

    total_work_energy = np.sum(energy_matrix[work_mask, frame])

    parking_energy_history.append(total_work_energy)

    #time_history.append(frame * 0.25)

    arrivals = 0
    departures = 0

    if frame > 0:

        prev_state = trip_types_matrix[:, frame-1]
        curr_state = trip_types_matrix[:, frame]

        arrivals = np.sum(
            (prev_state == "Driving") &
            (curr_state == "Work")
        )

        departures = np.sum(
            (prev_state == "Work") &
            (curr_state == "Driving")
        )

    work_arrival_history.append(arrivals)
    work_departure_history.append(departures)

    #x_vals = np.arange(len(parking_energy_history)) * 0.25
    n = min(len(work_arrival_history), len(work_departure_history))
    x_vals = np.arange(n) * 0.25

    #energy_line.set_data(x_vals, parking_energy_history[:n])
    energy_x = np.arange(len(parking_energy_history)) * 0.25
    energy_line.set_data(energy_x, parking_energy_history)

    ax_graph_energy.set_xlim(0, 24)

    if len(parking_energy_history) > 0 and max(parking_energy_history) > 0:
        ax_graph_energy.set_ylim(0, max(parking_energy_history)*1.2)
    else:
        ax_graph_energy.set_ylim(0, 1)

    arrival_line.set_data(x_vals, work_arrival_history[:n])
    departure_line.set_data(x_vals, work_departure_history[:n])

    ax_graph_parking.set_xlim(0, 24)

    max_flow = max(
        max(work_arrival_history, default=1),
        max(work_departure_history, default=1)
    )

    ax_graph_parking.set_ylim(0, max_flow*1.4)

    # ===============================
    # TITLES
    # ===============================

    ax.set_title(
        #f"Time {hours:02d}:{minutes:02d} | Cars at work: {cars_at_work}",
        f"Time {hours:02d}:{minutes:02d}",
        fontsize=12,
        pad=10
    )

    work_energy_text.set_text(
        f"Cars: {cars_at_work}\nEnergy: {total_work_energy:.1f} kWh"
    )

    # ===============================
    # MARKER SIZE
    # ===============================

    sizes = 30 + energy_matrix[:,frame] * 12
    scatter.set_sizes(sizes[visible_mask])

    return scatter, energy_line, arrival_line, departure_line

# ===============================
# ANIMATION
# ===============================

ani = FuncAnimation(
    fig,
    update,
    frames=intervals,
    interval=900, # večji je počasnejša je animacija
    blit=False
)


plt.show()
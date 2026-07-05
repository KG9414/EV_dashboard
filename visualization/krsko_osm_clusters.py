import osmnx as ox
import geopandas as gpd
import pandas as pd


# ===============================
# LAYER CONFIG
# Vsaka kategorija: (ime, barva, alpha, zorder)
# ===============================

LAYER_CONFIG = {
    # ---- NARAVA ----
    "forest":       ("#1a7a1a", 0.55, 2),   # temno zelena
    "grassland":    ("#a8d878", 0.45, 2),   # svetlo zelena
    "meadow":       ("#c8e6a0", 0.40, 2),
    "orchard":      ("#8fbc45", 0.45, 2),
    "vineyard":     ("#b5d46a", 0.45, 2),
    "farmland":     ("#e8d8a0", 0.40, 2),   # rumenkasta
    "plantation":   ("#5a9e5a", 0.45, 2),
    "grass":        ("#b8e090", 0.40, 2),
    "village_green":("#a0d870", 0.45, 2),
    "plant_nursery":("#70b870", 0.45, 2),
    "greenhouse_horticulture": ("#d0edb0", 0.40, 2),
    "flowerbed":    ("#f0c0d0", 0.50, 2),
    "nature_reserve": ("#2e8b57", 0.35, 2),
    # ---- VODA ----
    "water":        ("#4a9ed6", 0.65, 3),
    "wetland":      ("#7bb8d4", 0.50, 3),
    # ---- POZIDANO ----
    "residential":  ("#aec6cf", 0.50, 3),   # svetlo modra
    "commercial":   ("#f4a460", 0.55, 3),   # oranžna
    "retail":       ("#ffd700", 0.50, 3),   # zlata
    "industrial":   ("#cd5c5c", 0.55, 3),   # rdeča
    "brownfield":   ("#b8860b", 0.45, 3),
    "quarry":       ("#808080", 0.50, 3),
    "landfill":     ("#696969", 0.45, 3),
    "farmyard":     ("#deb887", 0.45, 3),
    # ---- JAVNE POVRŠINE ----
    "education":    ("#9370db", 0.50, 3),   # vijolična
    "cemetery":     ("#8fbc8f", 0.45, 3),
    "recreation_ground": ("#3cb371", 0.45, 3),
    # ---- PROSTI ČAS ----
    "park":         ("#228b22", 0.45, 3),   # zelena
    "garden":       ("#90ee90", 0.45, 3),
    "pitch":        ("#32cd32", 0.50, 3),   # igrišče
    "stadium":      ("#ff6347", 0.45, 3),
    "sports_centre":("#ff8c00", 0.45, 3),
    "swimming_pool":("#00bfff", 0.55, 3),
    "nature_reserve_leisure": ("#2e8b57", 0.35, 2),
    # ---- AMENITY ----
    "school":       ("#8b008b", 0.50, 4),   # temno vijolična
    "university":   ("#9400d3", 0.50, 4),
    "kindergarten": ("#da70d6", 0.50, 4),
    "hospital":     ("#ff4444", 0.55, 4),
    "parking":      ("#c0c0c0", 0.40, 3),
}

# Legenda za prikaz (samo ključne kategorije)
LEGEND_LABELS = {
    "forest":       "Gozd / Forest",
    "grassland":    "Travnik / Grassland",
    "farmland":     "Kmetijsko / Farmland",
    "water":        "Voda / Water",
    "residential":  "Stanovanjsko / Residential",
    "commercial":   "Poslovno / Commercial",
    "retail":       "Nakupovalno / Retail",
    "industrial":   "Industrijsko / Industrial",
    "education":    "Izobraževanje / Education",
    "park":         "Park",
    "pitch":        "Igrišče / Sports pitch",
    "school":       "Šola / School",
    "cemetery":     "Pokopališče / Cemetery",
    "parking":      "Parkirišče / Parking",
}


def get_krsko_clusters():

    place = "Krško, Slovenia"

    tags = {
        "landuse":  True,
        "leisure":  True,
        "amenity":  True,
        "natural":  True,
        "water":    True,
        "waterway": True,
        "building": True,
    }

    gdf = ox.features_from_place(place, tags)

    gdf_proj = gdf.to_crs(epsg=3857)

    clusters = {}

    # ==============================
    # RESIDENTIAL
    # ==============================
    residential = gdf_proj[gdf_proj["landuse"] == "residential"]
    if not residential.empty:
        largest = residential.loc[residential.geometry.area.idxmax()]
        centroid = largest.geometry.centroid
        cg = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["residential"] = (cg.iloc[0].x, cg.iloc[0].y)

    # ==============================
    # INDUSTRIAL
    # ==============================
    industrial = gdf_proj[gdf_proj["landuse"] == "industrial"]
    if not industrial.empty:
        largest = industrial.loc[industrial.geometry.area.idxmax()]
        centroid = largest.geometry.centroid
        cg = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["industrial"] = (cg.iloc[0].x, cg.iloc[0].y)

    # ==============================
    # URBAN ACTIVITY ZONE
    # ==============================
    urban_activity = gdf_proj[
        (gdf_proj["landuse"].isin(["commercial", "retail"])) |
        (gdf_proj["leisure"].isin(["recreation_ground", "park"])) |
        (gdf_proj["amenity"].isin(["school", "university", "marketplace"]))
    ]
    if not urban_activity.empty:
        merged = urban_activity.geometry.unary_union
        centroid = merged.centroid
        cg = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["urban_activity"] = (cg.iloc[0].x, cg.iloc[0].y)

    # ==============================
    # EDUCATION
    # ==============================
    education = gdf_proj[
        gdf_proj["amenity"].isin(["school", "college", "university", "kindergarten"])
    ]
    if not education.empty:
        merged = education.geometry.unary_union
        centroid = merged.centroid
        cg = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["education"] = (cg.iloc[0].x, cg.iloc[0].y)

    return clusters, gdf


def get_residential_zones(gdf, target_crs=3857, merge_buffer=10.0):
    gdf_proj = gdf.to_crs(epsg=target_crs)
    residential_mask = (
        gdf_proj["landuse"].isin(["residential", "housing"]) |
        gdf_proj["building"].isin([
            "residential", "house", "apartments", "detached",
            "semidetached_house", "terrace"
        ])
    )
    residential = gdf_proj[residential_mask].copy()
    if residential.empty:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    merged = residential.geometry.buffer(merge_buffer).unary_union
    if merge_buffer > 0:
        merged = merged.buffer(-merge_buffer)

    return gpd.GeoDataFrame(geometry=[merged], crs=target_crs)


def plot_landuse_layers(ax, gdf, alpha_scale=1.0):
    """
    Nariše vse zemlejvidne plasti na podani os (ax).
    Kliči po ctx.add_basemap(), da se plasti pokažejo nad karto.

    Parameters
    ----------
    ax          : matplotlib Axes (v CRS 3857)
    gdf         : GeoDataFrame, kot ga vrne get_krsko_clusters()
    alpha_scale : float, globalni faktor za prosojnost (privzeto 1.0)
    """

    gdf_proj = gdf.to_crs(epsg=3857)

    # Pomožna funkcija za risanje ene plasti
    def _plot(mask, color, alpha, zorder, label=None):
        sub = gdf_proj[mask]
        if not sub.empty:
            sub.plot(ax=ax, color=color, alpha=alpha * alpha_scale,
                     zorder=zorder, label=label)



    

    # ── POZIDANO ────────────────────────────────────────────────────
    residential_zones = get_residential_zones(gdf, target_crs=3857, merge_buffer=10.0)
    if not residential_zones.empty:
        residential_zones.plot(ax=ax, color="#aec6cf", alpha=0.50 * alpha_scale,
                               zorder=3, label="Stanovanjsko")
    _plot(gdf_proj["landuse"] == "commercial", "#f4a460", 0.55, 3, "Poslovno")
    _plot(gdf_proj["landuse"] == "retail",     "#ffd700", 0.50, 3, "Nakupovalno")
    _plot(gdf_proj["landuse"] == "industrial", "#cd5c5c", 0.55, 3, "Industrijsko")
    _plot(gdf_proj["landuse"] == "brownfield", "#b8860b", 0.40, 3)
    _plot(gdf_proj["landuse"] == "quarry",     "#808080", 0.50, 3, "Kamnolom")
    _plot(gdf_proj["landuse"] == "landfill",   "#696969", 0.45, 3)
    _plot(gdf_proj["landuse"] == "farmyard",   "#deb887", 0.45, 3)
    _plot(gdf_proj["landuse"] == "education",  "#9370db", 0.45, 3)

    # ── POKOPALIŠČE ─────────────────────────────────────────────────
    _plot(gdf_proj["landuse"] == "cemetery",   "#8fbc8f", 0.50, 3, "Pokopališče")

    # ── PROSTI ČAS ──────────────────────────────────────────────────
    _plot(gdf_proj["leisure"] == "park",       "#228b22", 0.50, 3, "Park")
    _plot(gdf_proj["leisure"] == "garden",     "#90ee90", 0.45, 3)
    _plot(gdf_proj["leisure"].isin(["pitch", "track"]),
                                               "#32cd32", 0.50, 3, "Igrišče")
    _plot(gdf_proj["leisure"] == "stadium",    "#ff6347", 0.45, 3, "Stadion")
    _plot(gdf_proj["leisure"].isin(["sports_centre", "fitness_centre"]),
                                               "#ff8c00", 0.45, 3, "Šport")
    _plot(gdf_proj["leisure"] == "swimming_pool",
                                               "#00bfff", 0.55, 3, "Bazen")
    _plot(gdf_proj["leisure"] == "nature_reserve",
                                               "#2e8b57", 0.35, 2, "Naravni rezervat")
    _plot(gdf_proj["landuse"] == "recreation_ground",
                                               "#3cb371", 0.45, 3)

    # ── IZOBRAŽEVANJE ────────────────────────────────────────────────
    _plot(gdf_proj["amenity"].isin(["school", "college", "university"]),
                                               "#8b008b", 0.55, 4, "Šola/Univerza")
    _plot(gdf_proj["amenity"] == "kindergarten",
                                               "#da70d6", 0.50, 4, "Vrtec")

    # ── ZDRAVSTVO ────────────────────────────────────────────────────
    _plot(gdf_proj["amenity"].isin(["hospital", "clinic"]),
                                               "#ff4444", 0.60, 4, "Zdravstvo")

    # ── PARKIRIŠČA ───────────────────────────────────────────────────
    _plot(gdf_proj["amenity"] == "parking",    "#c0c0c0", 0.40, 3, "Parkirišče")


if __name__ == "__main__":

    clusters, gdf = get_krsko_clusters()

    osm_table = gdf.copy().dropna(how="all")
    osm_table.to_excel("krsko_osm_tags.xlsx", index=False)
    print("Excel file saved: krsko_osm_tags.xlsx")

    # ── TESTNI PRIKAZ ────────────────────────────────────────────────
    import matplotlib.pyplot as plt
    import contextily as ctx # type: ignore

    gdf_proj = gdf.to_crs(epsg=3857)
    bounds = gdf_proj.geometry.total_bounds  # (minx, miny, maxx, maxy)

    fig, ax = plt.subplots(figsize=(12, 10))

    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_aspect("equal")

    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5)

    plot_landuse_layers(ax, gdf)

    ax.legend(loc="lower left", fontsize=8, framealpha=0.8)
    ax.set_axis_off()
    ax.set_title("Krško — OSM land-use layers", fontsize=13)

    plt.tight_layout()
    plt.savefig("krsko_landuse_preview.png", dpi=150)
    plt.show()
    print("Preview saved: krsko_landuse_preview.png")
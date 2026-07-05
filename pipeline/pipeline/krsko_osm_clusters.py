import osmnx as ox
import geopandas as gpd
import pandas as pd

def get_krsko_clusters():

    place = "Krško, Slovenia"

    # Povlečemo več tipov oznak
    tags = {
        "landuse": True,
        "leisure": True,
        "amenity": True
    }

    gdf = ox.features_from_place(place, tags)

    # Delamo v metričnem CRS za pravilne centroid-e
    gdf_proj = gdf.to_crs(epsg=3857)

    clusters = {}

    # ==============================
    # RESIDENTIAL
    # ==============================
    residential = gdf_proj[gdf_proj["landuse"] == "residential"]

    if not residential.empty:
        largest = residential.loc[residential.geometry.area.idxmax()]
        centroid = largest.geometry.centroid
        centroid_geo = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["residential"] = (centroid_geo.iloc[0].x, centroid_geo.iloc[0].y)

    # ==============================
    # INDUSTRIAL
    # ==============================
    industrial = gdf_proj[gdf_proj["landuse"] == "industrial"]

    if not industrial.empty:
        largest = industrial.loc[industrial.geometry.area.idxmax()]
        centroid = largest.geometry.centroid
        centroid_geo = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["industrial"] = (centroid_geo.iloc[0].x, centroid_geo.iloc[0].y)

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
        centroid_geo = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["urban_activity"] = (centroid_geo.iloc[0].x, centroid_geo.iloc[0].y)

    # ==============================
    # EDUCATION
    # ==============================
    education = gdf_proj[
        gdf_proj["amenity"].isin(["school", "college", "university", "kindergarten"])
    ]

    if not education.empty:
        merged = education.geometry.unary_union
        centroid = merged.centroid
        centroid_geo = gpd.GeoSeries([centroid], crs=3857).to_crs(epsg=4326)
        clusters["education"] = (centroid_geo.iloc[0].x, centroid_geo.iloc[0].y)

    return clusters, gdf


# ============================================================================
# Matplotlib helper used by the legacy desktop scripts (Krsko-4vozila.py etc.)
# ============================================================================

def plot_landuse_layers(ax, landuse_gdf):
    """Overlay categorised OSM landuse polygons on a matplotlib axis.

    Categories + colours match the deployed Streamlit app so screenshots
    line up. Reprojects to EPSG:3857 (Web Mercator) to match contextily
    basemaps.
    """
    g = landuse_gdf.to_crs(epsg=3857)

    style = {
        "residential": ("#2c7bb6", 0.25, ("landuse", {"residential"})),
        "industrial":  ("#d7191c", 0.25, ("landuse", {"industrial"})),
        "commercial":  ("#fdae61", 0.30, ("landuse", {"commercial", "retail"})),
        "parks":       ("#1a9641", 0.30, ("leisure", {"park", "recreation_ground"})),
        "education":   ("#984ea3", 0.35, ("amenity", {"school", "college",
                                                       "university", "kindergarten"})),
    }

    for cat, (color, alpha, (col, allowed)) in style.items():
        if col not in g.columns:
            continue
        sub = g[g[col].isin(allowed)]
        if sub.empty:
            continue
        sub.plot(ax=ax, color=color, alpha=alpha, zorder=2, edgecolor="none",
                 label=cat)


if __name__ == "__main__":

    clusters, gdf = get_krsko_clusters()

    # izberemo stolpce, ki so pomembni ali vse
    # osm_table = gdf[["landuse","amenity","leisure","building","shop"]]
    osm_table = gdf.copy()

    # odstranimo prazne vrstice
    osm_table = osm_table.dropna(how="all")

    # shranimo v Excel
    osm_table.to_excel("krsko_osm_tags.xlsx", index=False)

    print("Excel file saved: krsko_osm_tags.xlsx")
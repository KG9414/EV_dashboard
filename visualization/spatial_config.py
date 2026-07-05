import functools
import json

import osmnx as ox
import geopandas as gpd

KRSKO_OVERPASS_AREA_ID = 3601685729
KRSKO_OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

_DEFAULT_LANDUSE_TAGS = {
    "landuse": True,
    "leisure": True,
    "amenity": True,
    "building": True,
    "shop": True,
}

# Maps each trip state to (osmnx_column, set_of_allowed_values).
# None as the value set means "any non-null value in that column".
# Rules mirror the Overpass queries in Functions_step_2.init().
STATE_TO_LANDUSE_RULE = {
    "Home": (
        "building",
        {"house", "residential", "apartments", "detached",
         "semidetached_house", "terrace", "yes"},
    ),
    "Work": (
        "building",
        {"office", "commercial", "industrial", "retail", "warehouse"},
    ),
    "Business": (
        "building",
        {"office", "commercial", "industrial", "retail"},
    ),
    "Education": (
        "amenity",
        {"school", "college", "university", "music_school", "kindergarten"},
    ),
    "Shopping": (
        "shop",
        None,  # any shop tag qualifies
    ),
    "Transport": (
        "amenity",
        {"bus_station", "parking", "taxi", "ferry_terminal"},
    ),
    "Leisure": (
        "leisure",
        None,  # any leisure tag qualifies
    ),
    "Personal": (
        "amenity",
        {"pharmacy", "doctors", "hospital", "post_office", "bank", "atm", "clinic"},
    ),
    "unknown": (
        "building",
        {"yes"},
    ),
}


@functools.lru_cache(maxsize=None)
def get_krsko_boundary():
    """Return the Krško municipality boundary as a Shapely Polygon in EPSG:4326."""
    gdf = ox.geocode_to_gdf("Krško, Slovenia")
    return gdf.geometry.iloc[0]


@functools.lru_cache(maxsize=None)
def _get_krsko_landuse_cached(tags_json: str) -> gpd.GeoDataFrame:
    tags = json.loads(tags_json)
    return ox.features_from_place("Krško, Slovenia", tags=tags)


def get_krsko_landuse(tags: dict | None = None) -> gpd.GeoDataFrame:
    """Return OSM features for Krško, cached per unique tag combination."""
    if tags is None:
        tags = _DEFAULT_LANDUSE_TAGS
    return _get_krsko_landuse_cached(json.dumps(tags, sort_keys=True))

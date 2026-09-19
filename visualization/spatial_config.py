import functools
import hashlib
import json
from pathlib import Path

import osmnx as ox
import geopandas as gpd

PLACE = "Krško, Slovenia"

# Poizvedbe, ki jih uporablja dashboard (krsko_osm_clusters in data_loader).
CLUSTER_TAGS = {
    "landuse": True, "leisure": True, "amenity": True, "natural": True,
    "water": True, "waterway": True, "building": True,
}
BUILDING_TAGS = {"building": True}

# Posnetek OSM podatkov (scripts/build_osm_snapshot.py). Če datoteka obstaja,
# se podatki berejo iz nje in ne iz Overpassa — to je bistveno na Streamlit
# Cloud, kjer se predpomnilnik osmnx ne ujema in bi se ob vsakem zagonu
# prenašalo ~90 MB podatkov.
SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "osm_snapshot"


def snapshot_path(tags: dict) -> Path:
    key = hashlib.sha1(json.dumps(tags, sort_keys=True).encode()).hexdigest()[:12]
    return SNAPSHOT_DIR / f"features_{key}.parquet"


def features_from_place(place: str, tags: dict) -> gpd.GeoDataFrame:
    """ox.features_from_place, ki najprej poskusi prebrati posnetek."""
    p = snapshot_path(tags)
    if place == PLACE and p.exists():
        try:
            return gpd.read_parquet(p)
        except Exception as e:  # npr. manjka pyarrow
            print(f"OSM posnetek {p.name} ni berljiv ({e}); uporabljam osmnx.")
    return ox.features_from_place(place, tags=tags)

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
    return features_from_place(PLACE, tags)


def get_krsko_landuse(tags: dict | None = None) -> gpd.GeoDataFrame:
    """Return OSM features for Krško, cached per unique tag combination."""
    if tags is None:
        tags = _DEFAULT_LANDUSE_TAGS
    return _get_krsko_landuse_cached(json.dumps(tags, sort_keys=True))

"""Zgradi posnetek OSM podatkov za dashboard (visualization/data/osm_snapshot/).

Dashboard sicer ob vsakem hladnem zagonu kliče Nominatim in Overpass prek
osmnx. Na Streamlit Cloud se lokalni predpomnilnik osmnx ne ujema (ključ je
izračunan iz besedila poizvedbe, ki se med platformami razlikuje), zato se ob
zagonu prenaša ~90 MB podatkov. Posnetek je shranjen kot GeoParquet in ga
spatial_config.features_from_place() prebere namesto klica osmnx.

Zagon (iz mape visualization, kjer je predpomnilnik osmnx):
    python scripts/build_osm_snapshot.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import osmnx as ox  # noqa: E402

from spatial_config import (  # noqa: E402
    PLACE, CLUSTER_TAGS, BUILDING_TAGS, snapshot_path,
)


def build(tags: dict) -> None:
    gdf = ox.features_from_place(PLACE, tags=tags)
    out = snapshot_path(tags)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Seznami in slovarji (če jih osmnx vrne) se shranijo kot besedilo;
    # manjkajoče vrednosti ostanejo manjkajoče.
    for col in gdf.columns:
        if col != "geometry" and gdf[col].dtype == object:
            gdf[col] = gdf[col].map(
                lambda v: str(v) if isinstance(v, (list, tuple, dict, set)) else v
            )
    gdf.to_parquet(out, compression="zstd")
    print(f"{out.name}: {len(gdf)} objektov, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    for tags in (CLUSTER_TAGS, BUILDING_TAGS):
        build(tags)

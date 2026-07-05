"""
Build the OSM snapshot the Streamlit app reads.

Run me **once** locally (or whenever you change cluster definitions in
`pipeline/krsko_osm_clusters.py`). The Streamlit app reads the generated
files; it never calls Overpass at runtime.

    python scripts/build_osm_cache.py

Outputs (all under `data/osm/`):
    krsko_clusters.json       # cluster centroid coords
    krsko_residential.geojson # per-category landuse polygons
    krsko_industrial.geojson
    krsko_commercial.geojson
    krsko_parks.geojson
    krsko_education.geojson
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

OSM_DIR = PROJECT_ROOT / "data" / "osm"
OSM_DIR.mkdir(parents=True, exist_ok=True)


# Mapping from category -> (column, allowed values).
LANDUSE_RULES = {
    "residential": ("landuse",  {"residential"}),
    "industrial":  ("landuse",  {"industrial"}),
    "commercial":  ("landuse",  {"commercial", "retail"}),
    "parks":       ("leisure",  {"park", "recreation_ground"}),
    "education":   ("amenity",  {"school", "college", "university", "kindergarten"}),
}


def main() -> None:
    print("Fetching OSM data for Krško via Overpass (this can take ~30 s)...")
    from krsko_osm_clusters import get_krsko_clusters  # type: ignore

    clusters, landuse_gdf = get_krsko_clusters()

    # 1. Cluster centroids.
    clusters_path = OSM_DIR / "krsko_clusters.json"
    with open(clusters_path, "w") as f:
        json.dump({k: list(v) for k, v in clusters.items()}, f, indent=2)
    print(f"  wrote {clusters_path.relative_to(PROJECT_ROOT)} ({len(clusters)} clusters)")

    # 2. Per-category landuse polygons → GeoJSON (EPSG:4326 for Plotly mapbox).
    gdf = landuse_gdf.to_crs(epsg=4326)
    for cat, (col, allowed) in LANDUSE_RULES.items():
        if col not in gdf.columns:
            print(f"  (skipped {cat}: column '{col}' not in OSM data)")
            continue
        sub = gdf[gdf[col].isin(allowed)].copy()
        sub = sub[sub.geometry.notna()]
        keep = [c for c in (col, "name") if c in sub.columns] + ["geometry"]
        sub = sub[keep]
        out = OSM_DIR / f"krsko_{cat}.geojson"
        if sub.empty:
            out.write_text('{"type":"FeatureCollection","features":[]}')
            print(f"  wrote {out.relative_to(PROJECT_ROOT)} (0 features)")
            continue
        sub.to_file(out, driver="GeoJSON")
        print(f"  wrote {out.relative_to(PROJECT_ROOT)} ({len(sub)} features)")

    print("Done.")


if __name__ == "__main__":
    main()

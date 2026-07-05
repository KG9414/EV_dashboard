"""
Dump every OSM feature in Krško to an xlsx so you can refine the cluster
definitions in `pipeline/krsko_osm_clusters.py`.

    python scripts/explore_osm_tags.py

Outputs:
    data/osm/krsko_osm_tags.xlsx
    data/osm/krsko_tag_summary.xlsx   # value-counts per tag column

Tip: after editing cluster definitions, re-run `build_osm_cache.py` to
refresh what the Streamlit app shows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

OSM_DIR = PROJECT_ROOT / "data" / "osm"
OSM_DIR.mkdir(parents=True, exist_ok=True)

TAGS_PATH = OSM_DIR / "krsko_osm_tags.xlsx"
SUMMARY_PATH = OSM_DIR / "krsko_tag_summary.xlsx"


def main() -> None:
    import osmnx as ox

    place = "Krško, Slovenia"
    tags = {"landuse": True, "leisure": True, "amenity": True,
            "shop": True, "building": True, "tourism": True}

    print(f"Pulling OSM features for {place}...")
    gdf = ox.features_from_place(place, tags)

    # Coerce list-like values to strings so openpyxl is happy.
    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))
    for col in df.columns:
        df[col] = df[col].astype(str)
    df = df.dropna(how="all")
    df.to_excel(TAGS_PATH, index=False)
    print(f"  wrote {TAGS_PATH.relative_to(PROJECT_ROOT)} ({len(df)} rows)")

    # Per-column value counts -> summary workbook (one sheet per tag column).
    with pd.ExcelWriter(SUMMARY_PATH) as writer:
        for col in ["landuse", "leisure", "amenity", "shop", "building", "tourism"]:
            if col in df.columns:
                vc = df[col].value_counts().reset_index()
                vc.columns = [col, "count"]
                vc.to_excel(writer, sheet_name=col[:31], index=False)
    print(f"  wrote {SUMMARY_PATH.relative_to(PROJECT_ROOT)}")
    print("Done.")


if __name__ == "__main__":
    main()

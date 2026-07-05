"""
Scenario + OSM loaders. All loaders are cached so the same file isn't
re-parsed on every Streamlit widget interaction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = PROJECT_ROOT / "data" / "scenarios"
OSM_DIR = PROJECT_ROOT / "data" / "osm"

OSM_CLUSTERS_PATH = OSM_DIR / "krsko_clusters.json"

# Per-category landuse GeoJSON files produced by scripts/build_osm_cache.py
LANDUSE_CATEGORIES = ("residential", "industrial", "commercial", "parks", "education")


# ----------------------------------------------------------------------------
# Scenario discovery
# ----------------------------------------------------------------------------

SCENARIO_LABELS: dict[str, str] = {
    #"scenario_4_EVs_2_trips":  "4 EVs · 2 trips · 1 day",
    "scenario_5_EVs_4_trips":  "5 EVs · 4 trips · 1 day",
    "scenario_20_EVs_2_trips":  "20 EVs · 2 trips · 1 day",
    "scenario_25_EVs_4_trips": "25 EVs · 4 trips · 1 day",
    "scenario_100_EVs_2_trips": "100 EVs · 2 trips · 1 day",
}


_TRIP_REQUIRED_COL = "End"


def list_scenarios() -> list[tuple[str, Path]]:
    if not SCENARIO_DIR.exists():
        return []
    items: list[tuple[str, Path]] = []
    for p in sorted(SCENARIO_DIR.glob("*.xlsx")):
        try:
            cols = set(pd.read_excel(p, nrows=0).columns.str.strip())
        except Exception:
            continue
        if _TRIP_REQUIRED_COL not in cols:
            continue
        label = SCENARIO_LABELS.get(p.stem, p.stem.replace("_", " "))
        items.append((label, p))
    return items


@st.cache_data(show_spinner=False)
def load_scenario(path_str: str) -> pd.DataFrame:
    df = pd.read_excel(path_str)
    df.columns = df.columns.str.strip()
    return df


# ----------------------------------------------------------------------------
# OSM cache (optional)
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_osm_clusters() -> Optional[dict]:
    if not OSM_CLUSTERS_PATH.exists():
        return None
    with open(OSM_CLUSTERS_PATH) as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_landuse_layers() -> Optional[dict]:
    """{ 'residential': GeoJSON, 'industrial': GeoJSON, ... } or None."""
    layers: dict[str, dict] = {}
    for cat in LANDUSE_CATEGORIES:
        p = OSM_DIR / f"krsko_{cat}.geojson"
        if p.exists():
            with open(p) as f:
                layers[cat] = json.load(f)
    return layers if layers else None


def osm_cache_ready() -> bool:
    return OSM_CLUSTERS_PATH.exists() or any(
        (OSM_DIR / f"krsko_{cat}.geojson").exists() for cat in LANDUSE_CATEGORIES
    )

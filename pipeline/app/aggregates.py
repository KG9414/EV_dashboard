"""Nalaganje agregiranih rezultatov prožnosti (izhod flex_aggregation.py).

Datoteke so majhni povzetki (96 intervalov na scenarij), zato je prikaz
velikih scenarijev hiter tudi pri 16.803 vozilih — surovih datotek aplikacija
ne odpira.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FLEX_DIR = PROJECT_ROOT / "data" / "flex"

SCENARIO_LABELS = {
    "06_13pct": "6,13 % · 1.030 vozil",
    "10pct": "10 % · 1.680 vozil",
    "20pct": "20 % · 3.360 vozil",
    "50pct": "50 % · 8.401 vozil",
    "100pct": "100 % · 16.803 vozil",
}
SCENARIO_ORDER = list(SCENARIO_LABELS)

CATEGORY_LABELS = {
    "stanovanjsko": "Stanovanjsko",
    "industrijsko": "Industrijsko",
    "poslovno": "Poslovno",
    "izobrazevalno": "Izobraževalno",
    "zelene_povrsine": "Zelene površine",
    "delovno_neopredeljeno": "Delo (brez oznake)",
    "drugo_neopredeljeno": "Drugo (brez oznake)",
    "stavba_brez_oznake": "Stavba brez oznake",
    "brez_podatka": "Brez podatka",
}


def flex_data_ready() -> bool:
    return FLEX_DIR.exists() and any(FLEX_DIR.glob("flex_timeline_*.csv"))


def available_scenarios() -> list[str]:
    if not FLEX_DIR.exists():
        return []
    keys = [p.stem.replace("flex_timeline_", "") for p in FLEX_DIR.glob("flex_timeline_*.csv")]
    return [k for k in SCENARIO_ORDER if k in keys]


@st.cache_data(show_spinner=False)
def load_timeline(scenario: str) -> pd.DataFrame:
    return pd.read_csv(FLEX_DIR / f"flex_timeline_{scenario}.csv")


@st.cache_data(show_spinner=False)
def load_by_landuse(scenario: str) -> pd.DataFrame:
    df = pd.read_csv(FLEX_DIR / f"flex_by_landuse_{scenario}.csv")
    df["kategorija_naziv"] = df["kategorija"].map(CATEGORY_LABELS).fillna(df["kategorija"])
    return df


@st.cache_data(show_spinner=False)
def load_by_cell(scenario: str) -> pd.DataFrame:
    return pd.read_csv(FLEX_DIR / f"flex_by_cell_{scenario}.csv")


@st.cache_data(show_spinner=False)
def load_summary() -> pd.DataFrame | None:
    p = FLEX_DIR / "flex_summary.xlsx"
    return pd.read_excel(p) if p.exists() else None

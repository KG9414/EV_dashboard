"""
Build all per-vehicle / per-time-step quantities the dashboard needs.

This is the pure math, extracted from `Krsko-4vozila.py` and
`flexibility_plot.py`. No matplotlib, no streamlit, no IO besides reading
the dataframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd


# 96 time steps = 24 h at 15-min resolution.
DEFAULT_INTERVALS = 96
DT_H = 0.25                     # hours per timestep
MAX_CHARGER_KW = 11.0           # cap on AC charger power


# ----------------------------------------------------------------------------
# Trip-type colour map
# ----------------------------------------------------------------------------

TRIP_TYPE_COLORS: dict[str, str] = {
    "Work":      "#2563EB",
    "Shopping":  "#DC2626",
    "Leisure":   "#16A34A",
    "Education": "#EA580C",
    "Business":  "#7C3AED",
    "Transport": "#0EA5E9",
    "Personal":  "#DB2777",
    "Home":      "#374151",
    "Driving":   "#64748B",
}

WORK_COLOR = "#10B981"


# ----------------------------------------------------------------------------
# Result container
# ----------------------------------------------------------------------------

@dataclass
class Simulation:
    positions: np.ndarray        # (V, T, 2) -> (lon, lat)
    trip_types: np.ndarray       # (V, T) -> str
    eng_min: np.ndarray          # (V, T) -> kW charging (lower bound)
    eng_max: np.ndarray          # (V, T) -> kW charging (upper bound)
    arrivals_hist: np.ndarray    # (T,) work arrivals per frame
    departures_hist: np.ndarray  # (T,) work departures per frame
    cum_pos_flex: np.ndarray     # (T,) cumulative positive SoC flexibility [kWh]
    cum_neg_flex: np.ndarray     # (T,) cumulative negative SoC flexibility [kWh]
    has_flex: bool               # True iff scenario contained SoC-flex columns
    work_location: Optional[Tuple[float, float]]
    n_vehicles: int
    n_intervals: int

    @property
    def time_axis_hours(self) -> np.ndarray:
        return np.arange(self.n_intervals) * DT_H

    @property
    def charging_min_total(self) -> np.ndarray:
        return self.eng_min.sum(axis=0)

    @property
    def charging_max_total(self) -> np.ndarray:
        return self.eng_max.sum(axis=0)

    def vehicles_at_work(self, frame: int) -> int:
        return int(np.sum(self.trip_types[:, frame] == "Work"))


# ----------------------------------------------------------------------------
# Column-name compatibility
# ----------------------------------------------------------------------------

# Either (Pos_flex_kWh, Neg_flex_kWh) or (Poz_prisiljena, Neg_prisiljena).
_POS_COLS = ("Pos_flex_kWh", "Poz_prisiljena", "Poz")
_NEG_COLS = ("Neg_flex_kWh", "Neg_prisiljena", "Neg")


def _find_col(df: pd.DataFrame, candidates: tuple[str, ...]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ----------------------------------------------------------------------------
# Main entry
# ----------------------------------------------------------------------------

_REQUIRED_COLS = {"Vehicle ID", "Trip ID", "Trip type", "Start", "End",
                  "Start_lat", "Start_lon", "End_lat", "End_lon", "Energy_kWh"}


def build_simulation(df: pd.DataFrame, intervals: int = DEFAULT_INTERVALS) -> Simulation:
    df = df.copy()
    df.columns = df.columns.str.strip()

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Scenario data is missing columns: {sorted(missing)}. "
            "Expected trip-based format; received time-series format?"
        )

    pos_col = _find_col(df, _POS_COLS)
    neg_col = _find_col(df, _NEG_COLS)
    has_flex = pos_col is not None and neg_col is not None

    n_vehicles = int(df["Vehicle ID"].nunique())
    intervals = max(intervals, int(df["End"].max()) + 1)

    work_rows = df[df["Trip type"] == "Work"]
    work_location: Optional[Tuple[float, float]] = None
    if not work_rows.empty:
        wt = work_rows.iloc[0]
        work_location = (float(wt["End_lon"]), float(wt["End_lat"]))

    home_locations = (
        df[df["Trip ID"] == 1]
        .groupby("Vehicle ID")[["Start_lon", "Start_lat"]]
        .first()
    )

    pos = np.zeros((n_vehicles, intervals, 2))
    typ = np.full((n_vehicles, intervals), "Home", dtype=object)
    eng_min = np.zeros((n_vehicles, intervals))
    eng_max = np.zeros((n_vehicles, intervals))

    rng = np.random.default_rng(seed=42)

    # Vehicle IDs are usually 1..N but may have gaps; iterate over actual ids.
    vehicle_ids = sorted(df["Vehicle ID"].unique())

    for vi, vid in enumerate(vehicle_ids):
        # sort values iz Trip ID na Start, da gre kronološko, če se podre nazaj na Trip ID
        vt = df[df["Vehicle ID"] == vid].sort_values("Start").reset_index(drop=True)
        if vid not in home_locations.index:
            continue
        hc = (
            float(home_locations.loc[vid, "Start_lon"]),
            float(home_locations.loc[vid, "Start_lat"]),
        )
        cc, ct, ctype = hc, 0, "Home"

        # ---- positions + activity types ----
        for _, trip in vt.iterrows():
            s, e = int(trip["Start"]), int(trip["End"])
            dc = (float(trip["End_lon"]), float(trip["End_lat"]))
            ttype = trip["Trip type"]
            duration = max(e - s, 1)

            pos[vi, ct:s] = cc
            typ[vi, ct:s] = ctype

            for t in range(s, e):
                a = (t - s) / duration
                pos[vi, t] = (
                    cc[0] * (1 - a) + dc[0] * a + rng.normal(0, 5e-5),
                    cc[1] * (1 - a) + dc[1] * a + rng.normal(0, 5e-5),
                )
                typ[vi, t] = "Driving"

            if e < intervals:
                pos[vi, e] = dc

            later = vt[vt["Trip ID"] > trip["Trip ID"]]
            if not later.empty:
                ns = int(later.iloc[0]["Start"])
                pos[vi, e:ns] = dc
                typ[vi, e:ns] = ttype
                ct = ns
            else:
                ct = e

            cc, ctype = dc, ttype

        pos[vi, ct:] = hc
        typ[vi, ct:] = "Home"

        # ---- charging min/max during Work parking windows ----
        for _, trip in vt.iterrows():
            if trip["Trip type"] != "Work":
                continue
            park_s = int(trip["End"])
            after = vt[vt["Trip ID"] > trip["Trip ID"]]
            if after.empty:
                continue
            park_e = int(after.iloc[0]["Start"])
            hours = max(park_e - park_s, 1) * DT_H
            p_min = min(float(trip["Energy_kWh"]) / hours, MAX_CHARGER_KW)
            p_max = min(
                (float(trip["Energy_kWh"]) + float(after["Energy_kWh"].sum())) / hours,
                MAX_CHARGER_KW,
            )
            typ[vi, park_s:park_e] = "Work"
            eng_min[vi, park_s:park_e] = p_min
            eng_max[vi, park_s:park_e] = p_max

    # ---- arrivals / departures histograms ----
    arrivals_hist = np.zeros(intervals)
    departures_hist = np.zeros(intervals)
    for v in range(n_vehicles):
        for t in range(1, intervals):
            if typ[v, t - 1] == "Driving" and typ[v, t] == "Work":
                arrivals_hist[t] += 1
            if typ[v, t - 1] == "Work" and typ[v, t] == "Driving":
                departures_hist[t] += 1

    # ---- cumulative SoC flexibility timeline (if columns present) ----
    cum_pos = np.zeros(intervals)
    cum_neg = np.zeros(intervals)
    if has_flex:
        cum_pos, cum_neg = _flex_timeline(df, typ, vehicle_ids, intervals, pos_col, neg_col)

    return Simulation(
        positions=pos,
        trip_types=typ,
        eng_min=eng_min,
        eng_max=eng_max,
        arrivals_hist=arrivals_hist,
        departures_hist=departures_hist,
        cum_pos_flex=cum_pos,
        cum_neg_flex=cum_neg,
        has_flex=has_flex,
        work_location=work_location,
        n_vehicles=n_vehicles,
        n_intervals=intervals,
    )


def _flex_timeline(
    df: pd.DataFrame,
    typ: np.ndarray,
    vehicle_ids: list,
    intervals: int,
    pos_col: str,
    neg_col: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Cumulative ±flexibility kWh over time. Reproduces flexibility_plot.py."""
    pos_delta = np.zeros(intervals + 1)
    neg_delta = np.zeros(intervals + 1)

    for vi, vid in enumerate(vehicle_ids):
        in_work = False
        start_t: Optional[int] = None

        for t in range(intervals):
            if not in_work and typ[vi, t] == "Work":
                in_work, start_t = True, t
            elif in_work and typ[vi, t] != "Work":
                end_t = t
                in_work = False
                trip_row = _trip_ending_at_or_before(df, vid, start_t)
                if trip_row is None:
                    continue
                p_val = float(trip_row[pos_col])
                n_val = -float(trip_row[neg_col])
                pos_delta[start_t] += p_val
                pos_delta[end_t] -= p_val
                neg_delta[start_t] += n_val
                neg_delta[end_t] -= n_val

        if in_work and start_t is not None:
            trip_row = _trip_ending_at_or_before(df, vid, start_t)
            if trip_row is not None:
                pos_delta[start_t] += float(trip_row[pos_col])
                neg_delta[start_t] += -float(trip_row[neg_col])

    return np.cumsum(pos_delta)[:intervals], np.cumsum(neg_delta)[:intervals]


def _trip_ending_at_or_before(df: pd.DataFrame, vid, start_t: int):
    mask = (df["Vehicle ID"] == vid) & (df["End"] <= start_t)
    sub = df[mask]
    if sub.empty:
        return None
    return sub.iloc[-1]

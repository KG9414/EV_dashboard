"""
Functions_step_4.py
-------------------
Helpers for Step 4: per-vehicle State-of-Charge (SoC) simulation and
positive / negative flexibility computation, at 15-min resolution.

Separated from Step_4_prod.py so the math can be reused and tested on its own.

Conventions used throughout
---------------------------
- SoC is expressed in PERCENT (0..100).
- One time step = 15 minutes; one day = INTERVALS_PER_DAY = 96 steps.
- Battery capacity is kept as a per-vehicle (N,) array so the current uniform
  72 kWh value can later be replaced with per-vehicle values without touching
  call sites.
- Flexibility follows the user's formulas literally, with the Pos-flex sign
  flipped so a plot naturally places Pos below zero and Neg above zero.
  No clamping is applied to flex values.
"""

import numpy as np
import pandas as pd


# ----------------------------- Constants ----------------------------- #

DEFAULT_BATTERY_CAPACITY_KWH = 72.0
INTERVALS_PER_DAY = 96              # 15-min steps
SOC_LOWER_THRESHOLD = 20.0          # %  (floor for pos-flex formula)
SOC_UPPER_THRESHOLD = 80.0          # %  (ceiling for neg-flex formula)


# --------------------------- Battery model --------------------------- #

def build_battery_capacity_array(number_of_vehicles,
                                 capacity_kwh=DEFAULT_BATTERY_CAPACITY_KWH):
    """
    Build the per-vehicle battery-capacity array (kWh).

    Currently returns a uniform fill of `capacity_kwh`. To switch to
    per-vehicle capacities later, either:
      - pass in an array/list instead of a scalar, OR
      - load from a DataFrame column (e.g. df.groupby('Vehicle ID')
        ['Battery_kWh'].first().to_numpy()) and hand it to this function.

    Parameters
    ----------
    number_of_vehicles : int
    capacity_kwh       : float | array-like of length N

    Returns
    -------
    np.ndarray of shape (N,), dtype float
    """
    arr = np.asarray(capacity_kwh, dtype=float)
    if arr.ndim == 0:
        return np.full(int(number_of_vehicles), float(arr), dtype=float)
    if arr.shape != (int(number_of_vehicles),):
        raise ValueError(
            f"capacity_kwh array shape {arr.shape} does not match "
            f"number_of_vehicles={number_of_vehicles}"
        )
    return arr.astype(float, copy=False)


# --------------------------- Initial SoC ----------------------------- #

def extract_initial_soc(df, number_of_vehicles,
                        fallback_low=75.0, fallback_high=90.0, seed=None):
    """
    Read `Initial_SoC` (one value per vehicle) from the trip-parameters
    DataFrame. The column is expected to repeat the same value across all
    trip rows of a given vehicle; we take the first non-null value.

    If the column is missing entirely, fall back to a uniform draw in
    [fallback_low, fallback_high] (kept wide enough that most real fleets fit).

    Returns
    -------
    np.ndarray of shape (N,) — SoC in percent at t=0.
    """
    initial = np.zeros(int(number_of_vehicles), dtype=float)
    rng = np.random.default_rng(seed)
    has_column = 'Initial_SoC' in df.columns

    for v in range(1, number_of_vehicles + 1):
        v_rows = df[df['Vehicle ID'] == v]
        if has_column and v_rows['Initial_SoC'].notna().any():
            initial[v - 1] = float(v_rows['Initial_SoC'].dropna().iloc[0])
        else:
            initial[v - 1] = rng.uniform(fallback_low, fallback_high)
    return initial


# ------------------------- Energy consumption ------------------------ #

def build_energy_per_interval(df, number_of_vehicles, number_of_trips,
                              number_of_days):
    """
    Build the (N, T) matrix of energy drawn from the battery in each
    15-min interval, where T = 96 * number_of_days.

    For each trip row we take `Energy_kWh` (already computed in Step 2 as
    distance * efficiency) and spread it linearly across the intervals
    [Start, End). This keeps the per-trip total exactly equal to Step 2's
    value — no second efficiency sample is introduced.

    Start/End in the Excel are per-day (0..95); we offset by 96*day so
    day-to-day trips land at the right global index.
    """
    total_intervals = INTERVALS_PER_DAY * number_of_days
    energy = np.zeros((number_of_vehicles, total_intervals), dtype=float)

    for v in range(number_of_vehicles):
        v_rows = df[df['Vehicle ID'] == v + 1].reset_index(drop=True)
        for day in range(number_of_days):
            for trip in range(number_of_trips):
                row_idx = day * number_of_trips + trip
                if row_idx >= len(v_rows):
                    continue
                start = int(v_rows['Start'].iloc[row_idx]) + INTERVALS_PER_DAY * day
                end   = int(v_rows['End'].iloc[row_idx])   + INTERVALS_PER_DAY * day
                trip_energy = float(v_rows['Energy_kWh'].iloc[row_idx])
                n_intervals = max(end - start, 1)
                # Linearly distributed energy across the driving window
                energy[v, start:end] = trip_energy / n_intervals
    return energy


# ----------------------------- SoC sim ------------------------------- #

def simulate_soc(energy_per_interval, battery_capacity_kwh, initial_soc_pct,
                 warn_on_depletion=True):
    """
    Roll SoC forward in time, step by step. No charging is modelled — the
    only dynamic is consumption, so SoC is monotonically non-increasing.

    Multi-day is handled implicitly: T spans 96*number_of_days and SoC at
    t=96 carries directly into day 2 (the Initial_SoC is only applied at t=0).

    SoC is floored at 0 (a physical limit — the vehicle would have stopped).
    If that floor is ever hit we print a one-time warning per vehicle so it's
    obvious the inputs (Initial_SoC or trip energies) are inconsistent.

    Returns
    -------
    np.ndarray of shape (N, T), SoC in percent.
    """
    N, T = energy_per_interval.shape
    soc = np.zeros((N, T), dtype=float)

    for v in range(N):
        current = float(initial_soc_pct[v])
        cap = float(battery_capacity_kwh[v])
        depleted = False
        for t in range(T):
            drop_pct = (energy_per_interval[v, t] / cap) * 100.0
            current -= drop_pct
            if current < 0.0:
                if warn_on_depletion and not depleted:
                    print(f"[Step_4] Warning: vehicle {v + 1} would deplete the "
                          f"battery at interval {t} (SoC -> {current:.2f}%). "
                          f"Clamped at 0% and continuing.")
                    depleted = True
                current = 0.0
            soc[v, t] = current
    return soc


# --------------------------- Flexibility ----------------------------- #

def compute_flexibility(soc_matrix, battery_capacity_kwh,
                        soc_low=SOC_LOWER_THRESHOLD,
                        soc_high=SOC_UPPER_THRESHOLD):
    """
    Compute positive and negative flexibility at every (vehicle, time) cell.

    Formulas (per user specification):
        Pos_flex = - ((SoC - soc_low ) / 100) * capacity_kWh
        Neg_flex =   ((soc_high - SoC) / 100) * capacity_kWh

    The Pos_flex sign is flipped so plots place Pos below zero and Neg
    above zero out of the box (matches the demo's visual style).

    No clamping is applied — if SoC < 20, Pos_flex flips positive, and if
    SoC > 80, Neg_flex flips negative. These "inverted" values are kept
    intentionally (they carry information about over/undershoot).

    Returns
    -------
    (pos_flex, neg_flex) : tuple of np.ndarray, each shape (N, T), in kWh.
    """
    #cap = battery_capacity_kwh[:, None]                       # (N, 1) broadcast
    #pos = -((soc_matrix - soc_low)  / 100.0) * cap            # typically < 0
    #neg =  ((soc_high - soc_matrix) / 100.0) * cap            # typically > 0

    cap = battery_capacity_kwh[:, None]
    pos = np.maximum(((soc_matrix - soc_low) / 100.0) * cap, 0)
    neg = np.maximum(((soc_high - soc_matrix) / 100.0) * cap, 0)

    return pos, neg


# ---------------------- Per-trip summary rows ------------------------ #

def summarize_per_trip(df, soc_matrix, pos_flex, neg_flex, initial_soc_pct,
                       number_of_trips, number_of_days):
    """
    Collapse the (N, T) time-series into per-trip summary values aligned
    1-to-1 with the rows of `df`. For each trip row we record:

        SoC_at_Start   — SoC (%) *just before* the trip begins (pre-departure)
        SoC_at_End     — SoC (%) *just after* the trip ends (post-arrival)
        Pos_flex_kWh   — pos flex at the moment the vehicle parks (post-arrival)
        Neg_flex_kWh   — neg flex at that same moment

    Implementation detail: we build a padded SoC array of shape (N, T+1)
    with `initial_soc_pct` prepended at column 0, so that column `t`
    represents the battery state *before* interval t's consumption is
    applied. That lets us read SoC at any phase boundary by a single index
    lookup, without off-by-one gymnastics:

        soc_pad[:, Start]  = SoC just before the trip
        soc_pad[:, End]    = SoC just after the trip
    """
    N, T = soc_matrix.shape
    soc_pad = np.concatenate([np.asarray(initial_soc_pct)[:, None],
                              soc_matrix], axis=1)  # shape (N, T+1)

    work = df.copy()
    # Position of the row within its vehicle's block of rows
    work['_row_in_veh'] = work.groupby('Vehicle ID').cumcount()
    # Day index = 0..D-1 (rows are day-major per vehicle, same as Step_3)
    work['_day']        = work['_row_in_veh'] // number_of_trips
    work['_start_g']    = work['Start'].astype(int) + INTERVALS_PER_DAY * work['_day']
    work['_end_g']      = work['End'].astype(int)   + INTERVALS_PER_DAY * work['_day']
    work['_v_idx']      = work['Vehicle ID'].astype(int) - 1

    idx_start_pad = work['_start_g'].clip(lower=0, upper=T).to_numpy()
    idx_end_pad   = work['_end_g'].clip(lower=0, upper=T).to_numpy()
    # For flex we want the parked-state reading, i.e. the last driving
    # interval's post-state, which equals soc_pad[End]. Since flex matrices
    # are NOT padded, we index them at End-1 (clipped into valid range).
    idx_end_flex  = (work['_end_g'] - 1).clip(lower=0, upper=T - 1).to_numpy()
    v_idx         = work['_v_idx'].to_numpy()

    return {
        'SoC_at_Start': soc_pad  [v_idx, idx_start_pad],
        'SoC_at_End':   soc_pad  [v_idx, idx_end_pad],
        'Pos_flex_kWh': pos_flex [v_idx, idx_end_flex],
        'Neg_flex_kWh': neg_flex [v_idx, idx_end_flex],
    }


# ---------------------- Long-format time series --------------------- #

def build_timeseries_long(soc_matrix, pos_flex, neg_flex):
    """
    Flatten (N, T) matrices into a long-format DataFrame suitable for
    downstream plotting/animation:

        TimeStep | Time | Vehicle ID | SoC | Pos_flex_kWh | Neg_flex_kWh

    TimeStep is the global 15-min index (0..T-1); Time is the HH:MM label
    wrapped at 24h so multi-day simulations keep readable clock times.
    """
    N, T = soc_matrix.shape
    time_steps = np.arange(T)
    hh = ((time_steps * 15) // 60) % 24
    mm = (time_steps * 15) % 60
    time_labels = [f"{int(h):02d}:{int(m):02d}" for h, m in zip(hh, mm)]

    frames = []
    for v in range(N):
        frames.append(pd.DataFrame({
            'TimeStep':     time_steps,
            'Time':         time_labels,
            'Vehicle ID':   v + 1,
            'SoC':          soc_matrix[v],
            'Pos_flex_kWh': pos_flex[v],
            'Neg_flex_kWh': neg_flex[v],
        }))
    return pd.concat(frames, ignore_index=True)

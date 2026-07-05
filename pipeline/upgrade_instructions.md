# Model Upgrade Instructions
## Upgrades #5, #11, #14, #17

These instructions are written for Claude in VS Code (Claude Code).  
Each section describes **what to change, where, and exactly how**, referencing the existing files in the project.

---

## Upgrade #5 — Demographic Profile Weighting (Krško SiStat Data)

### What it is
Replace the hardcoded profile distribution `{Commuter: 0.60, Retired: 0.25, Nonccommuter: 0.15}` with weights derived from the actual Krško demographic data from the second PDF.

### Source data (from `S_tevilo_vozil_v_Krsem.pdf`)
```
Population Krško (1 Jan 2025): 26,175
Delovno aktivni (Commuter):    11,748  → 44.9 %
65+ (Retired):                  5,654  → 21.6 %
Noncommuter (0-14 + inactive): 8,773  → 33.5 %
```

### File to change
**`Step_1_prod.py`** — the `PROFILE_DISTRIBUTION` dict, around line 70.

### Current code
```python
PROFILE_DISTRIBUTION = {
    'Commuter': 0.60,
    'Retired': 0.25,
    'Nonccommuter': 0.15
}
```

### New code
```python
# Source: SiStat demographic data, Krško municipality, 1 Jan 2025
# Commuter  = delovno aktivni po prebivališču  (11,748 / 26,175)
# Retired   = 65+ residents                    (5,654  / 26,175)
# Noncommuter = 0-14 + inactive 15-64          (8,773  / 26,175)
PROFILE_DISTRIBUTION = {
    'Commuter':    0.449,
    'Retired':     0.216,
    'Nonccommuter': 0.335
}
```

### Verification step
After running `Step_1_prod.py`, check the printed `PROFILE DISTRIBUTION SUMMARY` block at the end.  
With 1,030 EV vehicles (6.13% scenario) expect approximately:
- Commuter:    ~463 vehicles
- Retired:     ~223 vehicles
- Nonccommuter: ~345 vehicles

---

## Upgrade #11 — Day-Type System (Weekday / Friday / Weekend / Holiday)

### What it is
Currently the model handles only `'Workday'` and partially treats Friday.  
Introduce a proper `day_type` enum with four categories and route each to a different trip-generation logic.

### File to change
**`Step_1_prod.py`** — the days list and the main `get_trip_parameters` loop.

### Step 1 — Define the day-type enum

Add near the top of `Step_1_prod.py`, after imports:

```python
from enum import Enum

class DayType(Enum):
    MON_THU = 'Mon-Thu'   # Standard workday
    FRIDAY  = 'Friday'    # Workday + higher leisure/shopping probability after work
    SATURDAY = 'Saturday' # No commute, leisure dominant, later departures
    SUNDAY   = 'Sunday'   # Lowest mobility, personal/leisure only
    HOLIDAY  = 'Holiday'  # Same as Sunday
```

### Step 2 — Replace the `days_week` list

Find the existing `days_week` list (currently something like `['Workday', 'Workday', ...]`) and replace:

```python
days_week = [
    DayType.MON_THU,
    DayType.MON_THU,
    DayType.MON_THU,
    DayType.MON_THU,
    DayType.FRIDAY,
    DayType.SATURDAY,
    DayType.SUNDAY,
]
```

### Step 3 — Add a helper that maps DayType → allowed purposes and trip-count weights

Add this function before `get_trip_parameters`:

```python
def get_day_config(day_type: DayType) -> dict:
    """
    Returns trip-generation config for each day type.
    'trip_count_weights': probability of [0, 2, 4] trips that day.
    'purpose_boost': multiplier applied on top of Markov for specific purposes.
    'departure_shift_h': shift the departure time distribution by this many hours (positive = later).
    """
    configs = {
        DayType.MON_THU: {
            'trip_count_weights': [0.0, 0.80, 0.20],   # 80% do 2 trips, 20% do 4 trips
            'purpose_boost': {},
            'departure_shift_h': 0.0,
        },
        DayType.FRIDAY: {
            'trip_count_weights': [0.0, 0.70, 0.30],   # slightly more multi-stop
            'purpose_boost': {'Leisure': 1.4, 'Shopping': 1.3},
            'departure_shift_h': 0.0,
        },
        DayType.SATURDAY: {
            'trip_count_weights': [0.10, 0.65, 0.25],
            'purpose_boost': {'Leisure': 1.8, 'Shopping': 1.6, 'Personal': 1.2},
            'departure_shift_h': 1.5,   # 1.5 h later on average
        },
        DayType.SUNDAY: {
            'trip_count_weights': [0.20, 0.70, 0.10],
            'purpose_boost': {'Leisure': 2.0, 'Personal': 1.3},
            'departure_shift_h': 2.0,
        },
        DayType.HOLIDAY: {
            'trip_count_weights': [0.25, 0.65, 0.10],
            'purpose_boost': {'Leisure': 2.2},
            'departure_shift_h': 2.5,
        },
    }
    return configs[day_type]
```

### Step 4 — Use `DayType` inside the generation loop

In `get_trip_parameters`, the current `if days[day] == 'Workday':` branch should become:

```python
day_config = get_day_config(days[day])

# Determine number of trips for this vehicle on this day
number_of_trips_today = np.random.choice(
    [0, 2, 4],
    p=day_config['trip_count_weights']
)
if number_of_trips_today == 0:
    # Vehicle stays home all day — append zeros / skip
    continue

# On non-workdays, remove 'Work' from allowed purposes for ALL profiles
if days[day] in (DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY):
    effective_purposes = [p for p in vehicle_profiles[vehicle].allowed_purposes if p != 'Work']
else:
    effective_purposes = vehicle_profiles[vehicle].allowed_purposes
```

Pass `day_config['departure_shift_h']` into `sample_departure_time` as an optional shift parameter (add the `shift_h=0.0` kwarg to that function in `Functions_step_1.py`).

### Output change
The exported DataFrame column `'Day Type'` will now contain the `DayType.value` string (e.g. `'Saturday'`) instead of `'Workday'`.

---

## Upgrade #14 — Trip-Chain Consistency Validator

### What it is
After a daily chain is generated, validate it against a set of logical rules before accepting it. Currently `validate_chain` in `UserProfile` only checks allowed purposes; it does not check sequencing or home-start/home-end.

### File to change
**`Step_1_prod.py`** — add a standalone validator function and call it after chain generation.

### New function — add after the `UserProfile` class block

```python
def validate_chain_consistency(trip_chain: list, profile, day_type: DayType) -> tuple[bool, str]:
    """
    Validates a generated daily trip chain for logical consistency.

    Rules:
    1. Chain must start with 'Home'.
    2. Chain must end with 'Home' (last destination).
    3. No consecutive identical purposes (no Home→Home).
    4. 'Work' purpose only allowed for Commuter profile AND on workday-type days.
    5. 'Work' must not appear more than once per day.
    6. 'Education' only allowed for Nonccommuter profile.
    7. Chain length must be at least 2 (depart and return).

    Returns:
        (True, '') if valid, or (False, reason_string) if invalid.
    """
    if len(trip_chain) < 2:
        return False, "Chain too short (< 2 trips)"

    if trip_chain[0] != 'Home':
        return False, f"Chain does not start at Home: starts at '{trip_chain[0]}'"

    if trip_chain[-1] != 'Home':
        return False, f"Chain does not end at Home: ends at '{trip_chain[-1]}'"

    for i in range(len(trip_chain) - 1):
        if trip_chain[i] == trip_chain[i + 1]:
            return False, f"Consecutive identical purpose at position {i}: '{trip_chain[i]}'"

    work_count = trip_chain.count('Work')
    if work_count > 1:
        return False, f"'Work' appears {work_count} times (max 1)"

    if work_count > 0:
        if not profile.work_required:
            return False, f"'Work' in chain but profile '{profile.name}' has work_required=False"
        if day_type in (DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY):
            return False, f"'Work' in chain on non-workday ({day_type.value})"

    if 'Education' in trip_chain and profile.name != 'Nonccommuter':
        return False, f"'Education' in chain but profile is '{profile.name}' (only Nonccommuter allowed)"

    return True, ''
```

### Where to call it

Inside the vehicle loop in `get_trip_parameters`, after the chain for a vehicle-day is assembled and before appending to output matrices:

```python
is_valid, reason = validate_chain_consistency(
    trip_chain=chosen_distribution[:],   # list of purpose strings for this day
    profile=vehicle_profiles[vehicle],
    day_type=days[day]
)

if not is_valid:
    print(f"[CHAIN REJECTED] Vehicle {vehicle+1}, Day {day+1}: {reason}. Retrying...")
    # reset and retry the vehicle-day loop (existing retry logic)
    success = False
    continue
```

### Optional — chain validation summary at end of run

After the generation loop, add:

```python
print("\n=== CHAIN VALIDATION SUMMARY ===")
print(f"Total chains generated : {total_chains}")
print(f"Chains rejected        : {rejected_chains}")
print(f"Rejection rate         : {rejected_chains/total_chains*100:.1f}%")
```

Add counters `total_chains = 0` and `rejected_chains = 0` before the loop and increment them accordingly.

---

## Upgrade #17 — Spatial Activity Concentration by Zone

### What it is
After simulation output is ready (from `Step_2_prod.py`), aggregate start/end coordinates and energy consumption into spatial zones (settlements or grid cells) to show which areas generate the most EV activity.

### File to create
Create a new file **`Step_4_analysis.py`** in the project root.

### Full code for `Step_4_analysis.py`

```python
"""
Step_4_analysis.py
Upgrade #17 — Spatial concentration of EV activity by zone.

Input : the trip file produced by Step_2_prod.py
        e.g. "02_Trips/02_Trips_1030_EVs_2_trips_1_days.xlsx"
Output: "04_Spatial/spatial_activity_summary.xlsx"
        + console table of top zones by arrivals / energy
"""

import os
import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt

# ── Configuration ───────────────────────────────────────────────────────────
TRIPS_FILE = "02_Trips/02_Trips_1030_EVs_2_trips_1_days.xlsx"  # adjust as needed
GRID_SIZE_KM = 0.5          # spatial resolution of grid cells
OUTPUT_DIR  = "04_Spatial"

# Krško bounding box (WGS-84)
LAT_MIN, LAT_MAX = 45.92, 46.00
LON_MIN, LON_MAX = 15.45, 15.58

# ── Helpers ──────────────────────────────────────────────────────────────────
def haversine(lon1, lat1, lon2, lat2):
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * 6371 * asin(sqrt(a))

def assign_grid_cell(lat, lon, lat_min, lon_min, grid_km):
    """Return (row, col) grid index for a coordinate."""
    row = int(haversine(lon, lat_min, lon, lat) / grid_km)
    col = int(haversine(lon_min, lat, lon, lat) / grid_km)
    return (row, col)

def cell_label(row, col, lat_min, lon_min, grid_km):
    """Human-readable label: approximate centre lat/lon of cell."""
    # Approximate: 1 degree lat ≈ 111 km, lon varies
    centre_lat = lat_min + (row + 0.5) * grid_km / 111.0
    centre_lon = lon_min + (col + 0.5) * grid_km / (111.0 * cos(radians(lat_min)))
    return f"{centre_lat:.4f}N, {centre_lon:.4f}E"

# ── Load data ────────────────────────────────────────────────────────────────
df = pd.read_excel(TRIPS_FILE)

required = ['Start location lat', 'Start location lon',
            'End location lat',   'End location lon',
            'Consumption_kWh',    'Distance']
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing columns in trip file: {missing}")

df = df.dropna(subset=required)

# ── Assign grid cells ────────────────────────────────────────────────────────
df['start_cell'] = df.apply(
    lambda r: assign_grid_cell(r['Start location lat'], r['Start location lon'],
                                LAT_MIN, LON_MIN, GRID_SIZE_KM), axis=1)
df['end_cell'] = df.apply(
    lambda r: assign_grid_cell(r['End location lat'], r['End location lon'],
                                LAT_MIN, LON_MIN, GRID_SIZE_KM), axis=1)

# ── Aggregate ────────────────────────────────────────────────────────────────
# Departures (trip origins)
departures = (df.groupby('start_cell')
                .agg(departures=('Distance', 'count'),
                     total_distance_km=('Distance', 'sum'))
                .reset_index()
                .rename(columns={'start_cell': 'cell'}))

# Arrivals + energy (trip destinations)
arrivals = (df.groupby('end_cell')
              .agg(arrivals=('Distance', 'count'),
                   total_energy_kWh=('Consumption_kWh', 'sum'))
              .reset_index()
              .rename(columns={'end_cell': 'cell'}))

summary = pd.merge(departures, arrivals, on='cell', how='outer').fillna(0)
summary['net_flow'] = summary['arrivals'] - summary['departures']
summary['cell_label'] = summary['cell'].apply(
    lambda c: cell_label(c[0], c[1], LAT_MIN, LON_MIN, GRID_SIZE_KM))
summary = summary.sort_values('total_energy_kWh', ascending=False)

# ── Print top 10 ─────────────────────────────────────────────────────────────
print("\n=== TOP 10 ZONES BY ENERGY DEMAND (kWh) ===")
print(summary[['cell_label', 'arrivals', 'departures',
               'net_flow', 'total_energy_kWh']].head(10).to_string(index=False))

# ── Export ───────────────────────────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
out_path = os.path.join(OUTPUT_DIR, "spatial_activity_summary.xlsx")
summary.to_excel(out_path, index=False)
print(f"\nSaved: {out_path}")
```

### How to run
```bash
python Step_4_analysis.py
```

Adjust `TRIPS_FILE` to match the actual output filename from `Step_2_prod.py` (it includes vehicle count, trip count, and day count in the name).

### Output columns explained
| Column | Meaning |
|--------|---------|
| `cell_label` | Approximate lat/lon centre of grid cell |
| `departures` | Number of trips starting in this cell |
| `arrivals` | Number of trips ending in this cell |
| `net_flow` | arrivals − departures (positive = net attractor) |
| `total_energy_kWh` | Total EV energy consumed arriving in this cell |

---

## Summary: Files Modified or Created

| Upgrade | File | Action |
|---------|------|--------|
| #5 — Demographic profile weights | `Step_1_prod.py` | Edit `PROFILE_DISTRIBUTION` dict |
| #11 — Day-type system | `Step_1_prod.py` | Add `DayType` enum, `get_day_config()`, update generation loop |
| #14 — Chain consistency validator | `Step_1_prod.py` | Add `validate_chain_consistency()`, call inside loop |
| #17 — Spatial activity aggregation | `Step_4_analysis.py` | **Create new file** |

Apply upgrades in the order listed — #5 and #14 are independent of each other, #11 must be done before #14 (since the validator needs `DayType`), and #17 is entirely standalone.

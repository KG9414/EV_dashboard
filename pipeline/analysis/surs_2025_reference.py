"""
SURS 2025 reference data — Potovalne navade prebivalstva Slovenije.

Source: SURS (Statistični urad RS) interactive mobility-habits dashboard, 2025 figures,
provided by the user as 4 screenshots on 2026-06-17. Exact page/table URL not yet confirmed —
cite generically as "SURS, Potovalne navade prebivalstva, Slovenija, 2025" until confirmed.

IMPORTANT — only data with exact printed values is included here:
  - DAILY_INDICATORS: transcribed from a printed table (image 2). Exact.
  - PURPOSE_STATS: transcribed from a bar chart with printed value labels (image 3). Exact.
  - TRIP_BUCKETS_2025: transcribed from printed bullet-point text (screenshot, 2026-06-27). Exact.
  - The mode-share-by-distance-bin stacked bar chart (image 1) had NO printed per-segment
    values, only visual proportions. It is deliberately NOT transcribed into numbers here —
    doing so would mean inventing data from eyeballed pixel heights. Use only qualitatively
    (e.g. "car share rises sharply beyond ~2.5 km") if referenced at all.
  - DEPARTURE_BY_PURPOSE_2021_QUALITATIVE: a line chart (2021, NOT 2025 — different vintage,
    see CITATION_2021_HOURLY) with no printed per-point values either. Only approximate peak
    hours are recorded, qualitatively. Per-hour percentages are NOT transcribed.

KNOWN CONFLICT: these numbers are ALL-MODE (car + walk + bike + public transport + other),
not car-only. They partially disagree with the car-trip calibration constants already in
pipeline/Step_1_fit_si.py (SURS_MEAN_DURATION_MIN=13.0, SURS_MEAN_DIST_KM=13.8,
SURS_MEAN_TRIPS_PER_DAY=2.94, cited there as ref [57]):
    metric                  Step_1_fit_si.py (old)   SURS 2025 all-mode (new, this file)
    mean trip duration      13.0 min                 24 min (all days)
    mean trip distance      13.8 km                  14.4 km (all days)
    mean trips/day          2.94                     2.3 (all days)
Distance is close; duration and trips/day are not. Possible explanation: the old constants
may be a car-only or different-year subset rather than this exact table. Not resolved —
both are shown side by side, clearly labelled, in the comparison figures pending verification.
"""

# ---------------------------------------------------------------------------
# Daily mobility indicators by day type (image 2 — printed table, exact values)
# ---------------------------------------------------------------------------
DAILY_INDICATORS = {
    "all_days": {
        "trips_per_day": 2.3,
        "dist_per_day_km": 32.4,
        "time_per_day_min": 55,
        "car_occupancy": 1.6,
        "dist_per_trip_km": 14.4,
        "duration_per_trip_min": 24,
    },
    "workday": {
        "trips_per_day": 2.4,
        "dist_per_day_km": 33.7,
        "time_per_day_min": 57,
        "car_occupancy": 1.4,
        "dist_per_trip_km": 13.7,
        "duration_per_trip_min": 23,
    },
    "non_workday": {
        "trips_per_day": 1.8,
        "dist_per_day_km": 29.2,
        "time_per_day_min": 51,
        "car_occupancy": 2.0,
        "dist_per_trip_km": 16.6,
        "duration_per_trip_min": 29,
    },
}

# Convenience: plausible real-world range (workday vs non-workday) for banding
DIST_PER_TRIP_RANGE_KM = (DAILY_INDICATORS["workday"]["dist_per_trip_km"],
                          DAILY_INDICATORS["non_workday"]["dist_per_trip_km"])  # (13.7, 16.6)
DURATION_PER_TRIP_RANGE_MIN = (DAILY_INDICATORS["workday"]["duration_per_trip_min"],
                               DAILY_INDICATORS["non_workday"]["duration_per_trip_min"])  # (23, 29)
TRIPS_PER_DAY_RANGE = (DAILY_INDICATORS["non_workday"]["trips_per_day"],
                       DAILY_INDICATORS["workday"]["trips_per_day"])  # (1.8, 2.4)

# ---------------------------------------------------------------------------
# Distance & duration by trip purpose (image 3 — printed bar labels, exact values)
# All-mode, Slovenia 2025. Keys match the pipeline/NHTS trip_label vocabulary
# where a direct correspondence exists ("Transport" <-> "peljati/priti iskat",
# matching the existing NHTS WHYTO mapping 6/7 -> Transport = drop off/pick up).
# ---------------------------------------------------------------------------
PURPOSE_STATS = {
    "Work":      {"dist_km": 18.3, "duration_min": 24},   # delo
    "Business":  {"dist_km": 32.9, "duration_min": 34},   # poslovni opravki
    "Education": {"dist_km": 15.8, "duration_min": 33},   # izobraževanje
    "Shopping":  {"dist_km": 6.9,  "duration_min": 13},   # nakupovanje
    "Transport": {"dist_km": 8.8,  "duration_min": 14},   # peljati/priti iskat
    "Leisure":   {"dist_km": 14.9, "duration_min": 32},   # prosti čas
    "Personal":  {"dist_km": 14.7, "duration_min": 22},   # osebni opravki
}
PURPOSE_STATS_ALL = {"dist_km": 14.4, "duration_min": 24}  # "vsi nameni"

# ---------------------------------------------------------------------------
# Trip distance/duration buckets + departure-time shares (printed bullet text,
# screenshot provided 2026-06-27). dist_per_trip_km/duration_per_trip_min here
# (14.4 km / 24 min) match DAILY_INDICATORS["all_days"] exactly, so this bullet
# list is treated as the SAME 2025 source -- but the year was not visible on
# this particular screenshot, so that's an inference, not a confirmed fact.
# ---------------------------------------------------------------------------
TRIP_BUCKETS_2025 = {
    "pct_trips_under_2_5km": 30,   # 30% poti krajših od 2.5 km (polovica teh peš)
    "pct_trips_under_50km": 93,    # 93% poti krajših od 50 km
    "pct_trips_under_10min": 41,   # 41% poti je trajalo 10 min ali manj
    "pct_depart_14_16h": 17,       # 17% poti se je začelo med 14. in 16. uro
    "pct_depart_7_9h": 13,         # 13% poti se je začelo med 7. in 9. uro
}
# Qualitative (confirmed, not numeric): shopping trips are shortest in both distance
# AND duration; education trips are shorter than work trips in distance but take
# longer in duration. This matches PURPOSE_STATS above (Shopping 6.9km/13min lowest;
# Education 15.8km/33min < Work 18.3km/24min in distance but > in duration).

# ---------------------------------------------------------------------------
# Departure time by purpose, hour-of-day (screenshot provided 2026-06-27).
# SOURCE YEAR IS 2021 ("Poti po nekaterih namenih in uri začetka, Slovenija, 2021")
# -- explicitly NOT 2025, do not mix with the rest of this module's data.
# The chart is a line chart with NO printed per-point values -- only approximate
# peak hours are recorded here (qualitative), per-hour percentages are NOT
# transcribed (would be fabricating data from eyeballed pixel positions).
# ---------------------------------------------------------------------------
DEPARTURE_BY_PURPOSE_2021_QUALITATIVE = {
    "Work":     "sharp peak ~6-7h (~15.5%), smaller secondary peak ~14-16h (~12.5%)",
    "Shopping": "peak ~10-11h (~14%)",
    "Leisure":  "peak ~18-19h (~10%)",
}

CITATION = "SURS, Potovalne navade prebivalstva, Slovenija, 2025 (exact URL not yet confirmed)"
CITATION_2021_HOURLY = ("SURS, \"Poti po nekaterih namenih in uri začetka, Slovenija, 2021\" "
                        "(exact URL not yet confirmed) -- 2021 vintage, not 2025")

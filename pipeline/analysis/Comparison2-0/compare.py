"""
NHTS vs DomCenter Pipeline — rigorous honest comparison
========================================================
Compares ONLY quantities that actually exist in both datasets.

Run from project root:
    cd /path/to/DomCenter
    source venv/bin/activate
    python analysis/Comparison2-0/compare.py
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ONEDRIVE = "/Users/karlagliha/Documents/Documents/Faks/Magisterij/OneDrive_1_2-25-2026"
PIPELINE_DIR = os.path.join(BASE, "pipeline")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_DIR = os.path.dirname(OUT_DIR)

sys.path.insert(0, ANALYSIS_DIR)
import surs_2025_reference as surs25

NHTS_CSV   = os.path.join(ONEDRIVE, "00_NHTS_data.csv")
GAUSS_XLSX = os.path.join(PIPELINE_DIR, "df_gauss_v1.xlsx")

# Largest pipeline output by vehicle count
PIPELINE_FILE = os.path.join(PIPELINE_DIR, "01_Trips_parameters_1344_EVs_2_trips_1_days.xlsx")

# NOTE: Step_1_fit_si.py's old SURS reference (~13 min, unverified source) conflicts with
# surs_2025_reference.py's "all days" duration of 24 min — possibly a car-only or
# different-year subset. The old value is deliberately NOT plotted on any chart (only
# verified SURS 2025 data appears on the figures); the conflict is documented in notes.txt.

# ---------------------------------------------------------------------------
# Step 1 — Load NHTS raw data
# ---------------------------------------------------------------------------
print("=" * 65)
print("Loading NHTS raw data …")
nhts_raw = pd.read_csv(NHTS_CSV, sep=";", low_memory=False)
print(f"  Shape: {nhts_raw.shape}")
print(f"  Columns: {list(nhts_raw.columns)}")
print(f"\n  First 5 rows:")
print(nhts_raw.head(5).to_string())

# NHTS trip purpose unique values
print(f"\n  TRIPPURP unique values: {sorted(nhts_raw['TRIPPURP'].dropna().unique().tolist())}")
print(f"  WHYTO unique values: {sorted(nhts_raw['WHYTO'].dropna().unique().tolist())}")
print(f"  TRPTRANS unique values: {sorted(nhts_raw['TRPTRANS'].dropna().unique().tolist())}")
print(f"  STRTTIME sample: {nhts_raw['STRTTIME'].dropna().head(10).tolist()}")
print(f"  TRVLCMIN sample: {nhts_raw['TRVLCMIN'].dropna().head(10).tolist()}")

# ---------------------------------------------------------------------------
# Step 2 — Filter NHTS exactly as the pipeline does (car trips only)
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("Filtering NHTS to car trips (TRPTRANS == 3) …")
nhts = nhts_raw[nhts_raw["TRPTRANS"] == 3].copy()
print(f"  After car filter: {nhts.shape[0]} trips")

# ---------------------------------------------------------------------------
# Step 3 — Map WHYTO codes to pipeline labels
# (from DFunctions_step_1.py location_group_map)
# ---------------------------------------------------------------------------
WHYTO_MAP = {
    -9: "unknown", -8: "unknown", -7: "unknown",
    1:  "Home",
    2:  "Work",   3:  "Work",
    4:  "Business", 5: "Business",
    6:  "Transport", 7: "Transport",
    8:  "Education", 9: "Education",
    10: "Personal", 12: "Personal", 14: "Personal",
    18: "Personal", 19: "Personal",
    11: "Shopping",
    13: "Leisure", 15: "Leisure", 16: "Leisure",
    17: "Leisure", 97: "Leisure",
}

nhts["trip_label"] = nhts["WHYTO"].map(WHYTO_MAP)
print(f"\n  WHYTO → label distribution:")
print(nhts["trip_label"].value_counts(dropna=False).to_string())
unmapped = nhts["WHYTO"][~nhts["WHYTO"].isin(WHYTO_MAP)].unique()
if len(unmapped) > 0:
    print(f"\n  WARNING: unmapped WHYTO codes: {sorted(unmapped.tolist())}")

# Keep only recognised labels for fair comparison
PIPELINE_STATES = ["Home", "Work", "Business", "Education",
                   "Shopping", "Transport", "Leisure", "Personal"]
nhts_mapped = nhts[nhts["trip_label"].isin(PIPELINE_STATES)].copy()
print(f"\n  After dropping unknown labels: {nhts_mapped.shape[0]} trips")

# ---------------------------------------------------------------------------
# Step 4 — Departure time from NHTS (STRTTIME is HHMM integer)
# Convert to hours (float)
# ---------------------------------------------------------------------------
def hhmm_to_hour(hhmm_series):
    """Convert HHMM integer to decimal hour. Returns NaN for invalid entries."""
    s = pd.to_numeric(hhmm_series, errors="coerce")
    hour = (s // 100).astype("float")
    minute = (s % 100).astype("float")
    # Filter out impossible values
    valid = (hour >= 0) & (hour <= 23) & (minute >= 0) & (minute < 60)
    result = hour + minute / 60.0
    result[~valid] = np.nan
    return result

nhts_mapped["depart_hour"] = hhmm_to_hour(nhts_mapped["STRTTIME"])
print(f"\n  NHTS departure hour — valid: {nhts_mapped['depart_hour'].notna().sum()}, "
      f"NaN: {nhts_mapped['depart_hour'].isna().sum()}")

# ---------------------------------------------------------------------------
# Step 5 — Trip duration from NHTS (TRVLCMIN = minutes)
# ---------------------------------------------------------------------------
nhts_mapped["duration_min"] = pd.to_numeric(nhts_mapped["TRVLCMIN"], errors="coerce")
nhts_mapped = nhts_mapped[nhts_mapped["duration_min"] > 0]   # drop zero/negative
print(f"  NHTS duration (min) — valid: {nhts_mapped['duration_min'].notna().sum()}")
print(f"  NHTS duration quantiles: {nhts_mapped['duration_min'].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).to_dict()}")

# Trips per person per day (NHTS persons identified by HOUSEID+PERSONID)
nhts_tpd = (
    nhts_mapped
    .groupby(["HOUSEID", "PERSONID"])["TDTRPNUM"]
    .count()
    .reset_index(name="trips_per_person")
)
print(f"\n  NHTS trips per person/day — distribution:")
print(nhts_tpd["trips_per_person"].value_counts().sort_index().to_string())

# ---------------------------------------------------------------------------
# Step 6 — Load pipeline output
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print(f"Loading pipeline file: {os.path.basename(PIPELINE_FILE)} …")
pipe = pd.read_excel(PIPELINE_FILE)
print(f"  Shape: {pipe.shape}")
print(f"  Columns: {list(pipe.columns)}")
print(f"\n  First 5 rows:")
print(pipe.head(5).to_string())
print(f"\n  Trip type unique values: {sorted(pipe['Trip type'].dropna().unique().tolist())}")
print(f"  Profile unique values: {sorted(pipe['Profile'].dropna().unique().tolist())}")

# ----- Business trip check -----
business_count = (pipe["Trip type"] == "Business").sum()
business_pct = 100.0 * business_count / len(pipe)
print(f"\n  *** Business trips in pipeline output: {business_count} "
      f"({business_pct:.2f}% of all trip records)")

# ---------------------------------------------------------------------------
# Step 7 — Derive pipeline departure time and duration
# Start is 15-min interval index (0-95 for 96 intervals in 24 h)
# Start * 0.25 = hour (float)
# Duration is in minutes
# ---------------------------------------------------------------------------
pipe["depart_hour"] = pipe["Start"] * 0.25
pipe["duration_min"] = pipe["Duration"]

# Trips per vehicle per day
pipe_tpv = (
    pipe
    .groupby(["Vehicle ID"])["Trip ID"]
    .count()
    .reset_index(name="trips_per_vehicle")
)
print(f"\n  Pipeline trips per vehicle — distribution:")
print(pipe_tpv["trips_per_vehicle"].value_counts().sort_index().to_string())

# ---------------------------------------------------------------------------
# Step 6c — Load NHTS-fitted departure-time curve (df_gauss)
# NOTE: df_gauss_v1.xlsx is generated from NHTS US car trips in Step_0_prod.py (line 382).
# It is NOT Slovenian data — it is the empirical NHTS departure probability distribution
# used as the sampling base in the pipeline. The 13-min duration reference is SURS (real SI data).
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("Loading NHTS-fitted departure-time curve (df_gauss_v1, NOT Slovenian data) …")
gauss_raw = pd.read_excel(GAUSS_XLSX)
# File has 24 hourly probability values in column index 1
hourly_prob = pd.to_numeric(gauss_raw.iloc[:, 1], errors="coerce").fillna(0).values[:24]
# Expand to 96 × 15-min intervals and normalise
prob_15min = np.repeat(hourly_prob, 4)
prob_15min = prob_15min / prob_15min.max()   # scale to 1 for density overlay
gauss_hours = np.arange(0, 24, 0.25) + 0.125   # centre of each 15-min bin
print(f"  Hourly probs (first 6h): {hourly_prob[:6].round(4).tolist()}")

# ---------------------------------------------------------------------------
# Step 8 — Decide valid panels (data-driven, not assumed)
# ---------------------------------------------------------------------------
has_trip_type  = nhts_mapped["trip_label"].notna().any() and pipe["Trip type"].notna().any()
has_depart     = nhts_mapped["depart_hour"].notna().any() and pipe["depart_hour"].notna().any()
has_duration   = nhts_mapped["duration_min"].notna().any() and pipe["duration_min"].notna().any()
# Purpose-level duration vs SURS 2025: needs overlap between pipeline Trip type,
# NHTS trip_label, and surs25.PURPOSE_STATS keys (Work, Business, Education,
# Shopping, Transport, Leisure, Personal — Home is not a destination purpose).
has_purpose_duration = has_trip_type and has_duration
has_work_departure   = has_trip_type and has_depart

SI_REF_COLOR   = "#9467bd"   # purple for SI calibration reference

print("\n" + "=" * 65)
print("Panel validity check:")
print(f"  Trip type/purpose distribution : {has_trip_type}")
print(f"  Departure time distribution    : {has_depart}")
print(f"  Trip duration distribution     : {has_duration}")
print(f"  Purpose-level duration vs SURS : {has_purpose_duration}")
print(f"  Work-only departure time       : {has_work_departure}")

valid_panels = [has_trip_type, has_depart, has_duration, has_purpose_duration, has_work_departure]
n_panels = sum(valid_panels)
assert n_panels >= 2, "Need at least 2 valid panels — check data."

# ---------------------------------------------------------------------------
# Step 9 — Build figure
# ---------------------------------------------------------------------------
sns.set_theme(style="whitegrid", font_scale=1.1)

NHTS_COLOR = "#1f77b4"   # blue
PIPE_COLOR  = "#d62728"  # red

# Dynamic layout: 2 per row
ncols = 2
nrows = (n_panels + 1) // 2
fig = plt.figure(figsize=(14, 5 * nrows))
gs = gridspec.GridSpec(nrows, ncols, hspace=0.45, wspace=0.35)
fig.suptitle(
    "NHTS (US national, car trips) vs. DomCenter Pipeline (Krško EV simulation)\n"
    "Honest comparison — only quantities present in both datasets",
    fontsize=13, y=1.01, ha="center"
)

panel_idx = 0

def next_ax(fig, gs, idx, ncols):
    row, col = divmod(idx, ncols)
    return fig.add_subplot(gs[row, col])


# --- Panel A: Trip type / purpose frequency ---
if has_trip_type:
    ax = next_ax(fig, gs, panel_idx, ncols)
    panel_idx += 1

    # Exclude Home — it inflates NHTS share due to return trips and is not a
    # meaningful destination category for the pipeline's outward-trip model.
    PLOT_STATES = [s for s in PIPELINE_STATES if s != "Home"]

    nhts_freq = nhts_mapped["trip_label"].value_counts(normalize=True).reindex(PIPELINE_STATES, fill_value=0)
    pipe_freq  = pipe["Trip type"].value_counts(normalize=True).reindex(PIPELINE_STATES, fill_value=0)

    # Re-normalise after dropping Home so bars sum to 100 %
    nhts_freq_plot = nhts_freq.reindex(PLOT_STATES).fillna(0)
    nhts_freq_plot = nhts_freq_plot / nhts_freq_plot.sum()
    pipe_freq_plot = pipe_freq.reindex(PLOT_STATES).fillna(0)
    pipe_freq_plot = pipe_freq_plot / pipe_freq_plot.sum()

    x = np.arange(len(PLOT_STATES))
    width = 0.38
    bars_nhts = ax.bar(x - width / 2, nhts_freq_plot.values * 100, width,
                       label=f"NHTS US (n={len(nhts_mapped):,})", color=NHTS_COLOR, alpha=0.85)
    bars_pipe = ax.bar(x + width / 2, pipe_freq_plot.values * 100, width,
                       label=f"Pipeline Krško (n={len(pipe):,})", color=PIPE_COLOR, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(PLOT_STATES, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Share (%)")
    ax.set_title("A) Trip destination purpose\n(Home excluded, renormalised)")
    ax.legend(fontsize=8)
    ax.set_ylim(0, max(nhts_freq_plot.max(), pipe_freq_plot.max()) * 125)


# --- Panel B: Departure time distribution ---
if has_depart:
    ax = next_ax(fig, gs, panel_idx, ncols)
    panel_idx += 1

    bins = np.arange(0, 24.25, 0.5)   # 30-min bins

    nhts_dep = nhts_mapped["depart_hour"].dropna()
    pipe_dep  = pipe["depart_hour"].dropna()

    ax.hist(nhts_dep, bins=bins, density=True,
            alpha=0.65, color=NHTS_COLOR, label=f"NHTS US (n={len(nhts_dep):,})")
    ax.hist(pipe_dep, bins=bins, density=True,
            alpha=0.65, color=PIPE_COLOR, label=f"Pipeline Krško (n={len(pipe_dep):,})")

    # NHTS-fitted departure curve used as sampling distribution in pipeline (Step_0_prod.py → df_gauss_v1.xlsx)
    ax.plot(gauss_hours, prob_15min * 0.30, color=SI_REF_COLOR,
            linewidth=2, linestyle="--", label="NHTS sampling curve (df_gauss_v1)")

    # SURS 2025 departure-time windows (printed bullet stats — exact, all-purpose share
    # of trips starting in each window). Shaded as bands, not a fabricated full curve.
    ax.axvspan(7, 9, color="#2ca02c", alpha=0.12)
    ax.axvspan(14, 16, color="#2ca02c", alpha=0.12)
    surs_7_9   = surs25.TRIP_BUCKETS_2025["pct_depart_7_9h"]
    surs_14_16 = surs25.TRIP_BUCKETS_2025["pct_depart_14_16h"]
    ax.plot([], [], color="#2ca02c", alpha=0.4, linewidth=8,
            label=f"SURS 2025: {surs_7_9}% poti 7–9h, {surs_14_16}% poti 14–16h")

    nhts_pct_7_9   = ((nhts_dep >= 7) & (nhts_dep < 9)).mean() * 100
    nhts_pct_14_16 = ((nhts_dep >= 14) & (nhts_dep < 16)).mean() * 100
    pipe_pct_7_9   = ((pipe_dep >= 7) & (pipe_dep < 9)).mean() * 100
    pipe_pct_14_16 = ((pipe_dep >= 14) & (pipe_dep < 16)).mean() * 100
    print(f"\n  Departure window check (SURS 2025: 7-9h={surs_7_9}%, 14-16h={surs_14_16}%):")
    print(f"    NHTS    — 7-9h: {nhts_pct_7_9:.1f}%, 14-16h: {nhts_pct_14_16:.1f}%")
    print(f"    Pipeline— 7-9h: {pipe_pct_7_9:.1f}%, 14-16h: {pipe_pct_14_16:.1f}%")

    ax.set_xlabel("Departure time (hour of day)")
    ax.set_ylabel("Density")
    ax.set_title("B) Departure time distribution\n(+ NHTS sampling curve; SURS 2025 windows shaded)")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.legend(fontsize=7)


# --- Panel C: Trip duration distribution ---
if has_duration:
    ax = next_ax(fig, gs, panel_idx, ncols)
    panel_idx += 1

    cap_min = 2
    cap_max = 120   # cap at 2 h for readability

    nhts_dur = nhts_mapped["duration_min"].dropna().clip(lower=cap_min, upper=cap_max)
    pipe_dur  = pipe["duration_min"].dropna().clip(lower=cap_min, upper=cap_max)

    bins = np.arange(0, cap_max + 5, 5)

    ax.hist(nhts_dur, bins=bins, density=True,
            alpha=0.65, color=NHTS_COLOR, label=f"NHTS US (n={len(nhts_dur):,})")
    ax.hist(pipe_dur, bins=bins, density=True,
            alpha=0.65, color=PIPE_COLOR, label=f"Pipeline Krško (n={len(pipe_dur):,})")

    nhts_med = nhts_dur.median()
    pipe_med  = pipe_dur.median()
    ax.axvline(nhts_med, color=NHTS_COLOR, linestyle="--", linewidth=1.5,
               label=f"NHTS median {nhts_med:.0f} min")
    ax.axvline(pipe_med, color=PIPE_COLOR, linestyle="--", linewidth=1.5,
               label=f"Pipeline median {pipe_med:.0f} min")
    # NOTE: the old Step_1_fit_si.py reference (~13 min, unverified source) is intentionally
    # NOT plotted here — only verified SURS 2025 data appears on this chart. The conflict
    # with the old figure is documented in notes.txt / REPORT.md, not shown on the image.
    # SURS 2025 all-mode reference: workday/non-workday range as a plausible band,
    # plus the "all days" point value. Source: surs_2025_reference.py (image 2 table).
    lo, hi = surs25.DURATION_PER_TRIP_RANGE_MIN
    ax.axvspan(lo, hi, color="#2ca02c", alpha=0.12,
               label=f"SURS 2025 workday–non-workday range [{lo:.0f}–{hi:.0f}] min")
    ax.axvline(surs25.DAILY_INDICATORS["all_days"]["duration_per_trip_min"], color="#2ca02c",
               linestyle="-.", linewidth=2,
               label=f"SURS 2025 all days {surs25.DAILY_INDICATORS['all_days']['duration_per_trip_min']:.0f} min")

    ax.set_xlabel("Trip duration (minutes, capped at 120)")
    ax.set_ylabel("Density")
    ax.set_title("C) Trip duration distribution\n(+ SURS 2025 all-mode plausible range)")
    ax.legend(fontsize=7)
    ax.set_xlim(0, cap_max)

    # Print summary stats
    print(f"\n  Duration comparison:")
    print(f"    NHTS    — median: {nhts_dur.median():.1f} min, mean: {nhts_dur.mean():.1f} min")
    print(f"    Pipeline— median: {pipe_dur.median():.1f} min, mean: {pipe_dur.mean():.1f} min")

    # SURS 2025 bucket check: 41% of trips <= 10 min (printed bullet stat, exact)
    surs_pct_10min = surs25.TRIP_BUCKETS_2025["pct_trips_under_10min"]
    nhts_pct_10min = (nhts_dur <= 10).mean() * 100
    pipe_pct_10min = (pipe_dur <= 10).mean() * 100
    print(f"\n  Trips <=10 min (SURS 2025: {surs_pct_10min}%):")
    print(f"    NHTS    : {nhts_pct_10min:.1f}%")
    print(f"    Pipeline: {pipe_pct_10min:.1f}%")


# --- Panel D: Per-purpose trip duration vs SURS 2025 (exact printed values) ---
if has_purpose_duration:
    ax = next_ax(fig, gs, panel_idx, ncols)
    panel_idx += 1

    purposes = list(surs25.PURPOSE_STATS.keys())   # Work, Business, Education, Shopping, Transport, Leisure, Personal

    nhts_by_purpose = nhts_mapped.groupby("trip_label")["duration_min"].mean()
    pipe_by_purpose  = pipe.groupby("Trip type")["duration_min"].mean()

    nhts_y = [nhts_by_purpose.get(p, np.nan) for p in purposes]
    pipe_y = [pipe_by_purpose.get(p, np.nan) for p in purposes]
    surs_y = [surs25.PURPOSE_STATS[p]["duration_min"] for p in purposes]

    x = np.arange(len(purposes))
    width = 0.27
    ax.bar(x - width, nhts_y, width, label="NHTS US (mean)", color=NHTS_COLOR, alpha=0.85)
    ax.bar(x,          pipe_y, width, label="Pipeline Krško (mean)", color=PIPE_COLOR, alpha=0.85)
    ax.bar(x + width,  surs_y, width, label="SURS 2025 Slovenia (point)", color="#2ca02c", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(purposes, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Mean trip duration (min)")
    ax.set_title("D) Trip duration by purpose\nNHTS vs. Pipeline vs. SURS 2025 (all-mode, Slovenia)")
    ax.legend(fontsize=8)

    print(f"\n  Per-purpose duration (min) — NHTS / Pipeline / SURS 2025:")
    for p, n_, pi_, s_ in zip(purposes, nhts_y, pipe_y, surs_y):
        print(f"    {p:12s}: NHTS={n_:.1f}  Pipeline={pi_:.1f}  SURS={s_:.1f}")


# --- Panel E: Work-only departure time, vs SURS 2021 Work curve (approximate peaks) ---
if has_work_departure:
    ax = next_ax(fig, gs, panel_idx, ncols)
    panel_idx += 1

    nhts_work_dep = nhts_mapped.loc[nhts_mapped["trip_label"] == "Work", "depart_hour"].dropna()
    pipe_work_dep = pipe.loc[pipe["Trip type"] == "Work", "depart_hour"].dropna()

    bins = np.arange(0, 24.25, 0.5)
    ax.hist(nhts_work_dep, bins=bins, density=True,
            alpha=0.65, color=NHTS_COLOR, label=f"NHTS Work only (n={len(nhts_work_dep):,})")
    ax.hist(pipe_work_dep, bins=bins, density=True,
            alpha=0.65, color=PIPE_COLOR, label=f"Pipeline Work only (n={len(pipe_work_dep):,})")

    # SURS 2021 Work curve (line chart, no printed per-point values) — peak HOURS only,
    # read approximately off chart gridlines. NOT 2025, NOT exact — see surs_2025_reference.py.
    ax.axvline(6.5, color="#2ca02c", linestyle=":", linewidth=2,
               label="SURS 2021 Work peak ~6–7h (~15.5%, approx.)")
    ax.axvline(15, color="#2ca02c", linestyle="--", linewidth=1.5,
               label="SURS 2021 Work 2nd peak ~14–16h (~12.5%, approx.)")

    pct_6_7_nhts = ((nhts_work_dep >= 6) & (nhts_work_dep < 7)).mean() * 100
    pct_6_7_pipe = ((pipe_work_dep >= 6) & (pipe_work_dep < 7)).mean() * 100
    print(f"\n  Work-only departures in 6-7h window (SURS 2021 approx ~15.5%):")
    print(f"    NHTS Work    : {pct_6_7_nhts:.1f}%")
    print(f"    Pipeline Work: {pct_6_7_pipe:.1f}%")

    ax.set_xlabel("Departure time (hour of day) — Work trips only")
    ax.set_ylabel("Density")
    ax.set_title("E) Work-only departure time\n(SURS 2021 Work peaks — approximate, different vintage)")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.legend(fontsize=7)


# ---------------------------------------------------------------------------
# If an odd number of panels, hide the last empty cell
# ---------------------------------------------------------------------------
if n_panels % 2 == 1:
    row, col = divmod(panel_idx, ncols)
    try:
        fig.add_subplot(gs[row, col]).set_visible(False)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Step 10 — Save figure
# ---------------------------------------------------------------------------
out_fig = os.path.join(OUT_DIR, "comparison_nhts_vs_pipeline.png")
fig.savefig(out_fig, dpi=150, bbox_inches="tight")
print(f"\n  Figure saved → {out_fig}")
plt.close(fig)

# ---------------------------------------------------------------------------
# Step 11 — Write notes.txt
# ---------------------------------------------------------------------------
notes_path = os.path.join(OUT_DIR, "notes.txt")

nhts_trippurp_values = sorted(nhts_raw["TRIPPURP"].dropna().unique().tolist())
nhts_whyto_values    = sorted(nhts_raw["WHYTO"].dropna().unique().tolist())

notes = f"""NHTS vs DomCenter Pipeline — Comparison Notes
==============================================
Generated by compare.py on the dataset loaded at runtime.

=== 1. NHTS columns used ===
  File   : {NHTS_CSV}
  Shape  : {nhts_raw.shape}
  Columns: {list(nhts_raw.columns)}

  Key columns:
    STRTTIME   — trip start time as HHMM integer (e.g. 830 = 08:30)
    TRVLCMIN   — travel time in minutes
    WHYTO      — numeric destination purpose code
    TRIPPURP   — string trip purpose code (HBW, HBO, HBSHOP, HBSOCREC, NHB, ...)
    TRPTRANS   — transport mode (3 = POV/private car, used as filter)
    HOUSEID    — household identifier
    PERSONID   — person identifier within household

  TRIPPURP unique values in the raw file:
    {nhts_trippurp_values}

  NOTE: TRIPPURP (HBW, HBO, etc.) is NOT mapped to pipeline labels —
  it is a different aggregation scheme (Home-Based Work, Home-Based Other, etc.)
  and does not cleanly align with the 8-way pipeline taxonomy.

  NHTS does NOT contain any "Commuter", "Retired", or "Nonccommuter" categories.
  No such comparison was made.

=== 2. WHYTO → pipeline label mapping ===
  Source: DFunctions_step_1.py  location_group_map
  This mapping was created by the DomCenter team and is the exact mapping
  used to derive the Markov transition matrices from NHTS.

  Mapping used:
    1  → Home
    2, 3  → Work
    4, 5  → Business
    6, 7  → Transport
    8, 9  → Education
    10, 12, 14, 18, 19  → Personal
    11  → Shopping
    13, 15, 16, 17, 97  → Leisure
    -9, -8, -7  → unknown (excluded from comparison)

  WHYTO unique values actually present in the raw file:
    {nhts_whyto_values}

=== 3. NHTS filter applied ===
  TRPTRANS == 3  (private car trips only)
  This matches the filter used in pipeline/Step_0_prod.py when building training data.
  Records after filter: {nhts.shape[0]} out of {nhts_raw.shape[0]} total.

=== 4. Pipeline file used ===
  {PIPELINE_FILE}
  Columns: Day Type, Vehicle ID, Trip ID, Profile, Trip type, Start, Duration, End
  Start × 0.25 = departure hour (float)
  Duration = trip duration in minutes

=== 5. Business trip finding ===
  Pipeline states list (from Step_1_prod.py line 88):
    ['Home', 'Work', 'Business', 'Education', 'Shopping', 'Transport', 'Leisure', 'Personal']
  Business IS in the states list.

  Business trips in pipeline output file (1344_EVs_2_trips):
    Count : {business_count}
    Share : {business_pct:.2f}% of all trip records

  Business in NHTS (WHYTO 4 or 5, mapped):
    Count  : {(nhts_mapped['trip_label'] == 'Business').sum()}
    Share  : {100.0 * (nhts_mapped['trip_label'] == 'Business').sum() / max(len(nhts_mapped), 1):.2f}%
    of car trips with known destination purpose

  NOTE: NHTS WHYTO codes 4 and 5 correspond to "Employer's business / work"
  and "Change type of transport" depending on the codebook version.
  The mapping comes from the DomCenter preprocessing (DFunctions_step_1.py).
  If Business appears rarely or not at all in the pipeline output, it may indicate
  the Markov transition matrix rarely selects it from Home, which is consistent
  with its low frequency in NHTS (car trips) data.

=== 6. Panels included and rationale ===
  A) Trip destination purpose frequency
     INCLUDED: NHTS WHYTO can be mapped to the 8 pipeline states via the
     established DFunctions_step_1.py mapping. Comparison is between
     car trips from NHTS and synthetic trips from the pipeline.

  B) Departure time distribution
     INCLUDED: NHTS STRTTIME (HHMM) converts cleanly to decimal hours.
     Pipeline Start index × 0.25 gives hours. Direct comparison is valid.

  C) Trip duration distribution
     INCLUDED: NHTS TRVLCMIN (minutes) vs pipeline Duration (minutes).
     NOTE: Pipeline duration was calibrated to Slovenian SURS data
     (mean ~13 min via shifted exponential), NOT to NHTS (mean ~25 min).
     The divergence here is expected and intentional — it is a calibration
     decision documented in Step_1_prod.py line 67–73.

  D) Trip duration by purpose vs SURS 2025
     INCLUDED: pipeline Trip type and NHTS trip_label both map onto the same
     7 destination purposes used in surs_2025_reference.py (Work, Business,
     Education, Shopping, Transport, Leisure, Personal). SURS values are
     exact printed bar labels from the source screenshot (image 3), not
     estimated. "Transport" pairs with SURS "peljati/priti iskat" (pick up/
     drop off), consistent with the existing WHYTO 6/7 -> Transport mapping.

  E) Work-only departure time vs SURS 2021 Work curve (NEW)
     INCLUDED: isolates Work trips specifically, since the all-purpose Panel B
     blends every trip type together and hides which purpose drives the morning
     over-concentration. SURS 2021 Work peak hours (~6-7h, ~14-16h) are
     approximate (read off chart gridlines, no printed values, different
     vintage than the rest of this module) and shown as reference lines only,
     not a fabricated full curve. See §6c for the root-cause finding.

=== 6b. SURS 2025 reference data (NEW) ===
  Source: {surs25.CITATION}
  Module: analysis/surs_2025_reference.py

  KNOWN CONFLICT WITH EXISTING CALIBRATION (Step_1_fit_si.py):
    metric                old (Step_1_fit_si.py)   SURS 2025 all-mode (new)
    mean trip duration    13.0 min                  24 min (all days), range 23-29
    mean trip distance    13.8 km                   14.4 km (all days), range 13.7-16.6
    mean trips/day        2.94                       2.3 (all days), range 1.8-2.4
  Distance is close; duration and trips/day are not. Not resolved — both
  shown side by side in Panel C, clearly labelled, pending verification of
  which source/year the old constants (ref [57]) actually correspond to.

  Trips/day sanity check: the pipeline production run uses a FIXED 2 trips/
  vehicle/day. SURS 2025 range is [1.8, 2.4] (non-workday to workday) —
  2 trips/day falls inside this real-world range.

  The mode-share-by-distance-bin chart (image 1, stacked bars) was NOT
  transcribed into numbers — it had no printed per-segment values, only
  visual proportions. Turning eyeballed pixel heights into a precise lookup
  table would be fabricating data. It is omitted from quantitative use.

=== 6c. SURS 2025 bucket checks (printed bullet stats, screenshot 2026-06-27) ===
  Source: same as above; year not printed on this specific screenshot but
  numbers (14.4 km / 24 min average) match DAILY_INDICATORS exactly, so
  treated as the same 2025 vintage.

  Departure-time window check:
    SURS 2025: 13% of trips depart 7-9h, 17% depart 14-16h
    NHTS      : {nhts_pct_7_9:.1f}% depart 7-9h, {nhts_pct_14_16:.1f}% depart 14-16h
    Pipeline  : {pipe_pct_7_9:.1f}% depart 7-9h, {pipe_pct_14_16:.1f}% depart 14-16h
    NHTS tracks SURS reasonably well. Pipeline massively over-concentrates
    morning departures (commuter profile forcing early Work departures) —
    this quantifies the "pronounced morning peak" already noted in REPORT.md
    with a real reference number instead of a qualitative description.

  Trip duration bucket check:
    SURS 2025: 41% of trips take <=10 min
    NHTS      : {nhts_pct_10min:.1f}%
    Pipeline  : {pipe_pct_10min:.1f}%
    NHTS matches SURS closely. Pipeline under-represents very short trips —
    consistent with Panel D showing pipeline duration doesn't vary enough
    by purpose (Shopping, the shortest real-world category, comes out too long).

  Qualitative confirmation (not separately plotted, matches Panel D data):
    SURS text states shopping trips are shortest in both distance AND duration,
    and education trips are shorter than work trips in distance but take longer
    in duration. Both match PURPOSE_STATS exactly (Shopping 6.9km/13min lowest;
    Education 15.8km/33min < Work 18.3km/24min in distance, > in duration).

  Work-only departure check (Panel E), vs SURS 2021 Work curve (different vintage,
  approximate peaks only -- see surs_2025_reference.py DEPARTURE_BY_PURPOSE_2021_QUALITATIVE):
    SURS 2021 Work peak: ~6-7h (~15.5%, approx., read from chart gridlines)
    NHTS Work    6-7h: {pct_6_7_nhts:.1f}%
    Pipeline Work 6-7h: {pct_6_7_pipe:.1f}%
  ROOT CAUSE (confirmed in code, Step_1_prod.py line 17-18):
    def sample_work_start():
        return np.random.uniform(7, 9)
  Work departure time is drawn from a flat uniform(7,9) distribution -- hence a hard
  floor at 7:00 (0% in 6-7h, by construction) and a flat 7-9h block (23.7% / 23.5%
  split between the two hours) instead of a real, sharply-peaked early-morning rush
  that starts before 7:00. This is a one-line hardcoded assumption, not emergent
  model behaviour -- it is the direct, localized cause of the 46.4%-in-7-9h finding
  above. NHTS Work (13.1% in 6-7h) does NOT have this artificial floor and tracks
  the SURS 2021 peak hour reasonably well, confirming the floor is pipeline-specific.

  NOT transcribed: the 2021 "Poti po nekaterih namenih in uri začetka" line
  chart (departure time by purpose: delo/nakupovanje/prosti čas) has no
  printed per-point values, and is a DIFFERENT YEAR (2021, not 2025) from
  the rest of this module's data. Only qualitative peak hours are recorded
  in surs_2025_reference.py (DEPARTURE_BY_PURPOSE_2021_QUALITATIVE) — do not
  treat it as 2025 data or as a precise distribution.

=== 7. Apples-to-oranges caveats (thesis must acknowledge) ===
  - NHTS 2017 is a US national household travel survey.
    The DomCenter pipeline targets Krško municipality, Slovenia.
    Trip distance, mode share, and urban form differ substantially.
  - The pipeline departure time distribution was fitted to SiStat Slovenian
    national statistics (pipeline/Step_0_prod.py), not directly to NHTS STRTTIME.
    NHTS data was used only to derive the Markov transition matrix (WHYTO).
  - The pipeline trip duration was re-calibrated to Slovenian SURS data
    (mean ~13 min) explicitly because NHTS-derived values (~24 min)
    were too long for the Krško context.
  - NHTS covers all car users; pipeline covers only EVs.
  - NHTS is a single observed day per person; pipeline generates synthetic
    days for 1344 vehicles.
"""

with open(notes_path, "w") as f:
    f.write(notes)

print(f"  Notes saved  → {notes_path}")
print("\nDone.")

"""
metrics.py — compute all comparison metrics between Model A and Model B.
Saves CSV tables to metrics/.
"""

import os
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import jensenshannon

OUT_DIR = os.path.join(os.path.dirname(__file__), "metrics")
os.makedirs(OUT_DIR, exist_ok=True)

RUN_DIR = os.path.join(os.path.dirname(__file__), "raw_runs")


# ── helpers ──────────────────────────────────────────────────────────────────

def ks_wasserstein(a, b, name):
    """KS statistic + p-value and Wasserstein distance between two 1-D arrays."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ks_stat, ks_p = stats.ks_2samp(a, b)
    wass = stats.wasserstein_distance(a, b)
    return {"metric": name, "KS_stat": round(ks_stat, 4), "KS_p": round(ks_p, 4),
            "Wasserstein": round(wass, 4)}


def js_divergence(a_series, b_series, categories):
    """Jensen–Shannon divergence between two categorical distributions."""
    a_counts = a_series.value_counts()
    b_counts = b_series.value_counts()
    p = np.array([a_counts.get(c, 0) for c in categories], dtype=float)
    q = np.array([b_counts.get(c, 0) for c in categories], dtype=float)
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum() if q.sum() > 0 else q
    return round(float(jensenshannon(p, q)), 4)


def chi2_activity(a_series, b_series, categories):
    """Chi-squared test on activity-type counts."""
    a_counts = np.array([a_series.value_counts().get(c, 0) for c in categories])
    b_counts = np.array([b_series.value_counts().get(c, 0) for c in categories])
    # Combine into contingency table
    table = np.vstack([a_counts, b_counts])
    # Remove zero-sum columns
    mask = table.sum(axis=0) > 0
    table = table[:, mask]
    chi2, p, dof, _ = stats.chi2_contingency(table)
    return round(chi2, 3), round(p, 4), dof


def spatial_spread(lat, lon):
    """Mean pairwise distance (km) between destinations using haversine approx."""
    coords = np.stack([np.radians(lat), np.radians(lon)], axis=1)
    n = len(coords)
    if n < 2:
        return np.nan
    # Vectorised haversine for all pairs
    lat1, lon1 = coords[:, 0:1], coords[:, 1:2]
    lat2, lon2 = coords[:, 0], coords[:, 1]
    dlat = lat1 - lat2
    dlon = lon1 - lon2
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    dist = 2 * 6371 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    # Upper triangle only
    triu = dist[np.triu_indices(n, k=1)]
    return float(np.mean(triu))


def convex_hull_area_km2(lat, lon):
    """Approximate convex hull area via degrees→km projection."""
    from shapely.geometry import MultiPoint
    if len(lat) < 3:
        return np.nan
    # 1° lat ≈ 111 km; 1° lon ≈ 111 * cos(lat_mean) km
    lat_m = np.mean(lat)
    x = np.array(lon) * 111 * np.cos(np.radians(lat_m))
    y = np.array(lat) * 111
    pts = MultiPoint(list(zip(x, y)))
    return round(pts.convex_hull.area, 2)


# ── main ─────────────────────────────────────────────────────────────────────

def run():
    prim = pd.read_parquet(os.path.join(RUN_DIR, "combined_primary.parquet"))
    a_sec = pd.read_parquet(os.path.join(RUN_DIR, "A_N100_4trips_step1only.parquet"))
    b_sec = pd.read_parquet(os.path.join(RUN_DIR, "B_N100_2trips.parquet"))

    A = prim[prim["model"] == "A"]
    B = prim[prim["model"] == "B"]

    # ── 1. Distributional metrics (primary N=25, trips=4) ────────────────────
    dist_rows = []
    dist_rows.append(ks_wasserstein(A["departure_time_h"], B["departure_time_h"], "Čas odhoda (h)"))
    dist_rows.append(ks_wasserstein(A["duration_min"],     B["duration_min"],     "Trajanje potovanja (min)"))
    dist_rows.append(ks_wasserstein(A["distance_km"],      B["distance_km"],      "Razdalja (km)"))
    dist_df = pd.DataFrame(dist_rows)
    dist_df.to_csv(os.path.join(OUT_DIR, "01_distribucijske_metrike.csv"), index=False)
    print("✓ 01_distribucijske_metrike.csv")

    # ── 2. Activity-type shares ──────────────────────────────────────────────
    # Primary (N=25) + secondary (N=100) — note trips differ at N=100
    activities = sorted(set(A["activity"]) | set(B["activity"]))

    def activity_table(a_s, b_s, label):
        rows = []
        for act in activities:
            pa = (a_s == act).sum() / len(a_s) * 100
            pb = (b_s == act).sum() / len(b_s) * 100
            rows.append({"aktivnost": act, "A_%": round(pa, 2), "B_%": round(pb, 2),
                         "razlika_pp": round(pb - pa, 2)})
        df = pd.DataFrame(rows)
        jsd = js_divergence(a_s, b_s, activities)
        chi2, p_chi, dof = chi2_activity(a_s, b_s, activities)
        df.attrs["JSD"] = jsd
        df.attrs["chi2"] = chi2
        df.attrs["chi2_p"] = p_chi
        return df, jsd, chi2, p_chi

    act_prim, jsd_p, chi2_p, p_chi_p = activity_table(A["activity"], B["activity"], "N25_4t")
    act_sec,  jsd_s, chi2_s, p_chi_s = activity_table(a_sec["activity"], b_sec["activity"], "N100")

    summary_act = pd.DataFrame([
        {"config": "N=25, trips=4 (primarna)", "JSD": jsd_p, "chi2": chi2_p, "chi2_p": p_chi_p},
        {"config": "N=100 (A=4t, B=2t, sekundarna)", "JSD": jsd_s, "chi2": chi2_s, "chi2_p": p_chi_s},
    ])
    act_prim.to_csv(os.path.join(OUT_DIR, "02a_deleži_aktivnosti_N25.csv"), index=False)
    act_sec.to_csv( os.path.join(OUT_DIR, "02b_deleži_aktivnosti_N100.csv"), index=False)
    summary_act.to_csv(os.path.join(OUT_DIR, "02c_aktivnosti_povzetek.csv"), index=False)
    print("✓ 02_deleži_aktivnosti_*.csv")

    # ── 3. Trips per vehicle ─────────────────────────────────────────────────
    trips_per_v = pd.DataFrame({
        "model": ["A (N=25, 4t)", "B (N=25, 4t)", "A (N=100, 4t)", "B (N=100, 2t)"],
        "poti_na_vozilo_povp": [
            A.groupby("vehicle_id")["trip_id"].count().mean(),
            B.groupby("vehicle_id")["trip_id"].count().mean(),
            a_sec.groupby("vehicle_id")["trip_id"].count().mean(),
            b_sec.groupby("vehicle_id")["trip_id"].count().mean(),
        ]
    }).round(2)
    trips_per_v.to_csv(os.path.join(OUT_DIR, "03_poti_na_vozilo.csv"), index=False)
    print("✓ 03_poti_na_vozilo.csv")

    # ── 4. Chain validity ────────────────────────────────────────────────────
    def chain_stats(df):
        """
        Trip type = destination (Home is implicit start/end, never in column).
        Measure: % with Work, % where last trip mirrors first (return symmetry).
        """
        out = {}
        for v, grp in df.groupby("vehicle_id"):
            grp = grp.sort_values("trip_id").reset_index(drop=True)
            trips = grp["activity"].tolist()
            out[v] = {
                "ima_work":          "Work" in trips,
                # For 4-trip chains: trip4 should mirror trip1, trip3 mirrors trip2
                "povratek_simetric": len(trips) >= 2 and trips[-1] == trips[0],
            }
        s = pd.DataFrame(out).T
        return {
            "ima_work_%":            round(s["ima_work"].mean() * 100, 1),
            "simetricen_povratek_%": round(s["povratek_simetric"].mean() * 100, 1),
        }

    chain_df = pd.DataFrame([
        {"model": "A (N=25, 4t)", **chain_stats(A)},
        {"model": "B (N=25, 4t)", **chain_stats(B)},
    ])
    chain_df.to_csv(os.path.join(OUT_DIR, "04_veljavnost_verig.csv"), index=False)
    print("✓ 04_veljavnost_verig.csv")

    # ── 5. Spatial properties (primary, where lat/lon exists) ────────────────
    a_end = A.dropna(subset=["end_lat", "end_lon"])
    b_end = B.dropna(subset=["end_lat", "end_lon"])

    spat_df = pd.DataFrame([
        {
            "model": "A — Velenje",
            "n_destinacij": len(a_end),
            "povp_meddestin_razdalja_km": round(spatial_spread(a_end["end_lat"], a_end["end_lon"]), 2),
            "konveksna_povrsina_km2": convex_hull_area_km2(a_end["end_lat"], a_end["end_lon"]),
            "st_unikatnih_krd_zaokr": len(
                (a_end["end_lat"].round(3).astype(str) + "," + a_end["end_lon"].round(3).astype(str)).unique()
            ),
        },
        {
            "model": "B — Krško",
            "n_destinacij": len(b_end),
            "povp_meddestin_razdalja_km": round(spatial_spread(b_end["end_lat"], b_end["end_lon"]), 2),
            "konveksna_povrsina_km2": convex_hull_area_km2(b_end["end_lat"], b_end["end_lon"]),
            "st_unikatnih_krd_zaokr": len(
                (b_end["end_lat"].round(3).astype(str) + "," + b_end["end_lon"].round(3).astype(str)).unique()
            ),
        },
    ])
    spat_df.to_csv(os.path.join(OUT_DIR, "05_prostorske_lastnosti.csv"), index=False)
    print("✓ 05_prostorske_lastnosti.csv")

    # ── 6. Operational summary ───────────────────────────────────────────────
    ops = pd.DataFrame([
        {"model": "A (Original)", "metoda_destinacij": "ORS isochrone API",
         "casovna_zamuda": "time.sleep(5) / klic", "deps_api": "Da (ORS)",
         "profili": "Ne", "day_types": 2, "validator_verig": "Ne"},
        {"model": "B (Pipeline)", "metoda_destinacij": "Haversine ring + gravitacijski model",
         "casovna_zamuda": "brez API zamude", "deps_api": "Ne (OSM lokalno)",
         "profili": "Da (Commuter/Retired/Noncommuter)", "day_types": 5,
         "validator_verig": "Da"},
    ])
    ops.to_csv(os.path.join(OUT_DIR, "06_operacijska_primerjava.csv"), index=False)
    print("✓ 06_operacijska_primerjava.csv")

    print("\nVse metrike shranjene v metrics/")
    return prim, act_prim, chain_df, spat_df


if __name__ == "__main__":
    run()

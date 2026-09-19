"""Agregacija prožnosti flote po času in prostoru (dve meji).

Ne spreminja Step_4_prod.py. Bere že izračunane datoteke:
  03_Vehicle_parameters/03_Vehicle_location_*.xlsx        stanje vozila (0 vožnja, 1 dom, 2 delo, 3 drugo)
  03_Vehicle_parameters/03_Vehicle_trip_parameters_*.xlsx  koordinate konca posamezne poti
  04_SoC_flexibility/04_SoC_flex_timeseries_*.xlsx|csv.gz  Pos/Neg_flex_kWh na vozilo in interval

Meji (odločitev: možnost C):
  zgornja meja = vsa parkirana vozila (stanja 1, 2, 3)  -> polnilnica povsod
  spodnja meja = samo vozila na delovnem mestu (stanje 2) -> polnilnica le na delu
Vozila v vožnji (stanje 0) se ne štejejo nikamor.

Prostorska razdelitev:
  (a) mreža 0,5 km, enaka ločljivost kot Step_4_analysis.py
  (b) tipi rabe prostora iz OSM (../data/osm/krsko_*.geojson) in oznake stavb
      iz istega predpomnjenega OSM nabora, kot ga uporablja Step 2

Zagon iz mape pipeline:  python3 flex_aggregation.py . ../data/osm

Izhod v 05_Flexibility/:
  flex_timeline_<scenarij>.csv     obe meji za celotno floto po intervalih
  flex_by_landuse_<scenarij>.csv   obe meji po tipu rabe prostora in intervalu
  flex_by_cell_<scenarij>.csv      zgornja meja po celici mreže in intervalu
  flex_summary.xlsx                povzetek vseh scenarijev
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

INTERVALS = 96
GRID_SIZE_KM = 0.5
# Izhodišče mreže: jugozahodni rob območja občine (celotni obseg podatkov, ne
# le ožje mestno jedro kot v Step_4_analysis.py).
GRID_LAT0, GRID_LON0 = 45.82, 15.34
KM_PER_DEG_LAT = 111.0

PARKED_STATES = (1, 2, 3)
WORK_STATE = 2

LANDUSE_FILES = {
    "stanovanjsko": "krsko_residential.geojson",
    "industrijsko": "krsko_industrial.geojson",
    "poslovno": "krsko_commercial.geojson",
    "izobrazevalno": "krsko_education.geojson",
    "zelene_povrsine": "krsko_parks.geojson",
}
NO_DATA = "brez_podatka"
UNTAGGED_BUILDING = "stavba_brez_oznake"

# Razvrstitev stavb iz istega OSM nabora, kot ga uporablja Step 2. Poligoni
# stavb so manjši od poligonov rabe prostora, zato pri prekrivanju obveljajo.
BUILDING_RULES = {
    "stanovanjsko": {"house", "residential", "apartments", "detached",
                     "semidetached_house", "terrace", "bungalow", "dormitory"},
    "industrijsko": {"industrial", "warehouse", "factory", "manufacture"},
    "poslovno": {"commercial", "retail", "office", "supermarket", "hotel"},
    "izobrazevalno": {"school", "university", "college", "kindergarten"},
}
AMENITY_RULES = {
    "izobrazevalno": {"school", "college", "university", "kindergarten", "music_school"},
    "poslovno": {"bank", "pharmacy", "post_office", "marketplace"},
}

SCENARIOS = [
    ("06_13pct", 824, 2, 206, 4),
    ("10pct", 1344, 2, 336, 4),
    ("20pct", 2688, 2, 672, 4),
    ("50pct", 6721, 2, 1680, 4),
    ("100pct", 13442, 2, 3361, 4),
]


# ---------------------------------------------------------------- vhod

def _timeseries(base: str, n: int, t: int) -> pd.DataFrame:
    stem = f"04_SoC_flexibility/04_SoC_flex_timeseries_{n}_EVs_{t}_trips_1_days"
    for ext, reader in ((".xlsx", pd.read_excel), (".csv.gz", pd.read_csv), (".csv", pd.read_csv)):
        p = os.path.join(base, stem + ext)
        if os.path.exists(p):
            return reader(p)
    raise FileNotFoundError(stem)


def _flex_matrices(ts: pd.DataFrame, n: int) -> tuple[np.ndarray, np.ndarray]:
    """(96, n) matriki Pos in Neg prožnosti."""
    pos = ts.pivot(index="TimeStep", columns="Vehicle ID", values="Pos_flex_kWh")
    neg = ts.pivot(index="TimeStep", columns="Vehicle ID", values="Neg_flex_kWh")
    pos = pos.reindex(index=range(INTERVALS), columns=range(1, n + 1))
    neg = neg.reindex(index=range(INTERVALS), columns=range(1, n + 1))
    return pos.to_numpy(float), neg.to_numpy(float)


def _positions(trips: pd.DataFrame, n: int) -> tuple[np.ndarray, np.ndarray]:
    """(96, n) matriki lat in lon: kje vozilo stoji v posameznem intervalu.

    Vozilo je do konca prve poti doma (izhodišče prve poti), potem pa na cilju
    zadnje poti, ki se je končala do vključno tega intervala.
    """
    lat = np.full((INTERVALS, n), np.nan)
    lon = np.full((INTERVALS, n), np.nan)
    steps = np.arange(INTERVALS)
    for vid, vt in trips.groupby("Vehicle ID", sort=False):
        if not 1 <= int(vid) <= n:
            continue
        vt = vt.sort_values("Trip ID")
        ends = vt["End"].to_numpy(int)
        idx = np.searchsorted(ends, steps, side="right") - 1
        end_lat = vt["End_lat"].to_numpy(float)
        end_lon = vt["End_lon"].to_numpy(float)
        home_lat = float(vt["Start_lat"].iloc[0])
        home_lon = float(vt["Start_lon"].iloc[0])
        col = int(vid) - 1
        lat[:, col] = np.where(idx >= 0, end_lat[np.clip(idx, 0, None)], home_lat)
        lon[:, col] = np.where(idx >= 0, end_lon[np.clip(idx, 0, None)], home_lon)
    return lat, lon


# ---------------------------------------------------------------- prostor

def grid_cell(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    km_per_deg_lon = KM_PER_DEG_LAT * np.cos(np.radians(GRID_LAT0))
    row = np.floor((lat - GRID_LAT0) * KM_PER_DEG_LAT / GRID_SIZE_KM)
    col = np.floor((lon - GRID_LON0) * km_per_deg_lon / GRID_SIZE_KM)
    return row.astype(int), col.astype(int)


def cell_centre(row: int, col: int) -> tuple[float, float]:
    km_per_deg_lon = KM_PER_DEG_LAT * np.cos(np.radians(GRID_LAT0))
    return (GRID_LAT0 + (row + 0.5) * GRID_SIZE_KM / KM_PER_DEG_LAT,
            GRID_LON0 + (col + 0.5) * GRID_SIZE_KM / km_per_deg_lon)


def load_buildings() -> gpd.GeoDataFrame | None:
    """Stavbe iz predpomnjenega OSM nabora, razvrščene po namembnosti."""
    try:
        from spatial_config import get_krsko_landuse
        gdf = get_krsko_landuse()
    except Exception as e:
        print(f"OSM stavbe niso na voljo: {e}")
        return None
    gdf = gdf[gdf.geometry.notna()].copy()
    kat = pd.Series(NO_DATA, index=gdf.index, dtype=object)
    if "building" in gdf.columns:
        b = gdf["building"].astype("string")
        for label, vals in BUILDING_RULES.items():
            kat[b.isin(vals)] = label
        kat[(kat == NO_DATA) & b.notna()] = UNTAGGED_BUILDING
    if "amenity" in gdf.columns:
        a = gdf["amenity"].astype("string")
        for label, vals in AMENITY_RULES.items():
            kat[a.isin(vals)] = label
    if "shop" in gdf.columns:
        kat[gdf["shop"].notna()] = "poslovno"
    gdf["kategorija"] = kat
    gdf = gdf[gdf["kategorija"] != NO_DATA]
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    return gpd.GeoDataFrame(gdf[["geometry", "kategorija"]], geometry="geometry", crs=gdf.crs)


def load_landuse(osm_dir: str) -> gpd.GeoDataFrame | None:
    frames = []
    for label, fname in LANDUSE_FILES.items():
        p = os.path.join(osm_dir, fname)
        if not os.path.exists(p):
            continue
        g = gpd.read_file(p)[["geometry"]].copy()
        g = g[g.geometry.notna() & g.geometry.is_valid]
        g["kategorija"] = label
        frames.append(g)
    if not frames:
        return None
    b = load_buildings()
    if b is not None:
        frames.append(b.to_crs("EPSG:4326"))
    g = pd.concat(frames, ignore_index=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs="EPSG:4326")
    # Pri prekrivanju obvelja manjši (bolj specifičen) poligon.
    g["povrsina"] = g.to_crs(3857).geometry.area
    return g.sort_values("povrsina")


def landuse_of(points: pd.DataFrame, landuse: gpd.GeoDataFrame | None) -> np.ndarray:
    if landuse is None:
        return np.full(len(points), NO_DATA, dtype=object)
    pts = gpd.GeoDataFrame(
        points.reset_index(drop=True),
        geometry=[Point(xy) for xy in zip(points["lon"], points["lat"])],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(pts, landuse[["geometry", "kategorija", "povrsina"]],
                       how="left", predicate="within")
    joined = joined.sort_values("povrsina").groupby(level=0).first()
    return joined["kategorija"].fillna(NO_DATA).to_numpy()


# ---------------------------------------------------------------- agregacija

def aggregate_file(base: str, n: int, t: int, landuse) -> dict:
    loc = pd.read_excel(
        os.path.join(base, f"03_Vehicle_parameters/03_Vehicle_location_{n}_EVs_{t}_trips_1_days.xlsx")
    ).to_numpy(int)[:INTERVALS, :n]
    trips = pd.read_excel(
        os.path.join(base, f"03_Vehicle_parameters/03_Vehicle_trip_parameters_{n}_EVs_{t}_trips_1_days.xlsx")
    )
    pos, neg = _flex_matrices(_timeseries(base, n, t), n)
    lat, lon = _positions(trips, n)

    parked = np.isin(loc, PARKED_STATES)
    at_work = loc == WORK_STATE

    # Cone: vsako vozilo ima čez dan le nekaj različnih lokacij, zato jih
    # razvrstimo enkrat na unikatno koordinato.
    flat = pd.DataFrame({"lat": lat.ravel(), "lon": lon.ravel()})
    uniq = flat.drop_duplicates().dropna().reset_index(drop=True)
    uniq["kategorija"] = landuse_of(uniq[["lat", "lon"]], landuse)
    r, c = grid_cell(uniq["lat"].to_numpy(), uniq["lon"].to_numpy())
    uniq["celica"] = [f"{a}_{b}" for a, b in zip(r, c)]
    key = {(round(a, 6), round(b, 6)): (k, cc)
           for a, b, k, cc in zip(uniq["lat"], uniq["lon"], uniq["kategorija"], uniq["celica"])}

    codes = {k: i for i, k in enumerate(uniq["kategorija"].unique())}
    uniq["kat_code"] = uniq["kategorija"].map(codes)
    cells = {c: i for i, c in enumerate(uniq["celica"].unique())}
    uniq["cel_code"] = uniq["celica"].map(cells)
    keys = pd.MultiIndex.from_arrays([uniq["lat"].round(6), uniq["lon"].round(6)])
    lookup_kat = pd.Series(uniq["kat_code"].to_numpy(), index=keys)
    lookup_cel = pd.Series(uniq["cel_code"].to_numpy(), index=keys)
    flat_keys = pd.MultiIndex.from_arrays([np.round(lat.ravel(), 6), np.round(lon.ravel(), 6)])
    kat_code = lookup_kat.reindex(flat_keys).to_numpy().reshape(lat.shape)
    cel_code = lookup_cel.reindex(flat_keys).to_numpy().reshape(lat.shape)
    inv_kat = {v: k for k, v in codes.items()}
    inv_cel = {v: k for k, v in cells.items()}
    kat_osm = np.vectorize(lambda c: inv_kat.get(c, NO_DATA))(kat_code).astype(object)
    cel = np.vectorize(lambda c: inv_cel.get(c, ""))(cel_code)

    # Namen parkiranja iz stanja vozila je zanesljivejši od oznake stavbe:
    # stanje 1 = doma (stanovanjsko), stanje 2 = delovno mesto, stanje 3 = drugo.
    kat = kat_osm.astype(object).copy()
    kat[loc == 1] = "stanovanjsko"
    work_ok = np.isin(kat_osm, ["industrijsko", "poslovno", "izobrazevalno"])
    kat[(loc == 2) & ~work_ok] = "delovno_neopredeljeno"
    other_unknown = np.isin(kat_osm, [UNTAGGED_BUILDING, NO_DATA])
    kat[(loc == 3) & other_unknown] = "drugo_neopredeljeno"

    return {
        "pos": pos, "neg": neg, "parked": parked, "work": at_work,
        "kat": kat, "kat_osm": kat_osm, "cel": cel,
    }


def scenario_frames(parts: list[dict], label: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    steps = np.arange(INTERVALS)
    times = [f"{s // 4:02d}:{15 * (s % 4):02d}" for s in steps]

    tl = {"TimeStep": steps, "Cas": times}
    for name, mask_key in (("zgornja", "parked"), ("spodnja", "work")):
        pos_sum = np.zeros(INTERVALS)
        neg_sum = np.zeros(INTERVALS)
        cnt = np.zeros(INTERVALS, int)
        for p in parts:
            m = p[mask_key]
            pos_sum += np.where(m, np.nan_to_num(p["pos"]), 0).sum(axis=1)
            neg_sum += np.where(m, np.nan_to_num(p["neg"]), 0).sum(axis=1)
            cnt += m.sum(axis=1)
        tl[f"pos_flex_kWh_{name}"] = pos_sum.round(1)
        tl[f"neg_flex_kWh_{name}"] = neg_sum.round(1)
        tl[f"parkirana_vozila_{name}"] = cnt
    timeline = pd.DataFrame(tl)
    timeline.insert(0, "scenarij", label)

    rows_k, rows_c = [], []
    for p in parts:
        for i in range(INTERVALS):
            df = pd.DataFrame({
                "kategorija": p["kat"][i], "celica": p["cel"][i],
                "pos": np.nan_to_num(p["pos"][i]), "neg": np.nan_to_num(p["neg"][i]),
                "parked": p["parked"][i], "work": p["work"][i],
            })
            df = df[df["parked"]]
            if df.empty:
                continue
            gk = df.groupby("kategorija").agg(
                pos_zgornja=("pos", "sum"), neg_zgornja=("neg", "sum"), vozila_zgornja=("pos", "size"),
            )
            gw = df[df["work"]].groupby("kategorija").agg(
                pos_spodnja=("pos", "sum"), neg_spodnja=("neg", "sum"), vozila_spodnja=("pos", "size"),
            )
            gk = gk.join(gw, how="left").fillna(0).reset_index()
            gk["TimeStep"] = i
            rows_k.append(gk)

            gc = df.groupby("celica").agg(
                pos_zgornja=("pos", "sum"), neg_zgornja=("neg", "sum"), vozila_zgornja=("pos", "size"),
            ).reset_index()
            gc["TimeStep"] = i
            rows_c.append(gc)

    by_kat = (pd.concat(rows_k).groupby(["TimeStep", "kategorija"], as_index=False).sum())
    by_cel = (pd.concat(rows_c).groupby(["TimeStep", "celica"], as_index=False).sum())
    for d in (by_kat, by_cel):
        d.insert(0, "scenarij", label)
        d["Cas"] = [f"{s // 4:02d}:{15 * (s % 4):02d}" for s in d["TimeStep"]]
    by_cel = by_cel[by_cel["celica"] != ""].copy()
    centres = {c: cell_centre(int(c.split("_")[0]), int(c.split("_")[1])) for c in by_cel["celica"].unique()}
    by_cel["sredisce_lat"] = [round(centres[c][0], 5) for c in by_cel["celica"]]
    by_cel["sredisce_lon"] = [round(centres[c][1], 5) for c in by_cel["celica"]]
    return timeline, by_kat, by_cel


def main(base: str = ".", osm_dir: str = os.path.join("..", "data", "osm"), out_dir: str = "05_Flexibility"):
    os.makedirs(os.path.join(base, out_dir), exist_ok=True)
    landuse = load_landuse(osm_dir)
    print("Sloji rabe prostora:", "ni podatkov" if landuse is None
          else landuse["kategorija"].value_counts().to_dict())

    summary = []
    for label, n2, t2, n4, t4 in SCENARIOS:
        parts = []
        for n, t in ((n2, t2), (n4, t4)):
            print(f"  {label}: {n}x{t}T ...", flush=True)
            parts.append(aggregate_file(base, n, t, landuse))
        timeline, by_kat, by_cel = scenario_frames(parts, label)
        timeline.to_csv(os.path.join(base, out_dir, f"flex_timeline_{label}.csv"), index=False)
        by_kat.to_csv(os.path.join(base, out_dir, f"flex_by_landuse_{label}.csv"), index=False)
        by_cel.to_csv(os.path.join(base, out_dir, f"flex_by_cell_{label}.csv"), index=False)

        evs = n2 + n4
        peak = timeline.loc[timeline["pos_flex_kWh_zgornja"].idxmax()]
        low = timeline.loc[timeline["pos_flex_kWh_zgornja"].idxmin()]
        summary.append({
            "scenarij": label, "vozila": evs,
            "pos_zgornja_max_kWh": peak["pos_flex_kWh_zgornja"], "ob_uri_max": peak["Cas"],
            "pos_zgornja_min_kWh": low["pos_flex_kWh_zgornja"], "ob_uri_min": low["Cas"],
            "pos_zgornja_povp_kWh": round(timeline["pos_flex_kWh_zgornja"].mean(), 1),
            "pos_spodnja_max_kWh": timeline["pos_flex_kWh_spodnja"].max(),
            "pos_spodnja_povp_kWh": round(timeline["pos_flex_kWh_spodnja"].mean(), 1),
            "povp_parkiranih_zgornja": round(timeline["parkirana_vozila_zgornja"].mean(), 1),
            "povp_parkiranih_spodnja": round(timeline["parkirana_vozila_spodnja"].mean(), 1),
            "delez_parkiranih_povp": round(timeline["parkirana_vozila_zgornja"].mean() / evs, 3),
            "pos_zgornja_max_na_vozilo_kWh": round(peak["pos_flex_kWh_zgornja"] / evs, 2),
        })
        print(pd.DataFrame(summary[-1:]).to_string(index=False))

    df = pd.DataFrame(summary)
    df.to_excel(os.path.join(base, out_dir, "flex_summary.xlsx"), index=False)
    print("\n", df.to_string(index=False))


if __name__ == "__main__":
    import sys
    main(*(sys.argv[1:] or []))

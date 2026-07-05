"""
Kalibracija parametra beta gravitacijskega modela (sample_destination) na
SURS referenčno povprečno razdaljo poti v Sloveniji (13.8 km).

Zakaj je potrebna kalibracija:
  beta=2 (Newtonov gravitacijski zakon) je bil doslej arbitrarna privzeta
  vrednost, brez preverjanja na slovenskih statistikah. Ta skripta jo
  empirično umeri na realnih podatkih, ne na sintetičnih igračkah.

Metodologija (vse na REALNIH podatkih, brez API klicev med kalibracijo):
  1. Izvori: naključno vzorčeni centroidi DEJANSKIH stanovanjskih stavb
     (OSM Krško, prek poi_home_search — enaka funkcija, ki jo uporablja
     produkcijski pipeline Step_2a_prod.py).
  2. Cilji: dejanski POI (Business/Education/Shopping/Transport/Leisure/
     Personal) z maso = ploščina stavbe v m² — enaka logika kot v
     haversine_ring_filter/ors_isochrone_filter.
  3. Trajanje poti: vzorčeno iz SI-kalibrirane eksponentne porazdelitve
     (loc=5, scale=8 min — glej Step_1_fit_si.py).
  4. Dosegljivost: namesto živih ORS klicev (počasno, omejena kvota)
     uporabimo LOKALNO cestno mrežo Krško (cache/krsko_drive.graphml) in
     Dijkstro po travel_time, da repliciramo anularno okno
     [floor(duration), ceil(duration)] min — IDENTIČNO oknu, ki ga
     ors_isochrone_filter dobi iz get_isochrone() (glej Functions_step_2.py
     get_isochrone: lower=floor(duration)*60, upper=ceil(duration)*60).
  5. Razdalja vsakega izbranega cilja = Dijkstra po length (m) po isti
     cestni mreži — dejanska cestna razdalja, ne zračna črta.
  6. Za vsako beta iz mreže vrednosti pokličemo obstoječi
     sample_destination(origin, candidates, beta) in zberemo razdalje.

Opomba o omejitvi: tip poti za vsak poskus je vzorčen UNIFORMNO med 6 tipi,
ki gredo skozi gravitacijski model (Work ima vnaprej določeno lokacijo,
Home je fiksen). Dejanska frekvenca tipov izhaja iz Markovske verige in ni
konstantna — a beta nadzoruje razdaljni razpad znotraj VSAKEGA posameznega
nabora kandidatov, kar je v grobem neodvisno od mešanice tipov.
"""

import os
import time

import numpy as np
import networkx as nx
import osmnx as ox

from Functions_step_2 import init, poi_home_search, sample_destination

np.random.seed(42)

SURS_TARGET_KM   = 13.8
N_ORIGINS        = 40
N_TRIALS_PER_BETA = 400
BETA_GRID        = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

DUR_LOC, DUR_SCALE = 5.0, 24.5   # SI-kalibrirano (popravljeno), Step_1_fit_si.py — mean=23.0 min po odsekanju

GRAVITY_TYPES = ["Business", "Education", "Shopping", "Transport", "Leisure", "Personal"]


def _load_graph():
    graph_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "krsko_drive.graphml")
    print(f"Nalagam cestno mrežo: {graph_path}")
    G = ox.load_graphml(graph_path)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    print(f"  {len(G.nodes)} vozlišč, {len(G.edges)} povezav")
    return G


def _prep_candidates(gdf):
    """Realni kandidati: WGS84 koordinate centroida + masa (ploščina v m², EPSG:3857)."""
    if gdf.empty:
        return []
    gdf_m = gdf.to_crs(epsg=3857)
    out = []
    for (idx, row), (_, row_m) in zip(gdf.iterrows(), gdf_m.iterrows()):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom.centroid if geom.geom_type != "Point" else geom
        geom_m = row_m.geometry
        mass = float(geom_m.area) if geom_m.geom_type in ("Polygon", "MultiPolygon") else 100.0
        out.append({"lat": point.y, "lon": point.x, "mass": mass})
    return out


def main():
    t_start = time.time()

    G = _load_graph()

    print("\nNalagam realne POI podatke (Krško, OSM)...")
    data_work, data_business, data_education, data_shopping, data_leisure, data_building = init()
    type_map = {
        "Business":  data_business, "Education": data_education,
        "Shopping":  data_shopping, "Leisure":    data_leisure,
        "Personal":  data_building, "Transport":  data_building,
    }
    candidates_by_type = {t: _prep_candidates(gdf) for t, gdf in type_map.items()}
    for t, c in candidates_by_type.items():
        print(f"  {t:10s}: {len(c):5d} kandidatov")

    print("\nIščem najbližja vozlišča za vse kandidate...")
    for t, cands in candidates_by_type.items():
        if not cands:
            continue
        xs = [c["lon"] for c in cands]
        ys = [c["lat"] for c in cands]
        nodes = ox.nearest_nodes(G, X=xs, Y=ys)
        nodes = list(nodes) if hasattr(nodes, "__iter__") else [nodes]
        for c, n in zip(cands, nodes):
            c["node"] = n

    print(f"\nVzorčim {N_ORIGINS} realnih stanovanjskih izvorov...")
    homes_gdf = poi_home_search("building")
    if len(homes_gdf) < N_ORIGINS:
        raise RuntimeError(f"Premalo stanovanjskih stavb ({len(homes_gdf)}) za {N_ORIGINS} izvorov.")
    origin_rows = np.random.choice(len(homes_gdf), size=N_ORIGINS, replace=False)
    origins = [(homes_gdf.iloc[i].geometry.y, homes_gdf.iloc[i].geometry.x) for i in origin_rows]

    print(f"Računam Dijkstra dosegljivost za {N_ORIGINS} izvorov (travel_time + length)...")
    origin_tables = []
    for (lat, lon) in origins:
        try:
            onode = ox.nearest_nodes(G, X=lon, Y=lat)
            time_lengths = nx.single_source_dijkstra_path_length(G, onode, weight="travel_time")
            dist_lengths = nx.single_source_dijkstra_path_length(G, onode, weight="length")
            origin_tables.append((time_lengths, dist_lengths))
        except Exception as e:
            print(f"  Izvor ({lat:.4f},{lon:.4f}) ni dosegljiv v mreži: {e}")
            origin_tables.append(None)

    rng = np.random.default_rng(42)

    # Identično vzorčenje kot Step_1_prod.py: diskretizirana porazdelitev na
    # [0,60] min / 1000 točk, NE kontinuirana exponentna s clip-om (clip dvigne
    # povprečje na ~26,9 min namesto pravih 23,0 min — preverjeno).
    _dur_x = np.linspace(0, 60, 1000)
    _dur_d = (1 / DUR_SCALE) * np.exp(-(_dur_x - DUR_LOC) / DUR_SCALE)
    _dur_d[_dur_x < DUR_LOC] = 0
    _dur_d = _dur_d / _dur_d.sum()

    def sample_trial():
        """Vrne (origin, reachable_candidates) ali None."""
        oi = rng.integers(N_ORIGINS)
        table = origin_tables[oi]
        if table is None:
            return None
        time_lengths, dist_lengths = table

        duration = float(rng.choice(_dur_x, p=_dur_d))
        # Identično oknu iz get_isochrone(): [floor(duration), ceil(duration)] min
        lo_s = np.floor(duration) * 60.0
        hi_s = np.ceil(duration) * 60.0

        ttype = GRAVITY_TYPES[rng.integers(len(GRAVITY_TYPES))]
        cands = candidates_by_type[ttype]
        if not cands:
            return None

        reachable = []
        for c in cands:
            t_s = time_lengths.get(c["node"])
            if t_s is None or not (lo_s <= t_s <= hi_s):
                continue
            d_m = dist_lengths.get(c["node"])
            if d_m is None:
                continue
            reachable.append({
                "coords": (c["lat"], c["lon"]),
                "mass": c["mass"],
                "_real_dist_km": d_m / 1000.0,
            })
        if not reachable:
            return None
        return origins[oi], reachable

    print(f"\nZaganjam {N_TRIALS_PER_BETA} poskusov za vsako od {len(BETA_GRID)} beta vrednosti...")
    results = {}
    for beta in BETA_GRID:
        dists = []
        attempts = 0
        while len(dists) < N_TRIALS_PER_BETA and attempts < N_TRIALS_PER_BETA * 8:
            attempts += 1
            trial = sample_trial()
            if trial is None:
                continue
            origin, reachable = trial
            chosen = sample_destination(origin, reachable, beta=beta)
            dists.append(chosen["_real_dist_km"])
        results[beta] = np.array(dists)
        status = f"mean={np.mean(dists):.2f} km" if dists else "NI VZORCEV"
        print(f"  beta={beta:4.1f}  N={len(dists):4d} (poskusov: {attempts:5d})  {status}")

    elapsed = time.time() - t_start

    print("\n" + "=" * 64)
    print("KALIBRACIJA BETA — REZULTATI")
    print("=" * 64)
    print(f"{'beta':>6s} {'N':>6s} {'mean [km]':>10s} {'median [km]':>12s} {'std [km]':>10s} {'|Δ SURS|':>10s}")

    best_beta, best_diff = None, np.inf
    for beta, d in results.items():
        if len(d) == 0:
            continue
        mean_d = float(np.mean(d))
        med_d  = float(np.median(d))
        std_d  = float(np.std(d))
        diff   = abs(mean_d - SURS_TARGET_KM)
        print(f"{beta:6.1f} {len(d):6d} {mean_d:10.2f} {med_d:12.2f} {std_d:10.2f} {diff:10.2f}")
        if diff < best_diff:
            best_diff = diff
            best_beta = beta

    print(f"\nSURS referenca (povprečna razdalja poti): {SURS_TARGET_KM} km")
    print(f"Skupni čas kalibracije: {elapsed:.1f} s")

    if best_beta is not None:
        print(f"\n>>> Priporočena vrednost: beta = {best_beta}  (|razlika od SURS| = {best_diff:.2f} km) <<<")

        # Validacijski ponovni zagon s priporočeno beta vrednostjo
        print(f"\nValidacija beta={best_beta} (nov seed=123, N={N_TRIALS_PER_BETA*2})...")
        rng2 = np.random.default_rng(123)
        val_dists = []
        attempts = 0
        N_VAL = N_TRIALS_PER_BETA * 2
        while len(val_dists) < N_VAL and attempts < N_VAL * 8:
            attempts += 1
            oi = rng2.integers(N_ORIGINS)
            table = origin_tables[oi]
            if table is None:
                continue
            time_lengths, dist_lengths = table
            duration = float(rng2.choice(_dur_x, p=_dur_d))
            lo_s, hi_s = np.floor(duration) * 60.0, np.ceil(duration) * 60.0
            ttype = GRAVITY_TYPES[rng2.integers(len(GRAVITY_TYPES))]
            cands = candidates_by_type[ttype]
            if not cands:
                continue
            reachable = [
                {"coords": (c["lat"], c["lon"]), "mass": c["mass"],
                 "_real_dist_km": dist_lengths[c["node"]] / 1000.0}
                for c in cands
                if c["node"] in time_lengths and lo_s <= time_lengths[c["node"]] <= hi_s
                and c["node"] in dist_lengths
            ]
            if not reachable:
                continue
            chosen = sample_destination(origins[oi], reachable, beta=best_beta)
            val_dists.append(chosen["_real_dist_km"])

        val_dists = np.array(val_dists)
        print(f"  N={len(val_dists)}  mean={np.mean(val_dists):.2f} km  "
              f"median={np.median(val_dists):.2f} km  std={np.std(val_dists):.2f} km")
        print(f"  SURS cilj: {SURS_TARGET_KM} km  |  razlika: {abs(np.mean(val_dists)-SURS_TARGET_KM):.2f} km")

    print("=" * 64)


if __name__ == "__main__":
    main()

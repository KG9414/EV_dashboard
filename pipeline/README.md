# DomCenter — V2G Mobility Visualiser

A lightweight Streamlit dashboard that animates electric vehicle movements,
workplace parking energy demand, and arrival/departure flows for a Slovenian
municipality (Krško). Built as a master's thesis demo on Vehicle-to-Grid
(V2G) flexibility.

The full simulation pipeline (NHTS data → user profiles → trip chains →
routing → SoC + flexibility) lives in `pipeline/` and is **research-only**.
The deployed app reads pre-baked scenario files; it does **not** call
OpenStreetMap, OpenRouteService, or Overpass at runtime.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Open http://localhost:8501 and pick a scenario from the sidebar.

## Project layout

```
app/                  # Streamlit visualiser (the deployable part)
  streamlit_app.py    # entry point
  data_loader.py      # cached scenario + OSM loaders
  simulation.py       # position / energy / arrival math
  charts.py           # Plotly map + line figures

data/
  scenarios/          # pre-baked vehicle-trip xlsx files (shipped with repo)
  osm/                # optional GeoJSON / JSON cache (built locally)

scripts/              # one-shot helpers run locally
  build_osm_cache.py  # snapshot OSM landuse + clusters into data/osm/
  explore_osm_tags.py # dump every OSM tag for Krško for analysis

pipeline/             # research code — not used by the deployed app
  Step_0_prod.py ... Step_4_prod.py
  Functions_step_*.py
  krsko_osm_clusters.py
  Dom_center_legacy.py     # original matplotlib version, kept for reference
  ...
```

## Adding a new scenario

1. Run the pipeline locally to generate
   `03_Vehicle_trip_parameters_<N>_EVs_<T>_trips_<D>_days.xlsx`.
2. Copy it into `data/scenarios/` with a clean name, e.g.
   `scenario_50_EVs_3_trips.xlsx`.
3. Add a human-readable label in `app/data_loader.py` → `SCENARIO_LABELS`.
4. Restart Streamlit. The new button appears in the sidebar.

## (Re)building the OSM cluster cache

Only needed if you want the landuse overlay or the cluster markers on the
map. Requires `osmnx` + `geopandas` (see `requirements-dev.txt`).

```bash
pip install -r requirements-dev.txt
python scripts/explore_osm_tags.py   # exports tag dump for analysis
python scripts/build_osm_cache.py    # produces data/osm/*.geojson + *.json
```

## Running the research pipeline

The pipeline's routing/isochrone calls (`pipeline/Functions_step_2.py`) need an
OpenRouteService API key — get a free one at
[openrouteservice.org](https://openrouteservice.org/dev/#/signup), then:

```bash
export ORS_API_KEY=<your_key>
```

See `.env.example`. The key is never hardcoded in source — importing the
module without `ORS_API_KEY` set raises immediately.

## Deploying

Push the repo to GitHub, then connect it on
[share.streamlit.io](https://share.streamlit.io). The free tier is enough
for the 4–25 EV demo scenarios. No Docker, no extra infrastructure.

## Thesis context

V2G (Vehicle-to-Grid) describes a future grid where parked EVs feed energy
back into the local network during peaks. This visualiser shows the two
quantities that drive V2G feasibility: where the cars actually are (heatmap)
and how much energy is sitting in workplace parking lots (line chart).
The underlying methodology — NHTS sampling, gravity-model destination
choice, OpenRouteService routing, and SoC-flexibility — is documented in
the corresponding thesis.

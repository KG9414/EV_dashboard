# EV_dashboard

Merged project for the Krško EV / V2G master's thesis. It brings the two
previously separate folders into one:

```
EV_dashboard/
├── pipeline/        ← copy of DomCenter (trip-generation & simulation pipeline)
└── visualization/   ← copy of Krsko_EV_model_commuting/Streamlit (the dashboard)
```

The pipeline **produces** the trip / SoC data (the `04_SoC_flex_*.xlsx` files);
the visualization **reads** those files and shows the interactive map, charts and
V2G analysis.

## What was and wasn't copied

- Copied: all pipeline code, input data, scenarios, analysis and docs; the full
  visualization app (code, `data/`, `components/`, `assets/`).
- **Excluded** (regenerable / environment-specific): `venv/`, `.venv/`, `.git/`,
  `__pycache__/`, `.DS_Store`, and the pipeline's `cache/`.
- **Kept on purpose:** `visualization/cache/` (~100 MB of cached OpenStreetMap
  responses). It lets the map load Krško's OSM zones without an internet round
  trip on first run. Safe to delete if you don't mind the app re-fetching OSM.

Because the two source folders shared many filenames (`Step_1_prod.py`,
`data/`, `cache/`, …), they are kept in separate subfolders rather than flattened
together, so nothing overwrites anything.

## Running the visualization (the dashboard)

```bash
cd visualization
python3 -m venv .venv && source .venv/bin/activate      # or use your own env
pip install streamlit pydeck osmnx geopandas shapely matplotlib plotly pandas numpy openpyxl
streamlit run app.py
```

Notes:
- First launch fetches Krško OSM data via `osmnx` (needs internet) unless the
  bundled `cache/` is present — which it is.
- The scenario data it reads lives in `visualization/data/` (`04_SoC_flex_*.xlsx`).

## Running the pipeline

The pipeline keeps its own documentation and requirements:

- `pipeline/README.md` — overview and usage.
- `pipeline/requirements.txt` / `pipeline/requirements-dev.txt` — dependencies.
- `pipeline/CLAUDE.md`, `pipeline/NACRT_PISANJA.md`, `pipeline/docs/` — project
  notes and equations.

Typical flow (see `pipeline/README.md` for specifics): run the numbered
`Step_*` / `pipeline/` scripts to generate trip parameters → trips → vehicle SoC
& flexibility, then copy/point the resulting `04_SoC_flex_*.xlsx` outputs into
`visualization/data/` to view them in the dashboard.

## Regenerating an environment

Each part was copied without its virtual environment. Create a fresh venv per
part (or one shared env) and install from `pipeline/requirements.txt` plus the
visualization dependencies listed above.

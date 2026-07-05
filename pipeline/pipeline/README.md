# pipeline/ — research scripts

These are the original step-by-step scripts that built the scenario files.
They are kept for reproducibility but are **not** used by the deployed
Streamlit app.

```
Step_0_prod.py            NHTS CSV → fitted profile distributions
Step_1_prod.py            distributions → 01_Trips_parameters_*.xlsx
Step_2_prod.py            trip chains → 02_Trips_*.xlsx (uses ORS + Overpass)
Step_3_prod.py            merge → 03_Vehicle_trip_parameters_*.xlsx
Step_4_prod.py            SoC + V2G flexibility → 04_SoC_flexibility/*.xlsx
Functions_step_*.py       helpers used by the steps above
krsko_osm_clusters.py     OSM landuse + cluster extraction for Krško
Dom_center_legacy.py      previous matplotlib visualiser (replaced by app/)
```

Run order: 0 → 1 → 2 → 3 → 4. Each step writes xlsx artefacts which the
next step reads. Most steps are imperative top-level scripts (no `main`
function); run them with `python pipeline/Step_X_prod.py`.

External APIs touched: Overpass (OSM), OpenRouteService. You will need
internet access and, for ORS, an API key.

When you produce a new fleet/trip variant you actually want to demo,
copy the resulting `03_Vehicle_trip_parameters_*.xlsx` into
`data/scenarios/` and add a label in `app/data_loader.py`.

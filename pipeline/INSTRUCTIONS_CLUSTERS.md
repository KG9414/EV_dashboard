# Cluster / Zone Unification — Implementation Instructions

## Context

This repository simulates EV trip chains for Krško, Slovenia. Spatial
logic is currently fragmented across four files with three parallel
representations of "Krško" and two unrelated centroid systems. Your job
is to consolidate this into a single source of truth and make every
spatial decision in the pipeline derive from that source.

Files in scope:
- `pipeline/Functions_step_2.py`
- `pipeline/Step_2_prod.py`
- `pipeline/krsko_osm_clusters.py`
- `pipeline/Functions_step_1.py`
- `pipeline/Dom_center_legacy.py` (read-only — do not modify behaviour,
  but update imports if required)

Constraints:
- Do not change the public signatures of `get_trip_parameters`,
  `sample_destination`, `next_state`, or `poi_search_filter`. Internal
  refactors are fine.
- The pipeline runs end-to-end as `Step_0 → Step_1 → Step_2 → Step_3`.
  After your changes, that chain must still produce
  `03_Vehicle_trip_parameters_*.xlsx` with the same column schema.
- Keep all hardcoded `ORS_API_KEY` strings out of source. Move them to
  an `.env`-style loader (use `os.environ.get("ORS_API_KEY")`). If the
  variable is unset, raise a clear `RuntimeError` at module import.

---

## Task 1 — Create a single spatial configuration module

Create `pipeline/spatial_config.py` containing:

1. `KRSKO_OVERPASS_AREA_ID = 3601685729` (constant).
2. `KRSKO_OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"`
   (constant).
3. A cached function `get_krsko_boundary() -> shapely.geometry.Polygon`
   that fetches the municipality boundary from Overpass once per
   process and returns the polygon in EPSG:4326. Cache via
   `functools.lru_cache`.
4. A cached function `get_krsko_landuse(tags: dict | None = None) ->
   geopandas.GeoDataFrame` that wraps `osmnx.features_from_place` with
   default `tags = {"landuse": True, "leisure": True, "amenity": True,
   "building": True, "shop": True}`. **Note the inclusion of
   `building`** — this is required for downstream tasks.
5. A constant `STATE_TO_LANDUSE_RULE` that maps each of the 9 trip
   states (`Home, Work, Business, Education, Shopping, Transport,
   Leisure, Personal, unknown`) to a tuple `(column_name,
   set_of_allowed_values)`. Use the same rules as the current
   `Functions_step_2.init()` Overpass queries (Work →
   `building ∈ {office, commercial, industrial, retail, warehouse}`
   etc.). For `unknown` use `("building", {"yes"})`.

### Acceptance criteria

- `python -c "from pipeline.spatial_config import get_krsko_boundary,
  get_krsko_landuse; b = get_krsko_boundary(); g = get_krsko_landuse();
  print(b.area, len(g))"` runs without error and prints two positive
  numbers.
- No other module in `pipeline/` imports `osmnx` or calls Overpass
  directly any more after Task 4 is done.

---

## Task 2 — Derive cluster centroids from OSM, not hand-pin

In `pipeline/Functions_step_1.py` replace the hand-pinned `centroids`
dict (lines 21–31 currently) with a function that derives one
representative point per state from the OSM landuse data fetched via
`spatial_config.get_krsko_landuse`.

Algorithm:
- For each state `s`, take the rows of the landuse GeoDataFrame that
  match `STATE_TO_LANDUSE_RULE[s]`.
- Reproject the matching rows to EPSG:3857 (metric).
- Compute one centroid as `unary_union(filtered.geometry).centroid`.
- Reproject the resulting point back to EPSG:4326 and store as
  `(lon, lat)`.
- Cache the resulting dict (`functools.lru_cache` on a private helper).

The `masses` dict (lines 33–44) should also be derived: each state's
mass is the **sum of building footprint areas (in m²)** for that
state's filtered features, scaled so that the maximum mass is 5000
(preserving the current Home mass for backward compatibility with the
`α=0.3` blend). If a state has no features (e.g. `Transport`), fall
back to `mass = 500`.

Do not change the gravity blend (`ALPHA = 0.3`, `MIN_DIST_KM = 0.1`)
nor the `next_state` signature.

### Acceptance criteria

- `python -c "from pipeline.Functions_step_1 import centroids, masses;
  print(centroids); print(masses)"` prints two dicts whose keys are
  exactly the 9 state names.
- Each centroid is within the Krško boundary polygon returned by
  `get_krsko_boundary()`. Verify with:
```python
  from shapely.geometry import Point
  from pipeline.spatial_config import get_krsko_boundary
  from pipeline.Functions_step_1 import centroids
  b = get_krsko_boundary()
  for s, (lon, lat) in centroids.items():
      assert b.contains(Point(lon, lat)), f"{s} centroid outside Krško"
```
- The maximum value in `masses` equals 5000 (within ±1 for rounding).
- The unit test `pipeline/test_user_profiles.py` still passes if it
  currently passes.

---

## Task 3 — Fix the 10 km home radius bug (× 111 issue)

In `pipeline/Step_2_prod.py` lines 74–87:

Current code computes `distance_km = geometry.distance(point) * 111`.
This is wrong: in EPSG:4326 `geometry.distance` returns degrees, and
the 111 km/° factor is only correct for latitudinal distance. At
Krško's latitude (~45.96°) one longitudinal degree is ~77.4 km, so the
"10 km disc" is currently an ellipse stretched east-west by ~30%.

Replace with a proper great-circle filter:

```python
from pipeline.Functions_step_2 import haversine
center_lon, center_lat = 15.4917, 45.9591  # remove these after Task 4

residential_objects_no_limit["distance_km"] = residential_objects_no_limit.geometry.apply(
    lambda geom: haversine(geom.x, geom.y, center_lon, center_lat)
)
```

Also expose `MAX_HOME_RADIUS_KM` as a module-level constant at the top
of `Step_2_prod.py`, defaulted to `10.0`, so it can be overridden
without editing function bodies.

### Acceptance criteria

- After re-running Step_2 with N=10 vehicles, every home in
  `02_Trips_*_ROS.shp` is within 10 km haversine distance from
  `(15.4917, 45.9591)`. Verify with:
```python
  import geopandas as gpd
  from pipeline.Functions_step_2 import haversine
  homes = gpd.read_file("pipeline/02_Trips/02_Trips_10_EVs_2_trips_1_days_ROS.shp")
  for _, row in homes.iterrows():
      d = haversine(row.geometry.x, row.geometry.y, 15.4917, 45.9591)
      assert d <= 10.0, f"home at {row.geometry} is {d:.2f} km out"
```
- The number of candidate residential objects returned by
  `poi_home_search` after the radius clip should DECREASE compared to
  before the fix (because the ellipse used to be larger E-W). Print
  before/after counts.

---

## Task 4 — Replace Overpass calls in Functions_step_2 with spatial_config

In `pipeline/Functions_step_2.py`:

1. Delete the module-level `area = 'Velenje'` block (lines 26–28).
   Delete the second `area = 'Krško'` block (lines 40–42). Both are
   dead/redundant after Task 1.
2. Rewrite `poi_home_search` to consume `spatial_config.get_krsko_landuse()`
   filtered by `building` in the residential value set. Do not call
   Overpass directly any more.
3. Rewrite `init(area_id)` so each of the six purpose queries reads
   from `spatial_config.get_krsko_landuse()` filtered via
   `STATE_TO_LANDUSE_RULE`. Keep the return signature
   `(data_work, data_business, data_education, data_shopping,
    data_leisure, data_building)` for backward compatibility, but the
   contents should now be `geopandas.GeoDataFrame` slices rather than
   raw Overpass dicts.
4. In `poi_search_filter` adapt the consumer code: the iteration
   `for element in data['elements']` becomes `for _, row in data.iterrows()`,
   and `tags.get('name', 'Unknown')` becomes `row.get('name', 'Unknown')`.
5. Remove the `fetch_overpass` helper — nothing should call it any more.

### Acceptance criteria

- `grep -n "overpass.kumi.systems" pipeline/` returns only matches in
  `spatial_config.py`.
- `grep -n "requests.get" pipeline/Functions_step_2.py` returns only
  matches for `get_isochrone` and `route_parameters` (ORS), not Overpass.
- Step 2 end-to-end still produces a valid `02_Trips_*.xlsx`.

---

## Task 5 — Replace constant mass per category with footprint-derived mass

In `pipeline/Functions_step_2.py` `poi_search_filter` (currently lines
1045–1054):

Replace the `mass_dict` constant lookup with per-feature footprint
mass. Each candidate destination's mass should be the **area of its
building footprint in m²** (compute from the polygon in EPSG:3857
before reducing to centroid). For point-only OSM features (nodes),
fall back to the median footprint mass of polygon features in the
same category. Store the mass on the feature dict as `'mass'` exactly
as today, so `sample_destination` does not need changes.

### Acceptance criteria

- `sample_destination` still receives a `mass` key on every candidate.
- For the Krško industrial cluster (large polygons), masses are now
  much larger than for individual retail shops (small polygons). Print
  the top 10 and bottom 10 masses for `WORK` category and confirm a
  spread of at least 100×.
- The existing gravity-validation tests at the end of `Step_2_prod.py`
  (TEST 1, TEST 2, TEST 3) must still pass.

---

## Task 6 — Add building layer to the legacy visualizer

In `pipeline/Dom_center_legacy.py` lines 248–275:

Currently only landuse polygons are coloured. Buildings outside any
landuse polygon stay white. Fix this without changing the existing
landuse palette.

1. Fetch `buildings = get_krsko_landuse({"building": True}).to_crs(3857)`.
2. Spatial-join buildings to landuse zones:
```python
   import geopandas as gpd
   joined = gpd.sjoin(buildings, landuse_gdf_3857[["geometry", "landuse",
       "leisure", "amenity"]], how="left", predicate="within")
```
3. For each building, derive a `color` column by applying the same
   rule set as the existing `style` dict in
   `krsko_osm_clusters.plot_landuse_layers`. Buildings that match no
   rule get the colour `"#bdbdbd"` (neutral grey) and the label
   `"unzoned"`.
4. Plot buildings on `ax` AFTER the landuse polygons but BEFORE the
   vehicle scatter. Use `alpha=0.6` and `linewidth=0`.
5. Extend the legend with `mpatches.Patch(color="#bdbdbd",
    label="unzoned building")`.

### Acceptance criteria

- Visually inspect the rendered map. Every OSM building in Krško is
  drawn in exactly one colour. No building remains white.
- Density of "unzoned" (grey) buildings is highest at the village
  fringes (Senovo, Leskovec, Stara vas), lowest in the Krško town
  centre.
- The animation and heatmap still update correctly when running
  `python pipeline/Dom_center_legacy.py`.

---

## Verification — full pipeline smoke test

After all six tasks, run:

```bash
cd pipeline
echo "10
2
1" | python Step_1_prod.py
echo "10
2
1
No
Yes" | python Step_2_prod.py
echo "10
2
1" | python Step_3_prod.py
```

Then confirm:
1. `03_Vehicle_trip_parameters_10_EVs_2_trips_1_days.xlsx` exists and
   has the same columns as before (`Vehicle ID, Trip ID, Day Type,
   Profile, Initial_SoC, Trip type, Start, End, Duration, Energy_kWh,
   Start_lat, Start_lon, End_lat, End_lon`).
2. The gravity-validation TEST 1/2/3 inside Step_2_prod still print
   PASSED.
3. `Dom_center_legacy.py` opens and renders buildings in colour.

---

## Out of scope — do NOT do in this pass

- Do not touch the user profile mix (60/25/15) or `UserProfile`
  classes. They are tracked in a separate work stream.
- Do not change the temporal resolution (15 min) or the NHTS-derived
  `trips_probability`.
- Do not implement dynamic SoC or charging-opportunity metrics. Those
  belong to a separate "Sklop B" track.
- Do not delete `Dom_center_legacy.py`. The Streamlit `app/` referenced
  in README does not exist yet.

When all six tasks pass their acceptance criteria, write a one-paragraph
PR description summarising the cluster unification and link to the
specific lines that previously held hand-pin centroids and the × 111
bug.
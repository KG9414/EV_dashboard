import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import math
import json
import time
import folium
import requests
from shapely.geometry import shape, Point, Polygon
from scipy.spatial import cKDTree
import networkx as nx
import osmnx as ox

sys.path.insert(0, os.path.dirname(__file__))
from spatial_config import get_krsko_landuse, STATE_TO_LANDUSE_RULE

_KRSKO_GRAPH = None
_route_cache = {}

_ORS_API_KEY = os.environ.get("ORS_API_KEY")
if _ORS_API_KEY is None:
    raise RuntimeError(
        "ORS_API_KEY environment variable is not set. "
        "Export it before importing Functions_step_2 (e.g. export ORS_API_KEY=<your_key>)."
    )


def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance between two points in km."""
    dlon = np.radians(lon2 - lon1)
    dlat = np.radians(lat2 - lat1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371  # Radius of earth in km
    return c * r


def id_of_area(municipality):
    """Return the Overpass area ID for a known municipality (reads from spatial_config)."""
    from spatial_config import KRSKO_OVERPASS_AREA_ID
    known = {"Krško": KRSKO_OVERPASS_AREA_ID}
    if municipality in known:
        return known[municipality]
    raise ValueError(f"Unknown municipality {municipality!r}. Add it to spatial_config.")

def poi_home_search(key=None, elements=None):
    """Return residential building candidates from the cached OSM dataset."""
    col, allowed = STATE_TO_LANDUSE_RULE["Home"]
    gdf = get_krsko_landuse()
    if col not in gdf.columns or allowed is None:
        subset = gdf.iloc[0:0].copy()
    else:
        subset = gdf[gdf[col].isin(allowed)].copy()

    data_list = []
    for _, row in subset.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom.centroid if geom.geom_type != "Point" else geom
        name_val = row.get("name", "Unknown")
        name = name_val if pd.notna(name_val) else "Unknown"
        data_list.append({"name": f"Home: {name}", "geometry": point})

    return gpd.GeoDataFrame(data_list, geometry="geometry", crs="EPSG:4326")

# def poi_search_filter(key, elements=None, ring_zone):
#     url = "http://overpass-api.de/api/interpreter"
#     if elements:
#         query = f"""
#             [out:json][timeout:25];
#             area({area_id})->.searchArea;
#             (
#             nwr['{key}'='{elements}'](area.searchArea);
#             );
#             out geom;
#             """
#     else:
#         query = f"""
#                 [out:json][timeout:25];
#                 area({area_id})->.searchArea;
#                 (
#                 nwr['{key}'](area.searchArea);
#                 );
#                 out geom;
#                 """
#
#     response = requests.get(url, params={'data': query})
#     data = response.json()
#     # DODATI DEL, KAJ SE ZGODI ČE NI POI, POKLIČEŠ education pa nič ne dobiš in ti javi error
#     data_list = []
#     for element in data['elements']:
#         geometry = None
#         tags = element.get('tags', {})
#
#         if 'lat' in element and 'lon' in element:
#             geometry = Point(element['lon'], element['lat'])
#         elif 'geometry' in element and len(element['geometry']) > 0:
#             try:
#                 polygon = Polygon([(point['lon'], point['lat']) for point in element['geometry']])
#                 geometry = polygon.centroid
#             except Exception as e:
#                 print(f'Neuspešno kreiran poligon za objekt: {tags.get('name', 'Nepoznato')}\n{e}')
#
#         if geometry:
#             data_list.append({'name': tags.get('name', 'Nepoznato'), 'geometry': geometry})
#
#     df_data = pd.DataFrame(data_list)
#     gdf_data = gpd.GeoDataFrame(data_list, geometry='geometry', crs='EPSG:4326')
#
#     if gdf_data.empty:
#         print('all_destination is empty!') i vrati se na pocetak
#     else:
#         filter = gdf_data[gdf_data.geometry.apply(lambda x: ring_zone.contains(x))]
#         if filter.empty:
#             print('filter is empty!') i vrati se na pocetak
#     return filter

def init(area_id=None):
    """Return GeoDataFrame slices for each trip purpose from the cached OSM dataset.

    area_id is accepted for backward compatibility but ignored — data is read
    from spatial_config.get_krsko_landuse() which already targets Krško.
    """
    gdf = get_krsko_landuse()

    def _filter(col, allowed):
        if col not in gdf.columns:
            return gdf.iloc[0:0].copy()
        if allowed is None:
            return gdf[gdf[col].notna()].copy()
        return gdf[gdf[col].isin(allowed)].copy()

    data_work = _filter(*STATE_TO_LANDUSE_RULE["Work"])
    data_business = _filter(*STATE_TO_LANDUSE_RULE["Business"])
    data_education = _filter(*STATE_TO_LANDUSE_RULE["Education"])
    data_shopping = _filter(*STATE_TO_LANDUSE_RULE["Shopping"])
    data_leisure = _filter(*STATE_TO_LANDUSE_RULE["Leisure"])
    if "building" in gdf.columns:
        data_building = gdf[gdf["building"].notna()].copy()
    else:
        data_building = gdf.iloc[0:0].copy()

    return data_work, data_business, data_education, data_shopping, data_leisure, data_building

# def init(area_id):
#
#     url = "http://overpass-api.de/api/interpreter"
#     work_query = f"""
#     [out:json][timeout:60];
#     area({area_id})->.searchArea;
#     (
#       nwr["office"](area.searchArea);
#       nwr["building"~"office|commercial|industrial|retail|warehouse"](area.searchArea);
#       nwr["shop"](area.searchArea);
#       nwr["craft"](area.searchArea);
#       nwr["amenity"="bank"](area.searchArea);
#       nwr["amenity"="marketplace"](area.searchArea);
#     );
#     out geom;
#     """
#     while True:
#         work_response = requests.get(url, params={'data': work_query})
#
#         # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#         if work_response.status_code in (504, 429):
#             print(f"Response {work_response.status_code}, retrying in 10 seconds...")
#             time.sleep(10)
#             continue
#
#         # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#         if work_response.status_code != 200:
#             print(f"Greška: Server je vratio status {work_response.status_code}. Odgovor: {work_response.text}")
#             time.sleep(10)
#             continue
#
#         # Pokušavamo da parsiramo JSON odgovor
#         try:
#             data_work = work_response.json()
#             break  # Ako uspe, izlazimo iz petlje
#         except Exception as e:
#             print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#             print("Odgovor servera:", work_response.text)
#             time.sleep(10)
#             continue
#     # work_response = requests.get(url, params={'data': work_query})
#
#     business_query = f"""
#     [out:json][timeout:60];
#     area({area_id})->.searchArea;
#     (
#       nwr["office"](area.searchArea);
#       nwr["building"~"office|commercial|industrial|retail"](area.searchArea);
#       nwr["shop"](area.searchArea);
#       nwr["amenity"="bank"](area.searchArea);
#       nwr["amenity"="marketplace"](area.searchArea);
#     );
#     out geom;
#     """
#     while True:
#         business_response = requests.get(url, params={'data': business_query})
#
#         # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#         if business_response.status_code in (504, 429):
#             print(f"Response {business_response.status_code}, retrying in 10 seconds...")
#             time.sleep(10)
#             continue
#
#         # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#         if business_response.status_code != 200:
#             print(f"Greška: Server je vratio status {business_response.status_code}. Odgovor: {business_response.text}")
#             time.sleep(10)
#             continue
#
#         # Pokušavamo da parsiramo JSON odgovor
#         try:
#             data_business = business_response.json()
#             break  # Ako uspe, izlazimo iz petlje
#         except Exception as e:
#             print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#             print("Odgovor servera:", business_response.text)
#             time.sleep(10)
#             continue
#     # business_response = requests.get(url, params={'data': business_query})
#
#     education_query = f"""
#     [out:json][timeout:60];
#     area({area_id})->.searchArea;
#     (
#       nwr["amenity"~"school|college|university|music_school|kindergarten"](area.searchArea);
#       nwr["office"="educational_institution"](area.searchArea);
#       nwr["building"="school"](area.searchArea);
#     );
#     out geom;
#     """
#     while True:
#         education_response = requests.get(url, params={'data': education_query})
#
#         # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#         if education_response.status_code in (504, 429):
#             print(f"Response {education_response.status_code}, retrying in 10 seconds...")
#             time.sleep(10)
#             continue
#
#         # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#         if education_response.status_code != 200:
#             print(f"Greška: Server je vratio status {education_response.status_code}. Odgovor: {education_response.text}")
#             time.sleep(10)
#             continue
#
#         # Pokušavamo da parsiramo JSON odgovor
#         try:
#             data_education = education_response.json()
#             break  # Ako uspe, izlazimo iz petlje
#         except Exception as e:
#             print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#             print("Odgovor servera:", education_response.text)
#             time.sleep(10)
#             continue
#     # education_response = requests.get(url, params={'data': education_query})
#
#     shopping_query = f"""
#     [out:json][timeout:60];
#     area({area_id})->.searchArea;
#     (
#       nwr["shop"](area.searchArea);
#       nwr["building"~"retail|commercial"](area.searchArea);
#       nwr["amenity"~"marketplace|mall|supermarket|department_store|convenience"](area.searchArea);
#     );
#     out geom;
#     """
#     while True:
#         shopping_response = requests.get(url, params={'data': shopping_query})
#
#         # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#         if shopping_response.status_code in (504, 429):
#             print(f"Response {shopping_response.status_code}, retrying in 10 seconds...")
#             time.sleep(10)
#             continue
#
#         # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#         if shopping_response.status_code != 200:
#             print(f"Greška: Server je vratio status {shopping_response.status_code}. Odgovor: {shopping_response.text}")
#             time.sleep(10)
#             continue
#
#         # Pokušavamo da parsiramo JSON odgovor
#         try:
#             data_shopping = shopping_response.json()
#             break  # Ako uspe, izlazimo iz petlje
#         except Exception as e:
#             print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#             print("Odgovor servera:", shopping_response.text)
#             time.sleep(10)
#             continue
#     # shopping_response = requests.get(url, params={'data': shopping_query})
#
#     leisure_query = f"""
#     [out:json][timeout:60];
#     area({area_id})->.searchArea;
#     (
#       nwr["leisure"](area.searchArea);
#     );
#     out geom;
#     """
#     while True:
#         leisure_response = requests.get(url, params={'data': leisure_query})
#
#         # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#         if leisure_response.status_code in (504, 429):
#             print(f"Response {leisure_response.status_code}, retrying in 10 seconds...")
#             time.sleep(10)
#             continue
#
#         # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#         if leisure_response.status_code != 200:
#             print(f"Greška: Server je vratio status {leisure_response.status_code}. Odgovor: {leisure_response.text}")
#             time.sleep(10)
#             continue
#
#         # Pokušavamo da parsiramo JSON odgovor
#         try:
#             data_leisure = leisure_response.json()
#             break  # Ako uspe, izlazimo iz petlje
#         except Exception as e:
#             print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#             print("Odgovor servera:", leisure_response.text)
#             time.sleep(10)
#             continue
#     # leisure_response = requests.get(url, params={'data': leisure_query})
#
#     building_query = f"""
#     [out:json][timeout:60];
#     area({area_id})->.searchArea;
#     (
#       nwr["building"](area.searchArea);
#     );
#     out geom;
#     """
#
#     while True:
#         building_response = requests.get(url, params={'data': building_query})
#
#         # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#         if building_response.status_code in (504, 429):
#             print(f"Response {building_response.status_code}, retrying in 10 seconds...")
#             time.sleep(10)
#             continue
#
#         # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#         if building_response.status_code != 200:
#             print(f"Greška: Server je vratio status {building_response.status_code}. Odgovor: {building_response.text}")
#             time.sleep(10)
#             continue
#
#         # Pokušavamo da parsiramo JSON odgovor
#         try:
#             data_building = building_response.json()
#             break  # Ako uspe, izlazimo iz petlje
#         except Exception as e:
#             print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#             print("Odgovor servera:", building_response.text)
#             time.sleep(10)
#             continue
#     # building_response = requests.get(url, params={'data': building_query})
#     return data_work, data_business, data_education, data_shopping, data_leisure, data_building

def get_isochrone_window(lower_min, upper_min, longitude, latitude):
    """Fetch ORS isochrone annular zone for an explicit [lower_min, upper_min] window (minutes).

    Used by ors_isochrone_filter to progressively widen the search window when the
    floor/ceil annular ring contains no candidates, instead of jumping straight to
    the full 0..upper isochrone (which floods the pool with very-close candidates).
    """
    lower_time = max(0, lower_min)*60
    upper_time = upper_min*60
    url = 'https://api.openrouteservice.org/v2/isochrones/driving-car'
    body = {
        'locations': [[longitude, latitude]],
        'range': [lower_time, upper_time]
    }
    header = {'Authorization': _ORS_API_KEY, 'Content-Type': 'application/json'}

    while True:
        response = requests.post(url, json=body, headers=header)

        if response.status_code != 200:
            print(f"Greška: Server je vratio status {response.status_code}. Odgovor: {response.text}")
            time.sleep(10)
            continue

        try:
            data = response.json()
            break
        except Exception as e:
            print("Došlo je do greške pri parsiranju JSON odgovora:", e)
            print("Odgovor servera:", response.text)
            time.sleep(10)
            continue

    if 'features' not in data or len(data['features']) < 2:
        raise ValueError("API nije vratio očekivani broj feature-a")

    polygon_lower = shape(data['features'][0]['geometry'])
    polygon_upper = shape(data['features'][1]['geometry'])
    reachable_area = polygon_upper.difference(polygon_lower)
    return reachable_area, polygon_lower, polygon_upper


def get_isochrone(duration, longitude, latitude):
    return get_isochrone_window(math.floor(duration), math.ceil(duration), longitude, latitude)

# def filter_area(objects, ring_zone):
#     filter = objects[objects.geometry.apply(lambda x: ring_zone.contains(x))]
#     return filter


# def sample_route_calculate(reachable_destinations, start_lon, start_lat):
#     chosen_destination = reachable_destinations.sample(1).iloc[0]
#
#     dest_lat, dest_lon = chosen_destination.geometry.y, chosen_destination.geometry.x
#     ORS_API_KEY = '<REDACTED-ROTATE-IF-STILL-ACTIVE>'
#     url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
#     header = {'Authorization': ORS_API_KEY, 'Content-Type': 'application/json'}
#     route_payload ={"coordinates": [[start_lon, start_lat], [dest_lon, dest_lat]], "format": "geojson"}
#
#     route_response = requests.post(url, headers=header, json=route_payload)
#     if route_response.status_code == 200:
#         route_data = route_response.json()
#         if "features" in route_data and len(route_data["features"]) > 0:
#             route_distance = route_data["features"][0]["properties"]["segments"][0]["distance"] / 1000  # m → km
#             route_duration = route_data["features"][0]["properties"]["segments"][0]["duration"] / 60  # s → min
#
#         route_coords = route_data["features"][0]["geometry"]["coordinates"]
#
#     return chosen_destination, chosen_destination['name'], dest_lat, dest_lon, route_distance, route_duration, route_coords

def sample_destination(origin, candidate_destinations, beta=2):
    """
    Sample a destination using the gravity model: P(i->j) proportional to M_j / d(i,j)^beta

    Args:
        origin: (lat, lon) tuple
        candidate_destinations: list of dicts with 'coords': (lat, lon), 'mass': float,
                                 and any other fields (e.g. 'name', '_idx')
        beta: distance decay exponent (default 2)

    Returns:
        The sampled destination dict.

    Example (3 vehicles):
        origin = (45.959, 15.491)
        candidates = [
            {'coords': (45.960, 15.500), 'mass': 100, 'name': 'Factory A'},
            {'coords': (45.955, 15.480), 'mass': 80,  'name': 'Office B'},
            {'coords': (45.965, 15.510), 'mass': 60,  'name': 'Workshop C'},
        ]
        # Vehicle 0 (Commuter, SoC~58%):     probs approx [0.617, 0.302, 0.080]
        # Vehicle 1 (Retired, SoC~41%):      same probs, independent draw
        # Vehicle 2 (Nonccommuter, SoC~23%): same probs, independent draw
    """
    epsilon = 1e-9
    weights = []
    for dest in candidate_destinations:
        d = haversine(origin[1], origin[0], dest['coords'][1], dest['coords'][0])
        weights.append(dest['mass'] / (d + epsilon) ** beta)

    weights = np.array(weights, dtype=float)
    total = weights.sum()
    probs = weights / total if total > 0 else np.ones(len(weights)) / len(weights)

    idx = np.random.choice(len(candidate_destinations), p=probs)
    return candidate_destinations[idx]


# def route_parameters(start_lat, start_lon, end_lat, end_lon):
#     ORS_API_KEY = '<REDACTED-ROTATE-IF-STILL-ACTIVE>'
#     url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
#     header = {'Authorization': ORS_API_KEY, 'Content-Type': 'application/json'}
#     route_payload = {"coordinates": [[start_lon, start_lat], [end_lon, end_lat]], "format": "geojson"}
#
#     route_response = requests.post(url, headers=header, json=route_payload)
#     print(f'Route parameters API response: {route_response.status_code}')
#
#     if route_response.status_code == 200:
#         route_data = route_response.json()
#         if "features" in route_data and len(route_data["features"]) > 0:
#             route_distance = route_data["features"][0]["properties"]["segments"][0]["distance"] / 1000  # m → km
#             route_duration = route_data["features"][0]["properties"]["segments"][0]["duration"] / 60  # s → min
#
#         route_coords = route_data["features"][0]["geometry"]["coordinates"]
#
#     return route_distance, route_duration, route_coords

def route_parameters(start_lat, start_lon, end_lat, end_lon):
    url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
    header = {'Authorization': _ORS_API_KEY, 'Content-Type': 'application/json'}
    route_payload = {"coordinates": [[start_lon, start_lat], [end_lon, end_lat]], "format": "geojson"}

    max_attempts = 5
    attempts = 0
    while attempts < max_attempts:
        route_response = requests.post(url, headers=header, json=route_payload)
        print(f'Route parameters API response: {route_response.status_code}')
        attempts += 1

        if route_response.status_code != 200:
            print(f"Greška: API Route Server je vratio status {route_response.status_code}. Odgovor: {route_response.text}")
            time.sleep(10)
            continue

        try:
            route_data = route_response.json()
        except Exception as e:
            print("Došlo je do greške pri parsiranju JSON odgovora:", e)
            print("Odgovor servera:", route_response.text)
            time.sleep(10)
            continue

        if "features" not in route_data or len(route_data["features"]) == 0:
            print("Greška: 'features' nisu pronađene u odgovoru. Pokušavam ponovo...")
            time.sleep(10)
            continue

        try:
            route_distance = route_data["features"][0]["properties"]["segments"][0]["distance"] / 1000  # m → km
            route_duration = route_data["features"][0]["properties"]["segments"][0]["duration"] / 60  # s → min
            route_coords = route_data["features"][0]["geometry"]["coordinates"]
            time.sleep(1.5)  # ORS rate limit: ~40 req/min → 1 req/1.5s
            return route_distance, route_duration, route_coords

        except Exception as e:
            print("Greška pri izvlačenju podataka iz features:", e)
            time.sleep(10)

    print(f'Route nije moguće pronaći nakon {attempts} pokušaja')

    return 0, 0, 0


def _get_krsko_graph():
    """Load and cache the Krško road network from the local graphml file."""
    global _KRSKO_GRAPH
    if _KRSKO_GRAPH is None:
        graph_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'krsko_drive.graphml')
        G = ox.load_graphml(graph_path)
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        _KRSKO_GRAPH = G
        print(f"Road network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
    return _KRSKO_GRAPH


def route_parameters_local(start_lat, start_lon, end_lat, end_lon):
    """Compute route distance and duration using the cached OSMnx road network.

    No API calls, no rate limits. Results cached by rounded coordinates (~100 m).
    Returns (distance_km, duration_min, route_coords) or (0, 0, 0) if no path.
    """
    key = (round(start_lat, 3), round(start_lon, 3), round(end_lat, 3), round(end_lon, 3))
    if key in _route_cache:
        return _route_cache[key]

    G = _get_krsko_graph()

    try:
        orig_node = ox.nearest_nodes(G, X=start_lon, Y=start_lat)
        dest_node = ox.nearest_nodes(G, X=end_lon, Y=end_lat)

        if orig_node == dest_node:
            result = (0.1, 1.0, [[start_lon, start_lat], [end_lon, end_lat]])
            _route_cache[key] = result
            return result

        route_nodes = nx.shortest_path(G, orig_node, dest_node, weight='length')

        distance_m = sum(
            G[u][v][0].get('length', 0)
            for u, v in zip(route_nodes[:-1], route_nodes[1:])
        )
        travel_time_s = sum(
            G[u][v][0].get('travel_time', G[u][v][0].get('length', 0) / 8.33)
            for u, v in zip(route_nodes[:-1], route_nodes[1:])
        )

        distance_km = distance_m / 1000
        duration_min = travel_time_s / 60
        route_coords = [[G.nodes[n]['x'], G.nodes[n]['y']] for n in route_nodes]

        result = (distance_km, duration_min, route_coords)
        _route_cache[key] = result
        return result

    except (nx.NetworkXNoPath, nx.NodeNotFound):
        print(f"Local routing: no path ({start_lat:.4f},{start_lon:.4f}) → ({end_lat:.4f},{end_lon:.4f})")
        result = (0, 0, 0)
        _route_cache[key] = result
        return result
    except Exception as e:
        print(f"Local routing error: {e}")
        return (0, 0, 0)


def parse_coordinates(json_str):
    try:
        if isinstance(json_str, str) and json_str.strip():
            data = json.loads(json_str)
            features = data['features']
            coordinates = []
            for feature in features:
                geometry = feature['geometry']
                if geometry['type'] == 'Point':
                    coordinates.append(geometry['coordinates'])
            return coordinates if coordinates else None
        else:
            return None
    except Exception as e:
        print(f'Napaka pri parsiranju JSON-a {e}')
        return None


def process_polygon(polygon):
    """
    Ekstrahuje koordinate spoljašnjeg prstena poligona, zaokružuje ih na 3 decimale,
    uzima svaku šestu koordinatu i vraća string u formatu "lat lon" pogodan za Overpass.

    :param polygon: Shapely Polygon objekat.
    :return: String sa koordinatama.
    """
    # Ekstrahujemo spoljašnje koordinate (koordinate dolaze kao (x, y) tj. (lon, lat))
    coords = list(polygon.exterior.coords)

    # Smanjujemo preciznost na 3 decimale i preuređujemo u format (lat, lon)
    rounded_coords = [(round(y, 3), round(x, 3)) for x, y in coords]

    coords_len = len(coords)
    if coords_len < 100:
        n = 1
    else:
        n = int(np.ceil(coords_len / 100))

    # Uzimamo svaku n koordinatu
    filtered_coords = rounded_coords[::n]

    # Formatiramo u string: svaki par "lat lon" odvojen je razmakom, a koordinatni parovi mogu biti razdvojeni novim redom
    poly_string = "\n".join(f"{lat} {lon}" for lat, lon in filtered_coords)

    return poly_string


# def poi_search_filter_old(trip_type, reachable_ring_area, polygon_lower, polygon_upper):
#     url = "http://overpass-api.de/api/interpreter"
#
#     poly_upper_string = process_polygon(polygon_upper)
#     poly_lower_string = process_polygon(polygon_lower)
#
#     t = trip_type.upper()
#     print(t)
#     if t == 'WORK':
#         candidate_sets = [
#             [  # Primarni upiti
#                 'nwr["office"](area.searchArea);',
#                 'nwr["building"~"office|commercial|industrial|retail|warehouse"](area.searchArea);',
#                 'nwr["shop"](area.searchArea);',
#                 'nwr["craft"](area.searchArea);',
#                 'nwr["amenity"="bank"](area.searchArea);',
#                 'nwr["amenity"="marketplace"](area.searchArea);'
#             ],
#             [  # Sekundarni upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#     elif t == 'BUSINESS':
#         candidate_sets = [
#             [  # Primarni upiti
#                 'nwr["office"](area.searchArea);',
#                 'nwr["building"~"office|commercial|industrial|retail"](area.searchArea);',
#                 'nwr["shop"](area.searchArea);',
#                 'nwr["amenity"="bank"](area.searchArea);',
#                 'nwr["amenity"="marketplace"](area.searchArea);'
#             ],
#             [  # Sekundarni upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#     elif t == 'EDUCATION':
#         candidate_sets = [
#             [  # Primarni upiti
#                 'nwr["amenity"~"school|college|university|music_school|kindergarten"](area.searchArea);',
#                 'nwr["office"="educational_institution"](area.searchArea);',
#                 'nwr["building"="school"](area.searchArea);'
#             ],
#             [  # Sekundarni upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#     elif t == 'TRANSPORT':
#         candidate_sets = [
#             [  # Jedini upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#     elif t == 'SHOPPING':
#         candidate_sets = [
#             [  # Primarni upiti
#                 'nwr["shop"](area.searchArea);',
#                 'nwr["building"~"retail|commercial"](area.searchArea);',
#                 'nwr["amenity"~"marketplace|mall|supermarket|department_store|convenience"](area.searchArea);'
#             ],
#             [  # Sekundarni upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#     elif t == 'LEISURE':
#         candidate_sets = [
#             [  # Primarni upiti
#                 'nwr["leisure"](area.searchArea);'
#             ],
#             [  # Sekundarni upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#     elif t == 'PERSONAL':
#         candidate_sets = [
#             [  # Jedini upit
#                 'nwr["building"](area.searchArea);'
#             ]
#         ]
#
#     else:
#         raise ValueError("Nepodržani tip upita.")
#
#     # Iteriraj kroz svaki skup kandidata
#     for candidate_set in candidate_sets:
#         subquery_block = "\n".join(candidate_set)
#
#         # Sastavi konačni upit
#         query = f"""
#                 [out:json][timeout:60];
#                 area({area_id})->.searchArea;
#                 (
#                 {subquery_block}
#                 );
#                 out geom;
#             """
#         print(query)
#         # response = requests.get(url, params={'data': query})
#         # print(response)
#         # while response.status_code == 504:
#         #     print("Response 504, retrying...")
#         #     time.sleep(10)  # opcioni delay da se izbegne preopterećenje servera
#         #     response = requests.get(url, params={'data': query})
#         # data = response.json()
#         # print(data)
#
#         while True:
#             response = requests.get(url, params={'data': query})
#
#             # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#             if response.status_code in (504, 429):
#                 print(f"Response {response.status_code}, retrying in 10 seconds...")
#                 time.sleep(10)
#                 continue
#
#             # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#             if response.status_code != 200:
#                 print(f"Greška: Server je vratio status {response.status_code}. Odgovor: {response.text}")
#                 time.sleep(10)
#                 continue
#
#             # Pokušavamo da parsiramo JSON odgovor
#             try:
#                 data = response.json()
#                 break  # Ako uspe, izlazimo iz petlje
#             except Exception as e:
#                 print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#                 print("Odgovor servera:", response.text)
#                 time.sleep(10)
#                 continue
#
#         # Nakon izlaska iz petlje, 'data' sadrži validan JSON odgovor
#
#         data_list = []
#         for element in data['elements']:
#             geometry = None
#             tags = element.get('tags', {})
#
#             if 'lat' in element and 'lon' in element:
#                 geometry = Point(element['lon'], element['lat'])
#             elif 'geometry' in element and len(element['geometry']) > 0:
#                 try:
#                     polygon = Polygon([(point['lon'], point['lat']) for point in element['geometry']])
#                     geometry = polygon.centroid
#                 except Exception as e:
#                     print(f"Neuspešno kreiran poligon za objekt: {tags.get('name', 'Unknown')}\n{e}")
#
#             if geometry:
#                 data_list.append({'name': tags.get('name', 'Unknown'), 'geometry': geometry})
#
#         if not data_list:
#             print(f"No results for combination {candidate_set}, trying next combination...")
#             continue
#
#         df_data = pd.DataFrame(data_list)
#         gdf_data = gpd.GeoDataFrame(data_list, geometry='geometry', crs='EPSG:4326')
#
#         if gdf_data.empty:
#             print(f"gdf_data is empty fot combination {candidate_set}, trying next combination...")
#             continue
#
#         reachable_area = reachable_ring_area
#         gdf_data = gdf_data[gdf_data.geometry.apply(lambda x: reachable_area.contains(x))]
#         if gdf_data.empty:
#             print(f"Filter is empty fot combination {candidate_set}, trying next combination...")
#             continue
#
#         break
#
#     if gdf_data.empty:
#         print("Out of area")
#         query = f"""
#                        [out:json][timeout:60];
#                        (
#                        nwr['building'](poly: "{poly_upper_string}");
#                        ) -> .upper;
#                        (
#                        nwr['building'](poly: "{poly_lower_string}");
#                        ) -> .lower;
#                        (
#                         .upper;
#                         - .lower;
#                        );
#                        out geom;
#                    """
#         print(query)
#         # response = requests.get(url, params={'data': query})
#         # print(response)
#         # while response.status_code == 504:
#         #     print("Response 504, retrying...")
#         #     time.sleep(10)  # opcioni delay da se izbegne preopterećenje servera
#         #     response = requests.get(url, params={'data': query})
#         # data = response.json()
#         # print(data)
#
#         while True:
#             response = requests.get(url, params={'data': query})
#
#             # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#             if response.status_code in (504, 429):
#                 print(f"Response {response.status_code}, retrying in 10 seconds...")
#                 time.sleep(10)
#                 continue
#
#             # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#             if response.status_code != 200:
#                 print(f"Greška: Server je vratio status {response.status_code}. Odgovor: {response.text}")
#                 time.sleep(10)
#                 continue
#
#             # Pokušavamo da parsiramo JSON odgovor
#             try:
#                 data = response.json()
#                 break  # Ako uspe, izlazimo iz petlje
#             except Exception as e:
#                 print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#                 print("Odgovor servera:", response.text)
#                 time.sleep(10)
#                 continue
#
#         # Nakon izlaska iz petlje, 'data' sadrži validan JSON odgovor
#
#         data_list = []
#
#         if not data['elements']:
#             print("Out of area - trying to find anything in this area")
#             query = f"""
#                                    [out:json][timeout:60];
#                                    (
#                                    nwr[~".+"~".+"](poly: "{poly_upper_string}");
#                                    ) -> .upper;
#                                    (
#                                    nwr[~".+"~".+"](poly: "{poly_lower_string}");
#                                    ) -> .lower;
#                                    (
#                                     .upper;
#                                     - .lower;
#                                    );
#                                    out geom;
#                                """
#             print(query)
#             # response = requests.get(url, params={'data': query})
#             # print(response)
#             # while response.status_code == 504:
#             #     print("Response 504, retrying...")
#             #     time.sleep(10)  # opcioni delay da se izbegne preopterećenje servera
#             #     response = requests.get(url, params={'data': query})
#             # data = response.json()
#             # print(data)
#
#             while True:
#                 response = requests.get(url, params={'data': query})
#
#                 # Ako dobijemo 504 ili 429, čekamo 10 sekundi i ponovo pokušavamo
#                 if response.status_code in (504, 429):
#                     print(f"Response {response.status_code}, retrying in 10 seconds...")
#                     time.sleep(10)
#                     continue
#
#                 # Ako dobijemo neki drugi neuspešan status, ispišemo poruku i ponovo pokušavamo
#                 if response.status_code != 200:
#                     print(f"Greška: Server je vratio status {response.status_code}. Odgovor: {response.text}")
#                     time.sleep(10)
#                     continue
#
#                 # Pokušavamo da parsiramo JSON odgovor
#                 try:
#                     data = response.json()
#                     break  # Ako uspe, izlazimo iz petlje
#                 except Exception as e:
#                     print("Došlo je do greške pri parsiranju JSON odgovora:", e)
#                     print("Odgovor servera:", response.text)
#                     time.sleep(10)
#                     continue
#
#             # Nakon izlaska iz petlje, 'data' sadrži validan JSON odgovor
#
#             data_list = []
#             for element in data['elements']:
#                 geometry = None
#                 tags = element.get('tags', {})
#
#                 if 'lat' in element and 'lon' in element:
#                     geometry = Point(element['lon'], element['lat'])
#                 elif 'geometry' in element and len(element['geometry']) > 0:
#                     try:
#                         polygon = Polygon([(point['lon'], point['lat']) for point in element['geometry']])
#                         geometry = polygon.centroid
#                     except Exception as e:
#                         print(f"Neuspešno kreiran poligon za objekt: {tags.get('name', 'Unknown')}\n{e}")
#
#                 if geometry:
#                     data_list.append({'name': tags.get('name', 'Unknown'), 'geometry': geometry})
#
#             df_data = pd.DataFrame(data_list)
#             gdf_data = gpd.GeoDataFrame(data_list, geometry='geometry', crs='EPSG:4326')
#
#         else:
#             for element in data['elements']:
#                 geometry = None
#                 tags = element.get('tags', {})
#
#                 if 'lat' in element and 'lon' in element:
#                     geometry = Point(element['lon'], element['lat'])
#                 elif 'geometry' in element and len(element['geometry']) > 0:
#                     try:
#                         polygon = Polygon([(point['lon'], point['lat']) for point in element['geometry']])
#                         geometry = polygon.centroid
#                     except Exception as e:
#                         print(f"Neuspešno kreiran poligon za objekt: {tags.get('name', 'Unknown')}\n{e}")
#
#                 if geometry:
#                     data_list.append({'name': tags.get('name', 'Unknown'), 'geometry': geometry})
#
#             df_data = pd.DataFrame(data_list)
#             gdf_data = gpd.GeoDataFrame(data_list, geometry='geometry', crs='EPSG:4326')
#
#     return df_data, gdf_data


def poi_search_filter(trip_type, reachable_ring_area, polygon_lower, polygon_upper, init_data):

    data_work, data_business, data_education, data_shopping, data_leisure, data_building = init_data

    t = trip_type.upper()
    print(t)

    if t == "WORK":
        candidate_sets = [[data_work], [data_building]]
    elif t == "BUSINESS":
        candidate_sets = [[data_business], [data_building]]
    elif t == "EDUCATION":
        candidate_sets = [[data_education], [data_building]]
    elif t == "TRANSPORT":
        candidate_sets = [[data_building]]
    elif t == "SHOPPING":
        candidate_sets = [[data_shopping], [data_building]]
    elif t == "LEISURE":
        candidate_sets = [[data_leisure], [data_building]]
    elif t == "PERSONAL":
        candidate_sets = [[data_building]]
    else:
        raise ValueError("Nepodržani tip upita.")

    def _footprint_masses(gdf_slice):
        """Return {index: footprint_area_m2} using EPSG:3857 areas; points get median."""
        gdf_m = gdf_slice.to_crs(epsg=3857)
        is_poly = gdf_m.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
        poly_areas = gdf_m.loc[is_poly, "geometry"].area
        median_area = float(poly_areas.median()) if not poly_areas.empty else 100.0
        result = {}
        for idx in gdf_m.index:
            g = gdf_m.loc[idx, "geometry"]
            if g.geom_type in ("Polygon", "MultiPolygon"):
                result[idx] = float(g.area)
            else:
                result[idx] = median_area
        return result

    def _gdf_to_candidates(data):
        if data.empty:
            return []
        masses_map = _footprint_masses(data)
        data_list = []
        for idx, row in data.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            point = geom.centroid if geom.geom_type != "Point" else geom
            name_val = row.get("name", "Unknown")
            name = name_val if pd.notna(name_val) else "Unknown"
            data_list.append({"name": name, "geometry": point, "mass": masses_map.get(idx, 100.0)})
        return data_list

    gdf_data = gpd.GeoDataFrame()
    df_data = pd.DataFrame()

    for candidate_set in candidate_sets:
        data = candidate_set[0]
        data_list = _gdf_to_candidates(data)

        if not data_list:
            print("No results for combination, trying next combination...")
            continue

        df_data = pd.DataFrame(data_list)
        gdf_data = gpd.GeoDataFrame(data_list, geometry="geometry", crs="EPSG:4326")

        if gdf_data.empty:
            print("gdf_data is empty for combination, trying next combination...")
            continue

        gdf_data = gdf_data[gdf_data.geometry.apply(lambda x: reachable_ring_area.contains(x))]
        if gdf_data.empty:
            print("Filter is empty for combination, trying next combination...")
            continue

        break

    if gdf_data.empty:
        print("Out of area — filtering buildings from cached dataset")
        data_list = _gdf_to_candidates(data_building)
        data_list = [d for d in data_list if reachable_ring_area.contains(d["geometry"])]

        if not data_list:
            return None, None

        df_data = pd.DataFrame(data_list)
        gdf_data = gpd.GeoDataFrame(data_list, geometry="geometry", crs="EPSG:4326")

    return df_data, gdf_data

def haversine_ring_filter(init_data, trip_type, start_lat, start_lon, duration_min, avg_speed_kmh=30):
    """Return candidate destinations reachable within duration_min from start using haversine ring.

    Replaces get_isochrone + poi_search_filter — no API calls.
    Returns list of dicts with keys: name, coords (lat,lon), mass, _idx.
    Returns None if no candidates found in the ring.
    """
    data_work, data_business, data_education, data_shopping, data_leisure, data_building = init_data

    type_map = {
        'WORK': data_work, 'BUSINESS': data_business, 'EDUCATION': data_education,
        'SHOPPING': data_shopping, 'LEISURE': data_leisure,
        'PERSONAL': data_building, 'TRANSPORT': data_building,
    }
    t = trip_type.upper()
    gdf = type_map.get(t, data_building)
    if gdf.empty:
        gdf = data_building
    if gdf.empty:
        return None

    max_r = duration_min * avg_speed_kmh / 60
    min_r = max(0.0, (duration_min - 5) * avg_speed_kmh / 60)

    # Pre-compute masses in metres² (reproject once per call)
    gdf_m = gdf.to_crs(epsg=3857)
    is_poly = gdf_m.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
    poly_areas = gdf_m.loc[is_poly, 'geometry'].area
    median_mass = float(poly_areas.median()) if not poly_areas.empty else 100.0

    candidates = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom.centroid if geom.geom_type != 'Point' else geom
        d = haversine(start_lon, start_lat, point.x, point.y)
        if min_r <= d <= max_r:
            name_val = row.get('name', 'Unknown')
            name = name_val if pd.notna(name_val) else 'Unknown'
            geom_m = gdf_m.loc[idx, 'geometry']
            mass = float(geom_m.area) if geom_m.geom_type in ('Polygon', 'MultiPolygon') else median_mass
            candidates.append({'name': name, 'coords': (point.y, point.x), 'mass': mass, '_idx': idx})

    return candidates if candidates else None


def ors_isochrone_filter(init_data, trip_type, start_lat, start_lon, duration_min):
    """Filter candidate destinations using ORS isochrones — same method as Golubović (2025).

    Two ORS API calls: isochrone at floor(duration) and ceil(duration) minutes.
    Candidates are POI that fall inside the annular zone (upper minus lower isochrone).
    Falls back to all POI within upper isochrone if annular zone is empty.
    Returns list of dicts {name, coords, mass, _idx} or None if no candidates.
    """
    data_work, data_business, data_education, data_shopping, data_leisure, data_building = init_data

    type_map = {
        'WORK': data_work, 'BUSINESS': data_business, 'EDUCATION': data_education,
        'SHOPPING': data_shopping, 'LEISURE': data_leisure,
        'PERSONAL': data_building, 'TRANSPORT': data_building,
    }
    t = trip_type.upper()
    gdf = type_map.get(t, data_building)
    if gdf.empty:
        gdf = data_building
    if gdf.empty:
        return None

    # Clamp duration to ORS limits (1–60 min)
    duration_clamped = max(1.0, min(float(duration_min), 60.0))
    lower0 = math.floor(duration_clamped)
    upper0 = math.ceil(duration_clamped)

    # Pre-compute masses
    gdf_m = gdf.to_crs(epsg=3857)
    is_poly = gdf_m.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
    poly_areas = gdf_m.loc[is_poly, 'geometry'].area
    median_mass = float(poly_areas.median()) if not poly_areas.empty else 100.0

    def _build_candidates(zone):
        cands = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            point = geom.centroid if geom.geom_type != 'Point' else geom
            if not zone.contains(point):
                continue
            name_val = row.get('name', 'Unknown')
            name = name_val if pd.notna(name_val) else 'Unknown'
            geom_m = gdf_m.loc[idx, 'geometry']
            mass = float(geom_m.area) if geom_m.geom_type in ('Polygon', 'MultiPolygon') else median_mass
            cands.append({'name': name, 'coords': (point.y, point.x), 'mass': mass, '_idx': idx})
        return cands

    # Primary: annular zone (as in Golubović), progressively widened outward
    # (floor-1..ceil+1, floor-2..ceil+2, ...) before giving up on the annular
    # constraint entirely — avoids flooding the candidate pool with trivially
    # close POI every time the thin floor/ceil ring happens to be empty.
    MAX_WIDEN = 4
    candidates = None
    polygon_upper = None
    for widen in range(MAX_WIDEN + 1):
        lower = max(0, lower0 - widen)
        upper = min(60, upper0 + widen)
        try:
            reachable_area, polygon_lower, polygon_upper = get_isochrone_window(
                lower, upper, start_lon, start_lat
            )
        except Exception as e:
            print(f"ORS isochrone failed: {e} — falling back to haversine ring")
            return haversine_ring_filter(init_data, trip_type, start_lat, start_lon, duration_min)

        candidates = _build_candidates(reachable_area)
        if candidates:
            if widen > 0:
                print(f"Annular zone widened by {widen} min for {trip_type} — found {len(candidates)} candidates")
            break

    # Fallback: entire upper isochrone (when annular zone stays empty even after widening)
    if not candidates:
        print(f"Annular zone empty for {trip_type} even after widening ±{MAX_WIDEN} min — trying full upper isochrone")
        candidates = _build_candidates(polygon_upper)

    # Last resort: any building in upper isochrone
    if not candidates:
        print(f"No typed POI in isochrone for {trip_type} — using all buildings")
        gdf_b = data_building
        gdf_bm = gdf_b.to_crs(epsg=3857)
        is_poly_b = gdf_bm.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
        poly_areas_b = gdf_bm.loc[is_poly_b, 'geometry'].area
        med_b = float(poly_areas_b.median()) if not poly_areas_b.empty else 100.0
        for idx, row in gdf_b.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            point = geom.centroid if geom.geom_type != 'Point' else geom
            if not polygon_upper.contains(point):
                continue
            name_val = row.get('name', 'Unknown')
            name = name_val if pd.notna(name_val) else 'Unknown'
            geom_m = gdf_bm.loc[idx, 'geometry']
            mass = float(geom_m.area) if geom_m.geom_type in ('Polygon', 'MultiPolygon') else med_b
            candidates.append({'name': name, 'coords': (point.y, point.x), 'mass': mass, '_idx': idx})

    return candidates if candidates else None


def find_substation(chosen_destination, gdf_sub):
    if not gdf_sub.empty:
        substation_coords = np.array([[point.x, point.y] for point in gdf_sub.geometry])
        destination_coords = np.array([[chosen_destination.geometry.x, chosen_destination.geometry.y]])

        tree = cKDTree(substation_coords)
        _, index = tree.query(destination_coords)

        nearest_substation = gdf_sub.iloc[index[0]]

    lon_start = np.radians(chosen_destination.geometry.x)
    lat_start = np.radians(chosen_destination.geometry.y)

    lon_end = np.radians(nearest_substation.geometry.x)
    lat_end = np.radians(nearest_substation.geometry.y)

    # Izračunajte razlike u koordinatama
    delta_lon = lon_end - lon_start
    delta_lat = lat_end - lat_start

    # Haversine formula
    a = np.sin(delta_lat / 2) ** 2 + np.cos(lat_start) * np.cos(lat_end) * np.sin(delta_lon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    radius = 6373
    distance = radius * c

    return nearest_substation, distance


def haversine_ring_filter_knn(init_data, trip_type, start_lat, start_lon,
                               duration_min, avg_speed_kmh=30, k_fallback=10):
    """Izboljšana verzija haversine_ring_filter z relaxed-ring fallback.

    Enako kot haversine_ring_filter za normalen primer. Ko je ring prazen:
    - Diagnoza: ali so POI znotraj min_r (preblizu) ali zunaj max_r (predaleč)?
    - Preblizu (pogost v malih mestih): odstrani min_r, vzorči iz [0, max_r]
      → gravitacijska logika ostane aktivna na pravih tipih POI
    - Predaleč: razširi max_r za 2× in poskusi znova
    - Ni POI tega tipa: zadnji resort — K najbližjih iz celotnega nabora stavb

    Vrne: (candidates, fallback_used)
      candidates — lista diktov {name, coords, mass, _idx} ali None
      fallback_used — True če je bil ring prazen in smo uporabili fallback
    """
    data_work, data_business, data_education, data_shopping, data_leisure, data_building = init_data

    type_map = {
        'WORK': data_work, 'BUSINESS': data_business, 'EDUCATION': data_education,
        'SHOPPING': data_shopping, 'LEISURE': data_leisure,
        'PERSONAL': data_building, 'TRANSPORT': data_building,
    }
    t = trip_type.upper()
    gdf = type_map.get(t, data_building)
    if gdf.empty:
        gdf = data_building
    if gdf.empty:
        return None, False

    max_r = duration_min * avg_speed_kmh / 60
    min_r = max(0.0, (duration_min - 5) * avg_speed_kmh / 60)

    # Izračunaj maso enkrat za ves GDF
    gdf_m = gdf.to_crs(epsg=3857)
    is_poly = gdf_m.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
    poly_areas = gdf_m.loc[is_poly, 'geometry'].area
    median_mass = float(poly_areas.median()) if not poly_areas.empty else 100.0

    def _to_candidate(idx, row):
        geom = row.geometry
        if geom is None or geom.is_empty:
            return None
        point = geom.centroid if geom.geom_type != 'Point' else geom
        name_val = row.get('name', 'Unknown')
        name = name_val if pd.notna(name_val) else 'Unknown'
        geom_m = gdf_m.loc[idx, 'geometry']
        mass = float(geom_m.area) if geom_m.geom_type in ('Polygon', 'MultiPolygon') else median_mass
        return {'name': name, 'coords': (point.y, point.x), 'mass': mass, '_idx': idx}

    def _filter_candidates(lo, hi):
        cands = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            point = geom.centroid if geom.geom_type != 'Point' else geom
            d = haversine(start_lon, start_lat, point.x, point.y)
            if lo <= d <= hi:
                c = _to_candidate(idx, row)
                if c:
                    cands.append(c)
        return cands

    # 1. Normalni ring filter [min_r, max_r]
    candidates = _filter_candidates(min_r, max_r)
    if candidates:
        return candidates, False

    # Diagnoza: POI preblizu (znotraj min_r) ali predaleč (zunaj max_r)?
    all_dists = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom.centroid if geom.geom_type != 'Point' else geom
        all_dists.append(haversine(start_lon, start_lat, point.x, point.y))

    if not all_dists:
        # Ni POI tega tipa — KNN iz vseh stavb kot zadnji resort
        all_pts = []
        idx_map = []
        for idx, row in data_building.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            pt = geom.centroid if geom.geom_type != 'Point' else geom
            all_pts.append((pt.x, pt.y))
            idx_map.append(idx)
        if not all_pts:
            return None, True
        tree = cKDTree(all_pts)
        k = min(k_fallback, len(all_pts))
        _, nn_pos = tree.query([start_lon, start_lat], k=k)
        nn_pos = [nn_pos] if k == 1 else list(nn_pos)
        fb_cands = [_to_candidate(idx_map[p], data_building.loc[idx_map[p]])
                    for p in nn_pos]
        return [c for c in fb_cands if c], True

    nearest_poi = min(all_dists)

    if nearest_poi < min_r:
        # POI so preblizu (min_r odreže vse): spusti min_r, vzorči iz [0, max_r].
        # Opomba: to vrne bližnje destinacije — pravi popravek bi bil večji avg_speed_kmh
        # ali krajši duration_min (kalibriran na lokalne podatke, ne NHTS).
        candidates = _filter_candidates(0.0, max_r)
        return (candidates if candidates else None), True
    else:
        # POI so predaleč: razširi max_r za 2× in poskusi
        candidates = _filter_candidates(min_r, max_r * 2.0)
        if not candidates:
            candidates = _filter_candidates(0.0, float('inf'))
        return (candidates if candidates else None), True

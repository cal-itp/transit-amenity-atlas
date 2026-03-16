import pygeohash as pgh
import geopandas as gpd
from shapely.geometry import box
import pandas as pd

df = pd.read_csv("../data/full_latest_stops.csv", low_memory=False)

for each_precision in [7,8,9]:
    geohashes = set()

    for index, row in df.iterrows():
        lat = row['stop_lat']
        lon = row['stop_lon']
        
        # Generate the geohash with each precision
        geohash = pgh.encode(lat, lon, precision=each_precision)
        
        geohashes.add(geohash)

    data = []
    for geohash in geohashes:
        bbox = pgh.get_bounding_box(geohash)
        poly = box(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)
        data.append({"geohash": geohash, "geometry": poly})
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    gdf.to_file(f"../data/hash_{each_precision}_boundary_output.fgb", engine="pyogrio")

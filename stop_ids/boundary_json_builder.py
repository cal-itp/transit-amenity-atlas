import pygeohash as pgh
import geopandas as gpd
from shapely.geometry import box
import pandas as pd

df = pd.read_csv("full_latest_stops.csv")

# iterate through unique geohashes and create bounding box polygons
data = []
for geohash in df['geohash_8'].unique():
    bbox = pgh.get_bounding_box(geohash)
    poly = box(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)
    data.append({"geohash": geohash, "geometry": poly})
gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
gdf.to_file("hash_8_boundary_output.json", driver="GeoJSON")

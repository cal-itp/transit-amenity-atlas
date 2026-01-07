import pygeohash as pgh
import geopandas as gpd
from shapely.geometry import box
import pandas as pd

df = pd.read_csv("../full_latest_stops.csv", low_memory=False)

# iterate through unique geohashes and create bounding box polygons
data = []
for geohash in df['geohash_8'].unique():
    bbox = pgh.get_bounding_box(geohash)
    poly = box(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)
    data.append({"geohash": geohash, "geometry": poly})
gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
gdf.to_file("../data/hash_8_boundary_output.fgb", engine="pyogrio")
# gdf.to_file("output.fgb", engine="pyogrio")

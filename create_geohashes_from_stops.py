"""
Create geohashes from all the latest transit stops and aggregate counts of stops per geohash.

Saves:
- full_latest_stops.csv: CSV of all stops with geohashes and counts
- stops_w_geohashes.gpkg: GeoPackage of stops with geohashes
"""

import duckdb
import geopandas as gpd
from google.cloud import bigquery
import pandas as pd
from urllib.parse import urlencode

client = bigquery.Client(project="cal-itp-data-infra")

def streetview_web_link(lat, lon, heading=0, pitch=0, fov=90):
    """
    Clickable Google Maps Street View (opens Maps with panorama).
    """
    params = {
        "api": "1",
        "map_action": "pano",
        "viewpoint": f"{lat},{lon}",
        "heading": str(heading),
        "pitch": str(pitch),
        "fov": str(fov),
    }
    return "https://www.google.com/maps/@?" + urlencode(params)

sql = """
SELECT
  ds.KEY,
  ds.feed_key,
  ds.base64_url,
  gd.analysis_name,
  ds.stop_id,
  ds.tts_stop_name,
  stop_lat,
  stop_lon,
  stop_code,
  stop_name,
  ST_GEOHASH(ST_GEOGPOINT(stop_lon, stop_lat), 7) AS geohash_id
FROM
  `mart_gtfs_schedule_latest.dim_stops_latest` ds
left join mart_transit_database.dim_gtfs_datasets gd
on ds.base64_url = gd.base64_url
where 
gd._is_current=TRUE
and
stop_lat != 0.0
;
"""
# Leave out nationwide stops agencies
df = client.query(sql).to_dataframe()  

df['streetview_link'] = df.apply(lambda r: streetview_web_link(r['stop_lat'], r['stop_lon']), axis=1)

con = duckdb.connect() 
con.register("stops_df", df)
sql = """
SELECT
  geohash_id,
  COUNT(*) AS n_stops_in_geohash,
FROM stops_df
GROUP BY geohash_id
order by n_stops_in_geohash DESC
"""
agg_df = con.execute(sql).fetchdf()

# merge counts back onto df
df = df.merge(agg_df, on="geohash_id", how="left")

# save full stops with geohashes and counts
df.to_csv("maps/full_latest_stops.csv", index=False)

# build GeoDataFrame (WGS84)
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['stop_lon'], df['stop_lat']), crs="EPSG:4326")

#https://gis.data.ca.gov/datasets/CDEGIS::california-state-boundary/explore
path = "California_State_Boundary.geojson"
ca_gdf = gpd.read_file(path)
gdf = gpd.clip(gdf, ca_gdf) # clip to CA boundary


gdf.to_file("maps/stops_w_geohashes_7.gpkg", layer="stops", driver="GPKG")
# alternatives:
gdf.to_file("maps/stops_w_geohashes_7.geojson", driver="GeoJSON")
# gdf.to_file("maps/stops_w_geohashes.shp")  # shapefile has name/field limits

out = gdf.copy()
out["lon"] = out.geometry.x
out["lat"] = out.geometry.y
out.drop(columns="geometry").to_csv("maps/stops_inside_ca_with_coords_7.csv", index=False)

import geopandas as gpd
from google.cloud import bigquery
import pandas as pd
from urllib.parse import urlencode

client = bigquery.Client(project="cal-itp-data-infra")

sql = """
WITH
  BaseStops AS (
    -- Filters and calculates the geohash for every relevant stop
SELECT
  ds.KEY,
  ds._gtfs_key,
  ds.feed_key,
  ds.base64_url,
  gd.analysis_name,
  ds.stop_id,
  ds.tts_stop_name,
  stop_lat,
  stop_lon,
  stop_code,
  stop_name,
  ST_GEOHASH(ST_GEOGPOINT(stop_lon, stop_lat), 7) AS geohash_7
FROM
  `mart_gtfs_schedule_latest.dim_stops_latest` ds
left join mart_transit_database.dim_gtfs_datasets gd
on ds.base64_url = gd.base64_url
where 
gd._is_current=TRUE
and
stop_lat != 0.0  )
SELECT
  t1.geohash_7 AS geohash_id,
  ANY_VALUE(t1.stop_lat) AS gh_stop_lat,
  ANY_VALUE(t1.stop_lon) AS gh_stop_lon,
  STRING_AGG(DISTINCT t1.analysis_name, ', ' ORDER BY t1.analysis_name) AS unique_agency_names_string,
  MIN(t1.stop_name) AS gh_stop_name,
  STRING_AGG(DISTINCT t1.stop_name, ', ' order by t1.stop_name) AS unique_stop_names_list,
  COUNT(t1.stop_name) AS stop_count
FROM
  BaseStops t1
GROUP BY
  1
  """
df = client.query(sql).to_dataframe()  

import geopandas as gpd


gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['gh_stop_lon'], df['gh_stop_lat']), crs="EPSG:4326")

#https://gis.data.ca.gov/datasets/CDEGIS::california-state-boundary/explore
path = "California_State_Boundary.geojson"
ca_gdf = gpd.read_file(path)
gdf = gpd.clip(gdf, ca_gdf) # clip to CA boundary

gdf.to_file("maps/geohashed_grouped_stops_7.gpkg", layer="stops", driver="GPKG")
gdf.to_file("maps/geohashed_grouped_stops_7.geojson", driver="GeoJSON")

out = gdf.copy()
out["lon"] = out.geometry.x
out["lat"] = out.geometry.y
out.drop(columns="geometry").to_csv("maps/geohashed_grouped_stops_7_inside_ca.csv", index=False)

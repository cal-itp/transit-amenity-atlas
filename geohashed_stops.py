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
      da.agency_name,
      ds.stop_name,
      ds.stop_lat,
      ds.stop_lon,
      ST_GEOHASH(ST_GEOGPOINT(ds.stop_lon, ds.stop_lat), 8) AS geohash_8
    FROM
      `mart_gtfs_schedule_latest.dim_stops_latest` ds
      LEFT JOIN mart_gtfs.dim_agency da
      ON ds.feed_key = da.feed_key
    WHERE
      da.agency_id NOT IN ('GREYHOUND-us', 'FLIXBUS-us')
      AND da.agency_name NOT IN ('Oregon POINT', 'Curry Public Transit')
      AND ds.stop_lat != 0.0
  )
SELECT
  t1.geohash_8 AS geohash_id,
  ANY_VALUE(t1.stop_lat) AS gh_stop_lat,
  ANY_VALUE(t1.stop_lon) AS gh_stop_lon,
  STRING_AGG(DISTINCT t1.agency_name, ', ' ORDER BY t1.agency_name) AS unique_agency_names_string,
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


df.to_csv("maps/geohashed_stops.csv", index=False)

gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['gh_stop_lon'], df['gh_stop_lat']), crs="EPSG:4326")

#https://gis.data.ca.gov/datasets/CDEGIS::california-state-boundary/explore
path = "California_State_Boundary.geojson"
ca_gdf = gpd.read_file(path)
gdf = gpd.clip(gdf, ca_gdf) # clip to CA boundary

gdf.to_file("maps/geohashed_stops.gpkg", layer="stops", driver="GPKG")
gdf.to_file("maps/geohashed_stops.geojson", driver="GeoJSON")

# Data dictionary — stops_inside_ca_with_coords_7.csv / stops_w_geohashes_7.gpkg

Please refer to https://dbt-docs.dds.dot.ca.gov/#!/model/model.calitp_warehouse.dim_stops_latest for more source information.

Here is a deeper explanation of geohashes: https://www.movable-type.co.uk/scripts/geohash.html

We are intentionally using the Base32 algorithm whcih shows up in python (geohash2) and in bigquery for maximum compatibility.

CRS: EPSG:4326 (WGS84)
Geometry column: geometry (Point). CSV includes lon/lat columns.


## Files
- `stops_inside_ca_with_coords_7.csv` — flattened CSV with lon/lat and attributes
- `stops_w_geohashes_7.gpkg` — GeoPackage with geometry column and same attributes

## Fields

| Field name | Type | Description | Example |
|---|---:|---|---|
| feed_key | string | Foreign key to the schedule_feeds table | `feed-xyz` |
| base64_url | string | Base 64 encoded URL from which this data was scraped. (used to join datasets) | `aGVsbG8=` |
| analysis_name | string | Human-readable dataset name from dim_gtfs_datasets | `SF Muni - 2025` |
| stop_id | string | Stop id as provided in source GTFS | `12345` |
| tts_stop_name | string | Text-to-speech friendly stop name | `Main St & 1st` |
| stop_name | string | Original stop name field | `Main St & 1st` |
| stop_lat | float | Original latitude from source | `37.7749` |
| stop_lon | float | Original longitude from source | `-122.4194` |
| stop_code | string/null | Stop code field (if present) | `S123` |
| geohash_id | string | Geohash precision 7 computed from lon/lat | `9q8yyk1` |
| n_stops_in_geohash | integer | Count of stops that share the geohash_id | `4` |
| streetview_link | string | Google Maps Street View link (opens panorama) | `https://www.google.com/maps/...?viewpoint=37.7,-122.4` |


## Files
- `geohashed_grouped_stops_7_inside_ca.csv` — flattened CSV with lon/lat and attributes
- `geohashed_grouped_stops_7.gpkg` — GeoPackage with geometry column and same attributes

## Fields

| Field name | Type | Description | Example |
|---|---:|---|---|
| analysis_name | string | Human-readable dataset name from dim_gtfs_datasets | `SF Muni - 2025` |
| gh_stop_name | string | A stop name from the geohash group| `Main St & 1st` |
| gh_stop_lat | float | One of the latitudes from a stop in the geohash | `37.7749` |
| gh_stop_lon | float | One of the longitudes from a stop in the geohash | `-122.4194` |
| geohash_id | string | Geohash precision 7 computed from lon/lat | `9q8yyk1` |

  t1.geohash_7 AS geohash_id,
  ANY_VALUE(t1.stop_lat) AS gh_stop_lat,
  ANY_VALUE(t1.stop_lon) AS gh_stop_lon,
  STRING_AGG(DISTINCT t1.analysis_name, ', ' ORDER BY t1.analysis_name) AS unique_agency_names_string,
  MIN(t1.stop_name) AS gh_stop_name,
  STRING_AGG(DISTINCT t1.stop_name, ', ' order by t1.stop_name) AS unique_stop_names_list,
  COUNT(t1.stop_name) AS stop_count

## Files
- `amenity_stops.csv`
- `amenity_stops.gpkg`

## Fields

Please refer to the [Initial schema for Stop Amenities](schema.md).

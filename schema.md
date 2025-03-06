# Transit Bus Stop Schema

This schema defines the structure for representing transit bus stop information.

## Core Attributes (Essential)

* `operator`: (String, Optional) Name of the company operating the buses that stop at the bus stop. If several different operating companies serve the stop, use a semicolon (;) to separate the different operators in the value of the tag.
* `stop_id`: (String) Unique identifier for the bus stop.
* `stop_code`: (String) Identifies the location for riders
* `name`: (String) Official name of the bus stop.
* `stop_lat`: (Float) Latitude (WGS84, EPSG:4326).
* `stop_lon`: (Float) Longitude (WGS84, EPSG:4326).

## Recommended Attributes (Important)

* `shelter`: (enum, Optional) 'yes' if the stop is protected from the rain by a shelter. 'no' if it is not.
* `bench`: (enum, Optional) 'yes' if a bench for riders to sit on is present at the stop. 'no' if not.
* `lit`: (enum, Optional) 'yes' if the bus stop is lit up at night. 'no' if not.
* `rt_signage`: (enum, Optional) 'yes' if their is real-time signage. 'no' if not.
* `bin`: (enum, Optional) 'yes' if there is a trash can at the bus stop. 'no' if not.

* `parent_station`: (String, Optional) `stop_id` of parent station.
* `wheelchair_boarding`: (Integer, Optional) Wheelchair accessibility:
    * `0`: Unknown
    * `1`: Accessible
    * `2`: Not Accessible

## Extensible Attributes (For Specific Needs)
* `osm_id`: (Integer, Optional) OpenStreetMap ID.
* `osm_tags`: (JSON, Optional) Original OSM tags (JSON).

**Derived from:**

* [GTFS stops.txt](https://gtfs.org/documentation/schedule/reference/#stopstxt)
* [OpenStreetMap Buses](https://wiki.openstreetmap.org/wiki/Buses#Bus_stops)

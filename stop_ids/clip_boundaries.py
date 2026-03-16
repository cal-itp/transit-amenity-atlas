import geopandas as gpd

#https://gis.data.ca.gov/datasets/CDEGIS::california-state-boundary/explore
def clip_to_ca_boundary(gdf):
    path = "ref_data/California_State_Boundary.geojson"
    ca_gdf = gpd.read_file(path)
    gdf = gpd.clip(gdf, ca_gdf) # clip to CA boundary
    return gdf

def clip_to_sf_boundary(gdf):
    path = "ref_data/Bay_Area_County_Polygons_20251209.geojson"
    sf_gdf = gpd.read_file(path)
    # Filter to only San Francisco county
    sf_gdf = sf_gdf[sf_gdf['county'] == "San Francisco"]
    gdf = gpd.clip(gdf, sf_gdf) # clip to SF boundary
    return gdf

def clip_to_vta_boundary(gdf):
    path = "ref_data/Bay_Area_County_Polygons_20251209.geojson"
    vta_gdf = gpd.read_file(path)
    vta_gdf = vta_gdf[vta_gdf['county'] == "Santa Clara"]

    gdf = gpd.clip(gdf, vta_gdf) # clip to VTA boundary
    return gdf

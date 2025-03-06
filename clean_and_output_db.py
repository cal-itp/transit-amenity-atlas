'''
1. Ingests all existing data files in the semi_processed folder.
2. Selects only the specified fields.
3. Combines all dataframes into a single dataframe.
4. Converts the 'shelter', 'bench', 'lit', 'rt_signage', 'bin', and 'wheelchair_boarding' columns to 'yes' or 'no'.
5. Exports the combined dataframe to a CSV file.
6. Exports the combined dataframe to a GeoJSON file.
'''
import logging
import os

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Configure logging
logging.basicConfig(
    filename='bus_stop_processing.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # 'w' for write (overwrite), 'a' for append (default)
)

source_folder = 'semi_processed'

dataframes = {}

# Define the fields to pull out
fields = [
    "operator", "stop_id", "stop_code", "name", "stop_lat", "stop_lon",
    "shelter", "bench", "lit", "rt_signage", "bin", "parent_station", "wheelchair_boarding"
]

agency_names = {
    'LA_Metro_Bus_Stop_Amenities.xlsx': 'LA Metro',
    'VVTA_Bus_Stop_Amenities.xlsx': 'VVTA',
    'SFMTA_Bus_Stop_Amenities_Updated_Feb_2024.xlsx': 'SFMTA',
    'Santa_Clara_Valley_Transportation_Authority_Bus_Stop_Amenities_Updated_2020.xlsx': 'Santa Clara VTA',
    'Santa_Monica_BBB_Bus_Stop_Amenities.xlsx': 'Santa Monica Big Blue Bus',
    'SBMTD_Bus_Stop_Amenities_Dataset_Cleaned_1-21-2025.xlsx': 'Santa Barbara MTD',
    'San_Diego_MTS_Bus_Stop_Amenities_Updated_Jun_2024.xlsx': 'San Diego MTS',
    'City_of_Needles_Bus_Stop_Amenities.xlsx': 'City of Needles',
    'BBB_Stop_Amenity_Data.xlsx': 'Santa Monica BBB'
}

# Loop through each file and read it into a pandas dataframe
files = os.listdir(source_folder)
for file in files:
    if file.endswith('.xlsx'):
        file_path = os.path.join(source_folder, file)
        try:
            df = pd.read_excel(file_path)
            # Select only the specified fields if they exist in the dataframe
            df = df[[field for field in fields if field in df.columns]]
            if file in agency_names:
                df['agency'] = agency_names[file]
            else:
                logging.info(f'New {file} with shape {df.shape}')

            dataframes[file] = df
            logging.info(f'Successfully ingested {file} with shape {df.shape}')
        except Exception as e:
            logging.error(f'Error ingesting {file}: {e}')

combined_df = pd.concat(dataframes, ignore_index=True)
combined_df['stop_id'] = combined_df['stop_id'].astype(str) #handle mixed types in stop_id

def yes_and_no_converter(x):
    if pd.isna(x) or x in [None]:
        return x
    elif x in ['No', 'no', False, 'False', 'None', 'N', 'n', 0, '0']:
        return 'no'
    elif x in ['Yes', 'yes', True, 'True', 'Y', 'y', 'Existing']:
        return 'yes'
    else:
        return x
def everything_else_converter(x):
    if pd.isna(x) or x in [None, 'yes', 'no']:
        return x
    else:
        return 'yes'

for column in ['shelter', 'bench', 'wheelchair_boarding', 'lit', 'bin', 'rt_signage']:
    if column in combined_df.columns:
        combined_df[column] = combined_df[column].str.strip()
        logging.info(f"Value counts for '{column}' before conversion:\n{combined_df[column].value_counts(dropna=False)}")
        combined_df[column] = combined_df[column].apply(yes_and_no_converter)
        logging.info(f"Value counts for '{column}' after conversion:\n{combined_df[column].value_counts(dropna=False)}")
        combined_df[column] = combined_df[column].apply(everything_else_converter)
        logging.info(f"Value counts for '{column}' after everything else conversion:\n{combined_df[column].value_counts(dropna=False)}")

    else:
        logging.warning(f"Column '{column}' not found in combined dataframe.")

combined_df.to_csv('combined_df.csv',index=False)

# Create a GeoDataFrame from the combined dataframe
logging.info(f"Shape of combined_df before scrubbing: {combined_df.shape}")

# Define valid latitude and longitude ranges for California
valid_lat_range = (32.0, 42.0)
valid_lon_range = (-125.0, -114.0)

# Query out rows with invalid geospatial values
valid_geo_df = combined_df[
    combined_df['stop_lat'].between(valid_lat_range[0], valid_lat_range[1]) &
    combined_df['stop_lon'].between(valid_lon_range[0], valid_lon_range[1])
]

logging.info(f"Shape of valid_geo_df after scrubbing: {valid_geo_df.shape}")
geometry = [Point(xy) for xy in zip(valid_geo_df['stop_lon'], valid_geo_df['stop_lat'])]
gdf = gpd.GeoDataFrame(valid_geo_df, geometry=geometry)

logging.info(f"Outputting geojson: stops_with_points.geojson")
gdf.to_file("stops_with_points.geojson", driver='GeoJSON')

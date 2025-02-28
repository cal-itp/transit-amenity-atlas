'''
1. Ingests all existing data files in the semi_processed folder.
2. Selects only the specified fields.
3. Combines all dataframes into a single dataframe.
4. Converts the 'shelter', 'bench', 'lit', 'rt_signage', 'bin', and 'wheelchair_boarding' columns to 'yes' or 'no'.
5. Exports the combined dataframe to a CSV file.
6. Exports the combined dataframe to a GeoJSON file.
'''

import os

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


# Define the path to the semi_processed folder
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
    'Santa_Monica_BBB_Bus_Stop_Amenities.xlsx': 'Santa Monica Big Blue Bus'
}

# Loop through each file and read it into a pandas dataframe
files = os.listdir(source_folder)
for file in files:
    if file.endswith('.xlsx'):
        file_path = os.path.join(source_folder, file)
        df = pd.read_excel(file_path)
        # Select only the specified fields if they exist in the dataframe
        df = df[[field for field in fields if field in df.columns]]
        df['agency'] = agency_names[file]
        dataframes[file] = df

# Print the names of the ingested files and their respective dataframes
for file, df in dataframes.items():
    print(f'Ingested {file} with shape {df.shape}')

combined_df = pd.concat(dataframes, ignore_index=True)

def no_converter(x):
    if pd.isna(x) or x in [None, 'No', 'no', False, 'False', 'None']:
        return 'no'
    else:
        return 'yes'

for column in ['shelter', 'bench','wheelchair_boarding','lit', 'bin', 'rt_signage']:
    combined_df[column] = combined_df[column].apply(no_converter)

combined_df.to_csv('combined_df.csv',index=False)

geo_dfs = combined_df.loc[~combined_df['stop_lat'].isnull(),] #scrub out rows with missing latitudes
geometry = [Point(xy) for xy in zip(geo_dfs['stop_lon'], geo_dfs['stop_lat'])]
gdf = gpd.GeoDataFrame(geo_dfs, geometry=geometry)

# Export to GeoJSON
gdf.to_file("stops_with_points.geojson", driver='GeoJSON')
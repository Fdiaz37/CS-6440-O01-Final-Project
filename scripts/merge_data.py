import pandas as pd
import os

def build_master_dataset(raw_dir, processed_dir):
    print("Starting the final merge...")

    # Grab our files
    sdoh_path = os.path.join(processed_dir, "sdoh_cleaned.csv")
    fhir_path = os.path.join(processed_dir, "fhir_burden_cleaned.csv")
    crosswalk_path = os.path.join(raw_dir, "HUD_ZIP_COUNTY.csv")

    # Quick check so the script doesn't crash if someone on the team forgot to download it
    if not os.path.exists(crosswalk_path):
        print("Make sure HUD_ZIP_COUNTY.csv is in the raw folder.")
        return

    # Load everything into pandas
    sdoh_df = pd.read_csv(sdoh_path)
    fhir_df = pd.read_csv(fhir_path)
    cw_df = pd.read_csv(crosswalk_path)

    # Make sure pandas didn't turn zip codes into math numbers 
    sdoh_df['Year'] = sdoh_df['Year'].astype(str)
    sdoh_df['FIPS Code'] = sdoh_df['FIPS Code'].astype(str).str.zfill(5)
    fhir_df['ZipCode'] = fhir_df['ZipCode'].astype(str).str.zfill(5)

    # Synthea gives us exact years, but CDC only gives us even years. We gotta bucket them so we don't lose patients during the merge.
    def map_year_to_svi(year):

        try:

            y = int(year)
            if y <= 2015: return '2014'
            elif y <= 2017: return '2016'
            elif y <= 2019: return '2018'
            elif y <= 2021: return '2020'
            else: return '2022'
        except:

            return 'Unknown'

    fhir_df['SVI_Year'] = fhir_df['Year'].apply(map_year_to_svi)

    # The HUD Geographic Crosswalk (Zip -> County)


    print("Parsing the HUD database...")
    
    # Clean the HUD columns just like we did ours

    cw_df['ZIP'] = cw_df['ZIP'].astype(str).str.zfill(5)

    cw_df['COUNTY'] = cw_df['COUNTY'].astype(str).str.zfill(5)

    # The HUD file puts zip codes in multiple counties if they cross borders. 
    # sort by Residential Ratio (RES_RATIO) so the county with the MOST houses stays at the top.
    if 'RES_RATIO' in cw_df.columns:


        cw_df = cw_df.sort_values(by=['ZIP', 'RES_RATIO'], ascending=[True, False])
    
    # Drop duplicates so we only keep the #1 majority county for each zip
    cw_df = cw_df.drop_duplicates(subset=['ZIP'])



    # Turn the dataframe into a fast dictionary lookup
    real_crosswalk = dict(zip(cw_df['ZIP'], cw_df['COUNTY']))

    # Map our synthetic patients to their real-world counties!
    fhir_df['FIPS Code'] = fhir_df['ZipCode'].map(real_crosswalk)


    # If any patients have fake zip codes that aren't in the HUD file, drop them so they don't break the map
    fhir_df = fhir_df.dropna(subset=['FIPS Code'])

    # Squish the FHIR Data.This takes the tall rows of ER reasons and flips them sideways into clean columns
    fhir_pivoted = fhir_df.pivot_table(
        index=['FIPS Code', 'SVI_Year'],

        columns='ER_Reason_Text',

        values='Total_ER_Visits',

        aggfunc='sum',
        fill_value=0 # Put a 0 if a county didn't have that specific ER visit
    ).reset_index()

    # Rename the columns so they look good on the dashboard
    new_cols = {}
    for col in fhir_pivoted.columns:
        if col not in ['FIPS Code', 'SVI_Year']:
            
            new_cols[col] = f"ER Visits: {col}"
    fhir_pivoted = fhir_pivoted.rename(columns=new_cols)

    # Add them all up for a Total column
    reason_cols = list(new_cols.values())
    fhir_pivoted['Total ER Visits'] = fhir_pivoted[reason_cols].sum(axis=1)

    # THE FINAL MERGE
    # Merge on both FIPS Code (Geography) AND Year (Timeline)
    final_dashboard_df = pd.merge(
        sdoh_df, 
        fhir_pivoted, 
        left_on=['FIPS Code', 'Year'], 
        right_on=['FIPS Code', 'SVI_Year'], 
        how='inner' # Inner join so we only map places that have BOTH CDC data and patient data
    )
    
    # We don't need SVI_Year anymore since we matched it to the CDC 'Year'
    final_dashboard_df = final_dashboard_df.drop(columns=['SVI_Year'])

    # Save 
    output_path = os.path.join(processed_dir, "final_dashboard_data.csv")
    final_dashboard_df.to_csv(output_path, index=False)

    print(f"Final dataset saved to {output_path}")

if __name__ == "__main__":
    # Figure out where this script is running from so the paths don't break on my teammates' computers
    script_dir = os.path.dirname(os.path.abspath(__file__))
    RAW_DIR = os.path.join(script_dir, "..", "data", "raw")
    PROCESSED_DIR = os.path.join(script_dir, "..", "data", "processed")
    
    build_master_dataset(RAW_DIR, PROCESSED_DIR)
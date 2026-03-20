import pandas as pd
import os
import glob

def process_cdc_svi_data(raw_data_dir, output_dir):
    print("Starting SDOH Data Processing...")
    
    #find all the SVI CSV files in the raw folder 
    svi_files = glob.glob(os.path.join(raw_data_dir, "SVI_DATA", "SVI_*_US_county.csv"))    
    if not svi_files:
        print("No CDC SVI files found in data/raw/ folder.")
        return

    all_years_data = []

    for file_path in svi_files:
        # Extract the year from the filename 
        filename = os.path.basename(file_path)

        year = filename.split('_')[1]
        
        # Load the CSV
        df = pd.read_csv(file_path)
        
        # Normalize changing column names across the datasets because they have diffrent column names for the same thing 
        if 'EP_POV150' in df.columns:
            df = df.rename(columns={'EP_POV150': 'EP_POV'})

        if 'STCNTY' in df.columns and 'FIPS' not in df.columns:
            df = df.rename(columns={'STCNTY': 'FIPS'})
            
        # Select the core columns
        keep_columns = ['FIPS', 'STATE', 'COUNTY', 'EP_POV', 'EP_UNEMP', 'EP_NOHSDP']
        
        available_cols = [col for col in keep_columns if col in df.columns]
        df = df[available_cols].copy()
        
        #Rename to Human-Readable "Long Names" for convenience
        long_names = {
            'FIPS': 'FIPS Code',
            'STATE': 'State',
            'COUNTY': 'County',
            'EP_POV': 'Poverty Percentage',
            'EP_UNEMP': 'Unemployment Percentage',
            'EP_NOHSDP': 'No High School Diploma Percentage'
        }
        df = df.rename(columns=long_names)
        
        # Add the Year column
        df['Year'] = year
        
        all_years_data.append(df)
        
    # Combine all 5 years into one massive DataFrame


    final_sdoh_df = pd.concat(all_years_data, ignore_index=True)
    
    # Ensure FIPS codes are 5-digit strings so Plotly maps them correctly

    if 'FIPS Code' in final_sdoh_df.columns:
        # Convert to string, remove any decimals if pandas read it as a float, and pad with leading zeros

        final_sdoh_df['FIPS Code'] = final_sdoh_df['FIPS Code'].astype(str).str.replace('.0', '', regex=False)
        final_sdoh_df['FIPS Code'] = final_sdoh_df['FIPS Code'].str.zfill(5)
        
    # Save the final cleaned CSV
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "sdoh_cleaned.csv")
    final_sdoh_df.to_csv(output_path, index=False)
    
    print(f"Cleaned SDOH data saved to {output_path}")

if __name__ == "__main__":
    #Find where this Python script is on pc
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    #Build the paths 
    RAW_DIR = os.path.join(script_dir, "..", "data", "raw")
    PROCESSED_DIR = os.path.join(script_dir, "..", "data", "processed")
    # Run the function
    process_cdc_svi_data(RAW_DIR, PROCESSED_DIR)
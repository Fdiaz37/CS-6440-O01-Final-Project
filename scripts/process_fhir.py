import pandas as pd
import json
import os
import glob

def process_fhir_data(raw_data_dir, output_dir):
    print("Starting FHIR Data Processing with ER Reasons...")
    
    fhir_files = glob.glob(os.path.join(raw_data_dir, "*.json"))
    
    if not fhir_files:
        print(f"No FHIR JSON files found in {raw_data_dir}.")
        return

    print(f"Found {len(fhir_files)} patient records. Extracting ER encounters...")
    
    # We will now store a list of specific ER VISITS, rather than just patients
    er_visit_records = []

    for file_path in fhir_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                bundle = json.load(f)
            except json.JSONDecodeError:
                continue 
        
        # Temporary patient demographics
        patient_id = None
        city = "Unknown"
        state = "Unknown"
        zipcode = "Unknown"
        
        # First pass: Find the Patient's demographics
        for entry in bundle.get('entry', []):

            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Patient':

                patient_id = resource.get('id')
                addresses = resource.get('address', [])
                if addresses:

                    city = addresses[0].get('city', 'Unknown')
                    state = addresses[0].get('state', 'Unknown')
                    zipcode = addresses[0].get('postalCode', 'Unknown')
                break # Once we find the patient profile
                
        # Second pass: Find all their ER visits and the reasons and year
        for entry in bundle.get('entry', []):

            resource = entry.get('resource', {})
            
            if resource.get('resourceType') == 'Encounter':

                enc_class = resource.get('class', {}).get('code', '')
                
                if enc_class == 'EMER': # If it's an ER visit
                    reason_code = "No Code"
                    reason_text = "Unknown Reason"
                    
                    # EXTRAT THE YEAR: Dig into the period object
                    period = resource.get('period', {})

                    start_date = period.get('start', '')

                    # Grab the first 4 characters ("2018")
                    visit_year = start_date[:4] if len(start_date) >= 4 else "Unknown"
                    
                    reasons = resource.get('reasonCode', [])

                    if reasons:
                        codings = reasons[0].get('coding', [])
                        if codings:
                            reason_code = codings[0].get('code', 'No Code')
                            reason_text = codings[0].get('display', 'Unknown Reason')
                    
                    if patient_id:
                        er_visit_records.append({
                            'Patient_ID': patient_id,
                            'Year': visit_year,
                            'City': city,
                            'State': state,
                            'ZipCode': zipcode,
                            'ER_Reason_Code': reason_code,
                            'ER_Reason_Text': reason_text
                        })

    # Convert to Pandas DataFrame
    df = pd.DataFrame(er_visit_records)

    if not df.empty:
        # AGGREGATION
        regional_burden = df.groupby(['Year', 'State', 'City', 'ZipCode', 'ER_Reason_Code', 'ER_Reason_Text']).agg(
            Total_ER_Visits=('Patient_ID', 'count')
        ).reset_index()

        regional_burden = regional_burden.sort_values(by=['Year', 'ZipCode', 'Total_ER_Visits'], ascending=[False, True, False])

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "fhir_burden_cleaned.csv")
        regional_burden.to_csv(output_path, index=False)
        print(f"Cleaned FHIR data saved to {output_path}")
    else:
        print("No ER visits found in this patient cohort.")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))

    RAW_DIR = os.path.join(script_dir, "..", "data", "raw", "FIHR R4 Synthethic", "synthea_sample_data_fhir_r4_nov2021", "fhir")


    PROCESSED_DIR = os.path.join(script_dir, "..", "data", "processed")

    process_fhir_data(RAW_DIR, PROCESSED_DIR)
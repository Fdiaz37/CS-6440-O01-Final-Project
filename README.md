# Public Health Dashboard: SDOH & Healthcare Burden

**Course:** CS 6440: Intro to Health Informatics  
**Team:** Peter Kupec, Yiming Chen, Tim Pham, Oluwafisayo Oduyemi, Fernando Diaz

## About This Project
This project is a serverless web dashboard designed to help public health officials visualize the relationship between Social Determinants of Health (SDOH) and healthcare utilization across the United States. 

To meet modern healthcare interoperability standards without requiring a live backend server, our data pipeline merges public U.S. Census/CDC data with synthetic patient records formatted in the FHIR (Fast Healthcare Interoperability Resources) standard. 

## Repository Structure
To keep our deployment lightweight, raw data is processed offline using Python, and only the finalized, flattened CSVs are pushed to the live website.

* `/data/raw/` - Ignored by Git. ownloaded FHIR and CDC files here.
* `/data/processed/` - Tracked by Git. Contains the final proccessed csv
* `/scripts/` - Contains `prep_data.py` `process_fhir.py` and 'merge_data.py' 
* `/site/` - Contains the HTML, JS , and CSS for the GitHub Pages dashboard.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Local Setup & Data Instructions

Because our raw datasets are too large for GitHub, you must download them locally to run the Python data pipeline. 

### Step 1: Clone the Repo
Clone this repository to your local machine and ensure you have Python and Pandas installed.
`pip install pandas requests`

### Step 2: Download the CDC SVI Data 
1. Go to the [CDC ATSDR Social Vulnerability Index page](https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html).
2. Download the CSV files for the entire United States at the County level for the years 2014, 2016, 2018, 2020, and 2022.
3. Move these CSV files into your local `data/raw/` folder.

### Step 3: Download the Synthetic FHIR Data 
1. Go to the [Synthea Downloads Page](https://synthea.mitre.org/downloads).
2. Under "Previous Versions", download the 1K Sample Synthetic Patient Records, FHIR R4 
3. Unzip the folder and place the JSON files into your local `data/raw/` folder.

### Step 4: Download the HUD-USPS ZIP Crosswalk Files:
1. Go to the [Downloads Page](https://www.huduser.gov/apps/public/uspscrosswalk/home).
2. Have to make an account and download the latest 4th Quarter 2025, Zip-COynty
3. Unzip the folder and place the JSON files into your local `data/raw/` folder.

-----------------------------------------------------------------------------------------------------------------------------------------------
## Data Processing Logic - SVI  (`prep_data.py`)

To maintain a fast, serverless architecture for GitHub Pages, all data merging is handled offline via our Python ETL (Extract, Transform, Load) pipeline. 

### Core Libraries
* **`pandas`**: Used for high-performance data manipulation, filtering, and standardizing the changing CDC column names across different years.
* **`glob`**: Utilized for dynamic pattern matching (e.g., `SVI_*_US_county.csv`). This prevents hardcoding filenames and allows the pipeline to automatically ingest new years of data if they are added to the `/raw` folder.
* **`os`**: Ensures relative file pathing works across all team members' operating systems (Windows/Mac/Linux) without breaking.

### The Processing Flow
1. **Dynamic Ingestion:** `glob` scans the `/data/raw/\SVI_DATA` directory for the downloaded CDC SVI files and extracts the year directly from the filename.
2. **Normalization:** The CDC alters its column headers periodically (e.g., `EP_POV` vs `EP_POV150`). The script standardizes these headers so they stack cleanly.
3. **Filtering:** We drop over 100 unused data points, keeping only the essential SDOH metrics (Poverty, Unemployment, Education) to keep the final payload lightweight.
4. **FIPS Standardization:** County FIPS codes are forced into a strict 5-digit string format (padding with leading zeros where necessary) to guarantee a 1:1 match with the frontend Plotly choropleth map.
5. **Output:** The script stacks the data into a single, flattened `sdoh_cleaned.csv` ready for frontend consumption.

-----------------------------------------------------------------------------------------------------------------------------------------------

### Healthcare Pipeline - FIHR (`process_fhir.py`)

The standard FHIR format represents a massive, highly nested JSON structure for every individual patient. To keep our serverless dashboard fast and responsive, this script flattens 1,000+ individual synthetic patient histories into a single, lightweight geographic metric. 

(We can find a larger sample size if we want, this was just to test the functionality of the scripts.
ONe thing to note is since the creators of Synthea is based in Massachusetts. When they generate their standard "1K Sample" test dataset, they default to generating patients in MA so the file stays small.)

#### Core Libraries
* **`json`**: Utilized to parse the complex, deeply nested dictionary structures inherent to FHIR Bundles.
* **`pandas`**: Used to aggregate the extracted patient data into regional cohorts using `.groupby()`.
* **`glob` **: Enables dynamic batch processing of all JSON files in the Synthea output directory, preventing hardcoded file paths.
* **`os`**: Ensures relative file pathing works across all team members' operating systems (Windows/Mac/Linux) without breaking.

#### The Processing Flow
1. **Batch Ingestion:** `glob` scans the `/data/raw/FIHR R4 Synthethic/...` directory and queues every patient JSON file for processing. Safety checks are included to skip corrupted files (`json.JSONDecodeError`).
2. **Double-Pass Extraction:** Because the order of resources within a FHIR Bundle array is not strictly guaranteed, the script makes two passes:
   * Pass 1 (Demographics): Locates the `Patient` resource to extract the geographic anchor (City, State, ZipCode).
   * Pass 2 (Encounters & Time): Locates `Encounter` resources, strictly filtering for hospital visits classified as Emergency (`class code: 'EMER'`). Crucially, it dives into the `period.start` object to extract the exact **Year** the ER visit occurred.
3. **Clinical Coding Extraction & Fallbacks:** For every ER visit, the script digs into the `reasonCode` block to extract the specific SNOMED-CT code and its human-readable `display` text. 
   * Data Integrity Guardrail: If the simulated EHR data is missing the human-readable text, the script defaults to `"Unknown Reason"` for the frontend display, while permanently retaining the SNOMED code in a separate `ER_Reason_Code` column.
4. **Spatio-Temporal Aggregation:** Instead of outputting a row for every patient, `pandas` aggregates the data by **Year**, **Location**, and **ER Reason**. It counts the number of unique occurrences, transforming individual patient histories into a Health metric (`Total_ER_Visits`) that can be mapped on a timeline.
5. **Output:** The script sorts by Year and highest-burden areas, exporting the flattened data as `fhir_burden_cleaned.csv`.

#### Architectural Decision: Geographic Aggregation
Instead of plotting individual patient records, our pipeline intentionally aggregates ER visits by Zip Code. This design choice was made to solve three specific engineering challenges:

1. **Data Alignment:** The CDC SVI dataset is measured at the geographic level (County). By aggregating the patient-level FHIR data into regional cohorts, we align the "grain" of both datasets, allowing for a clean, 1-to-1 data merge.
2. **Frontend Optimization:** Because this is a serverless application hosted on GitHub Pages, the user's browser must render the Plotly charts. Condensing gigabytes of raw JSON files into a single, lightweight CSV prevents browser crashes and guarantees instant load times.
3. **Privacy & Compliance:** Real-world health informatics requires strict adherence to HIPAA guidelines. By aggregating individual medical events into regional summaries, we successfully de-identify the synthetic patients, mirroring the exact reporting standards used by the CDC and WHO.

-----------------------------------------------------------------------------------------------------------------------------------------------


## The Master Merge (`merge_data.py`)

This is the final script in our backend pipeline. It acts as the master translator, taking our two completely different datasets (CDC SVI and Synthea FHIR) and snapping them together into a single, clean CSV file that our Plotly dashboard can read instantly. 

### How It Works (Step-by-Step)
1. **The Time Translator:** Synthea patients visit the ER every single day of the year (e.g., 2017, 2019), but the CDC only releases data every two years (2014, 2016, 2018...). The script safely "buckets" the hospital visits into the closest CDC reporting year so no patients get deleted during the merge.
2. **The Geographic Translator (HUD Crosswalk):** Synthea data uses Zip Codes, but CDC data uses County FIPS codes. We use the official **HUD ZIP-to-County Crosswalk** database to translate every synthetic patient's zip code into its correct 5-digit County code. 
3. **The Pivot (Squishing the Data):** The script takes the tall list of different ER visits (Asthma, COVID, Overdose) and pivots them sideways into clean, individual columns. 
4. **The Inner Merge:** Now that both datasets speak the exact same language (County FIPS Code + Year), we do a clean `pd.merge()` to fuse them together.

-----------------------------------------------------------------------------------------------------------------------------------------------

### Architectural Decisions & Edge Cases
When building this pipeline, we ran into several real-world data engineering hurdles. Here is how we solved them:

#### 1. Handling Overlapping County Borders (`RES_RATIO`)
**The Problem:** Zip codes are drawn by the Post Office, not the government. Because of this, a single zip code will often bleed across two different county lines. If we aren't careful, patients could be duplicated into the wrong county. 
**Our Solution:** We downloaded the official HUD crosswalk and utilized the `RES_RATIO` (Residential Ratio) column. Our script sorts the crosswalk by this ratio and drops duplicates, meaning we strictly assign ER visits to whichever county contains the *majority* of the residential houses for that zip code. 

#### 2. Flipping the Data (Long vs. Wide Format)
**The Problem:** Originally, our FHIR data was in a "Long" format (multiple rows for the exact same county, one for each disease). If we merged this directly with the CDC data, Pandas would have duplicated the county's poverty statistics over and over again, corrupting any future math or averages.
**Our Solution:** We used `pandas.pivot_table()` to convert the data into a "Wide" format. This forced the data into a strict 1-to-1 grain (Exactly One Row = One County Per Year). This is crucial for our front-end UI: Plotly doesn't have to run a slow filtering loop—it just instantly loads the column.

#### 3. Rolling Up vs. Splitting Down
**The Problem:** We had to decide whether to map the CDC data down to Zip Codes, or map the Patient data up to Counties.
**Our Solution:** In data science, you cannot reliably split statistical data downwards. If a county has a 15% poverty rate, we cannot accurately split that into its individual zip codes (because the wealth might be concentrated in just one neighborhood). Therefore, our architecture strictly "rolls up" the individual patient ER visits into the larger County buckets.
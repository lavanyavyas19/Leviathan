# app/core/ingestion_engine.py

import os
import pandas as pd
from datetime import datetime
from app.core.preprocessing import clean_and_preprocess  # updated import

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)

def run_ingestion_pipeline(csv_path: str = None) -> str:
    """
    Ingest AIS CSV, preprocess it, and save the processed file.
    """
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "ais_data.csv")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No AIS data found at: {csv_path}")

    print(f"✅ Found AIS data at: {csv_path}")
    df = pd.read_csv(csv_path)

    # --- Clean and preprocess ---
    df_clean = clean_and_preprocess(df)

    # --- Save processed output ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    processed_path = os.path.join(PROCESSED_DIR, f"ais_processed_{timestamp}.csv")
    df_clean.to_csv(processed_path, index=False)

    print(f"✅ Processed file saved to: {processed_path}")
    print(f"📊 Total records after cleaning: {len(df_clean)}")

    return processed_path

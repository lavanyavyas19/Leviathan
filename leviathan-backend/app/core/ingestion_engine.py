# app/core/ingestion_engine.py

import os
import pandas as pd
from datetime import datetime
from app.core.preprocessing import clean_and_preprocess
from app.utils.s3_upload import upload_clean_csv_to_s3  # make sure it exists correctly

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

def run_ingestion_pipeline(csv_path: str, clean_bucket: str) -> dict:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No AIS data found at: {csv_path}")

    df = pd.read_csv(csv_path)
    df_clean = clean_and_preprocess(df)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    processed_filename = f"ais_processed_{timestamp}.csv"
    local_processed_path = os.path.join(PROCESSED_DIR, processed_filename)
    df_clean.to_csv(local_processed_path, index=False)

    clean_key = f"clean/processed/date={datetime.now().date()}/{processed_filename}"
    s3_result = upload_clean_csv_to_s3(local_processed_path, clean_bucket, clean_key)

    if not s3_result["success"]:
        raise RuntimeError(s3_result["message"])

    return {
        "local_processed_path": local_processed_path,
        "clean_bucket": clean_bucket,
        "clean_key": clean_key,
        "clean_s3_uri": f"s3://{clean_bucket}/{clean_key}",
        "records_after_cleaning": len(df_clean)
    }

# app/core/ingestion_engine.py

import os
import pandas as pd
from datetime import datetime
from app.core.preprocessing import clean_and_preprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

# You can tune these depending on your RAM
READ_KWARGS = dict(
    low_memory=False,          # prevents chunked dtype guessing warnings
)

# Optional: if these columns exist, forcing types prevents mixed-type issues
# (comment out any you don't have)
DTYPE_HINTS = {
    # "mmsi": "Int64",
    # "vessel_type": "string",
    # "shipname": "string",
}


def _read_csv_auto(path: str) -> pd.DataFrame:
    """
    Reads .csv or .csv.gz safely. Pandas auto-detects gzip if extension is .gz,
    but we keep this helper so behavior is explicit and easy to tweak.
    """
    # compression="infer" handles .gz and normal .csv
    return pd.read_csv(
        path,
        compression="infer",
        dtype=DTYPE_HINTS if DTYPE_HINTS else None,
        **READ_KWARGS,
    )


def run_ingestion_pipeline(csv_path: str) -> str:
    """
    Ingest AIS CSV, preprocess it, and save the processed file.

    Returns:
        processed_path: path to cleaned CSV (not gz)
    """
    if not csv_path:
        raise ValueError("csv_path is required (no default fallback).")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No AIS data found at: {csv_path}")

    print(f"🔥 INGESTION INPUT FILE: {csv_path}")  # important

    # ---- Read ----
    df = _read_csv_auto(csv_path)
    print(f"📌 RAW rows loaded: {len(df)}")

    # ---- Clean / preprocess ----
    df_clean = clean_and_preprocess(df)

    # ---- Save ----
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    processed_path = os.path.join(PROCESSED_DIR, f"ais_processed_{timestamp}.csv")
    df_clean.to_csv(processed_path, index=False)

    print(f"✅ Processed file saved to: {processed_path}")
    print(f"📊 Total records after cleaning: {len(df_clean)}")

    return processed_path

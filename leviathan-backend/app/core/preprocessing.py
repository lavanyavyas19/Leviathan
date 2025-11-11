# app/core/preprocessing.py

import pandas as pd
import numpy as np

def clean_and_preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and standardizes AIS data for model input.
    Expected columns: MMSI, LAT, LON, SOG, COG, Vessel Type
    """
    # --- Normalize column names ---
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required_cols = ["mmsi", "lat", "lon", "sog", "cog", "vessel_type"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # --- Drop duplicates ---
    df = df.drop_duplicates(subset=["mmsi", "lat", "lon"], keep="last")

    # --- Handle invalid coordinates ---
    df = df[(df["lat"].between(-90, 90)) & (df["lon"].between(-180, 180))]

    # --- Handle invalid SOG/COG ---
    df["sog"] = pd.to_numeric(df["sog"], errors="coerce")
    df["cog"] = pd.to_numeric(df["cog"], errors="coerce")
    df = df.dropna(subset=["sog", "cog"])

    # --- Replace impossible values ---
    df["sog"] = df["sog"].clip(lower=0, upper=50)
    df["cog"] = df["cog"].clip(lower=0, upper=360)

    # --- Fill missing vessel types ---
    df["vessel_type"] = df["vessel_type"].fillna("Unknown")

    # --- Feature engineering example ---
    df["speed_class"] = pd.cut(df["sog"],
                               bins=[-1, 2, 10, 20, 50],
                               labels=["Stopped", "Slow", "Cruising", "Fast"])

    return df

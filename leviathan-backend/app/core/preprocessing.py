import pandas as pd
import numpy as np


def clean_and_preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and standardizes AIS data for model input.
    Designed to be safe for big data + consistent for downstream detection.
    """

    # Normalize column names
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Standardize schema
    df = df.rename(columns={
        "vesseltype": "vessel_type",
        "shiptype": "vessel_type",
        "ship_type": "vessel_type",
        "basedatetime": "timestamp",
        "vesselname": "vessel_name",
        "shipname": "vessel_name",
    })

    # Required columns (timestamp optional but highly recommended)
    required_cols = ["mmsi", "lat", "lon", "sog", "cog", "vessel_type"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Force numeric types early
    df["mmsi"] = pd.to_numeric(df["mmsi"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["sog"] = pd.to_numeric(df["sog"], errors="coerce")
    df["cog"] = pd.to_numeric(df["cog"], errors="coerce")

    df = df.dropna(subset=["mmsi", "lat", "lon", "sog", "cog"])

    # Coordinate validation
    df = df[df["lat"].between(-90, 90) & df["lon"].between(-180, 180)]

    # Parse timestamp if present
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        # keep rows without timestamp? choose one:
        df = df.dropna(subset=["timestamp"])

        # Sort correctly for downstream "last row per mmsi"
        df = df.sort_values(["mmsi", "timestamp"])

        # DEDUPE: one message per MMSI per timestamp
        df = df.drop_duplicates(subset=["mmsi", "timestamp"], keep="last")
    else:
        # Fallback: at least sort by mmsi if timestamp missing
        df = df.sort_values(["mmsi"])

    # Clip SOG / COG
    df["sog"] = df["sog"].clip(0, 50)
    df["cog"] = df["cog"].clip(0, 360)

    # Vessel type/name
    df["vessel_type"] = df["vessel_type"].fillna("Unknown").astype(str)
    df["vessel_name"] = df.get("vessel_name", "Unknown")
    df["vessel_name"] = df["vessel_name"].fillna("Unknown").astype(str)

    # Feature engineering
    df["speed_class"] = pd.cut(
        df["sog"],
        bins=[-1, 2, 10, 20, 50],
        labels=["Stopped", "Slow", "Cruising", "Fast"]
    )

    return df

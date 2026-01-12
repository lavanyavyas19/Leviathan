# app/core/preprocessing.py

import pandas as pd
import numpy as np
from typing import Optional, Dict

GULF_BOUNDS = {
    "min_lat": 18.0,   # you can adjust
    "max_lat": 31.5,
    "min_lon": -98.5,
    "max_lon": -80.0,
}

# column aliases from common AIS sources (MarineCadastre included)
ALIASES: Dict[str, list] = {
    "timestamp": ["basedatetime", "base_date_time", "time", "timestamp", "datetime"],
    "mmsi": ["mmsi"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "long", "longitude"],
    "sog": ["sog", "speed_over_ground", "speed"],
    "cog": ["cog", "course_over_ground", "course"],
    "vessel_type": ["vessel_type", "vesseltype", "shiptype", "type"],
    "heading": ["heading", "hdg"],
    "status": ["status", "navstatus", "navigation_status"],
}

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def _pick_col(df: pd.DataFrame, logical_name: str) -> Optional[str]:
    for c in ALIASES.get(logical_name, []):
        if c in df.columns:
            return c
    return None

def clean_and_preprocess(
    df: pd.DataFrame,
    bounds: Optional[dict] = GULF_BOUNDS,
    require_cog: bool = False,
) -> pd.DataFrame:
    """
    Flexible AIS cleaner for MarineCadastre-style CSVs.
    Outputs standardized columns:
      timestamp, mmsi, lat, lon, sog, cog, vessel_type, heading, status, speed_class
    """
    df = _normalize_cols(df)

    # Resolve actual column names
    ts_col = _pick_col(df, "timestamp")
    mmsi_col = _pick_col(df, "mmsi")
    lat_col = _pick_col(df, "lat")
    lon_col = _pick_col(df, "lon")
    sog_col = _pick_col(df, "sog")
    cog_col = _pick_col(df, "cog")
    vt_col  = _pick_col(df, "vessel_type")
    hdg_col = _pick_col(df, "heading")
    st_col  = _pick_col(df, "status")

    # Minimal requirements for your whole project
    for col, name in [(mmsi_col, "mmsi"), (lat_col, "lat"), (lon_col, "lon"), (sog_col, "sog")]:
        if col is None:
            raise ValueError(f"Missing required column: {name}")

    # Standardize names
    out = pd.DataFrame()
    out["mmsi"] = pd.to_numeric(df[mmsi_col], errors="coerce").astype("Int64")
    out["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    out["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    out["sog"] = pd.to_numeric(df[sog_col], errors="coerce")

    # Optional fields
    if ts_col is not None:
        out["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    else:
        # if no timestamp, create NaT (map time slider will be limited)
        out["timestamp"] = pd.NaT

    if cog_col is not None:
        out["cog"] = pd.to_numeric(df[cog_col], errors="coerce")
    else:
        out["cog"] = np.nan

    out["vessel_type"] = df[vt_col] if vt_col is not None else "Unknown"
    out["heading"] = pd.to_numeric(df[hdg_col], errors="coerce") if hdg_col is not None else np.nan
    out["status"] = df[st_col] if st_col is not None else "Unknown"

    # Drop bad essentials
    out = out.dropna(subset=["mmsi", "lat", "lon", "sog"])
    out = out[(out["lat"].between(-90, 90)) & (out["lon"].between(-180, 180))]

    # Gulf filter (VERY important for your map + compute)
    if bounds:
        out = out[
            (out["lat"].between(bounds["min_lat"], bounds["max_lat"])) &
            (out["lon"].between(bounds["min_lon"], bounds["max_lon"]))
        ]

    # Clean SOG
    out["sog"] = out["sog"].clip(lower=0, upper=60)  # allow up to 60 for fast craft

    # Clean COG: valid range 0-360, anything else -> NaN
    out.loc[~out["cog"].between(0, 360), "cog"] = np.nan
    if require_cog:
        out = out.dropna(subset=["cog"])

    # Timestamp cleaning
    if "timestamp" in out.columns:
        # Drop rows where timestamp exists but is invalid
        # (keeping NaT rows can break loitering models)
        out = out.dropna(subset=["timestamp"])

    # Dedupe: keep last record per (mmsi, timestamp) instead of (mmsi, lat, lon)
    out = out.sort_values(["mmsi", "timestamp"])
    out = out.drop_duplicates(subset=["mmsi", "timestamp"], keep="last")

    # Speed class
    out["speed_class"] = pd.cut(
        out["sog"],
        bins=[-0.01, 0.5, 2, 10, 20, 60],
        labels=["Stopped", "Drifting", "Slow", "Cruising", "Fast"],
    )

    return out

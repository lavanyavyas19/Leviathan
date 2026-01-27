# app/core/anomaly_detection.py

import os
import pandas as pd
import numpy as np
import joblib
from sklearn.cluster import DBSCAN

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "app", "ml")

SPOOFING_MODEL_PATH = os.path.join(MODEL_DIR, "spoofing_model.pkl")

LOITERING_EPS_NM = 1.0
LOITERING_MIN_SAMPLES = 5
LOITERING_MIN_DWELL_HOURS = 3
LOW_SPEED_THRESHOLD = 2.0


def haversine_nm_vec(lat1, lon1, lat2, lon2):
    """
    Vectorized haversine distance in nautical miles.
    lat/lon can be numpy arrays or pandas Series.
    """
    lat1 = np.radians(lat1.astype(float))
    lon1 = np.radians(lon1.astype(float))
    lat2 = np.radians(lat2.astype(float))
    lon2 = np.radians(lon2.astype(float))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    km = 6371.0088 * c
    nm = km * 0.539957
    return nm


def classify_spoofing_severity(score: float) -> str:
    if score < -0.5:
        return "high"
    elif score < -0.2:
        return "medium"
    else:
        return "low"


def classify_loitering_severity(cluster_size: int) -> str:
    if cluster_size > 15:
        return "high"
    elif cluster_size >= 5:
        return "medium"
    else:
        return "low"


def _circular_heading_change(series: pd.Series) -> pd.Series:
    """
    Correct heading diff for 0-360 wrap.
    """
    diff = series.diff()
    diff = diff.abs()
    # convert e.g. 358 -> 2
    diff = np.minimum(diff, 360 - diff)
    return diff.fillna(0)


def detect_spoofing_events(df: pd.DataFrame) -> pd.DataFrame:
    empty_cols = ["mmsi", "lat", "lon", "timestamp", "score", "severity", "type"]

    if not os.path.exists(SPOOFING_MODEL_PATH):
        print("⚠️ Spoofing model not found, skipping spoofing detection")
        return pd.DataFrame(columns=empty_cols)

    try:
        model = joblib.load(SPOOFING_MODEL_PATH)
    except Exception as e:
        print(f"⚠️ Failed to load spoofing model: {e}")
        return pd.DataFrame(columns=empty_cols)

    required_cols = ["mmsi", "lat", "lon", "sog", "cog"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        print(f"⚠️ Missing columns for spoofing detection: {missing_cols}")
        return pd.DataFrame(columns=empty_cols)

    df = df.copy()

    # Sort
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values(by=["mmsi", "timestamp"])
    else:
        df = df.sort_values(by=["mmsi"])

    # Ensure numeric
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["sog"] = pd.to_numeric(df["sog"], errors="coerce")
    df["cog"] = pd.to_numeric(df["cog"], errors="coerce")

    # Core features
    df["speed"] = df["sog"].clip(0, 60).fillna(0)

    # ✅ Correct heading change for wrap-around
    df["heading_change"] = df.groupby("mmsi")["cog"].apply(_circular_heading_change).reset_index(level=0, drop=True)

    # Jump distance
    lat_prev = df.groupby("mmsi")["lat"].shift(1)
    lon_prev = df.groupby("mmsi")["lon"].shift(1)

    df["jump_distance"] = haversine_nm_vec(df["lat"].fillna(0), df["lon"].fillna(0), lat_prev.fillna(0), lon_prev.fillna(0))
    df["jump_distance"] = df["jump_distance"].replace([np.inf, -np.inf], 0).fillna(0)

    # Time gap
    if "timestamp" in df.columns:
        df["time_gap"] = df.groupby("mmsi")["timestamp"].diff().dt.total_seconds().fillna(0)
    else:
        df["time_gap"] = 0

    # Speed change & acceleration
    df["speed_change"] = df.groupby("mmsi")["speed"].diff().abs().fillna(0)
    df["acceleration"] = np.where(df["time_gap"] > 0, df["speed_change"] / df["time_gap"], 0)

    # Turn rate
    df["turn_rate"] = np.where(df["time_gap"] > 0, df["heading_change"] / df["time_gap"], 0)

    features = ["speed", "heading_change", "jump_distance", "time_gap", "speed_change", "acceleration", "turn_rate"]
    X = df[features].replace([np.inf, -np.inf], 0).fillna(0).values

    # Predict + score (safe)
    predictions = model.predict(X)
    if hasattr(model, "decision_function"):
        scores = model.decision_function(X)
    elif hasattr(model, "score_samples"):
        scores = model.score_samples(X)
    else:
        # fallback: no score available
        scores = np.zeros(len(df), dtype=float)

    spoofing_mask = predictions == -1
    spoofing_df = df.loc[spoofing_mask].copy()

    if spoofing_df.empty:
        return pd.DataFrame(columns=empty_cols)

    spoofing_df["score"] = scores[spoofing_mask]
    spoofing_df["severity"] = spoofing_df["score"].apply(classify_spoofing_severity)
    spoofing_df["type"] = "spoofing"

    # Ensure timestamp exists in output
    if "timestamp" not in spoofing_df.columns:
        spoofing_df["timestamp"] = None

    return spoofing_df[["mmsi", "lat", "lon", "timestamp", "score", "severity", "type"]].copy()


def detect_loitering_events(df: pd.DataFrame) -> pd.DataFrame:
    empty_cols = ["mmsi", "lat", "lon", "timestamp", "cluster_size", "severity", "type"]

    required_cols = ["mmsi", "lat", "lon", "sog"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        print(f"⚠️ Missing columns for loitering detection: {missing_cols}")
        return pd.DataFrame(columns=empty_cols)

    df = df.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["sog"] = pd.to_numeric(df["sog"], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Low-speed filter
    low_speed_df = df[df["sog"] <= LOW_SPEED_THRESHOLD].copy()
    low_speed_df = low_speed_df.dropna(subset=["lat", "lon", "mmsi"])

    if low_speed_df.empty:
        return pd.DataFrame(columns=empty_cols)

    results = []

    # ✅ DBSCAN using haversine metric
    # Earth radius in km; 1 NM = 1.852 km
    eps_km = LOITERING_EPS_NM * 1.852
    eps_rad = eps_km / 6371.0088

    for mmsi, group in low_speed_df.groupby("mmsi"):
        if len(group) < LOITERING_MIN_SAMPLES:
            continue

        # Sort by time if possible for dwell time calc
        if "timestamp" in group.columns:
            group = group.sort_values("timestamp")

        coords_rad = np.radians(group[["lat", "lon"]].values.astype(float))

        dbscan = DBSCAN(eps=eps_rad, min_samples=LOITERING_MIN_SAMPLES, metric="haversine")
        labels = dbscan.fit_predict(coords_rad)

        for cluster_id in set(labels):
            if cluster_id == -1:
                continue

            cluster_points = group[labels == cluster_id]
            if len(cluster_points) < LOITERING_MIN_SAMPLES:
                continue

            centroid_lat = float(cluster_points["lat"].mean())
            centroid_lon = float(cluster_points["lon"].mean())
            avg_speed = float(cluster_points["sog"].mean())

            # ✅ Real dwell time if timestamps exist
            dwell_time_hours = None
            timestamp = None
            if "timestamp" in cluster_points.columns and cluster_points["timestamp"].notna().any():
                tmin = cluster_points["timestamp"].min()
                tmax = cluster_points["timestamp"].max()
                timestamp = tmin
                dwell_time_hours = (tmax - tmin).total_seconds() / 3600.0
            else:
                # fallback estimate (6 min intervals)
                dwell_time_hours = len(cluster_points) * 0.1

            if dwell_time_hours >= LOITERING_MIN_DWELL_HOURS:
                cluster_size = int(len(cluster_points))
                severity = classify_loitering_severity(cluster_size)

                results.append({
                    "mmsi": mmsi,
                    "lat": centroid_lat,
                    "lon": centroid_lon,
                    "timestamp": timestamp,
                    "cluster_size": cluster_size,
                    "severity": severity,
                    "type": "loitering",
                    "avg_speed": avg_speed,
                    "dwell_time_hr": float(dwell_time_hours),
                })

    if not results:
        return pd.DataFrame(columns=empty_cols)

    return pd.DataFrame(results)

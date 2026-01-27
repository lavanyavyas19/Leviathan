# train_loitering_model.py
import os
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import joblib
import pyarrow.parquet as pq

# ================= CONFIGURATION =================
PARQUET_PATH = r"/Users/lavanyavyas/Desktop/Leviathan-main/leviathan-backend/data/ais_15_days_training.parquet"

EPS_NM = 1.0
MIN_SAMPLES = 5
MIN_DWELL_HOURS = 3
LOW_SPEED_THRESHOLD = 2.0

MODEL_DIR = os.path.join(os.path.dirname(__file__), "app", "ml")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "loitering_model.pkl")

# ================= SEVERITY =================
def classify_loitering_severity(cluster_size: int) -> str:
    if cluster_size > 15:
        return "high"
    elif cluster_size >= 5:
        return "medium"
    return "low"

def detect_loitering(df_chunk):
    results = []

    # --- clean types ---
    df_chunk = df_chunk.copy()
    df_chunk["lat"] = pd.to_numeric(df_chunk["lat"], errors="coerce")
    df_chunk["lon"] = pd.to_numeric(df_chunk["lon"], errors="coerce")
    df_chunk["sog"] = pd.to_numeric(df_chunk["sog"], errors="coerce")
    df_chunk["timestamp"] = pd.to_datetime(df_chunk["timestamp"], errors="coerce")

    df_chunk = df_chunk.dropna(subset=["mmsi", "lat", "lon", "sog"])
    df_chunk = df_chunk[(df_chunk["lat"].between(-90, 90)) & (df_chunk["lon"].between(-180, 180))]

    # ✅ low-speed filter BEFORE clustering
    df_chunk = df_chunk[df_chunk["sog"] <= LOW_SPEED_THRESHOLD].copy()
    if df_chunk.empty:
        return pd.DataFrame(columns=["mmsi","lat","lon","timestamp","cluster_size","severity","type","avg_speed","dwell_time_hr"])

    # DBSCAN params for haversine
    eps_km = EPS_NM * 1.852
    eps_rad = eps_km / 6371.0088

    for mmsi, vessel_data in df_chunk.groupby("mmsi"):
        if len(vessel_data) < MIN_SAMPLES:
            continue

        # sort for dwell time calc
        vessel_data = vessel_data.sort_values("timestamp")

        coords_rad = np.radians(vessel_data[["lat", "lon"]].values.astype(float))

        db = DBSCAN(
            eps=eps_rad,
            min_samples=MIN_SAMPLES,
            metric="haversine"
        )
        labels = db.fit_predict(coords_rad)

        for cluster_id in set(labels):
            if cluster_id == -1:
                continue

            cluster_points = vessel_data[labels == cluster_id]
            if len(cluster_points) < MIN_SAMPLES:
                continue

            # ✅ real dwell time from timestamps
            dwell_time_hours = None
            timestamp = None
            if cluster_points["timestamp"].notna().any():
                tmin = cluster_points["timestamp"].min()
                tmax = cluster_points["timestamp"].max()
                timestamp = tmin
                dwell_time_hours = (tmax - tmin).total_seconds() / 3600.0
            else:
                # fallback if timestamps missing
                dwell_time_hours = len(cluster_points) * 0.1

            if dwell_time_hours < MIN_DWELL_HOURS:
                continue

            centroid_lat = float(cluster_points["lat"].mean())
            centroid_lon = float(cluster_points["lon"].mean())
            avg_speed = float(cluster_points["sog"].mean())
            cluster_size = int(len(cluster_points))

            results.append({
                "mmsi": mmsi,
                "lat": centroid_lat,
                "lon": centroid_lon,
                "timestamp": timestamp,
                "cluster_size": cluster_size,
                "severity": classify_loitering_severity(cluster_size),
                "type": "loitering",
                "avg_speed": avg_speed,
                "dwell_time_hr": float(dwell_time_hours),
            })

    return pd.DataFrame(results)

# ================= MAIN =================
print("📂 Loading parquet in row groups...")
table = pq.ParquetFile(PARQUET_PATH)
all_results = []

for i in range(table.num_row_groups):
    chunk_table = table.read_row_group(i, columns=["mmsi", "lat", "lon", "sog", "timestamp"])
    chunk = chunk_table.to_pandas()
    print(f"Processing row group {i+1}/{table.num_row_groups} with {len(chunk)} rows...")
    all_results.append(detect_loitering(chunk))

final_results = pd.concat(all_results, ignore_index=True)

print("\n✅ Detected", len(final_results), "loitering events (cluster-level, not row-level).")
print(final_results.head())

joblib.dump(final_results, MODEL_PATH)
print(f"💾 Saved to: {MODEL_PATH}")

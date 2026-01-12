# train_loitering_model.py
import os
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from geopy.distance import great_circle
import joblib
import gdown


# 1️⃣ CONFIGURATION

DRIVE_URL = "https://drive.google.com/file/d/1DkLo9Nv_XFmrakPscNhzEsV843QS7tEq/view?usp=sharing"

# DBSCAN hyperparameters
EPS_NM = 1.0          # Radius in nautical miles for clustering
MIN_SAMPLES = 5       # Minimum points per cluster
MIN_DWELL_HOURS = 3   # Minimum loitering time
LOW_SPEED_THRESHOLD = 2.0  # SOG (knots) threshold for “loitering”

PREFERRED_PATHS = [
    "ais_data.csv",
    os.path.join("data", "processed", "combined_ais.csv"),
    os.path.join("data", "raw", "combined_ais.csv")
]


# 2️⃣ CSV HANDLER — FIND OR DOWNLOAD DATA

def find_csv():
    for p in PREFERRED_PATHS:
        if os.path.exists(p):
            print(f"✅ Found local AIS data at: {p}")
            return p

    print("📡 Local CSV not found. Downloading from Google Drive...")
    file_id = DRIVE_URL.split("/d/")[1].split("/")[0]
    output = "ais_data.csv"
    gdown.download(f"https://drive.google.com/uc?id={file_id}", output, quiet=False)

    if os.path.exists(output):
        print(f"✅ Downloaded AIS CSV to: {output}")
        return output
    else:
        raise FileNotFoundError("❌ Could not download AIS CSV from Google Drive.")



# 3️⃣ LOAD AND PREPROCESS DATA

csv_path = find_csv()
df = pd.read_csv(csv_path)

# Normalize column names
df.columns = [c.strip().lower() for c in df.columns]

# Rename variants for consistency
rename_map = {
    "long": "lon",
    "longitude": "lon",
    "latitude": "lat",
    "vessel type": "vesseltype",
    "vessel_type": "vesseltype"
}
df.rename(columns=rename_map, inplace=True)

# Verify required columns
REQUIRED_COLUMNS = ["mmsi", "lat", "lon", "sog", "cog"]
for key in REQUIRED_COLUMNS:
    if key not in df.columns:
        raise ValueError(f"CSV missing required column: {key}")

print("✅ CSV columns verified:", list(df.columns))

# Drop rows with missing coordinates
df.dropna(subset=["lat", "lon"], inplace=True)



# 4️⃣ HELPER — DISTANCE CALCULATOR

def haversine_nm(lat1, lon1, lat2, lon2):
    km = great_circle((lat1, lon1), (lat2, lon2)).km
    return km * 0.539957  # convert km → nautical miles



# 5️⃣ LOITERING DETECTION USING DBSCAN

def detect_loitering(df, eps_nm=EPS_NM, min_samples=MIN_SAMPLES, min_dwell_hours=MIN_DWELL_HOURS):
    results = []

    for mmsi, vessel_data in df.groupby("mmsi"):
        if len(vessel_data) < min_samples:
            continue

        coords = vessel_data[["lat", "lon"]].to_numpy()
        kms_per_radian = 6371.0088
        eps_km = eps_nm * 1.852
        db = DBSCAN(
            eps=eps_km / kms_per_radian,
            min_samples=min_samples,
            algorithm='ball_tree',
            metric='haversine'
        )
        db.fit(np.radians(coords))

        vessel_data["cluster"] = db.labels_

        for cluster_id in set(db.labels_):
            if cluster_id == -1:
                continue

            cluster_points = vessel_data[vessel_data["cluster"] == cluster_id]
            avg_speed = cluster_points["sog"].mean()
            dwell_time_hours = len(cluster_points) * 0.1  # assuming ~6-min sampling interval

            if dwell_time_hours >= min_dwell_hours and avg_speed <= LOW_SPEED_THRESHOLD:
                centroid = cluster_points[["lat", "lon"]].mean().values.tolist()
                results.append({
                    "mmsi": mmsi,
                    "cluster_id": int(cluster_id),
                    "centroid_lat": centroid[0],
                    "centroid_lon": centroid[1],
                    "avg_speed_knots": round(avg_speed, 2),
                    "dwell_time_hr": round(dwell_time_hours, 2)
                })

    return pd.DataFrame(results)



# 6️⃣ TRAIN & SAVE MODEL

print("\n🚢 Detecting loitering behaviour...")
events = detect_loitering(df)

if not events.empty:
    print(f"✅ Detected {len(events)} loitering events.")
    print(events.head())
else:
    print("⚠️ No loitering detected in dataset.")

# Save results
model_dir = os.path.join(os.path.dirname(__file__), "app", "ml")
os.makedirs(model_dir, exist_ok=True)
model_path = os.path.join(model_dir, "loitering_model.pkl")
joblib.dump(events, model_path)

print(f"💾 Loitering results saved to {model_path}")

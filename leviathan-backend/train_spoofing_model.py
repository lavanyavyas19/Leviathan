# train_spoofing_model.py (improved)

import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import gdown

drive_url = "https://drive.google.com/file/d/1bzL9Cw8_MUVAqccKHrm0t9lntUIwq9_E/view?usp=drive_link"
file_id = drive_url.split("/d/")[1].split("/")[0]
download_url = f"https://drive.google.com/uc?id={file_id}"

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

csv_file = os.path.join(DATA_DIR, "ais_data.csv")

if not os.path.exists(csv_file):
    print("📥 Downloading dataset from Google Drive...")
    gdown.download(download_url, csv_file, quiet=False)
    print("✅ Download complete!")
else:
    print("✅ Dataset already exists locally")

df = pd.read_csv(csv_file)
print(f"✅ Loaded {len(df)} rows")

REQUIRED_COLS = ["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG"]
for col in REQUIRED_COLS:
    if col not in df.columns:
        raise ValueError(f"❌ Missing required column: {col}")

# ---- parse & clean ----
df["BaseDateTime"] = pd.to_datetime(df["BaseDateTime"], errors="coerce")
df = df.dropna(subset=["BaseDateTime", "MMSI"])

df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
df["SOG"] = pd.to_numeric(df["SOG"], errors="coerce")
df["COG"] = pd.to_numeric(df["COG"], errors="coerce")

# drop invalid coordinates
df = df.dropna(subset=["LAT", "LON"])
df = df[(df["LAT"].between(-90, 90)) & (df["LON"].between(-180, 180))]

df = df.sort_values(by=["MMSI", "BaseDateTime"])

# ---- features ----
def haversine_nm_vec(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1.astype(float))
    lon1 = np.radians(lon1.astype(float))
    lat2 = np.radians(lat2.astype(float))
    lon2 = np.radians(lon2.astype(float))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371.0088 * c
    return km * 0.539957

def circular_heading_change(s):
    diff = s.diff().abs()
    diff = np.minimum(diff, 360 - diff)
    return diff.fillna(0)

df["speed"] = df["SOG"].clip(0, 60).fillna(0)

df["heading_change"] = (
    df.groupby("MMSI")["COG"]
    .apply(circular_heading_change)
    .reset_index(level=0, drop=True)
)

lat_prev = df.groupby("MMSI")["LAT"].shift(1)
lon_prev = df.groupby("MMSI")["LON"].shift(1)

df["jump_distance"] = 0.0
mask = lat_prev.notna() & lon_prev.notna()
df.loc[mask, "jump_distance"] = haversine_nm_vec(
    df.loc[mask, "LAT"], df.loc[mask, "LON"],
    lat_prev.loc[mask], lon_prev.loc[mask]
)

df["time_gap"] = (
    df.groupby("MMSI")["BaseDateTime"]
    .diff()
    .dt.total_seconds()
    .replace([np.inf, -np.inf], np.nan)
    .fillna(0)
)

df["speed_change"] = df.groupby("MMSI")["speed"].diff().abs().fillna(0)

safe_gap = df["time_gap"].where(df["time_gap"] >= 30, np.nan)
df["acceleration"] = (df["speed_change"] / safe_gap).replace([np.inf, -np.inf], 0).fillna(0)
df["turn_rate"] = (df["heading_change"] / safe_gap).replace([np.inf, -np.inf], 0).fillna(0)

FEATURES = ["speed","heading_change","jump_distance","time_gap","speed_change","acceleration","turn_rate"]
X = df[FEATURES].replace([np.inf, -np.inf], 0).fillna(0).values

print(f"🧠 Feature matrix: {X.shape}")

# Optional: sample for training speed + better generalization
MAX_ROWS = 800_000
if len(X) > MAX_ROWS:
    idx = np.random.RandomState(42).choice(len(X), size=MAX_ROWS, replace=False)
    X_train = X[idx]
    print(f"🎯 Sampling to {MAX_ROWS} rows for training")
else:
    X_train = X

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", IsolationForest(
        n_estimators=300,
        contamination=0.01,   # ✅ WAY more realistic start
        random_state=42,
        n_jobs=-1
    ))
])

print("⚙️ Training Isolation Forest...")
pipeline.fit(X_train)
print("✅ Model training complete!")

model_dir = os.path.join(os.path.dirname(__file__), "app", "ml")
os.makedirs(model_dir, exist_ok=True)

model_path = os.path.join(model_dir, "spoofing_model.pkl")
joblib.dump(pipeline, model_path)
print(f"💾 Model saved to: {model_path}")

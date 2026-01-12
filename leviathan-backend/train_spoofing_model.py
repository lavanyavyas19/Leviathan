import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from datetime import datetime
import gdown

# 1. Download dataset
drive_url = "https://drive.google.com/file/d/1DkLo9Nv_XFmrakPscNhzEsV843QS7tEq/view?usp=sharing"
file_id = drive_url.split("/d/")[1].split("/")[0]
download_url = f"https://drive.google.com/uc?id={file_id}"
csv_file = "ais_data.csv"

print("📥 Downloading dataset from Google Drive...")
gdown.download(download_url, csv_file, quiet=False)
print("✅ Download complete!")

# 2. Load dataset
try:
    df = pd.read_csv(csv_file)
except Exception as e:
    raise ValueError(f"❌ Failed to read CSV. Error: {e}")

print(f"✅ Loaded {len(df)} rows and {len(df.columns)} columns.")
print("📊 Columns:", list(df.columns))

# 3. Ensure proper columns exist
required_base = ["BaseDateTime", "LAT", "LON", "SOG", "COG"]
for col in required_base:
    if col not in df.columns:
        raise ValueError(f"❌ Missing column '{col}' in dataset.")

# 4. Sort and prepare data
df = df.sort_values(by=["MMSI", "BaseDateTime"])
df["BaseDateTime"] = pd.to_datetime(df["BaseDateTime"], errors="coerce")

# 5. Compute derived features
def haversine(lat1, lon1, lat2, lon2):
    """Compute distance between two lat/lon pairs in nautical miles."""
    R = 6371  # Earth radius (km)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c * 0.539957  # km → nautical miles

df["speed"] = df["SOG"]

# Compute per MMSI group
df["heading_change"] = df.groupby("MMSI")["COG"].diff().fillna(0).abs()
df["jump_distance"] = df.groupby("MMSI").apply(
    lambda g: haversine(g["LAT"], g["LON"], g["LAT"].shift(), g["LON"].shift())
).reset_index(level=0, drop=True).fillna(0)

df["time_gap"] = df.groupby("MMSI")["BaseDateTime"].diff().dt.total_seconds().fillna(0)

# Replace infinities and NaNs
df = df.replace([np.inf, -np.inf], 0).fillna(0)

# 6. Select required features
X = df[["speed", "heading_change", "jump_distance", "time_gap"]].values

# 7. Train model with scaler
print("⚙️ Training Isolation Forest model...")
pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", IsolationForest(
        n_estimators=200,
        contamination=0.15,
        random_state=42
    ))
])

pipeline.fit(X)
print("✅ Model training complete!")

# 8. Save model
model_dir = os.path.join(os.path.dirname(__file__), "app", "ml")
os.makedirs(model_dir, exist_ok=True)

model_path = os.path.join(model_dir, "spoofing_model.pkl")
joblib.dump(pipeline, model_path)
print(f"💾 Model saved to: {model_path}")

# 9. Quick test
test_sample = np.array([[0, 0, 0, 0]])
prediction = pipeline.predict(test_sample)[0]
score = pipeline.named_steps["model"].decision_function(
    pipeline.named_steps["scaler"].transform(test_sample)
)[0]

print("\n🧩 Model expects exactly these 4 features: ['speed', 'heading_change', 'jump_distance', 'time_gap']")
print(f"✅ Test sample result: {'Spoofing' if prediction == -1 else 'Normal'} (score: {score:.4f})")




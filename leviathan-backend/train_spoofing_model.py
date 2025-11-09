# train_spoofing_model.py
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
import gdown


# 1. Download CSV from Google Drive

url = "https://drive.google.com/file/d/1DkLo9Nv_XFmrakPscNhzEsV843QS7tEq/view?usp=sharing"

csv_file = "ais_data.csv"

print("📥 Downloading dataset from Google Drive...")
gdown.download(url, csv_file, quiet=False)
print("✅ Download complete!")


# 2. Load Dataset

df = pd.read_csv(csv_file)
print(f"✅ CSV loaded successfully with {len(df)} rows and {len(df.columns)} columns.")
print("📊 Columns:", list(df.columns))


# 3. Select numeric columns only

df_numeric = df.select_dtypes(include=[np.number])

if df_numeric.empty:
    raise ValueError("❌ No numeric columns found in the dataset for training.")

print(f"✅ Using {len(df_numeric.columns)} numeric features: {list(df_numeric.columns)}")

X = df_numeric.values


# 4. Train Isolation Forest Model

print("⚙️ Training Isolation Forest model...")
model = IsolationForest(
    n_estimators=200,
    contamination=0.15,
    random_state=42
)
model.fit(X)
print("✅ Model training complete!")


# 5. Save Trained Model

model_dir = os.path.join(os.path.dirname(__file__), "app", "ml")
os.makedirs(model_dir, exist_ok=True)

model_path = os.path.join(model_dir, "spoofing_model.pkl")
joblib.dump(model, model_path)
print(f"💾 Model saved to: {model_path}")


# 6. Quick Test

test_sample = np.array([X[0]])  # Just test with first row or any random row
prediction = model.predict(test_sample)[0]
score = model.decision_function(test_sample)[0]

if prediction == -1:
    print(f"⚠️  Spoofing detected (score: {score:.4f})")
else:
    print(f"✅ Normal behaviour (score: {score:.4f})")

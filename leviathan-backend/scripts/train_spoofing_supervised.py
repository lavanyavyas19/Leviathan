import os
import numpy as np
import pandas as pd
import joblib

from sklearn.metrics import precision_recall_curve, average_precision_score
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from app.core.spoofing_features import add_spoofing_features

from app.core.preprocessing import clean_and_preprocess


DATA_PATH = "data/synthetic/ais_synth_labeled_20260219_121428.csv"
MODEL_OUT = "app/ml/spoofing_model.pkl"
THRESH_OUT = "app/ml/spoofing_threshold.txt"

FEATURES = [
    "speed",
    "heading_change",
    "jump_distance",
    "time_gap",
    "speed_change",
    "acceleration",
    "turn_rate",
]

MIN_PRECISION = float(os.getenv("MIN_SPOOFING_PRECISION", "0.40"))

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
    return km * 0.539957  # nautical miles


def circular_heading_change(series: pd.Series) -> pd.Series:
    diff = series.diff().abs()
    diff = np.minimum(diff, 360 - diff)
    return diff.fillna(0)



def build_features(df: pd.DataFrame):
    df = add_spoofing_features(df)

    missing = [c for c in FEATURES + ["gt_spoofing"] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after feature engineering: {missing}")

    X = df[FEATURES].replace([np.inf, -np.inf], 0).fillna(0)
    y = (df["gt_spoofing"] == 1).astype(int)
    return X, y



def time_split(df: pd.DataFrame, ts_col="timestamp", val_frac=0.2):
    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=[ts_col])
    df = df.sort_values(ts_col).reset_index(drop=True)

    cut = int(len(df) * (1 - val_frac))
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def pick_threshold_for_precision(y_true, y_prob, min_precision=0.80):
    p, r, thr = precision_recall_curve(y_true, y_prob)
    # p and r are length N+1, thr is length N
    # align: use p[:-1], r[:-1] with thr
    p2, r2 = p[:-1], r[:-1]

    ok = np.where(p2 >= min_precision)[0]
    if len(ok) == 0:
        # fallback: best F1
        f1 = 2 * p2 * r2 / (p2 + r2 + 1e-12)
        best = int(np.argmax(f1))
        return float(thr[best]), float(p2[best]), float(r2[best]), float(f1[best])

    # among those meeting precision, maximize recall (or F1)
    best = int(ok[np.argmax(r2[ok])])
    f1_best = float(2 * p2[best] * r2[best] / (p2[best] + r2[best] + 1e-12))
    return float(thr[best]), float(p2[best]), float(r2[best]), f1_best


def pick_threshold_max_f1(y_true, y_prob):
    p, r, thr = precision_recall_curve(y_true, y_prob)
    p2, r2 = p[:-1], r[:-1]
    f1 = 2 * p2 * r2 / (p2 + r2 + 1e-12)
    best = int(np.argmax(f1))
    return float(thr[best]), float(p2[best]), float(r2[best]), float(f1[best])


def main():
    print("📥 Loading dataset...")
    df = pd.read_csv(DATA_PATH, low_memory=False)
    print("rows:", len(df))

    print("🧹 clean_and_preprocess...")
    df = clean_and_preprocess(df)

    # MUST add engineered features BEFORE splitting + building X/y
    df = add_spoofing_features(df)

    if "timestamp" not in df.columns:
        raise ValueError("No timestamp column after preprocessing.")

    # ✅ THIS LINE must exist BEFORE build_features(train_df)
    train_df, val_df = time_split(df, "timestamp", val_frac=0.2)

    print("train rows:", len(train_df), "val rows:", len(val_df))
    print("train positives:", int((train_df["gt_spoofing"] == 1).sum()),
          "val positives:", int((val_df["gt_spoofing"] == 1).sum()))

    # ✅ Now build features
    X_train, y_train = build_features(train_df)
    X_val, y_val = build_features(val_df)
# weights
    y_train_np = y_train.to_numpy()
    n_pos = int((y_train_np == 1).sum())
    n_neg = int((y_train_np == 0).sum())
    pos_weight = n_neg / max(n_pos, 1)
    sample_weight = np.where(y_train_np == 1, pos_weight, 1.0)
    print("train pos:", n_pos, "train neg:", n_neg, "pos_weight:", float(pos_weight))

    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("model", HistGradientBoostingClassifier(
            max_depth=6,
            learning_rate=0.08,
            max_iter=300,
            random_state=42
        ))
    ])

    print("🧠 Training supervised spoofing classifier...")
    clf.fit(X_train, y_train, model__sample_weight=sample_weight)

    y_prob = clf.predict_proba(X_val)[:, 1]
    ap = average_precision_score(y_val, y_prob)

    thr_f1, p_f1, r_f1, f1_f1 = pick_threshold_max_f1(y_val.to_numpy(), y_prob)
    thr_prec, p_prec, r_prec, f1_prec = pick_threshold_for_precision(y_val.to_numpy(), y_prob, MIN_PRECISION)

    print(f"✅ VAL AP: {ap:.4f}")
    print(f"✅ best-F1 threshold: {thr_f1:.4f} (P={p_f1:.3f}, R={r_f1:.3f}, F1={f1_f1:.3f})")
    print(f"✅ min-precision threshold (target={MIN_PRECISION:.2f}): {thr_prec:.4f} (P={p_prec:.3f}, R={r_prec:.3f}, F1={f1_prec:.3f})")

    thr = thr_f1  # save best-F1 by default

    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    joblib.dump(clf, MODEL_OUT)
    with open(THRESH_OUT, "w") as f:
        f.write(str(thr))

        print("💾 saved model:", MODEL_OUT)
        print("💾 saved threshold:", THRESH_OUT)


if __name__ == "__main__":
        main()




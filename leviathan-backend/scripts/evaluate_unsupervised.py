# scripts/evaluate_unsupervised.py
# Run from leviathan-backend (with venv active):
#   python scripts/evaluate_unsupervised.py
#
# Output plots saved to: leviathan-backend/results/<run_timestamp>/
# IEEE-style plots + stability analysis + LOF baseline + IF top anomalies + model agreement

import os
import sys
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime

from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors, LocalOutlierFactor
from sklearn.metrics import silhouette_score


# =========================================================
# CONFIG
# =========================================================

FIXED_FILE = None  # e.g. "data/cleaned_ais_compressed_24_01_01.csv"
PRIORITY = ["processed", "cleaned", "compressed", "training", "ais_data"]

FEATURES = ["LON", "LAT", "SOG", "COG_sin", "COG_cos"]

# Isolation Forest
IF_N_ESTIMATORS = 300
IF_CONTAMINATION = 0.02

# DBSCAN
DBSCAN_MIN_SAMPLES = 10
DBSCAN_EPS_FALLBACK = 0.30

# Clamp auto eps to avoid extreme spikes
AUTO_EPS_LO_PCTL = 90
AUTO_EPS_HI_PCTL = 99

# Basic sanity filters
MAX_SOG = 60  # knots

# Output
USE_TIMESTAMPED_OUTPUT = True
AUTO_OPEN_RESULTS_FOLDER = True

# Figure export
PLOT_DPI = 300
SAVE_PDF = True  # IEEE: prefer PDF vector

# Plot styling (IEEE-ish)
USE_GRID = False
GRID_ALPHA = 0.12
MARKER_NORMAL = 6
MARKER_ANOMALY = 14
ALPHA_NORMAL = 0.75
ALPHA_ANOMALY = 0.90


# =========================================================
# HELPERS
# =========================================================

def pick_ais_file(data_dir: str) -> str:
    candidates = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            low = f.lower()
            if low.endswith(".csv") or low.endswith(".parquet"):
                full = os.path.join(root, f)
                score = 0
                for i, kw in enumerate(PRIORITY):
                    if kw in low:
                        score += (len(PRIORITY) - i) * 10
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                candidates.append((score, size, full))

    if not candidates:
        raise FileNotFoundError(f"No .csv or .parquet found under: {data_dir}")

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def load_df(file_path: str) -> pd.DataFrame:
    if file_path.lower().endswith(".csv"):
        return pd.read_csv(file_path)
    return pd.read_parquet(file_path)


def ensure_numeric_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    required_raw = ["LON", "LAT", "SOG", "COG"]
    missing = [c for c in required_raw if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}. Found: {list(df.columns)}")

    for col in required_raw:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df_use = df[required_raw].dropna().copy()

    df_use = df_use[df_use["LAT"].between(-90, 90)]
    df_use = df_use[df_use["LON"].between(-180, 180)]
    df_use = df_use[df_use["SOG"].between(0, MAX_SOG)]
    df_use = df_use[df_use["COG"].between(0, 360)]

    cog_rad = np.deg2rad(df_use["COG"].to_numpy())
    df_use["COG_sin"] = np.sin(cog_rad)
    df_use["COG_cos"] = np.cos(cog_rad)

    return df_use[FEATURES].copy()


def make_out_dir(base_out_dir: str) -> str:
    os.makedirs(base_out_dir, exist_ok=True)
    if not USE_TIMESTAMPED_OUTPUT:
        return base_out_dir
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(base_out_dir, f"run_{stamp}")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def savefig(out_dir: str, filename: str) -> None:
    plt.tight_layout()
    png_path = os.path.join(out_dir, filename)
    plt.savefig(png_path, dpi=PLOT_DPI, bbox_inches="tight")

    if SAVE_PDF:
        pdf_name = os.path.splitext(filename)[0] + ".pdf"
        plt.savefig(os.path.join(out_dir, pdf_name), bbox_inches="tight")

    plt.close()


def open_results_folder(path: str) -> None:
    if not AUTO_OPEN_RESULTS_FOLDER:
        return
    try:
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", path], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        print("⚠️ Could not open results folder:", e)


def set_ieee_style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.linewidth": 0.8,
    })


def compute_map_limits(lon: np.ndarray, lat: np.ndarray, pad_ratio: float = 0.03):
    lon_min, lon_max = float(np.min(lon)), float(np.max(lon))
    lat_min, lat_max = float(np.min(lat)), float(np.max(lat))
    lon_pad = (lon_max - lon_min) * pad_ratio if lon_max > lon_min else 0.1
    lat_pad = (lat_max - lat_min) * pad_ratio if lat_max > lat_min else 0.1
    return (lon_min - lon_pad, lon_max + lon_pad, lat_min - lat_pad, lat_max + lat_pad)


def apply_grid():
    if USE_GRID:
        plt.grid(True, alpha=GRID_ALPHA, linewidth=0.6)
    else:
        plt.grid(False)


def knee_eps_from_kdist(k_dist: np.ndarray) -> float:
    n = len(k_dist)
    if n < 10:
        return float(DBSCAN_EPS_FALLBACK)

    x = np.linspace(0, 1, n)
    denom = (k_dist.max() - k_dist.min() + 1e-12)
    y = (k_dist - k_dist.min()) / denom

    y0, y1 = y[0], y[-1]
    y_line = y0 + (y1 - y0) * x

    idx = int(np.argmax(y - y_line))
    eps_raw = float(k_dist[idx])

    lo = float(np.percentile(k_dist, AUTO_EPS_LO_PCTL))
    hi = float(np.percentile(k_dist, AUTO_EPS_HI_PCTL))
    return float(min(max(eps_raw, lo), hi))


# =========================================================
# MAIN
# =========================================================

def main() -> None:
    set_ieee_style()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    out_dir = make_out_dir(os.path.join(base_dir, "results"))

    file_path = os.path.join(base_dir, FIXED_FILE) if FIXED_FILE else pick_ais_file(data_dir)

    print("✅ Using AIS file:", file_path)

    df = load_df(file_path)
    print("✅ Loaded df:", df.shape)
    print("✅ Columns:", list(df.columns)[:25])

    df_use = ensure_numeric_and_clean(df)
    print("✅ Clean df_use:", df_use.shape)

    X = df_use[FEATURES].copy()
    lon = X["LON"].to_numpy()
    lat = X["LAT"].to_numpy()

    xlim_min, xlim_max, ylim_min, ylim_max = compute_map_limits(lon, lat)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print("✅ X_scaled shape:", X_scaled.shape)

    # =========================================================
    # Fig 1: Raw trajectory map
    # =========================================================
    plt.figure(figsize=(6.5, 4.8))
    plt.scatter(lon, lat, s=MARKER_NORMAL, alpha=ALPHA_NORMAL, linewidths=0)
    plt.xlim(xlim_min, xlim_max)
    plt.ylim(ylim_min, ylim_max)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Raw AIS Trajectory Map")
    apply_grid()
    savefig(out_dir, "fig1_raw_trajectory_map.png")

    # =========================================================
    # Isolation Forest
    # =========================================================
    iso = IsolationForest(
        n_estimators=IF_N_ESTIMATORS,
        contamination=IF_CONTAMINATION,
        random_state=42,
    )
    iso.fit(X_scaled)

    y_if = (iso.predict(X_scaled) == -1).astype(int)  # 1=anomaly
    scores = iso.decision_function(X_scaled)          # lower=more anomalous
    thr = np.percentile(scores, 100 * IF_CONTAMINATION)

    print("IF score min:", float(scores.min()))
    print("IF score max:", float(scores.max()))
    print("IF anomaly threshold (lower=more anomalous):", float(thr))

    # Case Study: top 5 anomalies
    top_idx = np.argsort(scores)[:5]
    print("\n=== Top 5 Isolation Forest Anomalies ===")
    for i, idx in enumerate(top_idx):
        print(f"Anomaly {i+1}: LON={lon[idx]:.4f}, LAT={lat[idx]:.4f}, SOG={X.iloc[idx]['SOG']:.2f}, score={scores[idx]:.6f}")

    # Fig 2: IF anomaly map
    plt.figure(figsize=(6.5, 4.8))
    plt.scatter(lon[y_if == 0], lat[y_if == 0], s=MARKER_NORMAL, alpha=ALPHA_NORMAL,
                label="Normal", linewidths=0)
    plt.scatter(lon[y_if == 1], lat[y_if == 1], s=MARKER_ANOMALY, alpha=ALPHA_ANOMALY,
                label="Anomaly", linewidths=0)
    plt.xlim(xlim_min, xlim_max)
    plt.ylim(ylim_min, ylim_max)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Isolation Forest: Detected Anomalies")
    plt.legend(frameon=False, loc="best")
    apply_grid()
    savefig(out_dir, "fig2_if_anomaly_map.png")

    # Fig 3: IF score histogram
    plt.figure(figsize=(6.5, 4.2))
    plt.hist(scores, bins=45, density=True)
    plt.axvline(thr, linestyle="--", label=f"Threshold (p{100*IF_CONTAMINATION:.0f})")
    plt.xlabel("Isolation Forest score (lower = more anomalous)")
    plt.ylabel("Density")
    plt.title("Isolation Forest Score Distribution")
    plt.legend(frameon=False, loc="best")
    apply_grid()
    savefig(out_dir, "fig3_if_score_histogram.png")

    # Fig 4: IF spatial score map
    plt.figure(figsize=(6.5, 4.8))
    sc = plt.scatter(lon, lat, c=scores, s=MARKER_NORMAL, alpha=0.9, linewidths=0)
    cbar = plt.colorbar(sc)
    cbar.set_label("IF score (lower = more anomalous)")
    plt.xlim(xlim_min, xlim_max)
    plt.ylim(ylim_min, ylim_max)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Spatial Distribution of IF Scores")
    apply_grid()
    savefig(out_dir, "fig4_if_spatial_score_map.png")

    # =========================================================
    # Baseline: Local Outlier Factor (after y_if exists)
    # =========================================================
    lof = LocalOutlierFactor(n_neighbors=50, contamination=IF_CONTAMINATION)
    y_lof = (lof.fit_predict(X_scaled) == -1).astype(int)

    lof_rate = 100 * np.mean(y_lof)
    lof_overlap = np.sum((y_lof == 1) & (y_if == 1))

    print("\n=== Local Outlier Factor Baseline ===")
    print(f"LOF anomaly %: {lof_rate:.2f}%")
    print(f"LOF-IF overlap count: {lof_overlap}")

    # =========================================================
    # DBSCAN eps selection via k-distance + knee
    # =========================================================
    k = DBSCAN_MIN_SAMPLES
    nn = NearestNeighbors(n_neighbors=k)
    nn.fit(X_scaled)
    distances, _ = nn.kneighbors(X_scaled)
    k_dist = np.sort(distances[:, k - 1])

    eps_used = knee_eps_from_kdist(k_dist)
    if not np.isfinite(eps_used) or eps_used <= 0:
        eps_used = float(DBSCAN_EPS_FALLBACK)
        print(f"⚠️ Auto eps failed; using fallback eps_used={eps_used:.3f}")
    else:
        print(f"✅ Auto-estimated eps (knee+clamp): {eps_used:.4f}")

    db = DBSCAN(eps=eps_used, min_samples=DBSCAN_MIN_SAMPLES)
    db_labels = db.fit_predict(X_scaled)
    y_db = (db_labels == -1).astype(int)

    # Fig 5: DBSCAN cluster/noise map
    plt.figure(figsize=(6.5, 4.8))
    noise_mask = db_labels == -1
    cluster_mask = ~noise_mask

    plt.scatter(lon[cluster_mask], lat[cluster_mask], s=MARKER_NORMAL, alpha=ALPHA_NORMAL,
                label="Clustered points", linewidths=0)
    plt.scatter(lon[noise_mask], lat[noise_mask], s=MARKER_ANOMALY, alpha=ALPHA_ANOMALY,
                label="Noise (-1)", linewidths=0)
    plt.xlim(xlim_min, xlim_max)
    plt.ylim(ylim_min, ylim_max)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("DBSCAN: Clusters vs Noise")
    plt.legend(frameon=False, loc="best")
    apply_grid()
    savefig(out_dir, "fig5_dbscan_cluster_map.png")

    # Fig 6: Full k-distance graph
    plt.figure(figsize=(6.5, 4.2))
    plt.plot(k_dist, linewidth=1.2)
    plt.axhline(eps_used, linestyle="--", label=f"Chosen eps = {eps_used:.3f}")
    plt.xlabel("Points sorted by distance")
    plt.ylabel(f"{k}-NN distance")
    plt.title("DBSCAN eps Selection via K-distance")
    plt.legend(frameon=False, loc="best")
    apply_grid()
    savefig(out_dir, "fig6_dbscan_k_distance.png")

    # Fig 7: Zoomed elbow region
    start = int(len(k_dist) * 0.80)
    plt.figure(figsize=(6.5, 4.2))
    plt.plot(np.arange(start, len(k_dist)), k_dist[start:], linewidth=1.2)
    plt.axhline(eps_used, linestyle="--", label=f"Chosen eps = {eps_used:.3f}")
    plt.xlabel("Points (zoomed tail region)")
    plt.ylabel(f"{k}-NN distance")
    plt.title("Zoomed K-distance (Elbow Region)")
    plt.legend(frameon=False, loc="best")
    apply_grid()
    savefig(out_dir, "fig7_dbscan_k_distance_zoom.png")

    # =========================================================
    # DBSCAN Stability Analysis + Fig 8
    # =========================================================
    eps_grid = np.linspace(eps_used * 0.7, eps_used * 1.3, 9)
    stability_results = []

    for eps in eps_grid:
        db_tmp = DBSCAN(eps=eps, min_samples=DBSCAN_MIN_SAMPLES)
        labels_tmp = db_tmp.fit_predict(X_scaled)

        noise_rate = 100 * np.mean(labels_tmp == -1)
        n_clusters_tmp = len(set(labels_tmp)) - (1 if -1 in labels_tmp else 0)

        sil_tmp = None
        mask_tmp = labels_tmp != -1
        if len(set(labels_tmp[mask_tmp])) > 1 and np.sum(mask_tmp) > 10:
            sil_tmp = silhouette_score(X_scaled[mask_tmp], labels_tmp[mask_tmp])

        stability_results.append((eps, noise_rate, n_clusters_tmp, sil_tmp))

    print("\n=== DBSCAN Stability Across eps ===")
    print("eps\tNoise%\tClusters\tSilhouette")
    for eps, noise_rate, n_clusters_tmp, sil_tmp in stability_results:
        sil_str = f"{sil_tmp:.3f}" if sil_tmp is not None else "NA"
        print(f"{eps:.3f}\t{noise_rate:.2f}\t{n_clusters_tmp}\t\t{sil_str}")

    eps_vals = [r[0] for r in stability_results]
    noise_vals = [r[1] for r in stability_results]

    plt.figure(figsize=(6.5, 4.2))
    plt.plot(eps_vals, noise_vals, marker="o", linewidth=1.2)
    plt.axvline(eps_used, linestyle="--", label=f"Chosen eps = {eps_used:.3f}")
    plt.xlabel("DBSCAN eps")
    plt.ylabel("Noise percentage (%)")
    plt.title("DBSCAN Sensitivity: Noise Percentage vs eps")
    plt.legend(frameon=False, loc="best")
    apply_grid()
    savefig(out_dir, "fig8_noise_vs_eps.png")

    # =========================================================
    # Summary metrics + Agreement
    # =========================================================
    if_rate = 100 * float(np.mean(y_if))
    db_rate = 100 * float(np.mean(y_db))
    n_clusters = len(set(db_labels)) - (1 if -1 in db_labels else 0)

    sil = None
    mask = db_labels != -1
    if len(set(db_labels[mask])) > 1 and np.sum(mask) > 10:
        sil = float(silhouette_score(X_scaled[mask], db_labels[mask]))

    print(f"\nIsolation Forest anomaly %: {if_rate:.2f}% (contamination={IF_CONTAMINATION})")
    print(f"DBSCAN noise %: {db_rate:.2f}% (eps_used={eps_used:.3f}, min_samples={DBSCAN_MIN_SAMPLES})")
    print(f"DBSCAN clusters (excluding noise): {n_clusters}")
    print(f"DBSCAN silhouette score (excluding noise): {sil:.3f}" if sil is not None else "DBSCAN silhouette: NA")

    overlap = np.sum((y_if == 1) & (y_db == 1))
    if_only = np.sum((y_if == 1) & (y_db == 0))
    db_only = np.sum((y_if == 0) & (y_db == 1))

    print("\n=== Model Agreement (IF vs DBSCAN) ===")
    print(f"IF-only anomalies: {if_only}")
    print(f"DBSCAN-only noise: {db_only}")
    print(f"Overlap (both): {overlap}")
    total_if = if_only + overlap
    total_db = db_only + overlap

    agree_if = 100 * overlap / total_if if total_if else 0
    agree_db = 100 * overlap / total_db if total_db else 0

    print(f"Agreement rate vs IF anomalies: {agree_if:.2f}%")
    print(f"Agreement rate vs DBSCAN noise: {agree_db:.2f}%")
    print(f"\n✅ Saved IEEE-style plots to: {out_dir}")
    open_results_folder(out_dir)


if __name__ == "__main__":
    main()
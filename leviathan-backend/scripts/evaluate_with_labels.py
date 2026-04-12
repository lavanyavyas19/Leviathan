#!/usr/bin/env python3
#evaluate_with_labels.py.bak
"""
Evaluation script with time-based train/test split.

Evaluates spoofing and loitering detection models against synthetic ground truth.
"""

import os
import sys
import json
import uuid
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple, List
import warnings
import random
import joblib

random.seed(42)
np.random.seed(42)
warnings.filterwarnings('ignore')

# Matplotlib import with comprehensive error handling and shadowing detection
MATPLOTLIB_AVAILABLE = False
MATPLOTLIB_VERSION = None
MATPLOTLIB_FILE = None

def get_env_threshold(name: str):
    v = os.getenv(name, "").strip()
    if not v:
        return None
    try:
        return float(v)
    except Exception:
        print(f"⚠️ Invalid {name}='{v}', ignoring.")
        return None



def debug_environment():
    """Print environment debug information."""
    print("="*80)
    print("ENVIRONMENT DEBUG")
    print("="*80)
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"sys.path (first 5 entries):")
    for i, path in enumerate(sys.path[:5], 1):
        print(f"  {i}. {path}")

    try:
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "-V"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if pip_result.returncode == 0:
            print(f"pip version: {pip_result.stdout.strip()}")
        else:
            print(f"pip check failed: {pip_result.stderr}")
    except Exception as e:
        print(f"pip check error: {e}")

    try:
        matplotlib_check = subprocess.run(
            [sys.executable, "-c", "import matplotlib; print(matplotlib.__version__, matplotlib.__file__)"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if matplotlib_check.returncode == 0:
            parts = matplotlib_check.stdout.strip().split(' ', 1)
            if len(parts) == 2:
                print(f"matplotlib (subprocess): version={parts[0]}, file={parts[1]}")
        else:
            print(f"matplotlib subprocess check failed: {matplotlib_check.stderr}")
    except Exception as e:
        print(f"matplotlib subprocess check error: {e}")

    print("="*80 + "\n")

# Try importing matplotlib
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
    MATPLOTLIB_VERSION = matplotlib.__version__
    MATPLOTLIB_FILE = getattr(matplotlib, "__file__", None)

    print(f"✅ matplotlib imported successfully")
    print(f"   Version: {MATPLOTLIB_VERSION}")
    print(f"   File: {MATPLOTLIB_FILE}")

    # Check for shadowing
    if MATPLOTLIB_FILE is None:
        print(f"   ⚠️  WARNING: matplotlib.__file__ is None (may indicate shadowing or namespace package)")
    elif "site-packages" not in MATPLOTLIB_FILE:
        print(f"   ⚠️  WARNING: matplotlib may be shadowed!")
        print(f"      Expected path to contain 'site-packages', got: {MATPLOTLIB_FILE}")
        print(f"      This may indicate a local matplotlib.py or matplotlib/ directory is shadowing the installed package.")
        print(f"      Check current directory and sys.path entries above for local matplotlib modules.")
    else:
        print(f"   ✅ matplotlib from site-packages (no shadowing detected)")

except ImportError as e:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib ImportError - plots will be skipped")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error message: {e}")
except Exception as e:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib import failed - plots will be skipped")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error message: {e}")

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from app.core.anomaly_detection import detect_spoofing_events, detect_loitering_events
from app.core.preprocessing import clean_and_preprocess
import joblib
from sklearn.metrics import (
    precision_recall_fscore_support,
    confusion_matrix,
    roc_curve,
    auc,
    roc_auc_score,
    precision_recall_curve,
    average_precision_score
)

# Configuration
MATCHING_TOLERANCE_SEC = 300  # ±5 minutes
DPI = 300
TRAIN_SPLIT = 0.7

# Precision-first threshold calibration
MIN_SPOOFING_PRECISION = float(os.getenv("MIN_SPOOFING_PRECISION", "0.20"))
MIN_SPOOFING_RECALL_STR = os.getenv("MIN_SPOOFING_RECALL", "")
try:
    MIN_SPOOFING_RECALL = float(MIN_SPOOFING_RECALL_STR) if MIN_SPOOFING_RECALL_STR else None
except Exception:
    MIN_SPOOFING_RECALL = None


def find_latest_synthetic_dataset(synthetic_dir: Path) -> Path:
    """Find the most recent synthetic dataset CSV."""
    csv_files = list(synthetic_dir.glob("ais_synth_labeled_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No synthetic datasets found in {synthetic_dir}")

    latest = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"📂 Using synthetic dataset: {latest.name}")
    return latest


def time_based_split(df: pd.DataFrame, train_split: float = 0.7) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset chronologically by timestamp."""
    if 'timestamp' not in df.columns:
        raise ValueError("DataFrame must have 'timestamp' column for time-based split")

    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    split_idx = int(len(df) * train_split)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    return train_df, test_df


def split_by_mmsi(df: pd.DataFrame, train_frac: float = 0.7, seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset by MMSI (no MMSI leakage)."""
    d = df[df["mmsi"].notna()].copy()
    mmsis = d["mmsi"].astype(int).unique()

    rng = np.random.default_rng(seed)
    rng.shuffle(mmsis)

    cut = int(train_frac * len(mmsis))
    train_ids = set(mmsis[:cut])

    train_df = d[d["mmsi"].astype(int).isin(train_ids)].copy()
    test_df  = d[~d["mmsi"].astype(int).isin(train_ids)].copy()

    return train_df, test_df
 


def print_split_statistics(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Print train/test split statistics + extra GT diagnostics for spoofing/loitering."""
    print("\n" + "="*80)
    print("TRAIN/TEST SPLIT STATISTICS")
    print("="*80)

    def mmsi_pos_count(df, col):
        if col not in df.columns or "mmsi" not in df.columns:
            return None
        return int(df.loc[df[col] == 1, "mmsi"].nunique())

    print(f"\nTrain set:")
    print(f"  Rows: {len(train_df):,}")
    print(f"  Spoofing positives: {int(train_df['gt_spoofing'].sum()):,} "
          f"(pos MMSIs: {mmsi_pos_count(train_df,'gt_spoofing')})")
    print(f"  Loitering positives: {int(train_df['gt_loitering'].sum()):,} "
          f"(pos MMSIs: {mmsi_pos_count(train_df,'gt_loitering')})")

    print(f"\nTest set:")
    print(f"  Rows: {len(test_df):,}")
    print(f"  Spoofing positives: {int(test_df['gt_spoofing'].sum()):,} "
          f"(pos MMSIs: {mmsi_pos_count(test_df,'gt_spoofing')})")
    print(f"  Loitering positives: {int(test_df['gt_loitering'].sum()):,} "
          f"(pos MMSIs: {mmsi_pos_count(test_df,'gt_loitering')})")

    test_spoofing = int(test_df['gt_spoofing'].sum())
    test_loitering = int(test_df['gt_loitering'].sum())

    if test_spoofing < 10:
        print(f"\n⚠️  WARNING: Test spoofing positives < 10 ({test_spoofing})")
        print("   Metrics may be unstable due to small positive sample.")

    if test_loitering < 20:
        print(f"\n⚠️  WARNING: Test loitering positives < 20 ({test_loitering})")
        print("   Metrics may be unstable due to small positive sample.")

    print("="*80 + "\n")

def build_gt_events(df: pd.DataFrame, gt_col: str, gap_sec: int = 300, min_points: int = 3, min_duration_sec: int = 60) -> pd.DataFrame:
    """
    Convert point-wise gt labels into event windows per MMSI.
    Event = consecutive gt=1 points with time gaps <= gap_sec.
    Filters events by min_points and min_duration_sec.
    Returns: mmsi, start_ts, end_ts, n_points, duration_sec
    """
    d = df[['mmsi', 'timestamp', gt_col]].copy()
    d['timestamp'] = pd.to_datetime(d['timestamp'], errors='coerce')
    d = d.dropna(subset=['timestamp'])
    d = d.sort_values(['mmsi', 'timestamp'])

    d = d[d[gt_col] == 1]
    if d.empty:
        return pd.DataFrame(columns=['mmsi', 'start_ts', 'end_ts', 'n_points', 'duration_sec'])

    dt = d.groupby('mmsi')['timestamp'].diff().dt.total_seconds()
    d['_new_event'] = (dt.isna()) | (dt > gap_sec)
    d['_event_id'] = d.groupby('mmsi')['_new_event'].cumsum()

    events = d.groupby(['mmsi','_event_id']).agg(
        start_ts=('timestamp','min'),
        end_ts=('timestamp','max'),
        n_points=('timestamp','size')
    ).reset_index()
    
    # Compute duration (fillna(0) to handle rare NaN cases)
    events['duration_sec'] = (events['end_ts'] - events['start_ts']).dt.total_seconds().fillna(0)
    
    # Filter by min_points and min_duration_sec
    events = events[
        (events['n_points'] >= min_points) & 
        (events['duration_sec'] >= min_duration_sec)
    ]
    
    return events[['mmsi', 'start_ts', 'end_ts', 'n_points', 'duration_sec']]


# ✅ NEW: build prediction events (same logic as GT, using timestamp gaps)
def build_pred_events(
    predictions_df: pd.DataFrame,
    gap_sec: int = 300,
    min_points: int = 3,
    min_duration_sec: int = 60
) -> pd.DataFrame:
    """
    Convert predictions into event windows per MMSI.

    Supports:
    - Detector outputs event windows directly (start/end columns)
    - Loitering cluster outputs (timestamp + dwell_time_hr)
    - Point predictions (mmsi + timestamp) grouped by time gaps
    """
    if predictions_df is None or predictions_df.empty:
        return pd.DataFrame(columns=["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"])

    p = predictions_df.copy()
    cols = set(p.columns)

    # ---------------------------------------------------------------------
    # CASE 0: predictions already have start_ts/end_ts in the exact schema
    # ---------------------------------------------------------------------
    if {"mmsi", "start_ts", "end_ts"}.issubset(cols):
        out = p.copy()
        out["start_ts"] = pd.to_datetime(out["start_ts"], errors="coerce")
        out["end_ts"] = pd.to_datetime(out["end_ts"], errors="coerce")
        out = out.dropna(subset=["mmsi", "start_ts", "end_ts"])

        out["duration_sec"] = (out["end_ts"] - out["start_ts"]).dt.total_seconds().clip(lower=0)

        if "n_points" not in out.columns:
            if "cluster_size" in out.columns:
                out["n_points"] = pd.to_numeric(out["cluster_size"], errors="coerce").fillna(1).astype(int)
            else:
                out["n_points"] = 1
        else:
            out["n_points"] = pd.to_numeric(out["n_points"], errors="coerce").fillna(1).astype(int)

        out = out[(out["n_points"] >= min_points) & (out["duration_sec"] >= min_duration_sec)]
        return out[["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"]].reset_index(drop=True)

    # ---------------------------------------------------------------------
    # CASE A: loitering cluster output: timestamp + dwell_time_hr
    # (your loitering detector returns this)
    # ---------------------------------------------------------------------
    if {"mmsi", "timestamp", "dwell_time_hr"}.issubset(cols):
        p["timestamp"] = pd.to_datetime(p["timestamp"], errors="coerce")
        p["dwell_time_hr"] = pd.to_numeric(p["dwell_time_hr"], errors="coerce")
        p = p.dropna(subset=["mmsi", "timestamp", "dwell_time_hr"])

        out = pd.DataFrame({
            "mmsi": p["mmsi"].astype(str),
            "start_ts": p["timestamp"],
            "end_ts": p["timestamp"] + pd.to_timedelta(p["dwell_time_hr"], unit="h"),
            "n_points": pd.to_numeric(p.get("cluster_size", np.nan), errors="coerce")
        })

        out["duration_sec"] = (out["end_ts"] - out["start_ts"]).dt.total_seconds().fillna(0)
        out["n_points"] = out["n_points"].fillna(1).astype(int)

        out = out[(out["n_points"] >= min_points) & (out["duration_sec"] >= min_duration_sec)]
        return out[["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"]].reset_index(drop=True)

    # ---------------------------------------------------------------------
    # CASE B: detector already outputs start/end in other common names
    # ---------------------------------------------------------------------
    candidates = [
        ("start_ts", "end_ts"),
        ("start_time", "end_time"),
        ("start", "end"),
        ("start_timestamp", "end_timestamp"),
    ]
    for s, e in candidates:
        if {"mmsi", s, e}.issubset(cols):
            p[s] = pd.to_datetime(p[s], errors="coerce")
            p[e] = pd.to_datetime(p[e], errors="coerce")
            p = p.dropna(subset=["mmsi", s, e])

            out = p[["mmsi", s, e]].copy().rename(columns={s: "start_ts", e: "end_ts"})
            out["n_points"] = pd.to_numeric(p.get("n_points", p.get("cluster_size", 1)), errors="coerce").fillna(1).astype(int)
            out["duration_sec"] = (out["end_ts"] - out["start_ts"]).dt.total_seconds().fillna(0)

            out = out[(out["n_points"] >= min_points) & (out["duration_sec"] >= min_duration_sec)]
            return out[["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"]].reset_index(drop=True)

    # ---------------------------------------------------------------------
    # CASE C: point predictions grouped by time gaps
    # ---------------------------------------------------------------------
    if "mmsi" not in cols:
        print("predictions_df missing mmsi (cannot build pred events)")
        return pd.DataFrame(columns=["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"])

    # choose a timestamp-like column
    if "timestamp" in cols:
        p["timestamp"] = pd.to_datetime(p["timestamp"], errors="coerce")
    elif "start_ts" in cols:
        p["timestamp"] = pd.to_datetime(p["start_ts"], errors="coerce")
    elif "start_time" in cols:
        p["timestamp"] = pd.to_datetime(p["start_time"], errors="coerce")
    else:
        print("predictions_df missing timestamp/start_ts/start_time (cannot build pred events)")
        return pd.DataFrame(columns=["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"])

    p = p.dropna(subset=["mmsi", "timestamp"])
    if p.empty:
        return pd.DataFrame(columns=["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"])

    # IMPORTANT: enforce consistent types + sorting
    p["mmsi"] = p["mmsi"].astype(str)

    p = p.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)
    dt = p.groupby("mmsi")["timestamp"].diff().dt.total_seconds()
    p["_new_event"] = dt.isna() | (dt > gap_sec)
    p["_event_id"] = p.groupby("mmsi")["_new_event"].cumsum()

    events = (
        p.groupby(["mmsi", "_event_id"], as_index=False)
         .agg(
            start_ts=("timestamp", "min"),
            end_ts=("timestamp", "max"),
            n_points=("timestamp", "size"),
         )
    )

    # ✅ Ensure mmsi column exists no matter what
    if "mmsi" not in events.columns:
        events = events.reset_index()
        if "mmsi" not in events.columns:
            # last-resort: recover from MultiIndex
            if isinstance(events.index, pd.MultiIndex):
                events = events.reset_index()

    events["duration_sec"] = (events["end_ts"] - events["start_ts"]).dt.total_seconds().fillna(0)
    events = events[(events["n_points"] >= min_points) & (events["duration_sec"] >= min_duration_sec)]

    return events[["mmsi", "start_ts", "end_ts", "n_points", "duration_sec"]].reset_index(drop=True)
# ✅ NEW: event-level matching (one-to-one greedy matching by maximum overlap duration)
def match_pred_events_to_gt_events(pred_events: pd.DataFrame, gt_events: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Event-level y_true/y_pred arrays with one-to-one greedy matching:
      - Each predicted event matches at most one GT event (and vice versa).
      - Matching is greedy: highest overlap duration first, per MMSI.
      - TP: matched pred event, FP: unmatched pred event, FN: unmatched GT event.
    """
    if gt_events is None or gt_events.empty:
        y_true = np.zeros(len(pred_events), dtype=int)
        y_pred = np.ones(len(pred_events), dtype=int)
        return y_true, y_pred

    if pred_events is None or pred_events.empty:
        y_true = np.ones(len(gt_events), dtype=int)
        y_pred = np.zeros(len(gt_events), dtype=int)
        return y_true, y_pred

    pe = pred_events.copy()
    ge = gt_events.copy()

    pe['start_ts'] = pd.to_datetime(pe['start_ts'], errors='coerce')
    pe['end_ts'] = pd.to_datetime(pe['end_ts'], errors='coerce')
    ge['start_ts'] = pd.to_datetime(ge['start_ts'], errors='coerce')
    ge['end_ts'] = pd.to_datetime(ge['end_ts'], errors='coerce')

    pe = pe.dropna(subset=['mmsi', 'start_ts', 'end_ts']).reset_index(drop=True)
    ge = ge.dropna(subset=['mmsi', 'start_ts', 'end_ts']).reset_index(drop=True)

    pe['_pred_id'] = pe.index
    ge['_gt_id'] = ge.index

    candidates = []
    ge_by_mmsi = {m: df for m, df in ge.groupby('mmsi')}

    for _, prow in pe.iterrows():
        m = prow['mmsi']
        if m not in ge_by_mmsi:
            continue

        ps, pe_ = prow['start_ts'], prow['end_ts']
        for _, grow in ge_by_mmsi[m].iterrows():
            gs, ge_ = grow['start_ts'], grow['end_ts']

            # Expand windows by tolerance to allow point-ish events to match
            tol = MATCHING_TOLERANCE_SEC

            ps0 = ps - pd.Timedelta(seconds=tol)
            pe0 = pe_ + pd.Timedelta(seconds=tol)
            gs0 = gs - pd.Timedelta(seconds=tol)
            ge0 = ge_ + pd.Timedelta(seconds=tol)

            overlap_start = max(ps0, gs0)
            overlap_end = min(pe0, ge0)

            if overlap_start < overlap_end:
                overlap = (overlap_end - overlap_start).total_seconds()
                # allow any positive overlap now
                candidates.append((overlap, int(prow["_pred_id"]), int(grow["_gt_id"])))

    candidates.sort(reverse=True, key=lambda x: x[0])

    matched_pred_ids = set()
    matched_gt_ids = set()

    for overlap, pred_id, gt_id in candidates:
        if pred_id in matched_pred_ids or gt_id in matched_gt_ids:
            continue
        matched_pred_ids.add(pred_id)
        matched_gt_ids.add(gt_id)

    y_true_list = []
    y_pred_list = []

    # predicted events: positive predictions
    for i in range(len(pe)):
        y_pred_list.append(1)
        y_true_list.append(1 if i in matched_pred_ids else 0)

    # unmatched GT events become FN
    for j in range(len(ge)):
        if j not in matched_gt_ids:
            y_true_list.append(1)
            y_pred_list.append(0)

    return np.array(y_true_list, dtype=int), np.array(y_pred_list, dtype=int)

def match_predictions_to_ground_truth(
    predictions_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
    gt_column: str,
    tolerance_sec: int = 300
 ) -> Tuple[np.ndarray, np.ndarray]:
    """
    FAST POINT-WISE matching using merge_asof:
    Match predictions to nearest GT point within ±tolerance per MMSI.
    Produces y_true (GT labels) and y_pred (matched predictions) arrays aligned to GT rows.
    """

    # ---------- Ground truth prep ----------
    gt = ground_truth_df.copy()
    gt["timestamp"] = pd.to_datetime(gt["timestamp"], errors="coerce")
    gt["mmsi"] = pd.to_numeric(gt["mmsi"], errors="coerce")

    gt = gt.dropna(subset=["mmsi", "timestamp"]).copy()
    gt["mmsi"] = gt["mmsi"].astype(np.int64)

    gt = gt.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)
    gt["_pos"] = np.arange(len(gt), dtype=np.int64)

    y_true = (gt[gt_column] == 1).astype(int).to_numpy()
    y_pred = np.zeros(len(gt), dtype=int)

    # ---------- Predictions prep ----------
    if predictions_df is None or predictions_df.empty:
        return y_true, y_pred
    if "mmsi" not in predictions_df.columns or "timestamp" not in predictions_df.columns:
        return y_true, y_pred

    pred = predictions_df.copy()
    pred["timestamp"] = pd.to_datetime(pred["timestamp"], errors="coerce")
    pred["mmsi"] = pd.to_numeric(pred["mmsi"], errors="coerce")
    pred = pred.dropna(subset=["mmsi", "timestamp"]).copy()
    if pred.empty:
        return y_true, y_pred

    pred["mmsi"] = pred["mmsi"].astype(np.int64)

    # ✅ CRITICAL: sort the EXACT frames you pass into merge_asof
    # IMPORTANT: merge_asof checks global sort on the "on" key (timestamp)
    pred_key = pred[["mmsi", "timestamp"]].sort_values(["timestamp", "mmsi"]).reset_index(drop=True)
    gt_key   = gt[["mmsi", "timestamp", "_pos"]].sort_values(["timestamp", "mmsi"]).reset_index(drop=True)
    tol = pd.Timedelta(seconds=tolerance_sec)
    
    assert pred_key["timestamp"].is_monotonic_increasing, "pred_key timestamp not globally sorted"
    assert gt_key["timestamp"].is_monotonic_increasing, "gt_key timestamp not globally sorted"

    merged = pd.merge_asof(
        pred_key,
        gt_key,
        on="timestamp",
        by="mmsi",
        direction="nearest",
        tolerance=tol
    )

    # Mark matched GT positions (unique to avoid double counting)
    matched_pos = merged["_pos"].dropna().astype(np.int64).unique()
    y_pred[matched_pos] = 1

    return y_true, y_pred



def debug_matching_stats(predictions_df, test_df, gt_column, tolerance_sec):
    print("\n" + "-" * 80)
    print(f"MATCHING DEBUG ({gt_column})")
    print("-" * 80)
    print(f"predictions rows: {len(predictions_df):,}")
    print(f"ground truth positives: {(test_df[gt_column] == 1).sum():,}")

    if predictions_df is None or predictions_df.empty:
        print("No predictions.")
        return

    if "mmsi" not in predictions_df.columns:
        print("predictions_df missing mmsi")
        return
    
    # ✅ timestamp column is required for matching stats
    if "timestamp" not in predictions_df.columns:
        print("predictions_df missing timestamp (debug limited)")
        return

    # sample a few MMSIs to avoid huge join
    sample_mmsi = predictions_df["mmsi"].dropna().astype(int).drop_duplicates().sample(
        n=min(20, predictions_df["mmsi"].nunique()), random_state=42
    )
    p = predictions_df[predictions_df["mmsi"].isin(sample_mmsi)].copy()
    g = test_df[test_df["mmsi"].isin(sample_mmsi)].copy()

    p["timestamp"] = pd.to_datetime(p.get("timestamp"), errors="coerce")
    g["timestamp"] = pd.to_datetime(g.get("timestamp"), errors="coerce")
    p = p.dropna(subset=["timestamp"])
    g = g.dropna(subset=["timestamp"])

    if p.empty or g.empty:
        print("No overlap in sampled MMSIs.")
        return

    # small join only
    merged = p[["mmsi", "timestamp"]].merge(
        g[["mmsi", "timestamp", gt_column]],
        on="mmsi",
        how="inner",
        suffixes=("_pred", "_gt")
    )
    merged["dt_sec"] = (merged["timestamp_gt"] - merged["timestamp_pred"]).abs().dt.total_seconds()
    within = (merged["dt_sec"] <= tolerance_sec).sum()

    print(f"sampled MMSIs: {len(sample_mmsi)}")
    print(f"pairs within ±{tolerance_sec}s (sample): {within:,} / {len(merged):,}")


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, scores: np.ndarray = None) -> Dict:
    """Compute classification metrics."""
    metrics = {}

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, average='binary', zero_division=0
    )

    metrics['precision'] = float(precision)
    metrics['recall'] = float(recall)
    metrics['f1'] = float(f1)

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    metrics['confusion_matrix'] = {
        'true_negatives': int(tn),
        'false_positives': int(fp),
        'false_negatives': int(fn),
        'true_positives': int(tp)
    }

    metrics['num_detected'] = int(y_pred.sum())
    metrics['num_ground_truth'] = int(y_true.sum())

    # ROC curve and AUC (if scores provided)
    # ROC requires point-wise arrays of equal length
    if scores is not None and len(scores) > 0:
        if len(scores) != len(y_true):
            print(f"⚠️  Skipping EVENT-LEVEL ROC (y_true is event-level, scores are point-wise). Point-wise ROC is computed later.")
            metrics['roc_auc'] = None
            metrics['roc_curve'] = None
        else:
            try:
                if len(np.unique(y_true)) > 1:
                    is_supervised = False
                    try:
                        model = joblib.load(str(backend_dir / "app" / "ml" / "spoofing_model.pkl"))
                        is_supervised = hasattr(model, "predict_proba")
                    except Exception:
                        pass

                    scores_normalized = scores if is_supervised else -scores
                    fpr, tpr, thresholds = roc_curve(y_true, scores_normalized)
                    roc_auc = auc(fpr, tpr)
                    metrics['roc_auc'] = float(roc_auc)
                    metrics['roc_curve'] = {
                        'fpr': fpr.tolist(),
                        'tpr': tpr.tolist(),
                        'thresholds': thresholds.tolist()
                    }
                else:
                    metrics['roc_auc'] = None
                    metrics['roc_curve'] = None
            except Exception as e:
                print(f"⚠️  ROC computation failed: {e}")
                metrics['roc_auc'] = None
                metrics['roc_curve'] = None
    else:
        metrics['roc_auc'] = None
        metrics['roc_curve'] = None

    if metrics['num_ground_truth'] < 10:
        metrics['warning'] = "Metrics unstable due to small positive sample (< 10)"

    return metrics


def plot_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, title: str, output_path: Path, dpi: int = 300) -> bool:
    """Plot confusion matrix."""
    if not MATPLOTLIB_AVAILABLE:
        print(f"   ⚠️  Skipped: {output_path.name} (matplotlib not available)")
        return False

    try:
        cm = confusion_matrix(y_true, y_pred)

        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(cm, interpolation='nearest', cmap='Blues' if 'loitering' in title.lower() else 'Reds')
        ax.figure.colorbar(im, ax=ax)

        thresh = cm.max() / 2. if cm.size else 0
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black",
                        fontsize=14, fontweight='bold')

        ax.set(xticks=np.arange(cm.shape[1]),
               yticks=np.arange(cm.shape[0]),
               xticklabels=['Normal', 'Anomaly'],
               yticklabels=['Normal', 'Anomaly'],
               title=title,
               ylabel='Actual',
               xlabel='Predicted')

        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close()

        if output_path.exists() and output_path.stat().st_size > 0:
            size_kb = output_path.stat().st_size / 1024
            print(f"   ✅ Saved: {output_path.name} ({size_kb:.1f} KB)")
            return True
        else:
            print(f"   ⚠️  Failed: {output_path.name} (file not created or empty)")
            return False

    except Exception as e:
        print(f"   ⚠️  Failed: {output_path.name} (error: {type(e).__name__}: {e})")
        try:
            plt.close('all')
        except:
            pass
        return False


def plot_roc_curve(fpr: np.ndarray, tpr: np.ndarray, roc_auc: float, output_path: Path, dpi: int = 300) -> bool:
    """Plot ROC curve."""
    if not MATPLOTLIB_AVAILABLE:
        print(f"   ⚠️  Skipped: {output_path.name} (matplotlib not available)")
        return False

    try:
        fig, ax = plt.subplots(figsize=(8, 6))

        ax.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
        ax.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random (AUC = 0.500)')

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate', fontsize=12)
        ax.set_ylabel('True Positive Rate', fontsize=12)
        ax.set_title('ROC Curve - Spoofing Detection', fontsize=14, fontweight='bold')
        ax.legend(loc="lower right", fontsize=11)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close()

        if output_path.exists() and output_path.stat().st_size > 0:
            size_kb = output_path.stat().st_size / 1024
            print(f"   ✅ Saved: {output_path.name} ({size_kb:.1f} KB)")
            return True
        else:
            print(f"   ⚠️  Failed: {output_path.name} (file not created or empty)")
            return False

    except Exception as e:
        print(f"   ⚠️  Failed: {output_path.name} (error: {type(e).__name__}: {e})")
        try:
            plt.close('all')
        except:
            pass
        return False

def plot_pr_curve(y_true: np.ndarray, scores: np.ndarray, output_path: Path, dpi: int = 300, is_supervised: bool = False) -> bool:
    if not MATPLOTLIB_AVAILABLE:
        print(f"   ⚠️  Skipped: {output_path.name} (matplotlib not available)")
        return False
    try:
        # For unsupervised (IF): lower score = more anomalous, so negate
        # For supervised (predict_proba): higher score = more anomalous, use as-is
        scores_norm = scores if is_supervised else -scores
        precision, recall, _ = precision_recall_curve(y_true, scores_norm)
        ap = average_precision_score(y_true, scores_norm)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(recall, precision, lw=2, label=f"PR curve (AP = {ap:.4f})")
        ax.set_xlabel("Recall", fontsize=12)
        ax.set_ylabel("Precision", fontsize=12)
        ax.set_title("Precision-Recall Curve - Spoofing (Point-wise)", fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower left", fontsize=11)

        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close()
        print(f"   ✅ Saved: {output_path.name}")
        return True
    except Exception as e:
        print(f"   ⚠️  Failed: {output_path.name} ({type(e).__name__}: {e})")
        try:
            plt.close("all")
        except:
            pass
        return False





def compute_pr_and_best_threshold(y_true_pointwise: np.ndarray, scores_pointwise: np.ndarray) -> Dict:
    """
    Compute PR curve and find best threshold (max F1).
    Returns dict with best_threshold, best_f1, average_precision.
    """
    # Convert scores so "higher = more anomalous"
    scores_norm = -scores_pointwise
    
    # Compute precision-recall curve
    precision, recall, thresholds = precision_recall_curve(y_true_pointwise, scores_norm)
    
    # Compute F1 for each threshold
    # thresholds length is (len(precision)-1), so we need to align
    f1_scores = []
    for i in range(len(thresholds)):
        p = precision[i]
        r = recall[i]
        if p + r > 0:
            f1 = 2 * (p * r) / (p + r)
        else:
            f1 = 0.0
        f1_scores.append(f1)
    
    # Find best threshold (max F1)
    # Note: thresholds from precision_recall_curve are in normalized space (scores_norm)
    # Convert back to original score space: threshold_original = -threshold_normalized
    if len(f1_scores) > 0:
        best_idx = np.argmax(f1_scores)
        best_threshold_normalized = float(thresholds[best_idx])
        best_threshold = -best_threshold_normalized  # Convert back to original score space
        best_f1 = float(f1_scores[best_idx])
    else:
        best_threshold = None
        best_f1 = 0.0
    
    # Compute average precision
    ap = float(average_precision_score(y_true_pointwise, scores_norm))
    
    return {
        "best_threshold": best_threshold,
        "best_f1": best_f1,
        "average_precision": ap
    }


def choose_threshold_for_min_precision(
    y_true_pointwise: np.ndarray,
    scores_pointwise: np.ndarray,
    min_precision: float,
    min_recall: float | None = None
) -> Dict:
    """
    Choose threshold that meets minimum precision (and optionally recall) requirements.
    Among candidates meeting constraints, chooses the one with MAX recall.
    Returns dict with chosen_threshold, precision, recall, f1, and counts.
    """
    # Convert scores so "higher = more anomalous"
    scores_norm = -scores_pointwise
    
    # Compute precision-recall curve
    precision, recall, thresholds = precision_recall_curve(y_true_pointwise, scores_norm)
    
    # Find candidates meeting precision (and optionally recall) constraints
    candidates = []
    for i in range(len(thresholds)):
        p = precision[i]
        r = recall[i]
        
        # Check precision constraint
        if p < min_precision:
            continue
        
        # Check recall constraint if provided
        if min_recall is not None and r < min_recall:
            continue
        
        # Compute F1
        if p + r > 0:
            f1 = 2 * (p * r) / (p + r)
        else:
            f1 = 0.0
        
        candidates.append({
            'idx': i,
            'precision': p,
            'recall': r,
            'f1': f1,
            'threshold_norm': thresholds[i]
        })
    
    # Choose candidate with MAX recall (if tie, max F1)
    if len(candidates) == 0:
        return {
            "min_precision": min_precision,
            "min_recall": min_recall,
            "chosen_threshold": None,
            "precision_at_threshold": None,
            "recall_at_threshold": None,
            "f1_at_threshold": None,
            "flagged_points": 0,
            "gt_positive_points": int(y_true_pointwise.sum())
        }
    
    # Sort by recall (descending), then F1 (descending)
    candidates.sort(key=lambda x: (x['recall'], x['f1']), reverse=True)
    best = candidates[0]
    
    # Convert threshold back to original score space
    chosen_threshold = -best['threshold_norm']
    
    # Compute flagged points at this threshold
    flagged_mask = scores_pointwise <= chosen_threshold
    flagged_points = int(flagged_mask.sum())
    
    return {
        "min_precision": min_precision,
        "min_recall": min_recall,
        "chosen_threshold": float(chosen_threshold),
        "precision_at_threshold": float(best['precision']),
        "recall_at_threshold": float(best['recall']),
        "f1_at_threshold": float(best['f1']),
        "flagged_points": flagged_points,
        "gt_positive_points": int(y_true_pointwise.sum())
    }


def get_scores_for_roc(df_in: pd.DataFrame) -> np.ndarray | None:
    """
    Compute scores for ROC/PR for ALL rows in df_in (same length, same order).

    - If model supports predict_proba: returns P(spoofing) in [0,1] (higher = more spoofing)
    - Else (IsolationForest style): returns anomaly score (lower = more anomalous)
    """
    try:
        model_path = backend_dir / "app" / "ml" / "spoofing_model.pkl"
        if not model_path.exists():
            return None

        model = joblib.load(str(model_path))
        from app.core.anomaly_detection import haversine_nm_vec, _circular_heading_change

        df = df_in.copy()

        # Required columns
        for c in ["mmsi", "lat", "lon", "sog", "cog"]:
            if c not in df.columns:
                print(f"⚠️  ROC scoring skipped: missing column {c}")
                return None

        # Keep original order for output alignment
        df["_row_id__"] = np.arange(len(df), dtype=np.int64)

        # Parse timestamp (do NOT drop rows)
        df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce")

        # Sort only for feature diffs; restore original order at the end
        df = df.sort_values(["mmsi", "timestamp", "_row_id__"], kind="mergesort")

        # Core features
        df["speed"] = pd.to_numeric(df["sog"], errors="coerce").clip(0, 60).fillna(0)

        df["heading_change"] = (
            df.groupby("mmsi")["cog"]
              .apply(_circular_heading_change)
              .reset_index(level=0, drop=True)
              .fillna(0)
        )

        lat_prev = df.groupby("mmsi")["lat"].shift(1)
        lon_prev = df.groupby("mmsi")["lon"].shift(1)

        df["jump_distance"] = haversine_nm_vec(
            pd.to_numeric(df["lat"], errors="coerce").fillna(0),
            pd.to_numeric(df["lon"], errors="coerce").fillna(0),
            pd.to_numeric(lat_prev, errors="coerce").fillna(0),
            pd.to_numeric(lon_prev, errors="coerce").fillna(0),
        ).replace([np.inf, -np.inf], 0).fillna(0)

        df["time_gap"] = (
            df.groupby("mmsi")["timestamp"]
              .diff()
              .dt.total_seconds()
              .replace([np.inf, -np.inf], np.nan)
              .fillna(0)
        )

        df["speed_change"] = df.groupby("mmsi")["speed"].diff().abs().fillna(0)

        # Match training: ignore tiny gaps (<30s) to avoid noisy division
        safe_gap = df["time_gap"].where(df["time_gap"] >= 30, np.nan)

        df["acceleration"] = (df["speed_change"] / safe_gap).replace([np.inf, -np.inf], 0).fillna(0)
        df["turn_rate"] = (df["heading_change"] / safe_gap).replace([np.inf, -np.inf], 0).fillna(0)

        features = ["speed", "heading_change", "jump_distance", "time_gap",
                    "speed_change", "acceleration", "turn_rate"]

        X = df[features].replace([np.inf, -np.inf], 0).fillna(0)

        # Scoring: supervised vs unsupervised
        if hasattr(model, "predict_proba"):
            scores = model.predict_proba(X)[:, 1]          # higher = more spoofing
        elif hasattr(model, "decision_function"):
            scores = model.decision_function(X)            # IF: lower = more anomalous
        elif hasattr(model, "score_samples"):
            scores = model.score_samples(X)                # IF: lower = more anomalous
        else:
            return None

        # Restore original row order
        out = pd.DataFrame({"_row_id__": df["_row_id__"].to_numpy(), "score": scores})
        out = out.sort_values("_row_id__", kind="mergesort")

        scores_out = out["score"].to_numpy()

        if len(scores_out) != len(df_in):
            print(f"⚠️  ROC scoring length mismatch: scores={len(scores_out)} rows={len(df_in)}")
            return None

        return scores_out

    except Exception as e:
        print(f"⚠️  Could not compute scores for ROC: {e}")
        return None
        
    
def evaluate_detection(
    test_df: pd.DataFrame,
    detection_func,
    gt_column: str,
    detection_type: str,
    score_threshold: float | None = None
):
    print(f"\n🔍 Running {detection_type} detection on test set...")
    import inspect

    # 1) RUN DETECTOR FIRST
    if detection_type == "spoofing" and score_threshold is not None:
        sig = inspect.signature(detection_func)
        params = sig.parameters

        if "score_threshold" in params:
            predictions_df = detection_func(test_df, score_threshold=score_threshold)
            print(f"   Using calibrated threshold (score_threshold): {score_threshold:.4f}")
        else:
            predictions_df = detection_func(test_df)
    else:
        predictions_df = detection_func(test_df)

    if predictions_df is None:
        predictions_df = pd.DataFrame()

    debug_matching_stats(predictions_df, test_df, gt_column, MATCHING_TOLERANCE_SEC)
    print(f"   Detected {len(predictions_df)} {detection_type} raw prediction rows")

    # 2) EVENT BUILDING PARAMS (different for spoofing vs loitering)
    if detection_type == "loitering":
        gt_events = build_gt_events(
            test_df, gt_column,
            gap_sec=MATCHING_TOLERANCE_SEC,
            min_points=5,
            min_duration_sec=int(3 * 3600)
        )
        pred_events = build_pred_events(
            predictions_df,
            gap_sec=MATCHING_TOLERANCE_SEC,
            min_points=5,
            min_duration_sec=int(3 * 3600)
        )
    else:
        gt_events = build_gt_events(
            test_df, gt_column,
            gap_sec=MATCHING_TOLERANCE_SEC,
            min_points=3,
            min_duration_sec=60
        )
        pred_events = build_pred_events(
            predictions_df,
            gap_sec=MATCHING_TOLERANCE_SEC,
            min_points=3,
            min_duration_sec=60
        )

    if pred_events is None or pred_events.empty:
        pred_events = pd.DataFrame(columns=["mmsi","start_ts","end_ts","n_points","duration_sec"])

    y_true, y_pred = match_pred_events_to_gt_events(pred_events, gt_events)

    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
    recall    = float(tp / (tp + fn)) if (tp + fn) else 0.0
    f1        = float(2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    metrics = {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn},
        "gt_events": int(len(gt_events)),
        "pred_events": int(len(pred_events)),
    }
    return metrics, predictions_df



def _cm_get(metrics: dict):
    cm = (metrics or {}).get("confusion_matrix", {}) or {}

    # Case A: dict with named keys
    if isinstance(cm, dict):
        tp = cm.get("true_positives", cm.get("tp", 0))
        fp = cm.get("false_positives", cm.get("fp", 0))
        fn = cm.get("false_negatives", cm.get("fn", 0))
        tn = cm.get("true_negatives", cm.get("tn", None))
        return int(tp or 0), int(fp or 0), int(fn or 0), (None if tn is None else int(tn))

    # Case B: 2x2 matrix [[tn, fp],[fn,tp]]
    try:
        arr = np.array(cm)
        if arr.shape == (2, 2):
            tn = int(arr[0, 0])
            fp = int(arr[0, 1])
            fn = int(arr[1, 0])
            tp = int(arr[1, 1])
            return tp, fp, fn, tn
    except Exception:
        pass

    return 0, 0, 0, None


def generate_research_summary(experiment_id: str, dataset_stats: Dict, split_stats: Dict,
                             spoofing_metrics: Dict, loitering_metrics: Dict, output_path: Path,
                             pointwise_roc_auc: float = None):
    
    spoof_tp, spoof_fp, spoof_fn, spoof_tn = _cm_get(spoofing_metrics)
    loit_tp, loit_fp, loit_fn, loit_tn = _cm_get(loitering_metrics)

    def _fmt_tn(x):
        return "N/A" if x is None else str(int(x))

    spoof_tn_s = _fmt_tn(spoof_tn)
    loit_tn_s  = _fmt_tn(loit_tn)

    """Generate research summary markdown."""
    content = f"""# Evaluation Results Summary

**Experiment ID:** `{experiment_id}`  
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Dataset Statistics

- **Total rows:** {dataset_stats['total_rows']:,}
- **Unique MMSIs:** {dataset_stats['unique_mmsis']:,}
- **Spoofing positives:** {dataset_stats['spoofing_positives']:,} ({dataset_stats['spoofing_pct']:.2f}%)
- **Loitering positives:** {dataset_stats['loitering_positives']:,} ({dataset_stats['loitering_pct']:.2f}%)
- **Total anomaly points:** {dataset_stats['total_anomalies']:,} ({dataset_stats['anomaly_pct']:.2f}%)

---

## Train/Test Split Statistics

### Training Set
- **Rows:** {split_stats['train_rows']:,}
- **Spoofing positives:** {split_stats['train_spoofing']:,}
- **Loitering positives:** {split_stats['train_loitering']:,}

### Test Set
- **Rows:** {split_stats['test_rows']:,}
- **Spoofing positives:** {split_stats['test_spoofing']:,}
- **Loitering positives:** {split_stats['test_loitering']:,}

---

## Detection Performance (EVENT-LEVEL)

### Spoofing Detection

| Metric | Value |
|--------|-------|
| Precision | {spoofing_metrics['precision']:.4f} |
| Recall | {spoofing_metrics['recall']:.4f} |
| F1-Score | {spoofing_metrics['f1']:.4f} |
| ROC AUC (point-wise) | {f"{pointwise_roc_auc:.4f}" if pointwise_roc_auc is not None else "N/A"} |
| True Positives | {spoof_tp} |
| False Positives | {spoof_fp} |
| False Negatives | {spoof_fn} |
| True Negatives | {spoof_tn_s} |
| Pred Events | {spoofing_metrics.get('pred_events','N/A')} |
| GT Events | {spoofing_metrics.get('gt_events','N/A')} |

### Loitering Detection

| Metric | Value |
|--------|-------|
| Precision | {loitering_metrics['precision']:.4f} |
| Recall | {loitering_metrics['recall']:.4f} |
| F1-Score | {loitering_metrics['f1']:.4f} |
| True Positives | {loit_tp} |
| False Positives | {loit_fp} |
| False Negatives | {loit_fn} |
| True Negatives | {loit_tn_s} |
| Pred Events | {loitering_metrics.get('pred_events','N/A')} |
| GT Events | {loitering_metrics.get('gt_events','N/A')} |

---

## Notes

- Metrics above are **event-level** (overlapping time windows per MMSI).
- Confusion matrix PNGs are still generated **point-wise** (per-row), useful for sanity checks.
- Isolation Forest model was pre-trained and not retrained on this dataset.
- DBSCAN loitering detection runs directly on test set (no pre-training).
- Time-based split ensures no data leakage between train and test sets.

"""
    with open(output_path, 'w') as f:
        f.write(content)
    print(f"📝 Research summary saved to: {output_path}")


def events_to_point_predictions(pred_df):
    if pred_df is None or pred_df.empty:
        return pred_df

    candidates = [
        ('start_ts','end_ts'),
        ('start_time','end_time'),
        ('start','end'),
        ('start_timestamp','end_timestamp'),
    ]

    for s, e in candidates:
        if s in pred_df.columns and e in pred_df.columns:
            tmp = pred_df[['mmsi', s, e]].copy()
            tmp[s] = pd.to_datetime(tmp[s], errors="coerce")
            tmp[e] = pd.to_datetime(tmp[e], errors="coerce")
            tmp = tmp.dropna(subset=[s, e])

            # create 3 representative points per event: start, mid, end
            mid = tmp[s] + (tmp[e] - tmp[s]) / 2
            out = pd.concat([
                tmp[['mmsi', s]].rename(columns={s: 'timestamp'}),
                pd.DataFrame({'mmsi': tmp['mmsi'].values, 'timestamp': mid.values}),
                tmp[['mmsi', e]].rename(columns={e: 'timestamp'}),
            ], ignore_index=True)

            return out

    return pred_df



def main():
    """Main evaluation function."""
    debug_environment()

    print("="*80)
    print("EVALUATION WITH TIME-BASED TRAIN/TEST SPLIT")
    print("="*80)

    synthetic_dir = backend_dir / "data" / "synthetic"
    synthetic_dir.mkdir(parents=True, exist_ok=True)

    input_csv = find_latest_synthetic_dataset(synthetic_dir)

    print(f"\n📂 Loading dataset: {input_csv.name}")
    df = pd.read_csv(input_csv)
    print(f"   Loaded {len(df):,} rows")

    print("\n🧹 Cleaning and preprocessing...")
    df = clean_and_preprocess(df)
    print(f"   After cleaning: {len(df):,} rows")

    required_gt_cols = ['gt_spoofing', 'gt_loitering', 'gt_anomaly']
    missing_gt = [c for c in required_gt_cols if c not in df.columns]
    if missing_gt:
        raise ValueError(f"Missing ground truth columns: {missing_gt}")

    dataset_stats = {
        'total_rows': len(df),
        'unique_mmsis': df['mmsi'].nunique(),
        'spoofing_positives': int(df['gt_spoofing'].sum()),
        'loitering_positives': int(df['gt_loitering'].sum()),
        'total_anomalies': int(df['gt_anomaly'].sum())
    }
    dataset_stats['spoofing_pct'] = (dataset_stats['spoofing_positives'] / dataset_stats['total_rows'] * 100) if dataset_stats['total_rows'] > 0 else 0
    dataset_stats['loitering_pct'] = (dataset_stats['loitering_positives'] / dataset_stats['total_rows'] * 100) if dataset_stats['total_rows'] > 0 else 0
    dataset_stats['anomaly_pct'] = (dataset_stats['total_anomalies'] / dataset_stats['total_rows'] * 100) if dataset_stats['total_rows'] > 0 else 0

    print("\n📊 Performing MMSI-based train/test split...")
    train_df, test_df = split_by_mmsi(df, train_frac=TRAIN_SPLIT, seed=42)
    print_split_statistics(train_df, test_df)

    # HARD CHECK: no MMSI leakage
    train_m = set(train_df["mmsi"].dropna().astype(int).unique())
    test_m  = set(test_df["mmsi"].dropna().astype(int).unique())
    print("MMSI overlap (must be 0):", len(train_m.intersection(test_m)))

    gt_loit_events = build_gt_events(test_df, 'gt_loitering', gap_sec=300, min_points=5, min_duration_sec=60)
    print("GT loitering events (test):", len(gt_loit_events))
    if len(gt_loit_events) > 0:
        print("GT loitering duration (sec) describe:")
        print(gt_loit_events['duration_sec'].describe())

    # Split train into train_sub and val for threshold calibration (80/20)
    print("\n📊 Performing time-based train/val split for threshold calibration...")
    train_sub, val_df = split_by_mmsi(train_df, train_frac=0.8, seed=43)
    print(f"   Train sub: {len(train_sub):,} rows ({int(train_sub['gt_spoofing'].sum()):,} spoofing positives)")
    print(f"   Val: {len(val_df):,} rows ({int(val_df['gt_spoofing'].sum()):,} spoofing positives)")

    # Calibrate spoofing threshold on validation set
    print("\n🔧 Loading spoofing threshold...")

    THRESH_PATH = "app/ml/spoofing_threshold.txt"
    MODEL_PATH = "app/ml/spoofing_model.pkl"

    chosen_threshold = None

    # Load model to check if it supports predict_proba
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        is_supervised = hasattr(model, "predict_proba")
    else:
        print("   ⚠️ No spoofing model found.")
        is_supervised = False

    if is_supervised and os.path.exists(THRESH_PATH):
        with open(THRESH_PATH, "r") as f:
            chosen_threshold = float(f.read().strip())
        print(f"   ✅ Using saved supervised threshold: {chosen_threshold:.6f}")

    elif not is_supervised:
        print("   ℹ️ Unsupervised spoofing model detected — skipping probability threshold file.")
        chosen_threshold = None

    else:
        print("   ⚠️ No saved threshold found. chosen_threshold = None")
        # -----------------------------
        # Existing validation calibration
        # -----------------------------
        val_scores = get_scores_for_roc(val_df)

        if val_scores is not None and len(val_scores) > 0:
            y_true_val = (val_df['gt_spoofing'] == 1).astype(int).values
            if len(val_scores) == len(y_true_val) and len(np.unique(y_true_val)) > 1:
                pr_info_val = compute_pr_and_best_threshold(y_true_val, val_scores)
                chosen_threshold = pr_info_val.get('best_threshold', None)
                print(
                    f"   ✅ PR calibration (val): AP={pr_info_val['average_precision']:.4f}, "
                    f"best_threshold={chosen_threshold}, best_f1={pr_info_val['best_f1']:.4f}"
                )
            else:
                print("   ⚠️  PR calibration (val): insufficient positives/classes")
        else:
            print("   ⚠️  PR calibration (val): scores unavailable")

    # -----------------------------
    # Env override still allowed
    # -----------------------------
    env_thr = get_env_threshold("SPOOFING_SCORE_THRESHOLD")
    if env_thr is not None:
        chosen_threshold = env_thr
        print(f"\n✅ Overriding threshold from env: SPOOFING_SCORE_THRESHOLD={chosen_threshold:.6f}")
    else:
        print(f"\nℹ️ Final spoofing threshold: {chosen_threshold}")
        
    val_scores = None    
    split_stats = {
        'train_rows': len(train_df),
        'test_rows': len(test_df),
        'train_spoofing': int(train_df['gt_spoofing'].sum()),
        'test_spoofing': int(test_df['gt_spoofing'].sum()),
        'train_loitering': int(train_df['gt_loitering'].sum()),
        'test_loitering': int(test_df['gt_loitering'].sum())
    }

    experiment_id = str(uuid.uuid4())
    output_dir = backend_dir / "data" / "jobs" / experiment_id
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n💾 Output directory: {output_dir}")

    spoofing_metrics, spoofing_predictions = evaluate_detection(
    test_df, detect_spoofing_events, 'gt_spoofing', 'spoofing', score_threshold=chosen_threshold
)
    print("\n🔎 DEBUG: Spoofing prediction structure")
    print("Columns:", list(spoofing_predictions.columns))
    print(spoofing_predictions.head(3))
    print("predictions timestamp nulls:",
      int(spoofing_predictions["timestamp"].isna().sum()) if "timestamp" in spoofing_predictions else "no timestamp col")
    print("unique predicted mmsi:",
      int(spoofing_predictions["mmsi"].nunique()) if "mmsi" in spoofing_predictions else "no mmsi col")


    loitering_metrics, loitering_predictions = evaluate_detection(
        test_df, detect_loitering_events, 'gt_loitering', 'loitering'
    )
    print("\n🔎 DEBUG: Loitering prediction structure")
    print("Columns:", list(loitering_predictions.columns))
    print(loitering_predictions.head(3))

    print("\n📊 Generating plots (POINT-WISE sanity check)...")

    # Optional: speed up point-wise matching by sampling
    MAX_CM_ROWS = 300000
    if len(test_df) > MAX_CM_ROWS:
        print(f"   ⚡ Using sampled subset for point-wise plots ({MAX_CM_ROWS} rows)")
        test_df_cm = test_df.sample(n=MAX_CM_ROWS, random_state=42)
    else:
        test_df_cm = test_df

    # Convert event outputs to point predictions (if needed)
    spoofing_predictions_cm = events_to_point_predictions(spoofing_predictions)

    y_true_spoofing_cm, y_pred_spoofing_cm = match_predictions_to_ground_truth(
    spoofing_predictions_cm, test_df_cm, 'gt_spoofing',
    tolerance_sec=MATCHING_TOLERANCE_SEC
)

    cm_spoofing_saved = plot_confusion_matrix(
        y_true_spoofing_cm, y_pred_spoofing_cm,
        "Confusion Matrix - Spoofing Detection (Point-wise)",
        output_dir / "confusion_matrix_spoofing.png",
        dpi=DPI
    )

    loitering_predictions_cm = events_to_point_predictions(loitering_predictions)
    y_true_loitering, y_pred_loitering = match_predictions_to_ground_truth(
    loitering_predictions_cm, test_df_cm, 'gt_loitering',
    tolerance_sec=MATCHING_TOLERANCE_SEC
)
    cm_loitering_saved = plot_confusion_matrix(
        y_true_loitering, y_pred_loitering,
        "Confusion Matrix - Loitering Detection (Point-wise)",
        output_dir / "confusion_matrix_loitering.png",
        dpi=DPI
    )

    # ROC/PR computation: use direct labels (no matching needed)
    # Get scores for all test rows

    test_sample = test_df_cm.sample(n=min(300000, len(test_df_cm)), random_state=42)
    scores_pointwise = get_scores_for_roc(test_sample)
    y_true_pointwise = (test_sample['gt_spoofing'] == 1).astype(int).values
    
    # ROC curve (spoofing only) - computed using POINT-WISE arrays with direct labels
    roc_saved = False
    pointwise_roc_auc = None
    pointwise_roc_curve = None
    
    if scores_pointwise is not None and len(scores_pointwise) > 0:
        if len(scores_pointwise) != len(y_true_pointwise):
            print(f"   ⚠️  Skipped: roc_curve.png (length mismatch: scores={len(scores_pointwise)}, y_true={len(y_true_pointwise)})")
        elif len(np.unique(y_true_pointwise)) <= 1:
            print(f"   ⚠️  Skipped: roc_curve.png (insufficient classes in y_true)")
        else:
            try:
                # Compute ROC using point-wise arrays with direct labels
                scores_normalized = -scores_pointwise  # Flip for ROC (higher = more anomalous)
                fpr, tpr, thresholds = roc_curve(y_true_pointwise, scores_normalized)
                roc_auc = auc(fpr, tpr)
                pointwise_roc_auc = float(roc_auc)
                pointwise_roc_curve = {
                    'fpr': fpr.tolist(),
                    'tpr': tpr.tolist(),
                    'thresholds': thresholds.tolist()
                }
                roc_saved = plot_roc_curve(fpr, tpr, roc_auc, output_dir / "roc_curve.png", dpi=DPI)
            except Exception as e:
                print(f"   ⚠️  Skipped: roc_curve.png (error: {type(e).__name__}: {e})")
    else:
        print("   ⚠️  Skipped: roc_curve.png (scores unavailable)")

    # --- PR Curve (Spoofing) ---
    pr_saved = False
    if scores_pointwise is not None and len(scores_pointwise) > 0:
        if len(scores_pointwise) == len(y_true_pointwise) and len(np.unique(y_true_pointwise)) > 1:
            pr_saved = plot_pr_curve(
                y_true_pointwise,
                scores_pointwise,
                output_dir / "pr_curve.png",
                dpi=DPI,
                is_supervised=is_supervised
        )
        else:
            print("   ⚠️  Skipped: pr_curve.png (invalid labels or length mismatch)")
    else:
        print("   ⚠️  Skipped: pr_curve.png (scores unavailable)")


    # PR threshold calibration (on test set for reporting only - threshold was chosen on val)
    # Note: This is for reporting/test visualization only. The actual threshold used for detection
    # was calibrated on the validation set to avoid data leakage.
    # Uses direct labels (y_true_pointwise) instead of matched predictions for cleaner PR computation.
    pr_info = None
    if scores_pointwise is not None and len(scores_pointwise) > 0:
        if len(scores_pointwise) == len(y_true_pointwise) and len(np.unique(y_true_pointwise)) > 1:
            try:
                pr_info = compute_pr_and_best_threshold(y_true_pointwise, scores_pointwise)
                print(f"   📊 PR calibration (test, for reference): AP={pr_info['average_precision']:.4f}, best_threshold={pr_info['best_threshold']:.4f}, best_f1={pr_info['best_f1']:.4f}")
                print(f"   ⚠️  Note: Threshold used for detection was calibrated on validation set, not test set")
            except Exception as e:
                print(f"   ⚠️  PR calibration (test) failed: {type(e).__name__}: {e}")
                pr_info = None

    # Precision-first threshold calibration (on test set for reporting only)
    # Uses direct labels (y_true_pointwise) instead of matched predictions for cleaner PR computation.
    prec_info = None
    if scores_pointwise is not None and len(scores_pointwise) > 0:
        if len(scores_pointwise) == len(y_true_pointwise) and len(np.unique(y_true_pointwise)) > 1:
            try:
                prec_info = choose_threshold_for_min_precision(
                    y_true_pointwise, scores_pointwise, MIN_SPOOFING_PRECISION, MIN_SPOOFING_RECALL
                )
                if prec_info['chosen_threshold'] is not None:
                    print(f"   📌 Precision-first threshold (test, for reference): min_precision={prec_info['min_precision']:.2f}, chosen_threshold={prec_info['chosen_threshold']:.4f}, P={prec_info['precision_at_threshold']:.4f}, R={prec_info['recall_at_threshold']:.4f}, F1={prec_info['f1_at_threshold']:.4f}, flagged={prec_info['flagged_points']}/{len(y_true_pointwise)}")
                else:
                    print(f"   ⚠️  Precision-first calibration (test): No threshold found meeting min_precision={MIN_SPOOFING_PRECISION:.2f}")
            except Exception as e:
                print(f"   ⚠️  Precision-first calibration (test) failed: {type(e).__name__}: {e}")
                prec_info = None

    print("\n📊 PLOTS GENERATED:")
    plot_status = [
    ("confusion_matrix_spoofing.png", cm_spoofing_saved),
    ("confusion_matrix_loitering.png", cm_loitering_saved),
    ("roc_curve.png", roc_saved),
    ("pr_curve.png", pr_saved),
]
    for filename, saved in plot_status:
        status = "✅ saved" if saved else "⚠️  skipped"
        print(f"   {status}: {filename}")

    results = {
        'experiment_id': experiment_id,
        'timestamp': datetime.now().isoformat(),
        'input_csv': str(input_csv.name),
        'dataset_stats': dataset_stats,
        'split_stats': split_stats,
        'spoofing': spoofing_metrics,
        'loitering': loitering_metrics,
        'spoofing_pointwise_roc_auc': pointwise_roc_auc,
        'spoofing_pointwise_roc_curve': pointwise_roc_curve,
        'spoofing_pr': pr_info,
        'matching_tolerance_sec': MATCHING_TOLERANCE_SEC,
        'train_split': TRAIN_SPLIT
        
    }

    with open(output_dir / "evaluation_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    print(f"   ✅ Evaluation results saved")

    # Save spoofing threshold (use validation-calibrated threshold if available, otherwise test set threshold for reference)
    threshold_to_save = chosen_threshold if chosen_threshold is not None else (pr_info['best_threshold'] if pr_info and pr_info.get('best_threshold') is not None else None)
    if threshold_to_save is not None:
        threshold_data = {
            "threshold": threshold_to_save,
            "method": "PR_maxF1",
            "calibrated_on": "validation" if chosen_threshold is not None else "test"
        }
        with open(output_dir / "spoofing_threshold.json", 'w') as f:
            json.dump(threshold_data, f, indent=2)
        print(f"   ✅ Saved spoofing threshold: {threshold_to_save:.4f} (calibrated on {'validation' if chosen_threshold is not None else 'test'})")

    # Save precision-first threshold if calibration succeeded
    if prec_info and prec_info.get('chosen_threshold') is not None:
        threshold_prec_data = {
            "threshold": prec_info['chosen_threshold'],
            "min_precision": prec_info['min_precision'],
            "min_recall": prec_info['min_recall'],
            "precision": prec_info['precision_at_threshold'],
            "recall": prec_info['recall_at_threshold'],
            "f1": prec_info['f1_at_threshold'],
            "flagged_points": prec_info['flagged_points'],
            "gt_positive_points": prec_info['gt_positive_points']
        }
        with open(output_dir / "spoofing_threshold_precision_first.json", 'w') as f:
            json.dump(threshold_prec_data, f, indent=2)
        print(f"   ✅ Saved precision-first threshold: {prec_info['chosen_threshold']:.4f}")

    metadata = {
        'experiment_id': experiment_id,
        'timestamp': datetime.now().isoformat(),
        'input_csv': str(input_csv.name),
        'parameters': {
            'dbscan': {'eps_nm': 1.0, 'min_samples': 5, 'min_dwell_hours': 3},
            'isolation_forest': {'model_path': 'app/ml/spoofing_model.pkl', 'note': 'Pre-trained model, not retrained'}
        },
        'runtime_seconds': None,
        'data_stats': dataset_stats
    }

    with open(output_dir / "experiment_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   ✅ Experiment metadata saved")

    generate_research_summary(
        experiment_id, dataset_stats, split_stats,
        spoofing_metrics, loitering_metrics,
        output_dir / "research_summary.md",
        pointwise_roc_auc
    )

    print("\n" + "="*80)
    print("EVALUATION COMPLETE")
    print("="*80)
    print(f"\n📊 Results Summary (EVENT-LEVEL):")
    print(f"   GT spoofing events: {spoofing_metrics.get('gt_events')}, Pred spoofing events: {spoofing_metrics.get('pred_events')}")
    print(f"   GT loitering events: {loitering_metrics.get('gt_events')}, Pred loitering events: {loitering_metrics.get('pred_events')}")
    print(f"   Spoofing F1: {spoofing_metrics['f1']:.4f}")
    print(f"   Loitering F1: {loitering_metrics['f1']:.4f}")
    roc_auc_display = f"{pointwise_roc_auc:.4f}" if pointwise_roc_auc is not None else "N/A"
    print(f"   ROC AUC (spoofing, point-wise): {roc_auc_display}")
    print(f"\n💾 All outputs saved to: {output_dir}")
    print("="*80 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())

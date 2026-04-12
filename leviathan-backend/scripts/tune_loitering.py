import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import pandas as pd
import numpy as np

from app.core.preprocessing import clean_and_preprocess
from app.core.anomaly_detection import detect_loitering_events
from scripts.evaluate_with_labels import build_gt_events, build_pred_events, match_pred_events_to_gt_events

DATA = "data/synthetic/ais_synth_labeled_20260219_121428.csv"

def run_one(df, eps_nm, min_samples, dwell_hr, low_speed, tol=300):
    os.environ["LOITERING_EPS_NM"] = str(eps_nm)
    os.environ["LOITERING_MIN_SAMPLES"] = str(min_samples)
    os.environ["LOITERING_MIN_DWELL_HOURS"] = str(dwell_hr)
    os.environ["LOW_SPEED_THRESHOLD"] = str(low_speed)

    pred = detect_loitering_events(df)

    gt_events = build_gt_events(df, "gt_loitering", gap_sec=tol, min_points=5, min_duration_sec=60)
    pred_events = build_pred_events(pred, gap_sec=tol, min_points=5, min_duration_sec=60)

    y_true, y_pred = match_pred_events_to_gt_events(pred_events, gt_events)

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2*p*r/(p+r)) if (p+r) else 0.0

    return f1, p, r, len(pred_events), len(gt_events)

def main():
    df = pd.read_csv(DATA, nrows=800000)  # keep it fast
    df = clean_and_preprocess(df)

    grid = []
    for eps_nm in [0.2, 0.3, 0.5, 0.8, 1.0]:
        for min_samples in [5, 8, 12]:
            for dwell_hr in [3, 6, 12]:
                for low_speed in [0.5, 1.0, 2.0]:
                    f1, p, r, pe, ge = run_one(df, eps_nm, min_samples, dwell_hr, low_speed)
                    grid.append((f1, p, r, eps_nm, min_samples, dwell_hr, low_speed, pe, ge))
                    print(f"F1={f1:.4f} P={p:.4f} R={r:.4f} eps={eps_nm} minS={min_samples} dwell={dwell_hr} lowSp={low_speed} predE={pe} gtE={ge}")

    grid.sort(reverse=True, key=lambda x: x[0])
    best = grid[0]
    print("\nBEST:", best)

if __name__ == "__main__":
    main()
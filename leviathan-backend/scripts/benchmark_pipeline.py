#!/usr/bin/env python3
"""
benchmark_pipeline.py — Leviathan pipeline benchmarking suite.

Measures per-stage timing, peak memory, feature distributions,
anomaly counts, and payload sizes for OLD vs NEW pipeline.

Usage:
    python scripts/benchmark_pipeline.py --csv path/to/ais.csv [--runs 3]

Outputs:
    - Console summary table
    - benchmark_results_<timestamp>.json
"""

import argparse
import gc
import json
import logging
import os
import sys
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-25s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")

# ── Add project root to path ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# MEASUREMENT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

class StageResult:
    """Holds timing, memory, and output metrics for one pipeline stage."""
    def __init__(self, name: str):
        self.name        = name
        self.elapsed_ms  = 0.0
        self.peak_mb     = 0.0
        self.current_mb  = 0.0
        self.extra: Dict[str, Any] = {}

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "peak_mb":    round(self.peak_mb, 2),
            "current_mb": round(self.current_mb, 2),
            **self.extra,
        }


def measure(name: str, fn, *args, **kwargs) -> Tuple[Any, StageResult]:
    """
    Run fn(*args, **kwargs) while measuring wall-clock time and peak heap.
    Returns (result, StageResult).
    """
    r = StageResult(name)
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    finally:
        r.elapsed_ms = (time.perf_counter() - t0) * 1000
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        r.current_mb = current / 1_048_576
        r.peak_mb    = peak    / 1_048_576
    return result, r


def df_stats(df: pd.DataFrame) -> dict:
    """Compute per-column descriptive stats for feature parity comparison."""
    stats = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            s = df[col].dropna()
            stats[col] = {
                "mean": float(s.mean()),
                "std":  float(s.std()),
                "min":  float(s.min()),
                "max":  float(s.max()),
                "p95":  float(np.percentile(s, 95)),
            }
    return stats


def payload_size_bytes(obj: Any) -> int:
    """Estimate JSON-serialised size of a Python object in bytes."""
    return len(json.dumps(obj, default=str).encode("utf-8"))


def file_size_mb(path: str) -> float:
    return os.path.getsize(path) / 1_048_576 if os.path.exists(path) else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: CSV READ
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_csv_read(csv_path: str) -> Tuple[pd.DataFrame, StageResult]:
    """Measure CSV read time with and without dtype specification."""
    from app.core.ingestion_engine import _peek_columns, _build_read_kwargs

    columns     = _peek_columns(csv_path)
    read_kwargs = _build_read_kwargs(columns)
    file_mb     = file_size_mb(csv_path)

    df, r = measure("csv_read", pd.read_csv, csv_path, **read_kwargs)
    r.extra = {
        "file_mb":    round(file_mb, 1),
        "rows":       len(df),
        "cols":       len(df.columns),
        "memory_mb":  round(df.memory_usage(deep=True).sum() / 1_048_576, 1),
        "dtype_map":  {k: str(v) for k, v in (read_kwargs.get("dtype") or {}).items()},
    }
    return df, r


def benchmark_csv_read_naive(csv_path: str) -> Tuple[pd.DataFrame, StageResult]:
    """Baseline: read with no dtype specification (old behavior)."""
    df, r = measure("csv_read_naive", pd.read_csv, csv_path, low_memory=False)
    r.name = "csv_read_naive"
    r.extra = {
        "rows":       len(df),
        "cols":       len(df.columns),
        "memory_mb":  round(df.memory_usage(deep=True).sum() / 1_048_576, 1),
    }
    return df, r


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_preprocessing(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, StageResult]:
    from app.core.preprocessing import clean_and_preprocess

    df, r = measure("preprocessing", clean_and_preprocess, df_raw.copy())
    r.extra = {
        "rows_out":   len(df),
        "rows_in":    len(df_raw),
        "row_drop_pct": round((1 - len(df) / len(df_raw)) * 100, 1),
        "memory_mb":  round(df.memory_usage(deep=True).sum() / 1_048_576, 1),
        "dtypes":     {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
    return df, r


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3: FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_feature_engineering(df_clean: pd.DataFrame) -> Tuple[pd.DataFrame, StageResult]:
    from app.core.anomaly_detection import compute_kinematic_features

    work = df_clean[["mmsi", "lat", "lon", "sog", "cog", "timestamp"]
                    if "timestamp" in df_clean.columns
                    else ["mmsi", "lat", "lon", "sog", "cog"]].copy()

    df, r = measure("feature_engineering", compute_kinematic_features, work)
    feat_cols = ["heading_change", "jump_distance", "time_gap",
                 "speed_change", "acceleration", "turn_rate"]
    r.extra = {
        "rows": len(df),
        "feature_stats": df_stats(df[feat_cols]),
        "negative_time_gap_count": int((df["time_gap"] < 0).sum()),
        "inf_values": {
            col: int(np.isinf(df[col].values).sum())
            for col in feat_cols
            if pd.api.types.is_numeric_dtype(df[col])
        },
    }
    return df, r


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4: SPOOFING DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_spoofing_detection(df_clean: pd.DataFrame) -> Tuple[pd.DataFrame, StageResult]:
    from app.core.anomaly_detection import detect_spoofing_events

    df, r = measure("spoofing_detection", detect_spoofing_events, df_clean)
    r.extra = {
        "events_found":      len(df),
        "unique_mmsi":       int(df["mmsi"].nunique()) if not df.empty else 0,
        "severity_counts":   df["severity"].value_counts().to_dict() if not df.empty else {},
        "score_stats": {
            "mean": float(df["score"].mean()) if not df.empty else None,
            "min":  float(df["score"].min())  if not df.empty else None,
            "p5":   float(np.percentile(df["score"].dropna(), 5)) if not df.empty else None,
        },
    }
    return df, r


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5: LOITERING DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_loitering_detection(df_clean: pd.DataFrame) -> Tuple[pd.DataFrame, StageResult]:
    from app.core.anomaly_detection import detect_loitering_events

    df, r = measure("loitering_detection", detect_loitering_events, df_clean)
    r.extra = {
        "events_found":    len(df),
        "unique_mmsi":     int(df["mmsi"].nunique()) if not df.empty else 0,
        "severity_counts": df["severity"].value_counts().to_dict() if not df.empty else {},
        "dwell_time_stats": {
            "mean_hr": float(df["dwell_time_hr"].mean()) if not df.empty else None,
            "max_hr":  float(df["dwell_time_hr"].max())  if not df.empty else None,
        },
    }
    return df, r


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 6: PAYLOAD GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_payload_generation(
    df_clean: pd.DataFrame,
    spoofing_events: pd.DataFrame,
    loitering_events: pd.DataFrame,
) -> Tuple[tuple, StageResult]:
    # Import _build_payloads from the route module
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.routes.ingestion import _build_payloads

    result, r = measure(
        "payload_generation",
        _build_payloads, df_clean, spoofing_events, loitering_events
    )
    live_alerts, vessel_logs, anomaly_reports, summary = result

    # Measure serialised sizes
    alerts_bytes  = payload_size_bytes(live_alerts)
    logs_bytes    = payload_size_bytes(vessel_logs)
    reports_bytes = payload_size_bytes(anomaly_reports)

    r.extra = {
        "live_alerts_count":     len(live_alerts),
        "vessel_logs_count":     len(vessel_logs),
        "live_alerts_size_kb":   round(alerts_bytes  / 1024, 1),
        "vessel_logs_size_kb":   round(logs_bytes    / 1024, 1),
        "anomaly_reports_size_b": reports_bytes,
        "total_payload_size_kb": round((alerts_bytes + logs_bytes + reports_bytes) / 1024, 1),
    }
    return result, r


# ─────────────────────────────────────────────────────────────────────────────
# FULL PIPELINE BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────

def run_full_benchmark(csv_path: str) -> dict:
    """Run all stages sequentially, collect metrics, return results dict."""
    logger.info(f"=" * 70)
    logger.info(f"BENCHMARK  {csv_path}  ({file_size_mb(csv_path):.1f} MB)")
    logger.info(f"=" * 70)

    results = {"csv_path": csv_path, "file_mb": file_size_mb(csv_path), "stages": []}

    # ── Read ─────────────────────────────────────────────────────────────────
    df_raw, r_read = benchmark_csv_read(csv_path)
    results["stages"].append(r_read.to_dict())
    logger.info(f"READ      {r_read.elapsed_ms:>8.1f} ms | {r_read.peak_mb:.1f} MB peak | {r_read.extra['rows']:,} rows")

    # ── Preprocess ───────────────────────────────────────────────────────────
    df_clean, r_pre = benchmark_preprocessing(df_raw)
    del df_raw
    gc.collect()
    results["stages"].append(r_pre.to_dict())
    logger.info(f"PREPROCESS {r_pre.elapsed_ms:>8.1f} ms | {r_pre.peak_mb:.1f} MB peak | {r_pre.extra['rows_out']:,} rows out")

    # ── Feature engineering ──────────────────────────────────────────────────
    df_feat, r_feat = benchmark_feature_engineering(df_clean)
    results["stages"].append(r_feat.to_dict())
    logger.info(f"FEATURES  {r_feat.elapsed_ms:>8.1f} ms | {r_feat.peak_mb:.1f} MB peak")

    if r_feat.extra["negative_time_gap_count"] > 0:
        logger.warning(f"⚠ NEGATIVE time_gap: {r_feat.extra['negative_time_gap_count']} rows — sort check may have misfired!")

    # ── Spoofing ─────────────────────────────────────────────────────────────
    sp_events, r_sp = benchmark_spoofing_detection(df_clean)
    results["stages"].append(r_sp.to_dict())
    logger.info(f"SPOOFING  {r_sp.elapsed_ms:>8.1f} ms | {r_sp.peak_mb:.1f} MB peak | {r_sp.extra['events_found']} events")

    # ── Loitering ────────────────────────────────────────────────────────────
    lt_events, r_lt = benchmark_loitering_detection(df_clean)
    results["stages"].append(r_lt.to_dict())
    logger.info(f"LOITERING {r_lt.elapsed_ms:>8.1f} ms | {r_lt.peak_mb:.1f} MB peak | {r_lt.extra['events_found']} events")

    # ── Payloads ─────────────────────────────────────────────────────────────
    payloads, r_pay = benchmark_payload_generation(df_clean, sp_events, lt_events)
    del df_clean
    gc.collect()
    results["stages"].append(r_pay.to_dict())
    logger.info(
        f"PAYLOADS  {r_pay.elapsed_ms:>8.1f} ms | {r_pay.peak_mb:.1f} MB peak | "
        f"alerts: {r_pay.extra['live_alerts_size_kb']} KB, "
        f"logs: {r_pay.extra['vessel_logs_size_kb']} KB"
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    total_ms   = sum(s["elapsed_ms"] for s in results["stages"])
    total_peak = max(s["peak_mb"]    for s in results["stages"])
    results["total_ms"]   = round(total_ms, 1)
    results["peak_mb"]    = round(total_peak, 1)
    results["timestamp"]  = datetime.now().isoformat()

    logger.info(f"-" * 70)
    logger.info(f"TOTAL     {total_ms:>8.1f} ms | {total_peak:.1f} MB max stage peak")
    logger.info(f"=" * 70)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE PARITY COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def compare_feature_distributions(
    stats_old: dict,
    stats_new: dict,
    tolerance: dict = None,
) -> dict:
    """
    Compare feature statistics between old and new pipeline runs.
    Returns a dict of {feature: {metric: {old, new, delta, pass}}} .
    """
    default_tol = {
        "heading_change": 0.1,
        "jump_distance":  0.01,
        "time_gap":       1.0,
        "speed_change":   0.05,
        "acceleration":   0.01,
        "turn_rate":      0.001,
    }
    tol = {**default_tol, **(tolerance or {})}

    report = {}
    for feat in tol:
        if feat not in stats_old or feat not in stats_new:
            continue
        old = stats_old[feat]
        new = stats_new[feat]
        feat_tol = tol[feat]
        delta_mean = abs(old["mean"] - new["mean"])
        report[feat] = {
            "mean_old":   round(old["mean"], 6),
            "mean_new":   round(new["mean"], 6),
            "delta_mean": round(delta_mean, 6),
            "tolerance":  feat_tol,
            "pass":       delta_mean <= feat_tol,
        }

    return report


# ─────────────────────────────────────────────────────────────────────────────
# ANOMALY PARITY COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)


def compare_anomaly_results(
    old_spoofing:  pd.DataFrame,
    new_spoofing:  pd.DataFrame,
    old_loitering: pd.DataFrame,
    new_loitering: pd.DataFrame,
) -> dict:
    """Compare anomaly detection parity between old and new pipelines."""
    old_sp_mmsi = set(old_spoofing["mmsi"].unique()) if not old_spoofing.empty else set()
    new_sp_mmsi = set(new_spoofing["mmsi"].unique()) if not new_spoofing.empty else set()
    old_lt_mmsi = set(old_loitering["mmsi"].unique()) if not old_loitering.empty else set()
    new_lt_mmsi = set(new_loitering["mmsi"].unique()) if not new_loitering.empty else set()

    sp_jaccard = jaccard(old_sp_mmsi, new_sp_mmsi)
    lt_jaccard = jaccard(old_lt_mmsi, new_lt_mmsi)

    sp_count_delta_pct = (
        abs(len(new_spoofing) - len(old_spoofing)) / max(len(old_spoofing), 1) * 100
    )
    lt_count_delta_pct = (
        abs(len(new_loitering) - len(old_loitering)) / max(len(old_loitering), 1) * 100
    )

    return {
        "spoofing": {
            "old_count":       len(old_spoofing),
            "new_count":       len(new_spoofing),
            "count_delta_pct": round(sp_count_delta_pct, 1),
            "mmsi_jaccard":    round(sp_jaccard, 4),
            "pass_count":      sp_count_delta_pct <= 10,
            "pass_overlap":    sp_jaccard >= 0.85,
        },
        "loitering": {
            "old_count":       len(old_loitering),
            "new_count":       len(new_loitering),
            "count_delta_pct": round(lt_count_delta_pct, 1),
            "mmsi_jaccard":    round(lt_jaccard, 4),
            "pass_count":      lt_count_delta_pct <= 10,
            "pass_overlap":    lt_jaccard >= 0.85,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Leviathan pipeline benchmark")
    parser.add_argument("--csv", required=True, help="Path to AIS CSV file")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs to average")
    parser.add_argument("--out",  default=None, help="Output JSON path")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        logger.error(f"File not found: {args.csv}")
        sys.exit(1)

    all_results = []
    for i in range(args.runs):
        logger.info(f"\nRUN {i + 1}/{args.runs}")
        result = run_full_benchmark(args.csv)
        all_results.append(result)

    # Average over runs
    if args.runs > 1:
        avg = {"runs": args.runs, "csv_path": args.csv, "stages": []}
        for stage_idx in range(len(all_results[0]["stages"])):
            stage_results = [r["stages"][stage_idx] for r in all_results]
            avg_elapsed = sum(s["elapsed_ms"] for s in stage_results) / args.runs
            avg_peak    = sum(s["peak_mb"]    for s in stage_results) / args.runs
            avg["stages"].append({
                "name":       stage_results[0]["name"],
                "elapsed_ms": round(avg_elapsed, 1),
                "peak_mb":    round(avg_peak, 1),
            })
        final = avg
    else:
        final = all_results[0]

    out_path = args.out or f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(final, f, indent=2, default=str)
    logger.info(f"\nResults saved to: {out_path}")

    # Print acceptance check
    total_ms = final.get("total_ms") or sum(s["elapsed_ms"] for s in final["stages"])
    peak_mb  = final.get("peak_mb")  or max(s["peak_mb"] for s in final["stages"])
    print(f"\n{'='*50}")
    print(f"  Total time : {total_ms:>8.0f} ms  (target < 15,000 ms)")
    print(f"  Peak memory: {peak_mb:>8.1f} MB  (target < 60 MB)")
    print(f"  Time PASS  : {'✅' if total_ms < 15_000 else '❌'}")
    print(f"  Memory PASS: {'✅' if peak_mb < 60 else '❌'}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()

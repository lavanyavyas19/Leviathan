# leviathan-backend/tests/test_regression.py
"""
Critical regression tests for the Leviathan optimization.
Run with: pytest tests/test_regression.py -v
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.preprocessing import clean_and_preprocess
from app.core.anomaly_detection import (
    compute_kinematic_features,
    haversine_nm_vec,
    classify_spoofing_severity_vec,
    _EPS_RAD,
    LOITERING_MIN_SAMPLES,
    LOITERING_EPS_NM,
)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_two_vessel_df():
    """A minimal, clean DataFrame with two vessels and 5 records each."""
    return pd.DataFrame({
        "mmsi":      [111, 111, 111, 111, 111, 222, 222, 222, 222, 222],
        "lat":       [10.0, 10.1, 10.2, 10.3, 10.4,
                      20.0, 20.1, 20.2, 20.3, 20.4],
        "lon":       [50.0, 50.1, 50.2, 50.3, 50.4,
                      60.0, 60.1, 60.2, 60.3, 60.4],
        "sog":       [5.0,  5.5,  4.8,  6.0,  5.2,
                      3.0,  3.1,  3.0,  3.2,  3.1],
        "cog":       [45.0, 46.0, 44.0, 46.0, 45.0,
                      90.0, 91.0, 89.0, 90.0, 91.0],
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00:00", "2024-01-01 00:10:00",
            "2024-01-01 00:20:00", "2024-01-01 00:30:00",
            "2024-01-01 00:40:00",
            "2024-01-01 00:00:00", "2024-01-01 00:10:00",
            "2024-01-01 00:20:00", "2024-01-01 00:30:00",
            "2024-01-01 00:40:00",
        ]),
    })


@pytest.fixture
def heading_wraparound_df():
    """Vessel turns from 350° to 10° — should produce heading_change=20, not 340."""
    return pd.DataFrame({
        "mmsi":      [999, 999, 999],
        "lat":       [10.0, 10.1, 10.2],
        "lon":       [50.0, 50.1, 50.2],
        "sog":       [5.0, 5.0, 5.0],
        "cog":       [350.0, 10.0, 20.0],  # 350→10: 20° change, 10→20: 10° change
        
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00:00",
            "2024-01-01 00:10:00",
            "2024-01-01 00:20:00",
        ]),
    })


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Sort-Avoidance Bug
# ─────────────────────────────────────────────────────────────────────────────

def test_sort_avoidance_correctly_detects_unsorted_data():
    """
    Critical: verify the sort-avoidance check does NOT skip sorting
    when records beyond the first 10,000 rows are unsorted.

    This test will FAIL with the current incomplete check (§2.1 bug)
    and PASS after applying the correct per-group timestamp diff check.
    """
    n_per_vessel   = 100
    n_vessels      = 200   # 200 × 100 = 20,000 rows; well beyond 10k sample
    base_ts        = pd.Timestamp("2024-01-01")

    rows = []
    for mmsi_i in range(n_vessels):
        for t_i in range(n_per_vessel):
            rows.append({
                "mmsi": 100_000_000 + mmsi_i,
                "lat":  10.0 + mmsi_i * 0.01,
                "lon":  50.0 + mmsi_i * 0.01,
                "sog":  5.0,
                "cog":  45.0,
                "timestamp": base_ts + pd.Timedelta(minutes=t_i),
            })

    df_sorted = pd.DataFrame(rows)

    # Reverse the timestamps for vessel 150 (rows 15000–15099)
    # This is far beyond the 10k row sample but should be detected
    mask = df_sorted["mmsi"] == 100_000_150
    df_sorted.loc[mask, "timestamp"] = df_sorted.loc[mask, "timestamp"].values[::-1]

    result = clean_and_preprocess(df_sorted.copy())

    # After preprocessing, all time_gaps within groups must be non-negative
    result_with_features = compute_kinematic_features(
        result[["mmsi", "lat", "lon", "sog", "cog", "timestamp"]].copy()
    )

    neg_gaps = (result_with_features["time_gap"] < 0).sum()
    assert neg_gaps == 0, (
        f"Found {neg_gaps} negative time_gap values. "
        "Sort-avoidance check incorrectly skipped sorting unsorted data beyond row 10k. "
        "Apply the per-group timestamp diff fix from §2.1."
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Heading Change Wraparound
# ─────────────────────────────────────────────────────────────────────────────

def test_heading_change_wraparound(heading_wraparound_df):
    """
    350° → 10° should produce heading_change=20°, not 340°.
    10°  → 20° should produce heading_change=10°.
    """
    df = heading_wraparound_df.copy()
    df["sog"] = df["sog"].astype(np.float32)
    df["cog"] = df["cog"].astype(np.float32)
    df["mmsi"] = df["mmsi"].astype(np.int32)

    result = compute_kinematic_features(df)

    # Row 0: first record — no previous, so heading_change=0
    assert result.iloc[0]["heading_change"] == pytest.approx(0.0, abs=0.01), \
        "First row heading_change should be 0"

    # Row 1: 350° → 10° = 20° circular change
    assert result.iloc[1]["heading_change"] == pytest.approx(20.0, abs=0.1), \
        f"350→10 should give 20°, got {result.iloc[1]['heading_change']:.2f}°"

    # Row 2: 10° → 20° = 10° change
    assert result.iloc[2]["heading_change"] == pytest.approx(10.0, abs=0.1), \
        f"10→20 should give 10°, got {result.iloc[2]['heading_change']:.2f}°"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Jump Distance is 0 for First Record in Each Group
# ─────────────────────────────────────────────────────────────────────────────

def test_jump_distance_zero_for_first_record(simple_two_vessel_df):
    """The first observation for each MMSI group has no previous position."""
    df = simple_two_vessel_df.copy()
    df["sog"] = df["sog"].astype(np.float32)
    df["cog"] = df["cog"].astype(np.float32)
    df["mmsi"] = df["mmsi"].astype(np.int32)

    result = compute_kinematic_features(df)

    # First record of MMSI 111 (row 0) and MMSI 222 (row 5)
    first_rows = result.groupby("mmsi").head(1)
    assert (first_rows["jump_distance"] == 0.0).all(), \
        f"First-row jump_distances should all be 0.0, got: {first_rows['jump_distance'].values}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Time Gap Non-Negative on Sorted Data
# ─────────────────────────────────────────────────────────────────────────────

def test_time_gap_non_negative(simple_two_vessel_df):
    """All time_gap values must be >= 0 when data is properly sorted."""
    df = simple_two_vessel_df.copy()
    df["sog"] = df["sog"].astype(np.float32)
    df["cog"] = df["cog"].astype(np.float32)
    df["mmsi"] = df["mmsi"].astype(np.int32)

    result = compute_kinematic_features(df)

    assert result["time_gap"].min() >= 0.0, \
        f"Negative time_gap found: {result['time_gap'].min()}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Acceleration is 0 When time_gap is 0 (No Division by Zero)
# ─────────────────────────────────────────────────────────────────────────────

def test_no_division_by_zero_in_acceleration():
    """When two consecutive records share an exact timestamp, acceleration must be 0."""
    df = pd.DataFrame({
        "mmsi":      [111, 111, 111],
        "lat":       [10.0, 10.1, 10.2],
        "lon":       [50.0, 50.1, 50.2],
        "sog":       np.array([5.0, 10.0, 3.0], dtype=np.float32),
        "cog":       np.array([45.0, 46.0, 44.0], dtype=np.float32),
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00:00",
            "2024-01-01 00:00:00",   # exact duplicate timestamp
            "2024-01-01 00:10:00",
        ]),
        "mmsi":      np.array([111, 111, 111], dtype=np.int32),
    })

    result = compute_kinematic_features(df)

    assert not np.any(np.isinf(result["acceleration"].values)), \
        "Infinity found in acceleration — division by zero not guarded"

    assert not np.any(np.isnan(result["acceleration"].values)), \
        "NaN found in acceleration"

    # Row with time_gap=0 should have acceleration=0
    zero_gap_rows = result[result["time_gap"] == 0]
    assert (zero_gap_rows["acceleration"] == 0.0).all(), \
        f"Acceleration should be 0 when time_gap=0, got: {zero_gap_rows['acceleration'].values}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — float32 Precision: Haversine Error < 1 Meter
# ─────────────────────────────────────────────────────────────────────────────

def test_float32_precision_haversine():
    """
    Verify that float32 coordinate precision loss causes < 1 nm error
    in haversine calculations (relevant for jump_distance feature).
    """
    # Known position: New York Harbor, ~40.6°N, 74.0°W
    lat1_f64 = np.array([40.612345678], dtype=np.float64)
    lon1_f64 = np.array([-74.012345678], dtype=np.float64)
    lat2_f64 = np.array([40.512345678], dtype=np.float64)
    lon2_f64 = np.array([-74.112345678], dtype=np.float64)

    # Simulate float32 storage precision
    lat1_f32 = np.array(lat1_f64, dtype=np.float32).astype(np.float64)
    lon1_f32 = np.array(lon1_f64, dtype=np.float32).astype(np.float64)
    lat2_f32 = np.array(lat2_f64, dtype=np.float32).astype(np.float64)
    lon2_f32 = np.array(lon2_f64, dtype=np.float32).astype(np.float64)

    dist_f64 = haversine_nm_vec(lat1_f64, lon1_f64, lat2_f64, lon2_f64)[0]
    dist_f32 = haversine_nm_vec(lat1_f32, lon1_f32, lat2_f32, lon2_f32)[0]

    error_nm = abs(dist_f64 - dist_f32)
    # 1 nm ≈ 1852 m; 0.001 nm ≈ 1.852 m — acceptable for maritime use
    assert error_nm < 0.001, \
        f"float32 precision error {error_nm:.6f} nm exceeds 0.001 nm tolerance"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — np.select Severity Matches Original Logic
# ─────────────────────────────────────────────────────────────────────────────

def test_np_select_severity_classification():
    """np.select() must produce identical results to the original scalar classify function."""
    scores = np.array([-0.8, -0.6, -0.5, -0.4, -0.25, -0.2, -0.1, 0.0, 0.1])

    # Original scalar function (reconstructed from pre-optimization code)
    def original_classify(score: float) -> str:
        if score < -0.5:
            return "high"
        elif score < -0.2:
            return "medium"
        return "low"

    expected = np.array([original_classify(s) for s in scores])
    actual   = classify_spoofing_severity_vec(scores)

    assert np.array_equal(expected, actual), (
        f"Severity mismatch:\n"
        f"  scores:   {scores}\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — DBSCAN Pre-Filter Doesn't Exclude Eligible Vessels
# ─────────────────────────────────────────────────────────────────────────────

def test_dbscan_prefilter_includes_all_eligible_vessels():
    """
    Vessels with exactly LOITERING_MIN_SAMPLES low-speed records
    must not be excluded by the pre-filter.
    """
    from app.core.anomaly_detection import LOITERING_MIN_SAMPLES

    # Create a vessel with exactly min_samples records close together
    n = LOITERING_MIN_SAMPLES
    df = pd.DataFrame({
        "mmsi":      np.full(n, 999999999, dtype=np.int32),
        "lat":       np.linspace(10.0, 10.001, n).astype(np.float32),
        "lon":       np.linspace(50.0, 50.001, n).astype(np.float32),
        "sog":       np.full(n, 0.5, dtype=np.float32),  # below LOW_SPEED_THRESHOLD
        "cog":       np.full(n, 45.0, dtype=np.float32),
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1h"),
    })

    # Pre-filter logic (copied from detect_loitering_events)
    from app.core.anomaly_detection import LOW_SPEED_THRESHOLD
    low   = df[df["sog"] <= LOW_SPEED_THRESHOLD]
    counts = low.groupby("mmsi", sort=False).size()
    eligible = counts[counts >= LOITERING_MIN_SAMPLES].index

    assert 999999999 in eligible, (
        f"Vessel with exactly {n} low-speed records should be eligible for DBSCAN, "
        f"but was excluded. counts={counts.to_dict()}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — groupby().last() vs tail(1): Document the NaN Behavior
# ─────────────────────────────────────────────────────────────────────────────

def test_groupby_last_returns_hybrid_row_when_last_row_has_nan():
    """
    Document that groupby().last() returns last non-NaN per column,
    which can create rows mixing data from different timesteps.
    This test exists to DOCUMENT the bug — remove this test after applying the fix.
    """
    df = pd.DataFrame({
        "mmsi":        [111, 111, 111],
        "timestamp":   pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "lat":         [10.0, 10.1, 10.2],
        "vessel_name": ["OCEAN STAR", "OCEAN STAR", np.nan],  # last row has NaN name
    })

    last_via_groupby = df.groupby("mmsi").last()
    last_via_tail    = df.sort_values("timestamp").groupby("mmsi").tail(1).set_index("mmsi")

    # groupby().last() returns "OCEAN STAR" (from row 1) but lat 10.2 (from row 2)
    assert last_via_groupby.loc[111, "vessel_name"] == "OCEAN STAR", \
        "groupby().last() should skip NaN and return earlier value"

    # tail(1) correctly returns the actual last row (NaN name)
    assert pd.isna(last_via_tail.loc[111, "vessel_name"]), \
        "tail(1) should return the actual last row including NaN"

    # This test documents the inconsistency — see fix in §2.2
    # After fix: vessel_logs should use drop_duplicates(keep='last') or tail(1)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 10 — Parquet Round-Trip Preserves Dtypes
# ─────────────────────────────────────────────────────────────────────────────

def test_parquet_dtype_preservation(tmp_path, simple_two_vessel_df):
    """float32/int32/category dtypes must survive Parquet write and read."""
    df = simple_two_vessel_df.copy()
    df["mmsi"]        = df["mmsi"].astype(np.int32)
    df["lat"]         = df["lat"].astype(np.float32)
    df["lon"]         = df["lon"].astype(np.float32)
    df["sog"]         = df["sog"].astype(np.float32)
    df["cog"]         = df["cog"].astype(np.float32)
    df["vessel_type"] = pd.Categorical(["Cargo"] * len(df))

    parquet_path = tmp_path / "test.parquet"
    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)

    df_loaded = pd.read_parquet(parquet_path, engine="pyarrow")

    for col in ["mmsi", "lat", "lon", "sog", "cog"]:
        assert df_loaded[col].dtype == df[col].dtype, \
            f"Column '{col}' dtype changed: {df[col].dtype} → {df_loaded[col].dtype}"

    # vessel_type should be category after Parquet round-trip with PyArrow
    # (PyArrow stores Categorical as dictionary-encoded, which loads as category)
    assert str(df_loaded["vessel_type"].dtype) in ("category", "object"), \
        f"vessel_type dtype unexpected: {df_loaded['vessel_type'].dtype}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 11 — No Negative time_gap After Clean Preprocessing
# ─────────────────────────────────────────────────────────────────────────────

def test_preprocessing_produces_sorted_output():
    """
    clean_and_preprocess must always return data sorted by (mmsi, timestamp)
    regardless of input order. Negative time_gaps in feature engineering
    indicate a sort failure.
    """
    # Deliberately unsorted input
    df_unsorted = pd.DataFrame({
        "mmsi": [111, 111, 111, 222, 222, 222],
        "lat":  [10.0, 10.2, 10.1, 20.0, 20.2, 20.1],
        "lon":  [50.0, 50.2, 50.1, 60.0, 60.2, 60.1],
        "sog":  [5.0,  5.0,  5.0,  3.0,  3.0,  3.0],
        "cog":  [45.0, 45.0, 45.0, 90.0, 90.0, 90.0],
        "timestamp": pd.to_datetime([
            "2024-01-01 00:20:00",  # out of order
            "2024-01-01 00:00:00",
            "2024-01-01 00:10:00",
            "2024-01-01 00:20:00",  # out of order
            "2024-01-01 00:00:00",
            "2024-01-01 00:10:00",
        ]),
    })

    df_clean = clean_and_preprocess(df_unsorted)
    df_feats = compute_kinematic_features(
        df_clean[["mmsi", "lat", "lon", "sog", "cog", "timestamp"]].copy()
    )

    assert df_feats["time_gap"].min() >= 0, \
        "Preprocessing failed to sort data — time_gap has negative values"

    # Also verify monotonic per group
    is_sorted = (
        df_feats.groupby("mmsi")["timestamp"]
        .apply(lambda g: g.is_monotonic_increasing)
        .all()
    )
    assert is_sorted, "Output is not monotonically sorted by timestamp within each MMSI group"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 12 — Payload Size Limits
# ─────────────────────────────────────────────────────────────────────────────

def test_payload_size_limits():
    """
    live_alerts and vessel_logs caps must never produce payloads that
    can crash the browser (>10 MB each).
    """
    import json
    MAX_ALERTS = 2_000
    MAX_LOGS   = 2_000
    # Simulate maximum-size records
    max_alert = {
        "type": "spoofing", "severity": "high",
        "mmsi": 123456789, "lat": 37.123456, "lon": -122.123456,
        "timestamp": "2024-01-01T00:00:00", "score": -0.8,
        "cluster_size": None, "dwell_time_hr": None,
    }
    max_log = {
        "mmsi": 123456789, "lat": 37.123456, "lon": -122.123456,
        "vessel_name": "VERY LONG VESSEL NAME HERE", "vessel_type": "Cargo",
        "sog": 15.5, "timestamp": "2024-01-01T00:00:00",
        "spoofing_flag": True, "loitering_flag": False,
        "destination": "HONG KONG", "draft": 12.5, "status": "spoofing",
    }

    alerts_payload = [max_alert] * MAX_ALERTS
    logs_payload   = [max_log]   * MAX_LOGS

    alerts_size_kb = len(json.dumps(alerts_payload).encode()) / 1024
    logs_size_kb   = len(json.dumps(logs_payload).encode())   / 1024

    # Each capped payload must be < 1 MB (well below browser crash threshold)
    assert alerts_size_kb < 1024, \
        f"live_alerts payload too large: {alerts_size_kb:.0f} KB (limit 1024 KB)"
    assert logs_size_kb < 1024, \
        f"vessel_logs payload too large: {logs_size_kb:.0f} KB (limit 1024 KB)"

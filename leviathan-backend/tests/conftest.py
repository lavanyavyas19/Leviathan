# leviathan-backend/tests/conftest.py
"""
pytest configuration and shared fixtures for the Leviathan test suite.

Adds leviathan-backend/ to sys.path so all tests can do:
    from app.core.preprocessing import clean_and_preprocess
without a package install.

Provides a `stub_joblib` auto-fixture that replaces joblib + sklearn
in environments where they are not installed (CI, sandboxes, cloud runners)
so feature-engineering tests can still run without the full ML stack.
"""

import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Ensure leviathan-backend/ is on sys.path for all tests ──────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent   # leviathan-backend/
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ── Joblib / sklearn stub ─────────────────────────────────────────────────────

def _install_stubs():
    """
    Insert minimal stubs for joblib and sklearn.cluster so module-level
    imports in anomaly_detection.py don't raise ImportError when those
    packages are absent from the test environment.
    """
    if "joblib" not in sys.modules:
        fake_jl          = types.ModuleType("joblib")
        fake_jl.load     = lambda *a, **kw: None
        fake_jl.Parallel = lambda **kw: (lambda fn: fn)
        fake_jl.delayed  = lambda fn: fn
        sys.modules["joblib"] = fake_jl

    if "sklearn" not in sys.modules:
        sys.modules["sklearn"] = types.ModuleType("sklearn")

    if "sklearn.cluster" not in sys.modules:
        fake_cluster = types.ModuleType("sklearn.cluster")

        class _FakeDBSCAN:
            def __init__(self, **kw):
                pass
            def fit_predict(self, X):
                # Return all noise (-1) so no spurious loitering clusters appear
                return np.full(len(X), -1)

        fake_cluster.DBSCAN          = _FakeDBSCAN
        sys.modules["sklearn.cluster"] = fake_cluster


# Install stubs at collection time — before any test module is imported
_install_stubs()


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def two_vessel_df():
    """
    Clean, sorted, two-vessel DataFrame with all columns that
    clean_and_preprocess() and compute_kinematic_features() require.
    5 records per vessel, 10-minute intervals.
    """
    base = pd.Timestamp("2024-01-01")
    rows = []
    for v, mmsi in enumerate([111111111, 222222222]):
        for t in range(5):
            rows.append({
                "mmsi":        mmsi,
                "lat":         10.0 + v * 1.0 + t * 0.01,
                "lon":         50.0 + v * 1.0 + t * 0.01,
                "sog":         5.0 + t * 0.1,
                "cog":         45.0 + t * 1.0,
                "heading":     45.0,
                "vessel_type": "Cargo",
                "vessel_name": f"VESSEL_{v}",
                "destination": "ROTTERDAM",
                "draft":       10.0,
                "timestamp":   base + pd.Timedelta(minutes=t * 10),
            })
    return pd.DataFrame(rows)


@pytest.fixture
def unsorted_beyond_10k_df():
    """
    20,000-row DataFrame (200 vessels × 100 rows).
    Vessel #150's timestamps are REVERSED.  The unsorted region starts at
    row 15,000, past any 10k-row sampling window.

    Purpose: prove BUG-001 fix catches unsorted data beyond the old sample limit.
    Expected behaviour after fix: clean_and_preprocess() sorts the data and
    all downstream time_gap values are >= 0.
    """
    base = pd.Timestamp("2024-01-01")
    rows = []
    for v in range(200):
        for t in range(100):
            rows.append({
                "mmsi":        100_000_000 + v,
                "lat":         10.0 + v * 0.01,
                "lon":         50.0,
                "sog":         5.0,
                "cog":         45.0,
                "vessel_type": "Cargo",
                "vessel_name": f"V{v}",
                "timestamp":   base + pd.Timedelta(minutes=t),
            })
    df = pd.DataFrame(rows)
    # Reverse timestamps for vessel 150 only (rows 15,000–15,099)
    mask = df["mmsi"] == 100_000_150
    df.loc[mask, "timestamp"] = df.loc[mask, "timestamp"].values[::-1]
    return df


@pytest.fixture
def heading_wraparound_df():
    """
    Single vessel, COG = [350°, 10°, 20°].
    Circular heading_change:  350→10 = 20°, 10→20 = 10°.
    Tests that diff() + np.minimum handles the 0°/360° boundary correctly.
    """
    return pd.DataFrame({
        "mmsi":      np.array([999, 999, 999], dtype=np.int32),
        "lat":       np.array([10.0, 10.1, 10.2], dtype=np.float32),
        "lon":       np.array([50.0, 50.1, 50.2], dtype=np.float32),
        "sog":       np.array([5.0,  5.0,  5.0],  dtype=np.float32),
        "cog":       np.array([350.0, 10.0, 20.0], dtype=np.float32),
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00:00",
            "2024-01-01 00:10:00",
            "2024-01-01 00:20:00",
        ]),
    })


@pytest.fixture
def duplicate_timestamp_df():
    """
    DataFrame where rows 0 and 1 share an identical timestamp.
    Verifies BUG-005: time_gap=0 → acceleration=0, no division by zero or inf.
    """
    return pd.DataFrame({
        "mmsi": np.array([111, 111, 111, 111], dtype=np.int32),
        "lat":  np.array([10.0, 10.01, 10.02, 10.03], dtype=np.float32),
        "lon":  np.array([50.0, 50.01, 50.02, 50.03], dtype=np.float32),
        "sog":  np.array([0.0, 50.0, 0.0, 5.0], dtype=np.float32),
        "cog":  np.array([45.0, 46.0, 44.0, 45.0], dtype=np.float32),
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00:00",
            "2024-01-01 00:00:00",   # exact duplicate → time_gap = 0
            "2024-01-01 00:10:00",
            "2024-01-01 00:20:00",
        ]),
    })


@pytest.fixture
def vessel_nan_lastrow_df():
    """
    Single vessel where the last row has NaN in vessel_name.
    Tests BUG-002: drop_duplicates(keep='last') must return the true last row
    (with NaN) rather than groupby().last()'s NaN-skipping hybrid row.
    """
    return pd.DataFrame({
        "mmsi":        np.array([111, 111, 111], dtype=np.int32),
        "lat":         np.array([10.0, 10.1, 10.2], dtype=np.float32),
        "lon":         np.array([50.0, 50.1, 50.2], dtype=np.float32),
        "sog":         np.array([5.0,  5.5,  6.0],  dtype=np.float32),
        "vessel_name": ["OCEAN STAR", "OCEAN STAR", np.nan],
        "timestamp":   pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    })

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
import pandas as pd
import joblib
from app.core.job_store import get_job, update_job
from app.core.anomaly_detection import detect_loitering_events
from app.core.audit_log import append_event                        # ← audit logging

router = APIRouter(prefix="/loitering", tags=["Loitering Detection"])

_BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_AUDIT_LOG = os.path.join(_BASE_DIR, "logs", "audit.ndjson")


# =========================
# 1️⃣ REAL-TIME DETECTION
# =========================
class AISPoint(BaseModel):
    mmsi: int
    lat: float
    lon: float
    sog: float
    timestamp: Optional[str] = None  # ISO string


class LoiteringDetectRequest(BaseModel):
    points: List[AISPoint]

@router.post("/detect")
def detect_loitering(job_id: str, payload: LoiteringDetectRequest):
    points = payload.points

    if not points or len(points) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 AIS points")

    # make sure job exists
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Convert to DataFrame for reuse of core logic
    df = pd.DataFrame([p.model_dump() for p in points])

    # Basic sanity
    if df[["lat", "lon"]].isna().any().any():
        raise HTTPException(status_code=400, detail="lat/lon cannot be null")

    # Your core detector expects these columns: mmsi, lat, lon, sog (+ optional timestamp)
    events_df = detect_loitering_events(df)

    # If nothing detected
    if events_df is None or len(events_df) == 0:
        return {
            "loitering_detected": False,
            "count": 0,
            "events": []
        }

    # Convert detections to alert records for job_store
    new_alerts = []
    for _, r in events_df.iterrows():
        new_alerts.append({
            "type": "loitering",
            "mmsi": int(r.get("mmsi")) if pd.notna(r.get("mmsi")) else None,
            "lat": float(r.get("lat")) if pd.notna(r.get("lat")) else None,
            "lon": float(r.get("lon")) if pd.notna(r.get("lon")) else None,
            "timestamp": str(r.get("timestamp") or ""),
            "severity": str(r.get("severity") or "low").lower(),
            "cluster_size": int(r.get("cluster_size")) if pd.notna(r.get("cluster_size")) else None,
            "dwell_time_hr": float(r.get("dwell_time_hr")) if pd.notna(r.get("dwell_time_hr")) else None,
        })

    # Append to existing live_alerts
    existing_alerts = job.get("live_alerts", []) or []
    existing_alerts.extend(new_alerts)

    update_job(job_id, {
        "live_alerts": existing_alerts,
        "status": "detections_updated"
    })

    # ── AUDIT: loitering detection run ─────────────────────────────────────
    append_event(_AUDIT_LOG, "loitering_detection_run", {
        "job_id":            job_id,
        "alerts_generated":  len(new_alerts),
        "model":             "DBSCAN-v4",
    })
    # ── AUDIT: one entry per high-severity alert ────────────────────────────
    for a in new_alerts:
        if str(a.get("severity", "")).lower() == "high":
            append_event(_AUDIT_LOG, "alert_emitted", {
                "job_id":        job_id,
                "type":          "loitering",
                "mmsi":          a.get("mmsi"),
                "lat":           a.get("lat"),
                "lon":           a.get("lon"),
                "severity":      a.get("severity"),
                "dwell_time_hr": a.get("dwell_time_hr"),
            })

    return {
        "loitering_detected": True,
        "count": int(len(events_df)),
        "events": events_df.to_dict(orient="records")
    }

# =========================
# 2️⃣ PRECOMPUTED EVENTS
# =========================
MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "ml", "loitering_events_training.pkl")
)

_LOITERING_COLS = [
    "mmsi", "lat", "lon", "timestamp", "start_ts", "end_ts",
    "cluster_size", "severity", "type", "avg_speed", "dwell_time_hr",
]

# Load pre-computed loitering events at startup.
# Wrapped in try/except so that a missing, corrupted, or version-incompatible
# .pkl file never crashes the whole backend — a warning is printed instead
# and the endpoint gracefully returns an empty dataset.
try:
    if os.path.exists(MODEL_PATH):
        loitering_events = joblib.load(MODEL_PATH)
        # Normalise: joblib.load may return list/dict instead of DataFrame
        if not isinstance(loitering_events, pd.DataFrame):
            loitering_events = pd.DataFrame(loitering_events)
        print(f"✅ Loitering events loaded: {len(loitering_events):,} rows")
    else:
        loitering_events = pd.DataFrame(columns=_LOITERING_COLS)
        print(f"⚠️ Loitering events file missing: {MODEL_PATH}")
except Exception as _load_err:
    loitering_events = pd.DataFrame(columns=_LOITERING_COLS)
    print(f"⚠️ Failed to load loitering events ({type(_load_err).__name__}: {_load_err}). "
          "The /loitering/events endpoint will return an empty dataset.")

@router.get("/events")
def get_loitering_events(
    severity: Optional[str] = Query(None, description="low | medium | high (or comma-separated)"),
    mmsi: Optional[int] = Query(None, description="Filter by vessel MMSI"),
    min_dwell_hr: Optional[float] = Query(None, ge=0, description="Minimum dwell time (hours)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    # ✅ Copy so we don't mutate the global df
    results = loitering_events.copy()

    if results is None or len(results) == 0:
        return {"count": 0, "offset": offset, "limit": limit, "events": []}

    # ✅ Normalize timestamp for sorting (won't crash if already datetime)
    if "timestamp" in results.columns:
        results["timestamp"] = pd.to_datetime(results["timestamp"], errors="coerce")
        results = results.sort_values("timestamp", ascending=False)

    # ✅ Severity filter supports "high,medium"
    if severity:
        allowed = {s.strip().lower() for s in str(severity).split(",") if s.strip()}
        results = results[results["severity"].astype(str).str.lower().isin(allowed)]

    # ✅ MMSI filter
    if mmsi is not None:
        results = results[results["mmsi"] == mmsi]

    # ✅ Minimum dwell filter
    if min_dwell_hr is not None and "dwell_time_hr" in results.columns:
        results = results[pd.to_numeric(results["dwell_time_hr"], errors="coerce") >= float(min_dwell_hr)]

    total_count = int(len(results))

    # ✅ Pagination
    results = results.iloc[offset : offset + limit]

    # ✅ Convert datetime back to ISO string for JSON
    if "timestamp" in results.columns:
        results["timestamp"] = results["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    # convert +0000 → +00:00
        results["timestamp"] = results["timestamp"].astype(str).str.replace(
            r"(\+|\-)(\d{2})(\d{2})$",
            r"\1\2:\3",
            regex=True
    )
    return {
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "events": results.to_dict(orient="records"),
    }
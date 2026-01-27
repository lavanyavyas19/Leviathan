from fastapi import APIRouter, HTTPException, Query
from app.core.job_store import get_job
import numpy as np
import math
from typing import Any

router = APIRouter(prefix="/jobs", tags=["Job Status"])


# ---------------------------------------------------
# JSON SAFETY FIX (NaN/Infinity -> None)
# ---------------------------------------------------
def json_safe(obj: Any):
    """
    Recursively replace NaN / Infinity (Python + NumPy) with None
    so FastAPI can JSON encode safely.
    """
    if obj is None:
        return None

    # ✅ convert numpy scalars to native python (np.float64, np.int64, etc.)
    if isinstance(obj, np.generic):
        obj = obj.item()

    # ✅ now this catches both python float and converted numpy float
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [json_safe(v) for v in obj]

    return obj


# ---------------------------------------------------
# Job status (USED BY POLLING)
# ---------------------------------------------------
@router.get("/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return json_safe(job)


# ---------------------------------------------------
# LIVE ALERTS (LIMITED + SLIM PAYLOAD)
# FRONTEND EXPECTS: ARRAY
#
# Supports:
#   severity=high           (default)
#   severity=medium
#   severity=low
#   severity=high,medium    (multiple)
#   severity=all            (no severity filter)
# ---------------------------------------------------
@router.get("/{job_id}/live-alerts")
def get_live_alerts(
    job_id: str,
    severity: str = Query("high"),
    limit: int = Query(200, ge=1, le=5000),
):
    job = get_job(job_id) or {}
    alerts = job.get("live_alerts", [])

    sev = (severity or "high").lower().strip()

    # Filter by severity unless "all"/"any" requested
    if sev not in ("all", "any", "*"):
        allowed = {s.strip() for s in sev.split(",") if s.strip()}
        alerts = [a for a in alerts if (a.get("severity") or "").lower() in allowed]

    alerts = alerts[:limit]

    # Slim response (ONLY what UI uses)
    payload = [
        {
            "type": a.get("type"),
            "severity": a.get("severity"),
            "mmsi": a.get("mmsi"),
            "lat": a.get("lat"),
            "lon": a.get("lon"),
            "timestamp": a.get("timestamp"),
            "score": a.get("score"),
            "cluster_size": a.get("cluster_size"),
            "dwell_time_hr": a.get("dwell_time_hr"),
        }
        for a in alerts
    ]

    return json_safe(payload)


# ---------------------------------------------------
# ANOMALY REPORTS (COUNTS OBJECT)
# FRONTEND EXPECTS: OBJECT
# ---------------------------------------------------
@router.get("/{job_id}/anomaly-reports")
def get_anomaly_reports(job_id: str):
    job = get_job(job_id) or {}
    payload = job.get(
        "anomaly_reports",
        {
            "total": 0,
            "spoofing": 0,
            "loitering": 0,
            "speed": 0,
            "deviation": 0,
        },
    )
    return json_safe(payload)


# ---------------------------------------------------
# VESSEL LOGS (LIMITED + NORMALIZED KEYS)
# FRONTEND EXPECTS: ARRAY
# ---------------------------------------------------
@router.get("/{job_id}/vessel-logs")
def get_vessel_logs(
    job_id: str,
    limit: int = Query(500, ge=1, le=10000),
):
    job = get_job(job_id) or {}
    logs = job.get("vessel_logs", [])
    logs = logs[:limit]

    slim_logs = []

    for r in logs:
        vessel_name = r.get("vessel_name") or r.get("vessel")
        vessel_type = r.get("vessel_type") or r.get("type")
        sog = r.get("sog") if r.get("sog") is not None else r.get("speed")
        timestamp = r.get("timestamp") or r.get("updated")

        slim_logs.append(
            {
                # core identifiers
                "mmsi": r.get("mmsi"),

                # position
                "lat": r.get("lat"),
                "lon": r.get("lon"),

                # frontend-expected keys
                "vessel_name": vessel_name,
                "vessel_type": vessel_type,
                "sog": sog,
                "timestamp": timestamp,

                # anomaly flags (safe defaults)
                "spoofing_flag": bool(r.get("spoofing_flag", False)),
                "loitering_flag": bool(r.get("loitering_flag", False)),

                # optional extras
                "destination": r.get("destination"),
                "draft": r.get("draft"),
            }
        )

    return json_safe(slim_logs)

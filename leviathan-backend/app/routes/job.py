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
# ---------------------------------------------------
@router.get("/{job_id}/live-alerts")
def get_live_alerts(
    job_id: str,
    severity: str = Query("high"),
    limit: int = Query(200, ge=1, le=5000),
):
    job = get_job(job_id) or {}
    alerts = job.get("live_alerts", []) or []

    # STEP 1: Normalize type + spoofing severity
    for a in alerts:
        t_raw = str(a.get("type") or "").lower()
        sev = str(a.get("severity") or "low").lower()

        if any(k in t_raw for k in ("spoof", "gps", "gnss", "jump", "inconsisten")):
            a["type"] = "spoofing"

            score = a.get("score")
            if isinstance(score, (int, float)):
                s = abs(score)
                if s >= 0.25:
                    sev = "high"
                elif s >= 0.12:
                    sev = "medium"
                else:
                    sev = "low"

        elif "loiter" in t_raw:
            a["type"] = "loitering"

        a["severity"] = sev

    # STEP 2: Severity filter
    sev_q = (severity or "high").lower().strip()
    if sev_q not in ("all", "any", "*"):
        allowed = {s.strip() for s in sev_q.split(",") if s.strip()}
        alerts = [a for a in alerts if a.get("severity") in allowed]

    # STEP 3: Sort newest first + limit
    def _ts(a):
        return str(a.get("timestamp") or "")

    alerts = sorted(alerts, key=_ts, reverse=True)[:limit]

    # STEP 4: Slim payload
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
# ---------------------------------------------------
@router.get("/{job_id}/anomaly-reports")
def get_anomaly_reports(job_id: str):
    job = get_job(job_id) or {}
    alerts = job.get("live_alerts", []) or []

    spoofing_vessels = set()
    loitering_vessels = set()

    for a in alerts:
        mmsi = a.get("mmsi") or a.get("vesselId")
        if not mmsi:
            continue

        t = str(a.get("type") or "").lower()
        if "loiter" in t:
            loitering_vessels.add(mmsi)
        elif "spoof" in t:
            spoofing_vessels.add(mmsi)

    payload = {
        "total": len(spoofing_vessels.union(loitering_vessels)),
        "spoofing": len(spoofing_vessels),
        "loitering": len(loitering_vessels),
        "speed": 0,
        "deviation": 0,
    }

    return json_safe(payload)


# ---------------------------------------------------
# VESSEL LOGS (LIMITED + NORMALIZED KEYS)
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
        vessel_name = (
            r.get("vessel_name")
            or r.get("shipname")
            or r.get("ship_name")
            or r.get("name")
            or r.get("vessel")
            or r.get("callsign")
        )

        vessel_type = r.get("vessel_type") or r.get("type")
        sog = r.get("sog") if r.get("sog") is not None else r.get("speed")
        timestamp = r.get("timestamp") or r.get("updated")

        slim_logs.append(
            {
                "mmsi": r.get("mmsi"),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "vessel_name": vessel_name,
                "vessel_type": vessel_type,
                "sog": sog,
                "timestamp": timestamp,
                "spoofing_flag": bool(r.get("spoofing_flag", False)),
                "loitering_flag": bool(r.get("loitering_flag", False)),
                "destination": r.get("destination"),
                "draft": r.get("draft"),
            }
        )

    return json_safe(slim_logs)

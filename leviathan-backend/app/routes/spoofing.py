from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import pandas as pd
from typing import Optional, List
import os

from app.core.job_store import update_job, get_job
from app.core.anomaly_detection import detect_spoofing_events
from app.core.audit_log import append_event                        # ← audit logging

router = APIRouter(prefix="/spoofing", tags=["Spoofing Detection"])

_BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_AUDIT_LOG = os.path.join(_BASE_DIR, "logs", "audit.ndjson")


# -----------------------------
# Input schema (AIS points)
# -----------------------------
class AISPoint(BaseModel):
    mmsi: int
    lat: float
    lon: float
    sog: float
    cog: float
    timestamp: Optional[str] = None


class SpoofingDetectRequest(BaseModel):
    points: List[AISPoint]


# -----------------------------
# Detect spoofing from AIS points
# -----------------------------
@router.post("/detect")
def detect_spoofing(job_id: str, payload: SpoofingDetectRequest):
    points = payload.points

    if not points or len(points) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 AIS points")

    # make sure job exists
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Convert request -> DataFrame
    df = pd.DataFrame([p.model_dump() for p in points])

    # Basic sanity
    required_cols = ["mmsi", "lat", "lon", "sog", "cog"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")

    if df[["lat", "lon", "sog", "cog"]].isna().any().any():
        raise HTTPException(status_code=400, detail="lat/lon/sog/cog cannot be null")

    # Use your core pipeline (computes features + runs model)
    events_df = detect_spoofing_events(df)

    # If nothing detected
    if events_df is None or len(events_df) == 0:
        return {
            "spoofing_detected": False,
            "count": 0,
            "events": []
        }

    # Convert detections to alert records for job_store
    new_alerts = []
    for _, r in events_df.iterrows():
        new_alerts.append({
            "type": "spoofing",
            "mmsi": int(r.get("mmsi")) if pd.notna(r.get("mmsi")) else None,
            "lat": float(r.get("lat")) if pd.notna(r.get("lat")) else None,
            "lon": float(r.get("lon")) if pd.notna(r.get("lon")) else None,
            "timestamp": str(r.get("timestamp") or ""),
            "severity": str(r.get("severity") or "low").lower(),
            "score": float(r.get("score")) if pd.notna(r.get("score")) else None,
        })

    # Append to existing live_alerts
    existing_alerts = job.get("live_alerts", []) or []
    existing_alerts.extend(new_alerts)

    update_job(job_id, {
        "live_alerts": existing_alerts,
        "status": "detections_updated"
    })

    # ── AUDIT: spoofing detection run ──────────────────────────────────────
    append_event(_AUDIT_LOG, "spoofing_detection_run", {
        "job_id":           job_id,
        "alerts_generated": len(new_alerts),
        "model":            "IsolationForest-n300",
        "contamination":    0.01,
    })
    # ── AUDIT: one entry per high-severity alert ────────────────────────────
    for a in new_alerts:
        if str(a.get("severity", "")).lower() == "high":
            append_event(_AUDIT_LOG, "alert_emitted", {
                "job_id":   job_id,
                "type":     "spoofing",
                "mmsi":     a.get("mmsi"),
                "lat":      a.get("lat"),
                "lon":      a.get("lon"),
                "severity": a.get("severity"),
                "score":    a.get("score"),
            })

    return {
        "spoofing_detected": True,
        "count": int(len(events_df)),
        "events": events_df.to_dict(orient="records")
    }


# -----------------------------
# Return spoofing alerts from job_store
# -----------------------------
@router.get("/events")
def get_spoofing_events(
    job_id: str,
    severity: Optional[str] = Query(None, description="low | medium | high (or comma-separated)"),
    mmsi: Optional[int] = Query(None, description="Filter by vessel MMSI"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    alerts = job.get("live_alerts", []) or []

    # keep only spoofing alerts
    results = [a for a in alerts if str(a.get("type", "")).lower() == "spoofing"]

    if severity:
        allowed = {s.strip().lower() for s in str(severity).split(",") if s.strip()}
        results = [a for a in results if str(a.get("severity", "")).lower() in allowed]

    if mmsi is not None:
        results = [a for a in results if a.get("mmsi") == mmsi]

    total_count = len(results)
    results = results[offset: offset + limit]

    return {
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "events": results
    }
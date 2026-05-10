# app/routes/job.py
#
# CRASH FIX — CRITICAL:
#   GET /jobs/{job_id} (status endpoint used by the polling loop) previously
#   returned the ENTIRE job dict, including live_alerts (thousands of records)
#   and vessel_logs (one record per unique MMSI vessel = up to 20 000+).
#   At 50–100 bytes per field × 16 fields × 20 000 vessels this reaches 50+ MB,
#   which Chrome parses in the main thread → "Aw, Snap!" OOM crash.
#
# FIX:
#   1. GET  /jobs/{id}                → METADATA ONLY (status, progress, summary)
#                                        Heavy arrays are STRIPPED from this response.
#   2. GET  /jobs/{id}/live-alerts    → Paginated alerts, hard cap 200
#   3. GET  /jobs/{id}/anomaly-reports→ Counts object (unchanged)
#   4. GET  /jobs/{id}/vessel-logs    → Paginated slim logs, hard cap 500
#   5. GET  /jobs/{id}/map-points     → NEW — sampled geo points, hard cap 500
#   6. GET  /jobs/{id}/chart-data     → NEW — pre-aggregated hourly time series

from collections import defaultdict
from datetime import datetime
from typing import Any

import math
import numpy as np

from fastapi import APIRouter, HTTPException, Query
from app.core.job_store import get_job

router = APIRouter(prefix="/jobs", tags=["Job Status"])

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def json_safe(obj: Any):
    """Recursively replace NaN / Infinity with None for safe JSON serialisation."""
    if obj is None:
        return None
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    return obj


# Keys that carry raw record arrays — must NEVER appear in the status response.
_HEAVY_KEYS = frozenset({"live_alerts", "vessel_logs"})


# ─────────────────────────────────────────────────────────────────────────────
# 1. JOB STATUS — METADATA ONLY (used by the polling loop)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}")
def get_job_status(job_id: str):
    """
    Returns lightweight job metadata only.
    Heavy arrays (live_alerts, vessel_logs) are stripped so this response
    never exceeds a few kilobytes regardless of dataset size.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # ── Strip every heavy array key ──────────────────────────────────────────
    status_payload = {k: v for k, v in job.items() if k not in _HEAVY_KEYS}

    return json_safe(status_payload)


# ─────────────────────────────────────────────────────────────────────────────
# 2. LIVE ALERTS — paginated, severity-filtered, hard cap 200
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}/live-alerts")
def get_live_alerts(
    job_id: str,
    severity: str = Query("high,medium"),
    limit:    int  = Query(100, ge=1, le=200),   # hard cap 200
    offset:   int  = Query(0,   ge=0),
):
    job    = get_job(job_id) or {}
    alerts = list(job.get("live_alerts", []) or [])

    # ── Normalise type only — keep stored severity ───────────────────────────
    #
    # IMPORTANT: do NOT override severity here from the score field.
    #
    # The old code re-classified spoofing severity using:
    #     sev = "high" if abs(score) >= 0.25 else "medium" if abs(score) >= 0.12 else "low"
    # This was calibrated for IsolationForest decision_function() scores
    # (negative range, roughly −0.5 to +0.5).
    #
    # The model is now a supervised HistGradientBoostingClassifier whose
    # score field holds a probability in [0, 1].  Any detected event has
    # probability >= 0.5 (our minimum threshold), so abs(score) >= 0.25 is
    # ALWAYS True — every event is forced to HIGH, hiding legitimate MEDIUM
    # events and making severity meaningless.
    #
    # The correct severity was already computed and stored by the detection
    # pipeline (classify_spoofing_severity_proba_vec / classify_loitering_severity_vec).
    # Trust it.
    for a in alerts:
        t_raw = str(a.get("type") or "").lower()
        sev   = str(a.get("severity") or "low").lower()

        if any(k in t_raw for k in ("spoof", "gps", "gnss", "jump", "inconsisten")):
            a["type"] = "spoofing"
        elif "loiter" in t_raw:
            a["type"] = "loitering"
        a["severity"] = sev   # stored value from anomaly_detection.py — do not override

    # ── Severity filter ──────────────────────────────────────────────────────
    sev_q = (severity or "high,medium").lower().strip()
    if sev_q not in ("all", "any", "*"):
        allowed = {s.strip() for s in sev_q.split(",") if s.strip()}
        alerts  = [a for a in alerts if a.get("severity") in allowed]

    # ── Sort newest-first, page, cap ─────────────────────────────────────────
    alerts = sorted(alerts, key=lambda a: str(a.get("timestamp") or ""), reverse=True)
    total  = len(alerts)
    alerts = alerts[offset : offset + limit]

    # ── Slim payload — only fields the frontend actually uses ────────────────
    payload = [
        {
            "type":         a.get("type"),
            "severity":     a.get("severity"),
            "mmsi":         a.get("mmsi"),
            "lat":          a.get("lat"),
            "lon":          a.get("lon"),
            "timestamp":    a.get("timestamp"),
            "score":        a.get("score"),
            "cluster_size": a.get("cluster_size"),
            "dwell_time_hr":a.get("dwell_time_hr"),
        }
        for a in alerts
    ]

    return json_safe(payload)


# ─────────────────────────────────────────────────────────────────────────────
# 3. ANOMALY REPORTS — counts object, no raw records
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}/anomaly-reports")
def get_anomaly_reports(job_id: str):
    job    = get_job(job_id) or {}
    alerts = job.get("live_alerts", []) or []
    # Use stored summary if available (avoids iterating large array)
    summary = job.get("summary") or {}
    if summary.get("anomaly_breakdown"):
        return json_safe(summary["anomaly_breakdown"])

    spoofing_vessels  = set()
    loitering_vessels = set()
    for a in alerts:
        mmsi = a.get("mmsi") or a.get("vesselId")
        if not mmsi:
            continue
        t = str(a.get("type") or "").lower()
        if "loiter" in t:
            loitering_vessels.add(mmsi)
        elif any(k in t for k in ("spoof", "gps")):
            spoofing_vessels.add(mmsi)

    return json_safe({
        "total":    len(spoofing_vessels | loitering_vessels),
        "spoofing": len(spoofing_vessels),
        "loitering":len(loitering_vessels),
        "speed":    0,
        "deviation":0,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. VESSEL LOGS — paginated, hard cap 500, slim fields only
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}/vessel-logs")
def get_vessel_logs(
    job_id: str,
    limit:  int = Query(200, ge=1, le=500),   # hard cap 500
    offset: int = Query(0,   ge=0),
    status: str = Query(None),  # "normal" | "spoofing" | "loitering" | None (all)
):
    job  = get_job(job_id) or {}
    logs = list(job.get("vessel_logs", []) or [])

    # ── Optional status filter ────────────────────────────────────────────────
    # Allows the frontend to request a specific subset (e.g. status=normal) so
    # it can retrieve normal vessels even when anomalous vessels dominate the
    # first page.  The stored list is interleaved but a status param is cleaner
    # for explicit UI-driven filtering.
    if status:
        s = status.strip().lower()
        logs = [l for l in logs if str(l.get("status", "normal")).lower() == s]

    total = len(logs)
    page  = logs[offset : offset + limit]

    slim = []
    for r in page:
        vessel_name = (
            r.get("vessel_name") or r.get("shipname") or r.get("ship_name")
            or r.get("name") or r.get("vessel") or r.get("callsign")
        )
        slim.append({
            "mmsi":           r.get("mmsi"),
            "lat":            r.get("lat"),
            "lon":            r.get("lon"),
            "vessel_name":    vessel_name,
            "vessel_type":    r.get("vessel_type") or r.get("type"),
            "sog":            r.get("sog") if r.get("sog") is not None else r.get("speed"),
            "timestamp":      r.get("timestamp") or r.get("updated"),
            "spoofing_flag":  bool(r.get("spoofing_flag", False)),
            "loitering_flag": bool(r.get("loitering_flag", False)),
            "destination":    r.get("destination"),
            "draft":          r.get("draft"),
            "status":         r.get("status", "normal"),
        })

    return json_safe(slim)


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAP POINTS — NEW: sampled geo positions for map rendering, hard cap 500
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}/map-points")
def get_map_points(
    job_id: str,
    limit:  int = Query(500, ge=1, le=500),   # hard cap 500
):
    """
    Returns a representative sample of vessel positions for map rendering.
    Anomalous vessels (spoofing/loitering) are always included; normal vessels
    are sampled evenly from the remainder to fill up to `limit` points.
    """
    job  = get_job(job_id) or {}
    logs = list(job.get("vessel_logs", []) or [])

    if not logs:
        return []

    # ── Always include anomalous vessels ─────────────────────────────────────
    anomalous = [r for r in logs if r.get("spoofing_flag") or r.get("loitering_flag")]
    normal    = [r for r in logs if not r.get("spoofing_flag") and not r.get("loitering_flag")]

    # Sample normal vessels to fill remaining budget
    remaining = max(0, limit - len(anomalous))
    if remaining > 0 and normal:
        step    = max(1, len(normal) // remaining)
        sampled = normal[::step][:remaining]
    else:
        sampled = []

    selected = anomalous + sampled

    # ── Minimal payload for map rendering ────────────────────────────────────
    points = [
        {
            "mmsi":           r.get("mmsi"),
            "lat":            r.get("lat"),
            "lon":            r.get("lon"),
            "spoofing_flag":  bool(r.get("spoofing_flag", False)),
            "loitering_flag": bool(r.get("loitering_flag", False)),
            "vessel_name":    r.get("vessel_name") or r.get("vessel") or f"MMSI-{r.get('mmsi')}",
            "status":         r.get("status", "normal"),
        }
        for r in selected
        if r.get("lat") is not None and r.get("lon") is not None
    ]

    return json_safe(points[:limit])


# ─────────────────────────────────────────────────────────────────────────────
# 6. CHART DATA — NEW: pre-aggregated hourly time series for BottomChart
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{job_id}/chart-data")
def get_chart_data(job_id: str):
    """
    Returns hourly-bucketed anomaly counts for the BottomChart component.
    The frontend receives O(24-48) data points instead of thousands of raw records.

    DATA SOURCE PRIORITY
    ────────────────────
    1. summary["chart_data"]  — pre-computed in _build_payloads() from the FULL
                                 spoofing_events / loitering_events DataFrames,
                                 BEFORE live_alerts is capped to 1 000 per type.
                                 This is the true distribution.

    2. live_alerts (fallback)  — capped subset; used only for jobs that were
                                 processed before this fix so the endpoint
                                 never returns an empty response.
    """
    job     = get_job(job_id) or {}
    summary = job.get("summary") or {}

    # ── 1. Preferred: pre-computed from FULL event arrays ────────────────────
    precomputed = summary.get("chart_data")
    if precomputed and isinstance(precomputed, list) and len(precomputed) > 0:
        return json_safe(precomputed)

    # ── 2. Fallback: aggregate from (capped) live_alerts ─────────────────────
    #    Covers jobs ingested before this fix.  Counts will be capped at
    #    1 000 per type but at least the endpoint returns usable data.
    alerts = list(job.get("live_alerts", []) or [])

    buckets: dict = defaultdict(lambda: {"spoofing": 0, "loitering": 0, "other": 0})

    for a in alerts:
        ts_str = a.get("timestamp")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            bucket_key = ts.strftime("%Y-%m-%dT%H:00:00")
        except Exception:
            continue

        a_type = str(a.get("type") or "").lower()
        if "spoof" in a_type:
            buckets[bucket_key]["spoofing"]  += 1
        elif "loiter" in a_type:
            buckets[bucket_key]["loitering"] += 1
        else:
            buckets[bucket_key]["other"]     += 1

    sorted_keys = sorted(buckets.keys())[-48:]

    series = [
        {
            "time":      k,
            "spoofing":  buckets[k]["spoofing"],
            "loitering": buckets[k]["loitering"],
            "other":     buckets[k]["other"],
            "total":     buckets[k]["spoofing"] + buckets[k]["loitering"] + buckets[k]["other"],
        }
        for k in sorted_keys
    ]

    return json_safe(series)

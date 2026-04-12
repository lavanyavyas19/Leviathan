from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import os

from app.core.job_store import get_job, ensure_job
from app.core.audit_log import append_event                        # ← audit logging

_BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_AUDIT_LOG = os.path.join(_BASE_DIR, "logs", "audit.ndjson")

router = APIRouter(prefix="/api/jobs", tags=["Metrics"])

# -------------------------
# Label schema (what user uploads)
# -------------------------
class LabelItem(BaseModel):
    mmsi: int
    type: str = Field(..., description="spoofing | loitering")
    timestamp: Optional[str] = Field(None, description="ISO time string (optional for event-level)")
    label: int = Field(..., description="1=anomaly present, 0=normal")

class LabelsUpload(BaseModel):
    labels: List[LabelItem]

# -------------------------
# helpers
# -------------------------
def norm_type(t: str) -> str:
    s = str(t or "").lower()
    if "spoof" in s:
        return "spoofing"
    if "loiter" in s:
        return "loitering"
    return s

def compute_event_metrics(pred_events: List[Dict[str, Any]], labels: List[Dict[str, Any]], target_type: str):
    """
    EVENT-LEVEL matching by (type + mmsi)
    - prediction event exists => predicted positive
    - ground truth label=1 => actual positive
    """
    # normalize preds
    pred_set = set()
    for a in pred_events or []:
        t = norm_type(a.get("type"))
        if t != target_type:
            continue
        mmsi = a.get("mmsi") or a.get("vesselId")
        if mmsi is None:
            continue
        pred_set.add((t, int(mmsi)))

    # normalize labels (only label==1 count as positives)
    true_pos_set = set()
    true_neg_set = set()
    for l in labels or []:
        t = norm_type(l.get("type"))
        if t != target_type:
            continue
        mmsi = l.get("mmsi")
        if mmsi is None:
            continue
        if int(l.get("label", 0)) == 1:
            true_pos_set.add((t, int(mmsi)))
        else:
            true_neg_set.add((t, int(mmsi)))

    # Confusion (event-level)
    TP = len(pred_set & true_pos_set)
    FP = len(pred_set - true_pos_set)  # predicted but not truly positive
    FN = len(true_pos_set - pred_set)  # truly positive but missed

    precision = TP / (TP + FP) if (TP + FP) else 0.0
    recall = TP / (TP + FN) if (TP + FN) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "TP": TP, "FP": FP, "FN": FN,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "predicted_positives": len(pred_set),
        "actual_positives": len(true_pos_set),
    }

# -------------------------
# Upload labels
# -------------------------
@router.post("/{job_id}/labels")
def upload_labels(job_id: str, payload: LabelsUpload):
    job = ensure_job(job_id)

    # store as plain dicts (json safe)
    job["labels"] = [l.model_dump() for l in payload.labels]
    job["labels_uploaded_at"] = datetime.utcnow().isoformat() + "Z"

    # ── AUDIT: ground truth labels uploaded ────────────────────────────────
    append_event(_AUDIT_LOG, "labels_uploaded", {
        "job_id":       job_id,
        "labels_count": len(job["labels"]),
    })

    return {"ok": True, "job_id": job_id, "labels_count": len(job["labels"])}

# -------------------------
# Compute metrics (F1/Precision/Recall)
# -------------------------
@router.get("/{job_id}/metrics")
def get_metrics(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    labels = job.get("labels", [])
    if not labels:
        return {"ok": False, "detail": "No labels uploaded yet", "job_id": job_id}

    alerts = job.get("live_alerts", []) or []

    # ---------------------------------------------------
    # FALLBACK: if no live_alerts, load predictions from event files
    # ---------------------------------------------------
    if not alerts:

        # ✅ Loitering (precomputed) events
        loiter_path = os.path.join("app", "ml", "loitering_events_training.pkl")
        if os.path.exists(loiter_path):
            lo_df = pd.read_pickle(loiter_path)

            for _, r in lo_df.iterrows():
                alerts.append({
                    "type": "loitering",
                    "mmsi": int(r.get("mmsi")) if pd.notna(r.get("mmsi")) else None,
                    "severity": str(r.get("severity") or "low").lower(),
                    "timestamp": str(r.get("timestamp") or ""),
                    "lat": float(r.get("lat")) if pd.notna(r.get("lat")) else None,
                    "lon": float(r.get("lon")) if pd.notna(r.get("lon")) else None,
                    "cluster_size": int(r.get("cluster_size")) if pd.notna(r.get("cluster_size")) else None,
                    "dwell_time_hr": float(r.get("dwell_time_hr")) if pd.notna(r.get("dwell_time_hr")) else None,
                })

        # ✅ Spoofing events
        spoof_path = os.path.join("app", "ml", "spoofing_events.pkl")
        if os.path.exists(spoof_path):
            sp_df = pd.read_pickle(spoof_path)

            has_mmsi = "mmsi" in sp_df.columns

            for _, r in sp_df.iterrows():
                alerts.append({
                    "type": "spoofing",
                    "mmsi": int(r.get("mmsi")) if has_mmsi and pd.notna(r.get("mmsi")) else None,
                    "severity": str(r.get("severity") or "low").lower(),
                    "timestamp": str(r.get("timestamp") or ""),
                    "lat": float(r.get("lat")) if "lat" in sp_df.columns and pd.notna(r.get("lat")) else None,
                    "lon": float(r.get("lon")) if "lon" in sp_df.columns and pd.notna(r.get("lon")) else None,
                    "score": float(r.get("anomaly_score")) if pd.notna(r.get("anomaly_score")) else None,
                })

    # -------------------------
    # Compute metrics
    # -------------------------
    spoof = compute_event_metrics(alerts, labels, "spoofing")
    loit = compute_event_metrics(alerts, labels, "loitering")

    macro_f1 = round((spoof["f1"] + loit["f1"]) / 2.0, 4)

    metrics = {
        "job_id": job_id,
        "macro_f1": macro_f1,
        "spoofing": spoof,
        "loitering": loit,
        "labels_count": len(labels),
        "alerts_count": len(alerts),
    }

    job["metrics"] = metrics

    # ── AUDIT: evaluation metrics computed ────────────────────────────────
    append_event(_AUDIT_LOG, "metrics_computed", {
        "job_id":    job_id,
        "macro_f1":  metrics["macro_f1"],
        "loitering": {
            "precision": metrics["loitering"]["precision"],
            "recall":    metrics["loitering"]["recall"],
            "f1":        metrics["loitering"]["f1"],
        },
        "spoofing": {
            "precision": metrics["spoofing"]["precision"],
            "recall":    metrics["spoofing"]["recall"],
            "f1":        metrics["spoofing"]["f1"],
        },
    })

    return metrics
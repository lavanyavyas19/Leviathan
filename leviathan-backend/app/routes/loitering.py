from fastapi import APIRouter, Query
from pydantic import BaseModel
from sklearn.cluster import DBSCAN
import numpy as np
import joblib
import os
from typing import Optional

router = APIRouter(prefix="/loitering", tags=["Loitering Detection"])


# =========================
# 1️⃣ REAL-TIME DETECTION
# =========================

class LoiteringInput(BaseModel):
    coordinates: list[list[float]]  # [[lat, lon], [lat, lon], ...]

def classify_severity(cluster_size: int) -> str:
    if cluster_size > 15:
        return "high"
    elif cluster_size >= 5:
        return "medium"
    else:
        return "low"

@router.post("/detect")
def detect_loitering(data: LoiteringInput):
    X = np.array(data.coordinates)

    model = DBSCAN(eps=0.01, min_samples=5)
    labels = model.fit_predict(X)

    clusters = [c for c in set(labels) if c != -1]

    if not clusters:
        return {
            "loitering_detected": False,
            "severity": "none",
            "cluster_size": 0
        }

    largest_cluster = max(np.sum(labels == c) for c in clusters)
    severity = classify_severity(largest_cluster)

    return {
        "loitering_detected": True,
        "severity": severity,
        "cluster_size": int(largest_cluster)
    }


# =========================
# 2️⃣ PRECOMPUTED EVENTS
# =========================

MODEL_PATH = os.path.join("app", "ml", "loitering_model.pkl")

# Load once at startup
loitering_events = joblib.load(MODEL_PATH)

@router.get("/events")
def get_loitering_events(
    severity: Optional[str] = Query(None, description="low | medium | high"),
    mmsi: Optional[int] = None,
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip")
):
    """
    Fetch detected loitering events (precomputed during training).

    - severity: optional filter (low | medium | high)
    - mmsi: optional filter for a specific vessel
    - limit: number of events to return (default 100)
    - offset: skip first N events (pagination)
    """
    if not os.path.exists(MODEL_PATH):
        return {"count": 0, "events": [], "message": "Events file not found."}

    # Lazy load the events file
    loitering_events = joblib.load(MODEL_PATH)

    # Apply filters
    results = loitering_events
    if severity:
        results = results[results["severity"].str.lower() == severity.lower()]
    if mmsi:
        results = results[results["mmsi"] == mmsi]

    total_count = len(results)

    # Pagination
    results = results.iloc[offset : offset + limit]

    return {
        "count": total_count,
        "offset": offset,
        "limit": limit,
        "events": results.to_dict(orient="records")
    }
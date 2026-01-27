from fastapi import APIRouter, Query
from pydantic import BaseModel
import numpy as np
import pandas as pd
import joblib
import os
from typing import Optional

router = APIRouter(prefix="/spoofing", tags=["Spoofing Detection"])

# -----------------------------
# Load trained spoofing model
# -----------------------------
MODEL_PATH = os.path.join("app", "ml", "spoofing_model.pkl")
model = joblib.load(MODEL_PATH)

# -----------------------------
# Persistent event storage
# -----------------------------
EVENTS_PATH = os.path.join("app", "ml", "spoofing_events.pkl")

if os.path.exists(EVENTS_PATH):
    spoofing_events = pd.read_pickle(EVENTS_PATH)
else:
    spoofing_events = pd.DataFrame(columns=[
        "speed",
        "heading_change",
        "jump_distance",
        "time_gap",
        "anomaly_score",
        "severity"
    ])

# -----------------------------
# Input schema (Swagger)
# -----------------------------
class SpoofingInput(BaseModel):
    speed: float
    heading_change: float
    jump_distance: float
    time_gap: float
    speed_change: float
    acceleration: float
    turn_rate: float


# -----------------------------
# Severity classification
# -----------------------------
def classify_severity(score: float) -> str:
    """
    IsolationForest:
    more negative = more anomalous
    """
    if score < -0.5:
        return "high"
    elif score < -0.2:
        return "medium"
    else:
        return "low"

# -----------------------------
# Detect spoofing (real-time)
# -----------------------------
@router.post("/detect")
def detect_spoofing(data: SpoofingInput):
    global spoofing_events

    # Convert to 1x7 feature array
    X = np.array([[
        data.speed,
        data.heading_change,
        data.jump_distance,
        data.time_gap,
        data.speed_change,
        data.acceleration,
        data.turn_rate
    ]])

    # 7-feature validation
    if X.shape[1] != 7:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"7 features required, got {X.shape[1]}"
        )

    # Predict using the IsolationForest pipeline
    prediction = model.predict(X)[0]
    anomaly_score = model.decision_function(X)[0]

    spoofing_detected = prediction == -1
    severity = classify_severity(anomaly_score) if spoofing_detected else "none"

    # Log event if spoofing detected
    if spoofing_detected:
        spoofing_events.loc[len(spoofing_events)] = [
            data.speed,
            data.heading_change,
            data.jump_distance,
            data.time_gap,
            round(anomaly_score, 4),
            severity
        ]
        spoofing_events.to_pickle(EVENTS_PATH)

    return {
        "spoofing_detected": bool(spoofing_detected),
        "anomaly_score": round(anomaly_score, 4),
        "severity": severity
    }

# -----------------------------
# Fetch spoofing events
# -----------------------------
@router.get("/events")
def get_spoofing_events(
    severity: Optional[str] = Query(None, description="low | medium | high")
):
    results = spoofing_events.copy()

    if severity:
        results = results[results["severity"] == severity.lower()]

    return {
        "count": len(results),
        "events": results.to_dict(orient="records")
    }

from fastapi import APIRouter
from pydantic import BaseModel
import numpy as np
import joblib

router = APIRouter(prefix="/spoofing", tags=["Spoofing Detection"])

model = joblib.load("app/ml/spoofing_model.pkl")

class SpoofingInput(BaseModel):
    speed: float
    heading_change: float
    jump_distance: float
    time_gap: float

@router.post("/detect")
def detect_spoofing(data: SpoofingInput):
    X = np.array([[data.speed, data.heading_change, data.jump_distance, data.time_gap]])
    prediction = model.predict(X)[0]
    anomaly_score = model.decision_function(X)[0]
    return {
        "spoofing_detected": bool(prediction == -1),
        "anomaly_score": round(anomaly_score, 4)
    }

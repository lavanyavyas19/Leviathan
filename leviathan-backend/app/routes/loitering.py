from fastapi import APIRouter
from pydantic import BaseModel
from sklearn.cluster import DBSCAN
import numpy as np

router = APIRouter(prefix="/loitering", tags=["Loitering Detection"])

class LoiteringInput(BaseModel):
    coordinates: list[list[float]]  # [ [lat, lon], [lat, lon], ...]

@router.post("/detect")
def detect_loitering(data: LoiteringInput):
    X = np.array(data.coordinates)
    model = DBSCAN(eps=0.01, min_samples=5)
    labels = model.fit_predict(X)
    loitering_detected = np.any(labels != -1)
    return {"loitering_detected": bool(loitering_detected)}

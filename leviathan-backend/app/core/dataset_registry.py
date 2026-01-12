# app/core/dataset_registry.py
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ACTIVE_DATASET_PATH = os.path.join(DATA_DIR, "active_dataset.json")

def set_active_dataset(payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(ACTIVE_DATASET_PATH, "w") as f:
        json.dump(payload, f, indent=2)

def get_active_dataset() -> Optional[Dict[str, Any]]:
    if not os.path.exists(ACTIVE_DATASET_PATH):
        return None
    with open(ACTIVE_DATASET_PATH, "r") as f:
        return json.load(f)

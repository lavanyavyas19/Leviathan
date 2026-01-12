from fastapi import APIRouter, HTTPException
from app.core.dataset_registry import get_active_dataset

router = APIRouter()

@router.get("/dataset/active")
def dataset_active():
    active = get_active_dataset()
    if not active:
        raise HTTPException(status_code=404, detail="No active dataset. Upload and process a dataset first.")
    return active

@router.get("/dataset/summary")
def dataset_summary():
    active = get_active_dataset()
    if not active:
        raise HTTPException(status_code=404, detail="No active dataset. Upload and process a dataset first.")
    return {
        "updated_at": active.get("updated_at"),
        "clean_s3_uri": active.get("clean_s3_uri"),
        "records_after_cleaning": active.get("records_after_cleaning"),
        "summary": active.get("summary", {})
    }

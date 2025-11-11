# app/routes/ingestion.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.ingestion_engine import run_ingestion_pipeline
import shutil
import os

router = APIRouter()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

@router.post("/ingest")
async def ingest_ais_data(file: UploadFile = File(...)):
    """
    Upload an AIS CSV file and trigger ingestion + preprocessing pipeline.
    """
    try:
        # --- Save uploaded file temporarily ---
        temp_path = os.path.join(DATA_DIR, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # --- Run the ingestion pipeline ---
        processed_path = run_ingestion_pipeline(temp_path)

        return {
            "status": "success",
            "message": "AIS data ingested and processed successfully",
            "processed_file": os.path.basename(processed_path)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during ingestion: {str(e)}")


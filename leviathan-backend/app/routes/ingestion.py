# app/routes/ingestion.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.core.ingestion_engine import run_ingestion_pipeline
import os
import shutil

router = APIRouter()

# Define data directory where uploaded files are stored
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

@router.post("/upload-ais-data")
async def upload_ais_data(file: UploadFile = File(...)):
    """
    Upload an AIS CSV file and trigger the ingestion + preprocessing pipeline.
    """
    try:
        # Ensure only valid file types are accepted
        if not file.filename.lower().endswith((".csv", ".json")):
            raise HTTPException(status_code=400, detail="Only .csv or .json files are allowed.")

        # Save uploaded file temporarily
        temp_path = os.path.join(DATA_DIR, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run your custom ingestion pipeline (returns path to processed file)
        processed_path = run_ingestion_pipeline(temp_path)

        # Build clean frontend-friendly JSON response
        return JSONResponse({
            "status": "success",
            "message": "AIS data uploaded and processed successfully.",
            "original_file": file.filename,
            "processed_file": os.path.basename(processed_path)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during ingestion: {str(e)}")

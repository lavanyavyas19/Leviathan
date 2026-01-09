# app/routes/ingestion.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.core.ingestion_engine import run_ingestion_pipeline
from app.utils.s3_upload import upload_raw_csv_to_s3
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Define data directory where uploaded files are stored
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)


@router.post("/upload-ais-data")
async def upload_ais_data(file: UploadFile = File(...)):
    """
    Upload an AIS CSV file, upload to S3 raw bucket, and trigger the ingestion + preprocessing pipeline.
    """
    try:
        # Ensure only valid file types are accepted
        if not file.filename.lower().endswith((".csv", ".json", ".gz", ".csv.gz")):
            raise HTTPException(status_code=400, detail="Only .csv, .json, or .csv.gz files are allowed.")

        # ========== NEW: Upload to S3 Raw Bucket ==========
        raw_bucket = os.getenv(
            'AWS_S3_RAW_BUCKET',
            'leviathan6475ae6b4f4b48dfa336e5b0541df3904d7b5-dev'
        )
        
        # Upload raw file to S3
        upload_result = await upload_raw_csv_to_s3(file, raw_bucket)
        
        if not upload_result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"S3 upload failed: {upload_result.get('message')}"
            )
        # ==================================================

        # Reset file pointer after S3 upload
        await file.seek(0)

        # Save uploaded file temporarily for local processing
        temp_path = os.path.join(DATA_DIR, file.filename)
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run your custom ingestion pipeline (returns path to processed file)
        processed_path = run_ingestion_pipeline(temp_path)

        # Build clean frontend-friendly JSON response with S3 info
        return JSONResponse({
            "status": "success",
            "message": "AIS data uploaded to S3 and processed successfully.",
            "original_file": file.filename,
            "processed_file": os.path.basename(processed_path),
            # NEW: S3 upload info
            "s3_upload": {
                "status": "uploaded",
                "bucket": upload_result['bucket'],
                "key": upload_result['s3_key'],
                "s3_location": f"s3://{upload_result['bucket']}/{upload_result['s3_key']}",
                "size_bytes": upload_result['size_bytes'],
                "lifecycle": "Auto-delete after 3 days"
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during ingestion: {str(e)}")

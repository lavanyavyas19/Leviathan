from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from uuid import uuid4
import os, shutil

from app.core.ingestion_engine import run_ingestion_pipeline
from app.utils.s3_upload import upload_raw_csv_to_s3
from app.core.job_store import create_job, update_job, get_job

load_dotenv()
router = APIRouter()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def _process_ingestion_job(job_id: str, temp_path: str, clean_bucket: str):
    try:
        update_job(job_id, {"status": "processing", "step": "clean_and_preprocess"})

        pipeline_result = run_ingestion_pipeline(temp_path, clean_bucket)

        update_job(job_id, {"status": "done", "step": "completed", "result": pipeline_result})

    except Exception as e:
        update_job(job_id, {"status": "failed", "error": str(e)})

    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass

@router.post("/upload-ais-data")
async def upload_ais_data(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith((".csv", ".json", ".gz", ".csv.gz")):
            raise HTTPException(status_code=400, detail="Only .csv, .json, or .csv.gz files are allowed.")

        raw_bucket = os.getenv("AWS_S3_RAW_BUCKET", "leviathan6475ae6b4f4b48dfa336e5b0541df3904d7b5-dev")
        clean_bucket = os.getenv("AWS_S3_CLEAN_BUCKET", "leviathan6475ae6b4f4b48dfa336e5b0541df3904d7b5-dev")

        # 1) Create job
        job_id = str(uuid4())
        create_job(job_id, {"status": "uploading", "filename": file.filename})

        # 2) Upload raw to S3
        upload_result = await upload_raw_csv_to_s3(file, raw_bucket)
        if not upload_result["success"]:
            update_job(job_id, {"status": "failed", "error": upload_result.get("message")})
            raise HTTPException(status_code=500, detail=upload_result.get("message"))

        update_job(job_id, {"status": "queued", "raw_s3": upload_result})

        # 3) Save locally
        await file.seek(0)
        temp_path = os.path.join(DATA_DIR, f"{job_id}_{file.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 4) Background processing
        background_tasks.add_task(_process_ingestion_job, job_id, temp_path, clean_bucket)

        # 5) Return immediately
        return JSONResponse({
            "status": "accepted",
            "job_id": job_id,
            "message": "Upload complete ✅ Processing started in background.",
            "raw_s3": upload_result
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

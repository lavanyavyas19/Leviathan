# app/routes/ingestion.py

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.core.ingestion_engine import run_ingestion_pipeline
from app.core.job_store import create_job, update_job
from app.core.anomaly_detection import detect_spoofing_events, detect_loitering_events
from app.utils.s3_upload import upload_raw_csv_to_s3, upload_clean_csv_to_s3

import pandas as pd
import joblib
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(tags=["Ingestion"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)


@router.post("/import")
async def import_ais_data(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Import AIS data file and start processing pipeline.
    Returns job_id immediately with PROCESSING status, processing happens in background.
    """
    job_id = str(uuid.uuid4())

    if not file.filename or not file.filename.lower().endswith((".csv", ".json", ".gz", ".csv.gz")):
        raise HTTPException(status_code=400, detail="Only .csv, .json, or .csv.gz files are allowed.")

    create_job(
        job_id,
        {
            "status": "PROCESSING",
            "created_at": datetime.now().isoformat(),
            "raw_s3": None,
            "clean_s3": None,
            "original_filename": file.filename,
        },
    )

    print(f"✅ Job {job_id} created")
    print(f"🔄 Job {job_id} → PROCESSING")

    await file.seek(0)
    file_content = await file.read()
    original_filename = file.filename or "upload.csv"

    raw_bucket = os.getenv("AWS_S3_RAW_BUCKET", "your-default-raw-bucket")

    background_tasks.add_task(
        process_file_background,
        job_id,
        file_content,
        original_filename,
        raw_bucket,
    )

    return JSONResponse({"job_id": job_id, "status": "PROCESSING"})


def _to_iso(val):
    """Make timestamps JSON-safe."""
    try:
        if val is None:
            return None
        # pandas Timestamp / datetime
        if hasattr(val, "isoformat"):
            return val.isoformat()
        # string or others
        return str(val)
    except Exception:
        return None


async def process_file_background(
    job_id: str,
    file_content: bytes,
    original_filename: str,
    bucket_name: str,
):
    """
    Background task to process the uploaded file:
    1. Upload raw file to S3
    2. Process/clean the file
    3. Detect anomalies
    4. Build job outputs (live_alerts, anomaly_reports, vessel_logs)
    5. Upload cleaned file to S3
    6. Update job status to DONE
    """
    try:
        class FileWrapper:
            def __init__(self, content: bytes, filename: str):
                self.content = content
                self.filename = filename
                self._position = 0

            async def seek(self, position: int):
                self._position = position

            async def read(self):
                return self.content

        # sanitize filename (avoid path traversal / weird paths)
        safe_name = os.path.basename(original_filename)
        file_wrapper = FileWrapper(file_content, safe_name)

        # 1) Upload raw
        upload_result = await upload_raw_csv_to_s3(file_wrapper, bucket_name, job_id)
        if not upload_result.get("success"):
            update_job(
                job_id,
                {
                    "status": "FAILED",
                    "error": upload_result.get("message", "S3 upload failed"),
                    "failed_at": datetime.now().isoformat(),
                },
            )
            print(f"❌ Job {job_id} → FAILED (S3 upload error)")
            return

        raw_s3_path = upload_result.get("s3_location")
        print(f"📤 Raw file uploaded: {raw_s3_path}")

        # 2) Write temp locally
        temp_path = os.path.join(DATA_DIR, f"{job_id}_{safe_name}")
        with open(temp_path, "wb") as f:
            f.write(file_content)

        # 3) Run ingestion pipeline
        processed_path = run_ingestion_pipeline(temp_path)
        print(f"✅ Processing complete: {processed_path}")

        df_clean = pd.read_csv(processed_path)
        print(f"📊 Loaded {len(df_clean)} cleaned records for anomaly detection")

        # 4) Anomaly detection
        print("🔍 Running spoofing detection...")
        spoofing_events = detect_spoofing_events(df_clean)
        print(f"✅ Detected {len(spoofing_events)} spoofing events")

        print("🔍 Running loitering detection...")
        loitering_events = detect_loitering_events(df_clean)
        print(f"✅ Detected {len(loitering_events)} loitering events")

        # -----------------------------
        # BUILD FRONTEND OUTPUTS
        # -----------------------------
        spoofing_list = []
        if hasattr(spoofing_events, "to_dict"):
            spoofing_list = spoofing_events.replace({pd.NA: None}).to_dict(orient="records")

        loitering_list = []
        if hasattr(loitering_events, "to_dict"):
            loitering_list = loitering_events.replace({pd.NA: None}).to_dict(orient="records")

        # Live alerts (JSON-safe timestamps)
        live_alerts = []

        for e in spoofing_list:
            live_alerts.append(
                {
                    "type": "spoofing",
                    "severity": e.get("severity", "low"),
                    "mmsi": e.get("mmsi"),
                    "lat": e.get("lat"),
                    "lon": e.get("lon"),
                    "timestamp": _to_iso(e.get("timestamp")),
                    "score": e.get("score"),
                }
            )

        for e in loitering_list:
            live_alerts.append(
                {
                    "type": "loitering",
                    "severity": e.get("severity", "low"),
                    "mmsi": e.get("mmsi"),
                    "lat": e.get("lat"),
                    "lon": e.get("lon"),
                    "timestamp": _to_iso(e.get("timestamp")),
                    "cluster_size": e.get("cluster_size"),
                    "dwell_time_hr": e.get("dwell_time_hr"),
                }
            )

        spoofing_count = len(spoofing_list)
        loitering_count = len(loitering_list)

        anomaly_reports = {
            "total": spoofing_count + loitering_count,
            "spoofing": spoofing_count,
            "loitering": loitering_count,
            "speed": 0,
            "deviation": 0,
        }

        # -----------------------------
        # VESSEL LOGS (with flags)
        # -----------------------------
        df_for_logs = df_clean.copy()

        vessel_name_col = None
        for c in ["vessel_name", "vessel", "shipname", "name"]:
            if c in df_for_logs.columns:
                vessel_name_col = c
                break

        if "timestamp" in df_for_logs.columns:
            df_for_logs["timestamp"] = pd.to_datetime(df_for_logs["timestamp"], errors="coerce")
            df_for_logs = df_for_logs.sort_values(["mmsi", "timestamp"])
        else:
            df_for_logs = df_for_logs.sort_values(["mmsi"])

        # ✅ FIX: last_rows MUST be outside if/else
        last_rows = df_for_logs.groupby("mmsi", as_index=False).tail(1)

        # MMSI sets
        try:
            spoofing_mmsi_set = {
                int(x)
                for x in pd.Series([e.get("mmsi") for e in spoofing_list]).dropna().unique()
            }
        except Exception:
            spoofing_mmsi_set = set()

        try:
            loitering_mmsi_set = {
                int(x)
                for x in pd.Series([e.get("mmsi") for e in loitering_list]).dropna().unique()
            }
        except Exception:
            loitering_mmsi_set = set()

        vessel_logs = []
        for _, r in last_rows.iterrows():
            mmsi = r.get("mmsi")
            try:
                mmsi_int = int(mmsi) if mmsi is not None else None
            except Exception:
                mmsi_int = None

            ts = r.get("timestamp")
            ts_iso = _to_iso(ts) if ts is not None and pd.notna(ts) else None

            vessel_name = (
                (r.get(vessel_name_col) if vessel_name_col else None)
                or (f"MMSI-{mmsi}" if mmsi is not None else "Unknown")
            )

            vessel_type = r.get("vessel_type")
            sog = r.get("sog")

            # ✅ FIX: use "is not None" not truthiness
            spoofing_flag = (mmsi_int in spoofing_mmsi_set) if (mmsi_int is not None) else False
            loitering_flag = (mmsi_int in loitering_mmsi_set) if (mmsi_int is not None) else False

            status = "normal"
            if spoofing_flag:
                status = "spoofing"
            elif loitering_flag:
                status = "loitering"

            vessel_logs.append(
                {
                    # Frontend keys
                    "vessel_name": vessel_name,
                    "vessel_type": vessel_type,
                    "sog": sog,
                    "timestamp": ts_iso,
                    "spoofing_flag": spoofing_flag,
                    "loitering_flag": loitering_flag,

                    # optional extras
                    "destination": r.get("destination"),
                    "draft": r.get("draft"),

                    # core
                    "mmsi": mmsi,
                    "lat": r.get("lat"),
                    "lon": r.get("lon"),

                    # backward compat
                    "vessel": vessel_name,
                    "type": vessel_type,
                    "speed": sog,
                    "updated": ts_iso,
                    "status": status,
                }
            )

        # Update job store
        update_job(
            job_id,
            {
                "live_alerts": live_alerts,
                "anomaly_reports": anomaly_reports,
                "vessel_logs": vessel_logs,
                "summary": {
                    "live_alerts_total": len(live_alerts),
                    "vessel_logs_total": len(vessel_logs),
                },
            },
        )

        # Save artifacts
        job_data_dir = os.path.join(DATA_DIR, "jobs", job_id)
        os.makedirs(job_data_dir, exist_ok=True)

        spoofing_path = os.path.join(job_data_dir, "spoofing_events.pkl")
        loitering_path = os.path.join(job_data_dir, "loitering_events.pkl")

        joblib.dump(spoofing_events, spoofing_path)
        joblib.dump(loitering_events, loitering_path)
        print(f"💾 Saved detection results to {job_data_dir}")

        # Upload cleaned file
        clean_upload_result = await upload_clean_csv_to_s3(
            processed_path,
            bucket_name,
            job_id,
            safe_name,
        )

        if not clean_upload_result.get("success"):
            update_job(
                job_id,
                {
                    "status": "FAILED",
                    "error": clean_upload_result.get("message", "Clean S3 upload failed"),
                    "raw_s3": raw_s3_path,
                    "failed_at": datetime.now().isoformat(),
                },
            )
            print(f"❌ Job {job_id} → FAILED (Clean S3 upload error)")
            return

        clean_s3_path = clean_upload_result.get("s3_location")
        print(f"📤 Cleaned file uploaded: {clean_s3_path}")

        update_job(
            job_id,
            {
                "status": "DONE",
                "raw_s3": raw_s3_path,
                "clean_s3": clean_s3_path,
                "completed_at": datetime.now().isoformat(),
            },
        )
        print(f"✅ Job {job_id} → DONE")

        # Cleanup
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(processed_path):
                os.remove(processed_path)
        except Exception as cleanup_error:
            print(f"⚠️ Warning: Failed to cleanup temp files: {cleanup_error}")

    except Exception as e:
        update_job(
            job_id,
            {
                "status": "FAILED",
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
            },
        )
        print(f"❌ Job {job_id} → FAILED: {str(e)}")

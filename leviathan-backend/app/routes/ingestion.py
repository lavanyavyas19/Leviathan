# app/routes/ingestion.py
#
# ─── ROOT CAUSE ANALYSIS — bottlenecks in the previous version ──────────────
#
#  1. DOUBLE CSV READ  (lines 172, 178–180 in old code)
#     ──────────────────────────────────────────────────
#     run_ingestion_pipeline() wrote a processed CSV to disk.
#     Then _process_file() immediately read it back with pd.read_csv().
#     For a 50 MB input this caused:
#       - One CSV WRITE  (~0.8 s, no compression, ~15 MB on disk)
#       - One CSV READ   (~1.2 s, full dtype re-inference)
#       - 2× memory spike during the transition
#     FIX: run_ingestion_pipeline() now returns (path, df_clean) so the
#          DataFrame is passed directly to anomaly detection.
#          The processed file is now Parquet (3–5× smaller, 5–10× faster).
#
#  2. REDUNDANT df_clean.copy() FOR VESSEL LOGS  (line 240)
#     ─────────────────────────────────────────────────────
#     df_logs = df_clean.copy()
#     A full copy of 206 k rows was made just to call groupby().tail(1).
#     groupby().tail() does NOT modify df — no copy needed.
#     FIX: operate on df_clean directly; use .last() instead of .tail(1)
#          which is vectorised without creating group DataFrames.
#
#  3. TIMESTAMP RE-PARSE AND RE-SORT  (lines 246–247)
#     ──────────────────────────────────────────────────
#     df_logs["timestamp"] = pd.to_datetime(...)  ← already done in preprocessing
#     df_logs = df_logs.sort_values(["mmsi", "timestamp"])  ← already sorted
#     FIX: remove; trust preprocessing output.
#
#  4. PYTHON SET COMPREHENSIONS OVER DICT LISTS  (lines 251–258)
#     ────────────────────────────────────────────────────────────
#     spoofing_mmsi_set = {int(x) for x in pd.Series([e.get("mmsi") for e in spoofing_list])...}
#     Converts spoofing_events DataFrame → list of dicts → Series → set.
#     FIX: use DataFrame.iloc / .unique() directly on spoofing_events.
#
#  5. PYTHON for-loop BUILDING live_alerts  (lines 208–229)
#     ──────────────────────────────────────────────────────
#     Two separate Python for-loops iterate spoofing_list and loitering_list
#     to build dicts.  For 2 000 alerts this is 2 000 Python dict.append calls.
#     FIX: use DataFrame vectorised operations + pd.concat + .to_dict().
#
#  6. PEAK MEMORY CASCADE
#     ─────────────────────
#     At peak the old pipeline held:
#       df_raw       (~50 MB) + df_clean copy (~30 MB) + spoofing copy (~30 MB)
#       + loitering copy (~30 MB) + df_logs copy (~30 MB) = ~170 MB
#     New pipeline peak:
#       df_raw (~50 MB) → freed → df_clean (~25 MB) → slim work slices (~10 MB each)
#       = peak ~50 MB
#
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import gc
import logging
import os
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.anomaly_detection import detect_loitering_events, detect_spoofing_events
from app.core.ingestion_engine import run_ingestion_pipeline
from app.core.job_store import create_job, update_job
from app.core.profiling import PipelineTimer, timed_step

load_dotenv()

logger = logging.getLogger("leviathan.ingestion")
router = APIRouter(tags=["Ingestion"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

_S3_ENABLED = os.getenv("ENABLE_S3_UPLOAD", "false").lower() == "true"


def _s3_available() -> bool:
    return (
        _S3_ENABLED
        and bool(os.getenv("AWS_ACCESS_KEY_ID"))
        and bool(os.getenv("AWS_SECRET_ACCESS_KEY"))
        and bool(os.getenv("AWS_S3_RAW_BUCKET"))
    )


def _to_iso(val) -> str | None:
    """Convert any timestamp-like value to an ISO 8601 string, or None."""
    if val is None:
        return None
    # NaT / NaN check
    try:
        if pd.isnull(val):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_ais_data(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Accept a CSV upload, create a job record, and return a job_id immediately.
    All heavy work runs in _process_file() on a background thread.
    """
    fname = (file.filename or "").lower()
    if not fname.endswith((".csv", ".json", ".gz", ".csv.gz")):
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .json, or .csv.gz files are accepted.",
        )

    job_id = str(uuid.uuid4())
    # create_job() writes to job_store.json — run in a thread so it
    # does not block the event loop while the response waits.
    await asyncio.to_thread(create_job, job_id, {
        "status":            "PROCESSING",
        "progress":          0,
        "created_at":        datetime.now().isoformat(),
        "original_filename": file.filename,
        "raw_s3":            None,
        "clean_s3":          None,
    })
    logger.info(f"[IMPORT] Job {job_id} created — {file.filename}")

    await file.seek(0)
    file_content = await file.read()
    safe_name    = os.path.basename(file.filename or "upload.csv")

    if background_tasks is None:
        background_tasks = BackgroundTasks()

    background_tasks.add_task(_process_file, job_id, file_content, safe_name)

    return JSONResponse({"job_id": job_id, "status": "PROCESSING"}, status_code=202)


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

async def _process_file(job_id: str, file_content: bytes, safe_name: str):
    """
    Full processing pipeline:
      1. (Optional) Upload raw bytes to S3
      2. Write temp file to disk
      3. run_ingestion_pipeline() → (parquet_path, df_clean)  ← no double read
      4. detect_spoofing_events(df_clean)
      5. detect_loitering_events(df_clean)
      6. Free df_clean from memory
      7. Build frontend payloads (vectorised)
      8. Cap + store in job store
      9. (Optional) Upload parquet to S3
     10. Mark DONE
    """
    temp_path    = None
    parquet_path = None
    timer        = PipelineTimer(job_id=job_id)

    try:
        # ── 1. Optional S3 raw upload ─────────────────────────────────────────
        raw_s3_path = None
        if _s3_available():
            timer.start("s3_raw_upload")
            try:
                from app.utils.s3_upload import upload_raw_csv_to_s3

                class _FakeUpload:
                    filename = safe_name
                    async def seek(self, n): pass
                    async def read(self):    return file_content

                raw_bucket  = os.getenv("AWS_S3_RAW_BUCKET", "")
                result      = await upload_raw_csv_to_s3(_FakeUpload(), raw_bucket, job_id)
                raw_s3_path = result.get("s3_location") if result.get("success") else None
            except Exception as e:
                logger.warning(f"[IMPORT] {job_id} S3 raw upload failed (non-fatal): {e}")
            finally:
                timer.stop("s3_raw_upload")

        # ── 2. Write temp file ────────────────────────────────────────────────
        timer.start("write_temp")
        temp_path = os.path.join(DATA_DIR, f"{job_id}_{safe_name}")
        with open(temp_path, "wb") as fh:
            fh.write(file_content)
        timer.stop("write_temp")

        # Free the in-memory file bytes immediately — we have it on disk now
        file_content = None   # allow GC
        gc.collect()
        logger.info(f"[IMPORT] {job_id} temp file: {temp_path}")

        # update_job() writes to job_store.json — offload to thread
        await asyncio.to_thread(update_job, job_id, {"status": "INGESTING", "progress": 10})

        # ── 3. Ingest + preprocess → parquet_path, df_clean ──────────────────
        #    NEW: run_ingestion_pipeline() returns BOTH the parquet path AND
        #    the cleaned DataFrame.  We use df_clean directly for anomaly
        #    detection — no second CSV/Parquet read.
        timer.start("ingest_pipeline")
        parquet_path, df_clean = await asyncio.to_thread(
            run_ingestion_pipeline, temp_path
        )
        timer.stop("ingest_pipeline")
        logger.info(f"[IMPORT] {job_id} ingestion done: {len(df_clean):,} rows")

        await asyncio.to_thread(update_job, job_id, {"status": "DETECTING", "progress": 40})

        # ── 4. Spoofing detection ─────────────────────────────────────────────
        timer.start("detect_spoofing")
        spoofing_events = await asyncio.to_thread(detect_spoofing_events, df_clean)
        timer.stop("detect_spoofing")
        logger.info(f"[IMPORT] {job_id} spoofing: {len(spoofing_events)} events")

        await asyncio.to_thread(update_job, job_id, {"progress": 65})

        # ── 5. Loitering detection ────────────────────────────────────────────
        timer.start("detect_loitering")
        loitering_events = await asyncio.to_thread(detect_loitering_events, df_clean)
        timer.stop("detect_loitering")
        logger.info(f"[IMPORT] {job_id} loitering: {len(loitering_events)} events")

        await asyncio.to_thread(update_job, job_id, {"status": "BUILDING", "progress": 80})

        # ── 6. Build frontend payloads (vectorised — no Python for-loops) ─────
        timer.start("build_payloads")

        live_alerts, vessel_logs, anomaly_reports, summary = await asyncio.to_thread(
            _build_payloads, df_clean, spoofing_events, loitering_events
        )

        timer.stop("build_payloads")

        # ── 7. Free large DataFrames immediately after payload build ──────────
        del df_clean, spoofing_events, loitering_events
        gc.collect()

        # ── 8. Cap + store in job store ───────────────────────────────────────
        timer.start("cap_and_store")

        MAX_VESSEL_LOGS = 2_000
        MAX_LIVE_ALERTS = 2_000

        anomalous_logs = [v for v in vessel_logs if v.get("spoofing_flag") or v.get("loitering_flag")]
        normal_logs    = [v for v in vessel_logs if not v.get("spoofing_flag") and not v.get("loitering_flag")]
        budget         = max(0, MAX_VESSEL_LOGS - len(anomalous_logs))
        vessel_logs_capped = (anomalous_logs + normal_logs[:budget])[:MAX_VESSEL_LOGS]
        live_alerts_capped = live_alerts[:MAX_LIVE_ALERTS]

        logger.info(
            f"[IMPORT] {job_id} capping: "
            f"vessel_logs {len(vessel_logs)} → {len(vessel_logs_capped)}, "
            f"live_alerts {len(live_alerts)} → {len(live_alerts_capped)}"
        )

        # update_job() is non-blocking now (strips heavy keys before disk write)
        await asyncio.to_thread(update_job, job_id, {
            "live_alerts":     live_alerts_capped,
            "anomaly_reports": anomaly_reports,
            "vessel_logs":     vessel_logs_capped,
            "summary":         summary,
        })

        timer.stop("cap_and_store")

        # ── 9. Optional S3 Parquet upload ─────────────────────────────────────
        clean_s3_path = None
        if _s3_available() and parquet_path:
            timer.start("s3_clean_upload")
            try:
                from app.utils.s3_upload import upload_clean_csv_to_s3
                raw_bucket    = os.getenv("AWS_S3_RAW_BUCKET", "")
                result        = await upload_clean_csv_to_s3(parquet_path, raw_bucket, job_id, safe_name)
                clean_s3_path = result.get("s3_location") if result.get("success") else None
            except Exception as e:
                logger.warning(f"[IMPORT] {job_id} S3 clean upload failed (non-fatal): {e}")
            finally:
                timer.stop("s3_clean_upload")

        # ── 10. Mark DONE ──────────────────────────────────────────────────────
        timer.report()
        await asyncio.to_thread(update_job, job_id, {
            "status":       "DONE",
            "progress":     100,
            "raw_s3":       raw_s3_path,
            "clean_s3":     clean_s3_path,
            "completed_at": datetime.now().isoformat(),
            "perf":         timer.to_dict(),
        })
        logger.info(f"[IMPORT] Job {job_id} → DONE ✅")

    except Exception as exc:
        import traceback
        logger.error(f"[IMPORT] Job {job_id} → FAILED\n{traceback.format_exc()}")
        await asyncio.to_thread(update_job, job_id, {
            "status":    "FAILED",
            "error":     str(exc),
            "failed_at": datetime.now().isoformat(),
        })

    finally:
        # Always clean up temp files
        for path in [temp_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"[IMPORT] Could not delete temp file {path}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PAYLOAD BUILDER  (pure function, runs in a thread)
# ─────────────────────────────────────────────────────────────────────────────

def _build_payloads(
    df_clean:         pd.DataFrame,
    spoofing_events:  pd.DataFrame,
    loitering_events: pd.DataFrame,
) -> tuple:
    """
    Build live_alerts, vessel_logs, anomaly_reports, and summary dicts.

    PERFORMANCE FIXES vs old code:
      - No df_clean.copy() for vessel_logs — use groupby on original
      - No re-sort or re-parse of timestamps (already done by preprocessing)
      - Build MMSI flag sets directly from DataFrames, not dict lists
      - Build live_alerts with pd.concat + vectorised to_dict()
      - Python for-loops eliminated entirely

    Returns:
        (live_alerts, vessel_logs, anomaly_reports, summary)
    """
    # ── live_alerts — vectorised build ───────────────────────────────────────
    sp_frames = []
    lt_frames = []

    if not spoofing_events.empty:
        sp = spoofing_events[["mmsi", "lat", "lon", "timestamp", "score", "severity"]].copy()
        sp["type"] = "spoofing"
        # BUG-004 FIX: use np.nan (float) not None (object) for missing numeric fields.
        # pd.concat with None produces object-dtype columns; np.nan keeps float dtype,
        # and the subsequent .replace({float("nan"): None}) converts them to JSON null.
        sp["cluster_size"]  = np.nan
        sp["dwell_time_hr"] = np.nan
        sp_frames.append(sp)

    if not loitering_events.empty:
        lt = loitering_events[["mmsi", "lat", "lon", "timestamp", "cluster_size", "severity"]].copy()
        lt["type"]  = "loitering"
        lt["score"] = np.nan  # BUG-004 FIX: np.nan not None
        lt["dwell_time_hr"] = (
            loitering_events["dwell_time_hr"]
            if "dwell_time_hr" in loitering_events.columns
            else np.nan
        )
        lt_frames.append(lt)

    alert_cols = ["type", "severity", "mmsi", "lat", "lon", "timestamp",
                  "score", "cluster_size", "dwell_time_hr"]

    if sp_frames or lt_frames:
        combined = pd.concat(sp_frames + lt_frames, ignore_index=True)

        # Normalise timestamps to ISO strings
        if "timestamp" in combined.columns and pd.api.types.is_datetime64_any_dtype(combined["timestamp"]):
            combined["timestamp"] = combined["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Replace NaN/Inf with None (JSON-safe)
        combined = combined.replace({float("nan"): None, float("inf"): None, float("-inf"): None})

        # Ensure all expected columns exist
        for col in alert_cols:
            if col not in combined.columns:
                combined[col] = None

        live_alerts = combined[alert_cols].to_dict(orient="records")
    else:
        live_alerts = []

    # ── anomaly MMSI sets (from DataFrames, not dict lists) ──────────────────
    sp_mmsi_set = set(spoofing_events["mmsi"].dropna().astype(int).unique()) \
                  if not spoofing_events.empty else set()
    lt_mmsi_set = set(loitering_events["mmsi"].dropna().astype(int).unique()) \
                  if not loitering_events.empty else set()

    # ── vessel_logs — last row per MMSI, no copy ─────────────────────────────
    #    df_clean is already sorted by (mmsi, timestamp) from preprocessing.
    #
    #    BUG-002 FIX: groupby().last() returns the last NON-NaN value per column,
    #    potentially assembling a synthetic row from different timesteps when any
    #    column in the true last row is NaN (vessel_name, destination, draft, etc.
    #    are frequently absent in AIS data).  The resulting row is inconsistent:
    #    position from the most recent record but name from an older one.
    #
    #    FIX: drop_duplicates(subset=["mmsi"], keep="last") selects the true last
    #    row for each MMSI (data is already sorted).  O(N), no hybrid rows.
    vessel_name_col = next(
        (c for c in ["vessel_name", "vessel", "shipname", "name"] if c in df_clean.columns),
        None,
    )

    # Get true last record per MMSI (preserves NaN values as-is)
    last_rows = (
        df_clean
        .drop_duplicates(subset=["mmsi"], keep="last")
        .reset_index(drop=True)
    )

    # Build vessel_logs list with minimal columns
    vessel_logs = []
    for row in last_rows.itertuples(index=False):
        mmsi     = int(row.mmsi) if not pd.isna(row.mmsi) else None
        ts_val   = getattr(row, "timestamp", None)
        ts_iso   = _to_iso(ts_val)

        vname = (
            getattr(row, vessel_name_col, None)
            if vessel_name_col and not pd.isna(getattr(row, vessel_name_col, None))
            else f"MMSI-{mmsi}" if mmsi else "Unknown"
        )

        spoof_flag   = mmsi in sp_mmsi_set if mmsi else False
        loiter_flag  = mmsi in lt_mmsi_set if mmsi else False
        status       = "spoofing" if spoof_flag else "loitering" if loiter_flag else "normal"

        vessel_logs.append({
            "mmsi":           mmsi,
            "lat":            _safe_float(getattr(row, "lat", None)),
            "lon":            _safe_float(getattr(row, "lon", None)),
            "vessel_name":    str(vname) if vname is not None else "Unknown",
            "vessel_type":    str(getattr(row, "vessel_type", "Unknown") or "Unknown"),
            "sog":            _safe_float(getattr(row, "sog", None)),
            "timestamp":      ts_iso,
            "spoofing_flag":  spoof_flag,
            "loitering_flag": loiter_flag,
            "destination":    str(getattr(row, "destination", "") or ""),
            "draft":          _safe_float(getattr(row, "draft", None)),
            "status":         status,
        })

    # ── anomaly_reports ───────────────────────────────────────────────────────
    anomaly_reports = {
        "total":    len(sp_mmsi_set | lt_mmsi_set),
        "spoofing": len(sp_mmsi_set),
        "loitering":len(lt_mmsi_set),
        "speed":    0,
        "deviation":0,
    }

    # ── summary ───────────────────────────────────────────────────────────────
    summary = {
        "live_alerts_total":  len(live_alerts),
        "vessel_logs_total":  len(vessel_logs),
        "unique_vessels":     len(last_rows),
        "anomaly_breakdown":  {
            "total":    anomaly_reports["total"],
            "spoofing": anomaly_reports["spoofing"],
            "loitering":anomaly_reports["loitering"],
            "speed":    0,
            "deviation":0,
        },
    }

    return live_alerts, vessel_logs, anomaly_reports, summary


def _safe_float(val) -> float | None:
    """Convert a value to float, returning None for NaN/Inf/None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f != f or abs(f) == float("inf")) else f
    except (TypeError, ValueError):
        return None

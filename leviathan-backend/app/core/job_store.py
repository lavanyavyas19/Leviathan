# app/core/job_store.py
import json
import logging
import os
from typing import Dict, Any, Optional
from threading import Lock

# Absolute path — correct regardless of the CWD when uvicorn is started.
_HERE      = os.path.dirname(os.path.abspath(__file__))  # …/app/core
_BASE_DIR  = os.path.dirname(os.path.dirname(_HERE))      # …/leviathan-backend
STORE_FILE = os.path.join(_BASE_DIR, "job_store.json")
_lock = Lock()

_logger = logging.getLogger("leviathan.jobstore")

# Keys whose values are large runtime arrays (can be 10s of MB per job).
# These are kept in the in-memory _jobs dict so the API can serve them,
# but they are NEVER written to disk — only metadata is persisted.
_DISK_STRIP_KEYS = frozenset({"live_alerts", "vessel_logs", "anomaly_reports"})

# Skip loading the store file if it is larger than this threshold.
# A file this large almost certainly contains unstripped payload arrays
# from an older version of the code and would OOM the process.
_MAX_STORE_BYTES = 50 * 1_048_576   # 50 MB


def _load_jobs() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(STORE_FILE):
        return {}
    try:
        file_size = os.path.getsize(STORE_FILE)
        if file_size > _MAX_STORE_BYTES:
            _logger.warning(
                f"job_store.json is {file_size / 1_048_576:.1f} MB — too large to load safely. "
                "Resetting to empty store.  Run `echo '{}' > job_store.json` to clear manually."
            )
            # Overwrite the bloated file with an empty store now so the next
            # restart loads instantly.  Previous job data is lost but the
            # server would be non-functional with a 10 GB store anyway.
            try:
                with open(STORE_FILE, "w") as f:
                    f.write("{}\n")
            except Exception:
                pass
            return {}
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_jobs() -> None:
    """
    Persist job metadata to disk.

    Heavy runtime arrays (live_alerts, vessel_logs, anomaly_reports) are
    stripped before writing.  They remain in the in-memory _jobs dict so
    the API can serve them within the current server process lifetime, but
    they are never written to job_store.json.

    This keeps the on-disk store small (a few KB per job) regardless of
    how many AIS records each job processed.
    """
    try:
        slim = {
            jid: {k: v for k, v in job.items() if k not in _DISK_STRIP_KEYS}
            for jid, job in _jobs.items()
        }
        with open(STORE_FILE, "w") as f:
            json.dump(slim, f, indent=2, default=str)
    except Exception as exc:
        # Log but do NOT re-raise — a failed disk write must never cause
        # a 500 on the HTTP endpoint that triggered the update.
        _logger.error(f"job_store: failed to persist to disk: {exc}")


_jobs: Dict[str, Dict[str, Any]] = _load_jobs()


def create_job(job_id: str, data: Dict[str, Any]) -> None:
    with _lock:
        _jobs[job_id] = data
        _save_jobs()


def update_job(job_id: str, patch: Dict[str, Any]) -> None:
    with _lock:
        if job_id not in _jobs:
            _jobs[job_id] = {}
        _jobs[job_id].update(patch)
        _save_jobs()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return _jobs.get(job_id)


def ensure_job(job_id: str) -> Dict[str, Any]:
    with _lock:
        if job_id not in _jobs:
            _jobs[job_id] = {}
            _save_jobs()
        return _jobs[job_id]
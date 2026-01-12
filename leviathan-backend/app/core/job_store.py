# app/core/job_store.py
from typing import Dict, Any
from threading import Lock

_jobs: Dict[str, Dict[str, Any]] = {}
_lock = Lock()

def create_job(job_id: str, data: Dict[str, Any]) -> None:
    with _lock:
        _jobs[job_id] = data

def update_job(job_id: str, patch: Dict[str, Any]) -> None:
    with _lock:
        if job_id not in _jobs:
            _jobs[job_id] = {}
        _jobs[job_id].update(patch)

def get_job(job_id: str):
    with _lock:
        return _jobs.get(job_id)

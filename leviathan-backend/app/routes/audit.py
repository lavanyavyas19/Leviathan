# app/routes/audit.py
"""
REST endpoint for serving tamper-evident audit log entries.
Reads the NDJSON audit log written by app.core.audit_log and returns
paginated records in a frontend-compatible format.

Pydantic v2 / FastAPI >=0.110 compatible — uses Annotated[] style for all
query params to avoid the Optional[str]=Query(None) validation regression.
"""

from __future__ import annotations

from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import os
import json
import traceback

router = APIRouter(tags=["Audit Logs"])

# Resolve path relative to THIS file so it is correct regardless of the CWD
# when uvicorn is started.
#   __file__  → …/leviathan-backend/app/routes/audit.py
#   _APP_DIR  → …/leviathan-backend/app
#   _BASE_DIR → …/leviathan-backend
_HERE     = os.path.dirname(os.path.abspath(__file__))
_APP_DIR  = os.path.dirname(_HERE)
_BASE_DIR = os.path.dirname(_APP_DIR)
AUDIT_LOG = os.path.join(_BASE_DIR, "logs", "audit.ndjson")


def _read_audit_entries() -> list:
    """
    Read all NDJSON records from the audit log.
    Returns [] if the file does not exist, is empty, or cannot be read.
    Skips individual lines that are not valid JSON.
    """
    if not os.path.exists(AUDIT_LOG):
        return []

    entries: list = []
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []

    return entries


@router.get("/audit-logs")
def get_audit_logs(
    limit:      Annotated[int, Query(ge=1, le=1000)] = 100,
    offset:     Annotated[int, Query(ge=0)]           = 0,
    event_type: Annotated[Optional[str], Query()]     = None,
) -> JSONResponse:
    """
    Return paginated audit log entries newest-first.

    Response schema:
        {
          "count":   int,
          "offset":  int,
          "limit":   int,
          "entries": [ { seq, timestamp_utc, event_type,
                         payload, previous_hash, current_hash }, ... ]
        }
    """
    try:
        entries = _read_audit_entries()

        if event_type:
            entries = [e for e in entries if e.get("event_type") == event_type]

        total = len(entries)
        entries = list(reversed(entries))          # newest first
        page    = entries[offset: offset + limit]  # paginate

        return JSONResponse(content={
            "count":   total,
            "offset":  offset,
            "limit":   limit,
            "entries": page,
        })

    except Exception as exc:
        # Surface the real exception in the uvicorn log AND in the HTTP response
        # so it is visible in the browser console rather than a blank 500.
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"audit-logs error — {type(exc).__name__}: {exc}",
        )

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
from pydantic import BaseModel
import os
import json
import traceback

from app.core.audit_log import append_event as _audit_append

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


# ─────────────────────────────────────────────────────────────────────────────
# ALERT ACTION  (ACK / DISMISS)
# ─────────────────────────────────────────────────────────────────────────────

class AlertActionBody(BaseModel):
    """Payload sent by the frontend when an operator ACKs or dismisses an alert."""
    action:    str             # "ALERT_ACK" | "ALERT_DISMISSED"
    alert_id:  str             # opaque key from alertKey() in RightPanel
    vessel_id: Optional[int]  = None
    timestamp: Optional[str]  = None
    user:      str             = "operator"
    details:   Optional[str]  = None


@router.post("/audit-logs/alert-action")
def log_alert_action(body: AlertActionBody) -> JSONResponse:
    """
    Write a tamper-evident audit entry for an operator ACK or Dismiss action.
    Returns { ok, seq } on success; never raises (errors are logged + 500).
    """
    action = (body.action or "").upper()
    if action not in ("ALERT_ACK", "ALERT_DISMISSED"):
        raise HTTPException(
            status_code=400,
            detail=f"action must be ALERT_ACK or ALERT_DISMISSED, got: {body.action!r}",
        )
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        record = _audit_append(AUDIT_LOG, action, {
            "alert_id":  body.alert_id,
            "vessel_id": body.vessel_id,
            "timestamp": body.timestamp,
            "user":      body.user,
            "details":   body.details,
        })
        return JSONResponse(content={"ok": True, "seq": record.get("seq")})
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"alert-action error — {type(exc).__name__}: {exc}",
        )

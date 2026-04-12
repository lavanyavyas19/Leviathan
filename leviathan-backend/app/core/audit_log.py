"""
audit_log.py — Tamper-Evident Append-Only Audit Log
====================================================
Implements an NDJSON (newline-delimited JSON) audit log where every entry
is cryptographically linked to its predecessor via SHA-256 hash chaining.

Design properties
-----------------
  * Append-only: one JSON line per event; existing lines are never modified.
  * Deterministic serialisation: json.dumps with sort_keys=True and
    separators=(',',':') ensures identical bytes for identical content,
    so any re-verification produces the same hashes.
  * Genesis entry: the first record uses previous_hash = "0" * 64, a
    conventional sentinel indicating no predecessor.
  * Tamper detection: modifying, inserting, or deleting any record breaks
    the hash linkage. verify_chain() detects and localises the break.
  * Thread-safe: a module-level Lock serialises concurrent append calls
    within the same process.
  * No external dependencies: only hashlib, json, os, threading, datetime.

Log record schema
-----------------
  {
    "seq":            int,          -- monotone sequence number (0-based)
    "timestamp_utc":  str,          -- ISO-8601 UTC, e.g. "2026-03-14T12:00:00.000000Z"
    "event_type":     str,          -- caller-defined label, e.g. "job_created"
    "payload":        dict,         -- arbitrary event data (must be JSON-serialisable)
    "previous_hash":  str (64 hex), -- SHA-256 of the previous record's canonical form
    "current_hash":   str (64 hex)  -- SHA-256 of THIS record's canonical form (see below)
  }

Hash input
----------
  current_hash = SHA-256(
      json.dumps(
          {
              "seq":           <seq>,
              "timestamp_utc": <timestamp_utc>,
              "event_type":    <event_type>,
              "payload":       <payload>,
              "previous_hash": <previous_hash>
          },
          sort_keys=True,
          separators=(',', ':')
      ).encode("utf-8")
  ).hexdigest()

Usage
-----
  from app.core.audit_log import append_event, verify_chain

  LOG = "audit.ndjson"

  append_event(LOG, "job_created",  {"job_id": "abc", "file": "ais.csv"})
  append_event(LOG, "alert_emitted", {"job_id": "abc", "mmsi": 123456789,
                                      "type": "loitering", "severity": "high"})

  result = verify_chain(LOG)
  print(result)
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from threading import Lock

# ── Module-level write lock ───────────────────────────────────────────────────
_write_lock = Lock()

# ── Constants ─────────────────────────────────────────────────────────────────
GENESIS_HASH = "0" * 64   # previous_hash of the very first record


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string with microseconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical(seq: int, timestamp_utc: str, event_type: str,
               payload: dict, previous_hash: str) -> str:
    """
    Produce a deterministic, canonical JSON string for the five fields that
    are covered by current_hash.  sort_keys=True guarantees key ordering;
    separators=(',',':') eliminates all optional whitespace so the byte
    sequence is identical across Python versions and platforms.
    """
    return json.dumps(
        {
            "seq":            seq,
            "timestamp_utc":  timestamp_utc,
            "event_type":     event_type,
            "payload":        payload,
            "previous_hash":  previous_hash,
        },
        sort_keys=True,
        separators=(',', ':'),
    )


def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8-encoded string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_hash(seq: int, timestamp_utc: str, event_type: str,
                  payload: dict, previous_hash: str) -> str:
    """Compute current_hash for a record."""
    return _sha256(_canonical(seq, timestamp_utc, event_type, payload, previous_hash))


def _read_last_record(log_path: str):
    """
    Return (seq, current_hash) of the last line in an existing log file.
    Returns (-1, GENESIS_HASH) if the file is absent or empty, so that the
    first real record gets seq=0 and previous_hash=GENESIS_HASH.
    """
    if not os.path.exists(log_path):
        return -1, GENESIS_HASH

    last_line = None
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped

    if last_line is None:
        return -1, GENESIS_HASH

    try:
        record = json.loads(last_line)
        return record["seq"], record["current_hash"]
    except (json.JSONDecodeError, KeyError):
        raise ValueError(
            f"Last line of {log_path!r} is malformed or missing 'seq'/'current_hash'. "
            "Cannot safely append to a corrupted log."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def append_event(log_path: str, event_type: str, payload: dict) -> dict:
    """
    Append one event to the audit log at log_path.

    Parameters
    ----------
    log_path   : str   Path to the NDJSON log file (created if absent).
    event_type : str   A short label such as "job_created" or "alert_emitted".
    payload    : dict  Arbitrary JSON-serialisable data for this event.

    Returns
    -------
    dict   The complete record that was written (useful for testing/logging).

    Raises
    ------
    ValueError  If the last existing line is unparseable (log is corrupted).
    TypeError   If payload is not JSON-serialisable.
    """
    with _write_lock:
        prev_seq, previous_hash = _read_last_record(log_path)

        seq           = prev_seq + 1
        timestamp_utc = _now_utc()
        current_hash  = _compute_hash(seq, timestamp_utc, event_type,
                                      payload, previous_hash)

        record = {
            "seq":           seq,
            "timestamp_utc": timestamp_utc,
            "event_type":    event_type,
            "payload":       payload,
            "previous_hash": previous_hash,
            "current_hash":  current_hash,
        }

        # Ensure parent directory exists
        parent = os.path.dirname(os.path.abspath(log_path))
        os.makedirs(parent, exist_ok=True)

        # Append one line; "a" mode never truncates or overwrites
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(',', ':')) + "\n")

        return record


def verify_chain(log_path: str) -> dict:
    """
    Verify the integrity of the entire audit log.

    For every record the function:
      1. Re-computes current_hash from (seq, timestamp_utc, event_type,
         payload, previous_hash) and checks it matches the stored value.
      2. Checks that the record's previous_hash matches current_hash of
         the preceding record (or GENESIS_HASH for seq 0).

    Parameters
    ----------
    log_path : str   Path to the NDJSON log file.

    Returns
    -------
    dict with keys:
        valid          bool   True only if every record passes both checks.
        records_checked int   Number of lines successfully parsed and checked.
        first_bad_seq  int|None  seq of the first failing record, else None.
        error          str|None  Human-readable description of failure, else None.

    Notes
    -----
    The function is read-only and can be called at any time without affecting
    the running system.  It works correctly on a copy of the log file.
    """
    if not os.path.exists(log_path):
        return {
            "valid":           False,
            "records_checked": 0,
            "first_bad_seq":   None,
            "error":           f"Log file not found: {log_path!r}",
        }

    expected_previous_hash = GENESIS_HASH
    expected_seq           = 0
    records_checked        = 0

    with open(log_path, "r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue   # skip blank lines (should not exist in well-formed logs)

            # ── Parse ────────────────────────────────────────────────────────
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                return {
                    "valid":           False,
                    "records_checked": records_checked,
                    "first_bad_seq":   None,
                    "error":           f"JSON parse error on line {lineno}: {exc}",
                }

            # ── Required fields ──────────────────────────────────────────────
            for field in ("seq", "timestamp_utc", "event_type",
                          "payload", "previous_hash", "current_hash"):
                if field not in record:
                    return {
                        "valid":           False,
                        "records_checked": records_checked,
                        "first_bad_seq":   record.get("seq"),
                        "error":           f"Missing field '{field}' on line {lineno}.",
                    }

            seq           = record["seq"]
            timestamp_utc = record["timestamp_utc"]
            event_type    = record["event_type"]
            payload       = record["payload"]
            previous_hash = record["previous_hash"]
            stored_hash   = record["current_hash"]

            # ── Sequence-number check ────────────────────────────────────────
            if seq != expected_seq:
                return {
                    "valid":           False,
                    "records_checked": records_checked,
                    "first_bad_seq":   seq,
                    "error":           (
                        f"Sequence gap on line {lineno}: "
                        f"expected seq={expected_seq}, found seq={seq}."
                    ),
                }

            # ── previous_hash linkage check ──────────────────────────────────
            if previous_hash != expected_previous_hash:
                return {
                    "valid":           False,
                    "records_checked": records_checked,
                    "first_bad_seq":   seq,
                    "error":           (
                        f"Chain break at seq={seq}: "
                        f"previous_hash in record does not match "
                        f"current_hash of predecessor.\n"
                        f"  Expected: {expected_previous_hash}\n"
                        f"  Found:    {previous_hash}"
                    ),
                }

            # ── current_hash recomputation check ────────────────────────────
            recomputed = _compute_hash(seq, timestamp_utc, event_type,
                                       payload, previous_hash)
            if recomputed != stored_hash:
                return {
                    "valid":           False,
                    "records_checked": records_checked,
                    "first_bad_seq":   seq,
                    "error":           (
                        f"Hash mismatch at seq={seq}: stored current_hash "
                        f"does not match re-computed value.  The record "
                        f"content has been altered.\n"
                        f"  Stored:      {stored_hash}\n"
                        f"  Recomputed:  {recomputed}"
                    ),
                }

            # ── Advance state ────────────────────────────────────────────────
            expected_previous_hash = stored_hash
            expected_seq           = seq + 1
            records_checked       += 1

    return {
        "valid":           True,
        "records_checked": records_checked,
        "first_bad_seq":   None,
        "error":           None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI helper (python -m app.core.audit_log verify <path>)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "verify":
        path = sys.argv[2]
        result = verify_chain(path)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["valid"] else 1)
    else:
        print("Usage: python audit_log.py verify <path-to-log.ndjson>")
        sys.exit(1)

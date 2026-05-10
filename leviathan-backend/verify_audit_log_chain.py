#!/usr/bin/env python3
"""
verify_audit_log_chain.py
=========================
Standalone script for verifying the integrity of a Leviathan audit log.

Usage
-----
    python verify_audit_log_chain.py                          # default: logs/audit.ndjson
    python verify_audit_log_chain.py logs/audit.ndjson        # explicit path
    python verify_audit_log_chain.py --json logs/audit.ndjson # machine-readable JSON output

Exit codes
----------
    0 — chain is valid (all records passed)
    1 — chain is invalid (tamper detected) or file not found

This script is self-contained and uses only the Python standard library.
It does NOT import from the Leviathan application package, so it can be
run on a copy of the log file on any machine with Python 3.8+.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────────────────────
# Constants (must match audit_log.py exactly)
# ─────────────────────────────────────────────────────────────────────────────
GENESIS_HASH = "0" * 64


# ─────────────────────────────────────────────────────────────────────────────
# Hash helpers (duplicated intentionally — no app package dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _canonical(seq, timestamp_utc, event_type, payload, previous_hash):
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


def _recompute_hash(seq, timestamp_utc, event_type, payload, previous_hash):
    text = _canonical(seq, timestamp_utc, event_type, payload, previous_hash)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Core verification logic
# ─────────────────────────────────────────────────────────────────────────────

def verify_chain(log_path):
    """
    Walk the NDJSON log and perform three checks on every record:
      1. seq is a monotone integer with no gaps or duplicates.
      2. previous_hash matches the current_hash of the preceding record
         (or GENESIS_HASH for the first record).
      3. current_hash matches the SHA-256 recomputed from the record fields.

    Returns a dict with:
        valid            bool
        records_checked  int
        first_bad_seq    int | None
        error            str | None
        event_type_counts  dict[str, int]   -- frequency of each event type
        log_path         str
        checked_at_utc   str
    """
    result = {
        "log_path":          log_path,
        "checked_at_utc":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "valid":             False,
        "records_checked":   0,
        "first_bad_seq":     None,
        "error":             None,
        "event_type_counts": {},
    }

    if not os.path.exists(log_path):
        result["error"] = f"Log file not found: {log_path!r}"
        return result

    file_size_bytes = os.path.getsize(log_path)
    result["file_size_bytes"] = file_size_bytes

    expected_previous_hash = GENESIS_HASH
    expected_seq           = 0
    event_counts           = {}

    with open(log_path, "r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue

            # ── 1. Parse JSON ─────────────────────────────────────────────
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                result["error"] = f"JSON parse error on line {lineno}: {exc}"
                return result

            # ── 2. Required fields present? ───────────────────────────────
            required = ("seq", "timestamp_utc", "event_type",
                        "payload", "previous_hash", "current_hash")
            for field in required:
                if field not in record:
                    result["first_bad_seq"] = record.get("seq")
                    result["error"] = (
                        f"Missing required field '{field}' on line {lineno}."
                    )
                    return result

            seq           = record["seq"]
            timestamp_utc = record["timestamp_utc"]
            event_type    = record["event_type"]
            payload       = record["payload"]
            previous_hash = record["previous_hash"]
            stored_hash   = record["current_hash"]

            # ── 3. Sequence-number continuity ─────────────────────────────
            if seq != expected_seq:
                result["first_bad_seq"] = seq
                result["error"] = (
                    f"Sequence discontinuity on line {lineno}: "
                    f"expected seq={expected_seq}, found seq={seq}. "
                    f"A record may have been inserted or deleted."
                )
                return result

            # ── 4. previous_hash linkage ──────────────────────────────────
            if previous_hash != expected_previous_hash:
                result["first_bad_seq"] = seq
                result["error"] = (
                    f"Chain break at seq={seq} (line {lineno}):\n"
                    f"  previous_hash stored in record:\n"
                    f"    {previous_hash}\n"
                    f"  expected (current_hash of predecessor):\n"
                    f"    {expected_previous_hash}\n"
                    f"A record may have been modified or a record was\n"
                    f"inserted before this one."
                )
                return result

            # ── 5. current_hash integrity ─────────────────────────────────
            recomputed = _recompute_hash(
                seq, timestamp_utc, event_type, payload, previous_hash
            )
            if recomputed != stored_hash:
                result["first_bad_seq"] = seq
                result["error"] = (
                    f"Hash mismatch at seq={seq} (line {lineno}):\n"
                    f"  Stored current_hash:\n"
                    f"    {stored_hash}\n"
                    f"  Re-computed current_hash:\n"
                    f"    {recomputed}\n"
                    f"The record content (seq, timestamp, event_type,\n"
                    f"payload, or previous_hash) has been altered."
                )
                return result

            # ── Advance state ─────────────────────────────────────────────
            expected_previous_hash = stored_hash
            expected_seq           = seq + 1
            result["records_checked"] += 1
            event_counts[event_type]  = event_counts.get(event_type, 0) + 1

    result["valid"]             = True
    result["event_type_counts"] = event_counts
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CLI rendering
# ─────────────────────────────────────────────────────────────────────────────

_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"


def _coloured(text, colour):
    """Only apply ANSI colour codes when writing to a terminal."""
    if sys.stdout.isatty():
        return f"{colour}{text}{_RESET}"
    return text


def _print_report(result):
    width = 62
    print()
    print(_coloured("=" * width, _BOLD))
    print(_coloured("  Leviathan Audit Log — Chain Verification Report", _BOLD))
    print(_coloured("=" * width, _BOLD))
    print(f"  Log file  : {result['log_path']}")
    print(f"  File size : {result.get('file_size_bytes', 'N/A')} bytes")
    print(f"  Checked   : {result['checked_at_utc']}")
    print(f"  Records   : {result['records_checked']}")
    print()

    if result["valid"]:
        print(_coloured("  ✅  CHAIN VALID — no tampering detected", _GREEN))
    else:
        print(_coloured("  ❌  CHAIN INVALID — tampering detected", _RED))
        bad = result.get("first_bad_seq")
        if bad is not None:
            print(_coloured(f"  First bad record: seq={bad}", _RED))
        if result.get("error"):
            print()
            print(_coloured("  Error detail:", _YELLOW))
            for line in result["error"].splitlines():
                print(f"    {line}")

    counts = result.get("event_type_counts")
    if counts:
        print()
        print("  Event type breakdown:")
        for evt, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"    {evt:<35} {cnt:>5}")

    print(_coloured("=" * width, _BOLD))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]

    if args:
        log_path = args[0]
    else:
        # default: relative to this script's directory
        here     = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(here, "logs", "audit.ndjson")

    result = verify_chain(log_path)

    if json_mode:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result)

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Leviathan Metrics Report (NO Ground Truth required)

Generates:
- Pipeline latency metrics (created->completed)
- Live alerts distribution (type/severity/time span/coords coverage)
- Vessel logs summary (counts/status distribution)
- Optional processed CSV stats (rows, unique MMSI, time span, throughput, missingness)
- Report-ready Markdown snippet

Usage (API only):
  python scripts/metrics_report.py --job-id <JOB_ID>

Usage (API + processed CSV stats):
  python scripts/metrics_report.py --job-id <JOB_ID> --processed-csv data/processed/<file>.csv

Optional:
  --api-base http://127.0.0.1:8000/api
  --limit-alerts 5000
  --out-json metrics_<JOB_ID>.json
  --out-md metrics_<JOB_ID>.md
"""

import argparse
import json
import os
import sys
from datetime import datetime
from collections import Counter, defaultdict

# Optional heavy deps
try:
    import pandas as pd
except Exception:
    pd = None

try:
    import requests
except Exception:
    requests = None


# -----------------------------
# Helpers
# -----------------------------
def parse_iso(ts: str):
    if not ts:
        return None
    try:
        # support "2026-01-29T21:26:42.769152" and "2022-11-09T23:59:59"
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def pct(num, den):
    if den == 0:
        return 0.0
    return round((num / den) * 100.0, 2)


def weighted_severity(sev: str) -> int:
    s = (sev or "").lower()
    if s == "high":
        return 3
    if s == "medium":
        return 2
    return 1  # low/default


def get_json(url: str, timeout=20):
    if requests is None:
        raise RuntimeError("requests is not installed. Install it or run in backend venv.")
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def summarize_numeric(series, name):
    # series may contain strings; coerce
    try:
        s = pd.to_numeric(series, errors="coerce")
        s = s.dropna()
        if len(s) == 0:
            return {"name": name, "count": 0}
        return {
            "name": name,
            "count": int(len(s)),
            "min": float(s.min()),
            "p50": float(s.quantile(0.5)),
            "p90": float(s.quantile(0.9)),
            "p99": float(s.quantile(0.99)),
            "max": float(s.max()),
            "mean": float(s.mean()),
        }
    except Exception:
        return {"name": name, "count": 0}


# -----------------------------
# Core report generation
# -----------------------------
def build_report(job_id: str, api_base: str, limit_alerts: int, processed_csv: str = None):
    base = api_base.rstrip("/")

    # ---- Job status ----
    job_status = get_json(f"{base}/jobs/{job_id}")

    created_at = parse_iso(job_status.get("created_at"))
    completed_at = parse_iso(job_status.get("completed_at"))
    latency_s = None
    if created_at and completed_at:
        latency_s = (completed_at - created_at).total_seconds()

    # ---- Anomaly reports ----
    anomaly_reports = get_json(f"{base}/jobs/{job_id}/anomaly-reports")

    # ---- Live alerts ----
    # Always pull severity=all to understand what detector produced.
    live_alerts = get_json(f"{base}/jobs/{job_id}/live-alerts?severity=all&limit={limit_alerts}")

    # ---- Vessel logs ----
    vessel_logs = get_json(f"{base}/jobs/{job_id}/vessel-logs?limit=10000")

    # -----------------------------
    # Live alerts summary
    # -----------------------------
    total_alerts = len(live_alerts) if isinstance(live_alerts, list) else 0

    by_type = Counter()
    by_sev = Counter()
    by_type_sev = Counter()
    with_coords = 0

    t_min = None
    t_max = None
    sev_weighted_volume = 0

    top_mmsi = Counter()

    for a in (live_alerts or []):
        t = (a.get("type") or "unknown").lower()
        s = (a.get("severity") or "low").lower()

        by_type[t] += 1
        by_sev[s] += 1
        by_type_sev[(t, s)] += 1
        sev_weighted_volume += weighted_severity(s)

        m = a.get("mmsi")
        if m is not None:
            top_mmsi[str(m)] += 1

        lat = a.get("lat")
        lon = a.get("lon")
        if lat is not None and lon is not None:
            with_coords += 1

        ts = parse_iso(a.get("timestamp"))
        if ts:
            if t_min is None or ts < t_min:
                t_min = ts
            if t_max is None or ts > t_max:
                t_max = ts

    by_type_sev_top = [
        {"type": k[0], "severity": k[1], "count": v}
        for k, v in by_type_sev.most_common(10)
    ]

    # -----------------------------
    # Vessel logs summary
    # -----------------------------
    vessel_logs_count = len(vessel_logs) if isinstance(vessel_logs, list) else 0
    vessel_status = Counter()
    spoofing_flag_ct = 0
    loitering_flag_ct = 0
    vessel_missing_coords = 0

    for v in (vessel_logs or []):
        st = (v.get("status") or "unknown").lower()
        vessel_status[st] += 1

        if bool(v.get("spoofing_flag")):
            spoofing_flag_ct += 1
        if bool(v.get("loitering_flag")):
            loitering_flag_ct += 1

        if v.get("lat") is None or v.get("lon") is None:
            vessel_missing_coords += 1

    # -----------------------------
    # Optional: processed CSV metrics
    # -----------------------------
    csv_metrics = {"enabled": False}
    if processed_csv:
        if pd is None:
            csv_metrics = {"enabled": True, "error": "pandas not installed in this environment."}
        elif not os.path.exists(processed_csv):
            csv_metrics = {"enabled": True, "error": f"processed_csv not found: {processed_csv}"}
        else:
            df = pd.read_csv(processed_csv, low_memory=False)
            csv_metrics["enabled"] = True
            csv_metrics["path"] = processed_csv
            csv_metrics["rows"] = int(len(df))
            csv_metrics["cols"] = int(len(df.columns))

            mmsi_col = pick_col(df, ["mmsi", "MMSI"])
            ts_col = pick_col(df, ["timestamp", "time", "base_datetime", "BaseDateTime"])
            lat_col = pick_col(df, ["lat", "LAT", "latitude", "Latitude"])
            lon_col = pick_col(df, ["lon", "LON", "longitude", "Longitude"])
            sog_col = pick_col(df, ["sog", "SOG", "speed", "Speed"])

            if mmsi_col:
                csv_metrics["unique_mmsi"] = int(df[mmsi_col].nunique(dropna=True))
            else:
                csv_metrics["unique_mmsi"] = None

            # time span + throughput
            duration_s = None
            t0 = None
            t1 = None
            if ts_col:
                ts_parsed = pd.to_datetime(df[ts_col], errors="coerce", utc=False)
                ts_parsed = ts_parsed.dropna()
                if len(ts_parsed) > 0:
                    t0 = ts_parsed.min()
                    t1 = ts_parsed.max()
                    duration_s = (t1 - t0).total_seconds() if t1 is not None else None

            csv_metrics["time_min"] = str(t0) if t0 is not None else None
            csv_metrics["time_max"] = str(t1) if t1 is not None else None
            csv_metrics["duration_seconds"] = float(duration_s) if duration_s else None

            if duration_s and duration_s > 0:
                csv_metrics["ingested_points_per_second"] = round(len(df) / duration_s, 2)
            else:
                csv_metrics["ingested_points_per_second"] = None

            # missing coords %
            missing_coords = None
            if lat_col and lon_col:
                missing_coords = int(((df[lat_col].isna()) | (df[lon_col].isna())).sum())
            csv_metrics["missing_coords_rows"] = missing_coords
            csv_metrics["missing_coords_pct"] = pct(missing_coords or 0, len(df)) if len(df) else 0.0

            # speed stats
            if sog_col:
                csv_metrics["speed_stats"] = summarize_numeric(df[sog_col], "speed/sog")
            else:
                csv_metrics["speed_stats"] = {"name": "speed/sog", "count": 0}

            # alerts density (alerts per 1M points)
            if len(df) > 0:
                csv_metrics["alerts_per_million_points"] = round((total_alerts / len(df)) * 1_000_000, 2)
            else:
                csv_metrics["alerts_per_million_points"] = None

            # vessel-level alert density
            uniq = csv_metrics.get("unique_mmsi") or 0
            if uniq > 0:
                csv_metrics["alerts_per_100_vessels"] = round((total_alerts / uniq) * 100, 2)
            else:
                csv_metrics["alerts_per_100_vessels"] = None

    # -----------------------------
    # Report JSON (final)
    # -----------------------------
    report = {
        "job_id": job_id,
        "job_status_keys": sorted(list(job_status.keys())),
        "job_created_at": job_status.get("created_at"),
        "job_completed_at": job_status.get("completed_at"),
        "job_latency_seconds": latency_s,
        "anomaly_reports_api": anomaly_reports,
        "live_alerts_summary": {
            "total": total_alerts,
            "with_coords": with_coords,
            "coords_coverage_pct": pct(with_coords, total_alerts),
            "time_min": t_min.isoformat() if t_min else None,
            "time_max": t_max.isoformat() if t_max else None,
            "by_type": dict(by_type),
            "by_severity": dict(by_sev),
            "by_type_severity_top": by_type_sev_top,
            "severity_weighted_volume": sev_weighted_volume,
            "top_mmsi_by_alerts": [{"mmsi": k, "alerts": v} for k, v in top_mmsi.most_common(10)],
        },
        "vessel_logs_summary": {
            "count": vessel_logs_count,
            "by_status": dict(vessel_status),
            "spoofing_flagged_vessels": spoofing_flag_ct,
            "loitering_flagged_vessels": loitering_flag_ct,
            "missing_coords_vessels": vessel_missing_coords,
            "missing_coords_pct": pct(vessel_missing_coords, vessel_logs_count),
        },
        "processed_csv_metrics": csv_metrics,
        "notes": [
            "This report is operational (no ground truth). For Precision/Recall/F1, run on injected/labeled data later.",
            "If live alerts look 'all low severity', it usually means real AIS is dominated by small inconsistencies; high severity is rarer.",
            "Use multiple days (CSV files) to compute mean±std for a paper-grade evaluation."
        ],
    }

    # -----------------------------
    # Report-ready Markdown snippet
    # -----------------------------
    md_lines = []
    md_lines.append("## Performance Metrics (Operational Evaluation – No Ground Truth)")
    md_lines.append("")
    md_lines.append(f"**Job ID:** `{job_id}`")
    md_lines.append("")
    if latency_s is not None:
        md_lines.append(f"- **End-to-end pipeline latency:** **{round(latency_s, 2)} s** (created → completed)")
    else:
        md_lines.append("- **End-to-end pipeline latency:** unavailable (missing created_at/completed_at)")
    md_lines.append("")
    md_lines.append("### Anomaly Output Volume")
    md_lines.append(f"- **Total anomalies (API /anomaly-reports):** {anomaly_reports.get('total')}")
    md_lines.append(f"- **Spoofing:** {anomaly_reports.get('spoofing')}")
    md_lines.append(f"- **Loitering:** {anomaly_reports.get('loitering')}")
    md_lines.append("")
    md_lines.append("### Live Alerts Quality & Coverage")
    md_lines.append(f"- **Live alerts sampled:** {total_alerts} (limit applied for reporting)")
    md_lines.append(f"- **Coordinate coverage:** {with_coords}/{total_alerts} (**{pct(with_coords, total_alerts)}%**)")
    if t_min and t_max:
        md_lines.append(f"- **Alert time span:** {t_min.isoformat()} → {t_max.isoformat()}")
    if by_type:
        md_lines.append(f"- **Alerts by type:** {dict(by_type)}")
    if by_sev:
        md_lines.append(f"- **Alerts by severity:** {dict(by_sev)}")
    md_lines.append(f"- **Severity-weighted volume (low=1, med=2, high=3):** {sev_weighted_volume}")
    md_lines.append("")
    md_lines.append("### Vessel Coverage")
    md_lines.append(f"- **Vessels in vessel-logs:** {vessel_logs_count}")
    if vessel_status:
        md_lines.append(f"- **Vessel status distribution:** {dict(vessel_status)}")
    md_lines.append(f"- **Vessels flagged spoofing:** {spoofing_flag_ct}")
    md_lines.append(f"- **Vessels flagged loitering:** {loitering_flag_ct}")
    md_lines.append("")
    if processed_csv and csv_metrics.get("enabled") and not csv_metrics.get("error"):
        md_lines.append("### Data Throughput (Processed AIS File)")
        md_lines.append(f"- **Processed rows:** {csv_metrics.get('rows')}")
        md_lines.append(f"- **Unique vessels (MMSI):** {csv_metrics.get('unique_mmsi')}")
        md_lines.append(f"- **Duration covered:** {csv_metrics.get('duration_seconds')} s")
        md_lines.append(f"- **Ingestion rate:** {csv_metrics.get('ingested_points_per_second')} points/s")
        md_lines.append(f"- **Missing coordinates:** {csv_metrics.get('missing_coords_pct')}% of rows")
        md_lines.append(f"- **Alerts per million points:** {csv_metrics.get('alerts_per_million_points')}")
        md_lines.append("")
    md_lines.append("**Note:** This evaluation reports operational performance and anomaly output characteristics on real AIS. Ground-truth accuracy (Precision/Recall/F1) will be computed later using injected/labeled datasets.")

    report_md = "\n".join(md_lines)
    return report, report_md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True, help="Leviathan job id")
    ap.add_argument("--api-base", default="http://127.0.0.1:8000/api", help="API base URL")
    ap.add_argument("--limit-alerts", type=int, default=5000, help="Max alerts pulled from API for summary")
    ap.add_argument("--processed-csv", default=None, help="Optional path to processed cleaned CSV for throughput stats")
    ap.add_argument("--out-json", default=None, help="Write JSON report to file")
    ap.add_argument("--out-md", default=None, help="Write Markdown snippet to file")
    args = ap.parse_args()

    try:
        report, report_md = build_report(
            job_id=args.job_id,
            api_base=args.api_base,
            limit_alerts=args.limit_alerts,
            processed_csv=args.processed_csv,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n================ Leviathan Metrics Report ================\n")
    print(json.dumps(report, indent=2))
    print("\n=========================================================\n")
    print("Report-ready Markdown (paste into your report):\n")
    print(report_md)
    print("\n")

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Wrote JSON: {args.out_json}")

    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"Wrote Markdown: {args.out_md}")


if __name__ == "__main__":
    main()

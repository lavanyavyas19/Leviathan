import sys
import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import glob
import pandas as pd

from app.core.preprocessing import clean_and_preprocess
from app.core.anomaly_detection import detect_loitering_events

INPUT_DIR = "data/raw_days"
OUTPUT_DIR = "data/batch_results"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "loitering_15day_results.csv")
OUTPUT_SUMMARY = os.path.join(OUTPUT_DIR, "loitering_15day_summary.csv")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_files = sorted(glob.glob(os.path.join(INPUT_DIR, "AIS_2022_01_*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {INPUT_DIR}")

    all_events = []
    summary_rows = []

    print(f"Found {len(csv_files)} files")

    for file_path in csv_files:
        day_name = os.path.basename(file_path)
        print(f"\nProcessing: {day_name}")

        try:
            df = pd.read_csv(file_path, low_memory=False)
            raw_rows = len(df)

            df = clean_and_preprocess(df)
            clean_rows = len(df)

            events_df = detect_loitering_events(df)

            if events_df is None or events_df.empty:
                detected_count = 0
                events_df = pd.DataFrame(columns=[
                    "mmsi", "lat", "lon", "timestamp", "start_ts", "end_ts",
                    "cluster_size", "severity", "type", "avg_speed", "dwell_time_hr"
                ])
            else:
                detected_count = len(events_df)
                events_df = events_df.copy()
                events_df["source_file"] = day_name

            all_events.append(events_df)

            summary_rows.append({
                "source_file": day_name,
                "raw_rows": raw_rows,
                "clean_rows": clean_rows,
                "loitering_events": detected_count
            })

            print(f"  Raw rows: {raw_rows}")
            print(f"  Clean rows: {clean_rows}")
            print(f"  Loitering events: {detected_count}")

        except Exception as e:
            print(f"  ERROR in {day_name}: {e}")
            summary_rows.append({
                "source_file": day_name,
                "raw_rows": None,
                "clean_rows": None,
                "loitering_events": None,
                "error": str(e)
            })

    combined_events = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    summary_df = pd.DataFrame(summary_rows)

    if not combined_events.empty:
        combined_events = combined_events.sort_values(
            by=["dwell_time_hr", "cluster_size"],
            ascending=[False, False]
        )

    combined_events.to_csv(OUTPUT_CSV, index=False)
    summary_df.to_csv(OUTPUT_SUMMARY, index=False)

    print("\nDone.")
    print(f"Saved combined events to: {OUTPUT_CSV}")
    print(f"Saved summary to: {OUTPUT_SUMMARY}")

    if not combined_events.empty:
        print("\nTop 10 detected events:")
        print(combined_events.head(10))


if __name__ == "__main__":
    main()
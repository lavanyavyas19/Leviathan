import numpy as np
import pandas as pd


def haversine_nm_vec(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1.astype(float))
    lon1 = np.radians(lon1.astype(float))
    lat2 = np.radians(lat2.astype(float))
    lon2 = np.radians(lon2.astype(float))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    c = 2*np.arcsin(np.sqrt(a))

    km = 6371.0088 * c
    return km * 0.539957  # nautical miles


def circular_heading_change(series: pd.Series) -> pd.Series:
    diff = series.diff().abs()
    diff = np.minimum(diff, 360 - diff)
    return diff.fillna(0)


def add_spoofing_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # required raw cols
    for c in ["mmsi", "lat", "lon", "sog", "cog", "timestamp"]:
        if c not in df.columns:
            raise ValueError(f"Missing required column for features: {c}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["mmsi", "timestamp"]).copy()

    # numeric
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["sog"] = pd.to_numeric(df["sog"], errors="coerce")
    df["cog"] = pd.to_numeric(df["cog"], errors="coerce")

    df = df.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)

    # speed
    df["speed"] = df["sog"].clip(0, 60).fillna(0)

    # heading change
    df["heading_change"] = (
        df.groupby("mmsi")["cog"]
          .apply(circular_heading_change)
          .reset_index(level=0, drop=True)
          .fillna(0)
    )

    # jump distance
    lat_prev = df.groupby("mmsi")["lat"].shift(1)
    lon_prev = df.groupby("mmsi")["lon"].shift(1)

    df["jump_distance"] = haversine_nm_vec(
        df["lat"].fillna(0), df["lon"].fillna(0),
        lat_prev.fillna(0), lon_prev.fillna(0),
    ).replace([np.inf, -np.inf], 0).fillna(0)

    # time gap
    df["time_gap"] = (
        df.groupby("mmsi")["timestamp"]
          .diff()
          .dt.total_seconds()
          .replace([np.inf, -np.inf], 0)
          .fillna(0)
    )

    # speed change
    df["speed_change"] = df.groupby("mmsi")["speed"].diff().abs().fillna(0)

    # acceleration + turn_rate (avoid divide-by-zero noise)
    safe_gap = df["time_gap"].where(df["time_gap"] >= 30, np.nan)
    df["acceleration"] = (df["speed_change"] / safe_gap).replace([np.inf, -np.inf], 0).fillna(0)
    df["turn_rate"] = (df["heading_change"] / safe_gap).replace([np.inf, -np.inf], 0).fillna(0)

    return df

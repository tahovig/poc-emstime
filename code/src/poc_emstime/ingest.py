"""Load and regularize LBNL Open uPMU channel data.

Each LBNL channel file is a headerless, gzip-compressed CSV of
(timestamp_ns, value) pairs sampled at 120 Hz — confirmed against a real
downloaded file, see ../../../data/README.md. There is no single wide CSV;
per-channel files must be merged on timestamp.
"""

import pandas as pd

SAMPLE_INTERVAL_NS = 8_333_333  # 120 Hz, confirmed against real LBNL data


def load_channel(path: str, column_name: str) -> pd.Series:
    df = pd.read_csv(path, header=None, names=["timestamp_ns", column_name])
    index = pd.to_datetime(df["timestamp_ns"], unit="ns")
    return pd.Series(df[column_name].values, index=index, name=column_name)


def load_upmu_site(paths: dict[str, str]) -> pd.DataFrame:
    """paths: {column_name: file_path}. Outer-joins channels on timestamp."""
    channels = [load_channel(path, name) for name, path in paths.items()]
    return pd.concat(channels, axis=1, join="outer").sort_index()


def add_gap_features(df: pd.DataFrame) -> pd.DataFrame:
    """Time_Delta_ms = gap to the previous sample, from the raw (pre-reindex) index.

    Must run before regularize(): reindexing onto a synthetic regular grid
    would make every gap look uniform, erasing the exact signal that dropout
    and jitter faults leave behind.
    """
    df = df.copy()
    delta_ms = df.index.to_series().diff().dt.total_seconds().mul(1000)
    df["Time_Delta_ms"] = delta_ms.fillna(delta_ms.median())
    return df


def regularize(df: pd.DataFrame, freq_ns: int = SAMPLE_INTERVAL_NS, ffill_limit: int = 3) -> pd.DataFrame:
    """Reindex onto a regular freq_ns grid spanning the data, forward-filling short gaps only.

    Was_Filled marks rows that didn't land on a real sample (within half a
    tick, to tolerate jitter) — evidence of a gap that regularize() would
    otherwise silently paper over.
    """
    # A clock-step fault whose offset is a multiple of the sample interval can
    # shift a row onto an already-occupied timestamp; reindex requires a
    # unique index, so drop the duplicate rather than fail.
    df = df[~df.index.duplicated(keep="first")]
    grid = pd.date_range(df.index.min(), df.index.max(), freq=pd.Timedelta(freq_ns, unit="ns"))
    tolerance = pd.Timedelta(freq_ns // 2, unit="ns")
    out = df.reindex(grid, method="nearest", tolerance=tolerance)
    out["Was_Filled"] = out.drop(columns=[c for c in ("Time_Delta_ms",) if c in out.columns]).isna().any(axis=1)
    fill_cols = [c for c in out.columns if c != "Was_Filled"]
    out[fill_cols] = out[fill_cols].ffill(limit=ffill_limit)
    return out

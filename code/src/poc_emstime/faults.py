"""Synthetic timing-fault injection for labeled anomaly evaluation.

Each injector takes clean data plus a (start, end) window, applies one fault
type within that window, and returns (modified_df, fault_window) where
fault_window = (start, end, fault_type) — the ground-truth label consumed by
evaluate.py. All injectors are deterministic given a seed.
"""

import numpy as np
import pandas as pd

FaultWindow = tuple[pd.Timestamp, pd.Timestamp, str]


def inject_timestamp_jitter(df: pd.DataFrame, start, end, std_ms: float, seed: int = 0) -> tuple[pd.DataFrame, FaultWindow]:
    """Perturb sample timestamps within the window by random offsets. Values untouched —
    isolates whether irregular spacing alone (not a value spike) is detectable."""
    df = df.copy()
    mask = (df.index >= start) & (df.index <= end)
    rng = np.random.default_rng(seed)
    offsets_ns = rng.normal(0, std_ms * 1e6, size=mask.sum()).astype("int64")
    new_index = df.index.values.copy()
    new_index[mask] = new_index[mask] + offsets_ns
    df.index = pd.DatetimeIndex(new_index, name=df.index.name)
    return df, (pd.Timestamp(start), pd.Timestamp(end), "timestamp_jitter")


def inject_dropout(df: pd.DataFrame, start, end) -> tuple[pd.DataFrame, FaultWindow]:
    """Remove rows within the window entirely — a real gap, not NaN-in-place."""
    keep = ~((df.index >= start) & (df.index <= end))
    return df.loc[keep].copy(), (pd.Timestamp(start), pd.Timestamp(end), "dropout")


def inject_clock_step(df: pd.DataFrame, start, end, offset_ms: float) -> tuple[pd.DataFrame, FaultWindow]:
    """Shift timestamps within the window by a fixed offset — models a GPS
    reacquisition/holdover step, distinct from a value-only spike."""
    df = df.copy()
    mask = (df.index >= start) & (df.index <= end)
    offset_ns = int(offset_ms * 1e6)
    new_index = df.index.values.copy()
    new_index[mask] = new_index[mask] + offset_ns
    df.index = pd.DatetimeIndex(new_index, name=df.index.name)
    return df, (pd.Timestamp(start), pd.Timestamp(end), "clock_step")


def inject_tq_corruption(df: pd.DataFrame, tq_col: str, start, end, bad_value=1.0) -> tuple[pd.DataFrame, FaultWindow]:
    """Set a time-quality/status column to a 'bad lock' sentinel across the window."""
    df = df.copy()
    mask = (df.index >= start) & (df.index <= end)
    df.loc[mask, tq_col] = bad_value
    return df, (pd.Timestamp(start), pd.Timestamp(end), "tq_corruption")


_INJECTORS = {
    "timestamp_jitter": inject_timestamp_jitter,
    "dropout": inject_dropout,
    "clock_step": inject_clock_step,
    "tq_corruption": inject_tq_corruption,
}


def inject_faults(df: pd.DataFrame, spec: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply a sequence of fault specs, e.g. [{"type": "dropout", "start": ..., "end": ...}, ...].
    Returns (modified_df, labels_df) where labels_df has columns [start, end, fault_type]."""
    labels = []
    for item in spec:
        item = dict(item)
        fault_type = item.pop("type")
        df, window = _INJECTORS[fault_type](df, **item)
        labels.append(window)
    labels_df = pd.DataFrame(labels, columns=["start", "end", "fault_type"])
    return df.sort_index(), labels_df

"""Rolling-window feature engineering and phase-angle unwrapping.

Time_Delta_ms and Was_Filled come from ingest.py and are carried through
unchanged — they're already first-class features, not smoothed. TQ/status
columns are passed through as-is for the same reason: they're categorical
state, not something to average.
"""

import numpy as np
import pandas as pd


def add_delta_and_rolling(df: pd.DataFrame, col: str, window: int) -> pd.DataFrame:
    df = df.copy()
    rolling_mean = df[col].rolling(window).mean()
    df[f"{col}_Delta"] = df[col].diff().abs()
    df[f"{col}_Rolling_Mean"] = rolling_mean
    df[f"{col}_Rolling_Std"] = df[col].rolling(window).std()
    df[f"{col}_Dev_From_Mean"] = (df[col] - rolling_mean).abs()
    return df


def unwrap_phase(series: pd.Series, period: float = 2 * np.pi) -> pd.Series:
    """Unwrap a phase-angle series before differencing it. np.unwrap's default
    assumes radians (period=2*pi) — pass period=360 for degree-valued angle
    channels. Prevents a fake delta spike when a phase angle crosses its
    +/-180deg or 0/2pi wraparound boundary."""
    return pd.Series(np.unwrap(series.values, period=period), index=series.index, name=series.name)

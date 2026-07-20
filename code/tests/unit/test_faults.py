import pandas as pd

from poc_emstime.faults import (
    inject_clock_step,
    inject_dropout,
    inject_faults,
    inject_timestamp_jitter,
    inject_tq_corruption,
)


def _clean_df(n=20, interval_ms=8.333333):
    index = pd.date_range("2026-01-01", periods=n, freq=pd.Timedelta(milliseconds=interval_ms))
    return pd.DataFrame({"Value": range(n), "TQ": [0.0] * n}, index=index)


def test_inject_timestamp_jitter_changes_index_not_values():
    df = _clean_df()
    start, end = df.index[5], df.index[10]
    out, window = inject_timestamp_jitter(df, start, end, std_ms=1.0, seed=1)
    assert window[2] == "timestamp_jitter"
    assert (out["Value"].values == df["Value"].values).all()
    assert not (out.index[5:11] == df.index[5:11]).all()


def test_inject_dropout_removes_rows():
    df = _clean_df()
    start, end = df.index[5], df.index[10]
    out, window = inject_dropout(df, start, end)
    assert window[2] == "dropout"
    assert len(out) == len(df) - 6
    assert not any((out.index >= start) & (out.index <= end))


def test_inject_clock_step_shifts_timestamps_in_window_only():
    df = _clean_df()
    start, end = df.index[5], df.index[10]
    out, window = inject_clock_step(df, start, end, offset_ms=50.0)
    assert window[2] == "clock_step"
    shifted = out.index[5:11]
    original = df.index[5:11]
    assert ((shifted - original) == pd.Timedelta(milliseconds=50)).all()
    assert (out.index[:5] == df.index[:5]).all()


def test_inject_tq_corruption_sets_flag_in_window():
    df = _clean_df()
    start, end = df.index[5], df.index[10]
    out, window = inject_tq_corruption(df, "TQ", start, end, bad_value=9.0)
    assert window[2] == "tq_corruption"
    assert (out.loc[start:end, "TQ"] == 9.0).all()
    assert (out["TQ"].drop(out.loc[start:end].index) == 0.0).all()


def test_inject_faults_composes_multiple_and_returns_labels():
    df = _clean_df()
    spec = [
        {"type": "dropout", "start": df.index[2], "end": df.index[4]},
        {"type": "tq_corruption", "tq_col": "TQ", "start": df.index[10], "end": df.index[12], "bad_value": 5.0},
    ]
    out, labels = inject_faults(df, spec)
    assert list(labels["fault_type"]) == ["dropout", "tq_corruption"]
    assert len(out) == len(df) - 3
    assert (out.loc[df.index[10]:df.index[12], "TQ"] == 5.0).all()

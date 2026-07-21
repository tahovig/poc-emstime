import numpy as np
import pandas as pd

from poc_emstime.app.downsample import decimate_for_chart


def _make_index(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq=pd.Timedelta(8_333_333, unit="ns"))


def _epoch_ms(index: pd.DatetimeIndex) -> np.ndarray:
    return index.astype("int64").to_numpy() // 1_000_000


EMPTY_LABELS = pd.DataFrame(columns=["start", "end", "fault_type"])


def test_small_dataset_is_not_decimated_at_all():
    n = 50
    index = _make_index(n)
    values = np.arange(n, dtype=float)
    y_pred = np.zeros(n, dtype=bool)

    chart = decimate_for_chart(index, values, y_pred, EMPTY_LABELS, max_buckets=2000)

    assert chart["n_rows_full"] == n
    assert len(chart["timestamps"]) == n


def test_large_dataset_is_bounded_in_size():
    n = 200_000
    index = _make_index(n)
    rng = np.random.default_rng(0)
    values = rng.normal(size=n)
    y_pred = np.zeros(n, dtype=bool)

    chart = decimate_for_chart(index, values, y_pred, EMPTY_LABELS, max_buckets=500)

    assert chart["n_rows_full"] == n
    assert len(chart["timestamps"]) <= 500 * 2
    assert len(chart["timestamps"]) < n


def test_anomalous_rows_always_survive_regardless_of_bucket_position():
    n = 10_000
    index = _make_index(n)
    values = np.zeros(n)  # flat signal -- every bucket's min/max pick is arbitrary/tied
    y_pred = np.zeros(n, dtype=bool)
    anomaly_positions = [17, 4234, 9999]
    for pos in anomaly_positions:
        y_pred[pos] = True

    chart = decimate_for_chart(index, values, y_pred, EMPTY_LABELS, max_buckets=50)

    kept_ms = set(chart["timestamps"])
    expected_ms = set(_epoch_ms(index)[anomaly_positions].tolist())
    assert expected_ms <= kept_ms
    assert sum(chart["anomaly"]) == len(anomaly_positions)
    assert chart["n_anomalies_full"] == len(anomaly_positions)


def test_a_real_spike_is_not_erased_by_min_max_bucketing():
    n = 100_000
    index = _make_index(n)
    values = np.zeros(n)
    values[55_555] = 1000.0
    y_pred = np.zeros(n, dtype=bool)  # unflagged -- testing the bucketing itself, not the anomaly override

    chart = decimate_for_chart(index, values, y_pred, EMPTY_LABELS, max_buckets=200)

    assert max(chart["values"]) == 1000.0


def test_fault_windows_pass_through_as_epoch_ms():
    n = 100
    index = _make_index(n)
    values = np.zeros(n)
    y_pred = np.zeros(n, dtype=bool)
    labels = pd.DataFrame([{"start": index[10], "end": index[13], "fault_type": "dropout"}])

    chart = decimate_for_chart(index, values, y_pred, labels, max_buckets=2000)

    assert len(chart["fault_windows"]) == 1
    window = chart["fault_windows"][0]
    assert window["fault_type"] == "dropout"
    assert window["start_ms"] < window["end_ms"]

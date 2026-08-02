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


def test_dense_anomaly_cluster_does_not_blow_up_payload_size():
    # Regression test for the README "Scaling" caveat: at contamination=0.01
    # on 10.37M real rows, ~103,680 flagged rows were all force-included,
    # making payload size scale with contamination x row count instead of
    # max_buckets. Here, half of a 100k-row dataset is flagged (a much more
    # extreme case) -- the payload must still stay bounded near max_buckets,
    # not near n/2.
    n = 100_000
    index = _make_index(n)
    values = np.zeros(n)
    y_pred = np.zeros(n, dtype=bool)
    y_pred[: n // 2] = True  # the entire first half of the run is "flagged"

    chart = decimate_for_chart(index, values, y_pred, EMPTY_LABELS, max_buckets=500)

    assert chart["n_anomalies_full"] == n // 2
    # Bounded near max_buckets (min + max + at most one anomaly per bucket),
    # not anywhere near the 50,000 flagged rows.
    assert len(chart["timestamps"]) <= 500 * 3
    assert sum(chart["anomaly"]) < 1000


def test_every_anomaly_containing_bucket_still_shows_an_anomaly():
    n = 10_000
    index = _make_index(n)
    values = np.zeros(n)
    y_pred = np.zeros(n, dtype=bool)
    # Two dense anomaly clusters landing in two different buckets (bucket
    # size is 10_000 / 50 = 200), rather than one flagged row each.
    y_pred[100:150] = True
    y_pred[5000:5050] = True

    chart = decimate_for_chart(index, values, y_pred, EMPTY_LABELS, max_buckets=50)

    kept_ms = np.array(chart["timestamps"])
    anomaly_ms = kept_ms[np.array(chart["anomaly"])]
    epoch_ms = _epoch_ms(index)
    # At least one kept point falls inside each cluster's time range.
    assert ((anomaly_ms >= epoch_ms[100]) & (anomaly_ms <= epoch_ms[149])).any()
    assert ((anomaly_ms >= epoch_ms[5000]) & (anomaly_ms <= epoch_ms[5049])).any()


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

"""Server-side chart decimation.

This is the concrete mechanism behind "the UI must not sacrifice
performance": it runs once, in the worker thread, immediately after
scoring, while the full arrays are still in memory -- never recomputed
on-demand per API request, which would require reloading a 10M+-row
dataframe just to serve a chart.
"""

import numpy as np
import pandas as pd


def decimate_for_chart(
    index: pd.DatetimeIndex,
    values: np.ndarray,
    y_pred: np.ndarray,
    labels_df: pd.DataFrame,
    max_buckets: int = 2000,
) -> dict:
    n = len(index)
    epoch_ms = pd.DatetimeIndex(index).astype("int64").to_numpy() // 1_000_000
    y_pred = np.asarray(y_pred, dtype=bool)

    if n <= max_buckets:
        keep = np.ones(n, dtype=bool)
    else:
        keep = np.zeros(n, dtype=bool)
        bucket_edges = np.linspace(0, n, max_buckets + 1, dtype=int)
        for start, end in zip(bucket_edges[:-1], bucket_edges[1:]):
            if end <= start:
                continue
            bucket_values = values[start:end]
            keep[start + int(np.argmin(bucket_values))] = True
            keep[start + int(np.argmax(bucket_values))] = True

            # An anomaly-containing bucket must never be a decimation
            # casualty -- but forcing in *every* flagged row (the prior
            # behavior) makes payload size scale with contamination x row
            # count instead of max_buckets: at contamination=0.01 on a
            # 10.37M-row run, that alone was ~103,680 extra points (see
            # README "Scaling"). One representative flagged row per bucket
            # keeps every anomalous region visible while bounding total
            # size to O(max_buckets) regardless of how many rows within a
            # bucket are flagged.
            bucket_anomalies = np.nonzero(y_pred[start:end])[0]
            if len(bucket_anomalies) > 0:
                keep[start + int(bucket_anomalies[0])] = True

    kept_idx = np.nonzero(keep)[0]

    fault_windows = [
        {
            "start_ms": int(pd.Timestamp(row.start).value // 1_000_000),
            "end_ms": int(pd.Timestamp(row.end).value // 1_000_000),
            "fault_type": row.fault_type,
        }
        for row in labels_df.itertuples(index=False)
    ]

    return {
        "timestamps": epoch_ms[kept_idx].tolist(),
        "values": np.asarray(values)[kept_idx].tolist(),
        "anomaly": y_pred[kept_idx].tolist(),
        "fault_windows": fault_windows,
        "n_rows_full": n,
        "n_anomalies_full": int(y_pred.sum()),
    }

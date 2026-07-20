"""Score detected anomalies against synthetically injected ground truth."""

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support


def ground_truth_mask(index: pd.DatetimeIndex, labels_df: pd.DataFrame) -> np.ndarray:
    """True where a timestamp falls inside any injected fault window."""
    mask = np.zeros(len(index), dtype=bool)
    for _, row in labels_df.iterrows():
        mask |= (index >= row["start"]) & (index <= row["end"])
    return mask


def score(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def score_by_fault_type(index: pd.DatetimeIndex, labels_df: pd.DataFrame, y_pred: np.ndarray) -> dict:
    """Detection rate per fault type: fraction of each injected window's rows
    flagged as anomalous. Precision isn't attributable to a specific fault
    type (a false positive isn't "caused" by any one injected fault), so this
    reports recall-style coverage only."""
    results = {}
    for fault_type, group in labels_df.groupby("fault_type"):
        mask = ground_truth_mask(index, group)
        if mask.sum() == 0:
            continue
        results[fault_type] = float(y_pred[mask].mean())
    return results

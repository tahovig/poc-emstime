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


def window_level_recall(index: pd.DatetimeIndex, labels_df: pd.DataFrame, y_pred: np.ndarray) -> dict:
    """For each individually labeled window, was at least one row in it
    flagged? A boundary-transition fault (dropout, clock_step) can be
    correctly and precisely caught by a single flagged row while still
    scoring near-zero on score_by_fault_type's per-row average, if the
    window spans several rows and only the transition row is genuinely
    anomalous. This answers the coarser "was it caught at all" question
    that per-row averaging dilutes."""
    results = {}
    for fault_type, group in labels_df.groupby("fault_type"):
        mask = ground_truth_mask(index, group)
        if mask.sum() == 0:
            continue
        results[fault_type] = bool(y_pred[mask].any())
    return results

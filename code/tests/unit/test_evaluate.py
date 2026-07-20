import numpy as np
import pandas as pd
import pytest

from poc_emstime.evaluate import ground_truth_mask, score, score_by_fault_type


def test_score_matches_hand_computed_precision_recall_f1():
    # 2 TP, 1 FP, 1 FN, 1 TN
    y_true = np.array([True, True, True, False, False])
    y_pred = np.array([True, True, False, True, False])
    result = score(y_true, y_pred)

    assert result["precision"] == 2 / 3
    assert result["recall"] == 2 / 3
    assert result["f1"] == 2 / 3


def test_ground_truth_mask_covers_injected_windows():
    index = pd.date_range("2026-01-01", periods=10, freq="s")
    labels = pd.DataFrame(
        [{"start": index[2], "end": index[4], "fault_type": "dropout"}]
    )
    mask = ground_truth_mask(index, labels)

    assert mask.sum() == 3
    assert mask[2] and mask[3] and mask[4]
    assert not mask[0] and not mask[5]


def test_score_by_fault_type_reports_per_type_detection_rate():
    index = pd.date_range("2026-01-01", periods=10, freq="s")
    labels = pd.DataFrame([
        {"start": index[0], "end": index[1], "fault_type": "dropout"},
        {"start": index[5], "end": index[7], "fault_type": "jitter"},
    ])
    y_pred = np.array([True, True, False, False, False, True, False, False, False, False])

    result = score_by_fault_type(index, labels, y_pred)

    assert result["dropout"] == 1.0  # both dropout rows flagged
    assert result["jitter"] == pytest.approx(1 / 3)

import numpy as np
import pandas as pd
import pytest

from poc_emstime.evaluate import ground_truth_mask, score, score_by_fault_type, window_level_recall


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


def test_window_level_recall_credits_a_single_flagged_row_in_a_wide_window():
    index = pd.date_range("2026-01-01", periods=10, freq="s")
    labels = pd.DataFrame([
        {"start": index[0], "end": index[3], "fault_type": "clock_step"},  # 4-row window
        {"start": index[6], "end": index[8], "fault_type": "dropout"},  # 3-row window, never flagged
    ])
    # only 1 of 4 clock_step rows flagged -> low per-row rate, but the fault was caught
    y_pred = np.array([False, False, False, True, False, False, False, False, False, False])

    per_row = score_by_fault_type(index, labels, y_pred)
    window_level = window_level_recall(index, labels, y_pred)

    assert per_row["clock_step"] == pytest.approx(0.25)
    assert window_level["clock_step"] is True
    assert window_level["dropout"] is False

import os

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from poc_emstime.pipeline import run

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_pipeline_channel.csv")

pytestmark = pytest.mark.integration

EXPECTED_STAGES = [
    "loading_channels",
    "injecting_faults",
    "computing_gap_features",
    "regularizing",
    "engineering_features",
    "cleaning_rows",
    "fitting_and_scoring",
    "finalizing_metrics",
]


def test_progress_callback_fires_expected_stages_in_order():
    seen = []
    run({"MAG": FIXTURE}, target_col="MAG", progress_callback=seen.append)

    assert seen == EXPECTED_STAGES


def test_no_progress_callback_is_fine():
    results = run({"MAG": FIXTURE}, target_col="MAG")
    assert results["n_rows"] > 0


def test_param_overrides_reach_the_fitted_model():
    results = run(
        {"MAG": FIXTURE},
        target_col="MAG",
        contamination=0.2,
        n_estimators=17,
        random_state=7,
        max_samples=0.5,
    )

    iforest = results["model"].named_steps["iforest"]
    assert iforest.contamination == 0.2
    assert iforest.n_estimators == 17
    assert iforest.random_state == 7
    assert iforest.max_samples == 0.5


def test_new_return_keys_have_consistent_shapes():
    results = run({"MAG": FIXTURE}, target_col="MAG")
    n = results["n_rows"]

    assert isinstance(results["model"], Pipeline)
    assert isinstance(results["index"], pd.DatetimeIndex)
    assert len(results["index"]) == n

    assert isinstance(results["y_pred"], np.ndarray)
    assert results["y_pred"].dtype == bool
    assert len(results["y_pred"]) == n
    assert int(results["y_pred"].sum()) == results["n_flagged"]

    assert len(results["target_series"]) == n
    assert len(results["time_delta_ms"]) == n

    assert list(results["labels"].columns) == ["start", "end", "fault_type"]

    assert results["feature_cols"] == [
        "MAG",
        "MAG_Delta",
        "MAG_Rolling_Std",
        "MAG_Dev_From_Mean",
        "Time_Delta_ms",
        "TQ",
    ]

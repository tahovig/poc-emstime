import os

import pytest

from poc_emstime.pipeline import run

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_pipeline_channel.csv")

pytestmark = pytest.mark.integration


def test_pipeline_runs_end_to_end_and_produces_scored_metrics():
    results = run({"MAG": FIXTURE}, target_col="MAG")

    assert results["n_rows"] > 0
    assert results["n_flagged"] >= 0

    overall = results["overall"]
    assert set(overall.keys()) == {"precision", "recall", "f1"}
    for value in overall.values():
        assert 0.0 <= value <= 1.0

    by_type = results["by_fault_type"]
    assert set(by_type.keys()) <= {"dropout", "timestamp_jitter", "clock_step", "tq_corruption"}
    for value in by_type.values():
        assert 0.0 <= value <= 1.0

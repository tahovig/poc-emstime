import numpy as np

from poc_emstime.model import build_pipeline, detect_anomalies


def test_detect_anomalies_flags_obvious_outliers():
    rng = np.random.default_rng(0)
    normal = rng.normal(0, 1, size=(200, 2))
    outliers = rng.normal(20, 1, size=(5, 2))
    X = np.vstack([normal, outliers])

    pipeline = build_pipeline(contamination=0.02)
    flags = detect_anomalies(pipeline, X)

    assert flags.dtype == bool
    assert flags.shape == (205,)
    assert flags[-5:].all()  # the far-away outliers should be flagged
    assert not flags[:50].any()  # a clean early slice should not be

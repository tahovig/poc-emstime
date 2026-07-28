import numpy as np

from poc_emstime.model import build_pipeline, detect_anomalies, fit_pipeline, score_anomalies


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


def test_fit_pipeline_returns_the_same_fitted_pipeline():
    rng = np.random.default_rng(0)
    baseline = rng.normal(0, 1, size=(200, 2))
    pipeline = build_pipeline(contamination=0.01)

    fitted = fit_pipeline(pipeline, baseline)

    assert fitted is pipeline


def test_score_anomalies_against_a_fixed_baseline_does_not_force_a_flag_rate():
    # detect_anomalies's fit_predict recomputes its ~contamination% cutoff
    # fresh against *whatever data it's given* -- so a channel with zero real
    # anomalies still has ~contamination% of its own rows called anomalous,
    # every time. That's the whole-signature blind spot this fit/score split
    # exists to fix: the cutoff is calibrated once, against the baseline, and
    # then held fixed. Scoring a second, independent clean sample against
    # that fixed cutoff should flag close to the calibrated rate (occasional
    # false positives are expected and fine), not something forced to ~100%
    # the way the old per-channel design was.
    rng = np.random.default_rng(0)
    baseline = rng.normal(0, 1, size=(500, 2))
    pipeline = build_pipeline(contamination=0.01)
    fit_pipeline(pipeline, baseline)

    clean_test = rng.normal(0, 1, size=(200, 2))
    outlier_test = rng.normal(20, 1, size=(5, 2))

    clean_flags = score_anomalies(pipeline, clean_test)
    outlier_flags = score_anomalies(pipeline, outlier_test)

    assert clean_flags.dtype == bool
    assert clean_flags.mean() < 0.05  # near the calibrated 1% rate, not ~100%
    assert outlier_flags.all()

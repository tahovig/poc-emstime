"""Isolation Forest anomaly detector: scaler + model, no import-time side effects."""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_pipeline(
    contamination: float = 0.01,
    n_estimators: int = 100,
    random_state: int = 42,
    max_samples: float = 1.0,
) -> Pipeline:
    """max_samples defaults to the full dataset (sklearn's own default is only
    256 rows per tree). Confirmed empirically on real LBNL data: with 256,
    a synthetic fault spanning ~4 rows out of 487k has under a 1-in-500
    chance of appearing in any given tree's training subsample, so almost no
    tree ever splits around it — recall for two of four fault types was 0.0
    despite one of them (a corrupted TQ flag) being ~400 standard deviations
    from baseline. Raising max_samples to the full dataset fixed it. This
    does not scale to the full multi-day dataset (100 trees x millions of
    rows each) — a future phase should use stratified/weighted sampling
    instead of naively raising max_samples further."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("iforest", IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            max_samples=max_samples,
        )),
    ])


def detect_anomalies(pipeline: Pipeline, X) -> np.ndarray:
    """Fits and scores in one pass (no holdout — there's no labeled training
    set to hold one out from; injected ground truth is used only at
    evaluation time in evaluate.py, never for fitting). Returns a bool array,
    True where IsolationForest flags the row as anomalous."""
    raw = pipeline.fit_predict(X)
    return raw == -1

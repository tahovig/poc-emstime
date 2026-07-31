"""Drives the anomaly detector against real GESL signatures.

Deliberately not pipeline.run(): that function's contract is shaped around a
single fixed target/TQ column pair and synthetic fault injection, neither of
which fits GESL (real, whole-signature-level labels; a variable number of
PMUs and measurement columns per signature). Reuses the same building blocks
(ingest/features/model) independently per channel instead.

Convention: SignatureRef.columns lists the *tagged* measurement suffixes to
check (e.g. ("_f", "_vp_a")) for a real Timing signature. An empty columns
tuple means "no specific tag to check" -- used for negative-control
signatures, where every available non-status channel is checked instead,
since the question there is whether the detector false-positives on
anything, not on one named measurement.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.pipeline import Pipeline

from poc_emstime import evaluate, features, gesl_client, gesl_parse, ingest, model
from poc_emstime.gesl_manifest import (
    BASELINE_TRAIN_SIGIDS,
    NEGATIVE_CONTROL_SIGIDS,
    SignatureRef,
    TIMING_SIGNATURES,
)


@dataclass
class SignatureResult:
    sigid: int
    source: str
    description: str
    any_flagged: bool
    channel_flagged: dict[str, bool]
    n_channels_checked: int

    @property
    def fraction_flagged(self) -> float:
        """Fraction of checked channels flagged -- a graded alternative to
        any_flagged. any() saturates once enough channels are scanned (a
        well-calibrated ~1-2% per-channel rate is nearly certain to hit
        *somewhere* across hundreds of channels); this lets a caller apply
        its own threshold instead of collapsing straight to a single bit."""
        if not self.n_channels_checked:
            return 0.0
        return sum(self.channel_flagged.values()) / self.n_channels_checked


def _channel_suffixes(frame, pmu_prefix: str) -> list[str]:
    """Every non-status measurement suffix this PMU actually reports."""
    prefix_len = len(pmu_prefix)
    return sorted(
        col[prefix_len:]
        for col in frame.columns
        if col.startswith(pmu_prefix) and not col.endswith("_status")
    )


def _channel_features(series, freq_ns: int, window: int):
    """Engineers the same feature set _evaluate_channel always has: gap
    features -> regularize -> rolling stats -> clean up. Returns None if too
    little real data survived regularization to fit anything meaningful --
    not evidence of an anomaly, just an unusable channel. Shared by both the
    per-channel fit_predict path and the baseline-pooling path, so the two
    approaches are judged on identically engineered features."""
    col = series.name
    channel_df = series.to_frame(col)
    channel_df = ingest.add_gap_features(channel_df)
    channel_df = ingest.regularize(channel_df, freq_ns=freq_ns)
    channel_df = features.add_delta_and_rolling(channel_df, col, window)

    rolling_cols = [f"{col}_Delta", f"{col}_Rolling_Std", f"{col}_Dev_From_Mean"]
    channel_df[rolling_cols] = channel_df[rolling_cols].fillna(0.0)
    channel_df = channel_df.dropna(subset=[col, "Time_Delta_ms"])

    if len(channel_df) < 2:
        return None
    return channel_df


def _feature_cols(col: str) -> list[str]:
    return [col, f"{col}_Delta", f"{col}_Rolling_Std", f"{col}_Dev_From_Mean", "Time_Delta_ms"]


def _evaluate_channel(series, freq_ns: int, window: int, contamination: float) -> bool:
    col = series.name
    channel_df = _channel_features(series, freq_ns, window)
    if channel_df is None:
        return False

    pipeline = model.build_pipeline(contamination=contamination)
    y_pred = model.detect_anomalies(pipeline, channel_df[_feature_cols(col)].values)
    return evaluate.signature_level_recall(y_pred)


def evaluate_signature(sig: SignatureRef, window: int = 10, contamination: float = 0.01) -> SignatureResult:
    zip_path = gesl_client.download_signature(sig.sigid)
    frame = gesl_parse.extract_pmu_frame(zip_path)
    pmu_prefixes = gesl_parse.list_pmu_prefixes(frame)

    # GESL's Time column is relative seconds-from-start at whatever rate this
    # signature's PMUs sampled at (~30Hz observed) -- not LBNL's fixed 120Hz --
    # so the regularization grid must be inferred per-signature, not assumed.
    freq_ns = int(frame.index.to_series().diff().median().value)

    channel_flagged: dict[str, bool] = {}
    for pmu_prefix in pmu_prefixes:
        suffixes = sig.columns or _channel_suffixes(frame, pmu_prefix)
        for suffix in suffixes:
            series = gesl_parse.load_signature_channel(frame, pmu_prefix, suffix)
            if series is None:
                continue
            channel_name = f"{pmu_prefix}{suffix}"
            channel_flagged[channel_name] = _evaluate_channel(
                series.rename(channel_name), freq_ns, window, contamination
            )

    return SignatureResult(
        sigid=sig.sigid,
        source=sig.source,
        description=sig.description,
        any_flagged=any(channel_flagged.values()),
        channel_flagged=channel_flagged,
        n_channels_checked=len(channel_flagged),
    )


def run_validation(window: int = 10, contamination: float = 0.01) -> dict:
    timing_results = [evaluate_signature(sig, window, contamination) for sig in TIMING_SIGNATURES]
    negative_results = [
        evaluate_signature(SignatureRef(sigid, "", "", ()), window, contamination)
        for sigid in NEGATIVE_CONTROL_SIGIDS
    ]

    return {
        "timing_results": timing_results,
        "negative_control_results": negative_results,
        "timing_recall": (
            sum(r.any_flagged for r in timing_results) / len(timing_results) if timing_results else 0.0
        ),
        "negative_control_fp_rate": (
            sum(r.any_flagged for r in negative_results) / len(negative_results)
            if negative_results
            else 0.0
        ),
    }


def fit_baseline_pipelines(window: int = 10, contamination: float = 0.01) -> dict[str, Pipeline]:
    """Pools every available channel of each measurement-type suffix (_f,
    _vp_a, etc.) across BASELINE_TRAIN_SIGIDS, then fits one IsolationForest
    per suffix via model.fit_pipeline -- a "known normal" reference that
    evaluate_signature_against_baseline scores real test signatures against
    with model.score_anomalies (predict only, never refit). Unlike
    evaluate_signature()'s per-channel fit_predict, this calibrates
    contamination once, against a fixed baseline, rather than fresh against
    whatever data each test channel happens to contain.

    One model per suffix, not one universal model: a frequency channel and
    a voltage-angle channel have entirely different scales/distributions,
    so pooling across suffixes would blur the baseline meaninglessly.
    """
    suffix_arrays: dict[str, list[np.ndarray]] = {}

    for sigid in BASELINE_TRAIN_SIGIDS:
        zip_path = gesl_client.download_signature(sigid)
        frame = gesl_parse.extract_pmu_frame(zip_path)
        freq_ns = int(frame.index.to_series().diff().median().value)

        for pmu_prefix in gesl_parse.list_pmu_prefixes(frame):
            for suffix in _channel_suffixes(frame, pmu_prefix):
                series = gesl_parse.load_signature_channel(frame, pmu_prefix, suffix)
                if series is None:
                    continue
                channel_name = f"{pmu_prefix}{suffix}"
                channel_df = _channel_features(series.rename(channel_name), freq_ns, window)
                if channel_df is None:
                    continue
                suffix_arrays.setdefault(suffix, []).append(
                    channel_df[_feature_cols(channel_name)].values
                )

    baseline_models: dict[str, Pipeline] = {}
    for suffix, arrays in suffix_arrays.items():
        X = np.vstack(arrays)
        baseline_models[suffix] = model.fit_pipeline(model.build_pipeline(contamination=contamination), X)
    return baseline_models


def _score_channel_against_baseline(series, freq_ns: int, window: int, pipeline: Pipeline) -> bool:
    col = series.name
    channel_df = _channel_features(series, freq_ns, window)
    if channel_df is None:
        return False

    y_pred = model.score_anomalies(pipeline, channel_df[_feature_cols(col)].values)
    return evaluate.signature_level_recall(y_pred)


def evaluate_signature_against_baseline(
    sig: SignatureRef, baseline_models: dict[str, Pipeline], window: int = 10
) -> SignatureResult:
    """Same SignatureResult shape as evaluate_signature(), but scores each
    channel against a fixed, already-fitted baseline_models[suffix] (see
    fit_baseline_pipelines) instead of fitting a fresh IsolationForest per
    channel. A channel whose suffix has no baseline model is skipped
    entirely -- there's nothing to score it against -- same as a channel
    that doesn't exist on this PMU at all.
    """
    zip_path = gesl_client.download_signature(sig.sigid)
    frame = gesl_parse.extract_pmu_frame(zip_path)
    pmu_prefixes = gesl_parse.list_pmu_prefixes(frame)
    freq_ns = int(frame.index.to_series().diff().median().value)

    channel_flagged: dict[str, bool] = {}
    for pmu_prefix in pmu_prefixes:
        suffixes = sig.columns or _channel_suffixes(frame, pmu_prefix)
        for suffix in suffixes:
            if suffix not in baseline_models:
                continue
            series = gesl_parse.load_signature_channel(frame, pmu_prefix, suffix)
            if series is None:
                continue
            channel_name = f"{pmu_prefix}{suffix}"
            channel_flagged[channel_name] = _score_channel_against_baseline(
                series.rename(channel_name), freq_ns, window, baseline_models[suffix]
            )

    return SignatureResult(
        sigid=sig.sigid,
        source=sig.source,
        description=sig.description,
        any_flagged=any(channel_flagged.values()),
        channel_flagged=channel_flagged,
        n_channels_checked=len(channel_flagged),
    )


def run_baseline_validation(window: int = 10, contamination: float = 0.01, threshold: float = 0.1) -> dict:
    """Same shape as run_validation(), for direct comparison: fits the
    baseline once (from BASELINE_TRAIN_SIGIDS, never scored/tested itself),
    then scores the same 14 TIMING_SIGNATURES + 15 NEGATIVE_CONTROL_SIGIDS
    used in the original per-channel-fit_predict validation.

    Unlike run_validation(), the signature-level verdict here is
    SignatureResult.fraction_flagged >= threshold, not any_flagged --
    any() saturates once a signature has enough channels (a single flagged
    channel out of hundreds shouldn't condemn the whole signature). The
    default threshold (0.1) is a starting point, not a tuned value; results
    are reported per-signature so a caller can recompute at other
    thresholds without re-fitting."""
    baseline_models = fit_baseline_pipelines(window=window, contamination=contamination)

    timing_results = [
        evaluate_signature_against_baseline(sig, baseline_models, window) for sig in TIMING_SIGNATURES
    ]
    negative_results = [
        evaluate_signature_against_baseline(SignatureRef(sigid, "", "", ()), baseline_models, window)
        for sigid in NEGATIVE_CONTROL_SIGIDS
    ]

    return {
        "timing_results": timing_results,
        "negative_control_results": negative_results,
        "threshold": threshold,
        "timing_recall": (
            sum(r.fraction_flagged >= threshold for r in timing_results) / len(timing_results)
            if timing_results
            else 0.0
        ),
        "negative_control_fp_rate": (
            sum(r.fraction_flagged >= threshold for r in negative_results) / len(negative_results)
            if negative_results
            else 0.0
        ),
    }

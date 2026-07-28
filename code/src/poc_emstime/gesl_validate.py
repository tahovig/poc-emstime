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

from poc_emstime import evaluate, features, gesl_client, gesl_parse, ingest, model
from poc_emstime.gesl_manifest import NEGATIVE_CONTROL_SIGIDS, SignatureRef, TIMING_SIGNATURES


@dataclass
class SignatureResult:
    sigid: int
    source: str
    description: str
    any_flagged: bool
    channel_flagged: dict[str, bool]
    n_channels_checked: int


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

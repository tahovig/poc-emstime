import os

import pytest

from poc_emstime import gesl_validate
from poc_emstime.gesl_manifest import SignatureRef, TIMING_SIGNATURES

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("GESL_APIKEY"),
        reason="GESL_APIKEY not set -- copy .env.example to .env and fill in real credentials",
    ),
]

# 5829: real signature, only 2 measuring PMUs -- picked for a fast real
# end-to-end run (download + parse + per-channel detection), not the
# 80-PMU 5711 used to design gesl_parse.py.
_SMALL_TIMING_SIGNATURE = next(sig for sig in TIMING_SIGNATURES if sig.sigid == 5829)

# Small real signatures for the baseline-fit path (1-2 measuring PMUs each,
# per GESL's own metadata) -- keeps this test's real API/network cost low
# while still exercising the real download/parse/fit path end to end.
_SMALL_BASELINE_TRAIN_SIGIDS = (5731, 5753, 5758)
_SMALL_NEGATIVE_CONTROL_SIGID = 5725


def test_evaluate_signature_shape_on_real_small_timing_signature():
    result = gesl_validate.evaluate_signature(_SMALL_TIMING_SIGNATURE, window=10, contamination=0.01)

    assert result.sigid == 5829
    # Whether the detector actually catches this real, independently-labeled
    # clock error is the empirical question this milestone exists to answer
    # -- not something to assert as a fixed invariant here.
    assert isinstance(result.any_flagged, bool)
    # 2 PMUs x up to 2 tagged suffixes (_f, _vp_a) -- not asserting the exact
    # count, since GESL's column layout isn't guaranteed uniform per PMU
    # (confirmed during M2: some PMUs carry an extra, non-tagged _status column).
    assert 1 <= result.n_channels_checked <= 4
    for channel_name, flagged in result.channel_flagged.items():
        assert channel_name.startswith("P")
        assert isinstance(flagged, bool)


def test_evaluate_signature_against_baseline_shape_on_real_small_signatures(monkeypatch):
    monkeypatch.setattr(gesl_validate, "BASELINE_TRAIN_SIGIDS", _SMALL_BASELINE_TRAIN_SIGIDS)
    baseline_models = gesl_validate.fit_baseline_pipelines(window=10, contamination=0.01)
    assert baseline_models  # at least one suffix's worth of real channels was pooled and fit

    timing_result = gesl_validate.evaluate_signature_against_baseline(
        _SMALL_TIMING_SIGNATURE, baseline_models, window=10
    )
    negative_result = gesl_validate.evaluate_signature_against_baseline(
        SignatureRef(_SMALL_NEGATIVE_CONTROL_SIGID, "", "", ()), baseline_models, window=10
    )

    # Same shape-only policy as the fit_predict integration test above:
    # whether this approach actually discriminates real anomalies from real
    # normal data is the empirical question F5's full run exists to answer.
    for result in (timing_result, negative_result):
        assert isinstance(result.any_flagged, bool)
        for channel_name, flagged in result.channel_flagged.items():
            assert channel_name.startswith("P")
            assert isinstance(flagged, bool)

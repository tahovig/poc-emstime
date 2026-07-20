import os

import pandas as pd
import pytest

from poc_emstime.ingest import SAMPLE_INTERVAL_NS, add_gap_features, load_channel, load_upmu_site, regularize

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_channel.csv")


def test_load_channel_parses_real_format():
    s = load_channel(FIXTURE, "MAG")
    assert s.name == "MAG"
    assert len(s) == 35
    assert s.index.is_monotonic_increasing
    assert s.iloc[0] == pytest.approx(1.0)


def test_load_upmu_site_joins_multiple_channels_on_timestamp():
    df = load_upmu_site({"MAG": FIXTURE, "ANG": FIXTURE})
    assert list(df.columns) == ["MAG", "ANG"]
    assert len(df) == 35
    assert (df["MAG"] == df["ANG"]).all()


def test_add_gap_features_flags_dropout_as_large_delta():
    df = load_upmu_site({"MAG": FIXTURE})
    df = add_gap_features(df)
    deltas_ms = df["Time_Delta_ms"].values
    # the dropout window removed 5 consecutive samples, so one real gap
    # should be ~6x the nominal 8.333ms interval
    nominal_ms = SAMPLE_INTERVAL_NS / 1e6
    assert deltas_ms.max() > 5 * nominal_ms


def test_regularize_flags_dropout_window_as_filled():
    df = load_upmu_site({"MAG": FIXTURE})
    df = add_gap_features(df)
    out = regularize(df)
    # the fixture's dropout window (rows 20-24) should surface as Was_Filled rows
    assert out["Was_Filled"].sum() >= 5


def test_regularize_respects_ffill_limit():
    df = load_upmu_site({"MAG": FIXTURE})
    df = add_gap_features(df)
    out = regularize(df, ffill_limit=2)
    # a 5-row gap with ffill_limit=2 must leave real NaNs beyond the limit
    assert out["MAG"].isna().sum() > 0


def test_regularize_tolerates_duplicate_timestamps():
    # a clock-step fault whose offset is a multiple of the sample interval
    # can land a shifted row on an already-occupied timestamp
    index = pd.to_datetime([1_600_000_000_000_000_000 + i * SAMPLE_INTERVAL_NS for i in range(10)])
    df = pd.DataFrame({"X": range(10)}, index=index)
    duped = pd.concat([df, df.iloc[[3]]]).sort_index()
    df = add_gap_features(duped)

    out = regularize(df)  # must not raise

    assert not out.index.duplicated().any()

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from poc_emstime import gesl_parse, ingest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "gesl_sample_pmu_frame.csv"


def _build_outer_zip(csv_bytes: bytes, sigid: int = 999) -> bytes:
    """Builds the real GESL nesting (outer zip -> metadata CSV + nested zip
    -> event CSV) entirely in memory -- no binary fixture committed, since
    GESL's redistribution terms haven't been verified (more conservative
    than even the LBNL fixture precedent of using synthetic-but-real-schema
    CSVs)."""
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner:
        inner.writestr("EventEI0001.csv", csv_bytes)

    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer:
        outer.writestr(f"sigId-{sigid}.zip", inner_buf.getvalue())
        outer.writestr(f"sigId-{sigid}-Metadata.csv", "ID, Data Source\n999, Test Source\n")

    return outer_buf.getvalue()


@pytest.fixture
def sample_outer_zip(tmp_path):
    zip_bytes = _build_outer_zip(FIXTURE.read_bytes())
    path = tmp_path / "sigId-999.zip"
    path.write_bytes(zip_bytes)
    return path


def test_extract_pmu_frame_parses_real_schema(sample_outer_zip):
    frame = gesl_parse.extract_pmu_frame(sample_outer_zip)

    assert isinstance(frame.index, pd.DatetimeIndex)
    assert "Time" not in frame.columns
    assert "P001_f" in frame.columns
    assert "P002_status" in frame.columns
    assert len(frame) == 15


def test_extract_pmu_frame_spacing_feeds_regularize_unmodified(sample_outer_zip):
    frame = gesl_parse.extract_pmu_frame(sample_outer_zip)
    inferred_freq_ns = int(frame.index.to_series().diff().median().value)

    regularized = ingest.regularize(frame, freq_ns=inferred_freq_ns)

    assert len(regularized) >= len(frame)
    assert "Was_Filled" in regularized.columns


def test_list_pmu_prefixes_reflects_actual_columns_not_assumed_count(sample_outer_zip):
    frame = gesl_parse.extract_pmu_frame(sample_outer_zip)
    assert gesl_parse.list_pmu_prefixes(frame) == ["P001", "P002", "P003"]


def test_load_signature_channel_finds_exact_column(sample_outer_zip):
    frame = gesl_parse.extract_pmu_frame(sample_outer_zip)
    series = gesl_parse.load_signature_channel(frame, "P001", "_f")
    assert series is not None
    assert len(series) == len(frame)
    assert series.iloc[0] == 60.001


def test_load_signature_channel_returns_none_for_missing_suffix(sample_outer_zip):
    frame = gesl_parse.extract_pmu_frame(sample_outer_zip)
    # Only P002 has a _status column in this fixture -- P001 must not.
    assert gesl_parse.load_signature_channel(frame, "P001", "_status") is None


def test_status_column_does_not_interfere_with_other_pmu_lookups(sample_outer_zip):
    frame = gesl_parse.extract_pmu_frame(sample_outer_zip)
    f = gesl_parse.load_signature_channel(frame, "P002", "_f")
    vp_a = gesl_parse.load_signature_channel(frame, "P002", "_vp_a")
    status = gesl_parse.load_signature_channel(frame, "P002", "_status")

    assert f is not None and vp_a is not None and status is not None
    assert not f.equals(vp_a)


def test_extract_pmu_frame_raises_clearly_on_missing_nested_zip(tmp_path):
    bad_zip = tmp_path / "sigId-000-broken.zip"
    with zipfile.ZipFile(bad_zip, "w") as z:
        z.writestr("sigId-000-Metadata.csv", "ID\n000\n")

    with pytest.raises(ValueError, match="no nested zip found"):
        gesl_parse.extract_pmu_frame(bad_zip)

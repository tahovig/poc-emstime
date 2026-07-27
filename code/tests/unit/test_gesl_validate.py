import io
import zipfile
from pathlib import Path

import pytest

from poc_emstime import gesl_validate
from poc_emstime.gesl_manifest import SignatureRef

FIXTURE = Path(__file__).parent.parent / "fixtures" / "gesl_sample_pmu_frame.csv"


def _build_outer_zip(csv_bytes: bytes, sigid: int = 999) -> bytes:
    """Same in-memory nesting as test_gesl_parse.py's helper -- duplicated
    rather than shared, since these are independent, self-contained test
    modules and the helper is a few lines."""
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


def test_evaluate_signature_checks_only_tagged_channels(sample_outer_zip, monkeypatch):
    monkeypatch.setattr(gesl_validate.gesl_client, "download_signature", lambda sigid, **kw: sample_outer_zip)
    sig = SignatureRef(999, "Test Source", "test", ("_f",))

    result = gesl_validate.evaluate_signature(sig, window=3, contamination=0.1)

    assert result.sigid == 999
    assert set(result.channel_flagged) == {"P001_f", "P002_f", "P003_f"}
    assert result.n_channels_checked == 3
    assert isinstance(result.any_flagged, bool)


def test_evaluate_signature_checks_all_non_status_channels_when_untagged(sample_outer_zip, monkeypatch):
    monkeypatch.setattr(gesl_validate.gesl_client, "download_signature", lambda sigid, **kw: sample_outer_zip)
    # Empty columns == negative-control convention: no named tag to check, so
    # scan every real measurement this PMU reports -- but never the _status
    # flag column, which isn't a continuous measurement.
    sig = SignatureRef(999, "Test Source", "test", ())

    result = gesl_validate.evaluate_signature(sig, window=3, contamination=0.1)

    assert set(result.channel_flagged) == {
        "P001_f", "P001_vp_a", "P002_f", "P002_vp_a", "P003_f", "P003_vp_a",
    }
    assert result.n_channels_checked == 6


def test_channel_suffixes_excludes_status_column(sample_outer_zip):
    frame = gesl_validate.gesl_parse.extract_pmu_frame(sample_outer_zip)
    assert gesl_validate._channel_suffixes(frame, "P002") == ["_f", "_vp_a"]


def test_run_validation_reports_recall_and_fp_rate(sample_outer_zip, monkeypatch):
    monkeypatch.setattr(gesl_validate.gesl_client, "download_signature", lambda sigid, **kw: sample_outer_zip)
    monkeypatch.setattr(
        gesl_validate, "TIMING_SIGNATURES", (SignatureRef(999, "Test Source", "test", ("_f",)),)
    )
    monkeypatch.setattr(gesl_validate, "NEGATIVE_CONTROL_SIGIDS", (999,))

    results = gesl_validate.run_validation(window=3, contamination=0.1)

    assert len(results["timing_results"]) == 1
    assert len(results["negative_control_results"]) == 1
    assert results["timing_recall"] in (0.0, 1.0)
    assert results["negative_control_fp_rate"] in (0.0, 1.0)

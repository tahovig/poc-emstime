from pathlib import Path

from poc_emstime.app.config import (
    DATASET_MANIFEST,
    DatasetSpec,
    is_available,
    list_datasets,
    resolve_channel_paths,
)


def test_manifest_has_expected_keys():
    assert set(DATASET_MANIFEST.keys()) == {"a6_bus1_partial", "a6_bus1_1day", "fixture_smoke_test"}


def test_full_120m_row_files_are_never_listed():
    # The full LBNL files OOM this environment during ingest alone (see
    # config.py's docstring) -- they must never be reachable from the manifest.
    listed_paths = {p for spec in DATASET_MANIFEST.values() for p in spec.channels.values()}
    assert "data/raw/_LBNL_a6_bus1_L1MAG.csv" not in listed_paths
    assert "data/raw/_LBNL_a6_bus1_LSTATE.csv" not in listed_paths


def test_fixture_smoke_test_dataset_is_available():
    # Its backing file is committed to the repo, so this must hold in any
    # checkout (including a fresh CI clone with no data/raw/ downloads).
    options = {opt.key: opt for opt in list_datasets()}
    assert options["fixture_smoke_test"].available is True


def test_is_available_false_for_missing_files():
    fake_spec = DatasetSpec(
        label="fake",
        channels={"MAG": "data/raw/does_not_exist_at_all.csv"},
        target_col="MAG",
    )
    assert is_available(fake_spec) is False


def test_resolve_channel_paths_returns_absolute_existing_paths():
    spec = DATASET_MANIFEST["fixture_smoke_test"]
    resolved = resolve_channel_paths(spec)
    assert Path(resolved["MAG"]).is_absolute()
    assert Path(resolved["MAG"]).exists()

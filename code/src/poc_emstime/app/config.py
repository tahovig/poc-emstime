"""Fixed configuration for the app layer: paths, dataset manifest, tunables.

The dataset manifest is a fixed, hardcoded set of already-downloaded local
files -- a new run never accepts an arbitrary path from the frontend, and
the full 120M-row LBNL files are deliberately never listed here, since
ingest.load_upmu_site() alone drives RSS past this environment's ~7.6GB
budget during the merge step, before any modeling happens.
"""

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_RAW_DIR = REPO_ROOT / "data" / "raw"
DATA_APP_DIR = REPO_ROOT / "data" / "app"
DB_PATH = DATA_APP_DIR / "db.sqlite3"
MODELS_DIR = DATA_APP_DIR / "models"

CHART_MAX_BUCKETS = 2000
HEARTBEAT_INTERVAL_S = 3
MAX_QUEUED_RUNS = 5


@dataclass(frozen=True)
class DatasetSpec:
    label: str
    channels: dict[str, str]  # {column_name: path, relative to REPO_ROOT}
    target_col: str
    tq_col: str = "TQ"


@dataclass(frozen=True)
class DatasetOption:
    key: str
    label: str
    target_col: str
    tq_col: str
    available: bool


DATASET_MANIFEST: dict[str, DatasetSpec] = {
    "a6_bus1_partial": DatasetSpec(
        label="a6_bus1 partial (~1.13hr, 487,667 rows)",
        channels={
            "MAG": "data/raw/_LBNL_a6_bus1_L1MAG_partial.csv",
            "TQ": "data/raw/_LBNL_a6_bus1_LSTATE_partial.csv",
        },
        target_col="MAG",
    ),
    "a6_bus1_1day": DatasetSpec(
        label="a6_bus1 1-day (10,368,000 rows, ~10min run)",
        channels={
            "MAG": "data/raw/_LBNL_a6_bus1_L1MAG_1day.csv",
            "TQ": "data/raw/_LBNL_a6_bus1_LSTATE_1day.csv",
        },
        target_col="MAG",
    ),
    "fixture_smoke_test": DatasetSpec(
        label="instant smoke test (synthetic fixture, <1s)",
        channels={
            "MAG": "code/tests/fixtures/sample_pipeline_channel.csv",
        },
        target_col="MAG",
    ),
}


def resolve_channel_paths(spec: DatasetSpec) -> dict[str, str]:
    return {col: str(REPO_ROOT / rel) for col, rel in spec.channels.items()}


def is_available(spec: DatasetSpec) -> bool:
    return all((REPO_ROOT / rel).exists() for rel in spec.channels.values())


def list_datasets() -> list[DatasetOption]:
    return [
        DatasetOption(
            key=key,
            label=spec.label,
            target_col=spec.target_col,
            tq_col=spec.tq_col,
            available=is_available(spec),
        )
        for key, spec in DATASET_MANIFEST.items()
    ]

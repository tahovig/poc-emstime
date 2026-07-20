"""Persisted run records: config, status, results, and where artifacts live."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # "synthetic_demo" is the only mode built in v1; the column exists now so
    # a future real-unlabeled-data mode doesn't require a migration.
    mode: str = Field(default="synthetic_demo")

    dataset_key: str
    target_col: str
    tq_col: str

    window: int = 10
    n_estimators: int = 100
    random_state: int = 42
    contamination: float = 0.01
    max_samples: float = 1.0

    status: str = Field(default="queued")  # queued | running | completed | failed

    created_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_s: Optional[float] = None

    n_rows: Optional[int] = None
    n_flagged: Optional[int] = None

    # Nullable: a future ground-truth-free run mode has no fault labels to
    # score against and would leave these (and the two _json fields) null.
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    by_fault_type_json: Optional[str] = None
    window_level_recall_json: Optional[str] = None

    chart_json: Optional[str] = None
    model_path: Optional[str] = None
    error_message: Optional[str] = None

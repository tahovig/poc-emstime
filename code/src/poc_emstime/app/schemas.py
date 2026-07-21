"""Pydantic request/response models.

Kept separate from db_models.Run so the wire shape can diverge from
storage layout (e.g. JSON-encoded columns become real dicts here) without
a migration.
"""

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from poc_emstime.app.db_models import Run


class RunCreateRequest(BaseModel):
    dataset_key: str
    window: int = 10
    contamination: float = 0.01
    n_estimators: int = 100
    random_state: int = 42


class RunSummary(BaseModel):
    id: int
    mode: str
    dataset_key: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_s: Optional[float] = None
    n_rows: Optional[int] = None
    n_flagged: Optional[int] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None

    @classmethod
    def from_run(cls, run: Run) -> "RunSummary":
        return cls(**{field: getattr(run, field) for field in cls.model_fields})


class RunDetail(RunSummary):
    target_col: str
    tq_col: str
    window: int
    n_estimators: int
    random_state: int
    contamination: float
    max_samples: float
    by_fault_type: dict[str, float] = {}
    window_level_recall: dict[str, bool] = {}
    error_message: Optional[str] = None

    @classmethod
    def from_run(cls, run: Run) -> "RunDetail":
        base_fields = {field: getattr(run, field) for field in RunSummary.model_fields}
        return cls(
            **base_fields,
            target_col=run.target_col,
            tq_col=run.tq_col,
            window=run.window,
            n_estimators=run.n_estimators,
            random_state=run.random_state,
            contamination=run.contamination,
            max_samples=run.max_samples,
            by_fault_type=json.loads(run.by_fault_type_json) if run.by_fault_type_json else {},
            window_level_recall=json.loads(run.window_level_recall_json) if run.window_level_recall_json else {},
            error_message=run.error_message,
        )


class DatasetOption(BaseModel):
    key: str
    label: str
    target_col: str
    tq_col: str
    available: bool

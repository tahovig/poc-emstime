import json
import queue
import time
from pathlib import Path

import joblib
import pytest

from poc_emstime.app import config, db, jobs
from poc_emstime.app.db_models import Run
from poc_emstime.app.progress import bus


@pytest.fixture
def isolated_app_env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_APP_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "db.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "models")
    db.init_db()
    yield
    monkeypatch.setattr(db, "_engine", None)


@pytest.fixture(autouse=True)
def _clean_progress_bus():
    # The bus is a module-level singleton; run ids restart from 1 in every
    # test's fresh isolated DB, so state must not leak across tests.
    bus._subscribers.clear()
    bus._history.clear()
    yield
    bus._subscribers.clear()
    bus._history.clear()


def _make_run(dataset_key: str = "fixture_smoke_test", **overrides) -> int:
    spec = config.DATASET_MANIFEST[dataset_key]
    with db.get_session() as session:
        run = Run(
            dataset_key=dataset_key,
            target_col=spec.target_col,
            tq_col=overrides.pop("tq_col", spec.tq_col),
            **overrides,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


def test_process_runs_fixture_end_to_end_and_persists_everything(isolated_app_env):
    run_id = _make_run(contamination=0.05, n_estimators=17, random_state=7)
    subscriber_queue, _ = bus.subscribe(run_id)

    jobs._process(jobs.RunJob(run_id))

    events = []
    while True:
        try:
            events.append(subscriber_queue.get_nowait())
        except queue.Empty:
            break

    with db.get_session() as session:
        run = session.get(Run, run_id)

    assert run.status == "completed"
    assert run.n_rows > 0
    assert run.duration_s is not None and run.duration_s >= 0
    assert 0.0 <= run.precision <= 1.0

    by_fault_type = json.loads(run.by_fault_type_json)
    window_level_recall = json.loads(run.window_level_recall_json)
    assert set(by_fault_type.keys()) == set(window_level_recall.keys())

    chart = json.loads(run.chart_json)
    assert chart["n_rows_full"] == run.n_rows
    assert len(chart["timestamps"]) <= chart["n_rows_full"]

    model_path = Path(run.model_path)
    assert model_path.is_absolute()
    assert model_path.exists()
    loaded_model = joblib.load(model_path)
    assert loaded_model.named_steps["iforest"].n_estimators == 17
    assert loaded_model.named_steps["iforest"].contamination == 0.05

    assert any(e.get("kind") == "progress" for e in events)
    assert any(e.get("kind") == "terminal" and e.get("status") == "completed" for e in events)


def test_process_marks_run_failed_on_unknown_dataset(isolated_app_env):
    with db.get_session() as session:
        run = Run(dataset_key="does_not_exist", target_col="MAG", tq_col="TQ")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    jobs._process(jobs.RunJob(run_id))

    with db.get_session() as session:
        run = session.get(Run, run_id)

    assert run.status == "failed"
    assert run.error_message


def test_submit_job_raises_when_queue_is_full(monkeypatch):
    small_queue = queue.Queue(maxsize=1)
    monkeypatch.setattr(jobs, "_queue", small_queue)

    jobs.submit_job(1)
    with pytest.raises(queue.Full):
        jobs.submit_job(2)


def test_worker_thread_processes_a_submitted_job_end_to_end(isolated_app_env):
    run_id = _make_run()

    jobs.start_worker()
    jobs.submit_job(run_id)

    deadline = time.monotonic() + 10
    status = "queued"
    while status not in ("completed", "failed") and time.monotonic() < deadline:
        time.sleep(0.05)
        with db.get_session() as session:
            status = session.get(Run, run_id).status

    assert status == "completed"

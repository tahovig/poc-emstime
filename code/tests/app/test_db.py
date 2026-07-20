import json
import threading

import pytest
from sqlmodel import select

from poc_emstime.app import config, db
from poc_emstime.app.db_models import Run


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Points db.py at a throwaway sqlite file instead of the real
    data/app/db.sqlite3, and resets the module-level engine singleton so a
    fresh engine gets built against it."""
    monkeypatch.setattr(db, "DATA_APP_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "db.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    db.init_db()
    yield db
    monkeypatch.setattr(db, "_engine", None)


def test_run_round_trips_through_sqlite(isolated_db):
    with isolated_db.get_session() as session:
        run = Run(dataset_key="fixture_smoke_test", target_col="MAG", tq_col="TQ")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    with isolated_db.get_session() as session:
        loaded = session.get(Run, run_id)
        assert loaded is not None
        assert loaded.dataset_key == "fixture_smoke_test"
        assert loaded.status == "queued"
        assert loaded.mode == "synthetic_demo"


def test_json_and_nullable_result_columns_round_trip(isolated_db):
    with isolated_db.get_session() as session:
        run = Run(
            dataset_key="fixture_smoke_test",
            target_col="MAG",
            tq_col="TQ",
            status="completed",
            precision=0.5,
            by_fault_type_json=json.dumps({"dropout": 0.33}),
            window_level_recall_json=json.dumps({"dropout": True}),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    with isolated_db.get_session() as session:
        loaded = session.get(Run, run_id)
        assert loaded.precision == 0.5
        assert json.loads(loaded.by_fault_type_json) == {"dropout": 0.33}
        assert json.loads(loaded.window_level_recall_json) == {"dropout": True}


def test_a_fresh_run_leaves_result_fields_null(isolated_db):
    with isolated_db.get_session() as session:
        run = Run(dataset_key="fixture_smoke_test", target_col="MAG", tq_col="TQ")
        session.add(run)
        session.commit()
        session.refresh(run)

        assert run.precision is None
        assert run.by_fault_type_json is None
        assert run.model_path is None


def test_concurrent_sessions_from_different_threads_do_not_error(isolated_db):
    # This is the concrete thing that makes cross-thread access (HTTP
    # handlers + the background worker) safe: check_same_thread=False plus
    # every operation using its own short-lived Session.
    errors = []

    def create_one():
        try:
            with isolated_db.get_session() as session:
                session.add(Run(dataset_key="fixture_smoke_test", target_col="MAG", tq_col="TQ"))
                session.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=create_one) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    with isolated_db.get_session() as session:
        assert len(session.exec(select(Run)).all()) == 5

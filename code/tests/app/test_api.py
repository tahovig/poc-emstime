import queue as queue_mod
import time

import pytest
from fastapi.testclient import TestClient

from poc_emstime.app import config, db
from poc_emstime.app.db_models import Run
from poc_emstime.app.main import app
from poc_emstime.app.routers import runs as runs_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_APP_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "db.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "models")

    with TestClient(app) as test_client:
        yield test_client

    monkeypatch.setattr(db, "_engine", None)


def _wait_for_terminal(client, run_id, timeout=10):
    deadline = time.monotonic() + timeout
    detail = None
    while time.monotonic() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        detail = resp.json()
        if detail["status"] in ("completed", "failed"):
            return detail
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not reach a terminal status within {timeout}s: {detail}")


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_datasets_includes_available_fixture(client):
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    options = {o["key"]: o for o in resp.json()}
    assert options["fixture_smoke_test"]["available"] is True


def test_create_run_rejects_unknown_dataset_key(client):
    resp = client.post("/api/runs", json={"dataset_key": "does_not_exist"})
    assert resp.status_code == 404


def test_get_run_404_for_missing_id(client):
    resp = client.get("/api/runs/999999")
    assert resp.status_code == 404


def test_get_chart_404_before_completion(client):
    with db.get_session() as session:
        run = Run(dataset_key="fixture_smoke_test", target_col="MAG", tq_col="TQ")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    resp = client.get(f"/api/runs/{run_id}/chart")
    assert resp.status_code == 404


def test_create_run_runs_to_completion_and_is_fully_retrievable(client):
    create_resp = client.post("/api/runs", json={"dataset_key": "fixture_smoke_test"})
    assert create_resp.status_code == 201
    run_id = create_resp.json()["id"]
    assert create_resp.json()["status"] in ("queued", "running", "completed")

    detail = _wait_for_terminal(client, run_id)

    assert detail["status"] == "completed"
    assert detail["n_rows"] > 0
    assert set(detail["by_fault_type"].keys()) == set(detail["window_level_recall"].keys())
    assert 0.0 <= detail["precision"] <= 1.0

    chart_resp = client.get(f"/api/runs/{run_id}/chart")
    assert chart_resp.status_code == 200
    assert chart_resp.json()["n_rows_full"] == detail["n_rows"]


def test_list_runs_orders_newest_first(client):
    first = client.post("/api/runs", json={"dataset_key": "fixture_smoke_test"}).json()
    second = client.post("/api/runs", json={"dataset_key": "fixture_smoke_test"}).json()

    resp = client.get("/api/runs")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert ids.index(second["id"]) < ids.index(first["id"])


def test_delete_run_removes_it(client):
    created = client.post("/api/runs", json={"dataset_key": "fixture_smoke_test"}).json()
    run_id = created["id"]
    _wait_for_terminal(client, run_id)

    resp = client.delete(f"/api/runs/{run_id}")
    assert resp.status_code == 204

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 404


def test_create_run_returns_429_and_rolls_back_when_queue_is_full(client, monkeypatch):
    before = client.get("/api/runs").json()

    def _raise_full(run_id):
        raise queue_mod.Full()

    monkeypatch.setattr(runs_router.jobs, "submit_job", _raise_full)

    resp = client.post("/api/runs", json={"dataset_key": "fixture_smoke_test"})
    assert resp.status_code == 429

    after = client.get("/api/runs").json()
    assert len(after) == len(before)


def test_progress_stream_of_an_already_completed_run_yields_one_terminal_event(client):
    created = client.post("/api/runs", json={"dataset_key": "fixture_smoke_test"}).json()
    run_id = created["id"]
    _wait_for_terminal(client, run_id)

    with client.stream("GET", f"/api/runs/{run_id}/progress") as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    assert "event: terminal" in body
    assert '"status": "completed"' in body or '"status":"completed"' in body

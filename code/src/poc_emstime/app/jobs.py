"""Single-worker background job execution for runs.

A dedicated OS thread (not an asyncio task) processes exactly one run at a
time from a bounded queue. This is a deliberate concurrency limit, not
just an assumption: pipeline.run()'s model-fit step is synchronous/
CPU-bound and can take ~10 minutes on real data, and this environment has
only ~7.6GB RAM -- running two fits at once risks the same OOM already
seen when loading the full dataset.
"""

import json
import queue
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone

import joblib

from poc_emstime import pipeline
from poc_emstime.app import config, db
from poc_emstime.app.db_models import Run
from poc_emstime.app.downsample import decimate_for_chart
from poc_emstime.app.progress import bus


@dataclass
class RunJob:
    run_id: int


_queue: queue.Queue = queue.Queue(maxsize=config.MAX_QUEUED_RUNS)
_worker_started = False
_worker_lock = threading.Lock()


def submit_job(run_id: int) -> None:
    """Raises queue.Full if config.MAX_QUEUED_RUNS runs are already
    queued/running -- callers (the API layer) turn that into HTTP 429."""
    _queue.put_nowait(RunJob(run_id))


def start_worker() -> None:
    """Idempotent: safe to call more than once (e.g. on app reload); only
    ever starts one worker thread for the process's lifetime."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True
        threading.Thread(target=_worker_loop, daemon=True, name="poc-emstime-run-worker").start()


def _worker_loop() -> None:
    while True:
        job = _queue.get()
        try:
            _process(job)
        except Exception:
            # _process handles its own DB-visible failure state; this is a
            # last-resort net so a bug there can't kill the worker thread
            # and silently stop every future run from executing.
            traceback.print_exc()
        finally:
            _queue.task_done()


class _StageTracker:
    """Shared mutable state between pipeline.run()'s progress_callback
    (fires at ~8 discrete stage boundaries) and the heartbeat thread below
    (ticks periodically so the ~10min fitting_and_scoring stage never looks
    frozen to a connected client)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.stage = "queued"
        self.stage_started = time.monotonic()

    def set_stage(self, stage: str) -> None:
        with self._lock:
            self.stage = stage
            self.stage_started = time.monotonic()

    def snapshot(self):
        with self._lock:
            return self.stage, self.stage_started


def _process(job: RunJob) -> None:
    run_id = job.run_id

    with db.get_session() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        dataset_key = run.dataset_key
        target_col = run.target_col
        tq_col = run.tq_col
        window = run.window
        n_estimators = run.n_estimators
        random_state = run.random_state
        contamination = run.contamination
        max_samples = run.max_samples

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()

    start_time = time.monotonic()
    tracker = _StageTracker()
    stop_heartbeat = threading.Event()

    def on_stage(stage: str) -> None:
        tracker.set_stage(stage)
        bus.publish(run_id, {
            "kind": "progress",
            "run_id": run_id,
            "stage": stage,
            "elapsed_s": round(time.monotonic() - start_time, 1),
            "stage_elapsed_s": 0.0,
        })

    def heartbeat() -> None:
        while not stop_heartbeat.wait(config.HEARTBEAT_INTERVAL_S):
            stage, stage_started = tracker.snapshot()
            bus.publish(run_id, {
                "kind": "progress",
                "run_id": run_id,
                "stage": stage,
                "elapsed_s": round(time.monotonic() - start_time, 1),
                "stage_elapsed_s": round(time.monotonic() - stage_started, 1),
            })

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    try:
        spec = config.DATASET_MANIFEST[dataset_key]
        channel_paths = config.resolve_channel_paths(spec)
        result = pipeline.run(
            channel_paths=channel_paths,
            target_col=target_col,
            tq_col=tq_col,
            window=window,
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            max_samples=max_samples,
            progress_callback=on_stage,
        )
    except Exception as exc:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=config.HEARTBEAT_INTERVAL_S + 1)
        with db.get_session() as session:
            run = session.get(Run, run_id)
            run.status = "failed"
            run.error_message = f"{type(exc).__name__}: {exc}"
            run.completed_at = datetime.now(timezone.utc)
            run.duration_s = round(time.monotonic() - start_time, 1)
            session.add(run)
            session.commit()
        bus.publish(run_id, {"kind": "terminal", "run_id": run_id, "status": "failed"})
        return

    stop_heartbeat.set()
    heartbeat_thread.join(timeout=config.HEARTBEAT_INTERVAL_S + 1)

    chart = decimate_for_chart(
        result["index"],
        result["target_series"],
        result["y_pred"],
        result["labels"],
        max_buckets=config.CHART_MAX_BUCKETS,
    )

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = config.MODELS_DIR / f"{run_id}.joblib"
    joblib.dump(result["model"], model_path)

    with db.get_session() as session:
        run = session.get(Run, run_id)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.duration_s = round(time.monotonic() - start_time, 1)
        run.n_rows = result["n_rows"]
        run.n_flagged = result["n_flagged"]
        run.precision = result["overall"]["precision"]
        run.recall = result["overall"]["recall"]
        run.f1 = result["overall"]["f1"]
        run.by_fault_type_json = json.dumps(result["by_fault_type"])
        run.window_level_recall_json = json.dumps(result["window_level_recall"])
        run.chart_json = json.dumps(chart)
        run.model_path = str(model_path)
        session.add(run)
        session.commit()

    bus.publish(run_id, {"kind": "terminal", "run_id": run_id, "status": "completed"})

"""Run lifecycle endpoints: create, list, detail, chart data, progress stream."""

import json
import queue as queue_mod
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import select
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from poc_emstime.app import config, db, jobs
from poc_emstime.app.db_models import Run
from poc_emstime.app.progress import bus
from poc_emstime.app.schemas import RunCreateRequest, RunDetail, RunSummary

router = APIRouter()


@router.post("/runs", response_model=RunSummary, status_code=201)
def create_run(payload: RunCreateRequest) -> RunSummary:
    spec = config.DATASET_MANIFEST.get(payload.dataset_key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown dataset_key: {payload.dataset_key!r}")
    if not config.is_available(spec):
        raise HTTPException(
            status_code=409,
            detail=f"dataset files for {payload.dataset_key!r} are not present on disk",
        )

    with db.get_session() as session:
        run = Run(
            dataset_key=payload.dataset_key,
            target_col=spec.target_col,
            tq_col=spec.tq_col,
            window=payload.window,
            contamination=payload.contamination,
            n_estimators=payload.n_estimators,
            random_state=payload.random_state,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
        summary = RunSummary.from_run(run)

    try:
        jobs.submit_job(run_id)
    except queue_mod.Full:
        # Roll back the row we just created rather than leave a permanent
        # "queued" ghost run that will never actually be processed.
        with db.get_session() as session:
            orphan = session.get(Run, run_id)
            if orphan is not None:
                session.delete(orphan)
                session.commit()
        raise HTTPException(status_code=429, detail="too many runs queued, try again shortly")

    return summary


@router.get("/runs", response_model=list[RunSummary])
def list_runs(limit: int = 50, offset: int = 0) -> list[RunSummary]:
    with db.get_session() as session:
        statement = select(Run).order_by(Run.created_at.desc()).offset(offset).limit(limit)
        return [RunSummary.from_run(run) for run in session.exec(statement).all()]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int) -> RunDetail:
    with db.get_session() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunDetail.from_run(run)


@router.get("/runs/{run_id}/chart")
def get_run_chart(run_id: int) -> dict:
    with db.get_session() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        if run.chart_json is None:
            raise HTTPException(status_code=404, detail="run has no chart data yet (not completed)")
        return json.loads(run.chart_json)


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: int) -> None:
    with db.get_session() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        if run.model_path:
            Path(run.model_path).unlink(missing_ok=True)
        session.delete(run)
        session.commit()


def _sse_format(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


@router.get("/runs/{run_id}/progress")
async def stream_progress(run_id: int, request: Request) -> StreamingResponse:
    with db.get_session() as session:
        if session.get(Run, run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")

    async def event_source():
        # Subscribe *before* checking status: if the run finishes in the
        # gap between the check and the subscribe call, we'd otherwise miss
        # its terminal event entirely.
        subscriber_queue, history = bus.subscribe(run_id)
        try:
            with db.get_session() as session:
                run = session.get(Run, run_id)
                current_status = run.status if run is not None else None

            if current_status in ("completed", "failed"):
                yield _sse_format("terminal", {"run_id": run_id, "status": current_status})
                return

            for event in history:
                kind = event.get("kind", "progress")
                yield _sse_format(kind, {k: v for k, v in event.items() if k != "kind"})

            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Short-timeout poll, not an unbounded blocking get: a
                    # bare queue.get() bridged onto the event loop wouldn't
                    # unblock on client disconnect, so unsubscribe() below
                    # would never run.
                    event = await run_in_threadpool(subscriber_queue.get, True, 1.0)
                except queue_mod.Empty:
                    continue
                kind = event.get("kind", "progress")
                yield _sse_format(kind, {k: v for k, v in event.items() if k != "kind"})
                if kind == "terminal":
                    break
        finally:
            bus.unsubscribe(run_id, subscriber_queue)

    return StreamingResponse(event_source(), media_type="text/event-stream")

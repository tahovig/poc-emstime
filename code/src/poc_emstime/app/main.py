"""FastAPI app: lifespan wiring (DB init, background worker) and API routers.

SPA static-file/fallback serving for the single-command demo path is added
in a later milestone, once there's a built frontend to serve.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from poc_emstime.app import db, jobs
from poc_emstime.app.routers import datasets, runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    jobs.start_worker()
    yield


app = FastAPI(title="poc-emstime", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router, prefix="/api")
app.include_router(runs.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def serve() -> None:
    import uvicorn

    uvicorn.run("poc_emstime.app.main:app", host="0.0.0.0", port=8000)

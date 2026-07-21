"""FastAPI app: lifespan wiring (DB init, background worker), API routers,
and -- once a frontend build exists -- static/SPA-fallback serving so a
single process can demo the whole app on one port.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from poc_emstime.app import config, db, jobs
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


FRONTEND_DIST = config.REPO_ROOT / "code" / "frontend" / "dist"

# Only wired up once `npm run build` has actually produced dist/ -- in dev
# mode there's no build yet, and StaticFiles raises at startup if its
# directory doesn't exist, so this stays optional rather than assumed.
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # A client-side route (e.g. /runs/7) has no matching server route
        # of its own -- Starlette's StaticFiles(html=True) only serves
        # index.html at the exact root, not arbitrary deep links, so this
        # catch-all is what makes a browser refresh on /runs/7 still work.
        # Anything under /api/ that reached here matched no real endpoint
        # and should 404 as JSON, not silently return the SPA shell.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(FRONTEND_DIST / "index.html")


def serve() -> None:
    import uvicorn

    uvicorn.run("poc_emstime.app.main:app", host="0.0.0.0", port=8000)

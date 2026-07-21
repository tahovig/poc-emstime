"""SQLModel engine/session setup for run persistence.

Both HTTP request handlers and the background worker thread touch this
database. What makes that safe isn't `check_same_thread=False` alone -- it's
that every operation opens and closes its own short-lived Session via a
context manager (get_session) rather than holding one open across threads.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from poc_emstime.app.config import DATA_APP_DIR, DB_PATH

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        DATA_APP_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
    return _engine


def init_db() -> None:
    from poc_emstime.app import db_models  # noqa: F401  (registers Run with SQLModel.metadata)

    SQLModel.metadata.create_all(get_engine())


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session

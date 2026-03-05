"""SQLModel data models for MedIntel."""

from datetime import datetime, date
from typing import Optional

from sqlmodel import SQLModel, Field, create_engine, Session
from sqlalchemy import event

from src.config import DB_PATH


class Source(SQLModel, table=True):
    """A data source (journal feed, API, etc.)."""

    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: str  # "rss", "api", "scraper"
    url: str
    active: bool = True
    last_fetched: Optional[datetime] = None


class Article(SQLModel, table=True):
    """A single medical article / news item."""

    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    abstract: Optional[str] = None
    url: str = Field(index=True)
    source: str  # human‑readable source name
    journal: Optional[str] = None
    pub_date: Optional[date] = None
    authors: Optional[str] = None
    doi: Optional[str] = Field(default=None, index=True)
    study_type: Optional[str] = None
    mesh_terms: Optional[str] = None  # comma‑separated
    language: Optional[str] = "en"

    # computed / enriched
    relevance_score: float = 0.0
    specialty: Optional[str] = None
    summary_de: Optional[str] = None
    status: str = "NEW"  # NEW | APPROVED | REJECTED | SAVED | ALERT

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Engine helper
# ---------------------------------------------------------------------------

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

        # Enable WAL mode for better concurrent reads
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        SQLModel.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    return Session(get_engine())

"""Lumio — Database abstraction layer.

Provides dual-mode support:
- DATABASE_URL set → PostgreSQL (production, Neon)
- DATABASE_URL not set → SQLite (local development)
"""
import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, text, event
from sqlmodel import SQLModel, Session

logger = logging.getLogger(__name__)

def _resolve_database_url() -> str:
    """Resolve DATABASE_URL from env, Streamlit secrets, or SQLite fallback."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("database", {}).get("DATABASE_URL")
        except Exception:
            pass
    if not url:
        from src.config import DB_PATH
        url = f"sqlite:///{DB_PATH}"
        logger.info("No DATABASE_URL found, using SQLite: %s", DB_PATH)
    return url

DATABASE_URL = _resolve_database_url()

def is_postgres() -> bool:
    """Check if we're running against PostgreSQL."""
    return DATABASE_URL.startswith("postgresql")

def is_sqlite() -> bool:
    """Check if we're running against SQLite."""
    return DATABASE_URL.startswith("sqlite")

# Engine creation
_engine_kwargs = {"echo": False}
if is_postgres():
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 5,
        "pool_pre_ping": True,  # handles Neon cold-start
    })

_engine = create_engine(DATABASE_URL, **_engine_kwargs)

# SQLite-specific PRAGMA settings
if is_sqlite():
    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

def get_engine():
    """Return the shared engine."""
    return _engine

def get_session():
    """Return a new SQLModel Session."""
    return Session(_engine)

@contextmanager
def get_raw_conn():
    """Get a raw DB-API connection from the pool.

    Replaces all sqlite3.connect() calls. Usage:
        with get_raw_conn() as conn:
            conn.execute(text("SELECT ..."), {"param": value})
    """
    with _engine.connect() as conn:
        yield conn
        conn.commit()

def init_db():
    """Create all tables."""
    SQLModel.metadata.create_all(_engine)

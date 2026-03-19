"""SQLModel data models for Lumio."""

from datetime import datetime, date, timezone
from typing import Optional


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware, avoids deprecated utcnow)."""
    return datetime.now(timezone.utc)

from sqlmodel import SQLModel, Field, create_engine, Session
from sqlalchemy import Index, event

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

    __table_args__ = (
        Index("ix_article_source", "source"),
        Index("ix_article_language", "language"),
        Index("ix_article_status_pub_date", "status", "pub_date"),
        Index("ix_article_status_ack", "status", "alert_acknowledged_at"),
        Index("ix_article_pub_date_score", "pub_date", "relevance_score"),
        Index("ix_article_specialty_pub_date", "specialty", "pub_date"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    abstract: Optional[str] = None
    url: str = Field(index=True)
    source: str  # human‑readable source name
    journal: Optional[str] = None
    pub_date: Optional[date] = Field(default=None, index=True)
    authors: Optional[str] = None
    doi: Optional[str] = Field(default=None, index=True)
    study_type: Optional[str] = None
    mesh_terms: Optional[str] = None  # comma‑separated
    language: Optional[str] = "en"

    # computed / enriched
    relevance_score: float = Field(default=0.0, index=True)
    score_breakdown: Optional[str] = None  # JSON: {"journal":23.4,"design":22.5,...}
    specialty: Optional[str] = Field(default=None, index=True)
    summary_de: Optional[str] = None
    highlight_tags: Optional[str] = None  # pipe-separated relevance tags
    status: str = Field(default="NEW", index=True)  # NEW | APPROVED | REJECTED | SAVED | ALERT

    created_at: datetime = Field(default_factory=_utcnow)
    alert_acknowledged_at: Optional[datetime] = None

    def detach(self) -> "Article":
        """Return a session-independent copy of this article."""
        return Article(**{c.name: getattr(self, c.name) for c in self.__table__.columns})


class StatusChange(SQLModel, table=True):
    """Audit log of article status transitions (for adaptive learning)."""

    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    old_status: str
    new_status: str
    changed_at: datetime = Field(default_factory=_utcnow)


class Watchlist(SQLModel, table=True):
    """User-defined topic watchlist for targeted surveillance."""

    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True)
    name: str
    keywords: str  # comma-separated search terms
    specialty_filter: Optional[str] = None
    min_score: float = 0.0
    notify_email: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    last_match_at: Optional[datetime] = None


class WatchlistMatch(SQLModel, table=True):
    """Matches between watchlists and articles."""

    __table_args__ = (
        Index("ix_wm_wl_matched", "watchlist_id", "matched_at"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    watchlist_id: int = Field(index=True)
    article_id: int = Field(index=True)
    matched_at: datetime = Field(default_factory=_utcnow)
    notified: bool = False


class UserProfile(SQLModel, table=True):
    """Per-user learning profile (replaces user_profile.json)."""

    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, index=True)
    profile_json: str = "{}"
    updated_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Engine helper
# ---------------------------------------------------------------------------

_engine = None


def _migrate_db():
    """Add columns that don't exist yet (lightweight migration)."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()

        def _add_column_if_missing(table: str, column: str, col_type: str):
            cursor.execute(f"PRAGMA table_info({table})")
            cols = {row[1] for row in cursor.fetchall()}
            if column not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                conn.commit()

        _add_column_if_missing("article", "alert_acknowledged_at", "DATETIME")
        _add_column_if_missing("statuschange", "user_id", "INTEGER")
        _add_column_if_missing("watchlist", "user_id", "INTEGER")

        # Composite indexes for query performance
        _composite_indexes = [
            "CREATE INDEX IF NOT EXISTS ix_article_source ON article(source)",
            "CREATE INDEX IF NOT EXISTS ix_article_language ON article(language)",
            "CREATE INDEX IF NOT EXISTS ix_article_status_pub_date ON article(status, pub_date)",
            "CREATE INDEX IF NOT EXISTS ix_article_status_ack ON article(status, alert_acknowledged_at)",
            "CREATE INDEX IF NOT EXISTS ix_article_pub_date_score ON article(pub_date, relevance_score)",
            "CREATE INDEX IF NOT EXISTS ix_article_specialty_pub_date ON article(specialty, pub_date)",
            "CREATE INDEX IF NOT EXISTS ix_wm_wl_matched ON watchlistmatch(watchlist_id, matched_at)",
        ]
        for sql in _composite_indexes:
            try:
                cursor.execute(sql)
            except Exception as exc:
                logger.debug("Index creation skipped: %s", exc)
        conn.commit()
    finally:
        conn.close()


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
        _migrate_db()
    return _engine


def get_session() -> Session:
    return Session(get_engine())


# ---------------------------------------------------------------------------
# FTS5 Full-Text Search
# ---------------------------------------------------------------------------

_FTS5_COLUMNS = (
    "title", "abstract", "summary_de", "highlight_tags",
    "authors", "journal", "mesh_terms", "specialty", "source",
)


def init_fts5():
    """Create FTS5 virtual table if it doesn't exist. Idempotent.

    Drops and recreates if the column set has changed.
    """
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='article_fts'"
        )
        if cursor.fetchone() is not None:
            cursor.execute("PRAGMA table_info(article_fts)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            expected_cols = set(_FTS5_COLUMNS)
            if not expected_cols.issubset(existing_cols):
                cursor.execute("DROP TABLE article_fts")
                conn.commit()
            else:
                create_fts5_triggers()
                return
        cursor.execute(f"""
            CREATE VIRTUAL TABLE article_fts USING fts5(
                {', '.join(_FTS5_COLUMNS)},
                content='article', content_rowid='id'
            )
        """)
        conn.commit()
    finally:
        conn.close()
    create_fts5_triggers()


def create_fts5_triggers():
    """Create SQLite triggers to keep article_fts in sync with the article table.

    Uses external-content FTS5 protocol: deletions require inserting the
    *old* column values with the special 'delete' command, then re-inserting
    the new values.

    All triggers use CREATE TRIGGER IF NOT EXISTS for idempotency.
    """
    import sqlite3

    cols = ", ".join(_FTS5_COLUMNS)
    new_vals = ", ".join(f"new.{c}" for c in _FTS5_COLUMNS)
    old_vals = ", ".join(f"old.{c}" for c in _FTS5_COLUMNS)

    # Columns relevant for the UPDATE trigger condition
    update_cols = ("title", "abstract", "summary_de", "highlight_tags")
    update_of = ", ".join(update_cols)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()

        # AFTER INSERT — index newly added articles
        cursor.execute(f"""
            CREATE TRIGGER IF NOT EXISTS articles_ai
            AFTER INSERT ON article BEGIN
                INSERT INTO article_fts(rowid, {cols})
                VALUES (new.id, {new_vals});
            END;
        """)

        # AFTER UPDATE — re-index when key text columns change
        cursor.execute(f"""
            CREATE TRIGGER IF NOT EXISTS articles_au
            AFTER UPDATE OF {update_of} ON article BEGIN
                INSERT INTO article_fts(article_fts, rowid, {cols})
                VALUES ('delete', old.id, {old_vals});
                INSERT INTO article_fts(rowid, {cols})
                VALUES (new.id, {new_vals});
            END;
        """)

        # AFTER DELETE — remove from index
        cursor.execute(f"""
            CREATE TRIGGER IF NOT EXISTS articles_ad
            AFTER DELETE ON article BEGIN
                INSERT INTO article_fts(article_fts, rowid, {cols})
                VALUES ('delete', old.id, {old_vals});
            END;
        """)

        conn.commit()
    finally:
        conn.close()


def populate_fts5():
    """Populate/rebuild the FTS5 index from the article table. Idempotent.

    With external-content FTS5, SELECT count(*) reads the content table,
    so we probe the actual inverted index with a MATCH query instead.
    """
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='article_fts'"
        )
        if cursor.fetchone() is None:
            return
        cursor.execute("SELECT count(*) FROM article")
        if cursor.fetchone()[0] == 0:
            return
        needs_rebuild = True
        try:
            cursor.execute(
                "SELECT rowid FROM article_fts "
                "WHERE article_fts MATCH 'a OR e OR i OR s OR t' LIMIT 1"
            )
            if cursor.fetchone() is not None:
                needs_rebuild = False
        except Exception as exc:
            logger.debug("FTS5 probe failed (will rebuild): %s", exc)
        if needs_rebuild:
            cursor.execute(
                "INSERT INTO article_fts(article_fts) VALUES('rebuild')"
            )
            conn.commit()
    finally:
        conn.close()


def fts5_search(query: str, limit: int = 500) -> list:
    """Search articles using FTS5. Returns article IDs ordered by BM25 rank.

    Returns empty list if FTS5 table doesn't exist or query is invalid
    (graceful fallback to ILIKE in caller).
    """
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='article_fts'"
        )
        if cursor.fetchone() is None:
            return []
        try:
            cursor.execute(
                "SELECT rowid FROM article_fts "
                "WHERE article_fts MATCH ? "
                "ORDER BY bm25(article_fts) LIMIT ?",
                (query, limit),
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []
    finally:
        conn.close()

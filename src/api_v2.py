"""Lumio API v2 — Full REST API for Next.js frontend migration.

Exposes all data queries as JSON endpoints with caching, CORS, and auth.
Replaces the Streamlit data layer (components/helpers.py) with a proper API.

Run: uvicorn src.api_v2:app --reload --host 0.0.0.0 --port 8000
Docs: http://localhost:8000/docs
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from cachetools import TTLCache

from src.models import (
    Article, Source, StatusChange, Watchlist, WatchlistMatch,
    FeedStatus, get_engine, get_session,
)
from src.config import FEED_REGISTRY, SCORE_THRESHOLD_HIGH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_debug = os.getenv("LUMIO_DEBUG", "").lower() in ("1", "true", "yes")

app = FastAPI(
    title="Lumio API",
    version="2.0",
    description="Medical Evidence Dashboard API",
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
)

# CORS — allow Next.js dev + Vercel production
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://*.vercel.app",
]
# Add custom origin from env if set
_custom_origin = os.getenv("CORS_ORIGIN")
if _custom_origin:
    _ALLOWED_ORIGINS.append(_custom_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://lumio(-[a-z0-9]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Ensure DB exists on startup
get_engine()

# ---------------------------------------------------------------------------
# Caching (in-memory, TTL-based)
# ---------------------------------------------------------------------------
_cache_articles = TTLCache(maxsize=50, ttl=180)
_cache_stats = TTLCache(maxsize=5, ttl=600)
_cache_kpis = TTLCache(maxsize=5, ttl=600)
_cache_unique = TTLCache(maxsize=20, ttl=900)
_cache_trends = TTLCache(maxsize=5, ttl=600)
_cache_saisonal = TTLCache(maxsize=20, ttl=3600)

# ---------------------------------------------------------------------------
# Auth (reused from api.py)
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)
API_TOKEN = os.getenv("API_TOKEN", "")


def _verify_token(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)):
    if not API_TOKEN:
        logger.warning("API_TOKEN not configured — mutation endpoints are unprotected")
        return
    if not creds or creds.credentials != API_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
_RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))
_RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))
_rate_limit_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(endpoint: str):
    now = time.monotonic()
    calls = _rate_limit_log[endpoint]
    _rate_limit_log[endpoint] = [t for t in calls if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_log[endpoint]) >= _RATE_LIMIT_MAX:
        raise HTTPException(429, f"Rate limit: max {_RATE_LIMIT_MAX}/{_RATE_LIMIT_WINDOW}s")
    _rate_limit_log[endpoint].append(now)


# ---------------------------------------------------------------------------
# Pydantic models (response schemas)
# ---------------------------------------------------------------------------

class ArticleResponse(BaseModel):
    id: Optional[int]
    title: str
    abstract: Optional[str]
    url: str
    source: str
    journal: Optional[str]
    pub_date: Optional[date]
    authors: Optional[str]
    doi: Optional[str]
    study_type: Optional[str]
    language: Optional[str]
    source_category: Optional[str]
    relevance_score: float
    score_breakdown: Optional[str]
    scoring_version: Optional[str]
    specialty: Optional[str]
    summary_de: Optional[str]
    highlight_tags: Optional[str]
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class StatusUpdate(BaseModel):
    new_status: str


class WatchlistCreate(BaseModel):
    name: str
    keywords: str
    specialty_filter: Optional[str] = None
    min_score: float = 0.0


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

@app.get("/api/articles", response_model=List[ArticleResponse])
def get_articles(
    specialties: Optional[str] = Query(None, description="Comma-separated"),
    sources: Optional[str] = Query(None),
    source_categories: Optional[str] = Query(None),
    min_score: float = 0.0,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search_query: str = "",
    status_filter: str = "ALL",
    language: Optional[str] = None,
    limit: int = Query(500, le=2000),
):
    """Fetch articles with filters."""
    from sqlmodel import select, col, func
    from src.models import fts5_search

    with get_session() as session:
        stmt = select(Article)

        if specialties:
            stmt = stmt.where(col(Article.specialty).in_(specialties.split(",")))
        if sources:
            stmt = stmt.where(col(Article.source).in_(sources.split(",")))
        if source_categories:
            stmt = stmt.where(col(Article.source_category).in_(source_categories.split(",")))
        if min_score > 0:
            stmt = stmt.where(Article.relevance_score >= min_score)
        if date_from:
            stmt = stmt.where(Article.pub_date >= date_from)
        if date_to:
            stmt = stmt.where(Article.pub_date <= date_to)
        if language and language not in ("Alle", "all"):
            lang_code = "de" if language.lower() in ("deutsch", "de") else "en"
            stmt = stmt.where(Article.language == lang_code)
        if status_filter and status_filter != "ALL":
            stmt = stmt.where(Article.status == status_filter)

        # FTS5 search
        if search_query:
            fts_ids = fts5_search(search_query, limit=limit)
            if fts_ids:
                stmt = stmt.where(col(Article.id).in_(fts_ids))
            else:
                stmt = stmt.where(Article.title.ilike(f"%{search_query}%"))

        stmt = stmt.order_by(Article.relevance_score.desc()).limit(limit)
        articles = session.exec(stmt).all()
        return [ArticleResponse.from_orm(a) for a in articles]


@app.patch("/api/articles/{article_id}/status", dependencies=[Depends(_verify_token)])
def update_status(article_id: int, body: StatusUpdate):
    """Change article status with audit logging."""
    with get_session() as session:
        article = session.get(Article, article_id)
        if not article:
            raise HTTPException(404, "Article not found")

        old_status = article.status
        article.status = body.new_status

        session.add(StatusChange(
            article_id=article_id,
            old_status=old_status,
            new_status=body.new_status,
        ))
        session.commit()
        return {"ok": True, "old": old_status, "new": body.new_status}


# ---------------------------------------------------------------------------
# Stats & KPIs
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    """Dashboard statistics."""
    cache_key = "stats"
    if cache_key in _cache_stats:
        return _cache_stats[cache_key]

    from sqlmodel import select, func, col
    with get_session() as session:
        total = session.exec(select(func.count(Article.id))).one()
        hq = session.exec(
            select(func.count(Article.id)).where(Article.relevance_score >= SCORE_THRESHOLD_HIGH)
        ).one()
        alerts = session.exec(
            select(func.count(Article.id)).where(Article.status == "ALERT")
        ).one()
        saved = session.exec(
            select(func.count(Article.id)).where(Article.status == "SAVED")
        ).one()

    result = {"total": total, "hq": hq, "alerts": alerts, "saved": saved}
    _cache_stats[cache_key] = result
    return result


@app.get("/api/dashboard-kpis")
def get_dashboard_kpis():
    """Dashboard hero bar KPIs with sparkline."""
    cache_key = "kpis"
    if cache_key in _cache_kpis:
        return _cache_kpis[cache_key]

    from sqlmodel import select, func, col
    today = date.today()
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)

    with get_session() as session:
        this_week = session.exec(
            select(func.count(Article.id)).where(Article.pub_date >= week_ago)
        ).one()
        last_week = session.exec(
            select(func.count(Article.id)).where(
                Article.pub_date >= two_weeks_ago,
                Article.pub_date < week_ago,
            )
        ).one()

        avg_score_week = session.exec(
            select(func.avg(Article.relevance_score)).where(Article.pub_date >= week_ago)
        ).one() or 0
        avg_score_last = session.exec(
            select(func.avg(Article.relevance_score)).where(
                Article.pub_date >= two_weeks_ago,
                Article.pub_date < week_ago,
            )
        ).one() or 0

        unreviewed_hq = session.exec(
            select(func.count(Article.id)).where(
                Article.status == "NEW",
                Article.relevance_score >= SCORE_THRESHOLD_HIGH,
            )
        ).one()

        # Sparkline: 30-day article counts (single GROUP BY query)
        thirty_days_ago = today - timedelta(days=29)
        rows = session.exec(
            select(Article.pub_date, func.count(Article.id))
            .where(Article.pub_date >= thirty_days_ago)
            .group_by(Article.pub_date)
        ).all()
        day_counts = {r[0]: r[1] for r in rows}
        sparkline = [day_counts.get(today - timedelta(days=29 - i), 0) for i in range(30)]

    wow_delta = round((this_week - last_week) / max(last_week, 1) * 100) if last_week else 0

    result = {
        "this_week": this_week,
        "last_week": last_week,
        "wow_delta": wow_delta,
        "avg_score_week": round(float(avg_score_week), 1),
        "avg_score_last": round(float(avg_score_last), 1),
        "unreviewed_hq": unreviewed_hq,
        "sparkline": sparkline,
    }
    _cache_kpis[cache_key] = result
    return result


@app.get("/api/unique-values/{column}")
def get_unique_values(column: str):
    """Distinct non-null values for a column (for dropdowns)."""
    cache_key = f"unique_{column}"
    if cache_key in _cache_unique:
        return _cache_unique[cache_key]

    allowed = {"specialty", "source", "journal", "language", "study_type", "source_category"}
    if column not in allowed:
        raise HTTPException(400, f"Column must be one of: {allowed}")

    col_attr = getattr(Article, column)
    with get_session() as session:
        from sqlmodel import select
        results = session.exec(
            select(col_attr).where(col_attr.isnot(None)).distinct()
        ).all()
        values = sorted([r for r in results if r])

    _cache_unique[cache_key] = values
    return values


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.get("/api/alerts/unacknowledged")
def get_unacknowledged_alerts():
    """Recent safety alerts that haven't been acknowledged."""
    from sqlmodel import select, col
    cutoff = date.today() - timedelta(days=30)
    with get_session() as session:
        articles = session.exec(
            select(Article).where(
                Article.status == "ALERT",
                Article.alert_acknowledged_at.is_(None),
                Article.pub_date >= cutoff,
            ).order_by(Article.pub_date.desc())
        ).all()
        return [ArticleResponse.from_orm(a) for a in articles]


@app.post("/api/alerts/acknowledge", dependencies=[Depends(_verify_token)])
def acknowledge_alerts(article_ids: List[int]):
    """Mark alerts as acknowledged."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        for aid in article_ids:
            article = session.get(Article, aid)
            if article:
                article.alert_acknowledged_at = now
        session.commit()
    return {"ok": True, "acknowledged": len(article_ids)}


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

@app.get("/api/trends")
def get_trends():
    """Themen-Radar: computed trend clusters."""
    cache_key = "trends"
    if cache_key in _cache_trends:
        return _cache_trends[cache_key]

    from src.processing.trends import compute_trends
    trends = compute_trends()
    result = [
        {
            "topic_label": t.topic_label,
            "smart_label_de": getattr(t, "smart_label_de", t.topic_label),
            "count_current": t.count_current,
            "count_previous": t.count_previous,
            "growth_rate": t.growth_rate,
            "avg_score": t.avg_score,
            "top_journals": t.top_journals,
            "specialties": t.specialties,
            "momentum": t.momentum,
            "evidence_trend": getattr(t, "evidence_trend", "stable"),
            "is_cross_specialty": getattr(t, "is_cross_specialty", False),
            "article_ids": t.article_ids[:10],
        }
        for t in trends
    ]
    _cache_trends[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Congresses
# ---------------------------------------------------------------------------

@app.get("/api/congresses")
def get_congresses():
    """All congresses with article counts."""
    from src.processing.kongresse import load_congresses
    congresses = load_congresses(with_articles=True)
    return [
        {
            "id": c.id, "name": c.name, "short": c.short,
            "date_start": c.date_start.isoformat(), "date_end": c.date_end.isoformat(),
            "city": c.city, "country": c.country, "venue": c.venue,
            "website": c.website, "specialty": c.specialty,
            "congress_type": c.congress_type, "cme_points": c.cme_points,
            "estimated_attendees": c.estimated_attendees,
            "abstract_deadline": c.abstract_deadline.isoformat() if c.abstract_deadline else None,
            "description_de": c.description_de,
            "keywords": c.keywords,
            "related_article_count": c.related_article_count,
            "days_until": c.days_until,
            "status": c.status,
        }
        for c in congresses
    ]


@app.post("/api/congresses/{congress_id}/favorite", dependencies=[Depends(_verify_token)])
def toggle_congress_favorite(congress_id: str, user_id: int = 1):
    """Toggle congress favorite."""
    from src.processing.kongresse import toggle_favorite
    is_fav = toggle_favorite(congress_id, user_id)
    return {"ok": True, "congress_id": congress_id, "is_favorite": is_fav}


# ---------------------------------------------------------------------------
# Watchlists
# ---------------------------------------------------------------------------

@app.get("/api/watchlists")
def get_watchlists():
    """Active watchlists with match counts."""
    from src.processing.watchlist import get_active_watchlists, get_watchlist_counts
    watchlists = get_active_watchlists()
    counts = get_watchlist_counts()
    return [
        {
            "id": w.id, "name": w.name, "keywords": w.keywords,
            "specialty_filter": w.specialty_filter, "min_score": w.min_score,
            "match_count": counts.get(w.id, 0),
        }
        for w in watchlists
    ]


@app.post("/api/watchlists", dependencies=[Depends(_verify_token)])
def create_watchlist(body: WatchlistCreate):
    """Create a new watchlist."""
    with get_session() as session:
        wl = Watchlist(
            name=body.name, keywords=body.keywords,
            specialty_filter=body.specialty_filter,
            min_score=body.min_score,
        )
        session.add(wl)
        session.commit()
        session.refresh(wl)
        return {"ok": True, "id": wl.id}


@app.delete("/api/watchlists/{watchlist_id}", dependencies=[Depends(_verify_token)])
def delete_watchlist(watchlist_id: int):
    """Delete a watchlist and its matches."""
    from sqlmodel import delete
    with get_session() as session:
        session.exec(delete(WatchlistMatch).where(WatchlistMatch.watchlist_id == watchlist_id))
        wl = session.get(Watchlist, watchlist_id)
        if wl:
            session.delete(wl)
        session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Saisonal
# ---------------------------------------------------------------------------

@app.get("/api/saisonal/hero")
def saisonal_hero(month: int = 0):
    cache_key = f"hero_{month}"
    if cache_key in _cache_saisonal:
        return _cache_saisonal[cache_key]
    from src.processing.redaktionskalender import get_seasonal_hero
    result = get_seasonal_hero(month=month)
    _cache_saisonal[cache_key] = result
    return result


@app.get("/api/saisonal/timeline")
def saisonal_timeline(year: int = 0):
    cache_key = f"timeline_{year}"
    if cache_key in _cache_saisonal:
        return _cache_saisonal[cache_key]
    from src.processing.redaktionskalender import get_timeline_data
    result = get_timeline_data(year=year)
    _cache_saisonal[cache_key] = result
    return result


@app.get("/api/saisonal/clusters")
def saisonal_clusters(month: int = 0):
    cache_key = f"clusters_{month}"
    if cache_key in _cache_saisonal:
        return _cache_saisonal[cache_key]
    from src.processing.redaktionskalender import get_cluster_cards
    result = get_cluster_cards(month=month)
    _cache_saisonal[cache_key] = result
    return result


@app.get("/api/saisonal/awareness")
def saisonal_awareness(days_ahead: int = 90):
    cache_key = f"awareness_{days_ahead}"
    if cache_key in _cache_saisonal:
        return _cache_saisonal[cache_key]
    from src.processing.redaktionskalender import get_upcoming_awareness
    result = get_upcoming_awareness(days_ahead=days_ahead)
    _cache_saisonal[cache_key] = result
    return result


@app.get("/api/saisonal/regulatory")
def saisonal_regulatory(days_ahead: int = 90):
    cache_key = f"regulatory_{days_ahead}"
    if cache_key in _cache_saisonal:
        return _cache_saisonal[cache_key]
    from src.processing.redaktionskalender import get_upcoming_regulatory
    result = get_upcoming_regulatory(days_ahead=days_ahead)
    _cache_saisonal[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Feed Admin
# ---------------------------------------------------------------------------

@app.get("/api/feeds/status")
def get_feed_status():
    """Feed health status for all configured feeds."""
    from src.processing.feed_monitor import get_all_feed_statuses
    statuses = get_all_feed_statuses()

    # Enrich with registry info
    result = []
    for name, cfg in FEED_REGISTRY.items():
        db_status = next((s for s in statuses if s["feed_name"] == name), {})
        result.append({
            "name": name,
            "url": cfg.url,
            "feed_type": cfg.feed_type,
            "source_category": cfg.source_category,
            "language": cfg.language,
            "active": cfg.active,
            "status_color": db_status.get("status_color", "yellow"),
            "articles_last_24h": db_status.get("articles_last_24h", 0),
            "articles_last_7d": db_status.get("articles_last_7d", 0),
            "last_error": db_status.get("last_error"),
            "consecutive_failures": db_status.get("consecutive_failures", 0),
        })
    return result


# ---------------------------------------------------------------------------
# Pipeline & Digest (protected, from api.py)
# ---------------------------------------------------------------------------

@app.post("/api/pipeline/run", dependencies=[Depends(_verify_token)])
async def trigger_pipeline(days_back: int = 1):
    """Run the full ingestion + scoring pipeline."""
    _check_rate_limit("pipeline/run")
    from src.pipeline import run_pipeline
    try:
        stats = await run_pipeline(days_back=days_back)
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(500, "Pipeline execution failed")
    return {"status": "ok", "stats": stats}


@app.post("/api/digest/send", dependencies=[Depends(_verify_token)])
def trigger_digest(email: str = ""):
    """Send the daily digest email."""
    from src.digest import send_digest
    # Only allow sending to the configured digest email (prevent relay abuse)
    allowed_email = os.getenv("DIGEST_EMAIL", "")
    to = email if email == allowed_email else allowed_email
    if not to:
        raise HTTPException(400, "No recipient configured")
    ok = send_digest(to_email=to)
    if not ok:
        raise HTTPException(500, "Digest send failed")
    return {"status": "ok", "sent_to": to}

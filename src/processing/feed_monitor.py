"""Feed health monitoring — tracks fetch success/failure and article counts."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import select

from src.models import FeedStatus, Article, get_engine, get_session

logger = logging.getLogger(__name__)


def update_feed_status(feed_name: str, success: bool, article_count: int = 0, error: Optional[str] = None):
    """Update the status of a feed after a fetch attempt."""
    get_engine()
    now = datetime.now(timezone.utc)

    with get_session() as session:
        status = session.exec(
            select(FeedStatus).where(FeedStatus.feed_name == feed_name)
        ).first()

        if not status:
            status = FeedStatus(feed_name=feed_name)
            session.add(status)

        if success:
            status.last_successful_fetch = now
            status.consecutive_failures = 0
            status.last_error = None
        else:
            status.consecutive_failures += 1
            status.last_error = str(error)[:500] if error else "Unknown error"
            status.last_error_at = now

            if status.consecutive_failures >= 3:
                logger.warning(
                    "Feed %s has %d consecutive failures — last error: %s",
                    feed_name, status.consecutive_failures, status.last_error,
                )

        session.commit()


def refresh_article_counts():
    """Refresh article counts (last 24h, last 7d) for all feeds."""
    get_engine()
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    with get_session() as session:
        # Get all feed statuses
        statuses = session.exec(select(FeedStatus)).all()

        for status in statuses:
            count_24h = session.exec(
                select(Article.id).where(
                    Article.source == status.feed_name,
                    Article.created_at >= day_ago,
                )
            ).all()
            count_7d = session.exec(
                select(Article.id).where(
                    Article.source == status.feed_name,
                    Article.created_at >= week_ago,
                )
            ).all()

            status.articles_last_24h = len(count_24h)
            status.articles_last_7d = len(count_7d)

        session.commit()


def get_all_feed_statuses() -> list[dict]:
    """Get feed status for all feeds, suitable for UI display.

    Returns list of dicts with: feed_name, status_color, last_fetch,
    articles_24h, articles_7d, last_error, active.
    """
    get_engine()
    now = datetime.now(timezone.utc)

    def _aware(dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime is timezone-aware (UTC) for safe comparison."""
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    with get_session() as session:
        statuses = session.exec(select(FeedStatus)).all()

        result = []
        for s in statuses:
            last_fetch = _aware(s.last_successful_fetch)
            # Determine status color
            if not s.active:
                color = "gray"  # Deaktiviert
            elif s.consecutive_failures >= 3:
                color = "red"  # 3+ failures
            elif last_fetch and (now - last_fetch) > timedelta(hours=72):
                color = "red"  # >72h since last fetch
            elif last_fetch and (now - last_fetch) > timedelta(hours=24):
                color = "yellow"  # 24-72h
            elif s.last_error:
                color = "yellow"  # Has recent error
            elif s.last_successful_fetch:
                color = "green"  # All good
            else:
                color = "yellow"  # Never fetched yet

            result.append({
                "feed_name": s.feed_name,
                "status_color": color,
                "last_successful_fetch": s.last_successful_fetch,
                "articles_last_24h": s.articles_last_24h,
                "articles_last_7d": s.articles_last_7d,
                "consecutive_failures": s.consecutive_failures,
                "last_error": s.last_error,
                "active": s.active,
            })

        return result

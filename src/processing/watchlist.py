"""Watchlist matching engine for Lumio.

Matches articles against user-defined watchlists using keyword search
on title + abstract + summary. Same pattern as detect_alert() in classifier.py.
"""

import html as html_mod
import logging
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlmodel import select, col

from src.models import (
    Article, Watchlist, WatchlistMatch, get_session,
)

logger = logging.getLogger(__name__)


def match_article(article: Article, watchlist: Watchlist) -> bool:
    """Check if a single article matches a watchlist's criteria."""
    # Build searchable text from all relevant fields
    text = " ".join(
        (field or "").lower()
        for field in [
            article.title,
            article.abstract,
            article.summary_de,
            article.highlight_tags,
            article.mesh_terms,
        ]
    )

    # Parse comma-separated keywords
    keywords = [kw.strip().lower() for kw in watchlist.keywords.split(",") if kw.strip()]
    if not keywords:
        return False

    # At least one keyword must match (substring check — supports German
    # compound words like "Herzinsuffizienztherapie" containing "Herzinsuffizienz")
    if not any(kw in text for kw in keywords):
        return False

    # Optional: specialty filter
    if watchlist.specialty_filter and article.specialty != watchlist.specialty_filter:
        return False

    # Optional: minimum score
    if watchlist.min_score > 0 and article.relevance_score < watchlist.min_score:
        return False

    return True


def match_watchlists(
    articles: list[Article],
    watchlists: Optional[list[Watchlist]] = None,
) -> dict[int, list[Article]]:
    """Match articles against all active watchlists.

    Returns dict mapping watchlist_id -> list of matching articles.
    """
    if watchlists is None:
        watchlists = get_active_watchlists()

    matches: dict[int, list[Article]] = {}
    for wl in watchlists:
        matched = [a for a in articles if match_article(a, wl)]
        if matched:
            matches[wl.id] = matched
    return matches


def store_matches(matches: dict[int, list[Article]]):
    """Store new watchlist matches in the DB (skips duplicates)."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        for wl_id, articles in matches.items():
            # Get existing matches to avoid duplicates
            existing = set(
                session.exec(
                    select(WatchlistMatch.article_id).where(
                        WatchlistMatch.watchlist_id == wl_id
                    )
                ).all()
            )
            new_count = 0
            for article in articles:
                if article.id not in existing:
                    session.add(WatchlistMatch(
                        watchlist_id=wl_id,
                        article_id=article.id,
                        matched_at=now,
                    ))
                    new_count += 1

            # Update last_match_at on the watchlist
            if new_count > 0:
                wl = session.get(Watchlist, wl_id)
                if wl:
                    wl.last_match_at = now

        session.commit()

    total = sum(len(arts) for arts in matches.values())
    logger.info("Watchlist matching: %d new matches across %d watchlists", total, len(matches))


def get_active_watchlists(user_id: Optional[int] = None) -> list[Watchlist]:
    """Get active watchlists, optionally filtered by user_id."""
    with get_session() as session:
        stmt = select(Watchlist).where(Watchlist.active == True)
        if user_id is not None:
            stmt = stmt.where(Watchlist.user_id == user_id)
        return list(session.exec(stmt).all())


def get_watchlist_matches(watchlist_id: int, limit: int = 50) -> list[Article]:
    """Get matched articles for a specific watchlist, ordered by match date."""
    with get_session() as session:
        stmt = (
            select(Article)
            .join(WatchlistMatch, WatchlistMatch.article_id == Article.id)
            .where(WatchlistMatch.watchlist_id == watchlist_id)
            .order_by(col(WatchlistMatch.matched_at).desc())
            .limit(limit)
        )
        return list(session.exec(stmt).all())


def get_watchlist_counts(user_id: Optional[int] = None) -> dict[int, int]:
    """Get match counts per watchlist (for sidebar display)."""
    from sqlmodel import func
    with get_session() as session:
        stmt = select(
            WatchlistMatch.watchlist_id,
            func.count(WatchlistMatch.id),
        )
        if user_id is not None:
            stmt = stmt.join(Watchlist, Watchlist.id == WatchlistMatch.watchlist_id).where(
                Watchlist.user_id == user_id
            )
        stmt = stmt.group_by(WatchlistMatch.watchlist_id)
        results = session.exec(stmt).all()
        return {wl_id: count for wl_id, count in results}


def _build_watchlist_email_html(
    watchlist: Watchlist,
    articles: list[Article],
) -> str:
    """Build HTML email body for a watchlist notification."""
    top_articles = sorted(articles, key=lambda a: a.relevance_score, reverse=True)[:5]
    rows = ""
    for a in top_articles:
        score = a.relevance_score
        title = html_mod.escape(a.title)
        rows += (
            f'<tr><td style="padding:6px 8px;text-align:right;font-weight:bold">'
            f'{score:.0f}</td>'
            f'<td style="padding:6px 8px">{title}</td></tr>\n'
        )

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                 max-width:600px;margin:0 auto;padding:20px;color:#1e293b">
        <h2 style="color:#2563eb">Lumio Watchlist: {html_mod.escape(watchlist.name)}</h2>
        <p>{len(articles)} neue Treffer gefunden.</p>
        <table style="width:100%;border-collapse:collapse;margin-top:12px">
            <tr style="border-bottom:2px solid #e2e8f0">
                <th style="text-align:right;padding:6px 8px">Score</th>
                <th style="text-align:left;padding:6px 8px">Titel</th>
            </tr>
            {rows}
        </table>
        <p style="color:#94a3b8;font-size:12px;margin-top:20px">
            Lumio Watchlist-Benachrichtigung
        </p>
    </body>
    </html>
    """


def send_watchlist_notification(
    watchlist: Watchlist,
    articles: list[Article],
) -> bool:
    """Send email notification for watchlist matches.

    Uses the same SMTP env vars as the digest (SMTP_HOST, SMTP_USER, etc.).
    Returns True on success, False otherwise.
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)
    to_email = os.getenv("ALERT_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, to_email]):
        logger.debug("SMTP not configured — watchlist notification skipped.")
        return False

    body = _build_watchlist_email_html(watchlist, articles)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"Lumio Watchlist: {watchlist.name} — {len(articles)} neue Treffer"
    )
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(
            "Watchlist notification sent for '%s' (%d matches)",
            watchlist.name, len(articles),
        )
        return True
    except Exception as exc:
        logger.error("Failed to send watchlist notification: %s", exc)
        return False


def _mark_matches_notified(watchlist_id: int, article_ids: list[int]):
    """Set notified=True on WatchlistMatch rows after email is sent."""
    with get_session() as session:
        stmt = select(WatchlistMatch).where(
            WatchlistMatch.watchlist_id == watchlist_id,
            col(WatchlistMatch.article_id).in_(article_ids),
        )
        for match in session.exec(stmt).all():
            match.notified = True
        session.commit()


def _notify_watchlists(
    matches: dict[int, list[Article]],
    watchlists: list[Watchlist],
):
    """Send email notifications for watchlists that have notify_email=True."""
    wl_by_id = {wl.id: wl for wl in watchlists}

    for wl_id, articles in matches.items():
        wl = wl_by_id.get(wl_id)
        if wl is None or not wl.notify_email:
            continue

        if send_watchlist_notification(wl, articles):
            _mark_matches_notified(wl_id, [a.id for a in articles])


def run_watchlist_matching(article_count: int = 0):
    """Full watchlist matching pipeline step: match + store + notify.

    Loads the most recent articles from DB to avoid DetachedInstanceError.
    Args:
        article_count: hint for how many articles to load (0 = last 1000).
    """
    watchlists = get_active_watchlists()
    if not watchlists:
        logger.info("No active watchlists, skipping matching")
        return

    limit = max(article_count, 1000)
    with get_session() as session:
        fresh_articles = session.exec(
            select(Article).order_by(col(Article.id).desc()).limit(limit)
        ).all()

        if not fresh_articles:
            logger.info("No articles in DB for watchlist matching")
            return

        matches = match_watchlists(fresh_articles, watchlists)
        if matches:
            store_matches(matches)
            _notify_watchlists(matches, watchlists)
        else:
            logger.info("No watchlist matches found")

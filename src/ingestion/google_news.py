"""Google News RSS ingestion for German medical news."""

import logging
from datetime import date

import feedparser
import httpx

from src.config import GOOGLE_NEWS_RSS
from src.models import Article

logger = logging.getLogger(__name__)


async def fetch_google_news(client: httpx.AsyncClient) -> list[Article]:
    """Fetch German medical news from Google News RSS."""
    articles: list[Article] = []

    try:
        resp = await client.get(GOOGLE_NEWS_RSS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except (httpx.HTTPError, Exception) as exc:
        logger.error("Google News RSS failed: %s", exc)
        return articles

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title:
            continue

        link = entry.get("link", "")

        pub_date = None
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if t:
            try:
                pub_date = date(t.tm_year, t.tm_mon, t.tm_mday)
            except Exception:
                pass

        # Google News often includes the source in the title as " - SourceName"
        source_hint = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            source_hint = parts[-1].strip()

        articles.append(
            Article(
                title=title,
                abstract=entry.get("summary", "") or None,
                url=link,
                source=f"Google News ({source_hint})" if source_hint else "Google News",
                journal="Google News",
                pub_date=pub_date,
                language="de",
            )
        )

    logger.info("Google News: fetched %d entries", len(articles))
    return articles

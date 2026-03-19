"""Google News RSS ingestion for German medical news."""

import logging
import re
from datetime import date

import feedparser
import httpx

from src.config import GOOGLE_NEWS_RSS_FEEDS
from src.models import Article

logger = logging.getLogger(__name__)


async def _fetch_single_feed(
    client: httpx.AsyncClient, feed_name: str, feed_url: str
) -> list[Article]:
    """Fetch a single Google News RSS feed."""
    articles: list[Article] = []

    try:
        resp = await client.get(feed_url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except (httpx.HTTPError, Exception) as exc:
        logger.error("Google News RSS '%s' failed: %s", feed_name, exc)
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

        # Strip HTML tags from Google News summaries
        abstract_raw = entry.get("summary", "") or ""
        if "<" in abstract_raw:
            abstract_raw = re.sub(r"<[^>]+>", "", abstract_raw).strip()
        abstract = abstract_raw or None

        articles.append(
            Article(
                title=title,
                abstract=abstract,
                url=link,
                source=f"Google News ({source_hint})" if source_hint else feed_name,
                journal="Google News",
                pub_date=pub_date,
                language="de",
            )
        )

    logger.info("%s: fetched %d entries", feed_name, len(articles))
    return articles


async def fetch_google_news(client: httpx.AsyncClient) -> list[Article]:
    """Fetch German medical news from all Google News RSS feeds."""
    all_articles: list[Article] = []
    seen_urls: set[str] = set()

    for feed_name, feed_url in GOOGLE_NEWS_RSS_FEEDS.items():
        articles = await _fetch_single_feed(client, feed_name, feed_url)
        for a in articles:
            if a.url not in seen_urls:
                seen_urls.add(a.url)
                all_articles.append(a)

    logger.info("Google News total: %d unique entries from %d feeds",
                len(all_articles), len(GOOGLE_NEWS_RSS_FEEDS))
    return all_articles

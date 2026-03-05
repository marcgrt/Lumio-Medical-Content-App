"""RSS feed ingestion for medical journals."""

import logging
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from src.config import RSS_FEEDS
from src.models import Article

logger = logging.getLogger(__name__)


def _parse_pub_date(entry: dict) -> Optional[date]:
    """Try to extract a publication date from a feed entry."""
    for field in ("published", "updated", "dc_date"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).date()
            except Exception:
                pass
    # feedparser's parsed struct
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return date(t.tm_year, t.tm_mon, t.tm_mday)
            except Exception:
                pass
    return None


async def fetch_rss_feeds(client: httpx.AsyncClient) -> list[Article]:
    """Fetch articles from all configured journal RSS feeds."""
    articles: list[Article] = []

    for source_name, feed_url in RSS_FEEDS.items():
        try:
            resp = await client.get(feed_url, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("RSS feed %s failed: %s", source_name, exc)
            continue

        count = 0
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue

            link = entry.get("link", "")
            abstract = entry.get("summary", "") or entry.get("description", "")
            # Strip HTML tags naively
            if "<" in abstract:
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            pub_date = _parse_pub_date(entry)
            doi = None
            # Some feeds include DOI in dc:identifier or prism:doi
            for key in ("prism_doi", "dc_identifier"):
                val = entry.get(key, "")
                if val and ("10." in val):
                    doi = val if val.startswith("10.") else val.split("10.", 1)[-1]
                    doi = "10." + doi if not doi.startswith("10.") else doi
                    break

            articles.append(
                Article(
                    title=title,
                    abstract=abstract[:5000] if abstract else None,
                    url=link,
                    source=source_name,
                    journal=source_name,
                    pub_date=pub_date,
                    authors=", ".join(
                        a.get("name", "") for a in entry.get("authors", [])
                    ) or None,
                    doi=doi,
                    language="de" if "ärzteblatt" in source_name.lower() else "en",
                )
            )
            count += 1

        logger.info("RSS %s: fetched %d entries", source_name, count)

    return articles

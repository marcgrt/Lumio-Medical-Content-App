"""Cochrane Library — systematic reviews (highest evidence level)."""

import logging
import re
from datetime import date
from typing import Optional

import feedparser
import httpx

from src.models import Article

logger = logging.getLogger(__name__)

COCHRANE_RSS_URL = (
    "https://www.cochranelibrary.com/cdsr/table-of-contents/rss.xml"
)


def _parse_pub_date(entry: dict):
    """Extract publication date from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return date(t.tm_year, t.tm_mon, t.tm_mday)
            except Exception:
                pass
    return None


def _extract_doi(entry: dict) -> Optional[str]:
    """Try to extract a DOI from the entry link or identifiers."""
    link = entry.get("link", "")
    # Cochrane links often contain the DOI path
    doi_match = re.search(r"(10\.\d{4,}/\S+)", link)
    if doi_match:
        # Clean trailing punctuation
        doi = doi_match.group(1).rstrip(".")
        return doi

    for key in ("prism_doi", "dc_identifier"):
        val = entry.get(key, "")
        if val and "10." in val:
            doi = val if val.startswith("10.") else "10." + val.split("10.", 1)[-1]
            return doi

    return None


async def fetch_cochrane(client: httpx.AsyncClient) -> list[Article]:
    """Fetch recent Cochrane systematic reviews."""
    articles: list[Article] = []

    try:
        resp = await client.get(COCHRANE_RSS_URL, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("Cochrane RSS feed failed: %s", exc)
        return articles

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title:
            continue

        link = entry.get("link", "")
        abstract = entry.get("summary", "") or entry.get("description", "")
        if "<" in abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        pub_date = _parse_pub_date(entry)
        doi = _extract_doi(entry)

        authors = ", ".join(
            a.get("name", "") for a in entry.get("authors", [])
        ) or None

        articles.append(
            Article(
                title=title,
                abstract=abstract[:5000] if abstract else None,
                url=link,
                source="Cochrane Library",
                journal="Cochrane Database of Systematic Reviews",
                pub_date=pub_date,
                authors=authors,
                doi=doi,
                study_type="Systematic Review",
                language="en",
            )
        )

    logger.info("Cochrane: fetched %d reviews", len(articles))
    return articles

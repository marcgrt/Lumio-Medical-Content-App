"""EMA (European Medicines Agency) — DHPC and safety referrals."""

import logging
import re
from datetime import date

import feedparser
import httpx

from src.models import Article

logger = logging.getLogger(__name__)

EMA_RSS_URL = "https://www.ema.europa.eu/en/news.xml"

# Keywords that indicate safety-relevant content (DHPC, referrals, recalls)
_SAFETY_KEYWORDS = [
    "dhpc", "direct healthcare professional communication",
    "safety referral", "pharmacovigilance",
    "recall", "withdrawal", "suspension",
    "contraindication", "risk", "adverse",
    "signal", "prac",
]


def _is_safety_related(title: str, summary: str) -> bool:
    """Return True if the entry appears to be a safety communication."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in _SAFETY_KEYWORDS)


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


async def fetch_ema(client: httpx.AsyncClient) -> list[Article]:
    """Fetch safety-related news from the EMA RSS feed."""
    articles: list[Article] = []

    try:
        resp = await client.get(EMA_RSS_URL, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("EMA RSS feed failed: %s", exc)
        return articles

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title:
            continue

        link = entry.get("link", "")
        abstract = entry.get("summary", "") or entry.get("description", "")
        if "<" in abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        # Focus on safety-relevant items
        if not _is_safety_related(title, abstract):
            continue

        pub_date = _parse_pub_date(entry)

        articles.append(
            Article(
                title=title,
                abstract=abstract[:5000] if abstract else None,
                url=link,
                source="EMA Safety",
                journal="European Medicines Agency",
                pub_date=pub_date,
                language="en",
            )
        )

    logger.info("EMA: fetched %d safety-related entries", len(articles))
    return articles

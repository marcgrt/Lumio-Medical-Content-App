"""RKI (Robert Koch Institut) — epidemiological bulletins and outbreak reports."""

import logging
import re
from datetime import date

import feedparser
import httpx

from src.models import Article

logger = logging.getLogger(__name__)

RKI_RSS_URL = (
    "https://www.rki.de/SiteGlobals/Functions/RSS/RSS-EpidBull.xml?nn=16776976"
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


async def fetch_rki(client: httpx.AsyncClient) -> list[Article]:
    """Fetch epidemiological bulletins and reports from the RKI RSS feed."""
    articles: list[Article] = []

    try:
        resp = await client.get(RKI_RSS_URL, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("RKI RSS feed failed: %s", exc)
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

        articles.append(
            Article(
                title=title,
                abstract=abstract[:5000] if abstract else None,
                url=link,
                source="RKI",
                journal="Robert Koch Institut",
                pub_date=pub_date,
                language="de",
            )
        )

    logger.info("RKI: fetched %d entries", len(articles))
    return articles

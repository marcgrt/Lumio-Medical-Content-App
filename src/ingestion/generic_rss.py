"""Generic RSS feed fetcher for new sources (Berufspolitik, Behörden, Fachgesellschaften).

Uses the FEED_REGISTRY to discover which feeds to fetch.
Handles feeds that are not covered by the legacy rss_feeds.py module.
"""

import logging
import re
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from src.config import FEED_REGISTRY, RSS_FEEDS, GOOGLE_NEWS_RSS_FEEDS
from src.models import Article

logger = logging.getLogger(__name__)

# Feeds already handled by other modules — don't double-fetch
_HANDLED_ELSEWHERE = (
    set(RSS_FEEDS.keys())
    | set(GOOGLE_NEWS_RSS_FEEDS.keys())
    | {
        "Europe PMC", "medRxiv", "bioRxiv", "WHO DON",
        "BfArM", "EMA", "Cochrane", "AWMF", "RKI",
        # Wave 3 / scrape-only sources (handled by dedicated scrapers later)
        "Medscape DE", "Medscape EN", "arznei-telegramm",
        # Scrape-only sources
        "DGIM", "DGK", "DEGAM", "AWMF Leitlinien",
    }
)


def _parse_pub_date(entry: dict) -> Optional[date]:
    """Extract publication date from feed entry."""
    for field in ("published", "updated", "dc_date"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).date()
            except Exception:
                pass
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return date(t.tm_year, t.tm_mon, t.tm_mday)
            except Exception:
                pass
    return None


async def fetch_generic_rss(client: httpx.AsyncClient) -> list[Article]:
    """Fetch articles from all RSS-based feeds in FEED_REGISTRY not handled elsewhere.

    This covers new sources like G-BA, IQWiG, KBV, Marburger Bund, Medical Tribune etc.
    """
    articles: list[Article] = []

    for name, cfg in FEED_REGISTRY.items():
        if name in _HANDLED_ELSEWHERE:
            continue
        if not cfg.active:
            logger.info("Generic RSS %s: skipped (inactive)", name)
            continue
        if cfg.feed_type not in ("rss",):
            continue

        try:
            resp = await client.get(cfg.url, timeout=25, follow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Generic RSS feed %s failed: %s", name, exc)
            continue

        count = 0
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue

            link = entry.get("link", "")
            abstract = entry.get("summary", "") or entry.get("description", "")
            if "<" in abstract:
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            pub_date = _parse_pub_date(entry)

            # Extract DOI if present (unlikely for Berufspolitik, but handle it)
            doi = None
            for key in ("prism_doi", "dc_identifier"):
                val = entry.get(key, "")
                if val and "10." in val:
                    doi = val if val.startswith("10.") else "10." + val.split("10.", 1)[-1]
                    break

            # G-BA: extract PDF link for Tragende Gründe if available
            full_text_url = None
            if "g-ba" in name.lower():
                for enc in entry.get("enclosures", []):
                    if enc.get("type", "").endswith("pdf"):
                        full_text_url = enc.get("href")
                        break
                for link_entry in entry.get("links", []):
                    if link_entry.get("type", "").endswith("pdf"):
                        full_text_url = link_entry.get("href")
                        break

            articles.append(
                Article(
                    title=title,
                    abstract=abstract[:5000] if abstract else None,
                    url=link,
                    source=name,
                    journal=name,
                    pub_date=pub_date,
                    authors=", ".join(
                        a.get("name", "") for a in entry.get("authors", [])
                    ) or None,
                    doi=doi,
                    language=cfg.language,
                    source_category=cfg.source_category,
                    full_text_url=full_text_url,
                )
            )
            count += 1

        logger.info("Generic RSS %s: fetched %d entries", name, count)

    return articles

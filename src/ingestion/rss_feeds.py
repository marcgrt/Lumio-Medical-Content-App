"""RSS feed ingestion for medical journals and news sources."""

import logging
import re
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from src.config import RSS_FEEDS, FEED_REGISTRY
from src.models import Article, FilteredArticle, derive_source_category

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Apotheke Adhoc pre-filter — drops pure industry/finance articles
# ---------------------------------------------------------------------------
ADHOC_SKIP_KEYWORDS = [
    "umsatz", "quartalszahlen", "börse", "aktie", "übernahme",
    "merger", "akquisition", "gewinn", "dividende", "marktkapitalisierung",
    "bilanz", "jahresbericht", "ipo", "investor", "geschäftsbericht",
]

ADHOC_CLINICAL_OVERRIDE = [
    "patient", "therapie", "wirkstoff", "zulassung", "studie", "arznei",
]


def should_skip_adhoc_article(title: str, abstract: str) -> bool:
    """Filter Apotheke-Adhoc articles with pure industry/finance content."""
    text = (title + " " + (abstract or "")).lower()
    has_finance = any(kw in text for kw in ADHOC_SKIP_KEYWORDS)
    has_clinical = any(kw in text for kw in ADHOC_CLINICAL_OVERRIDE)
    return has_finance and not has_clinical


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
    """Fetch articles from all configured journal RSS feeds.

    Skips feeds marked as inactive in FEED_REGISTRY.
    Applies Apotheke Adhoc pre-filter for finance/industry articles.
    """
    articles: list[Article] = []
    filtered_articles: list[FilteredArticle] = []
    adhoc_filtered = 0

    for source_name, feed_url in RSS_FEEDS.items():
        # Check if feed is active in registry
        registry_entry = FEED_REGISTRY.get(source_name)
        if registry_entry and not registry_entry.active:
            logger.info("RSS %s: skipped (inactive)", source_name)
            continue

        try:
            resp = await client.get(feed_url, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("RSS feed %s failed: %s", source_name, exc)
            continue

        # Determine source_category and language from registry
        source_category = registry_entry.source_category if registry_entry else derive_source_category(source_name)
        language = registry_entry.language if registry_entry else ("de" if any(
            s in source_name.lower() for s in ("ärzteblatt", "aerzteblatt", "ärzte zeitung",
            "aerztezeitung", "pharmazeutische zeitung", "apotheke adhoc", "medical tribune")
        ) else "en")

        is_adhoc = "apotheke adhoc" in source_name.lower()

        count = 0
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue

            link = entry.get("link", "")
            abstract = entry.get("summary", "") or entry.get("description", "")
            # Strip HTML tags
            if "<" in abstract:
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            # Apotheke Adhoc pre-filter
            if is_adhoc and should_skip_adhoc_article(title, abstract):
                adhoc_filtered += 1
                filtered_articles.append(FilteredArticle(
                    title=title,
                    url=link,
                    source=source_name,
                    filter_reason="adhoc_finance_filter",
                ))
                logger.debug("Adhoc pre-filter skipped: %s", title[:80])
                continue

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
                    language=language,
                    source_category=source_category,
                )
            )
            count += 1

        logger.info("RSS %s: fetched %d entries", source_name, count)

    if adhoc_filtered:
        logger.info("Apotheke Adhoc pre-filter: %d articles skipped (industry/finance)", adhoc_filtered)

    # Store filtered articles for editorial review
    if filtered_articles:
        try:
            from src.models import get_engine, get_session
            get_engine()
            with get_session() as session:
                for fa in filtered_articles:
                    session.add(fa)
                session.commit()
        except Exception as exc:
            logger.warning("Could not store filtered articles: %s", exc)

    return articles

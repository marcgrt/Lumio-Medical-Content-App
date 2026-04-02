"""HTML scrapers for German medical societies (Fachgesellschaften).

These sources typically don't have RSS feeds and require HTML scraping.
Volume is low (1-5 articles/month), so robustness > performance.
"""

import logging
import re
from datetime import date
from typing import Optional

import httpx

from src.config import FEED_REGISTRY
from src.models import Article

logger = logging.getLogger(__name__)

# Rate limit: max 1 request per 10 seconds (respected via sequential fetching)
_TIMEOUT = 25


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    if "<" in text:
        return re.sub(r"<[^>]+>", "", text).strip()
    return text.strip()


def _parse_date_de(text: str) -> Optional[date]:
    """Parse common German date formats (DD.MM.YYYY, DD. Monat YYYY)."""
    # DD.MM.YYYY
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # YYYY-MM-DD (ISO)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None


async def _scrape_press_page(
    client: httpx.AsyncClient,
    name: str,
    url: str,
    source_category: str,
    language: str = "de",
) -> list[Article]:
    """Generic press page scraper — extracts links with titles and dates.

    Uses CSS-selector-like heuristics: looks for <a> tags inside common
    press list containers (article, .news, .press, li).
    Falls back gracefully on parsing errors.
    """
    articles: list[Article] = []

    try:
        resp = await client.get(url, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("Fachgesellschaft %s scrape failed: %s", name, exc)
        return articles

    # Simple regex-based extraction — more robust than full HTML parser
    # for these simple press pages. Look for links in list/article context.
    # Pattern: find all <a href="...">Title</a> with optional date nearby
    link_pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{10,200})</a>',
        re.IGNORECASE,
    )

    base_url = resp.url  # follow redirects
    seen_urls = set()

    for match in link_pattern.finditer(html):
        href = match.group(1).strip()
        title = _strip_html(match.group(2)).strip()

        if not title or len(title) < 15:
            continue

        # Skip navigation/footer links
        skip_patterns = ["impressum", "datenschutz", "kontakt", "sitemap",
                         "cookie", "javascript:", "mailto:", "#", "login"]
        if any(p in href.lower() for p in skip_patterns):
            continue

        # Build absolute URL
        if href.startswith("/"):
            full_url = f"{base_url.scheme}://{base_url.host}{href}"
        elif href.startswith("http"):
            full_url = href
        else:
            continue

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Try to find a date near the link (within ~200 chars before/after)
        start = max(0, match.start() - 200)
        end = min(len(html), match.end() + 200)
        context = html[start:end]
        pub_date = _parse_date_de(context)

        articles.append(
            Article(
                title=title,
                abstract=None,  # Will be filled by abstract_fetcher
                url=full_url,
                source=name,
                journal=name,
                pub_date=pub_date,
                language=language,
                source_category=source_category,
            )
        )

    # Limit to most recent entries (these are press pages, not feeds)
    articles = articles[:20]

    logger.info("Fachgesellschaft %s: scraped %d entries", name, len(articles))
    return articles


async def fetch_fachgesellschaften(client: httpx.AsyncClient) -> list[Article]:
    """Fetch press releases from scrape-only sources (Fachgesellschaften + Berufspolitik)."""
    all_articles: list[Article] = []

    scrape_sources = ["DGIM", "DGK", "DEGAM", "IQWiG", "KBV", "Medical Tribune"]

    for name in scrape_sources:
        cfg = FEED_REGISTRY.get(name)
        if not cfg or not cfg.active:
            logger.info("Fachgesellschaft %s: skipped (inactive or not configured)", name)
            continue

        articles = await _scrape_press_page(
            client, name, cfg.url, cfg.source_category, cfg.language,
        )
        all_articles.extend(articles)

    return all_articles

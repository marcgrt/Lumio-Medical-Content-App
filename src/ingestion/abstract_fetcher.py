"""Fetch missing abstracts by scraping article pages.

Google News articles (and others) often arrive without abstracts, which
degrades scoring and summarization.  This module enriches those articles
by fetching the actual page and extracting the main text from meta tags
or the HTML body.
"""

import asyncio
import logging
import re
from html.parser import HTMLParser
from typing import Optional

import httpx

from src.models import Article

logger = logging.getLogger(__name__)

MAX_ABSTRACT_LENGTH = 5000
_REQUEST_TIMEOUT = 15  # seconds per request

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Lightweight HTML body-text extractor (no external dependency)
# ---------------------------------------------------------------------------

class _BodyTextExtractor(HTMLParser):
    """Extract visible text from <p> tags, ignoring scripts/styles."""

    _SKIP_TAGS = frozenset({"script", "style", "noscript", "nav", "footer", "header"})

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_p = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "p" and self._skip_depth == 0:
            self._in_p = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "p":
            self._in_p = False

    def handle_data(self, data: str) -> None:
        if self._in_p and self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self, max_words: int = 500) -> str:
        words: list[str] = []
        for chunk in self._chunks:
            words.extend(chunk.split())
            if len(words) >= max_words:
                break
        return " ".join(words[:max_words])


# ---------------------------------------------------------------------------
# Meta-tag extraction helpers
# ---------------------------------------------------------------------------

_META_PATTERN = re.compile(
    r'<meta\s[^>]*?(?:'
    r'(?:name|property)\s*=\s*["\'](?:og:description|description|article:description|twitter:description)["\']'
    r'[^>]*?content\s*=\s*["\']([^"\']{20,})["\']'
    r'|'
    r'content\s*=\s*["\']([^"\']{20,})["\']'
    r'[^>]*?(?:name|property)\s*=\s*["\'](?:og:description|description|article:description|twitter:description)["\']'
    r')',
    re.IGNORECASE | re.DOTALL,
)


def _extract_meta_description(html: str) -> Optional[str]:
    """Try to pull a description from common meta tags."""
    # Only search in the first 50 kB (meta tags live in <head>)
    head = html[:50_000]
    match = _META_PATTERN.search(head)
    if match:
        text = (match.group(1) or match.group(2) or "").strip()
        if len(text) >= 20:
            return text
    return None


def _extract_body_text(html: str) -> Optional[str]:
    """Fall back to extracting ~500 words from <p> tags."""
    parser = _BodyTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return None
    text = parser.get_text(max_words=500)
    return text if len(text) >= 40 else None


def _extract_abstract(html: str) -> Optional[str]:
    """Extract an abstract from raw HTML, trying meta tags first."""
    text = _extract_meta_description(html)
    if not text:
        text = _extract_body_text(html)
    if text:
        return text[:MAX_ABSTRACT_LENGTH]
    return None


# ---------------------------------------------------------------------------
# Async fetching
# ---------------------------------------------------------------------------

async def _fetch_one(
    client: httpx.AsyncClient,
    article: Article,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Fetch the article page and enrich its abstract in-place.

    Returns True if an abstract was successfully extracted.
    """
    async with semaphore:
        try:
            resp = await client.get(
                article.url,
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=True,
            )
            if resp.status_code in (403, 401, 451):
                # Paywall or forbidden — skip silently
                return False
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.debug("abstract_fetcher: skip %s — %s", article.url, exc)
            return False

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return False

        abstract = _extract_abstract(resp.text)
        if abstract:
            article.abstract = abstract
            return True
        return False


async def fetch_abstracts(
    articles: list[Article],
    max_workers: int = 10,
) -> list[Article]:
    """Enrich articles that are missing abstracts by fetching their pages.

    Only articles where ``article.abstract`` is None or empty are fetched.
    The original list is returned (modified in-place) for convenience.
    """
    need_fetch = [a for a in articles if not a.abstract]
    if not need_fetch:
        logger.info("abstract_fetcher: all %d articles already have abstracts", len(articles))
        return articles

    logger.info(
        "abstract_fetcher: fetching abstracts for %d / %d articles (max_workers=%d)",
        len(need_fetch), len(articles), max_workers,
    )

    semaphore = asyncio.Semaphore(max_workers)
    async with httpx.AsyncClient(
        headers={"User-Agent": _BROWSER_UA},
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *(_fetch_one(client, a, semaphore) for a in need_fetch),
            return_exceptions=True,
        )

    fetched = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if isinstance(r, Exception))
    if failed:
        logger.warning("abstract_fetcher: %d unexpected errors during fetch", failed)
    logger.info(
        "abstract_fetcher: enriched %d / %d articles with abstracts",
        fetched, len(need_fetch),
    )
    return articles

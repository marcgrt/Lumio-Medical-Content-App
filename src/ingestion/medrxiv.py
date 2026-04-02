"""medRxiv / bioRxiv API client."""

import logging
from datetime import date, timedelta

import httpx

from src.config import MEDRXIV_API_BASE, BIORXIV_API_BASE
from src.models import Article

logger = logging.getLogger(__name__)


async def _fetch_rxiv(
    client: httpx.AsyncClient,
    base_url: str,
    source_name: str,
    days_back: int = 1,
) -> list[Article]:
    """Fetch recent preprints from medRxiv or bioRxiv."""
    end = date.today()
    start = end - timedelta(days=days_back)
    url = f"{base_url}/{start.isoformat()}/{end.isoformat()}/0/json"

    articles: list[Article] = []
    try:
        resp = await client.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("%s request failed: %s", source_name, exc)
        return articles

    collection = data.get("collection", [])
    if not collection:
        msg = data.get("messages", [{}])[0]
        logger.warning(
            "%s returned 0 articles for %s → %s (API message: %s)",
            source_name, start.isoformat(), end.isoformat(), msg,
        )
        return articles

    for item in collection:
        pub_date = None
        raw = item.get("date")
        if raw:
            try:
                pub_date = date.fromisoformat(raw)
            except ValueError:
                pass

        doi = item.get("doi", "")
        articles.append(
            Article(
                title=item.get("title", "").strip(),
                abstract=item.get("abstract", ""),
                url=f"https://doi.org/{doi}" if doi else "",
                source=source_name,
                journal=source_name,
                pub_date=pub_date,
                authors=item.get("authors", ""),
                doi=doi or None,
                study_type="Preprint",
                language="en",
            )
        )

    logger.info("%s: fetched %d preprints", source_name, len(articles))
    return articles


async def fetch_medrxiv(
    client: httpx.AsyncClient, days_back: int = 1
) -> list[Article]:
    return await _fetch_rxiv(client, MEDRXIV_API_BASE, "medRxiv", days_back)


async def fetch_biorxiv(
    client: httpx.AsyncClient, days_back: int = 1
) -> list[Article]:
    return await _fetch_rxiv(client, BIORXIV_API_BASE, "bioRxiv", days_back)

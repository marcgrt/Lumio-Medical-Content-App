"""WHO Disease Outbreak News client."""

import logging
from datetime import date

import httpx

from src.config import WHO_DON_API
from src.models import Article

logger = logging.getLogger(__name__)


async def fetch_who_don(client: httpx.AsyncClient) -> list[Article]:
    """Fetch recent Disease Outbreak News from the WHO API."""
    articles: list[Article] = []

    try:
        resp = await client.get(WHO_DON_API, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("WHO DON API failed: %s", exc)
        return articles

    items = data.get("value", [])
    for item in items[:30]:  # limit to most recent 30
        pub_date = None
        raw = item.get("PublicationDate") or item.get("DatePublished")
        if raw:
            try:
                pub_date = date.fromisoformat(raw[:10])
            except ValueError:
                pass

        title = item.get("Title", "").strip()
        if not title:
            continue

        url = item.get("UrlName", "")
        if url and not url.startswith("http"):
            url = f"https://www.who.int/emergencies/disease-outbreak-news/{url}"

        articles.append(
            Article(
                title=title,
                abstract=item.get("Summary", "") or item.get("Description", ""),
                url=url,
                source="WHO Disease Outbreak News",
                journal="WHO Disease Outbreak News",
                pub_date=pub_date,
                language="en",
            )
        )

    logger.info("WHO DON: fetched %d items", len(articles))
    return articles

"""WHO Disease Outbreak News client."""

import logging
from datetime import date, timedelta

import httpx

from src.config import WHO_DON_API
from src.models import Article

logger = logging.getLogger(__name__)

# Only keep items published within this many days.
_MAX_AGE_DAYS = 30


async def fetch_who_don(client: httpx.AsyncClient) -> list[Article]:
    """Fetch recent Disease Outbreak News from the WHO API."""
    articles: list[Article] = []
    cutoff = date.today() - timedelta(days=_MAX_AGE_DAYS)

    # The WHO API is OData-based; request only recent items server-side.
    params = {
        "$filter": f"PublicationDate ge {cutoff.isoformat()}T00:00:00Z",
        "$orderby": "PublicationDate desc",
    }

    try:
        resp = await client.get(
            WHO_DON_API, params=params, timeout=30, follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("WHO DON API failed: %s", exc)
        return articles

    items = data.get("value", [])
    for item in items:
        # --- parse publication date ------------------------------------------
        pub_date = None
        raw = item.get("PublicationDate") or item.get("DatePublished")
        if raw:
            try:
                # Handles both "2025-03-01" and "2025-03-01T00:00:00Z" formats.
                pub_date = date.fromisoformat(raw[:10])
            except ValueError:
                pass

        # Client-side guard: skip items older than the cutoff even if the
        # server ignored the $filter parameter.
        if pub_date is not None and pub_date < cutoff:
            continue

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

    logger.info("WHO DON: fetched %d items (cutoff %s)", len(articles), cutoff)
    return articles

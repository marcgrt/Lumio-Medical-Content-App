"""Europe PMC REST API client."""

import logging
from datetime import date, timedelta

import httpx

from src.config import EUROPE_PMC_BASE, EUROPE_PMC_PAGE_SIZE
from src.models import Article

logger = logging.getLogger(__name__)


def _build_query(days_back: int = 1) -> str:
    """Build Europe PMC query for recent medical articles."""
    end = date.today()
    start = end - timedelta(days=days_back)
    return (
        f'src:med AND LANG:"eng" '
        f"AND FIRST_PDATE:[{start.isoformat()} TO {end.isoformat()}]"
    )


async def fetch_europe_pmc(
    client: httpx.AsyncClient,
    days_back: int = 1,
    max_results: int = 100,
) -> list[Article]:
    """Fetch recent articles from Europe PMC."""
    query = _build_query(days_back)
    articles: list[Article] = []
    cursor_mark = "*"

    while len(articles) < max_results:
        params = {
            "query": query,
            "format": "json",
            "pageSize": min(EUROPE_PMC_PAGE_SIZE, max_results - len(articles)),
            "cursorMark": cursor_mark,
            "resultType": "core",
        }

        try:
            resp = await client.get(EUROPE_PMC_BASE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Europe PMC request failed: %s", exc)
            break

        results = data.get("resultList", {}).get("result", [])
        if not results:
            break

        for r in results:
            pub_date = None
            raw_date = r.get("firstPublicationDate")
            if raw_date:
                try:
                    pub_date = date.fromisoformat(raw_date)
                except ValueError:
                    pass

            mesh_list = r.get("meshHeadingList", {}).get("meshHeading", [])
            mesh_terms = ", ".join(
                m.get("descriptorName", "") for m in mesh_list
            ) if mesh_list else None

            articles.append(
                Article(
                    title=r.get("title", "").strip(),
                    abstract=r.get("abstractText", ""),
                    url=f"https://europepmc.org/article/MED/{r.get('pmid', '')}",
                    source="Europe PMC",
                    journal=r.get("journalTitle", ""),
                    pub_date=pub_date,
                    authors=r.get("authorString", ""),
                    doi=r.get("doi"),
                    study_type=r.get("pubTypeList", {}).get("pubType", [None])[0]
                    if r.get("pubTypeList", {}).get("pubType")
                    else None,
                    mesh_terms=mesh_terms,
                    language="en" if r.get("language", "eng") == "eng" else r.get("language"),
                )
            )

        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor_mark:
            break
        cursor_mark = next_cursor

    logger.info("Europe PMC: fetched %d articles", len(articles))
    return articles

"""AWMF (Arbeitsgemeinschaft der Wissenschaftlichen Medizinischen Fachgesellschaften)
— German clinical guidelines (Leitlinien).

Primary: RSS feed from awmf.org. Fallback: scrape the register listing page.
"""

import logging
import re
from datetime import date

import feedparser
import httpx

from src.models import Article

logger = logging.getLogger(__name__)

AWMF_RSS_URL = (
    "https://www.awmf.org/?tx_awmfev_pi5%5Bcategory%5D=2&type=100"
    "&cHash=a3e2ec82427046f4fe5f5021ac0fcb9f"
)
AWMF_SEARCH_URL = "https://register.awmf.org/de/leitlinien/aktuelle-leitlinien"
AWMF_BASE = "https://register.awmf.org"


def _parse_date_de(text: str):
    """Parse a German-format date string like '01.03.2026' or '2026-03-01'."""
    text = text.strip()
    # ISO format
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    # DD.MM.YYYY
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


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


async def _fetch_awmf_rss(client: httpx.AsyncClient) -> list[Article]:
    """Primary: fetch from AWMF RSS feed."""
    articles: list[Article] = []
    resp = await client.get(AWMF_RSS_URL, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)

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
                source="AWMF Leitlinien",
                journal="AWMF",
                pub_date=pub_date,
                study_type="Clinical Guideline",
                language="de",
            )
        )
    return articles


async def _fetch_awmf_scrape(client: httpx.AsyncClient) -> list[Article]:
    """Fallback: scrape the guideline listing page."""
    articles: list[Article] = []
    resp = await client.get(AWMF_SEARCH_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text

    pattern = re.compile(
        r'<a[^>]+href="(/de/leitlinien/detail/ll/[\d\-]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    seen_urls: set[str] = set()
    for match in pattern.finditer(html):
        path = match.group(1).strip()
        raw_title = match.group(2).strip()
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        if not title or len(title) < 10:
            continue
        url = f"{AWMF_BASE}{path}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        pub_date = None
        context = html[max(0, match.start() - 200):match.end() + 200]
        date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", context)
        if date_match:
            pub_date = _parse_date_de(date_match.group(1))

        articles.append(
            Article(
                title=title,
                abstract=None,
                url=url,
                source="AWMF Leitlinien",
                journal="AWMF",
                pub_date=pub_date,
                study_type="Clinical Guideline",
                language="de",
            )
        )
    return articles


async def fetch_awmf(client: httpx.AsyncClient) -> list[Article]:
    """Fetch German clinical guidelines from AWMF (RSS first, scrape fallback)."""
    try:
        articles = await _fetch_awmf_rss(client)
        if articles:
            logger.info("AWMF (RSS): fetched %d guidelines", len(articles))
            return articles
    except Exception as exc:
        logger.warning("AWMF RSS feed failed: %s, trying scrape fallback", exc)

    try:
        articles = await _fetch_awmf_scrape(client)
        logger.info("AWMF (scrape): fetched %d guidelines", len(articles))
        return articles
    except Exception as exc:
        logger.warning("AWMF scrape fallback also failed: %s", exc)
        return []

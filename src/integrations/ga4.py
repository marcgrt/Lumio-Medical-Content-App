"""Google Analytics 4 integration for LUMIO Signal.

Pulls user behavior signals from GA4:
- Null-Treffer-Suchen (searches with no results)
- Bounce-Signale (high bounce rate pages)
- Top-Suchbegriffe (most searched terms)
- Leseabbrüche (pages with low engagement time)

Requires:
- GA4 Property ID in env var LUMIO_GA4_PROPERTY_ID
- Service Account JSON in env var LUMIO_GA4_CREDENTIALS_PATH
  (or the file at PROJECT_ROOT/credentials/ga4-service-account.json)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from src.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROPERTY_ID = os.getenv("LUMIO_GA4_PROPERTY_ID", "")
_CREDENTIALS_PATH = os.getenv(
    "LUMIO_GA4_CREDENTIALS_PATH",
    str(PROJECT_ROOT / "credentials" / "ga4-service-account.json"),
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NullSearch:
    """A search term that returned no results on esanum."""
    term: str
    session_count: int
    date_range: str  # e.g. "7d"


@dataclass
class BounceSignal:
    """A page with high bounce rate (users leave quickly)."""
    page_path: str
    page_title: str
    sessions: int
    bounce_rate: float  # 0.0-1.0
    avg_engagement_seconds: float


@dataclass
class TopSearch:
    """A frequently searched term on esanum."""
    term: str
    search_count: int
    results_shown: bool  # True if results were displayed


@dataclass
class EngagementDrop:
    """A page where users leave early (low engagement time)."""
    page_path: str
    page_title: str
    sessions: int
    avg_engagement_seconds: float
    expected_engagement_seconds: float  # Based on word count / content type


@dataclass
class GA4Report:
    """Aggregated GA4 signals for the Lücken-Detektor."""
    null_searches: list[NullSearch] = field(default_factory=list)
    bounce_signals: list[BounceSignal] = field(default_factory=list)
    top_searches: list[TopSearch] = field(default_factory=list)
    engagement_drops: list[EngagementDrop] = field(default_factory=list)
    date_range_days: int = 7
    generated_at: Optional[date] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _get_client():
    """Create a GA4 BetaAnalyticsDataClient from service account credentials."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    if not Path(_CREDENTIALS_PATH).exists():
        raise FileNotFoundError(
            f"GA4 credentials not found at {_CREDENTIALS_PATH}. "
            f"Set LUMIO_GA4_CREDENTIALS_PATH or place the file at "
            f"credentials/ga4-service-account.json"
        )

    return BetaAnalyticsDataClient.from_service_account_json(_CREDENTIALS_PATH)


def _check_config() -> Optional[str]:
    """Check if GA4 is properly configured. Returns error message or None."""
    if not _PROPERTY_ID:
        return "LUMIO_GA4_PROPERTY_ID nicht gesetzt"
    if not Path(_CREDENTIALS_PATH).exists():
        return f"GA4 Credentials nicht gefunden: {_CREDENTIALS_PATH}"
    return None


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_null_searches(days: int = 7, limit: int = 20) -> list[NullSearch]:
    """Fetch content demand signals from 404 pages and referrer paths.

    esanum doesn't have standard GA4 site search, so we use 404 pages
    as proxy for "content users wanted but didn't find". Also fetches
    pages with the pageReferrer containing search terms.
    """
    from google.analytics.data_v1beta.types import (
        RunReportRequest, Dimension, Metric, DateRange,
        FilterExpression, Filter,
    )

    client = _get_client()

    # Strategy: Fetch pages that landed on /404 — the referrer path
    # often contains the topic the user was looking for
    request = RunReportRequest(
        property=f"properties/{_PROPERTY_ID}",
        dimensions=[
            Dimension(name="pageReferrer"),
            Dimension(name="pagePath"),
        ],
        metrics=[
            Metric(name="sessions"),
        ],
        date_ranges=[DateRange(
            start_date=f"{days}daysAgo",
            end_date="today",
        )],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                    value="404",
                ),
            )
        ),
        order_bys=[{"metric": {"metric_name": "sessions"}, "desc": True}],
        limit=100,
    )

    response = client.run_report(request)
    results = []
    seen_terms = set()
    for row in response.rows:
        referrer = row.dimension_values[0].value
        sessions = int(row.metric_values[0].value)

        # Extract meaningful term from referrer URL
        term = _extract_topic_from_url(referrer)
        if not term or term in seen_terms or sessions < 2:
            continue
        seen_terms.add(term)

        results.append(NullSearch(
            term=term,
            session_count=sessions,
            date_range=f"{days}d",
        ))

    logger.info("GA4: %d Nachfrage-Signale (404-Seiten) gefunden", len(results))
    return results[:limit]


def _extract_topic_from_url(url: str) -> str:
    """Extract a meaningful topic/search term from a referrer URL."""
    if not url or url in ("(not set)", "(direct)"):
        return ""
    import re
    from urllib.parse import urlparse, parse_qs

    try:
        parsed = urlparse(url)
    except Exception:
        return ""

    # Google search: extract 'q' parameter
    if "google" in parsed.netloc:
        q = parse_qs(parsed.query).get("q", [""])[0]
        return q.strip()

    # esanum internal: extract topic from path
    path = parsed.path.strip("/")
    if not path:
        return ""

    # Clean up path segments
    segments = [s for s in path.split("/") if s and s not in (
        "feeds", "posts", "fachbereichsseite", "fachportal",
        "de", "en", "api", "static", "assets",
    )]

    if segments:
        # Last meaningful segment is usually the topic
        topic = segments[-1].replace("-", " ").replace("_", " ")
        # Remove IDs and very short segments
        if len(topic) > 3 and not topic.isdigit():
            return topic.title()

    return ""


def fetch_bounce_signals(days: int = 7, min_sessions: int = 10, limit: int = 20) -> list[BounceSignal]:
    """Fetch pages with high bounce rates (>70%) and enough traffic.

    These are pages where users land but leave quickly without engaging.
    """
    from google.analytics.data_v1beta.types import (
        RunReportRequest, Dimension, Metric, DateRange,
        FilterExpression, Filter,
    )

    client = _get_client()

    # GA4 uses engagementRate (inverse of bounce) and userEngagementDuration
    request = RunReportRequest(
        property=f"properties/{_PROPERTY_ID}",
        dimensions=[
            Dimension(name="pagePath"),
            Dimension(name="pageTitle"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagementRate"),
            Metric(name="userEngagementDuration"),
        ],
        date_ranges=[DateRange(
            start_date=f"{days}daysAgo",
            end_date="today",
        )],
        order_bys=[{"metric": {"metric_name": "engagementRate"}, "desc": False}],  # Lowest engagement first
        limit=100,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        sessions = int(row.metric_values[0].value)
        if sessions < min_sessions:
            continue
        engagement_rate = float(row.metric_values[1].value)
        bounce_rate = 1.0 - engagement_rate  # Inverse
        if bounce_rate < 0.70:
            continue
        engagement_seconds = float(row.metric_values[2].value) / max(sessions, 1)

        results.append(BounceSignal(
            page_path=row.dimension_values[0].value,
            page_title=row.dimension_values[1].value[:100],
            sessions=sessions,
            bounce_rate=bounce_rate,
            avg_engagement_seconds=engagement_seconds,
        ))

    results.sort(key=lambda b: (-b.bounce_rate, -b.sessions))
    logger.info("GA4: %d Seiten mit hoher Bounce-Rate", len(results[:limit]))
    return results[:limit]


def fetch_top_searches(days: int = 7, limit: int = 30) -> list[TopSearch]:
    """Fetch most frequently searched terms on esanum."""
    from google.analytics.data_v1beta.types import (
        RunReportRequest, Dimension, Metric, DateRange,
    )

    client = _get_client()

    request = RunReportRequest(
        property=f"properties/{_PROPERTY_ID}",
        dimensions=[Dimension(name="searchTerm")],
        metrics=[
            Metric(name="sessions"),
        ],
        date_ranges=[DateRange(
            start_date=f"{days}daysAgo",
            end_date="today",
        )],
        order_bys=[{"metric": {"metric_name": "sessions"}, "desc": True}],
        limit=limit,
    )

    response = client.run_report(request)
    results = []
    for row in response.rows:
        term = row.dimension_values[0].value
        if term and term not in ("(not set)", "(not provided)"):
            results.append(TopSearch(
                term=term,
                search_count=int(row.metric_values[0].value),
                results_shown=True,  # GA4 doesn't distinguish this natively
            ))

    logger.info("GA4: %d Top-Suchbegriffe", len(results))
    return results


# ---------------------------------------------------------------------------
# Aggregated report
# ---------------------------------------------------------------------------

def fetch_ga4_report(days: int = 7) -> GA4Report:
    """Fetch all GA4 signals and return an aggregated report.

    Gracefully handles missing configuration or API errors.
    """
    config_error = _check_config()
    if config_error:
        logger.info("GA4 nicht konfiguriert: %s", config_error)
        return GA4Report(
            date_range_days=days,
            generated_at=date.today(),
            error=config_error,
        )

    report = GA4Report(
        date_range_days=days,
        generated_at=date.today(),
    )

    try:
        report.null_searches = fetch_null_searches(days=days)
    except Exception as exc:
        logger.warning("GA4 Null-Treffer-Suchen fehlgeschlagen: %s", exc)

    try:
        report.bounce_signals = fetch_bounce_signals(days=days)
    except Exception as exc:
        logger.warning("GA4 Bounce-Signale fehlgeschlagen: %s", exc)

    try:
        report.top_searches = fetch_top_searches(days=days)
    except Exception as exc:
        logger.warning("GA4 Top-Suchen fehlgeschlagen: %s", exc)

    return report

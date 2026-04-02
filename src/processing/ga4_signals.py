"""GA4 Signal Processing — fetches and stores user behavior signals.

Runs as part of the pipeline (Step 8) to keep demand signals fresh.
Stores aggregated signals in the GA4Signal DB table for use by:
- Lücken-Detektor (demand gaps)
- Insights dashboard (weekly comparisons)
- Scoring boost (future Ebene 2)
"""

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import select, col

from src.models import get_engine, get_session

logger = logging.getLogger(__name__)


def refresh_ga4_signals(days: int = 7) -> dict:
    """Fetch fresh GA4 data and store as JSON in GA4SignalCache.

    Called by the pipeline after article storage.
    Returns summary stats for pipeline logging.
    """
    try:
        from src.integrations.ga4 import fetch_ga4_report, _check_config
    except ImportError:
        logger.debug("GA4 module not available")
        return {"status": "not_available"}

    config_error = _check_config()
    if config_error:
        logger.info("GA4 nicht konfiguriert: %s", config_error)
        return {"status": "not_configured", "error": config_error}

    report = fetch_ga4_report(days=days)
    if report.error:
        logger.warning("GA4 Report fehlgeschlagen: %s", report.error)
        return {"status": "error", "error": report.error}

    # Store in DB
    _store_signal_cache("ga4_report", {
        "null_searches": [{"term": ns.term, "session_count": ns.session_count} for ns in report.null_searches],
        "top_searches": [{"term": ts.term, "search_count": ts.search_count} for ts in report.top_searches],
        "bounce_signals": [
            {"page_path": bs.page_path, "page_title": bs.page_title,
             "sessions": bs.sessions, "bounce_rate": bs.bounce_rate,
             "avg_engagement_seconds": bs.avg_engagement_seconds}
            for bs in report.bounce_signals
        ],
        "date_range_days": days,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })

    # Also fetch and store fachgebiet engagement data
    fachgebiet_data = _fetch_fachgebiet_engagement(days)
    if fachgebiet_data:
        _store_signal_cache("ga4_fachgebiet_engagement", fachgebiet_data)

    # Fetch peak hours
    peak_hours = _fetch_peak_hours(days)
    if peak_hours:
        _store_signal_cache("ga4_peak_hours", peak_hours)

    # Fetch device split
    device_data = _fetch_device_split(days)
    if device_data:
        _store_signal_cache("ga4_devices", device_data)

    stats = {
        "status": "ok",
        "null_searches": len(report.null_searches),
        "top_searches": len(report.top_searches),
        "bounce_signals": len(report.bounce_signals),
        "fachgebiete_tracked": len(fachgebiet_data.get("fachgebiete", [])) if fachgebiet_data else 0,
    }
    logger.info(
        "GA4 Signals: %d Null-Suchen, %d Top-Suchen, %d Bounce-Signale, %d Fachgebiete",
        stats["null_searches"], stats["top_searches"],
        stats["bounce_signals"], stats["fachgebiete_tracked"],
    )
    return stats


def _fetch_fachgebiet_engagement(days: int) -> Optional[dict]:
    """Fetch engagement per Fachgebiet from GA4."""
    try:
        from src.integrations.ga4 import _get_client, _PROPERTY_ID
        from google.analytics.data_v1beta.types import (
            RunReportRequest, Dimension, Metric, DateRange,
            FilterExpression, Filter,
        )

        client = _get_client()
        request = RunReportRequest(
            property=f"properties/{_PROPERTY_ID}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="userEngagementDuration"),
                Metric(name="engagementRate"),
            ],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="pagePath",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                        value="/feeds/",
                    ),
                )
            ),
            order_bys=[{"metric": {"metric_name": "sessions"}, "desc": True}],
            limit=50,
        )

        response = client.run_report(request)
        fachgebiete = []
        for row in response.rows:
            path = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            duration = float(row.metric_values[1].value)
            engagement = float(row.metric_values[2].value)
            avg_time = duration / max(sessions, 1)

            # Extract fachgebiet name from path
            name = _extract_fachgebiet_from_path(path)
            if name and sessions >= 10:
                fachgebiete.append({
                    "name": name,
                    "path": path,
                    "sessions": sessions,
                    "avg_engagement_seconds": round(avg_time, 1),
                    "engagement_rate": round(engagement, 3),
                })

        return {
            "fachgebiete": fachgebiete,
            "date_range_days": days,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("GA4 Fachgebiet-Engagement fehlgeschlagen: %s", exc)
        return None


def _extract_fachgebiet_from_path(path: str) -> str:
    """Extract Fachgebiet name from esanum URL path."""
    import re
    # Pattern: /fachbereichsseite-{name}/feeds/{name}/posts
    # or: /feeds/fachportal-{name}/posts
    m = re.search(r"fachbereichsseite-([^/]+)", path)
    if m:
        return m.group(1).replace("-", " ").title()
    m = re.search(r"fachportal-([^/]+)", path)
    if m:
        return m.group(1).replace("-", " ").title()
    m = re.search(r"/feeds/([^/]+)/posts", path)
    if m:
        name = m.group(1)
        if name not in ("kolumnen", "medizinische-news"):
            return name.replace("-", " ").title()
    return ""


def _fetch_peak_hours(days: int) -> Optional[dict]:
    """Fetch session distribution by hour."""
    try:
        from src.integrations.ga4 import _get_client, _PROPERTY_ID
        from google.analytics.data_v1beta.types import (
            RunReportRequest, Dimension, Metric, DateRange,
        )

        client = _get_client()
        request = RunReportRequest(
            property=f"properties/{_PROPERTY_ID}",
            dimensions=[Dimension(name="hour")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )

        response = client.run_report(request)
        hours = {}
        for row in response.rows:
            hours[int(row.dimension_values[0].value)] = int(row.metric_values[0].value)

        # Find peak hours
        sorted_hours = sorted(hours.items(), key=lambda x: -x[1])
        peak_hours = [h for h, _ in sorted_hours[:3]]

        return {
            "hours": hours,
            "peak_hours": peak_hours,
            "date_range_days": days,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("GA4 Peak Hours fehlgeschlagen: %s", exc)
        return None


def _fetch_device_split(days: int) -> Optional[dict]:
    """Fetch device category distribution."""
    try:
        from src.integrations.ga4 import _get_client, _PROPERTY_ID
        from google.analytics.data_v1beta.types import (
            RunReportRequest, Dimension, Metric, DateRange,
        )

        client = _get_client()
        request = RunReportRequest(
            property=f"properties/{_PROPERTY_ID}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )

        response = client.run_report(request)
        devices = {}
        total = 0
        for row in response.rows:
            cat = row.dimension_values[0].value
            count = int(row.metric_values[0].value)
            devices[cat] = count
            total += count

        return {
            "devices": devices,
            "total_sessions": total,
            "mobile_pct": round(devices.get("mobile", 0) / max(total, 1) * 100, 1),
            "desktop_pct": round(devices.get("desktop", 0) / max(total, 1) * 100, 1),
            "date_range_days": days,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("GA4 Device Split fehlgeschlagen: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Cache storage (uses TrendCache table for simplicity)
# ---------------------------------------------------------------------------

def _store_signal_cache(cache_key: str, data: dict):
    """Store GA4 signal data in the TrendCache table."""
    from src.models import TrendCache
    get_engine()
    with get_session() as session:
        existing = session.exec(
            select(TrendCache).where(TrendCache.cache_key == cache_key)
        ).first()
        if existing:
            existing.data_json = json.dumps(data, ensure_ascii=False, default=str)
            existing.computed_at = datetime.now(timezone.utc)
        else:
            session.add(TrendCache(
                cache_key=cache_key,
                data_json=json.dumps(data, ensure_ascii=False, default=str),
                computed_at=datetime.now(timezone.utc),
            ))
        session.commit()


def get_signal_cache(cache_key: str) -> Optional[dict]:
    """Retrieve cached GA4 signal data."""
    from src.models import TrendCache
    get_engine()
    with get_session() as session:
        cached = session.exec(
            select(TrendCache).where(TrendCache.cache_key == cache_key)
        ).first()
        if cached:
            try:
                return json.loads(cached.data_json)
            except (json.JSONDecodeError, TypeError):
                return None
    return None

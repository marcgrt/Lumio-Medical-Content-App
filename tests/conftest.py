"""Shared fixtures for Lumio tests."""

from datetime import date, timedelta
from dataclasses import dataclass, field

import pytest

from src.models import Article


# ---------------------------------------------------------------------------
# Article factory
# ---------------------------------------------------------------------------

def make_article(**kwargs) -> Article:
    """Create a test Article with sensible defaults."""
    defaults = {
        "title": "Test Article",
        "url": "https://example.com/test",
        "source": "PubMed",
        "journal": "Test Journal",
        "relevance_score": 50.0,
        "status": "NEW",
        "pub_date": date.today(),
        "language": "en",
        "study_type": "Original",
    }
    defaults.update(kwargs)
    return Article(**defaults)


def make_articles(n: int, **shared_kwargs) -> list:
    """Create n test articles with unique titles/urls."""
    return [
        make_article(
            title=f"Article {i}: {shared_kwargs.get('title', 'Test')}",
            url=f"https://example.com/{i}",
            id=i,
            **{k: v for k, v in shared_kwargs.items() if k != "title"},
        )
        for i in range(1, n + 1)
    ]


# ---------------------------------------------------------------------------
# TrendCluster factory
# ---------------------------------------------------------------------------

def make_trend(**kwargs):
    """Create a TrendCluster with defaults for testing."""
    from src.processing.trends import TrendCluster
    defaults = {
        "topic_label": "Test Trend",
        "article_ids": [1, 2, 3],
        "count_current": 5,
        "count_previous": 2,
        "growth_rate": 1.5,
        "avg_score": 70.0,
        "top_journals": ["NEJM"],
        "specialties": ["Kardiologie"],
        "momentum": "rising",
        "evidence_trend": "stable",
        "high_tier_ratio": 0.2,
        "is_cross_specialty": False,
    }
    defaults.update(kwargs)
    return TrendCluster(**defaults)

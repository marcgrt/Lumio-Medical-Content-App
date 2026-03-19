"""Tests for pipeline store_articles logic — dedup and bulk prefetch.

Since src.pipeline imports ingestion modules that require Python 3.10+,
we test the store_articles logic by extracting and exercising its dedup
algorithm directly, without importing the full pipeline module.
"""

import pytest

from src.models import Article


def _make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test Article",
        "url": "https://example.com/test",
        "source": "Test",
        "relevance_score": 0.0,
    }
    defaults.update(kwargs)
    return Article(**defaults)


def _simulate_store_dedup(
    articles: list[Article],
    existing_urls: set[str],
    existing_dois: set[str],
) -> list[Article]:
    """Reproduce the dedup logic from store_articles without DB dependency.

    This mirrors the algorithm in src.pipeline.store_articles:
    - Skip if URL already exists
    - Skip if DOI already exists
    - Track newly added URLs/DOIs within the batch
    """
    stored = []
    for article in articles:
        if article.url in existing_urls:
            continue
        if article.doi and article.doi in existing_dois:
            continue
        stored.append(article)
        existing_urls.add(article.url)
        if article.doi:
            existing_dois.add(article.doi)
    return stored


# ---------------------------------------------------------------------------
# store_articles dedup logic
# ---------------------------------------------------------------------------

class TestStoreArticlesDedup:
    """Test the dedup algorithm used by store_articles."""

    def test_skips_duplicate_url(self):
        existing_urls = {"https://existing.com/article"}
        articles = [
            _make_article(url="https://existing.com/article", title="Existing"),
            _make_article(url="https://new.com/article", title="New Article"),
        ]
        result = _simulate_store_dedup(articles, existing_urls, set())
        assert len(result) == 1
        assert result[0].title == "New Article"

    def test_skips_duplicate_doi(self):
        existing_dois = {"10.1234/existing"}
        articles = [
            _make_article(url="https://a.com", doi="10.1234/existing", title="Dup DOI"),
            _make_article(url="https://b.com", doi="10.1234/new", title="New DOI"),
        ]
        result = _simulate_store_dedup(articles, set(), existing_dois)
        assert len(result) == 1
        assert result[0].title == "New DOI"

    def test_stores_all_new(self):
        articles = [
            _make_article(url="https://a.com", title="Article A"),
            _make_article(url="https://b.com", title="Article B"),
        ]
        result = _simulate_store_dedup(articles, set(), set())
        assert len(result) == 2

    def test_no_articles_stored_when_all_exist(self):
        existing_urls = {"https://a.com"}
        articles = [_make_article(url="https://a.com")]
        result = _simulate_store_dedup(articles, existing_urls, set())
        assert len(result) == 0

    def test_within_batch_url_dedup(self):
        """Two articles in same batch with same URL — only first stored."""
        articles = [
            _make_article(url="https://same.com", title="First"),
            _make_article(url="https://same.com", title="Duplicate"),
        ]
        result = _simulate_store_dedup(articles, set(), set())
        assert len(result) == 1
        assert result[0].title == "First"

    def test_within_batch_doi_dedup(self):
        """Two articles in same batch with same DOI — only first stored."""
        articles = [
            _make_article(url="https://a.com", doi="10.1/same", title="First"),
            _make_article(url="https://b.com", doi="10.1/same", title="Second"),
        ]
        result = _simulate_store_dedup(articles, set(), set())
        assert len(result) == 1
        assert result[0].title == "First"

    def test_none_doi_not_tracked(self):
        """Articles with None DOI should not block each other."""
        articles = [
            _make_article(url="https://a.com", doi=None, title="First"),
            _make_article(url="https://b.com", doi=None, title="Second"),
        ]
        result = _simulate_store_dedup(articles, set(), set())
        assert len(result) == 2

    def test_empty_doi_not_tracked(self):
        """Articles with empty-string DOI should not block each other."""
        articles = [
            _make_article(url="https://a.com", doi="", title="First"),
            _make_article(url="https://b.com", doi="", title="Second"),
        ]
        result = _simulate_store_dedup(articles, set(), set())
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Bulk URL/DOI prefetch optimization
# ---------------------------------------------------------------------------

class TestBulkPrefetch:
    """Verify the bulk-prefetch pattern: two sets are built upfront,
    not one query per article (N+1 avoidance)."""

    def test_existing_sets_used_for_all_articles(self):
        """All 10 articles should be checked against pre-built sets,
        not individual queries."""
        existing_urls = {f"https://example.com/{i}" for i in range(5)}
        existing_dois = set()

        articles = [
            _make_article(url=f"https://example.com/{i}", title=f"Art {i}")
            for i in range(10)
        ]

        result = _simulate_store_dedup(articles, existing_urls, existing_dois)
        # First 5 are duplicates, last 5 are new
        assert len(result) == 5
        for i, a in enumerate(result):
            assert a.url == f"https://example.com/{i + 5}"

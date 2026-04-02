"""Tests for src.processing.dedup — deduplication logic."""

import pytest

from src.models import Article
from src.processing.dedup import deduplicate, _normalize_title, _similarity_ratio


def _make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test Article",
        "url": "https://example.com/test",
        "source": "Test",
        "relevance_score": 0.0,
    }
    defaults.update(kwargs)
    return Article(**defaults)


# ---------------------------------------------------------------------------
# Exact DOI dedup
# ---------------------------------------------------------------------------

class TestDOIDedup:
    def test_same_doi_removed(self):
        a1 = _make_article(title="Article A", url="https://a.com", doi="10.1234/abc")
        a2 = _make_article(title="Article B", url="https://b.com", doi="10.1234/abc")
        result = deduplicate([a1, a2])
        assert len(result) == 1
        assert result[0].title == "Article A"

    def test_different_doi_kept(self):
        a1 = _make_article(title="Meta-analysis of cardiovascular outcomes", url="https://a.com", doi="10.1234/abc")
        a2 = _make_article(title="Randomized trial of immunotherapy for melanoma", url="https://b.com", doi="10.1234/xyz")
        result = deduplicate([a1, a2])
        assert len(result) == 2

    def test_doi_case_insensitive(self):
        a1 = _make_article(title="Article A", url="https://a.com", doi="10.1234/ABC")
        a2 = _make_article(title="Article B", url="https://b.com", doi="10.1234/abc")
        result = deduplicate([a1, a2])
        assert len(result) == 1

    def test_none_doi_not_deduped(self):
        a1 = _make_article(title="Cardiovascular outcomes meta-analysis review", url="https://a.com", doi=None)
        a2 = _make_article(title="Immunotherapy checkpoint inhibitor melanoma trial", url="https://b.com", doi=None)
        result = deduplicate([a1, a2])
        assert len(result) == 2

    def test_empty_doi_not_deduped(self):
        a1 = _make_article(title="Cardiovascular outcomes meta-analysis review", url="https://a.com", doi="")
        a2 = _make_article(title="Immunotherapy checkpoint inhibitor melanoma trial", url="https://b.com", doi="")
        result = deduplicate([a1, a2])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Levenshtein title dedup
# ---------------------------------------------------------------------------

class TestTitleLevenshteinDedup:
    def test_identical_titles_removed(self):
        a1 = _make_article(title="Exact Same Title", url="https://a.com")
        a2 = _make_article(title="Exact Same Title", url="https://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1

    def test_near_identical_titles_removed(self):
        a1 = _make_article(title="Metformin in Type 2 Diabetes", url="https://a.com")
        a2 = _make_article(title="Metformin in Type 2 Diabete", url="https://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1

    def test_different_titles_kept(self):
        a1 = _make_article(title="Cardiology and Heart Failure", url="https://a.com")
        a2 = _make_article(title="Neurology and Brain Imaging", url="https://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 2

    def test_title_normalization_strips_punctuation(self):
        a1 = _make_article(title="Hello, World!", url="https://a.com")
        a2 = _make_article(title="Hello World", url="https://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1

    def test_title_normalization_case_insensitive(self):
        a1 = _make_article(title="UPPER CASE TITLE", url="https://a.com")
        a2 = _make_article(title="upper case title", url="https://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Different articles are kept
# ---------------------------------------------------------------------------

class TestDifferentArticlesKept:
    def test_completely_different_articles(self):
        articles = [
            _make_article(title="Meta-Analysis of GLP-1 in Diabetes", url="https://a.com", doi="10.1/a"),
            _make_article(title="Randomized Trial of Immunotherapy for Melanoma", url="https://b.com", doi="10.1/b"),
            _make_article(title="Stroke Prevention in Atrial Fibrillation", url="https://c.com", doi="10.1/c"),
        ]
        result = deduplicate(articles)
        assert len(result) == 3

    def test_empty_list(self):
        assert deduplicate([]) == []

    def test_single_article(self):
        a = _make_article(title="Solo Article", url="https://a.com")
        result = deduplicate([a])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestNormalizeTitle:
    def test_lowercase(self):
        assert _normalize_title("HELLO") == "hello"

    def test_strips_punctuation(self):
        assert _normalize_title("hello, world!") == "hello world"

    def test_collapses_whitespace(self):
        assert _normalize_title("hello   world") == "hello world"

    def test_strips_accents(self):
        result = _normalize_title("Über die Ärzte")
        assert "u" in result  # umlaut stripped


class TestSimilarityRatio:
    def test_identical(self):
        assert _similarity_ratio("abc", "abc") == 1.0

    def test_similar(self):
        assert _similarity_ratio("abc", "ab") > 0.6

    def test_completely_different(self):
        assert _similarity_ratio("abc", "xyz") < 0.5

    def test_empty_strings(self):
        assert _similarity_ratio("", "") == 1.0
        assert _similarity_ratio("abc", "") == 0.0

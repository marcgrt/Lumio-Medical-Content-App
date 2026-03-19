"""Tests for src.processing.watchlist — watchlist matching logic."""

import pytest

from src.models import Article, Watchlist
from src.processing.watchlist import match_article, match_watchlists


def _make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test Article",
        "url": "https://example.com/test",
        "source": "Test",
        "relevance_score": 50.0,
    }
    defaults.update(kwargs)
    return Article(**defaults)


def _make_watchlist(**kwargs) -> Watchlist:
    defaults = {
        "id": 1,
        "name": "Test Watchlist",
        "keywords": "diabetes",
        "min_score": 0.0,
        "active": True,
    }
    defaults.update(kwargs)
    return Watchlist(**defaults)


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------

class TestKeywordMatching:
    def test_keyword_in_title(self):
        a = _make_article(title="New diabetes treatment discovered")
        wl = _make_watchlist(keywords="diabetes")
        assert match_article(a, wl) is True

    def test_keyword_in_abstract(self):
        a = _make_article(title="A clinical study", abstract="Results for diabetes patients")
        wl = _make_watchlist(keywords="diabetes")
        assert match_article(a, wl) is True

    def test_keyword_in_summary(self):
        a = _make_article(title="Unrelated title", summary_de="Neue Erkenntnisse zu Diabetes")
        wl = _make_watchlist(keywords="diabetes")
        assert match_article(a, wl) is True

    def test_keyword_not_found(self):
        a = _make_article(title="Cardiology breakthrough", abstract="Heart failure study")
        wl = _make_watchlist(keywords="diabetes")
        assert match_article(a, wl) is False

    def test_keyword_case_insensitive(self):
        a = _make_article(title="DIABETES management update")
        wl = _make_watchlist(keywords="diabetes")
        assert match_article(a, wl) is True

    def test_keyword_word_boundary(self):
        """Keyword 'diabet' should not match via word boundary if full word is 'diabetes'."""
        a = _make_article(title="The diabetes study")
        wl = _make_watchlist(keywords="diabet")
        # 'diabet' is not a word boundary match inside 'diabetes'
        assert match_article(a, wl) is False

    def test_empty_keywords_no_match(self):
        a = _make_article(title="Anything here")
        wl = _make_watchlist(keywords="")
        assert match_article(a, wl) is False


# ---------------------------------------------------------------------------
# Multiple keywords (at least one must match)
# ---------------------------------------------------------------------------

class TestMultipleKeywords:
    def test_first_keyword_matches(self):
        a = _make_article(title="New diabetes guidelines")
        wl = _make_watchlist(keywords="diabetes, insulin, glp-1")
        assert match_article(a, wl) is True

    def test_second_keyword_matches(self):
        a = _make_article(title="Insulin resistance study")
        wl = _make_watchlist(keywords="diabetes, insulin, glp-1")
        assert match_article(a, wl) is True

    def test_none_match(self):
        a = _make_article(title="Heart failure in elderly")
        wl = _make_watchlist(keywords="diabetes, insulin, glp-1")
        assert match_article(a, wl) is False

    def test_whitespace_around_keywords(self):
        a = _make_article(title="Insulin dosing study")
        wl = _make_watchlist(keywords="  diabetes ,  insulin  , glp-1  ")
        assert match_article(a, wl) is True


# ---------------------------------------------------------------------------
# Specialty filter
# ---------------------------------------------------------------------------

class TestSpecialtyFilter:
    def test_matching_specialty(self):
        a = _make_article(
            title="Diabetes treatment",
            specialty="Diabetologie/Endokrinologie",
        )
        wl = _make_watchlist(
            keywords="diabetes",
            specialty_filter="Diabetologie/Endokrinologie",
        )
        assert match_article(a, wl) is True

    def test_non_matching_specialty(self):
        a = _make_article(
            title="Diabetes treatment",
            specialty="Kardiologie",
        )
        wl = _make_watchlist(
            keywords="diabetes",
            specialty_filter="Diabetologie/Endokrinologie",
        )
        assert match_article(a, wl) is False

    def test_no_specialty_filter(self):
        a = _make_article(title="Diabetes treatment", specialty="Kardiologie")
        wl = _make_watchlist(keywords="diabetes", specialty_filter=None)
        assert match_article(a, wl) is True


# ---------------------------------------------------------------------------
# Minimum score filter
# ---------------------------------------------------------------------------

class TestMinScoreFilter:
    def test_score_above_min(self):
        a = _make_article(title="Diabetes study", relevance_score=75.0)
        wl = _make_watchlist(keywords="diabetes", min_score=50.0)
        assert match_article(a, wl) is True

    def test_score_below_min(self):
        a = _make_article(title="Diabetes news brief", relevance_score=30.0)
        wl = _make_watchlist(keywords="diabetes", min_score=50.0)
        assert match_article(a, wl) is False

    def test_score_equal_to_min(self):
        a = _make_article(title="Diabetes study", relevance_score=50.0)
        wl = _make_watchlist(keywords="diabetes", min_score=50.0)
        assert match_article(a, wl) is True

    def test_zero_min_score(self):
        a = _make_article(title="Diabetes news", relevance_score=10.0)
        wl = _make_watchlist(keywords="diabetes", min_score=0.0)
        assert match_article(a, wl) is True


# ---------------------------------------------------------------------------
# match_watchlists (multi-watchlist)
# ---------------------------------------------------------------------------

class TestMatchWatchlists:
    def test_matches_correct_watchlists(self):
        articles = [
            _make_article(title="Diabetes trial results", url="https://a.com"),
            _make_article(title="Heart failure study", url="https://b.com"),
        ]
        watchlists = [
            _make_watchlist(id=1, keywords="diabetes"),
            _make_watchlist(id=2, keywords="heart"),
        ]
        result = match_watchlists(articles, watchlists)
        assert 1 in result
        assert 2 in result
        assert len(result[1]) == 1
        assert result[1][0].title == "Diabetes trial results"
        assert result[2][0].title == "Heart failure study"

    def test_no_matches(self):
        articles = [_make_article(title="Unrelated content", url="https://a.com")]
        watchlists = [_make_watchlist(id=1, keywords="diabetes")]
        result = match_watchlists(articles, watchlists)
        assert len(result) == 0

    def test_empty_watchlists(self):
        articles = [_make_article(title="Diabetes study", url="https://a.com")]
        result = match_watchlists(articles, watchlists=[])
        assert len(result) == 0

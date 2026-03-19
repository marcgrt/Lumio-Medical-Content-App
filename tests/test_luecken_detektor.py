"""Tests for src.processing.luecken_detektor — gap detection helpers."""

import pytest

from src.processing.luecken_detektor import (
    _extract_trending_keywords,
    _generate_coverage_suggestion,
)
from tests.conftest import make_article


# ---------------------------------------------------------------------------
# Trending Keyword Extraction
# ---------------------------------------------------------------------------

class TestExtractTrendingKeywords:
    def test_extracts_long_words(self):
        """Only words > 5 chars should be extracted."""
        articles = [
            make_article(title="Immunotherapy checkpoint inhibitors melanoma"),
        ]
        keywords = _extract_trending_keywords(articles, top_n=5)
        assert "immunotherapy" in keywords
        assert "checkpoint" in keywords
        assert "inhibitors" in keywords
        assert "melanoma" in keywords

    def test_short_words_excluded(self):
        articles = [make_article(title="The new drug for old age")]
        keywords = _extract_trending_keywords(articles, top_n=10)
        # All words <= 5 chars: "the", "new", "drug", "for", "old", "age"
        assert len(keywords) == 0

    def test_counts_frequency(self):
        """Most common words should appear first."""
        articles = [
            make_article(title="Diabetes treatment outcomes", url="u/1"),
            make_article(title="Diabetes management guidelines", url="u/2"),
            make_article(title="Cancer immunotherapy results", url="u/3"),
        ]
        keywords = _extract_trending_keywords(articles, top_n=3)
        # "diabetes" appears 2x, should be first
        assert keywords[0] == "diabetes"

    def test_highlight_tags_counted(self):
        articles = [
            make_article(title="Test Article", highlight_tags="Herzinsuffizienz|SGLT2"),
        ]
        keywords = _extract_trending_keywords(articles, top_n=5)
        assert "herzinsuffizienz" in keywords

    def test_studientyp_tags_excluded(self):
        articles = [
            make_article(title="Test Article",
                         highlight_tags="Studientyp: RCT|Herzinsuffizienz"),
        ]
        keywords = _extract_trending_keywords(articles, top_n=5)
        assert not any("studientyp" in k for k in keywords)

    def test_empty_list(self):
        assert _extract_trending_keywords([], top_n=5) == []

    def test_top_n_respected(self):
        articles = [
            make_article(
                title="Immunotherapy checkpoint inhibitors melanoma treatment outcomes",
                url=f"u/{i}",
            )
            for i in range(5)
        ]
        keywords = _extract_trending_keywords(articles, top_n=2)
        assert len(keywords) <= 2


# ---------------------------------------------------------------------------
# Coverage Suggestion Generation
# ---------------------------------------------------------------------------

class TestGenerateCoverageSuggestion:
    def test_critical_no_approvals_high_quality(self):
        result = _generate_coverage_suggestion(
            specialty="Kardiologie", total=20, hq_count=8,
            approved=0, severity="critical", topics=["SGLT2", "HF"]
        )
        assert "Dringend" in result
        assert "Kardiologie" in result
        assert "8 hochwertige" in result

    def test_critical_no_approvals_low_quality(self):
        result = _generate_coverage_suggestion(
            specialty="Dermatologie", total=10, hq_count=2,
            approved=0, severity="critical", topics=["Melanom"]
        )
        assert "null Freigaben" in result
        assert "Dermatologie" in result

    def test_warning_low_rate(self):
        result = _generate_coverage_suggestion(
            specialty="Onkologie", total=30, hq_count=12,
            approved=3, severity="warning", topics=["Immuntherapie"]
        )
        assert "%" in result
        assert "Onkologie" in result

    def test_info_level(self):
        result = _generate_coverage_suggestion(
            specialty="Allgemeinmedizin", total=50, hq_count=20,
            approved=20, severity="info", topics=["Prävention"]
        )
        assert "ausbaufähig" in result

    def test_empty_topics_fallback(self):
        result = _generate_coverage_suggestion(
            specialty="Test", total=5, hq_count=2,
            approved=0, severity="critical", topics=[]
        )
        assert "diverse Themen" in result

"""Tests for src.processing.konkurrenz_radar — topic extraction and overlap logic."""

from collections import Counter
from datetime import date, timedelta

import pytest

from src.processing.konkurrenz_radar import (
    _extract_topic_keywords,
    _compute_topic_overlaps,
    TopicOverlap,
)
from tests.conftest import make_article


class TestExtractTopicKeywords:
    """Test keyword extraction from article titles."""

    def test_extracts_meaningful_words(self):
        articles = [
            make_article(title="Immunotherapy for advanced melanoma"),
        ]
        keywords = _extract_topic_keywords(articles)
        assert "immunotherapy" in keywords
        assert "melanoma" in keywords

    def test_filters_short_words(self):
        """Words shorter than 3 chars should be excluded."""
        articles = [make_article(title="A of in GLP-1 and HF")]
        keywords = _extract_topic_keywords(articles)
        assert "of" not in keywords
        assert "in" not in keywords
        assert "a" not in keywords

    def test_filters_stopwords(self):
        """Common stopwords should be excluded."""
        articles = [make_article(title="The study with patients and results")]
        keywords = _extract_topic_keywords(articles)
        assert "the" not in keywords
        assert "with" not in keywords
        assert "and" not in keywords

    def test_counts_unique_per_article(self):
        """Same word in one title counts only once per article."""
        articles = [
            make_article(title="Cancer cancer cancer treatment"),
        ]
        keywords = _extract_topic_keywords(articles)
        assert keywords["cancer"] == 1

    def test_counts_across_articles(self):
        """Word appearing in 3 articles counts 3.
        Note: regex splits on non-alpha chars so 'SGLT2' -> 'sglt' + '2' (dropped)."""
        articles = [
            make_article(title="Melanoma immunotherapy results", url="https://a.com/1"),
            make_article(title="Melanoma checkpoint inhibitors", url="https://a.com/2"),
            make_article(title="Melanoma survival outcomes", url="https://a.com/3"),
        ]
        keywords = _extract_topic_keywords(articles)
        assert keywords.get("melanoma", 0) == 3

    def test_empty_article_list(self):
        assert _extract_topic_keywords([]) == Counter()

    def test_article_without_title(self):
        articles = [make_article(title=None)]
        keywords = _extract_topic_keywords(articles)
        assert len(keywords) == 0


class TestComputeTopicOverlaps:
    """Test the overlap detection between our articles and competitors."""

    def test_exclusive_ours(self):
        """Topics only we cover should be 'exclusive_ours'."""
        today = date.today()
        our_articles = [
            make_article(title="Innovative immunotherapy crispr", url="u/1",
                         pub_date=today, status="APPROVED"),
            make_article(title="Advanced crispr gene editing", url="u/2",
                         pub_date=today - timedelta(days=1), status="APPROVED"),
        ]
        comp_articles = {
            "medRxiv": [
                make_article(title="Cardiac rehabilitation exercise", url="c/1",
                             source="medRxiv", pub_date=today),
            ]
        }
        our_topics = _extract_topic_keywords(our_articles)
        comp_topics = {"medRxiv": _extract_topic_keywords(comp_articles["medRxiv"])}
        overlaps = _compute_topic_overlaps(
            our_topics, comp_topics, our_articles, comp_articles, days=7
        )
        exclusive_ours = [o for o in overlaps if o.status == "exclusive_ours"]
        topics = [o.topic for o in exclusive_ours]
        assert "crispr" in topics

    def test_overlap_detected(self):
        """Shared topics should have status 'overlap'."""
        today = date.today()
        # Both sides publish about "melanoma" (keyword appears in both)
        our_articles = [
            make_article(title="Melanoma immunotherapy response", url="u/1",
                         pub_date=today, status="APPROVED"),
            make_article(title="Melanoma checkpoint treatment", url="u/2",
                         pub_date=today - timedelta(days=1), status="APPROVED"),
        ]
        comp_articles = {
            "medRxiv": [
                make_article(title="Melanoma survival analysis", url="c/1",
                             source="medRxiv", pub_date=today - timedelta(days=2)),
                make_article(title="Melanoma biomarker study", url="c/2",
                             source="medRxiv", pub_date=today - timedelta(days=3)),
            ]
        }
        our_topics = _extract_topic_keywords(our_articles)
        comp_topics = {"medRxiv": _extract_topic_keywords(comp_articles["medRxiv"])}
        overlaps = _compute_topic_overlaps(
            our_topics, comp_topics, our_articles, comp_articles, days=7
        )
        # "melanoma" should appear as overlap or gap (both sides have it)
        shared = [o for o in overlaps if o.status in ("overlap", "gap")
                  and o.our_coverage > 0 and o.total_competitor_articles > 0]
        topic_names = [o.topic for o in shared]
        assert "melanoma" in topic_names

    def test_we_covered_first_when_earlier(self):
        """If we published before competitors, we_covered_first=True."""
        today = date.today()
        our_articles = [
            make_article(title="Melanoma immunotherapy breakthrough", url="u/1",
                         pub_date=today - timedelta(days=5), status="APPROVED"),
            make_article(title="Melanoma targeted therapy", url="u/2",
                         pub_date=today - timedelta(days=4), status="APPROVED"),
        ]
        comp_articles = {
            "medRxiv": [
                make_article(title="Melanoma checkpoint inhibitors", url="c/1",
                             source="medRxiv", pub_date=today - timedelta(days=2)),
                make_article(title="Melanoma survival data", url="c/2",
                             source="medRxiv", pub_date=today - timedelta(days=1)),
            ]
        }
        our_topics = _extract_topic_keywords(our_articles)
        comp_topics = {"medRxiv": _extract_topic_keywords(comp_articles["medRxiv"])}
        overlaps = _compute_topic_overlaps(
            our_topics, comp_topics, our_articles, comp_articles, days=7
        )
        melanoma_overlap = [o for o in overlaps if o.topic == "melanoma"]
        assert len(melanoma_overlap) > 0
        assert melanoma_overlap[0].we_covered_first is True

    def test_same_day_not_covered_first(self):
        """Same-day publication should NOT count as 'we covered first'."""
        today = date.today()
        our_articles = [
            make_article(title="Melanoma immunotherapy study", url="u/1",
                         pub_date=today, status="APPROVED"),
            make_article(title="Melanoma checkpoint results", url="u/2",
                         pub_date=today, status="APPROVED"),
        ]
        comp_articles = {
            "medRxiv": [
                make_article(title="Melanoma survival outcomes", url="c/1",
                             source="medRxiv", pub_date=today),
                make_article(title="Melanoma biomarker validation", url="c/2",
                             source="medRxiv", pub_date=today),
            ]
        }
        our_topics = _extract_topic_keywords(our_articles)
        comp_topics = {"medRxiv": _extract_topic_keywords(comp_articles["medRxiv"])}
        overlaps = _compute_topic_overlaps(
            our_topics, comp_topics, our_articles, comp_articles, days=7
        )
        melanoma_overlap = [o for o in overlaps if o.topic == "melanoma"]
        if melanoma_overlap:
            assert melanoma_overlap[0].we_covered_first is False

"""Tests for src.processing.redaktions_gedaechtnis — topic extraction and editorial suggestions."""

from datetime import date, timedelta

import pytest

from src.processing.redaktions_gedaechtnis import (
    _extract_topics,
    _calc_days_since,
    _generate_suggestion,
)


# ---------------------------------------------------------------------------
# Topic Extraction
# ---------------------------------------------------------------------------

class TestExtractTopics:
    def test_extracts_medical_entities(self):
        """Should find medical keywords from the entities list."""
        topics = _extract_topics(
            "SGLT2 Inhibitors in Heart Failure Treatment",
            "Randomized trial of dapagliflozin in patients with heart failure"
        )
        assert len(topics) > 0

    def test_extracts_specialty_terms(self):
        """Should find terms from SPECIALTY_MESH config."""
        topics = _extract_topics("Immunotherapy for advanced melanoma")
        # "melanoma" or "immunotherapy" should be recognized
        found = [t for t in topics if "melanom" in t or "immunother" in t]
        assert len(found) > 0

    def test_empty_input(self):
        assert _extract_topics("", "") == []
        assert _extract_topics("") == []

    def test_none_input(self):
        assert _extract_topics(None, None) == []

    def test_preserves_order_removes_duplicates(self):
        topics = _extract_topics(
            "Cardiac cardiac heart failure cardiac arrest",
            "heart failure treatment cardiac outcomes"
        )
        # Should have no duplicates
        assert len(topics) == len(set(topics))

    def test_case_insensitive(self):
        topics_upper = _extract_topics("DIABETES MELLITUS")
        topics_lower = _extract_topics("diabetes mellitus")
        assert topics_upper == topics_lower


# ---------------------------------------------------------------------------
# Days Since Calculation
# ---------------------------------------------------------------------------

class TestCalcDaysSince:
    def test_no_similar_articles(self):
        assert _calc_days_since([]) == -1

    def test_recent_article(self):
        similar = [{"approved_date": date.today() - timedelta(days=3), "score": 80}]
        assert _calc_days_since(similar) == 3

    def test_today(self):
        similar = [{"approved_date": date.today(), "score": 90}]
        assert _calc_days_since(similar) == 0

    def test_no_approved_date(self):
        similar = [{"approved_date": None, "score": 50}]
        assert _calc_days_since(similar) == -1


# ---------------------------------------------------------------------------
# Suggestion Generation
# ---------------------------------------------------------------------------

class TestGenerateSuggestion:
    def test_new_topic(self):
        label, detail = _generate_suggestion(-1, [], [])
        assert "Neues Thema" in label

    def test_recently_reported(self):
        similar = [{"score": 85, "approved_date": date.today() - timedelta(days=3)}]
        label, detail = _generate_suggestion(3, similar, ["diabetes"])
        assert "Kuerzlich" in label
        assert "3 Tag" in detail

    def test_topic_running(self):
        similar = [{"score": 70, "approved_date": date.today() - timedelta(days=15)}]
        label, detail = _generate_suggestion(15, similar, ["heart failure"])
        assert "Thema laeuft" in label or "laeuft" in label

    def test_update_needed(self):
        similar = [{"score": 60, "approved_date": date.today() - timedelta(days=45)}]
        label, detail = _generate_suggestion(45, similar, ["SGLT2", "Diabetes"])
        assert "Update faellig" in label
        assert "45 Tagen" in detail

    def test_edge_case_7_days(self):
        """Exactly 7 days should NOT be 'recently reported' (< 7)."""
        similar = [{"score": 75, "approved_date": date.today() - timedelta(days=7)}]
        label, _ = _generate_suggestion(7, similar, ["test"])
        assert "Kuerzlich" not in label

    def test_edge_case_30_days(self):
        """Exactly 30 days should still be 'topic running' (<= 30)."""
        similar = [{"score": 65, "approved_date": date.today() - timedelta(days=30)}]
        label, _ = _generate_suggestion(30, similar, ["test"])
        assert "Thema laeuft" in label

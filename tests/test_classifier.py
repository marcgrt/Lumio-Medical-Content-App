"""Tests for src.processing.classifier — specialty classification and alert detection."""

import pytest

from src.models import Article
from src.processing.classifier import classify_specialty, detect_alert, classify_articles


def _make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test Article",
        "url": "https://example.com/test",
        "source": "Test",
        "relevance_score": 0.0,
        "status": "NEW",
    }
    defaults.update(kwargs)
    return Article(**defaults)


# ---------------------------------------------------------------------------
# Specialty classification
# ---------------------------------------------------------------------------

class TestClassifySpecialty:
    def test_cardiology(self):
        a = _make_article(
            title="Cardiovascular outcomes in heart failure patients",
            abstract="Cardiac function improved with new therapy",
        )
        assert classify_specialty(a) == "Kardiologie"

    def test_oncology(self):
        a = _make_article(
            title="Immunotherapy for advanced melanoma",
            abstract="Checkpoint inhibitor shows tumor response",
        )
        assert classify_specialty(a) == "Onkologie"

    def test_neurology(self):
        a = _make_article(
            title="Alzheimer disease progression and dementia",
            abstract="Neurological assessment of stroke patients",
        )
        assert classify_specialty(a) == "Neurologie"

    def test_diabetology(self):
        a = _make_article(
            title="GLP-1 receptor agonists in type 2 diabetes",
            abstract="HbA1c and insulin sensitivity improvements",
        )
        assert classify_specialty(a) == "Diabetologie/Endokrinologie"

    def test_no_match(self):
        a = _make_article(
            title="General organizational announcement",
            abstract="Administrative update for staff",
        )
        result = classify_specialty(a)
        assert result is None

    def test_uses_mesh_terms(self):
        a = _make_article(
            title="A clinical study",
            mesh_terms="heart, cardiac, coronary",
        )
        assert classify_specialty(a) == "Kardiologie"

    def test_best_match_wins(self):
        """When multiple specialties match, the one with more keyword hits wins."""
        a = _make_article(
            title="Cardiac heart cardiovascular myocardial",  # 4 cardiology keywords
            abstract="cancer",  # 1 oncology keyword
        )
        assert classify_specialty(a) == "Kardiologie"


# ---------------------------------------------------------------------------
# Alert detection
# ---------------------------------------------------------------------------

class TestDetectAlert:
    def test_unconditional_keyword_triggers_alert(self):
        a = _make_article(title="Rückruf: Medikament XY vom Markt genommen")
        assert detect_alert(a) is True

    def test_rote_hand_brief_triggers(self):
        a = _make_article(title="Rote-Hand-Brief zu Wirkstoff Z")
        assert detect_alert(a) is True

    def test_bfarm_contextual_triggers(self):
        a = _make_article(
            title="BfArM warnt vor Nebenwirkungen",
            abstract="Die Behörde warnt vor schweren Nebenwirkungen",
        )
        assert detect_alert(a) is True

    def test_bfarm_without_context_no_alert(self):
        a = _make_article(
            title="BfArM stellt Daten bereit",
            abstract="Neue Datenbank verfügbar",
        )
        assert detect_alert(a) is False

    def test_suppress_pattern_prevents_alert(self):
        a = _make_article(
            title="Interview: BfArM warnt vor Risiken",
        )
        assert detect_alert(a) is False

    def test_normal_article_no_alert(self):
        a = _make_article(
            title="Meta-analysis of statin therapy",
            abstract="Statins reduced cardiovascular events",
        )
        assert detect_alert(a) is False

    def test_black_box_warning(self):
        a = _make_article(title="FDA issues black box warning for drug Y")
        assert detect_alert(a) is True


# ---------------------------------------------------------------------------
# classify_articles (integration)
# ---------------------------------------------------------------------------

class TestClassifyArticles:
    def test_sets_specialty(self):
        articles = [
            _make_article(title="Heart failure treatment update"),
        ]
        result = classify_articles(articles)
        assert result[0].specialty == "Kardiologie"

    def test_sets_alert_status(self):
        articles = [
            _make_article(title="Rückruf eines Arzneimittels"),
        ]
        result = classify_articles(articles)
        assert result[0].status == "ALERT"

    def test_normal_article_stays_new(self):
        articles = [
            _make_article(title="Regular clinical study on outcomes"),
        ]
        result = classify_articles(articles)
        assert result[0].status == "NEW"

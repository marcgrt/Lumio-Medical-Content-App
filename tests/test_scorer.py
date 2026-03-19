"""Tests for src.processing.scorer — rule-based + LLM scoring."""

import json
from datetime import date

import pytest

from src.models import Article
from src.processing.scorer import (
    compute_relevance_score,
    _journal_score,
    _study_design_score,
    _recency_score,
    _keyword_boost,
    _arztrelevanz_score,
    _parse_llm_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(**kwargs) -> Article:
    """Create a minimal Article with sensible defaults."""
    defaults = {
        "title": "Test Article",
        "url": "https://example.com/test",
        "source": "Test",
        "relevance_score": 0.0,
    }
    defaults.update(kwargs)
    return Article(**defaults)


# ---------------------------------------------------------------------------
# Journal scoring
# ---------------------------------------------------------------------------

class TestJournalScore:
    def test_top_journal(self):
        a = _make_article(journal="New England Journal of Medicine")
        score = _journal_score(a)
        assert score >= 90, f"NEJM should score ≥90, got {score}"

    def test_german_medical_journal(self):
        a = _make_article(journal="Deutsches Ärzteblatt")
        score = _journal_score(a)
        assert score >= 50, f"Ärzteblatt should score ≥50, got {score}"

    def test_unknown_journal(self):
        a = _make_article(journal="Unknown Journal of Testing")
        score = _journal_score(a)
        assert 0 < score < 50, f"Unknown journal should get default, got {score}"

    def test_no_journal(self):
        a = _make_article(journal=None)
        score = _journal_score(a)
        assert score > 0, "None journal should still return a default score"


# ---------------------------------------------------------------------------
# Study design scoring
# ---------------------------------------------------------------------------

class TestStudyDesignScore:
    def test_rct(self):
        a = _make_article(title="A Randomized Controlled Trial of X")
        score = _study_design_score(a)
        assert score >= 80, f"RCT should score ≥80, got {score}"

    def test_meta_analysis(self):
        a = _make_article(title="Meta-Analysis of Y")
        score = _study_design_score(a)
        assert score >= 90, f"Meta-analysis should score ≥90, got {score}"

    def test_case_report(self):
        a = _make_article(title="Case Report: Rare Condition")
        score = _study_design_score(a)
        assert score < 60, f"Case report should score <60, got {score}"


# ---------------------------------------------------------------------------
# Recency scoring
# ---------------------------------------------------------------------------

class TestRecencyScore:
    def test_today(self):
        a = _make_article(pub_date=date.today())
        score = _recency_score(a)
        assert score >= 95, f"Today's article should score ≥95, got {score}"

    def test_old_article(self):
        a = _make_article(pub_date=date(2020, 1, 1))
        score = _recency_score(a)
        assert score < 5, f"Old article should score <5, got {score}"

    def test_no_date(self):
        a = _make_article(pub_date=None)
        score = _recency_score(a)
        assert score == 50.0, "No date should give 50.0"


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

class TestCompositeScore:
    def test_returns_tuple(self):
        a = _make_article(title="Test", journal="NEJM", pub_date=date.today())
        score, breakdown = compute_relevance_score(a)
        assert isinstance(score, float)
        assert isinstance(breakdown, dict)

    def test_score_range(self):
        a = _make_article(title="Test")
        score, _ = compute_relevance_score(a)
        assert 0.0 <= score <= 100.0, f"Score out of range: {score}"

    def test_breakdown_keys(self):
        a = _make_article(title="Test")
        _, bd = compute_relevance_score(a)
        for key in ("journal", "design", "recency", "keywords",
                     "arztrelevanz", "bonus", "total"):
            assert key in bd, f"Missing key: {key}"

    def test_high_quality_article(self):
        a = _make_article(
            title="Meta-Analysis of GLP-1 Receptor Agonists in Type 2 Diabetes",
            journal="The Lancet",
            pub_date=date.today(),
            abstract="This systematic review and meta-analysis found that "
                     "GLP-1 receptor agonists significantly reduced HbA1c "
                     "and cardiovascular events in patients with type 2 diabetes.",
        )
        score, _ = compute_relevance_score(a)
        assert score >= 50, f"High-quality article should score ≥50, got {score}"


# ---------------------------------------------------------------------------
# LLM score parsing
# ---------------------------------------------------------------------------

class TestParseLLMScore:
    def test_valid_json(self):
        raw = json.dumps({
            "studientyp": 18,
            "klinische_relevanz": 16,
            "neuigkeitswert": 14,
            "zielgruppen_fit": 15,
            "quellenqualitaet": 19,
            "begr_studientyp": "RCT mit großer Stichprobe",
            "begr_klinische_relevanz": "Neue Therapieoption",
            "begr_neuigkeitswert": "Phase-III-Daten",
            "begr_zielgruppen_fit": "Breite Anwendung",
            "begr_quellenqualitaet": "NEJM Publikation",
        })
        result = _parse_llm_score(raw)
        assert result is not None
        assert result["scorer"] == "llm"
        assert result["total"] == 18 + 16 + 14 + 15 + 19
        assert result["studientyp"] == 18

    def test_markdown_fences(self):
        raw = "```json\n" + json.dumps({
            "studientyp": 10,
            "klinische_relevanz": 10,
            "neuigkeitswert": 10,
            "zielgruppen_fit": 10,
            "quellenqualitaet": 10,
        }) + "\n```"
        result = _parse_llm_score(raw)
        assert result is not None
        assert result["total"] == 50

    def test_clamps_to_20(self):
        raw = json.dumps({
            "studientyp": 25,
            "klinische_relevanz": -5,
            "neuigkeitswert": 10,
            "zielgruppen_fit": 10,
            "quellenqualitaet": 10,
        })
        result = _parse_llm_score(raw)
        assert result is not None
        assert result["studientyp"] == 20
        assert result["klinische_relevanz"] == 0

    def test_missing_dimension(self):
        raw = json.dumps({"studientyp": 10, "klinische_relevanz": 10})
        result = _parse_llm_score(raw)
        assert result is None, "Missing dimensions should return None"

    def test_invalid_json(self):
        result = _parse_llm_score("not json at all")
        assert result is None

    def test_reasoning_truncated(self):
        long_reason = "x" * 500
        raw = json.dumps({
            "studientyp": 10,
            "klinische_relevanz": 10,
            "neuigkeitswert": 10,
            "zielgruppen_fit": 10,
            "quellenqualitaet": 10,
            "begr_studientyp": long_reason,
        })
        result = _parse_llm_score(raw)
        assert result is not None
        assert len(result["begr_studientyp"]) <= 200

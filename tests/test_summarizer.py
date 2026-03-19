"""Tests for src.processing.summarizer — validation, templates, highlights."""

import pytest

from src.models import Article
from src.processing.summarizer import (
    _validate_summary,
    generate_template_summary,
    generate_highlight_tags,
    clean_title,
    _clean_abstract,
    _pick_kern_and_detail,
)
from datetime import date


def _make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test Article",
        "url": "https://example.com",
        "source": "Test",
        "relevance_score": 0.0,
    }
    defaults.update(kwargs)
    return Article(**defaults)


# ---------------------------------------------------------------------------
# Summary validation
# ---------------------------------------------------------------------------

class TestValidateSummary:
    def test_valid_format(self):
        raw = "KERN: Ergebnis X;;;PRAXIS: Therapie Y;;;EINORDNUNG: RCT mit 500 Patienten"
        result = _validate_summary(raw, "Test")
        assert result is not None
        assert "KERN:" in result
        assert ";;;" in result

    def test_newline_separators_normalized(self):
        raw = "KERN: Ergebnis X\nPRAXIS: Therapie Y\nEINORDNUNG: RCT"
        result = _validate_summary(raw, "Test")
        assert result is not None
        assert ";;;PRAXIS:" in result
        assert ";;;EINORDNUNG:" in result

    def test_missing_kern(self):
        raw = "Some random LLM output without the required format"
        result = _validate_summary(raw, "Test")
        assert result is None, "Missing KERN: should return None"

    def test_partial_format(self):
        raw = "KERN: Only the core finding"
        result = _validate_summary(raw, "Test")
        assert result is not None, "KERN-only should still pass"


# ---------------------------------------------------------------------------
# Title cleaning
# ---------------------------------------------------------------------------

class TestCleanTitle:
    def test_strip_bracket_prefix(self):
        assert clean_title("[Articles] Real Title Here") == "Real Title Here"

    def test_no_prefix(self):
        assert clean_title("Normal Title") == "Normal Title"

    def test_comment_prefix(self):
        assert clean_title("[Comment] On the Study") == "On the Study"


# ---------------------------------------------------------------------------
# Abstract cleaning
# ---------------------------------------------------------------------------

class TestCleanAbstract:
    def test_stuck_headers(self):
        raw = "Results were positive.ConclusionThis confirms the hypothesis."
        cleaned = _clean_abstract(raw)
        # Should insert space before "Conclusion"
        assert "Conclusion" in cleaned
        assert ".Conclusion" not in cleaned

    def test_empty_abstract(self):
        assert _clean_abstract("") == ""
        assert _clean_abstract(None) == ""


# ---------------------------------------------------------------------------
# Sentence picking (KERN + DETAIL)
# ---------------------------------------------------------------------------

class TestPickKernAndDetail:
    def test_result_sentence_preferred_for_kern(self):
        sentences = [
            "Background is that the disease is common",
            "We conducted a randomized trial with 500 patients",
            "We found that treatment X significantly reduced mortality",
        ]
        kern, detail = _pick_kern_and_detail(sentences)
        assert kern is not None
        assert "found that" in kern.lower() or "significantly" in kern.lower()

    def test_kern_and_detail_differ(self):
        sentences = [
            "The aim of this study was to evaluate X",
            "We enrolled 200 patients in a RCT",
            "Treatment showed significant improvement in outcomes",
        ]
        kern, detail = _pick_kern_and_detail(sentences)
        assert kern != detail

    def test_empty_list(self):
        kern, detail = _pick_kern_and_detail([])
        assert kern is None
        assert detail is None

    def test_single_sentence(self):
        kern, detail = _pick_kern_and_detail(["Only one sentence here"])
        assert kern is not None
        assert detail is None


# ---------------------------------------------------------------------------
# Template summary
# ---------------------------------------------------------------------------

class TestTemplateSummary:
    def test_produces_kern(self):
        a = _make_article(
            title="GLP-1 in Diabetes",
            abstract="Background: Diabetes is common. Methods: We conducted "
                     "a meta-analysis. Results: GLP-1 agonists reduced HbA1c "
                     "significantly. Conclusion: GLP-1 is effective.",
            journal="Lancet",
        )
        summary = generate_template_summary(a)
        assert "KERN:" in summary
        assert ";;;" in summary

    def test_no_abstract(self):
        a = _make_article(title="Some Title", abstract=None, journal="BMJ")
        summary = generate_template_summary(a)
        assert "KERN:" in summary

    def test_separator_format(self):
        a = _make_article(
            title="Test",
            abstract="We found that X is effective. The study enrolled 100 patients.",
            journal="Test Journal",
        )
        summary = generate_template_summary(a)
        parts = summary.split(";;;")
        assert len(parts) >= 2, "Should have at least KERN + DESIGN"


# ---------------------------------------------------------------------------
# Highlight tags
# ---------------------------------------------------------------------------

class TestHighlightTags:
    def test_top_journal_tag(self):
        a = _make_article(journal="The Lancet", title="Test")
        tags = generate_highlight_tags(a)
        assert any("Top-Quelle" in t for t in tags.split("|"))

    def test_rct_tag(self):
        a = _make_article(title="A Randomized Controlled Trial of X")
        tags = generate_highlight_tags(a)
        assert "RCT" in tags

    def test_safety_tag(self):
        a = _make_article(
            title="Drug Recall and Safety Warning for Medication X",
            abstract="rückruf warnung nebenwirkung"
        )
        tags = generate_highlight_tags(a)
        assert "Sicherheitsrelevant" in tags

    def test_max_three_tags(self):
        a = _make_article(
            title="Meta-Analysis Guideline Update Safety Warning",
            abstract="rückruf leitlinie meta-analysis randomized",
            journal="NEJM",
        )
        tags = generate_highlight_tags(a)
        tag_list = tags.split("|")
        assert len(tag_list) <= 3, f"Max 3 tags, got {len(tag_list)}: {tags}"

    def test_german_source_tag(self):
        a = _make_article(journal="Deutsches Ärzteblatt", title="Fachbeitrag")
        tags = generate_highlight_tags(a)
        assert "Ärzteblatt" in tags or "Fachquelle" in tags

    def test_fallback_tag(self):
        a = _make_article(
            title="Some Article",
            source="Europe PMC",
            pub_date=date(2020, 1, 1),
        )
        tags = generate_highlight_tags(a)
        assert len(tags) > 0, "Should always produce at least one tag"

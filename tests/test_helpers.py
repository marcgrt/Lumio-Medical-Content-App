"""Tests for pure helper functions in components/helpers.py."""

import pytest

from components.helpers import (
    _esc,
    score_pill,
    spec_pill,
    status_badge,
    momentum_badge,
    evidence_badge,
    cross_specialty_badge,
    _parse_summary,
)
from src.config import SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MID


# ---------------------------------------------------------------------------
# HTML Escape
# ---------------------------------------------------------------------------

class TestEsc:
    def test_escapes_html(self):
        assert "&lt;" in _esc("<script>")
        assert "&amp;" in _esc("A & B")

    def test_none_returns_empty(self):
        assert _esc(None) == ""

    def test_plain_text_unchanged(self):
        assert _esc("Hello World") == "Hello World"


# ---------------------------------------------------------------------------
# Score Pill
# ---------------------------------------------------------------------------

class TestScorePill:
    def test_high_score_class(self):
        html = score_pill(80)
        assert "score-high" in html
        assert "80" in html

    def test_mid_score_class(self):
        html = score_pill(50)
        assert "score-mid" in html

    def test_low_score_class(self):
        html = score_pill(20)
        assert "score-low" in html


# ---------------------------------------------------------------------------
# Specialty Pill
# ---------------------------------------------------------------------------

class TestSpecPill:
    def test_known_specialty(self):
        html = spec_pill("Kardiologie")
        assert "Kardiologie" in html
        assert "a-spec" in html

    def test_unknown_specialty_fallback(self):
        html = spec_pill("Unknown Specialty")
        assert "Unknown Specialty" in html
        assert "a-spec" in html


# ---------------------------------------------------------------------------
# Status Badge
# ---------------------------------------------------------------------------

class TestStatusBadge:
    def test_new_status(self):
        html = status_badge("NEW")
        assert "Neu" in html
        assert "status-new" in html

    def test_approved_status(self):
        html = status_badge("APPROVED")
        assert "Gemerkt" in html
        assert "status-approved" in html

    def test_alert_status(self):
        html = status_badge("ALERT")
        assert "Alert" in html
        assert "status-alert" in html

    def test_unknown_status_fallback(self):
        html = status_badge("CUSTOM")
        assert "CUSTOM" in html


# ---------------------------------------------------------------------------
# Momentum Badge
# ---------------------------------------------------------------------------

class TestMomentumBadge:
    def test_exploding(self):
        html = momentum_badge("exploding", 3.0)
        assert "Stark steigend" in html
        assert "3.0x" in html

    def test_rising(self):
        html = momentum_badge("rising", 1.5)
        assert "Steigend" in html
        assert "1.5x" in html

    def test_stable_no_multiplier(self):
        html = momentum_badge("stable", 0.5)
        assert "Stabil" in html
        assert "x" not in html

    def test_falling(self):
        html = momentum_badge("falling", -0.5)
        assert html  # just check it doesn't crash


# ---------------------------------------------------------------------------
# Evidence Badge
# ---------------------------------------------------------------------------

class TestEvidenceBadge:
    def test_rising_evidence(self):
        html = evidence_badge("rising", "RCT")
        assert "RCT" in html
        assert "rising" in html

    def test_stable_evidence(self):
        html = evidence_badge("stable", "Review")
        assert "Review" in html

    def test_no_dominant_type_empty(self):
        assert evidence_badge("rising", "") == ""

    def test_escapes_html_in_type(self):
        html = evidence_badge("stable", "<script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Cross-Specialty Badge
# ---------------------------------------------------------------------------

class TestCrossSpecialtyBadge:
    def test_with_spread(self):
        html = cross_specialty_badge("Kardiologie → Nephrologie")
        assert "Kardiologie" in html

    def test_empty_spread(self):
        assert cross_specialty_badge("") == ""


# ---------------------------------------------------------------------------
# Parse Summary
# ---------------------------------------------------------------------------

class TestParseSummary:
    def test_llm_format(self):
        raw = "KERN: Neue Studie zeigt...;;;PRAXIS: Für Ärzte relevant...;;;EINORDNUNG: Dies ergänzt..."
        core, detail, praxis = _parse_summary(raw)
        assert "Neue Studie" in core
        assert "Für Ärzte" in praxis
        assert "Dies ergänzt" in detail

    def test_template_format(self):
        raw = "KERN: Befund A;;;DESIGN: RCT;;;DETAIL: Weitere Infos"
        core, detail, praxis = _parse_summary(raw)
        assert "Befund A" in core
        assert "Weitere Infos" in detail
        assert praxis == ""

    def test_legacy_format(self):
        raw = "Kernbefund: Wichtig | Details: Mehr dazu"
        core, detail, praxis = _parse_summary(raw)
        assert "Wichtig" in core
        assert "Mehr dazu" in detail

    def test_plain_text_truncated(self):
        raw = "A" * 200
        core, detail, praxis = _parse_summary(raw)
        assert len(core) == 150

    def test_empty_input(self):
        core, detail, praxis = _parse_summary("")
        assert core == "" and detail == "" and praxis == ""

    def test_none_input(self):
        core, detail, praxis = _parse_summary(None)
        assert core == "" and detail == "" and praxis == ""

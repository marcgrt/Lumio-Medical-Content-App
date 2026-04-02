"""Tests for LUMIO Scoring v2 — 6-dimension model.

Covers:
- LLM prompt contains all 6 dimensions and calibration examples
- JSON parsing handles the nested v2 structure
- Validation: scores capped at dimension maxima
- Total score calculated from individual scores
- Tier assignment thresholds
- Fallback (rule-based) scoring produces plausible values
- v1 scores remain readable (backward compat)
"""

import json
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from src.processing.scorer import (
    _LLM_SCORING_SYSTEM_PROMPT,
    _V2_DIMS,
    _parse_llm_score,
    _parse_llm_score_v1,
    compute_relevance_score,
    compute_relevance_score_v1,
    compute_relevance_score_v2,
)
from src.config import (
    SCORE_THRESHOLD_HIGH,
    SCORE_THRESHOLD_MID,
    V2_DIMENSIONS,
    V2_TIER_TOP,
    V2_TIER_RELEVANT,
    SCORE_THRESHOLD_HIGH_V1,
    SCORE_THRESHOLD_MID_V1,
)
from src.models import Article


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(**kwargs) -> Article:
    """Create an Article with sensible defaults for testing."""
    defaults = {
        "title": "Test Article",
        "abstract": "",
        "url": "https://example.com/test",
        "source": "Test Source",
        "journal": None,
        "pub_date": date.today(),
        "doi": None,
        "study_type": None,
        "mesh_terms": None,
        "language": "en",
    }
    defaults.update(kwargs)
    return Article(**defaults)


def _make_v2_llm_response(
    car=10, ed=10, ta=10, nov=8, sa=6, pq=6,
    one_line_summary="Test summary",
) -> str:
    """Build a valid v2 JSON response string."""
    total = car + ed + ta + nov + sa + pq
    tier = "TOP" if total >= 70 else ("RELEVANT" if total >= 45 else "MONITOR")
    return json.dumps({
        "scores": {
            "clinical_action_relevance": {"score": car, "reason": "Test reason CAR"},
            "evidence_depth": {"score": ed, "reason": "Test reason ED"},
            "topic_appeal": {"score": ta, "reason": "Test reason TA"},
            "novelty": {"score": nov, "reason": "Test reason NOV"},
            "source_authority": {"score": sa, "reason": "Test reason SA"},
            "presentation_quality": {"score": pq, "reason": "Test reason PQ"},
        },
        "total_score": total,
        "tier": tier,
        "one_line_summary": one_line_summary,
    })


# ---------------------------------------------------------------------------
# 1. LLM prompt contains all 6 dimensions and calibration examples
# ---------------------------------------------------------------------------

class TestPromptContent:
    """Verify the system prompt includes all required v2 content."""

    def test_prompt_contains_all_six_dimensions(self):
        for dim_key in _V2_DIMS:
            # Map field names to prompt text
            pass
        assert "clinical_action_relevance" in _LLM_SCORING_SYSTEM_PROMPT or \
               "Klinische Handlungsrelevanz" in _LLM_SCORING_SYSTEM_PROMPT
        assert "evidence_depth" in _LLM_SCORING_SYSTEM_PROMPT or \
               "Evidenz- & Recherchetiefe" in _LLM_SCORING_SYSTEM_PROMPT
        assert "topic_appeal" in _LLM_SCORING_SYSTEM_PROMPT or \
               "Thematische Zugkraft" in _LLM_SCORING_SYSTEM_PROMPT
        assert "Neuigkeitswert" in _LLM_SCORING_SYSTEM_PROMPT
        assert "Quellenautorität" in _LLM_SCORING_SYSTEM_PROMPT or \
               "Quellenautori" in _LLM_SCORING_SYSTEM_PROMPT
        assert "Aufbereitungsqualität" in _LLM_SCORING_SYSTEM_PROMPT or \
               "Aufbereitungsqualit" in _LLM_SCORING_SYSTEM_PROMPT

    def test_prompt_contains_max_values(self):
        assert "(0–20)" in _LLM_SCORING_SYSTEM_PROMPT
        assert "(0–16)" in _LLM_SCORING_SYSTEM_PROMPT
        assert "(0–12)" in _LLM_SCORING_SYSTEM_PROMPT

    def test_prompt_contains_calibration_examples(self):
        """All 8 calibration anchors (A–H) must be present."""
        assert "~87" in _LLM_SCORING_SYSTEM_PROMPT   # A: NEJM Meta-Analyse
        assert "~84" in _LLM_SCORING_SYSTEM_PROMPT   # B: Ärzteblatt investigativ
        assert "~81" in _LLM_SCORING_SYSTEM_PROMPT   # C: Rote-Hand-Brief
        assert "~31" in _LLM_SCORING_SYSTEM_PROMPT   # D: Case Report
        assert "~30" in _LLM_SCORING_SYSTEM_PROMPT   # E: Pharma PM
        assert "~69" in _LLM_SCORING_SYSTEM_PROMPT   # F: Nature Medicine
        assert "~65" in _LLM_SCORING_SYSTEM_PROMPT   # G: CME
        assert "~66" in _LLM_SCORING_SYSTEM_PROMPT   # H: Burnout

    def test_prompt_contains_feedback_placeholder(self):
        # The prompt template in _build_scoring_prompt should contain
        # the FEEDBACK_EXAMPLES placeholder concept
        from src.processing.scorer import _build_scoring_prompt
        article = _make_article()
        user_msg = _build_scoring_prompt(article)
        assert "FEEDBACK_EXAMPLES" in user_msg

    def test_prompt_contains_json_format(self):
        from src.processing.scorer import _build_scoring_prompt
        article = _make_article()
        user_msg = _build_scoring_prompt(article)
        assert "clinical_action_relevance" in user_msg
        assert "evidence_depth" in user_msg
        assert "one_line_summary" in user_msg


# ---------------------------------------------------------------------------
# 2. JSON parsing handles nested v2 structure
# ---------------------------------------------------------------------------

class TestParseV2:
    """Test _parse_llm_score with v2 nested JSON."""

    def test_valid_response(self):
        raw = _make_v2_llm_response(car=15, ed=12, ta=10, nov=8, sa=6, pq=6)
        result = _parse_llm_score(raw)
        assert result is not None
        assert result["scorer"] == "llm"
        assert result["scoring_version"] == "v2"
        assert result["scores"]["clinical_action_relevance"]["score"] == 15
        assert result["scores"]["evidence_depth"]["score"] == 12
        assert result["scores"]["novelty"]["score"] == 8
        assert result["scores"]["source_authority"]["score"] == 6

    def test_reasons_preserved(self):
        raw = _make_v2_llm_response()
        result = _parse_llm_score(raw)
        assert result["scores"]["clinical_action_relevance"]["reason"] == "Test reason CAR"

    def test_one_line_summary_extracted(self):
        raw = _make_v2_llm_response(one_line_summary="Important finding about diabetes")
        result = _parse_llm_score(raw)
        assert result["one_line_summary"] == "Important finding about diabetes"

    def test_markdown_wrapped_json(self):
        raw = "```json\n" + _make_v2_llm_response() + "\n```"
        result = _parse_llm_score(raw)
        assert result is not None
        assert result["scoring_version"] == "v2"

    def test_missing_dimension_returns_none(self):
        data = json.loads(_make_v2_llm_response())
        del data["scores"]["novelty"]
        raw = json.dumps(data)
        result = _parse_llm_score(raw)
        assert result is None

    def test_invalid_json_returns_none(self):
        result = _parse_llm_score("not json at all")
        assert result is None


# ---------------------------------------------------------------------------
# 3. Validation: scores capped at dimension maxima
# ---------------------------------------------------------------------------

class TestScoreCapping:
    """Scores exceeding dimension max must be capped."""

    def test_cap_at_max(self):
        # novelty max is 16, source_authority max is 12, presentation_quality max is 12
        raw = _make_v2_llm_response(car=25, ed=22, ta=21, nov=20, sa=15, pq=15)
        result = _parse_llm_score(raw)
        assert result is not None
        assert result["scores"]["clinical_action_relevance"]["score"] == 20  # capped at 20
        assert result["scores"]["evidence_depth"]["score"] == 20  # capped at 20
        assert result["scores"]["topic_appeal"]["score"] == 20  # capped at 20
        assert result["scores"]["novelty"]["score"] == 16  # capped at 16
        assert result["scores"]["source_authority"]["score"] == 12  # capped at 12
        assert result["scores"]["presentation_quality"]["score"] == 12  # capped at 12

    def test_negative_scores_floored_at_zero(self):
        raw = _make_v2_llm_response(car=-5, ed=0, ta=10, nov=8, sa=6, pq=6)
        result = _parse_llm_score(raw)
        assert result["scores"]["clinical_action_relevance"]["score"] == 0
        assert result["scores"]["evidence_depth"]["score"] == 0


# ---------------------------------------------------------------------------
# 4. Total score calculated from individual scores
# ---------------------------------------------------------------------------

class TestTotalCalculation:
    """Total must be calculated from individual scores, not trusted from LLM."""

    def test_total_is_sum_of_dimensions(self):
        raw = _make_v2_llm_response(car=15, ed=12, ta=10, nov=8, sa=6, pq=6)
        result = _parse_llm_score(raw)
        expected = 15 + 12 + 10 + 8 + 6 + 6
        assert result["total"] == expected

    def test_total_ignores_llm_total(self):
        """Even if LLM reports wrong total, we recalculate."""
        data = json.loads(_make_v2_llm_response(car=10, ed=10, ta=10, nov=8, sa=6, pq=6))
        data["total_score"] = 999  # LLM lies about total
        raw = json.dumps(data)
        result = _parse_llm_score(raw)
        assert result["total"] == 10 + 10 + 10 + 8 + 6 + 6  # = 50, not 999

    def test_capped_total(self):
        """When individual scores are capped, total reflects capped values."""
        raw = _make_v2_llm_response(car=20, ed=20, ta=20, nov=16, sa=12, pq=12)
        result = _parse_llm_score(raw)
        assert result["total"] == 100.0  # max possible


# ---------------------------------------------------------------------------
# 5. Tier assignment thresholds
# ---------------------------------------------------------------------------

class TestTierAssignment:
    """Verify tier boundaries: >=70 TOP, 45-69 RELEVANT, <45 MONITOR."""

    def test_score_70_is_top(self):
        raw = _make_v2_llm_response(car=15, ed=15, ta=15, nov=10, sa=8, pq=7)
        result = _parse_llm_score(raw)
        assert result["total"] == 70
        assert result["tier"] == "TOP"

    def test_score_69_is_relevant(self):
        raw = _make_v2_llm_response(car=15, ed=15, ta=15, nov=10, sa=8, pq=6)
        result = _parse_llm_score(raw)
        assert result["total"] == 69
        assert result["tier"] == "RELEVANT"

    def test_score_45_is_relevant(self):
        raw = _make_v2_llm_response(car=10, ed=10, ta=10, nov=5, sa=5, pq=5)
        result = _parse_llm_score(raw)
        assert result["total"] == 45
        assert result["tier"] == "RELEVANT"

    def test_score_44_is_monitor(self):
        raw = _make_v2_llm_response(car=10, ed=10, ta=10, nov=5, sa=5, pq=4)
        result = _parse_llm_score(raw)
        assert result["total"] == 44
        assert result["tier"] == "MONITOR"

    def test_config_thresholds_match_v2(self):
        assert SCORE_THRESHOLD_HIGH == 70
        assert SCORE_THRESHOLD_MID == 45
        assert V2_TIER_TOP == 70
        assert V2_TIER_RELEVANT == 45


# ---------------------------------------------------------------------------
# 6. Fallback scoring produces plausible values
# ---------------------------------------------------------------------------

class TestFallbackScoring:
    """Rule-based v2 fallback must produce plausible scores."""

    def test_nejm_meta_analysis_diabetes(self):
        """NEJM Meta-Analysis on Diabetes should score ~75-90."""
        a = _make_article(
            title="Meta-Analysis: SGLT2-Inhibitoren als neue Erstlinientherapie bei Typ-2-Diabetes",
            abstract=(
                "Background: This systematic review and meta-analysis evaluated the efficacy "
                "of SGLT2 inhibitors as first-line therapy for type 2 diabetes. "
                "Methods: We searched PubMed, Cochrane, and EMBASE for randomized controlled "
                "trials comparing SGLT2 inhibitors with metformin. "
                "Results: 28 RCTs with 45,000 patients were included. SGLT2 inhibitors "
                "showed superior cardiovascular outcomes (HR 0.78, 95% CI 0.72-0.85). "
                "Conclusion: SGLT2 inhibitors should be considered as first-line therapy "
                "in patients with cardiovascular risk. "
                "References: Smith et al., Jones et al., Wang et al., Mueller et al."
            ),
            journal="New England Journal of Medicine",
            doi="10.1056/NEJMoa2301234",
            study_type="Meta-Analysis",
            pub_date=date.today(),
        )
        score, breakdown = compute_relevance_score_v2(a)
        assert 70 <= score <= 100, f"NEJM Meta-Analysis Diabetes: expected ~75-90, got {score}"
        assert breakdown["scoring_version"] == "v2"
        assert breakdown["scorer"] == "rule_v2"
        assert breakdown["estimated"] is True

    def test_aerzteblatt_investigativ_krankenhausreform(self):
        """Ärzteblatt investigative piece on hospital reform should score ~45-85.

        Rule-based scoring is approximate; the LLM scorer would give ~84.
        The key signal is that topic_appeal is high (Krankenhausreform, Ärztemangel).
        """
        a = _make_article(
            title="Krankenhausreform: Was die Klinikschließungen für niedergelassene Ärzte bedeuten",
            abstract=(
                "Die Krankenhausreform wird massive Auswirkungen auf die ambulante Versorgung "
                "haben. Eine exklusive Datenanalyse des Deutschen Ärzteblatts zeigt: In 120 "
                "Landkreisen drohen Versorgungslücken. Vier Experten ordnen die Folgen ein. "
                "Ärztemangel und Bürokratie verschärfen die Situation zusätzlich. "
                "Die Honorarreform muss nachziehen, sonst kollabiert das System."
            ),
            journal="Deutsches Ärzteblatt",
            source="Deutsches Ärzteblatt",
            pub_date=date.today(),
        )
        score, breakdown = compute_relevance_score_v2(a)
        assert 45 <= score <= 95, f"Ärzteblatt Investigativ: expected ~45-85, got {score}"
        # Topic appeal should be high (Krankenhausreform + Ärztemangel)
        ta = breakdown["scores"]["topic_appeal"]["score"]
        assert ta >= 14, f"Topic appeal should be high, got {ta}"

    def test_pharma_press_release_phase_ii(self):
        """Pharma press release Phase II should score ~25-45."""
        a = _make_article(
            title="PharmaCorp meldet positive Phase-II-Daten für Onkologie-Kandidat XR-7742",
            abstract=(
                "PharmaCorp gab heute positive Ergebnisse der Phase-II-Studie bekannt. "
                "Press release: The investigational compound showed a response rate of 42%."
            ),
            journal=None,
            source="PharmaCorp Pressemitteilung",
            pub_date=date.today() - timedelta(days=10),
        )
        score, breakdown = compute_relevance_score_v2(a)
        assert 20 <= score <= 50, f"Pharma PM Phase II: expected ~25-40, got {score}"

    def test_fallback_breakdown_structure(self):
        """Verify v2 fallback breakdown has correct structure."""
        a = _make_article(title="Test", abstract="Some abstract text here")
        score, bd = compute_relevance_score_v2(a)
        assert "scores" in bd
        assert len(bd["scores"]) == 6
        for dim_key in _V2_DIMS:
            assert dim_key in bd["scores"]
            assert "score" in bd["scores"][dim_key]
            assert "reason" in bd["scores"][dim_key]
        assert "total" in bd
        assert "tier" in bd
        assert bd["tier"] in ("TOP", "RELEVANT", "MONITOR")
        assert "one_line_summary" in bd

    def test_fallback_scores_within_dimension_maxima(self):
        """Each dimension score must not exceed its max."""
        a = _make_article(
            title="Meta-analysis systematic review neue Therapie Leitlinie Rückruf Ärztemangel "
                  "first-in-class erstmals breakthrough",
            abstract="A " * 300,  # long abstract
            journal="NEJM",
            doi="10.1234/test",
        )
        _, bd = compute_relevance_score_v2(a)
        for dim_key, dim_max in _V2_DIMS.items():
            actual = bd["scores"][dim_key]["score"]
            assert 0 <= actual <= dim_max, \
                f"{dim_key}: {actual} exceeds max {dim_max}"


# ---------------------------------------------------------------------------
# 7. v1 backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """v1 scores must remain readable and v1 functions must still work."""

    def test_v1_parser_still_works(self):
        """The v1 parser should handle old-format LLM responses."""
        v1_response = json.dumps({
            "studientyp": 18,
            "klinische_relevanz": 16,
            "neuigkeitswert": 14,
            "zielgruppen_fit": 12,
            "quellenqualitaet": 15,
            "begr_studientyp": "Meta-Analyse",
            "begr_klinische_relevanz": "Neue Therapie",
            "begr_neuigkeitswert": "Erstmalig",
            "begr_zielgruppen_fit": "Breit relevant",
            "begr_quellenqualitaet": "NEJM",
        })
        result = _parse_llm_score_v1(v1_response)
        assert result is not None
        assert result["scorer"] == "llm"
        assert result["scoring_version"] == "v1"
        assert result["total"] == 75.0

    def test_v2_parser_falls_back_to_v1(self):
        """If v2 parser gets v1 JSON (no 'scores' key), it should fallback."""
        v1_response = json.dumps({
            "studientyp": 15,
            "klinische_relevanz": 14,
            "neuigkeitswert": 12,
            "zielgruppen_fit": 10,
            "quellenqualitaet": 14,
        })
        result = _parse_llm_score(v1_response)
        assert result is not None
        assert result["scoring_version"] == "v1"

    def test_compute_relevance_score_v1_alias(self):
        """compute_relevance_score should still work (aliased to v1)."""
        a = _make_article(title="Test", journal="NEJM")
        score, breakdown = compute_relevance_score(a)
        assert 0 <= score <= 100
        assert "journal" in breakdown  # v1 breakdown key

    def test_v1_thresholds_preserved(self):
        assert SCORE_THRESHOLD_HIGH_V1 == 65
        assert SCORE_THRESHOLD_MID_V1 == 40

    def test_v1_dimensions_in_breakdown(self):
        """v1 breakdown should have the old 5-dimension keys."""
        v1_response = json.dumps({
            "studientyp": 18,
            "klinische_relevanz": 16,
            "neuigkeitswert": 14,
            "zielgruppen_fit": 12,
            "quellenqualitaet": 15,
        })
        result = _parse_llm_score_v1(v1_response)
        assert "studientyp" in result
        assert "klinische_relevanz" in result
        assert "quellenqualitaet" in result

    def test_v2_breakdown_has_new_keys(self):
        """v2 breakdown should have the new 6-dimension nested structure."""
        raw = _make_v2_llm_response()
        result = _parse_llm_score(raw)
        assert "scores" in result
        assert "clinical_action_relevance" in result["scores"]
        assert "presentation_quality" in result["scores"]
        assert "one_line_summary" in result


# ---------------------------------------------------------------------------
# 8. Config constants
# ---------------------------------------------------------------------------

class TestConfigV2:
    """Verify v2 config constants are correctly defined."""

    def test_v2_dimensions_defined(self):
        assert len(V2_DIMENSIONS) == 6
        assert V2_DIMENSIONS["clinical_action_relevance"]["max"] == 20
        assert V2_DIMENSIONS["evidence_depth"]["max"] == 20
        assert V2_DIMENSIONS["topic_appeal"]["max"] == 20
        assert V2_DIMENSIONS["novelty"]["max"] == 16
        assert V2_DIMENSIONS["source_authority"]["max"] == 12
        assert V2_DIMENSIONS["presentation_quality"]["max"] == 12

    def test_dimension_maxima_sum_to_100(self):
        total = sum(d["max"] for d in V2_DIMENSIONS.values())
        assert total == 100


# ---------------------------------------------------------------------------
# 9. Article model has scoring_version field
# ---------------------------------------------------------------------------

class TestArticleModel:
    """Verify the Article model supports scoring_version."""

    def test_default_scoring_version(self):
        a = _make_article()
        assert a.scoring_version == "v1"

    def test_set_scoring_version_v2(self):
        a = _make_article()
        a.scoring_version = "v2"
        assert a.scoring_version == "v2"

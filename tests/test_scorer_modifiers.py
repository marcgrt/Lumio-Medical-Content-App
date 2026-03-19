"""Tests for scoring modifier functions in src.processing.scorer."""

import pytest

from src.processing.scorer import (
    _redaktions_bonus,
    _interdisciplinary_bonus,
    _abstract_length_modifier,
    _open_access_bonus,
    _structured_abstract_bonus,
    _doi_bonus,
    _paywall_modifier,
    _industry_news_modifier,
)
from tests.conftest import make_article


# ---------------------------------------------------------------------------
# Redaktions-Bonus
# ---------------------------------------------------------------------------

class TestRedaktionsBonus:
    def test_aerzteblatt_gets_bonus(self):
        a = make_article(journal="Deutsches Ärzteblatt")
        assert _redaktions_bonus(a) > 0

    def test_unknown_journal_no_bonus(self):
        a = make_article(journal="Nature")
        assert _redaktions_bonus(a) == 0.0

    def test_case_insensitive(self):
        a = make_article(journal="DEUTSCHES ÄRZTEBLATT International")
        assert _redaktions_bonus(a) > 0


# ---------------------------------------------------------------------------
# Interdisciplinary Bonus
# ---------------------------------------------------------------------------

class TestInterdisciplinaryBonus:
    def test_single_specialty_no_bonus(self):
        a = make_article(title="Cardiac surgery outcomes",
                         abstract="Heart failure treatment results")
        assert _interdisciplinary_bonus(a) == 0.0

    def test_two_specialties_small_bonus(self):
        # Cardiology + Nephrology keywords
        a = make_article(
            title="Cardiorenal syndrome treatment",
            abstract="Heart failure and kidney disease interaction with dialysis"
        )
        bonus = _interdisciplinary_bonus(a)
        assert bonus == 5.0

    def test_three_specialties_large_bonus(self):
        # Cardiology + Oncology + Neurology keywords
        a = make_article(
            title="Cardiovascular myocardial effects of chemotherapy on brain metastases",
            abstract="Cardiac arrhythmia tumor immunotherapy neurological seizure stroke complications"
        )
        bonus = _interdisciplinary_bonus(a)
        assert bonus == 10.0


# ---------------------------------------------------------------------------
# Abstract Length Modifier
# ---------------------------------------------------------------------------

class TestAbstractLengthModifier:
    def test_normal_abstract_no_penalty(self):
        a = make_article(abstract="Word " * 100, source="PubMed")
        assert _abstract_length_modifier(a) == 0.0

    def test_short_abstract_penalized(self):
        a = make_article(abstract="Very short.", source="PubMed")
        assert _abstract_length_modifier(a) == -5.0

    def test_news_source_exempt(self):
        a = make_article(abstract="Short.", source="Google News")
        assert _abstract_length_modifier(a) == 0.0

    def test_editorial_exempt(self):
        a = make_article(title="Editorial: perspective on cancer",
                         abstract="Brief", source="PubMed")
        assert _abstract_length_modifier(a) == 0.0


# ---------------------------------------------------------------------------
# Open Access Bonus
# ---------------------------------------------------------------------------

class TestOpenAccessBonus:
    def test_pmc_url(self):
        a = make_article(url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123")
        assert _open_access_bonus(a) == 5.0

    def test_plos_journal(self):
        a = make_article(journal="PLoS Medicine", url="https://example.com")
        assert _open_access_bonus(a) == 5.0

    def test_regular_article_no_bonus(self):
        a = make_article(url="https://example.com/article",
                         journal="Nature Medicine")
        assert _open_access_bonus(a) == 0.0


# ---------------------------------------------------------------------------
# Structured Abstract Bonus
# ---------------------------------------------------------------------------

class TestStructuredAbstractBonus:
    def test_full_imrad_abstract(self):
        abstract = (
            "Background: This study investigates... " * 5 +
            "Methods: We conducted a randomized... " * 5 +
            "Results: Patients showed significant... " * 5 +
            "Conclusion: Our findings demonstrate... " * 5
        )
        a = make_article(abstract=abstract)
        assert _structured_abstract_bonus(a) >= 4.0

    def test_partial_structure(self):
        abstract = (
            "Objective: To evaluate treatment outcomes. " * 5 +
            "Results: Significant improvement was observed. " * 5
        )
        a = make_article(abstract=abstract)
        assert _structured_abstract_bonus(a) >= 2.0

    def test_short_abstract_no_bonus(self):
        a = make_article(abstract="Short unstructured text.")
        assert _structured_abstract_bonus(a) == 0.0


# ---------------------------------------------------------------------------
# DOI Bonus
# ---------------------------------------------------------------------------

class TestDOIBonus:
    def test_valid_doi(self):
        a = make_article(doi="10.1056/NEJMoa2302392")
        assert _doi_bonus(a) == 2.0

    def test_no_doi(self):
        a = make_article(doi=None)
        assert _doi_bonus(a) == 0.0

    def test_empty_doi(self):
        a = make_article(doi="")
        assert _doi_bonus(a) == 0.0


# ---------------------------------------------------------------------------
# Paywall Modifier
# ---------------------------------------------------------------------------

class TestPaywallModifier:
    def test_nejm_with_full_abstract_no_penalty(self):
        a = make_article(journal="New England Journal of Medicine",
                         abstract="Word " * 100)
        assert _paywall_modifier(a) == 0.0

    def test_nejm_no_abstract_strong_penalty(self):
        a = make_article(journal="New England Journal of Medicine",
                         abstract="")
        assert _paywall_modifier(a) == -15.0

    def test_nejm_short_abstract_moderate_penalty(self):
        a = make_article(journal="JAMA",
                         abstract="Word " * 50)  # ~50 words
        assert _paywall_modifier(a) == -8.0

    def test_non_paywall_journal_no_penalty(self):
        a = make_article(journal="PLoS One", abstract="")
        assert _paywall_modifier(a) == 0.0


# ---------------------------------------------------------------------------
# Industry News Modifier
# ---------------------------------------------------------------------------

class TestIndustryNewsModifier:
    def test_merger_news_penalized(self):
        a = make_article(
            title="Pharma-Übernahme: Milliarden-Deal für Biotech-Firma",
            abstract="Die Akquisition umfasst Milliarden Euro"
        )
        assert _industry_news_modifier(a) < 0

    def test_clinical_trial_not_penalized(self):
        a = make_article(
            title="Phase III Zulassung für neues Medikament",
            abstract="FDA approval nach klinischer Studie"
        )
        assert _industry_news_modifier(a) == 0.0

    def test_regular_article_not_penalized(self):
        a = make_article(
            title="SGLT2 inhibitors in heart failure",
            abstract="Randomized trial outcomes"
        )
        assert _industry_news_modifier(a) == 0.0

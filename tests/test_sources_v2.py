"""Tests for sources v2 — feed registry, source_category, dedup, pre-filter."""

import pytest
from datetime import date

from src.models import Article, derive_source_category
from src.config import FEED_REGISTRY, RSS_FEEDS, JOURNAL_TIERS, get_active_feeds
from src.ingestion.rss_feeds import should_skip_adhoc_article
from src.processing.dedup import deduplicate, _normalize_title, _similarity_ratio
from tests.conftest import make_article


# ---------------------------------------------------------------------------
# Feed configuration tests
# ---------------------------------------------------------------------------

class TestFeedRegistry:
    """Tests for the FEED_REGISTRY configuration."""

    def test_all_feeds_registered(self):
        """All ~33 feeds are registered in FEED_REGISTRY."""
        assert len(FEED_REGISTRY) >= 30

    def test_all_feeds_have_source_category(self):
        """Every feed has a non-empty source_category."""
        for name, cfg in FEED_REGISTRY.items():
            assert cfg.source_category, f"Feed {name} has no source_category"

    def test_no_duplicate_urls(self):
        """No two active feeds share the same URL."""
        active_urls = [cfg.url for cfg in FEED_REGISTRY.values() if cfg.active]
        assert len(active_urls) == len(set(active_urls))

    def test_biorxiv_inactive(self):
        """bioRxiv is deactivated."""
        assert "bioRxiv" in FEED_REGISTRY
        assert FEED_REGISTRY["bioRxiv"].active is False

    def test_rss_feeds_dict_contains_specialty_journals(self):
        """RSS_FEEDS dict includes the new specialty journals."""
        assert "European Heart Journal" in RSS_FEEDS
        assert "Lancet Oncology" in RSS_FEEDS
        assert "JCO" in RSS_FEEDS
        assert "Diabetes Care" in RSS_FEEDS

    def test_get_active_feeds(self):
        """get_active_feeds returns only active feeds."""
        active = get_active_feeds()
        assert "bioRxiv" not in active
        assert "NEJM" in active

    def test_get_active_feeds_wave_filter(self):
        """Wave filter returns all active feeds when all are wave=1."""
        wave1 = get_active_feeds(wave=1)
        all_active = get_active_feeds()
        assert len(wave1) == len(all_active)

    def test_new_sources_in_registry(self):
        """New sources from the v2 spec are registered."""
        expected = [
            "G-BA", "IQWiG", "KBV", "Marburger Bund",
            "DGIM", "DGK", "DEGAM",
            "Medical Tribune", "Medscape DE", "Medscape EN",
            "arznei-telegramm", "AWMF Leitlinien",
        ]
        for name in expected:
            assert name in FEED_REGISTRY, f"Missing: {name}"


# ---------------------------------------------------------------------------
# source_category tests
# ---------------------------------------------------------------------------

class TestSourceCategory:
    """Tests for source_category derivation and mapping."""

    def test_derive_top_journal(self):
        assert derive_source_category("NEJM") == "top_journal"
        assert derive_source_category("The Lancet") == "top_journal"
        assert derive_source_category("BMJ") == "top_journal"

    def test_derive_specialty_journal(self):
        assert derive_source_category("European Heart Journal") == "specialty_journal"
        assert derive_source_category("Lancet Oncology") == "specialty_journal"

    def test_lancet_vs_lancet_oncology(self):
        """'Lancet Oncology' should be specialty, not top_journal."""
        assert derive_source_category("Lancet Oncology") == "specialty_journal"
        assert derive_source_category("The Lancet") == "top_journal"

    def test_derive_fachpresse_de(self):
        assert derive_source_category("Deutsches Ärzteblatt") == "fachpresse_de"
        assert derive_source_category("Apotheke Adhoc") == "fachpresse_de"

    def test_derive_berufspolitik(self):
        assert derive_source_category("KBV") == "berufspolitik"
        assert derive_source_category("Marburger Bund") == "berufspolitik"

    def test_derive_behoerde(self):
        assert derive_source_category("G-BA") == "behoerde"
        assert derive_source_category("BfArM") == "behoerde"

    def test_derive_news_aggregation(self):
        assert derive_source_category("Google News (Medizin)") == "news_aggregation"

    def test_derive_unknown_returns_none(self):
        assert derive_source_category("Unknown Source XYZ") is None


# ---------------------------------------------------------------------------
# Journal-Tier mapping tests
# ---------------------------------------------------------------------------

class TestJournalTiers:
    """Tests for the expanded journal-tier mapping."""

    def test_new_specialty_journals_mapped(self):
        """New specialty journals are in the tier mapping."""
        assert "european heart journal" in JOURNAL_TIERS
        assert "diabetes care" in JOURNAL_TIERS

    def test_berufspolitik_mapped(self):
        assert "g-ba" in JOURNAL_TIERS
        assert "kbv" in JOURNAL_TIERS
        assert "iqwig" in JOURNAL_TIERS

    def test_aufbereitete_mapped(self):
        assert "arznei-telegramm" in JOURNAL_TIERS
        assert "medscape" in JOURNAL_TIERS
        assert "medical tribune" in JOURNAL_TIERS

    def test_gba_higher_than_kbv(self):
        """G-BA (regulatory authority) scores higher than KBV."""
        assert JOURNAL_TIERS["g-ba"] > JOURNAL_TIERS["kbv"]


# ---------------------------------------------------------------------------
# Dedup tests
# ---------------------------------------------------------------------------

class TestDedup:
    """Tests for the updated deduplication logic."""

    def test_doi_match_is_duplicate(self):
        """Two articles with the same DOI are duplicates."""
        a1 = make_article(title="Study A", doi="10.1234/test", url="http://a.com")
        a2 = make_article(title="Study A (copy)", doi="10.1234/test", url="http://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1

    def test_similar_title_is_duplicate(self):
        """Two articles with >85% title similarity are duplicates."""
        a1 = make_article(title="Empagliflozin reduces heart failure mortality", url="http://a.com")
        a2 = make_article(title="Empagliflozin reduces heart failure mortality in patients", url="http://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1

    def test_different_articles_not_duplicate(self):
        """A NEJM study and a Medscape commentary are NOT duplicates."""
        a1 = make_article(
            title="Empagliflozin in Heart Failure with Preserved Ejection Fraction",
            source="NEJM",
            abstract="In this randomized trial, empagliflozin reduced...",
            url="http://nejm.com/1",
        )
        a2 = make_article(
            title="Medscape-Einordnung: Was die EMPEROR-Preserved-Studie für die Praxis bedeutet",
            source="Medscape DE",
            abstract="Die EMPEROR-Preserved-Studie zeigt erstmals...",
            url="http://medscape.com/1",
        )
        result = deduplicate([a1, a2])
        assert len(result) == 2, "Original study and commentary should NOT be deduplicated"

    def test_keeps_longer_abstract(self):
        """When deduplicating, keeps the article with the longer abstract."""
        a1 = make_article(title="Same Study Title", abstract="Short", url="http://a.com")
        a2 = make_article(title="Same Study Title", abstract="This is a much longer abstract with more detail", url="http://b.com")
        result = deduplicate([a1, a2])
        assert len(result) == 1
        assert len(result[0].abstract) > 10  # kept the longer one

    def test_similarity_ratio(self):
        """_similarity_ratio gives expected results."""
        assert _similarity_ratio("hello world", "hello world") == 1.0
        assert _similarity_ratio("hello world", "hello world!") > 0.9
        assert _similarity_ratio("completely different", "nothing alike here") < 0.5


# ---------------------------------------------------------------------------
# Apotheke Adhoc pre-filter tests
# ---------------------------------------------------------------------------

class TestAdhocPreFilter:
    """Tests for the Apotheke Adhoc industry/finance pre-filter."""

    def test_finance_article_filtered(self):
        """Pure finance article is filtered."""
        assert should_skip_adhoc_article(
            "Pharmakonzern X meldet Umsatzwachstum Q3",
            "Der Umsatz stieg um 15% auf 2,3 Mrd. Euro."
        ) is True

    def test_clinical_override_keeps_article(self):
        """Article with clinical content is NOT filtered even with finance keywords."""
        assert should_skip_adhoc_article(
            "Pharmakonzern X meldet Zulassung für neuen Wirkstoff",
            "Die EU-Zulassung des Wirkstoffs erfolgte nach Phase-III-Studie."
        ) is False

    def test_dividend_article_filtered(self):
        """Pure dividend/market article is filtered."""
        assert should_skip_adhoc_article(
            "Apothekenmarkt: Dividende steigt",
            "Die Dividende der Apothekengruppe stieg auf 2,50 Euro."
        ) is True

    def test_normal_medical_article_passes(self):
        """Normal medical article is not affected by the filter."""
        assert should_skip_adhoc_article(
            "Neue Rabattverträge für Antibiotika",
            "Ab Januar gelten neue Rabattverträge für häufig verordnete Antibiotika."
        ) is False

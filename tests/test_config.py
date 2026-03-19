"""Tests for src.config — validate constants, thresholds, and scoring weights."""

import pytest

from src import config


class TestScoringWeights:
    """Scoring weights should be sensible and sum correctly."""

    def test_weights_sum_to_one(self):
        total = (
            config.WEIGHT_JOURNAL
            + config.WEIGHT_STUDY_DESIGN
            + config.WEIGHT_RECENCY
            + config.WEIGHT_KEYWORD_BOOST
            + config.WEIGHT_ARZTRELEVANZ
        )
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"

    def test_weights_positive(self):
        for name in ("WEIGHT_JOURNAL", "WEIGHT_STUDY_DESIGN", "WEIGHT_RECENCY",
                      "WEIGHT_KEYWORD_BOOST", "WEIGHT_ARZTRELEVANZ"):
            val = getattr(config, name)
            assert val > 0, f"{name} should be positive, got {val}"


class TestScoreThresholds:
    def test_high_greater_than_mid(self):
        assert config.SCORE_THRESHOLD_HIGH > config.SCORE_THRESHOLD_MID

    def test_thresholds_in_range(self):
        assert 0 < config.SCORE_THRESHOLD_MID < 100
        assert 0 < config.SCORE_THRESHOLD_HIGH < 100


class TestJournalTiers:
    """JOURNAL_TIERS should map known journals to valid scores."""

    def test_all_scores_in_range(self):
        for journal, score in config.JOURNAL_TIERS.items():
            assert 0 <= score <= 100, f"{journal}: score {score} out of range"

    def test_nejm_top_tier(self):
        # NEJM should be among the highest-scored journals
        nejm_score = None
        for key, val in config.JOURNAL_TIERS.items():
            if "nejm" in key.lower() or "new england" in key.lower():
                nejm_score = val
                break
        assert nejm_score is not None, "NEJM not found in JOURNAL_TIERS"
        assert nejm_score >= 90


class TestSpecialtyMesh:
    """SPECIALTY_MESH should cover all 13 specialties with non-empty keyword lists."""

    def test_at_least_10_specialties(self):
        assert len(config.SPECIALTY_MESH) >= 10

    def test_all_have_keywords(self):
        for spec, keywords in config.SPECIALTY_MESH.items():
            assert len(keywords) > 0, f"Specialty '{spec}' has no keywords"


class TestLLMConfig:
    """LLM task-provider mapping should be complete."""

    def test_all_tasks_have_providers(self):
        required_tasks = ["scoring", "summary", "article_draft"]
        for task in required_tasks:
            providers = config.LLM_TASK_PROVIDERS.get(task, [])
            assert len(providers) > 0, f"Task '{task}' has no providers"

    def test_provider_chain_returns_list(self):
        chain = config.get_provider_chain("scoring")
        assert isinstance(chain, list)
        assert len(chain) > 0

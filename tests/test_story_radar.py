"""Tests for src.processing.story_radar — pitch scoring logic."""

import pytest

from src.processing.story_radar import _compute_pitch_score
from tests.conftest import make_trend


class TestPitchScore:
    """Test the pure pitch-scoring function."""

    def test_baseline_stable_trend(self):
        """A basic stable trend with average metrics."""
        trend = make_trend(avg_score=50.0, momentum="stable",
                           is_cross_specialty=False, evidence_trend="stable",
                           high_tier_ratio=0.1, count_current=3)
        score = _compute_pitch_score(trend)
        assert 0 <= score <= 100

    def test_exploding_cross_specialty_trend(self):
        """An exploding cross-specialty trend should score very high."""
        trend = make_trend(
            avg_score=85.0, momentum="exploding",
            is_cross_specialty=True, evidence_trend="rising",
            high_tier_ratio=0.5, count_current=10,
        )
        score = _compute_pitch_score(trend)
        assert score >= 80, f"Ideal trend scored only {score}"

    def test_falling_trend_penalized(self):
        """A falling trend should score lower than a rising one."""
        rising = make_trend(momentum="rising", avg_score=60.0, count_current=8)
        falling = make_trend(momentum="falling", avg_score=60.0, count_current=8)
        assert _compute_pitch_score(rising) > _compute_pitch_score(falling)

    def test_cross_specialty_bonus(self):
        """Cross-specialty trends get a 20-point bonus."""
        base = make_trend(is_cross_specialty=False, avg_score=50.0)
        cross = make_trend(is_cross_specialty=True, avg_score=50.0)
        diff = _compute_pitch_score(cross) - _compute_pitch_score(base)
        assert diff == 20.0

    def test_evidence_rising_bonus(self):
        """Rising evidence trend adds 15 points."""
        base = make_trend(evidence_trend="stable", avg_score=50.0)
        rising = make_trend(evidence_trend="rising", avg_score=50.0)
        diff = _compute_pitch_score(rising) - _compute_pitch_score(base)
        assert diff == 15.0

    def test_high_tier_journal_bonus(self):
        """High-tier ratio > 0.3 adds 10 points."""
        low = make_trend(high_tier_ratio=0.1, avg_score=50.0)
        high = make_trend(high_tier_ratio=0.5, avg_score=50.0)
        diff = _compute_pitch_score(high) - _compute_pitch_score(low)
        assert diff == 10.0

    def test_cluster_size_sweet_spot(self):
        """5-15 articles is the sweet spot (+15 points)."""
        small = make_trend(count_current=2, avg_score=50.0)
        sweet = make_trend(count_current=10, avg_score=50.0)
        large = make_trend(count_current=20, avg_score=50.0)
        assert _compute_pitch_score(sweet) > _compute_pitch_score(small)
        assert _compute_pitch_score(sweet) > _compute_pitch_score(large)

    def test_score_clamped_to_0_100(self):
        """Score should never exceed 0-100 range."""
        # Worst case: negative momentum, low avg_score
        worst = make_trend(avg_score=0.0, momentum="falling",
                           is_cross_specialty=False, evidence_trend="falling",
                           high_tier_ratio=0.0, count_current=1)
        assert _compute_pitch_score(worst) >= 0

        # Best case: all bonuses
        best = make_trend(avg_score=100.0, momentum="exploding",
                          is_cross_specialty=True, evidence_trend="rising",
                          high_tier_ratio=1.0, count_current=10)
        assert _compute_pitch_score(best) <= 100

    def test_avg_score_scales_proportionally(self):
        """Higher avg_score should give higher pitch score."""
        low = make_trend(avg_score=20.0)
        high = make_trend(avg_score=80.0)
        assert _compute_pitch_score(high) > _compute_pitch_score(low)

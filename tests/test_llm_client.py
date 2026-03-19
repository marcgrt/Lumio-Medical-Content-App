"""Tests for src.llm_client — rate limiting & utility functions."""

from datetime import date

import pytest

from src.llm_client import (
    _track_call,
    _is_key_rate_limited,
    _call_counts,
    _RATE_LIMITS,
    get_usage_stats,
)


class TestRateLimiting:
    def setup_method(self):
        """Reset call counters before each test."""
        _call_counts.clear()

    def test_track_call_increments(self):
        _track_call("test_provider", 0)
        assert _call_counts["test_provider#0"] == (date.today(), 1)
        _track_call("test_provider", 0)
        assert _call_counts["test_provider#0"] == (date.today(), 2)

    def test_track_call_separate_keys(self):
        _track_call("groq", 0)
        _track_call("groq", 1)
        assert _call_counts["groq#0"][1] == 1
        assert _call_counts["groq#1"][1] == 1

    def test_not_rate_limited_initially(self):
        assert _is_key_rate_limited("groq", 0) is False

    def test_rate_limited_at_limit(self):
        limit = _RATE_LIMITS.get("groq", {}).get("rpd", 10_000)
        _call_counts["groq#0"] = (date.today(), limit)
        assert _is_key_rate_limited("groq", 0) is True

    def test_not_rate_limited_below_limit(self):
        _call_counts["groq#0"] = (date.today(), 10)
        assert _is_key_rate_limited("groq", 0) is False

    def test_new_day_resets(self):
        yesterday = date(2020, 1, 1)
        _call_counts["groq#0"] = (yesterday, 99999)
        assert _is_key_rate_limited("groq", 0) is False

    def test_unknown_provider_high_limit(self):
        _call_counts["unknown#0"] = (date.today(), 5000)
        assert _is_key_rate_limited("unknown", 0) is False


class TestUsageStats:
    def setup_method(self):
        _call_counts.clear()

    def test_empty_stats(self):
        stats = get_usage_stats()
        assert stats == {}

    def test_stats_after_calls(self):
        _call_counts["groq#0"] = (date.today(), 42)
        stats = get_usage_stats()
        assert "groq" in stats
        assert stats["groq"]["calls_today"] == 42

    def test_stale_date_excluded(self):
        _call_counts["groq#0"] = (date(2020, 1, 1), 500)
        stats = get_usage_stats()
        assert stats == {}, "Yesterday's stats should not appear"

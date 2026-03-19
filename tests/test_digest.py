"""Tests for src.digest — article diversification and digest generation."""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from src.digest import get_top_articles, _score_color
from tests.conftest import make_article, make_articles


class TestScoreColor:
    """Test the color coding helper."""

    def test_high_score_green(self):
        assert _score_color(80) == "#22c55e"

    def test_mid_score_yellow(self):
        assert _score_color(50) == "#eab308"

    def test_low_score_red(self):
        assert _score_color(20) == "#ef4444"


class TestDiversification:
    """Test that get_top_articles diversifies by specialty."""

    @patch("src.digest.get_session")
    @patch("src.digest.get_engine")
    def test_caps_per_specialty(self, mock_engine, mock_session):
        """Max 3 articles per specialty by default."""
        # Create 10 cardiology + 5 oncology articles
        pool = []
        for i in range(10):
            pool.append(make_article(
                id=i, title=f"Cardio {i}", specialty="Kardiologie",
                relevance_score=90 - i, pub_date=date.today(),
                url=f"https://test.com/{i}",
            ))
        for i in range(10, 15):
            pool.append(make_article(
                id=i, title=f"Onco {i}", specialty="Onkologie",
                relevance_score=85 - i, pub_date=date.today(),
                url=f"https://test.com/{i}",
            ))

        # Mock session to return our pool
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.exec = MagicMock(return_value=MagicMock(all=MagicMock(return_value=pool)))
        mock_session.return_value = mock_ctx

        result = get_top_articles(n=10, days_back=2, max_per_specialty=3)

        # Should have max 3 from Kardiologie
        cardio = [a for a in result if a.specialty == "Kardiologie"]
        assert len(cardio) <= 3

    @patch("src.digest.get_session")
    @patch("src.digest.get_engine")
    def test_respects_n_limit(self, mock_engine, mock_session):
        """Should return at most n articles."""
        pool = make_articles(30, specialty="Allgemeinmedizin",
                             relevance_score=70, pub_date=date.today())

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.exec = MagicMock(return_value=MagicMock(all=MagicMock(return_value=pool)))
        mock_session.return_value = mock_ctx

        result = get_top_articles(n=5, days_back=2, max_per_specialty=10)
        assert len(result) <= 5

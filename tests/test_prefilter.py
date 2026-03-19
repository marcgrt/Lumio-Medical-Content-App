"""Tests for src.processing.prefilter — response parsing & batch logic."""

import json

import pytest

from src.processing.prefilter import (
    _parse_response,
    _parse_batch_response,
    _strip_markdown_fences,
    _build_batch_message,
)
from src.models import Article


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
# Single-article response parsing
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_relevant_true(self):
        raw = '{"relevant": true, "fachgebiet": "Kardiologie"}'
        relevant, fach = _parse_response(raw)
        assert relevant is True
        assert fach == "Kardiologie"

    def test_relevant_false(self):
        raw = '{"relevant": false, "fachgebiet": "Sonstige"}'
        relevant, fach = _parse_response(raw)
        assert relevant is False
        assert fach == "Sonstige"

    def test_markdown_fences(self):
        raw = '```json\n{"relevant": true, "fachgebiet": "Neurologie"}\n```'
        relevant, fach = _parse_response(raw)
        assert relevant is True
        assert fach == "Neurologie"

    def test_invalid_specialty(self):
        raw = '{"relevant": true, "fachgebiet": "Astrologie"}'
        relevant, fach = _parse_response(raw)
        assert relevant is True
        assert fach is None, "Invalid specialty should be set to None"

    def test_invalid_json_keeps_article(self):
        relevant, fach = _parse_response("this is not json")
        assert relevant is True, "Parse failure should keep the article"
        assert fach is None

    def test_empty_string(self):
        relevant, fach = _parse_response("")
        assert relevant is True

    def test_missing_relevant_key(self):
        raw = '{"fachgebiet": "Onkologie"}'
        relevant, fach = _parse_response(raw)
        assert relevant is True, "Missing 'relevant' should default to True"
        assert fach == "Onkologie"


# ---------------------------------------------------------------------------
# Batch response parsing
# ---------------------------------------------------------------------------

class TestParseBatchResponse:
    def test_valid_array(self):
        raw = json.dumps([
            {"id": 1, "relevant": True, "fachgebiet": "Kardiologie"},
            {"id": 2, "relevant": False, "fachgebiet": "Sonstige"},
            {"id": 3, "relevant": True, "fachgebiet": "Neurologie"},
        ])
        results = _parse_batch_response(raw, 3)
        assert results is not None
        assert len(results) == 3
        assert results[0] == (True, "Kardiologie")
        assert results[1] == (False, "Sonstige")
        assert results[2] == (True, "Neurologie")

    def test_wrapped_in_dict(self):
        raw = json.dumps({
            "results": [
                {"id": 1, "relevant": True, "fachgebiet": "Onkologie"},
                {"id": 2, "relevant": False, "fachgebiet": "Sonstige"},
            ]
        })
        results = _parse_batch_response(raw, 2)
        assert results is not None
        assert len(results) == 2

    def test_markdown_fences(self):
        raw = "```json\n" + json.dumps([
            {"id": 1, "relevant": True, "fachgebiet": "Kardiologie"},
        ]) + "\n```"
        results = _parse_batch_response(raw, 1)
        assert results is not None
        assert results[0] == (True, "Kardiologie")

    def test_invalid_json_returns_none(self):
        results = _parse_batch_response("not json", 3)
        assert results is None

    def test_fewer_results_than_expected(self):
        raw = json.dumps([
            {"id": 1, "relevant": True, "fachgebiet": "Kardiologie"},
        ])
        results = _parse_batch_response(raw, 3)
        assert results is not None
        assert len(results) == 3
        # Missing articles default to (True, None)
        assert results[1] == (True, None)
        assert results[2] == (True, None)

    def test_out_of_order_ids(self):
        raw = json.dumps([
            {"id": 3, "relevant": False, "fachgebiet": "Sonstige"},
            {"id": 1, "relevant": True, "fachgebiet": "Kardiologie"},
            {"id": 2, "relevant": True, "fachgebiet": "Neurologie"},
        ])
        results = _parse_batch_response(raw, 3)
        assert results is not None
        assert results[0] == (True, "Kardiologie")
        assert results[1] == (True, "Neurologie")
        assert results[2] == (False, "Sonstige")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestStripMarkdownFences:
    def test_json_fence(self):
        assert _strip_markdown_fences("```json\n{}\n```") == "{}"

    def test_no_fence(self):
        assert _strip_markdown_fences('{"a": 1}') == '{"a": 1}'

    def test_only_opening_fence(self):
        assert _strip_markdown_fences("```\n{}") == "{}"


class TestBuildBatchMessage:
    def test_numbered_articles(self):
        articles = [
            _make_article(title="Article One"),
            _make_article(title="Article Two"),
        ]
        msg = _build_batch_message(articles)
        assert "--- Artikel 1 ---" in msg
        assert "--- Artikel 2 ---" in msg
        assert "Article One" in msg
        assert "Article Two" in msg

    def test_abstract_truncation(self):
        long_abstract = "x" * 2000
        articles = [_make_article(abstract=long_abstract)]
        msg = _build_batch_message(articles)
        # Batch uses 800 chars max per abstract
        assert len(msg) < 1500

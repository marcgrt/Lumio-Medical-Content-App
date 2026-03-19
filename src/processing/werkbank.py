"""Artikel-Werkbank -- Strukturierte Recherche-Mappe fuer Redakteure.

Builds a structured research dossier from a search query: articles sorted by
evidence level, grouped into an evidence pyramid, with score breakdowns and
auto-suggested watchlist keywords.
"""
from __future__ import annotations

import json
import logging
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta

from src.config import STUDY_DESIGN_KEYWORDS
from src.models import Article, get_session, fts5_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvidenceTier:
    """A tier in the evidence pyramid."""
    name: str           # e.g. "Meta-Analysen & Systematic Reviews"
    level: int          # 1 = highest
    articles: list      # list of Article-like dicts
    count: int = 0


@dataclass
class ResearchDossier:
    """Complete research dossier for a search topic."""
    query: str
    total_results: int
    evidence_pyramid: list       # list[EvidenceTier], sorted by level (1=top)
    specialty_breakdown: dict    # Specialty -> count
    journal_breakdown: dict      # Journal -> count
    score_stats: dict            # min, max, avg, median
    time_range: dict             # earliest, latest pub_date
    suggested_watchlist_keywords: list  # Auto-extracted keywords for watchlist
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Evidence tier definitions
# ---------------------------------------------------------------------------

EVIDENCE_TIERS = [
    (1, "Meta-Analysen & Systematic Reviews",
     ["meta-analysis", "meta analysis", "systematic review",
      "metaanalyse", "systematische ubersicht", "systematische uebersicht"]),
    (2, "RCTs & Randomisierte Studien",
     ["randomized", "randomised", "rct", "randomized controlled",
      "randomisiert", "randomisierte studie"]),
    (3, "Leitlinien & Guidelines",
     ["leitlinie", "guideline", "s3-leitlinie", "s3 leitlinie",
      "s2k-leitlinie", "s2e-leitlinie", "s1-leitlinie",
      "nice guideline", "esc guideline", "awmf",
      "practice guideline", "clinical practice guideline",
      "behandlungsempfehlung", "therapieempfehlung"]),
    (4, "Kohortenstudien & Observational",
     ["cohort study", "cohort", "case-control", "case control",
      "cross-sectional", "cross sectional", "prevalence study",
      "observational", "kohortenstudie", "beobachtungsstudie",
      "registerstudie"]),
    (5, "Reviews & Expert Opinion",
     ["review", "editorial", "perspective", "viewpoint", "expert review",
      "kommentar", "standpunkt", "narrative review", "clinical review",
      "state of the art", "uebersichtsarbeit", "fachartikel"]),
    (6, "News, Fallberichte & Sonstiges",
     ["news", "press release", "nachricht", "meldung",
      "case report", "case series", "fallbericht",
      "opinion", "letter to the editor", "correspondence", "leserbrief"]),
]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_dossier(query: str, articles: list = None,
                  days_back: int = 30, max_articles: int = 100) -> ResearchDossier:
    """Build a structured research dossier from a search query.

    Parameters
    ----------
    query : str
        The search term entered by the editor.
    articles : list[Article], optional
        Pre-fetched articles (from get_articles). If *None*, the function
        performs its own FTS5 search.
    days_back : int
        How many days back to search (only used when *articles* is None).
    max_articles : int
        Maximum number of articles to include in the dossier.
    """

    if articles is None:
        articles = _fetch_articles(query, days_back, max_articles)

    # Cap to max_articles (already sorted by relevance by caller)
    articles = articles[:max_articles]

    # Classify each article into an evidence tier
    tier_buckets: dict[int, list] = {i: [] for i in range(1, 7)}
    for a in articles:
        tier_level = _classify_evidence_tier(a)
        article_dict = _article_to_dict(a, tier_level)
        tier_buckets[tier_level].append(article_dict)

    # Sort articles within each tier by score DESC
    for level in tier_buckets:
        tier_buckets[level].sort(
            key=lambda x: x.get("relevance_score", 0), reverse=True
        )

    # Build evidence pyramid
    evidence_pyramid = []
    for level, name, _keywords in EVIDENCE_TIERS:
        bucket = tier_buckets[level]
        evidence_pyramid.append(EvidenceTier(
            name=name,
            level=level,
            articles=bucket,
            count=len(bucket),
        ))

    # Compute specialty breakdown
    specialty_counter = Counter()
    for a in articles:
        if a.specialty:
            specialty_counter[a.specialty] += 1
    specialty_breakdown = dict(specialty_counter.most_common())

    # Compute journal breakdown
    journal_counter = Counter()
    for a in articles:
        if a.journal:
            journal_counter[a.journal] += 1
    journal_breakdown = dict(journal_counter.most_common(10))

    # Score statistics
    scores = [a.relevance_score for a in articles if a.relevance_score is not None]
    if scores:
        score_stats = {
            "min": round(min(scores), 1),
            "max": round(max(scores), 1),
            "avg": round(statistics.mean(scores), 1),
            "median": round(statistics.median(scores), 1),
        }
    else:
        score_stats = {"min": 0, "max": 0, "avg": 0, "median": 0}

    # Time range
    dates = [a.pub_date for a in articles if a.pub_date is not None]
    if dates:
        time_range = {
            "earliest": min(dates),
            "latest": max(dates),
        }
    else:
        time_range = {"earliest": None, "latest": None}

    # Suggest watchlist keywords
    suggested_keywords = _suggest_keywords(query, articles)

    return ResearchDossier(
        query=query,
        total_results=len(articles),
        evidence_pyramid=evidence_pyramid,
        specialty_breakdown=specialty_breakdown,
        journal_breakdown=journal_breakdown,
        score_stats=score_stats,
        time_range=time_range,
        suggested_watchlist_keywords=suggested_keywords,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_articles(query: str, days_back: int, max_articles: int) -> list:
    """Fetch articles via FTS5 or ILIKE fallback."""
    from sqlmodel import select, col

    fts_ids = fts5_search(query, limit=max_articles)

    with get_session() as session:
        stmt = select(Article)

        if days_back > 0:
            cutoff = date.today() - timedelta(days=days_back)
            stmt = stmt.where(
                (Article.pub_date >= cutoff) | (Article.pub_date.is_(None))
            )

        if fts_ids:
            stmt = stmt.where(col(Article.id).in_(fts_ids))
        else:
            pattern = f"%{query}%"
            stmt = stmt.where(
                col(Article.title).ilike(pattern)
                | col(Article.abstract).ilike(pattern)
            )

        stmt = stmt.limit(max_articles)
        articles = session.exec(stmt).all()

        # Detach from session
        result = [a.detach() for a in articles]

    # Re-sort by FTS rank if used, otherwise by relevance_score
    if fts_ids:
        id_rank = {aid: rank for rank, aid in enumerate(fts_ids)}
        result.sort(key=lambda a: id_rank.get(a.id, 999999))
    else:
        result.sort(key=lambda a: a.relevance_score or 0, reverse=True)

    return result


def _classify_evidence_tier(article) -> int:
    """Classify article into evidence tier (1=highest, 6=lowest).

    Checks study_type field first, then scans title and abstract for keywords.
    Uses EVIDENCE_TIERS definitions for matching.
    """
    # Build searchable text
    text_parts = []
    if hasattr(article, "study_type") and article.study_type:
        text_parts.append(article.study_type.lower())
    if hasattr(article, "title") and article.title:
        text_parts.append(article.title.lower())
    if hasattr(article, "abstract") and article.abstract:
        text_parts.append(article.abstract.lower())
    if hasattr(article, "highlight_tags") and article.highlight_tags:
        text_parts.append(article.highlight_tags.lower())

    searchable = " ".join(text_parts)

    # Check study_type directly first (most reliable signal)
    study_type = (article.study_type or "").lower() if hasattr(article, "study_type") else ""
    if study_type:
        for level, _name, keywords in EVIDENCE_TIERS:
            for kw in keywords:
                if kw in study_type:
                    return level

    # Fall back to title + abstract keyword matching
    for level, _name, keywords in EVIDENCE_TIERS:
        for kw in keywords:
            if kw in searchable:
                return level

    # Default: tier 6 (News/Other)
    return 6


def _article_to_dict(article, tier_level: int) -> dict:
    """Convert an Article to a dict with score breakdown details."""
    score_details = _extract_score_details(article)

    return {
        "id": article.id,
        "title": article.title,
        "abstract": article.abstract,
        "url": article.url,
        "journal": article.journal,
        "pub_date": article.pub_date,
        "relevance_score": article.relevance_score or 0,
        "specialty": article.specialty,
        "study_type": article.study_type,
        "summary_de": article.summary_de,
        "highlight_tags": article.highlight_tags,
        "score_breakdown": article.score_breakdown,
        "score_details": score_details,
        "source": article.source,
        "authors": article.authors,
        "language": article.language,
        "tier_level": tier_level,
        "status": article.status,
    }


def _extract_score_details(article) -> dict:
    """Extract human-readable score breakdown from article.

    Returns a dict of {component: {score: float, label: str}, ...}.
    Handles both rule-based and LLM-based score breakdowns.
    """
    if not article.score_breakdown:
        return {}

    try:
        bd = json.loads(article.score_breakdown)
    except (json.JSONDecodeError, TypeError):
        return {}

    is_llm = bd.get("scorer") == "llm"

    if is_llm:
        return {
            "Studientyp": {
                "score": bd.get("studientyp", 0),
                "max": 20,
                "label": bd.get("begr_studientyp", ""),
            },
            "Klinische Relevanz": {
                "score": bd.get("klinische_relevanz", 0),
                "max": 20,
                "label": bd.get("begr_klinische_relevanz", ""),
            },
            "Neuigkeitswert": {
                "score": bd.get("neuigkeitswert", 0),
                "max": 20,
                "label": bd.get("begr_neuigkeitswert", ""),
            },
            "Zielgruppen-Fit": {
                "score": bd.get("zielgruppen_fit", 0),
                "max": 20,
                "label": bd.get("begr_zielgruppen_fit", ""),
            },
            "Quellenqualitaet": {
                "score": bd.get("quellenqualitaet", 0),
                "max": 20,
                "label": bd.get("begr_quellenqualitaet", ""),
            },
        }
    else:
        details = {}
        component_map = {
            "journal": ("Journal", 30),
            "design": ("Studiendesign", 25),
            "recency": ("Aktualitaet", 20),
            "keywords": ("Keyword-Boost", 15),
            "arztrelevanz": ("Arztrelevanz", 10),
            "bonus": ("Redaktions-Bonus", 10),
            "preference": ("Praeferenz-Bonus", 15),
        }
        for key, (label, max_val) in component_map.items():
            val = bd.get(key, 0)
            if val > 0:
                details[label] = {"score": val, "max": max_val, "label": ""}
        return details


def _suggest_keywords(query: str, articles: list) -> list[str]:
    """Auto-suggest watchlist keywords from query and article content.

    Extracts the query terms plus frequent meaningful terms from article
    titles. Returns a deduplicated list of 5-8 keywords.
    """
    # Start with query terms (split on whitespace and common separators)
    query_terms = [t.strip().lower() for t in re.split(r"[\s,;+]+", query) if len(t.strip()) >= 3]

    # Collect title words from top-scoring articles
    word_counter = Counter()
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "are", "was",
        "were", "been", "have", "has", "had", "not", "but", "its", "can",
        "will", "may", "all", "one", "two", "new", "use", "used", "nach",
        "eine", "einer", "eines", "einem", "einen", "der", "die", "das",
        "und", "oder", "von", "mit", "bei", "zur", "zum", "auf", "aus",
        "ist", "sind", "wird", "wurde", "werden", "als", "auch", "sich",
        "den", "dem", "des", "ein", "wie", "nur", "noch", "mehr", "ueber",
        "their", "than", "into", "most", "other", "some", "such", "what",
        "between", "study", "studie", "results", "patients", "patienten",
        "ergebnisse", "analysis",
    }

    for a in articles[:30]:  # top 30 articles
        title = a.title if hasattr(a, "title") else ""
        if not title:
            continue
        words = re.findall(r"[a-zA-ZäöüßÄÖÜ]{3,}", title.lower())
        for w in words:
            if w not in stopwords and w not in query_terms:
                word_counter[w] += 1

    # Take the most frequent title terms
    top_words = [w for w, _count in word_counter.most_common(10) if _count >= 2]

    # Combine: query terms first, then top title terms
    combined = list(dict.fromkeys(query_terms + top_words))  # deduplicate, preserve order

    # Also add specialty if there is a dominant one
    spec_counter = Counter()
    for a in articles:
        spec = a.specialty if hasattr(a, "specialty") else None
        if spec:
            spec_counter[spec] += 1
    if spec_counter:
        top_spec = spec_counter.most_common(1)[0][0]
        if top_spec.lower() not in [k.lower() for k in combined]:
            combined.append(top_spec)

    return combined[:8]

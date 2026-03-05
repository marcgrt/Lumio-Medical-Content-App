"""Multi-tier relevance scoring for medical articles."""

import math
from datetime import date

from src.config import (
    JOURNAL_TIERS,
    DEFAULT_JOURNAL_SCORE,
    STUDY_DESIGN_KEYWORDS,
    DEFAULT_STUDY_DESIGN_SCORE,
    WEIGHT_JOURNAL,
    WEIGHT_STUDY_DESIGN,
    WEIGHT_RECENCY,
    WEIGHT_KEYWORD_BOOST,
    SAFETY_KEYWORDS,
    GUIDELINE_KEYWORDS,
    LANDMARK_KEYWORDS,
    SAFETY_BOOST,
    GUIDELINE_BOOST,
    LANDMARK_BOOST,
)
from src.models import Article


def _journal_score(article: Article) -> float:
    """Score based on journal tier."""
    journal = (article.journal or "").lower()
    for fragment, score in JOURNAL_TIERS.items():
        if fragment in journal:
            return score
    return DEFAULT_JOURNAL_SCORE


def _study_design_score(article: Article) -> float:
    """Score based on detected study design."""
    text = f"{article.title or ''} {article.abstract or ''} {article.study_type or ''}".lower()
    for keywords, score in STUDY_DESIGN_KEYWORDS:
        if any(kw in text for kw in keywords):
            return score
    return DEFAULT_STUDY_DESIGN_SCORE


def _recency_score(article: Article) -> float:
    """Exponential decay: today=100, -10/day."""
    if not article.pub_date:
        return 50.0  # unknown date → middle value
    days_old = (date.today() - article.pub_date).days
    return max(0.0, 100.0 * math.exp(-0.1 * days_old))


def _keyword_boost(article: Article) -> float:
    """Bonus points for safety, guideline, and landmark keywords."""
    text = f"{article.title or ''} {article.abstract or ''}".lower()
    boost = 0.0
    if any(kw in text for kw in SAFETY_KEYWORDS):
        boost = max(boost, SAFETY_BOOST)
    if any(kw in text for kw in GUIDELINE_KEYWORDS):
        boost = max(boost, GUIDELINE_BOOST)
    if any(kw in text for kw in LANDMARK_KEYWORDS):
        boost = max(boost, LANDMARK_BOOST)
    return boost


def _interdisciplinary_bonus(article: Article) -> float:
    """Bonus for articles spanning multiple specialties (often more interesting)."""
    from src.config import SPECIALTY_MESH

    text = (
        f"{article.title or ''} {article.abstract or ''} "
        f"{article.mesh_terms or ''}"
    ).lower()

    hit_count = 0
    for keywords in SPECIALTY_MESH.values():
        if any(kw in text for kw in keywords):
            hit_count += 1

    # Bonus kicks in at 2+ specialties
    if hit_count >= 3:
        return 10.0
    elif hit_count >= 2:
        return 5.0
    return 0.0


def _abstract_length_modifier(article: Article) -> float:
    """Malus for very short abstracts (editorials, comments)."""
    abstract = article.abstract or ""
    word_count = len(abstract.split())
    if word_count < 50:
        return -10.0  # likely editorial / comment / no real abstract
    return 0.0


def compute_relevance_score(article: Article) -> float:
    """Compute composite relevance score (0-100)."""
    j = _journal_score(article)
    s = _study_design_score(article)
    r = _recency_score(article)
    k = _keyword_boost(article)

    score = (
        WEIGHT_JOURNAL * j
        + WEIGHT_STUDY_DESIGN * s
        + WEIGHT_RECENCY * r
        + WEIGHT_KEYWORD_BOOST * k
    )

    # Additional modifiers
    score += _interdisciplinary_bonus(article)
    score += _abstract_length_modifier(article)

    return round(min(100.0, max(0.0, score)), 1)


def score_articles(articles: list[Article]) -> list[Article]:
    """Score a list of articles in place and return them sorted by score."""
    for article in articles:
        article.relevance_score = compute_relevance_score(article)
    articles.sort(key=lambda a: a.relevance_score, reverse=True)
    return articles

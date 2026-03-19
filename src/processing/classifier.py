"""Specialty classification based on MeSH terms and keyword matching."""

from typing import Optional

from src.config import (
    SPECIALTY_MESH,
    ALERT_RULES_UNCONDITIONAL,
    ALERT_RULES_CONTEXTUAL,
    ALERT_SUPPRESS_TITLE_PATTERNS,
)
from src.models import Article


def classify_specialty(article: Article) -> Optional[str]:
    """Classify article into a medical specialty."""
    text = (
        f"{article.title or ''} {article.abstract or ''} "
        f"{article.mesh_terms or ''}"
    ).lower()

    best_match: Optional[str] = None
    best_count = 0

    for specialty, keywords in SPECIALTY_MESH.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_match = specialty

    return best_match if best_count >= 1 else None


def detect_alert(article: Article) -> bool:
    """Check if article should be flagged as ALERT.

    Two-tier system:
    1. Suppress: title patterns that are known false positives → skip
    2. Unconditional: high-specificity keywords → always alert
    3. Contextual: ambiguous keywords + action context → alert
    """
    title_lower = (article.title or "").lower()
    text = f"{title_lower} {(article.abstract or '').lower()}"

    # Step 1: Suppress known false-positive title patterns
    if any(pat in title_lower for pat in ALERT_SUPPRESS_TITLE_PATTERNS):
        return False

    # Step 2: Unconditional keywords — always trigger
    if any(kw in text for kw in ALERT_RULES_UNCONDITIONAL):
        return True

    # Step 3: Contextual keywords — require co-occurrence
    for trigger, context_words in ALERT_RULES_CONTEXTUAL:
        if trigger in text:
            if any(ctx in text for ctx in context_words):
                return True

    return False


def classify_articles(articles: list) -> list:
    """Classify all articles by specialty and detect alerts."""
    for article in articles:
        article.specialty = classify_specialty(article)
        if detect_alert(article):
            article.status = "ALERT"
    return articles

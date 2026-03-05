"""Specialty classification based on MeSH terms and keyword matching."""

from typing import Optional

from src.config import SPECIALTY_MESH, ALERT_KEYWORDS
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
    """Check if article should be flagged as ALERT."""
    text = f"{article.title or ''} {article.abstract or ''}".lower()
    return any(kw in text for kw in ALERT_KEYWORDS)


def classify_articles(articles: list[Article]) -> list[Article]:
    """Classify all articles by specialty and detect alerts."""
    for article in articles:
        article.specialty = classify_specialty(article)
        if detect_alert(article):
            article.status = "ALERT"
    return articles

"""Specialty classification based on MeSH terms and keyword matching.

Also provides a keyword-based medical-relevance check that works
without any LLM — used as a fallback when the LLM prefilter is
rate-limited.
"""

import logging
from typing import Optional

from src.config import (
    SPECIALTY_MESH,
    ALERT_RULES_UNCONDITIONAL,
    ALERT_RULES_CONTEXTUAL,
    ALERT_SUPPRESS_TITLE_PATTERNS,
)
from src.models import Article

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Broad medical-relevance keywords (language-agnostic).
# If NONE of these appear in title+abstract, the article is almost certainly
# not relevant for a physician dashboard.  This is deliberately broad — we
# want high recall (keep edge cases) and only drop obvious non-medical items.
# ---------------------------------------------------------------------------
_MEDICAL_KEYWORDS: list[str] = [
    # EN clinical
    "patient", "clinical", "therapy", "treatment", "disease", "diagnosis",
    "symptom", "surgery", "surgical", "hospital", "physician", "nurse",
    "medication", "drug", "dose", "dosing", "trial", "randomized",
    "placebo", "outcome", "mortality", "morbidity", "survival",
    "efficacy", "safety", "adverse", "infection", "vaccine",
    "screening", "prevention", "guideline", "prognosis",
    "chronic", "acute", "syndrome", "disorder", "pathology",
    "oncology", "cardiology", "neurology", "pediatric", "geriatric",
    "epidemiology", "prevalence", "incidence", "cohort", "meta-analysis",
    "systematic review", "health care", "healthcare", "medical",
    "pharmaceutical", "pharmacol", "biomarker", "imaging",
    "transplant", "rehabilitation", "palliative", "intensive care",
    "emergency", "outpatient", "inpatient", "primary care",
    # DE clinical
    "patient", "klinisch", "therapie", "behandlung", "krankheit",
    "diagnose", "medikament", "arzt", "ärzt", "pflege", "krankenhaus",
    "klinik", "studie", "leitlinie", "prävention", "impfung",
    "chirurgie", "operativ", "praxis", "rezept", "verschreibung",
    "nebenwirkung", "heilung", "chronisch", "akut", "syndrom",
    "erkrankung", "gesundheit", "pharma", "apotheke", "zulassung",
    "bfarm", "ema ", "fda ",
]


def is_medically_relevant(article: Article) -> bool:
    """Fast keyword check: does this article contain ANY medical signal?

    Returns True if at least one medical keyword is found in the
    title + abstract.  This is a *low bar* — it intentionally keeps
    borderline articles.  Its purpose is to catch clearly non-medical
    items (chemistry, materials science, finance, agriculture, etc.)
    that slip through when the LLM prefilter is rate-limited.
    """
    text = (
        f"{article.title or ''} {article.abstract or ''}"
    ).lower()
    return any(kw in text for kw in _MEDICAL_KEYWORDS)


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


def _assign_secondary_specialties(article: Article) -> None:
    """Find all matching specialties beyond the primary one."""
    text = (
        f"{article.title or ''} {article.abstract or ''} "
        f"{article.mesh_terms or ''}"
    ).lower()

    matched = []
    for spec_name, keywords in SPECIALTY_MESH.items():
        if any(kw in text for kw in keywords):
            matched.append(spec_name)

    secondary = [m for m in matched if m != article.specialty]
    article.secondary_specialties = ",".join(secondary) if secondary else None


def classify_articles(articles: list) -> list:
    """Classify all articles by specialty and detect alerts.

    If the article already has a specialty (e.g. from LLM prefilter),
    keep it — only assign via keyword matching if missing.
    Also assigns secondary_specialties for cross-cutting articles.
    """
    for article in articles:
        if not article.specialty or article.specialty == "Sonstige":
            article.specialty = classify_specialty(article)
        _assign_secondary_specialties(article)
        if detect_alert(article):
            article.status = "ALERT"
    return articles

"""Feedback loop — extract Approve/Reject decisions as few-shot examples.

After 4-6 weeks of usage (~300-500 decisions), the scoring prompt is
enriched with real examples of articles the content manager approved
or rejected. This calibrates the LLM scorer to the editor's preferences.

Two mechanisms:
1. **Few-shot examples**: Best approved + worst rejected articles become
   scoring examples injected into the LLM prompt.
2. **Threshold calibration**: If the content manager regularly approves
   low-scored articles or rejects high-scored ones, the scoring threshold
   should be adjusted.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from sqlmodel import col, func, select

from src.config import DB_PATH
from src.models import Article, get_engine, get_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Minimum decisions before feedback loop activates
FEEDBACK_MIN_DECISIONS = 20
# Number of few-shot examples per category (approved / rejected)
FEEDBACK_MAX_EXAMPLES = 3
# Only use articles with clear signal (high-score approved, low-score rejected)
FEEDBACK_APPROVED_MIN_SCORE = 60
FEEDBACK_REJECTED_MAX_SCORE = 80

# v2 feedback thresholds (only active when _v2_ready() returns True)
FEEDBACK_V2_MIN_ARTICLES = 30
FEEDBACK_V2_APPROVED_MIN_SCORE = 60
FEEDBACK_V2_REJECTED_MAX_SCORE = 55


def get_feedback_examples() -> Optional[Dict[str, list]]:
    """Fetch the best approved and worst rejected articles as examples.

    Returns ``None`` if not enough decisions yet (<FEEDBACK_MIN_DECISIONS).
    Otherwise returns::

        {
            "approved": [{"title": ..., "journal": ..., "score": ..., ...}, ...],
            "rejected": [{"title": ..., "journal": ..., "score": ..., ...}, ...],
            "stats": {"total_approved": N, "total_rejected": M, "avg_approved_score": X, ...}
        }
    """
    get_engine()

    with get_session() as session:
        # Count total decisions
        approved_articles = session.exec(
            select(Article)
            .where(Article.status == "APPROVED")
            .order_by(col(Article.relevance_score).desc())
        ).all()

        rejected_articles = session.exec(
            select(Article)
            .where(Article.status == "REJECTED")
            .order_by(col(Article.relevance_score).asc())
        ).all()

    total = len(approved_articles) + len(rejected_articles)
    if total < FEEDBACK_MIN_DECISIONS:
        logger.debug(
            "Feedback loop: %d decisions (need %d) — not active yet",
            total, FEEDBACK_MIN_DECISIONS,
        )
        return None

    # Best approved: high-score articles the editor confirmed as good
    best_approved = [
        _article_to_example(a)
        for a in approved_articles[:FEEDBACK_MAX_EXAMPLES]
        if a.relevance_score >= FEEDBACK_APPROVED_MIN_SCORE
    ]

    # Worst rejected: articles that scored well but the editor said "no"
    # These are the most informative — they show what the LLM overrated
    worst_rejected = [
        _article_to_example(a)
        for a in reversed(rejected_articles)  # highest-scored rejected first
        if a.relevance_score <= FEEDBACK_REJECTED_MAX_SCORE
    ][:FEEDBACK_MAX_EXAMPLES]

    # Stats for threshold calibration
    avg_approved = (
        sum(a.relevance_score for a in approved_articles) / len(approved_articles)
        if approved_articles else 0
    )
    avg_rejected = (
        sum(a.relevance_score for a in rejected_articles) / len(rejected_articles)
        if rejected_articles else 0
    )

    stats = {
        "total_approved": len(approved_articles),
        "total_rejected": len(rejected_articles),
        "avg_approved_score": round(avg_approved, 1),
        "avg_rejected_score": round(avg_rejected, 1),
    }

    logger.info(
        "Feedback loop active: %d approved (avg %.1f), %d rejected (avg %.1f)",
        stats["total_approved"], stats["avg_approved_score"],
        stats["total_rejected"], stats["avg_rejected_score"],
    )

    return {
        "approved": best_approved,
        "rejected": worst_rejected,
        "stats": stats,
    }


def build_few_shot_messages(
    feedback: Dict[str, list],
) -> List[Dict[str, str]]:
    """Convert feedback examples into chat messages for the scoring prompt.

    Returns a list of user/assistant message pairs that can be prepended
    to the scoring conversation as few-shot examples.
    """
    messages: List[Dict[str, str]] = []

    # Add approved examples
    for ex in feedback.get("approved", []):
        messages.append({
            "role": "user",
            "content": _example_to_prompt(ex),
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(
                _example_to_ideal_score(ex, approved=True),
                ensure_ascii=False,
            ),
        })

    # Add rejected examples
    for ex in feedback.get("rejected", []):
        messages.append({
            "role": "user",
            "content": _example_to_prompt(ex),
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(
                _example_to_ideal_score(ex, approved=False),
                ensure_ascii=False,
            ),
        })

    return messages


def get_threshold_recommendation(
    feedback: Dict[str, list],
) -> Optional[float]:
    """Suggest a scoring threshold based on approval patterns.

    If the content manager regularly approves articles below the current
    threshold or rejects above it, suggest an adjustment.

    Returns a recommended threshold (float) or ``None`` if no adjustment
    is warranted.
    """
    stats = feedback.get("stats", {})
    avg_approved = stats.get("avg_approved_score", 0)
    avg_rejected = stats.get("avg_rejected_score", 0)
    total = stats.get("total_approved", 0) + stats.get("total_rejected", 0)

    if total < FEEDBACK_MIN_DECISIONS:
        return None

    # The ideal threshold sits between average rejected and average approved
    if avg_approved > avg_rejected > 0:
        midpoint = round((avg_approved + avg_rejected) / 2, 1)
        return midpoint

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _article_to_example(article: Article) -> dict:
    """Convert an Article to a compact feedback example dict."""
    breakdown = {}
    if article.score_breakdown:
        try:
            breakdown = json.loads(article.score_breakdown)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "title": article.title or "",
        "journal": article.journal or "",
        "study_type": article.study_type or "",
        "specialty": article.specialty or "",
        "score": article.relevance_score,
        "breakdown": breakdown,
        "abstract_snippet": (article.abstract or "")[:300],
    }


def _example_to_prompt(example: dict) -> str:
    """Build a user-message-style prompt from a feedback example."""
    parts = [f"Titel: {example['title']}"]
    if example.get("journal"):
        parts.append(f"Journal: {example['journal']}")
    if example.get("study_type") and example["study_type"] != "Unbekannt":
        parts.append(f"Studientyp: {example['study_type']}")
    if example.get("abstract_snippet"):
        parts.append(f"Abstract: {example['abstract_snippet']}")
    return "\n".join(parts)


def _example_to_ideal_score(example: dict, approved: bool) -> dict:
    """Create an idealised score response for a feedback example.

    For approved articles: use the stored breakdown if LLM-scored, or
    synthesise high scores. For rejected: synthesise low scores.
    """
    bd = example.get("breakdown", {})

    if bd.get("scorer") == "llm":
        # Use the actual LLM scores (they were validated by the editor)
        return {
            "studientyp": bd.get("studientyp", 14),
            "klinische_relevanz": bd.get("klinische_relevanz", 14),
            "neuigkeitswert": bd.get("neuigkeitswert", 14),
            "zielgruppen_fit": bd.get("zielgruppen_fit", 14),
            "quellenqualitaet": bd.get("quellenqualitaet", 14),
            "begr_studientyp": bd.get("begr_studientyp", ""),
            "begr_klinische_relevanz": bd.get("begr_klinische_relevanz", ""),
            "begr_neuigkeitswert": bd.get("begr_neuigkeitswert", ""),
            "begr_zielgruppen_fit": bd.get("begr_zielgruppen_fit", ""),
            "begr_quellenqualitaet": bd.get("begr_quellenqualitaet", ""),
        }

    # Synthesise plausible scores for rule-based-scored articles
    total = example.get("score", 50)
    if approved:
        # Distribute score across 5 dimensions (high)
        per_dim = min(20, max(10, total / 5))
        reason = "Vom Redakteur freigegeben"
    else:
        # Low scores for rejected
        per_dim = min(10, max(2, total / 5))
        reason = "Vom Redakteur abgelehnt"

    return {
        "studientyp": round(per_dim),
        "klinische_relevanz": round(per_dim),
        "neuigkeitswert": round(per_dim),
        "zielgruppen_fit": round(per_dim),
        "quellenqualitaet": round(per_dim),
        "begr_studientyp": reason,
        "begr_klinische_relevanz": reason,
        "begr_neuigkeitswert": reason,
        "begr_zielgruppen_fit": reason,
        "begr_quellenqualitaet": reason,
    }


# ---------------------------------------------------------------------------
# v2 feedback support
# ---------------------------------------------------------------------------

def _v2_ready() -> bool:
    """Check if enough v2-scored articles have been approved/rejected.

    Returns True when >30 v2-scored articles have editorial decisions,
    enabling v2-specific feedback examples in the scoring prompt.
    """
    get_engine()
    with get_session() as session:
        v2_decided = session.exec(
            select(func.count(Article.id)).where(
                Article.scoring_version == "v2",
                Article.status.in_(["APPROVED", "REJECTED"]),  # type: ignore[union-attr]
            )
        ).one()
    return v2_decided > FEEDBACK_V2_MIN_ARTICLES


def get_v2_feedback_examples() -> Optional[Dict[str, list]]:
    """Get feedback examples specifically from v2-scored articles.

    Returns None if not enough v2 decisions yet (falls back to calibration
    anchors in the prompt). When ready, uses v2 thresholds:
    approved >= 60, rejected < 55.
    """
    if not _v2_ready():
        logger.debug("v2 feedback not ready yet (need >%d v2 decisions)", FEEDBACK_V2_MIN_ARTICLES)
        return None

    get_engine()
    with get_session() as session:
        approved = session.exec(
            select(Article)
            .where(
                Article.scoring_version == "v2",
                Article.status == "APPROVED",
                Article.relevance_score >= FEEDBACK_V2_APPROVED_MIN_SCORE,
            )
            .order_by(col(Article.relevance_score).desc())
            .limit(FEEDBACK_MAX_EXAMPLES)
        ).all()

        rejected = session.exec(
            select(Article)
            .where(
                Article.scoring_version == "v2",
                Article.status == "REJECTED",
                Article.relevance_score < FEEDBACK_V2_REJECTED_MAX_SCORE,
            )
            .order_by(col(Article.relevance_score).asc())
            .limit(FEEDBACK_MAX_EXAMPLES)
        ).all()

    if not approved and not rejected:
        return None

    return {
        "approved": [_article_to_example(a) for a in approved],
        "rejected": [_article_to_example(a) for a in rejected],
        "stats": {
            "total_approved": len(approved),
            "total_rejected": len(rejected),
        },
    }

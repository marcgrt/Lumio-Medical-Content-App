"""Redaktions-Gedaechtnis -- Institutionelles Wissen der Redaktion.

Remembers which articles were approved, which topics were covered, and when.
When a new article arrives on a topic already covered, Lumio shows context like:
"Aehnlich: vor 12 Tagen berichtet" or "Neues Thema".
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from collections import Counter

from sqlmodel import select, func, col, or_, and_

from src.models import Article, StatusChange, get_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArticleMemory:
    """Memory context for a single article."""
    article_id: int
    similar_approved: list[dict]      # [{id, title, score, approved_date, similarity_reason}]
    topic_history: dict               # {topic: {last_covered: date, count_30d: N, count_all: N}}
    days_since_last_coverage: int     # Days since last approved article on similar topic
    coverage_suggestion: str          # "Update faellig", "Neues Thema", "Kuerzlich berichtet"
    suggestion_detail_de: str         # Human-readable suggestion


@dataclass
class EditorialMemoryReport:
    """Overall editorial memory report."""
    topics_covered_30d: dict[str, int]          # topic -> count of approved articles
    topics_stale: list[dict]                     # Topics not covered in 30+ days but trending
    most_covered_specialties: list[tuple]        # [(specialty, count)]
    least_covered_specialties: list[tuple]       # [(specialty, count)]
    approval_patterns: dict                      # {avg_score_approved, avg_score_rejected, ...}
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------

def _get_medical_entities() -> list[str]:
    """Import MEDICAL_ENTITIES from trends.py (lazy to avoid circular imports)."""
    from src.processing.trends import _MEDICAL_ENTITIES
    return _MEDICAL_ENTITIES


def _get_word_boundary_keywords() -> set[str]:
    """Import word-boundary keywords from trends.py."""
    from src.processing.trends import _WORD_BOUNDARY_KEYWORDS
    return _WORD_BOUNDARY_KEYWORDS


def _extract_topics(title: str, abstract: str = "") -> list[str]:
    """Extract medical topic keywords from text.

    Uses MEDICAL_ENTITIES from trends.py for matching.
    Also extracts specialty-relevant terms from SPECIALTY_MESH.
    """
    text = f"{title or ''} {abstract or ''}".lower()
    if not text.strip():
        return []

    found = []
    entities = _get_medical_entities()
    boundary_kws = _get_word_boundary_keywords()

    for kw in entities:
        if kw in boundary_kws:
            # Word-boundary match
            idx = text.find(kw)
            while idx != -1:
                before_ok = (idx == 0 or not text[idx - 1].isalpha())
                after_pos = idx + len(kw)
                after_ok = (after_pos >= len(text) or not text[after_pos].isalpha())
                if before_ok and after_ok:
                    found.append(kw)
                    break
                idx = text.find(kw, idx + 1)
        else:
            if kw in text:
                found.append(kw)

    # Also extract specialty terms from config
    from src.config import SPECIALTY_MESH
    for specialty, terms in SPECIALTY_MESH.items():
        for term in terms:
            if len(term) >= 4 and term in text and term not in found:
                found.append(term)

    return list(dict.fromkeys(found))  # unique, preserving order


# ---------------------------------------------------------------------------
# Find similar approved articles
# ---------------------------------------------------------------------------

def _find_similar_approved(
    topics: list[str],
    specialty: str,
    exclude_id: int,
    days_back: int = 90,
) -> list[dict]:
    """Find approved articles covering similar topics.

    Searches APPROVED articles matching any of the topics in title or abstract
    (case-insensitive LIKE queries). Filters by specialty if available.
    Returns [{id, title, score, approved_date, similarity_reason}].
    """
    if not topics:
        return []

    cutoff = date.today() - timedelta(days=days_back)

    with get_session() as session:
        # Build OR conditions for topic matching in title/abstract
        conditions = []
        for topic in topics[:10]:  # limit to avoid huge queries
            pattern = f"%{topic}%"
            conditions.append(col(Article.title).ilike(pattern))
            conditions.append(col(Article.abstract).ilike(pattern))

        stmt = (
            select(Article)
            .where(Article.status == "APPROVED")
            .where(Article.id != exclude_id)
            .where(or_(*conditions))
            .where(
                (Article.pub_date >= cutoff) | (Article.pub_date.is_(None))
            )
            .order_by(col(Article.pub_date).desc())
            .limit(20)
        )

        articles = session.exec(stmt).all()

        results = []
        for a in articles:
            # Determine which topics matched
            a_text = f"{a.title or ''} {a.abstract or ''}".lower()
            matched_topics = [t for t in topics if t in a_text]

            # Get approval date from StatusChange
            approved_date = _get_approval_date(session, a.id) or a.pub_date

            results.append({
                "id": a.id,
                "title": a.title,
                "score": a.relevance_score,
                "approved_date": approved_date,
                "similarity_reason": ", ".join(matched_topics[:3]),
            })

        return results


def _get_approval_date(session, article_id: int) -> Optional[date]:
    """Get the date when an article was approved from StatusChange log."""
    stmt = (
        select(StatusChange.changed_at)
        .where(StatusChange.article_id == article_id)
        .where(StatusChange.new_status == "APPROVED")
        .order_by(col(StatusChange.changed_at).desc())
        .limit(1)
    )
    result = session.exec(stmt).first()
    if result:
        if isinstance(result, datetime):
            return result.date()
        return result
    return None


# ---------------------------------------------------------------------------
# Article memory (single article context)
# ---------------------------------------------------------------------------

def get_article_memory(article_id: int) -> Optional[ArticleMemory]:
    """Get editorial memory context for a specific article."""
    with get_session() as session:
        article = session.get(Article, article_id)
        if not article:
            return None

        # Extract topics from this article
        topics = _extract_topics(article.title or "", article.abstract or "")

        # Find similar approved articles
        similar = _find_similar_approved(
            topics,
            article.specialty or "",
            exclude_id=article.id,
            days_back=90,
        )

        # Build topic history
        topic_history = {}
        today = date.today()
        for topic in topics[:5]:  # limit for performance
            pattern = f"%{topic}%"
            # Count approved articles matching this topic in last 30 days
            cutoff_30d = today - timedelta(days=30)
            count_30d = session.exec(
                select(func.count(Article.id))
                .where(Article.status == "APPROVED")
                .where(
                    col(Article.title).ilike(pattern)
                    | col(Article.abstract).ilike(pattern)
                )
                .where(Article.pub_date >= cutoff_30d)
            ).one() or 0

            # Count all approved articles matching this topic
            count_all = session.exec(
                select(func.count(Article.id))
                .where(Article.status == "APPROVED")
                .where(
                    col(Article.title).ilike(pattern)
                    | col(Article.abstract).ilike(pattern)
                )
            ).one() or 0

            # Last covered date
            last_approved = session.exec(
                select(Article.pub_date)
                .where(Article.status == "APPROVED")
                .where(
                    col(Article.title).ilike(pattern)
                    | col(Article.abstract).ilike(pattern)
                )
                .where(Article.id != article_id)
                .order_by(col(Article.pub_date).desc())
                .limit(1)
            ).first()

            topic_history[topic] = {
                "last_covered": last_approved,
                "count_30d": count_30d,
                "count_all": count_all,
            }

        # Calculate days since last coverage
        days_since = _calc_days_since(similar)

        # Generate suggestion
        suggestion, detail = _generate_suggestion(days_since, similar, topics)

        return ArticleMemory(
            article_id=article_id,
            similar_approved=similar,
            topic_history=topic_history,
            days_since_last_coverage=days_since,
            coverage_suggestion=suggestion,
            suggestion_detail_de=detail,
        )


def _calc_days_since(similar: list[dict]) -> int:
    """Calculate days since last similar approved article."""
    if not similar:
        return -1  # never covered
    today = date.today()
    for s in similar:
        d = s.get("approved_date")
        if d:
            if isinstance(d, datetime):
                d = d.date()
            if isinstance(d, date):
                return (today - d).days
    return -1


def _generate_suggestion(
    days_since: int, similar: list[dict], topics: list[str]
) -> tuple[str, str]:
    """Generate coverage suggestion based on editorial memory."""
    if days_since < 0 or not similar:
        return (
            "Neues Thema",
            "Noch nicht berichtet -- neues Thema fuer die Redaktion.",
        )

    if days_since < 7:
        ref = similar[0]
        return (
            "Kuerzlich berichtet",
            f"Aehnlicher Artikel vor {days_since} Tag(en) freigegeben "
            f"(Score {ref['score']:.0f}). Duplikat pruefen.",
        )

    if days_since <= 30:
        ref = similar[0]
        return (
            "Thema laeuft",
            f"Letzter Artikel vor {days_since} Tagen "
            f"(Score {ref['score']:.0f}). Follow-up moeglich.",
        )

    # > 30 days
    ref = similar[0]
    topic_str = ", ".join(topics[:2]) if topics else "Thema"
    return (
        "Update faellig",
        f"Letzter {topic_str}-Artikel vor {days_since} Tagen -- Update faellig?",
    )


# ---------------------------------------------------------------------------
# Batch loading for article cards (performance)
# ---------------------------------------------------------------------------

def get_memory_batch(article_ids: list[int]) -> dict[int, ArticleMemory]:
    """Load editorial memory for multiple articles at once.

    This is the batch version for use in article card rendering.
    Uses a single DB session and shared topic lookup for performance.
    """
    if not article_ids:
        return {}

    results: dict[int, ArticleMemory] = {}

    with get_session() as session:
        # Load all articles
        stmt = select(Article).where(col(Article.id).in_(article_ids))
        articles = session.exec(stmt).all()

        if not articles:
            return {}

        # Pre-load all approved articles from last 90 days for matching
        cutoff_90d = date.today() - timedelta(days=90)
        approved_stmt = (
            select(Article)
            .where(Article.status == "APPROVED")
            .where(
                (Article.pub_date >= cutoff_90d) | (Article.pub_date.is_(None))
            )
        )
        approved_articles = session.exec(approved_stmt).all()

        # Pre-extract topics for all approved articles
        approved_topics_map: dict[int, set[str]] = {}
        approved_data: list[dict] = []
        for aa in approved_articles:
            topics_set = set(_extract_topics(aa.title or "", aa.abstract or ""))
            approved_topics_map[aa.id] = topics_set

            # Get approval date
            approved_date = _get_approval_date(session, aa.id) or aa.pub_date

            approved_data.append({
                "id": aa.id,
                "title": aa.title,
                "score": aa.relevance_score,
                "approved_date": approved_date,
                "specialty": aa.specialty,
                "topics": topics_set,
            })

        today = date.today()

        for article in articles:
            a_topics = set(_extract_topics(article.title or "", article.abstract or ""))

            # Find similar approved by topic overlap
            similar = []
            for ad in approved_data:
                if ad["id"] == article.id:
                    continue
                overlap = a_topics & ad["topics"]
                if overlap:
                    similar.append({
                        "id": ad["id"],
                        "title": ad["title"],
                        "score": ad["score"],
                        "approved_date": ad["approved_date"],
                        "similarity_reason": ", ".join(list(overlap)[:3]),
                    })

            # Sort by date (most recent first)
            similar.sort(
                key=lambda s: s.get("approved_date") or date.min,
                reverse=True,
            )
            similar = similar[:5]  # keep top 5

            days_since = _calc_days_since(similar)
            suggestion, detail = _generate_suggestion(
                days_since, similar, list(a_topics)
            )

            results[article.id] = ArticleMemory(
                article_id=article.id,
                similar_approved=similar,
                topic_history={},  # skip detailed topic history in batch mode
                days_since_last_coverage=days_since,
                coverage_suggestion=suggestion,
                suggestion_detail_de=detail,
            )

    return results


# ---------------------------------------------------------------------------
# Editorial report
# ---------------------------------------------------------------------------

def get_editorial_report(days: int = 30) -> EditorialMemoryReport:
    """Generate overall editorial memory report."""
    cutoff = date.today() - timedelta(days=days)

    with get_session() as session:
        # 1. Get all approved articles in the period
        approved_stmt = (
            select(Article)
            .where(Article.status == "APPROVED")
            .where(Article.pub_date >= cutoff)
        )
        approved_articles = session.exec(approved_stmt).all()

        # 2. Count topics among approved articles
        topic_counter: Counter = Counter()
        for a in approved_articles:
            for topic in _extract_topics(a.title or "", a.abstract or ""):
                topic_counter[topic] += 1

        topics_covered_30d = dict(topic_counter.most_common(30))

        # 3. Find stale topics
        stale = get_stale_topics(days_threshold=days)

        # 4. Specialty coverage
        spec_counter: Counter = Counter()
        for a in approved_articles:
            if a.specialty:
                spec_counter[a.specialty] += 1

        from src.config import SPECIALTY_MESH
        all_specs = list(SPECIALTY_MESH.keys())
        most_covered = spec_counter.most_common(5)
        # Least covered: specialties with fewest approvals
        least_covered = sorted(
            [(s, spec_counter.get(s, 0)) for s in all_specs],
            key=lambda x: x[1],
        )[:5]

        # 5. Approval patterns
        approved_scores = [a.relevance_score for a in approved_articles]

        rejected_stmt = (
            select(Article.relevance_score)
            .where(Article.status == "REJECTED")
            .where(Article.pub_date >= cutoff)
        )
        rejected_scores = list(session.exec(rejected_stmt).all())

        avg_approved = (
            sum(approved_scores) / len(approved_scores) if approved_scores else 0
        )
        avg_rejected = (
            sum(rejected_scores) / len(rejected_scores) if rejected_scores else 0
        )

        # Approval rate
        total_reviewed = len(approved_scores) + len(rejected_scores)
        approval_rate = (
            len(approved_scores) / total_reviewed if total_reviewed else 0
        )

        approval_patterns = {
            "avg_score_approved": round(avg_approved, 1),
            "avg_score_rejected": round(avg_rejected, 1),
            "total_approved": len(approved_scores),
            "total_rejected": len(rejected_scores),
            "approval_rate": round(approval_rate * 100, 1),
        }

    return EditorialMemoryReport(
        topics_covered_30d=topics_covered_30d,
        topics_stale=stale,
        most_covered_specialties=most_covered,
        least_covered_specialties=least_covered,
        approval_patterns=approval_patterns,
    )


# ---------------------------------------------------------------------------
# Stale topics
# ---------------------------------------------------------------------------

def get_stale_topics(days_threshold: int = 30) -> list[dict]:
    """Find topics that haven't been covered recently but are still active.

    Topics with approved articles > days_threshold ago that still have
    NEW articles coming in.
    Returns [{topic, last_approved_date, days_ago, new_article_count}].
    """
    cutoff_stale = date.today() - timedelta(days=days_threshold)
    cutoff_recent = date.today() - timedelta(days=7)

    with get_session() as session:
        # Get all approved articles older than threshold
        old_approved_stmt = (
            select(Article)
            .where(Article.status == "APPROVED")
            .where(Article.pub_date < cutoff_stale)
            .order_by(col(Article.pub_date).desc())
            .limit(200)
        )
        old_approved = session.exec(old_approved_stmt).all()

        # Get recent NEW articles
        new_articles_stmt = (
            select(Article)
            .where(Article.status == "NEW")
            .where(Article.pub_date >= cutoff_recent)
        )
        new_articles = session.exec(new_articles_stmt).all()

        # Also check if topic has been covered recently (would make it not stale)
        recent_approved_stmt = (
            select(Article)
            .where(Article.status == "APPROVED")
            .where(Article.pub_date >= cutoff_stale)
        )
        recent_approved = session.exec(recent_approved_stmt).all()
        recent_approved_topics: set[str] = set()
        for a in recent_approved:
            for t in _extract_topics(a.title or "", a.abstract or ""):
                recent_approved_topics.add(t)

    # Extract topics from old approved articles
    topic_last_date: dict[str, date] = {}
    for a in old_approved:
        for topic in _extract_topics(a.title or "", a.abstract or ""):
            existing = topic_last_date.get(topic)
            if existing is None or (a.pub_date and a.pub_date > existing):
                topic_last_date[topic] = a.pub_date

    # Count new articles per topic
    new_topic_counts: Counter = Counter()
    for a in new_articles:
        for topic in _extract_topics(a.title or "", a.abstract or ""):
            new_topic_counts[topic] += 1

    # Find stale topics: covered before but not recently, with new articles
    today = date.today()
    stale_topics = []
    for topic, last_date in topic_last_date.items():
        if topic in recent_approved_topics:
            continue  # Not stale -- was covered recently
        new_count = new_topic_counts.get(topic, 0)
        if new_count == 0:
            continue  # No new articles -- not active

        days_ago = (today - last_date).days if last_date else days_threshold + 1
        if days_ago >= days_threshold:
            stale_topics.append({
                "topic": topic,
                "last_approved_date": last_date,
                "days_ago": days_ago,
                "new_article_count": new_count,
            })

    # Sort by new_article_count (most active stale topics first)
    stale_topics.sort(key=lambda x: x["new_article_count"], reverse=True)
    return stale_topics[:15]

"""Konkurrenz-Radar — Wettbewerbsanalyse der deutschen Fachpresse."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict
from typing import Optional

from sqlmodel import select, col
from src.models import Article, get_session

logger = logging.getLogger(__name__)

# German medical press sources (= competitors to monitor)
COMPETITOR_SOURCES = [
    "Deutsches Ärzteblatt",
    "Ärzte Zeitung",
    "Ärzte Zeitung Medizin",
    "Pharmazeutische Zeitung",
    "Apotheke Adhoc",
]

# Stopwords for keyword extraction (German + English + medical filler)
_STOPWORDS: set[str] = {
    # German
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem",
    "einen", "eines", "und", "oder", "aber", "auch", "auf", "aus", "bei", "bis",
    "für", "mit", "nach", "von", "vor", "zu", "zum", "zur", "über", "unter",
    "durch", "gegen", "ohne", "um", "als", "wie", "wenn", "weil", "dass",
    "ist", "sind", "war", "hat", "haben", "wird", "werden", "kann", "können",
    "soll", "sollen", "nicht", "sich", "sie", "ihr", "ihm", "wir", "ich",
    "er", "es", "im", "am", "an", "so", "da", "noch", "nur", "schon", "mehr",
    "neue", "neuer", "neues", "neuem", "neuen", "neue", "ersten", "erste",
    "seiner", "seine", "seinem", "seinen", "ihrer", "ihre", "ihrem", "ihren",
    "was", "wer", "wo", "welche", "welcher", "welchem", "welchen",
    "dieser", "diese", "diesem", "diesen", "dieses", "jeder", "jede", "jedem",
    "jeden", "jedes", "alle", "allem", "allen", "aller", "alles",
    "kein", "keine", "keinem", "keinen", "keiner", "keines",
    "sehr", "viel", "viele", "vielen", "vieler", "vieles",
    "wieder", "bereits", "seit", "beim", "doch", "nun", "mal",
    "laut", "sowie", "etwa", "dabei", "damit", "daher", "jedoch",
    "teil", "rund", "jahr", "jahre", "jahren",
    # English
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "has", "have", "had", "been", "being", "will", "would", "can", "could",
    "not", "but", "its", "his", "her", "their", "our", "your",
    "new", "may", "also", "than", "into", "more", "most", "some",
    "study", "studies", "results", "patients", "clinical", "trial",
    "analysis", "data", "use", "risk", "treatment", "associated",
    "between", "among", "after", "during", "about", "each", "other",
    # Common filler
    "kommentar", "news", "aktuell", "meldung", "bericht", "update",
}

# Minimum keyword length to consider
_MIN_KEYWORD_LEN = 3


@dataclass
class CompetitorCoverage:
    """Coverage analysis for one competitor source."""
    source_name: str
    article_count: int
    top_specialties: list[tuple]     # [(specialty, count)] top 5
    top_topics: list[tuple]          # [(topic_keyword, count)] top 10
    exclusive_topics: list[str]      # Topics only this source covers
    avg_score: float


@dataclass
class TopicOverlap:
    """Topic overlap analysis between competitors and our editorial team."""
    topic: str
    our_coverage: int
    competitor_coverage: dict        # {source: article_count}
    total_competitor_articles: int
    we_covered_first: bool
    gap_days: int
    status: str                      # "exclusive_ours" | "exclusive_theirs" | "overlap" | "gap"


@dataclass
class KonkurrenzReport:
    """Complete competitor analysis report."""
    period_days: int
    competitor_stats: list[CompetitorCoverage]
    topic_overlaps: list[TopicOverlap]
    our_exclusives: list[str]
    their_exclusives: list[dict]     # [{topic, sources, article_count}]
    speed_analysis: dict             # {avg_gap_days, times_first, times_behind}
    summary_de: str
    generated_at: datetime = field(default_factory=datetime.now)


def generate_konkurrenz_report(days: int = 7) -> KonkurrenzReport:
    """Generate full competitor analysis report."""
    # 1. Load articles
    comp_articles = _get_competitor_articles(days)
    our_articles = _get_our_coverage(days)

    # 2. Extract topics
    all_comp_flat = [a for arts in comp_articles.values() for a in arts]
    comp_topic_counter = _extract_topic_keywords(all_comp_flat)

    # Per-source topic counters
    per_source_topics: dict[str, Counter] = {}
    for source, arts in comp_articles.items():
        per_source_topics[source] = _extract_topic_keywords(arts)

    our_topic_counter = _extract_topic_keywords(our_articles)

    # 3. Build competitor stats
    competitor_stats = []
    # Collect all topics across all sources for exclusive detection
    all_source_topic_sets: dict[str, set] = {}
    for source, arts in comp_articles.items():
        if not arts:
            continue
        src_topics = per_source_topics.get(source, Counter())
        all_source_topic_sets[source] = set(src_topics.keys())

        # Specialties
        spec_counter = Counter(a.specialty for a in arts if a.specialty)
        top_specs = spec_counter.most_common(5)

        # Avg score
        scores = [a.relevance_score for a in arts if a.relevance_score]
        avg = sum(scores) / len(scores) if scores else 0.0

        competitor_stats.append(CompetitorCoverage(
            source_name=source,
            article_count=len(arts),
            top_specialties=top_specs,
            top_topics=src_topics.most_common(10),
            exclusive_topics=[],  # filled below
            avg_score=round(avg, 1),
        ))

    # Find exclusive topics per source (topics only ONE source covers, not us)
    our_topic_set = set(our_topic_counter.keys())
    for cs in competitor_stats:
        src_set = all_source_topic_sets.get(cs.source_name, set())
        other_sources = set()
        for other_src, other_set in all_source_topic_sets.items():
            if other_src != cs.source_name:
                other_sources |= other_set
        exclusives = src_set - other_sources - our_topic_set
        cs.exclusive_topics = sorted(exclusives, key=lambda t: per_source_topics[cs.source_name].get(t, 0), reverse=True)[:10]

    # 4. Compute topic overlaps
    topic_overlaps = _compute_topic_overlaps(
        our_topic_counter, per_source_topics,
        our_articles, comp_articles, days
    )

    # 5. Our exclusives vs their exclusives
    all_comp_topic_set = set(comp_topic_counter.keys())
    our_exclusives = sorted(
        our_topic_set - all_comp_topic_set,
        key=lambda t: our_topic_counter[t], reverse=True
    )[:15]

    their_exclusive_topics = all_comp_topic_set - our_topic_set
    their_exclusives = []
    for topic in sorted(their_exclusive_topics, key=lambda t: comp_topic_counter[t], reverse=True)[:15]:
        sources_with = [s for s, tc in per_source_topics.items() if topic in tc]
        their_exclusives.append({
            "topic": topic,
            "sources": sources_with,
            "article_count": comp_topic_counter[topic],
        })

    # 6. Speed analysis
    speed_analysis = _compute_speed_analysis(topic_overlaps)

    # 7. Summary
    summary_de = _generate_summary({
        "our_exclusives": our_exclusives,
        "their_exclusives": their_exclusives,
        "speed": speed_analysis,
        "competitor_stats": competitor_stats,
        "our_article_count": len(our_articles),
        "comp_article_count": len(all_comp_flat),
        "period_days": days,
    })

    return KonkurrenzReport(
        period_days=days,
        competitor_stats=competitor_stats,
        topic_overlaps=topic_overlaps,
        our_exclusives=our_exclusives,
        their_exclusives=their_exclusives,
        speed_analysis=speed_analysis,
        summary_de=summary_de,
    )


def _get_competitor_articles(days: int) -> dict[str, list]:
    """Load articles grouped by competitor source.
    Returns {source_name: [articles]}"""
    cutoff = date.today() - timedelta(days=days)
    result: dict[str, list] = {s: [] for s in COMPETITOR_SOURCES}

    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.source.in_(COMPETITOR_SOURCES))  # type: ignore[attr-defined]
            .where(col(Article.pub_date) >= cutoff)
        )
        articles = session.exec(stmt).all()
        for a in articles:
            detached = a.detach()
            if detached.source in result:
                result[detached.source].append(detached)

    return result


def _get_our_coverage(days: int) -> list:
    """Load our APPROVED articles from the period."""
    cutoff = date.today() - timedelta(days=days)

    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.status == "APPROVED")
            .where(col(Article.pub_date) >= cutoff)
        )
        articles = session.exec(stmt).all()
        return [a.detach() for a in articles]


def _extract_topic_keywords(articles: list) -> Counter:
    """Extract topic keywords from a list of articles.
    Uses title words, filtering stopwords. Returns Counter of meaningful keywords."""
    counter: Counter = Counter()
    splitter = re.compile(r"[^a-zA-ZäöüÄÖÜßéèê]+")

    for art in articles:
        title = art.title or ""
        words = splitter.split(title.lower())
        seen_in_title: set[str] = set()
        for w in words:
            if len(w) < _MIN_KEYWORD_LEN:
                continue
            if w in _STOPWORDS:
                continue
            if w not in seen_in_title:
                seen_in_title.add(w)
                counter[w] += 1

    return counter


def _compute_topic_overlaps(
    our_topics: Counter,
    competitor_topics: dict[str, Counter],
    our_articles: list,
    comp_articles: dict[str, list],
    days: int,
) -> list[TopicOverlap]:
    """Compute topic overlap between us and competitors."""
    # Collect all topics from both sides
    all_comp_topics: set[str] = set()
    for tc in competitor_topics.values():
        all_comp_topics |= set(tc.keys())

    our_topic_set = set(our_topics.keys())
    all_topics = our_topic_set | all_comp_topics

    # Build date index: topic -> {source: earliest_pub_date}
    our_topic_dates: dict[str, date] = {}
    splitter = re.compile(r"[^a-zA-ZäöüÄÖÜßéèê]+")

    for art in our_articles:
        if not art.pub_date:
            continue
        words = set(splitter.split((art.title or "").lower())) - _STOPWORDS
        for w in words:
            if len(w) >= _MIN_KEYWORD_LEN and w in all_topics:
                if w not in our_topic_dates or art.pub_date < our_topic_dates[w]:
                    our_topic_dates[w] = art.pub_date

    comp_topic_dates: dict[str, dict[str, date]] = defaultdict(dict)
    for source, arts in comp_articles.items():
        for art in arts:
            if not art.pub_date:
                continue
            words = set(splitter.split((art.title or "").lower())) - _STOPWORDS
            for w in words:
                if len(w) >= _MIN_KEYWORD_LEN and w in all_topics:
                    if source not in comp_topic_dates[w] or art.pub_date < comp_topic_dates[w][source]:
                        comp_topic_dates[w][source] = art.pub_date

    overlaps: list[TopicOverlap] = []

    # Focus on topics that appear at least twice total (avoid noise)
    for topic in all_topics:
        our_count = our_topics.get(topic, 0)

        comp_coverage: dict[str, int] = {}
        for source, tc in competitor_topics.items():
            if topic in tc:
                comp_coverage[source] = tc[topic]
        total_comp = sum(comp_coverage.values())

        if our_count == 0 and total_comp == 0:
            continue

        # Determine status
        if our_count > 0 and total_comp == 0:
            status = "exclusive_ours"
        elif our_count == 0 and total_comp > 0:
            status = "exclusive_theirs"
        else:
            status = "overlap"

        # Speed: who published first?
        we_covered_first = False
        gap_days = 0

        if status == "overlap":
            our_date = our_topic_dates.get(topic)
            # Earliest competitor date for this topic
            comp_dates_for_topic = comp_topic_dates.get(topic, {})
            earliest_comp = None
            for src, d in comp_dates_for_topic.items():
                if earliest_comp is None or d < earliest_comp:
                    earliest_comp = d

            if our_date and earliest_comp:
                diff = (our_date - earliest_comp).days
                we_covered_first = diff < 0
                gap_days = abs(diff)
                if not we_covered_first and gap_days > 0:
                    status = "gap"

        # Only include topics with meaningful frequency (>= 2 total mentions)
        total_mentions = our_count + total_comp
        if total_mentions < 2:
            continue

        overlaps.append(TopicOverlap(
            topic=topic,
            our_coverage=our_count,
            competitor_coverage=comp_coverage,
            total_competitor_articles=total_comp,
            we_covered_first=we_covered_first,
            gap_days=gap_days,
            status=status,
        ))

    # Sort: exclusive_theirs first (actionable), then gap, then overlap, then exclusive_ours
    status_order = {"exclusive_theirs": 0, "gap": 1, "overlap": 2, "exclusive_ours": 3}
    overlaps.sort(key=lambda o: (
        status_order.get(o.status, 9),
        -(o.total_competitor_articles + o.our_coverage),
    ))

    return overlaps[:50]  # Cap at 50 for display


def _compute_speed_analysis(overlaps: list[TopicOverlap]) -> dict:
    """Analyze who publishes first on overlapping topics."""
    times_first = 0
    times_behind = 0
    gap_days_list: list[int] = []

    for o in overlaps:
        if o.status in ("overlap", "gap"):
            if o.we_covered_first:
                times_first += 1
            else:
                times_behind += 1
            if o.gap_days > 0:
                gap_days_list.append(o.gap_days)

    avg_gap = round(sum(gap_days_list) / len(gap_days_list), 1) if gap_days_list else 0.0

    return {
        "avg_gap_days": avg_gap,
        "times_first": times_first,
        "times_behind": times_behind,
        "total_overlap_topics": times_first + times_behind,
    }


def _generate_summary(report_data: dict) -> str:
    """Generate a German executive summary without LLM (rule-based)."""
    our_excl = len(report_data["our_exclusives"])
    their_excl = len(report_data["their_exclusives"])
    speed = report_data["speed"]
    comp_stats = report_data["competitor_stats"]
    period = report_data["period_days"]
    our_count = report_data["our_article_count"]
    comp_count = report_data["comp_article_count"]

    period_label = f"den letzten {period} Tagen" if period != 7 else "dieser Woche"

    parts = []

    # Part 1: volume overview
    parts.append(
        f"In {period_label}: {our_count} freigegebene Artikel (wir) vs. "
        f"{comp_count} Artikel der Konkurrenz."
    )

    # Part 2: exclusives
    if our_excl > 0 or their_excl > 0:
        excl_parts = []
        if our_excl > 0:
            excl_parts.append(f"{our_excl} exklusive Themen bei uns")
        if their_excl > 0:
            excl_parts.append(f"{their_excl} Themen nur bei der Konkurrenz")
        parts.append(" ".join(excl_parts) + ".")

    # Part 3: speed
    if speed["total_overlap_topics"] > 0:
        if speed["times_first"] > speed["times_behind"]:
            parts.append(
                f"Bei {speed['times_first']} von {speed['total_overlap_topics']} "
                f"gemeinsamen Themen waren wir schneller."
            )
        elif speed["times_behind"] > speed["times_first"]:
            parts.append(
                f"Bei {speed['times_behind']} von {speed['total_overlap_topics']} "
                f"gemeinsamen Themen war die Konkurrenz schneller "
                f"(Ø {speed['avg_gap_days']} Tage Vorsprung)."
            )
        else:
            parts.append("Geschwindigkeit bei gemeinsamen Themen ausgeglichen.")

    # Part 4: dominant competitor
    if comp_stats:
        dominant = max(comp_stats, key=lambda cs: cs.article_count)
        if dominant.top_specialties:
            top_spec = dominant.top_specialties[0][0]
            top_count = dominant.top_specialties[0][1]
            parts.append(
                f"{dominant.source_name} dominiert bei {top_spec} "
                f"({top_count} Artikel)."
            )

    return " ".join(parts)

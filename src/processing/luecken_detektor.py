"""Lücken-Detektor — Erkennt redaktionelle Lücken in der Themenabdeckung.

Identifiziert Fachgebiete und Trend-Themen, die qualitativ hochwertige
Artikel haben, aber keine redaktionelle Freigabe erhalten haben.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import select, func, col

from src.models import Article, get_session
from src.config import SPECIALTY_MESH, SCORE_THRESHOLD_HIGH

logger = logging.getLogger(__name__)

# HQ-Schwelle: Artikel mit Score >= diesem Wert gelten als hochwertig
_HQ_THRESHOLD = SCORE_THRESHOLD_HIGH  # 65


@dataclass
class CoverageLuecke:
    """Eine erkannte Lücke in der redaktionellen Abdeckung."""
    specialty: str                    # Fachgebiet mit Lücke
    total_articles: int              # Wie viele Artikel gibt es insgesamt
    high_quality_count: int          # Davon mit Score >= 65
    approved_count: int              # Davon freigegeben
    approval_rate: float             # approved / total
    avg_score: float                 # Durchschnittlicher Score
    trending_topics: list[str] = field(default_factory=list)
    top_unreviewed: list[dict] = field(default_factory=list)
    severity: str = "info"           # "critical" | "warning" | "info"
    suggestion_de: str = ""          # Redaktioneller Vorschlag


@dataclass
class TopicLuecke:
    """Ein spezifisches Thema das trending ist aber nicht bearbeitet wurde."""
    topic: str                       # Thema-Label
    article_count: int = 0           # Anzahl Artikel
    avg_score: float = 0.0           # Ø Score
    momentum: str = "stable"         # Trend-Momentum
    specialties: list[str] = field(default_factory=list)
    top_article_ids: list[int] = field(default_factory=list)
    days_unreviewed: int = 0         # Wie lange schon nicht bearbeitet
    suggestion_de: str = ""          # Konkreter Pitch


def detect_coverage_gaps(days: int = 7) -> list[CoverageLuecke]:
    """Erkennt Fachgebiete mit schlechter redaktioneller Abdeckung.

    Prüft für jedes Fachgebiet: Wie viele Artikel gibt es, wie viele
    sind hochwertig (Score >= 65), und wie viele wurden freigegeben?
    """
    cutoff = date.today() - timedelta(days=days)
    gaps: list[CoverageLuecke] = []

    with get_session() as session:
        for specialty in SPECIALTY_MESH:
            # Alle Artikel im Zeitraum für dieses Fachgebiet
            base_stmt = (
                select(Article)
                .where(Article.specialty == specialty)
                .where(Article.pub_date >= cutoff)
            )
            articles = list(session.exec(base_stmt).all())
            total = len(articles)

            if total == 0:
                continue

            # Zähler berechnen
            hq_articles = [a for a in articles if a.relevance_score >= _HQ_THRESHOLD]
            high_quality_count = len(hq_articles)
            approved_count = sum(1 for a in articles if a.status == "APPROVED")
            avg_score = sum(a.relevance_score for a in articles) / total
            approval_rate = approved_count / total if total > 0 else 0.0

            # Severity bestimmen
            if high_quality_count >= 5 and approved_count == 0:
                severity = "critical"
            elif total > 10 and approved_count == 0:
                severity = "critical"
            elif high_quality_count > 0 and approval_rate < 0.20:
                severity = "warning"
            elif approval_rate < 0.40:
                severity = "info"
            else:
                # Kein Handlungsbedarf — überspringen
                continue

            # Top 5 unreviewed HQ-Artikel (Status NEW, Score absteigend)
            unreviewed = [
                a for a in articles
                if a.status == "NEW" and a.relevance_score >= _HQ_THRESHOLD
            ]
            unreviewed.sort(key=lambda a: a.relevance_score, reverse=True)
            top_unreviewed = [
                {
                    "id": a.id,
                    "title": a.title[:80] + ("..." if len(a.title) > 80 else ""),
                    "score": round(a.relevance_score, 1),
                    "journal": a.journal or "Unbekannt",
                }
                for a in unreviewed[:5]
            ]

            # Trending-Topics aus Keywords extrahieren (einfache Häufigkeitsanalyse)
            trending_topics = _extract_trending_keywords(hq_articles)

            # Suggestion generieren
            suggestion_de = _generate_coverage_suggestion(
                specialty, total, high_quality_count, approved_count,
                severity, trending_topics,
            )

            gaps.append(CoverageLuecke(
                specialty=specialty,
                total_articles=total,
                high_quality_count=high_quality_count,
                approved_count=approved_count,
                approval_rate=round(approval_rate, 3),
                avg_score=round(avg_score, 1),
                trending_topics=trending_topics,
                top_unreviewed=top_unreviewed,
                severity=severity,
                suggestion_de=suggestion_de,
            ))

    # Sortieren: critical zuerst, dann warning, dann info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    gaps.sort(key=lambda g: (severity_order.get(g.severity, 9), -g.high_quality_count))

    logger.info(
        "Lücken-Detektor: %d Fachgebiete mit Lücken erkannt "
        "(critical=%d, warning=%d, info=%d)",
        len(gaps),
        sum(1 for g in gaps if g.severity == "critical"),
        sum(1 for g in gaps if g.severity == "warning"),
        sum(1 for g in gaps if g.severity == "info"),
    )
    return gaps


def _extract_trending_keywords(articles: list[Article], top_n: int = 5) -> list[str]:
    """Extrahiert häufige Themen-Keywords aus Artikel-Titeln und Tags."""
    from collections import Counter

    word_counts: Counter = Counter()
    for a in articles:
        # Titel-Wörter (> 5 Zeichen, um Stopwords zu vermeiden)
        title_words = (a.title or "").lower().split()
        for w in title_words:
            w_clean = w.strip(".,;:!?()[]\"'")
            if len(w_clean) > 5:
                word_counts[w_clean] += 1

        # Highlight-Tags
        if a.highlight_tags:
            for tag in a.highlight_tags.split("|"):
                tag = tag.strip()
                if tag and not tag.startswith("Studientyp:"):
                    word_counts[tag.lower()] += 1

    return [word for word, _ in word_counts.most_common(top_n)]


def _generate_coverage_suggestion(
    specialty: str,
    total: int,
    hq_count: int,
    approved: int,
    severity: str,
    topics: list[str],
) -> str:
    """Generiert einen redaktionellen Vorschlag auf Deutsch."""
    topics_str = ", ".join(topics[:3]) if topics else "diverse Themen"

    if severity == "critical" and approved == 0 and hq_count >= 5:
        return (
            f"{specialty}: {hq_count} hochwertige Artikel warten auf Sichtung — "
            f"keiner wurde bisher freigegeben. Schwerpunkte: {topics_str}. "
            f"Dringend redaktionelle Bewertung empfohlen."
        )
    elif severity == "critical" and approved == 0:
        return (
            f"{specialty}: {total} Artikel im Zeitraum, aber null Freigaben. "
            f"Redaktionelle Abdeckung fehlt komplett. Themen: {topics_str}."
        )
    elif severity == "warning":
        rate_pct = round(approved / total * 100) if total else 0
        return (
            f"{specialty}: Nur {rate_pct}% Freigaberate ({approved}/{total}). "
            f"{hq_count} HQ-Artikel vorhanden. "
            f"Empfehlung: Fokus auf {topics_str}."
        )
    else:  # info
        rate_pct = round(approved / total * 100) if total else 0
        return (
            f"{specialty}: {rate_pct}% Freigaberate — ausbaufähig. "
            f"Aktuelle Themen: {topics_str}."
        )


def detect_topic_gaps(days: int = 7) -> list[TopicLuecke]:
    """Erkennt Trend-Themen ohne redaktionelle Bearbeitung.

    Nutzt compute_trends() für aktuelle Trends und prüft, ob in jedem
    Cluster mindestens ein Artikel APPROVED ist.
    """
    try:
        from src.processing.trends import compute_trends, TrendCluster
    except ImportError:
        logger.warning("Trends-Modul nicht verfügbar — Topic-Gaps übersprungen")
        return []

    clusters, _ = compute_trends(days=days, use_embeddings=False, max_clusters=12)
    if not clusters:
        logger.info("Keine Trend-Cluster gefunden — keine Topic-Gaps")
        return []

    topic_gaps: list[TopicLuecke] = []

    with get_session() as session:
        for cluster in clusters:
            if not cluster.article_ids:
                continue

            # Prüfe ob IRGENDEIN Artikel im Cluster APPROVED ist
            approved_stmt = (
                select(func.count(Article.id))
                .where(col(Article.id).in_(cluster.article_ids))
                .where(Article.status == "APPROVED")
            )
            approved_count = session.exec(approved_stmt).one()

            if approved_count > 0:
                # Thema ist redaktionell abgedeckt — kein Gap
                continue

            # Ältestes Datum im Cluster für days_unreviewed
            oldest_stmt = (
                select(func.min(Article.pub_date))
                .where(col(Article.id).in_(cluster.article_ids))
            )
            oldest_date = session.exec(oldest_stmt).one()
            days_unreviewed = 0
            if oldest_date:
                if isinstance(oldest_date, date):
                    days_unreviewed = (date.today() - oldest_date).days
                else:
                    days_unreviewed = (date.today() - oldest_date).days

            # Pitch-Score für Ranking: momentum * avg_score * log(count)
            momentum_weight = {
                "exploding": 4, "rising": 3, "stable": 2, "falling": 1,
            }.get(cluster.momentum, 2)

            count = cluster.count_current or len(cluster.article_ids)
            pitch_score = (
                momentum_weight
                * (cluster.avg_score / 100.0)
                * math.log2(max(count, 1) + 1)
            )

            # Top 5 Artikel-IDs nach Score
            top_ids_stmt = (
                select(Article.id)
                .where(col(Article.id).in_(cluster.article_ids))
                .order_by(col(Article.relevance_score).desc())
                .limit(5)
            )
            top_ids = list(session.exec(top_ids_stmt).all())

            # Suggestion generieren
            suggestion_de = _generate_topic_suggestion(cluster, count, days_unreviewed)

            topic_gaps.append(TopicLuecke(
                topic=cluster.smart_label_de or cluster.topic_label,
                article_count=count,
                avg_score=cluster.avg_score,
                momentum=cluster.momentum,
                specialties=cluster.specialties[:4],
                top_article_ids=top_ids,
                days_unreviewed=days_unreviewed,
                suggestion_de=suggestion_de,
            ))

            # Pitch-Score für späteres Sortieren merken
            topic_gaps[-1]._pitch_score = pitch_score  # type: ignore[attr-defined]

    # Sortieren nach Pitch-Score (absteigend)
    topic_gaps.sort(
        key=lambda t: getattr(t, "_pitch_score", 0),
        reverse=True,
    )

    logger.info("Lücken-Detektor: %d Trend-Themen ohne Freigabe erkannt", len(topic_gaps))
    return topic_gaps


def _generate_topic_suggestion(cluster, count: int, days_unreviewed: int) -> str:
    """Generiert einen konkreten Pitch für ein unbewertetes Trendthema."""
    topic = cluster.smart_label_de or cluster.topic_label
    specs = ", ".join(cluster.specialties[:2]) if cluster.specialties else "diverse Fachgebiete"
    journals = ", ".join(cluster.top_journals[:2]) if cluster.top_journals else "verschiedene Quellen"

    if cluster.momentum == "exploding":
        return (
            f"Stark steigendes Thema: '{topic}' — {count} Artikel "
            f"in {specs}, publiziert u.a. in {journals}. "
            f"Seit {days_unreviewed} Tagen ohne redaktionelle Sichtung. "
            f"Sofortige Bearbeitung empfohlen."
        )
    elif cluster.momentum == "rising":
        return (
            f"Aufkommendes Thema: '{topic}' mit {count} Artikeln. "
            f"Schwerpunkt in {specs}. "
            f"Gute Evidenzlage (Ø {cluster.avg_score:.0f} Score) — lohnt sich für Aufbereitung."
        )
    else:
        return (
            f"Thema '{topic}': {count} Artikel aus {specs}. "
            f"Ø Score {cluster.avg_score:.0f} — bisher unbearbeitet. "
            f"Prüfung auf redaktionelle Relevanz empfohlen."
        )


def get_full_gap_report(days: int = 7) -> dict:
    """Vollständige Lücken-Analyse für das Editorial-Dashboard.

    Kombiniert Coverage-Gaps (pro Fachgebiet) und Topic-Gaps (pro Trend)
    in einen umfassenden Report.
    """
    coverage_gaps = detect_coverage_gaps(days)
    topic_gaps = detect_topic_gaps(days)

    # Summary-Statistiken
    total_specialties = len(SPECIALTY_MESH)
    underserved = [g for g in coverage_gaps if g.approval_rate < 0.30]
    biggest_gap = (
        coverage_gaps[0].specialty if coverage_gaps else None
    )

    return {
        "coverage_gaps": coverage_gaps,
        "topic_gaps": topic_gaps,
        "summary_stats": {
            "total_specialties": total_specialties,
            "underserved_count": len(underserved),
            "trending_uncovered": len(topic_gaps),
            "biggest_gap": biggest_gap,
        },
        "generated_at": datetime.now(),
    }

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


@dataclass
class StaleContent:
    """Ein Artikel der möglicherweise medizinisch veraltet ist."""
    article_id: int
    title: str
    specialty: str
    pub_date: date
    age_days: int
    source: str
    relevance_score: float
    reason: str  # Warum veraltet (z.B. "Neuere Leitlinie verfügbar")
    newer_article_id: Optional[int] = None
    newer_article_title: Optional[str] = None
    freshness_score: float = 0.0  # 0=veraltet, 100=aktuell


@dataclass
class RegulatoryGap:
    """Eine regulatorische Neuigkeit ohne redaktionelle Aufbereitung."""
    title: str
    source: str  # EMA, AWMF, G-BA, BfArM
    pub_date: date
    age_days: int
    article_id: int
    relevance_score: float
    has_coverage: bool  # Gibt es einen aufbereiteten Artikel dazu?
    related_article_count: int  # Wie viele Artikel zum gleichen Thema?
    suggestion_de: str


def detect_stale_content(days_lookback: int = 90, min_age_days: int = 30) -> list[StaleContent]:
    """Erkennt Artikel die möglicherweise medizinisch veraltet sind.

    Prüft für APPROVED/SAVED Artikel ob es neuere Artikel zum gleichen
    Thema/Fachgebiet gibt, die deutlich höher scoren.

    Content Freshness Score (0-100):
    - 100: Kein neuerer Artikel zum Thema
    - 70-99: Neuere Artikel existieren, aber gleicher Evidenzstand
    - 30-69: Neuere Artikel mit höherem Score (Update empfohlen)
    - 0-29: Deutlich neuerer High-Score Artikel (wahrscheinlich veraltet)
    """
    cutoff = date.today() - timedelta(days=days_lookback)
    min_age_cutoff = date.today() - timedelta(days=min_age_days)
    stale: list[StaleContent] = []

    with get_session() as session:
        # Finde alle freigegebenen/gemerkten Artikel die alt genug sind
        old_articles = session.exec(
            select(Article)
            .where(Article.status.in_(["APPROVED", "SAVED"]))
            .where(Article.pub_date <= min_age_cutoff)
            .where(Article.pub_date >= cutoff)
            .order_by(col(Article.pub_date))
        ).all()

        if not old_articles:
            return stale

        for old_art in old_articles:
            if not old_art.specialty or not old_art.pub_date:
                continue

            age_days = (date.today() - old_art.pub_date).days

            # Suche neuere Artikel im gleichen Fachgebiet mit höherem Score
            newer = session.exec(
                select(Article)
                .where(Article.specialty == old_art.specialty)
                .where(Article.pub_date > old_art.pub_date)
                .where(Article.relevance_score > old_art.relevance_score + 10)
                .order_by(col(Article.relevance_score).desc())
                .limit(1)
            ).first()

            if not newer:
                continue  # Kein besserer neuerer Artikel → noch aktuell

            # Titel-Ähnlichkeit prüfen (gleiche Thematik?)
            from src.processing.dedup import _normalize_title, _similarity_ratio
            sim = _similarity_ratio(
                _normalize_title(old_art.title),
                _normalize_title(newer.title),
            )

            # Keyword-Overlap prüfen (gleiche Schlagworte?)
            old_words = set(_normalize_title(old_art.title).split())
            new_words = set(_normalize_title(newer.title).split())
            keyword_overlap = len(old_words & new_words) / max(len(old_words | new_words), 1)

            # Nur wenn thematisch verwandt (Titel >30% ähnlich ODER >25% Keyword-Overlap)
            if sim < 0.30 and keyword_overlap < 0.25:
                continue

            # Freshness Score berechnen
            score_gap = newer.relevance_score - old_art.relevance_score
            recency_gap = (newer.pub_date - old_art.pub_date).days if newer.pub_date else 0

            freshness = 100.0
            if score_gap > 20:
                freshness -= 40  # Deutlich höherer Score
            elif score_gap > 10:
                freshness -= 20
            if recency_gap > 60:
                freshness -= 30  # Deutlich neuerer Artikel
            elif recency_gap > 30:
                freshness -= 15
            if age_days > 90:
                freshness -= 20  # Sehr alter Artikel
            elif age_days > 60:
                freshness -= 10
            freshness = max(0.0, min(100.0, freshness))

            # Grund-Text generieren
            if score_gap > 20:
                reason = f"Neuerer Artikel mit deutlich höherem Score ({newer.relevance_score:.0f} vs. {old_art.relevance_score:.0f})"
            else:
                reason = f"Neuerer Artikel verfügbar (Score {newer.relevance_score:.0f}, {recency_gap} Tage neuer)"

            # Prüfe ob Leitlinien-Update
            new_title_lower = (newer.title or "").lower()
            if any(kw in new_title_lower for kw in ["leitlinie", "guideline", "s3-", "s2k-", "update", "aktualisier"]):
                reason = f"Neuere Leitlinie verfügbar: {newer.title[:80]}"
                freshness = min(freshness, 25)  # Leitlinien-Update = definitiv veraltet

            stale.append(StaleContent(
                article_id=old_art.id,
                title=old_art.title[:120],
                specialty=old_art.specialty,
                pub_date=old_art.pub_date,
                age_days=age_days,
                source=old_art.source or "",
                relevance_score=old_art.relevance_score,
                reason=reason,
                newer_article_id=newer.id,
                newer_article_title=newer.title[:120] if newer.title else None,
                freshness_score=freshness,
            ))

    # Sortieren: niedrigster Freshness Score zuerst (am meisten veraltet)
    stale.sort(key=lambda s: s.freshness_score)
    logger.info("Content Freshness: %d potenziell veraltete Artikel erkannt", len(stale))
    return stale


def detect_regulatory_gaps(days: int = 14) -> list[RegulatoryGap]:
    """Erkennt regulatorische Neuigkeiten ohne redaktionelle Aufbereitung.

    Prüft EMA-, AWMF-, G-BA-, BfArM-Artikel der letzten N Tage und ob
    es dazu aufbereitete Artikel (Fachpresse) gibt.
    """
    cutoff = date.today() - timedelta(days=days)
    regulatory_sources = ["ema", "awmf", "g-ba", "bfarm", "iqwig", "rki"]
    gaps: list[RegulatoryGap] = []

    with get_session() as session:
        # Finde alle Behörden-Artikel im Zeitraum
        reg_articles = session.exec(
            select(Article)
            .where(Article.pub_date >= cutoff)
            .where(
                col(Article.source_category).in_(["behoerde", "leitlinie"])
            )
            .order_by(col(Article.relevance_score).desc())
        ).all()

        for reg in reg_articles:
            if not reg.title:
                continue

            # Suche aufbereitete Artikel zum gleichen Thema
            from src.processing.dedup import _normalize_title
            title_words = _normalize_title(reg.title).split()
            # Nimm die 3 längsten Wörter als Keywords
            keywords = sorted(title_words, key=len, reverse=True)[:3]

            if not keywords:
                continue

            # Suche nach Artikeln mit ähnlichen Keywords aus Fachpresse
            from sqlalchemy import or_
            coverage_conditions = [
                col(Article.title).ilike(f"%{kw}%") for kw in keywords if len(kw) > 4
            ]
            if not coverage_conditions:
                continue

            related = session.exec(
                select(func.count(Article.id))
                .where(Article.pub_date >= cutoff)
                .where(
                    col(Article.source_category).in_(["fachpresse_de", "fachpresse_aufbereitet"])
                )
                .where(or_(*coverage_conditions))
            ).one()

            has_coverage = related > 0
            if has_coverage:
                continue  # Bereits aufbereitet

            age_days = (date.today() - reg.pub_date).days if reg.pub_date else 0
            source_label = (reg.source or "Behörde")[:30]

            suggestion = (
                f"{source_label}: '{reg.title[:80]}' "
                f"hat keine redaktionelle Einordnung. "
            )
            if age_days <= 3:
                suggestion += "Aktuell und zeitkritisch."
            elif age_days <= 7:
                suggestion += "Noch aktuell, Aufbereitung empfohlen."
            else:
                suggestion += f"Seit {age_days} Tagen unbearbeitet."

            gaps.append(RegulatoryGap(
                title=reg.title[:150],
                source=source_label,
                pub_date=reg.pub_date,
                age_days=age_days,
                article_id=reg.id,
                relevance_score=reg.relevance_score,
                has_coverage=False,
                related_article_count=0,
                suggestion_de=suggestion,
            ))

    # Sortieren: neueste und höchstbewertete zuerst
    gaps.sort(key=lambda g: (-g.relevance_score, g.age_days))
    logger.info("Regulatorische Lücken: %d Behörden-Meldungen ohne Aufbereitung", len(gaps))
    return gaps[:20]  # Top 20


def detect_demand_gaps(days: int = 7) -> list[dict]:
    """Kreuzt GA4-Null-Treffer mit LUMIO-Artikelbestand.

    Findet Suchbegriffe die Ärzte auf esanum suchen, zu denen LUMIO
    keine oder nur wenige Artikel hat. Das sind die wertvollsten
    Content-Lücken (Signal-Konzept).

    Returns list of dicts mit: term, search_count, lumio_article_count,
    gap_severity, suggestion.
    """
    try:
        from src.integrations.ga4 import fetch_ga4_report
    except ImportError:
        logger.debug("GA4-Modul nicht verfügbar")
        return []

    report = fetch_ga4_report(days=days)
    if report.error or not report.null_searches:
        return []

    demand_gaps = []

    with get_session() as session:
        for ns in report.null_searches:
            # Prüfe ob LUMIO Artikel zu diesem Suchbegriff hat
            from sqlalchemy import or_
            pattern = f"%{ns.term}%"
            count = session.exec(
                select(func.count(Article.id)).where(
                    or_(
                        col(Article.title).ilike(pattern),
                        col(Article.abstract).ilike(pattern),
                    )
                )
            ).one()

            if count >= 5:
                continue  # Genug Artikel vorhanden

            severity = "critical" if ns.session_count >= 50 and count == 0 else \
                       "warning" if ns.session_count >= 20 or count == 0 else "info"

            if count == 0:
                suggestion = (
                    f"\u00c4rzte suchen nach \u201a{ns.term}\u2018 ({ns.session_count} Suchen in {days}d), "
                    f"aber kein einziger Artikel dazu vorhanden. "
                    f"Hohe Priorit\u00e4t f\u00fcr Content-Erstellung."
                )
            else:
                suggestion = (
                    f"\u00c4rzte suchen nach \u201a{ns.term}\u2018 ({ns.session_count} Suchen), "
                    f"aber nur {count} Artikel verf\u00fcgbar. Nachschub empfohlen."
                )

            demand_gaps.append({
                "term": ns.term,
                "search_count": ns.session_count,
                "lumio_article_count": count,
                "gap_severity": severity,
                "suggestion": suggestion,
            })

    demand_gaps.sort(key=lambda g: (
        {"critical": 0, "warning": 1, "info": 2}[g["gap_severity"]],
        -g["search_count"],
    ))

    logger.info("Demand-Gaps: %d Nachfrage-L\u00fccken erkannt", len(demand_gaps))
    return demand_gaps[:20]


def get_full_gap_report(days: int = 7) -> dict:
    """Vollst\u00e4ndige L\u00fccken-Analyse f\u00fcr das Editorial-Dashboard.

    Kombiniert Coverage-Gaps (pro Fachgebiet), Topic-Gaps (pro Trend),
    Content Freshness, regulat. L\u00fccken und GA4-Nachfrage-L\u00fccken (Signal).
    """
    coverage_gaps = detect_coverage_gaps(days)
    topic_gaps = detect_topic_gaps(days)

    # Content Freshness (90 Tage zur\u00fcck, min. 30 Tage alt)
    try:
        stale_content = detect_stale_content(days_lookback=90, min_age_days=30)
    except Exception as exc:
        logger.warning("Content Freshness fehlgeschlagen: %s", exc)
        stale_content = []

    # Regulatorische L\u00fccken (letzte 14 Tage)
    try:
        regulatory_gaps = detect_regulatory_gaps(days=14)
    except Exception as exc:
        logger.warning("Regulat. L\u00fccken-Erkennung fehlgeschlagen: %s", exc)
        regulatory_gaps = []

    # GA4 Nachfrage-L\u00fccken (Signal)
    try:
        demand_gaps = detect_demand_gaps(days=days)
    except Exception as exc:
        logger.warning("GA4 Demand-Gaps fehlgeschlagen: %s", exc)
        demand_gaps = []

    # Summary-Statistiken
    total_specialties = len(SPECIALTY_MESH)
    underserved = [g for g in coverage_gaps if g.approval_rate < 0.30]
    biggest_gap = (
        coverage_gaps[0].specialty if coverage_gaps else None
    )

    return {
        "coverage_gaps": coverage_gaps,
        "topic_gaps": topic_gaps,
        "stale_content": stale_content,
        "regulatory_gaps": regulatory_gaps,
        "demand_gaps": demand_gaps,
        "summary_stats": {
            "total_specialties": total_specialties,
            "underserved_count": len(underserved),
            "trending_uncovered": len(topic_gaps),
            "stale_count": len(stale_content),
            "regulatory_gap_count": len(regulatory_gaps),
            "demand_gap_count": len(demand_gaps),
            "biggest_gap": biggest_gap,
        },
        "generated_at": datetime.now(),
    }

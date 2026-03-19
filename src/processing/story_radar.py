"""Story-Radar: Automatische Redaktions-Pitches aus Trend-Clustern.

Generiert editorial Story-Pitches aus trending Cross-Specialty-Themen.
Wenn ein medizinisches Thema in einem Fachgebiet aufkommt und sich auf
andere ausbreitet, wird ein fertiger Pitch fuer Medizinredakteure erstellt.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.processing.trends import compute_trends, TrendCluster

logger = logging.getLogger(__name__)


@dataclass
class StoryPitch:
    """Ein redaktioneller Story-Pitch basierend auf einem Trend-Cluster."""

    headline_de: str = ""
    hook_de: str = ""
    evidence_summary_de: str = ""
    angle_suggestions: list[str] = field(default_factory=list)
    source_articles: list[int] = field(default_factory=list)
    trend: Optional[TrendCluster] = None
    pitch_score: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Pitch-Scoring
# ---------------------------------------------------------------------------

def _compute_pitch_score(trend: TrendCluster) -> float:
    """Berechne einen Pitch-Score (0-100) fuer einen Trend-Cluster.

    Hoehere Scores = bessere Pitch-Kandidaten.
    """
    score = 0.0

    # Basis: avg_score des Clusters (skaliert auf 0-25)
    score += min(trend.avg_score * 0.25, 25.0)

    # Cross-Specialty Bonus
    if trend.is_cross_specialty:
        score += 20.0

    # Momentum Bonus
    momentum_bonus = {
        "exploding": 25.0,
        "rising": 15.0,
        "stable": 0.0,
        "falling": -5.0,
    }
    score += momentum_bonus.get(trend.momentum, 0.0)

    # Evidence-Trend Bonus
    if trend.evidence_trend == "rising":
        score += 15.0

    # High-Tier Journal Ratio Bonus
    if trend.high_tier_ratio > 0.3:
        score += 10.0

    # Cluster-Size Sweet Spot (5-15 Artikel)
    if 5 <= trend.count_current <= 15:
        score += 15.0

    return round(min(max(score, 0.0), 100.0), 1)


# ---------------------------------------------------------------------------
# LLM Pitch-Generierung
# ---------------------------------------------------------------------------

def _generate_pitch_with_llm(trend: TrendCluster, pitch_score: float) -> StoryPitch:
    """Generiere einen Story-Pitch via LLM fuer einen Trend-Cluster."""
    from src.config import get_provider_chain
    from src.llm_client import cached_chat_completion

    # Kontext fuer den Prompt aufbauen
    specialties_text = ", ".join(trend.specialties[:5]) or "Diverse"
    journals_text = ", ".join(trend.top_journals[:5]) or "Diverse"

    evidence_text = ""
    if trend.evidence_levels:
        ev_parts = [f"{k}: {v}" for k, v in sorted(
            trend.evidence_levels.items(), key=lambda x: -x[1]
        )[:5]]
        evidence_text = f"Studientypen: {', '.join(ev_parts)}"

    momentum_text = {
        "exploding": "stark steigend (explosives Wachstum)",
        "rising": "steigend",
        "stable": "stabil",
        "falling": "ruecklaeufig",
    }.get(trend.momentum, "stabil")

    cross_text = ""
    if trend.is_cross_specialty and trend.specialty_spread:
        cross_text = f"Cross-Specialty-Expansion: {trend.specialty_spread}"

    summary_text = trend.trend_summary_de or "Keine Zusammenfassung verfuegbar."

    system_prompt = (
        "Du bist Redaktionsassistent einer medizinischen Fachredaktion. "
        "Generiere einen Story-Pitch fuer Redakteure, die Artikel fuer "
        "praktizierende Aerzte schreiben."
    )

    user_prompt = f"""Erstelle einen Story-Pitch basierend auf folgendem medizinischen Trend:

Thema: {trend.topic_label}
Smart-Label: {trend.smart_label_de or trend.topic_label}
Artikelanzahl: {trend.count_current}
Momentum: {momentum_text}
Fachgebiete: {specialties_text}
Top-Quellen: {journals_text}
{evidence_text}
{cross_text}
Trend-Zusammenfassung: {summary_text}

Antworte EXAKT in diesem Format (4 Teile getrennt durch ;;;):
HEADLINE: [Catchy deutsche Headline fuer den Redaktions-Pitch, max 80 Zeichen];;;HOOK: [2-3 Saetze: Warum ist das JETZT eine Story? Momentum, Evidenz-Shift, Cross-Specialty-Aspekt];;;EVIDENZ: [Kurze Zusammenfassung der wichtigsten Studien/Journals, Studientypen, Scores];;;ANGLES: [3 konkrete Blickwinkel/Angles, getrennt durch |, die der Redakteur verfolgen koennte]"""

    providers = get_provider_chain("trend_summary")
    text = cached_chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
        max_tokens=400,
    )

    pitch = StoryPitch(
        source_articles=trend.article_ids[:20],
        trend=trend,
        pitch_score=pitch_score,
        generated_at=datetime.now(),
    )

    if text is None:
        logger.warning("LLM-Pitch-Generierung fehlgeschlagen fuer '%s'", trend.topic_label)
        _fallback_pitch(pitch, trend)
        return pitch

    # Response parsen
    parts = text.split(";;;")
    for part in parts:
        part = part.strip()
        upper = part.upper()
        if upper.startswith("HEADLINE:"):
            pitch.headline_de = part[9:].strip().strip('"')
        elif upper.startswith("HOOK:"):
            pitch.hook_de = part[5:].strip()
        elif upper.startswith("EVIDENZ:"):
            pitch.evidence_summary_de = part[8:].strip()
        elif upper.startswith("ANGLES:"):
            raw_angles = part[7:].strip()
            pitch.angle_suggestions = [
                a.strip() for a in raw_angles.split("|") if a.strip()
            ]

    # Fallback fuer fehlende Felder
    if not pitch.headline_de:
        pitch.headline_de = trend.smart_label_de or trend.topic_label
    if not pitch.hook_de:
        _fallback_pitch(pitch, trend)
    if not pitch.angle_suggestions:
        pitch.angle_suggestions = _fallback_angles(trend)

    return pitch


def _fallback_pitch(pitch: StoryPitch, trend: TrendCluster):
    """Template-basierter Fallback wenn LLM nicht verfuegbar."""
    topic = trend.smart_label_de or trend.topic_label
    specs = ", ".join(trend.specialties[:2]) or "diverse Fachgebiete"
    journals = ", ".join(trend.top_journals[:2]) or "verschiedene Quellen"

    if not pitch.headline_de:
        pitch.headline_de = topic

    if not pitch.hook_de:
        if trend.momentum == "exploding":
            pitch.hook_de = (
                f"{topic} zeigt explosives Wachstum mit {trend.count_current} "
                f"neuen Artikeln. Das Thema gewinnt rasant an Bedeutung in {specs}."
            )
        elif trend.is_cross_specialty:
            pitch.hook_de = (
                f"{topic} breitet sich ueber Fachgrenzen aus ({trend.specialty_spread}). "
                f"Ein Thema, das praktizierende Aerzte jetzt kennen sollten."
            )
        else:
            pitch.hook_de = (
                f"{trend.count_current} aktuelle Artikel zu {topic} in {specs}. "
                f"Das Thema verdient redaktionelle Aufmerksamkeit."
            )

    if not pitch.evidence_summary_de:
        ev_parts = []
        if trend.evidence_levels:
            for etype, ecount in sorted(
                trend.evidence_levels.items(), key=lambda x: -x[1]
            )[:3]:
                ev_parts.append(f"{etype} ({ecount}x)")
        ev_text = ", ".join(ev_parts) if ev_parts else "diverse Studientypen"
        pitch.evidence_summary_de = (
            f"Evidenzbasis: {ev_text}. "
            f"Top-Quellen: {journals}. "
            f"Durchschnittlicher Relevanz-Score: {trend.avg_score:.0f}/100."
        )

    if not pitch.angle_suggestions:
        pitch.angle_suggestions = _fallback_angles(trend)


def _fallback_angles(trend: TrendCluster) -> list[str]:
    """Generiere Standard-Angles basierend auf Trend-Eigenschaften."""
    angles = []
    topic = trend.smart_label_de or trend.topic_label

    if trend.is_cross_specialty and trend.specialty_spread:
        angles.append(
            f"Cross-Specialty-Perspektive: Wie {topic} Fachgrenzen ueberschreitet "
            f"({trend.specialty_spread})"
        )
    if trend.dominant_study_type:
        angles.append(
            f"Evidenz-Update: Was die neuesten {trend.dominant_study_type}-Studien zeigen"
        )
    angles.append(
        f"Praxis-Relevanz: Was sich fuer den Praxisalltag aendert"
    )

    # Auffuellen auf mindestens 3 Angles
    if len(angles) < 3:
        angles.append(f"Experten-Interview: Einordnung durch Fachspezialisten")
    if len(angles) < 3:
        angles.append(f"Leitlinien-Check: Aktuelle Empfehlungen vs. neue Evidenz")

    return angles[:3]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_story_pitches(
    trends: list[TrendCluster],
    max_pitches: int = 3,
) -> list[StoryPitch]:
    """Generiere Story-Pitches aus einer Liste von Trend-Clustern.

    Bewertet alle Trends, waehlt die besten Kandidaten und
    generiert LLM-gestuetzte Pitches.
    """
    if not trends:
        return []

    # Score berechnen und sortieren
    scored = [(trend, _compute_pitch_score(trend)) for trend in trends]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Top-N auswaehlen
    top_trends = scored[:max_pitches]

    # Pitches generieren
    pitches = []
    for trend, pitch_score in top_trends:
        try:
            pitch = _generate_pitch_with_llm(trend, pitch_score)
            pitches.append(pitch)
        except Exception as exc:
            logger.error(
                "Pitch-Generierung fehlgeschlagen fuer '%s': %s",
                trend.topic_label, exc,
            )

    # Nach pitch_score sortieren (absteigend)
    pitches.sort(key=lambda p: p.pitch_score, reverse=True)
    return pitches


def get_story_pitches(
    days: int = 7,
    max_pitches: int = 3,
) -> list[StoryPitch]:
    """Haupteinstiegspunkt: Trends berechnen und Story-Pitches generieren.

    Ruft ``compute_trends`` auf, filtert die besten Kandidaten
    und generiert LLM-Pitches.
    """
    logger.info("Story-Radar: Generiere Pitches (days=%d, max=%d)", days, max_pitches)

    result = compute_trends(days=days, min_cluster_size=3, use_embeddings=False, max_clusters=8)
    if isinstance(result, tuple):
        trends, _ = result
    else:
        trends = result

    if not trends:
        logger.info("Story-Radar: Keine Trends verfuegbar")
        return []

    pitches = generate_story_pitches(trends, max_pitches=max_pitches)
    logger.info("Story-Radar: %d Pitches generiert", len(pitches))
    return pitches

"""Redaktionskalender — Intelligente Themenplanung für die Redaktion.

Includes the "Saisonal" tab backend: seasonal topic clusters, awareness days,
regulatory dates, and timeline data for practicing physicians.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Optional
from collections import Counter, defaultdict

from sqlmodel import select, func, col
from src.models import Article, get_session

logger = logging.getLogger(__name__)


# Major medical congresses (month, name, specialty, typical_duration_days)
MEDICAL_CONGRESSES = [
    (1, "J.P. Morgan Healthcare Conference", "Allgemeinmedizin", 4),
    (1, "ASCO GI (Gastrointestinal Cancers Symposium)", "Onkologie", 3),
    (2, "ATTD (Advanced Technologies & Treatments for Diabetes)", "Diabetologie/Endokrinologie", 4),
    (3, "ACC (American College of Cardiology)", "Kardiologie", 3),
    (3, "ECTRIMS (Multiple Sclerosis)", "Neurologie", 4),
    (4, "DGK (Deutsche Gesellschaft für Kardiologie)", "Kardiologie", 4),
    (4, "DGIM (Deutsche Gesellschaft für Innere Medizin)", "Allgemeinmedizin", 5),
    (5, "ATS (American Thoracic Society)", "Pneumologie", 5),
    (5, "ASCO (American Society of Clinical Oncology)", "Onkologie", 5),
    (6, "EHA (European Hematology Association)", "Onkologie", 4),
    (6, "EULAR (Rheumatologie)", "Orthopädie", 4),
    (6, "ADA (American Diabetes Association)", "Diabetologie/Endokrinologie", 5),
    (8, "ESC (European Society of Cardiology)", "Kardiologie", 5),
    (9, "ESMO (European Society for Medical Oncology)", "Onkologie", 5),
    (9, "EASD (European Association for the Study of Diabetes)", "Diabetologie/Endokrinologie", 4),
    (9, "DGP (Deutsche Gesellschaft für Pneumologie)", "Pneumologie", 4),
    (10, "UEG Week (Gastroenterologie)", "Gastroenterologie", 4),
    (10, "DGHO (Deutsche Gesellschaft für Hämatologie/Onkologie)", "Onkologie", 4),
    (10, "ACR (American College of Rheumatology)", "Orthopädie", 5),
    (11, "AHA (American Heart Association)", "Kardiologie", 4),
    (11, "AASLD (Liver Meeting)", "Gastroenterologie", 5),
    (11, "RSNA (Radiological Society)", "Allgemeinmedizin", 6),
    (12, "ASH (American Society of Hematology)", "Onkologie", 4),
]

# Seasonal health patterns
SEASONAL_TOPICS = {
    1: ["Grippe-Saison Höhepunkt", "Vitamin-D-Mangel", "Winterdepression"],
    2: ["Grippe-Nachläufer", "Fastenzeit & Ernährung"],
    3: ["Allergie-Saison Start", "Frühjahrsmüdigkeit", "Pollenflug"],
    4: ["Allergie Hochphase", "Sonnenschutz-Saison Start", "Zecken-Saison"],
    5: ["Allergie + Asthma Peak", "Sonnenbrand-Prävention", "FSME-Impfung"],
    6: ["Hitze-Prävention", "Reisemedizin-Saison", "UV-Schutz"],
    7: ["Hitzewelle & Kreislauf", "Reisedurchfall", "Badeunfälle"],
    8: ["Hitze-Spätfolgen", "Schulstart-Impfungen", "Kongress-Saison Start"],
    9: ["Grippe-Impfung Start", "Herbst-Depression", "RSV-Saison Vorbereitung"],
    10: ["Grippe-Impfkampagne", "Erkältungswelle Start", "Vitamin-D Supplementierung"],
    11: ["Grippe-Welle", "Norovirus-Saison", "Winterhaut"],
    12: ["RSV bei Kindern Peak", "Feiertags-Notfälle", "Jahresrückblick Medizin"],
}

# Search keywords for seasonal topics (topic -> list of DB search terms)
_SEASONAL_SEARCH_KEYS: dict[str, list[str]] = {
    "Grippe-Saison Höhepunkt": ["grippe", "influenza", "flu"],
    "Vitamin-D-Mangel": ["vitamin d", "vitamin-d"],
    "Winterdepression": ["depression", "seasonal affective", "winterdepression"],
    "Grippe-Nachläufer": ["grippe", "influenza", "flu"],
    "Fastenzeit & Ernährung": ["ernährung", "nutrition", "fasten", "diet"],
    "Allergie-Saison Start": ["allergi", "pollen", "heuschnupfen", "hay fever"],
    "Frühjahrsmüdigkeit": ["müdigkeit", "fatigue", "frühjahrsmüdigkeit"],
    "Pollenflug": ["pollen", "allergi", "heuschnupfen"],
    "Allergie Hochphase": ["allergi", "pollen", "antihistamin"],
    "Sonnenschutz-Saison Start": ["sonnenschutz", "uv", "sunscreen", "melanom"],
    "Zecken-Saison": ["zecken", "borreliose", "lyme", "fsme", "tick"],
    "Allergie + Asthma Peak": ["asthma", "allergi", "bronchial"],
    "Sonnenbrand-Prävention": ["sonnenbrand", "sunburn", "uv", "melanom"],
    "FSME-Impfung": ["fsme", "zecken", "tick", "impfung"],
    "Hitze-Prävention": ["hitze", "heat", "hitzschlag", "dehydrat"],
    "Reisemedizin-Saison": ["reisemedizin", "travel medicine", "malaria", "impfung"],
    "UV-Schutz": ["uv", "sonnenschutz", "melanom", "hautkrebs"],
    "Hitzewelle & Kreislauf": ["hitze", "heat", "kreislauf", "cardiovascular"],
    "Reisedurchfall": ["durchfall", "diarrhea", "reise", "travel"],
    "Badeunfälle": ["ertrinken", "drowning", "badeunfall"],
    "Hitze-Spätfolgen": ["hitze", "heat", "dehydrat"],
    "Schulstart-Impfungen": ["impfung", "vaccine", "vaccination", "immunis"],
    "Kongress-Saison Start": ["kongress", "congress", "conference"],
    "Grippe-Impfung Start": ["grippe", "influenza", "impfung", "vaccine"],
    "Herbst-Depression": ["depression", "mental health", "seasonal"],
    "RSV-Saison Vorbereitung": ["rsv", "respiratory syncytial"],
    "Grippe-Impfkampagne": ["grippe", "influenza", "impfung", "vaccine"],
    "Erkältungswelle Start": ["erkältung", "cold", "rhinovirus", "infekt"],
    "Vitamin-D Supplementierung": ["vitamin d", "vitamin-d", "supplement"],
    "Grippe-Welle": ["grippe", "influenza", "flu"],
    "Norovirus-Saison": ["norovirus", "gastroenteritis", "magen-darm"],
    "Winterhaut": ["haut", "skin", "dermat", "neurodermitis", "trocken"],
    "RSV bei Kindern Peak": ["rsv", "respiratory syncytial", "bronchiolitis"],
    "Feiertags-Notfälle": ["notfall", "emergency", "vergiftung", "unfall"],
    "Jahresrückblick Medizin": ["jahresrückblick", "review", "highlights"],
}

# Relevance scoring for congress events (by specialty importance)
_CONGRESS_RELEVANCE: dict[str, int] = {
    "Kardiologie": 5,
    "Onkologie": 5,
    "Neurologie": 4,
    "Diabetologie/Endokrinologie": 4,
    "Pneumologie": 3,
    "Gastroenterologie": 3,
    "Allgemeinmedizin": 4,
    "Orthopädie": 3,
}


@dataclass
class CalendarEvent:
    """An event in the editorial calendar."""
    date_start: date
    date_end: Optional[date]
    title: str
    category: str                    # "congress" | "seasonal" | "guideline" | "reminder"
    specialty: str
    description_de: str              # Brief description
    prep_reminder_de: str            # "2 Wochen vorher: Trend-Check zu [Thema]"
    relevance_score: int             # 1-5 stars
    related_article_count: int       # How many recent articles on this topic


@dataclass
class CalendarMonth:
    """Calendar data for one month."""
    year: int
    month: int
    events: list[CalendarEvent] = field(default_factory=list)
    seasonal_topics: list[str] = field(default_factory=list)


def _estimate_congress_date(month: int, year: int, duration_days: int) -> tuple[date, date]:
    """Estimate congress start date as the second week of the month."""
    # Place congress in the middle of the month (day 10-15)
    day = min(12, calendar.monthrange(year, month)[1])
    start = date(year, month, day)
    end = start + timedelta(days=duration_days - 1)
    return start, end


def _extract_search_keywords(name: str) -> list[str]:
    """Extract meaningful search keywords from a congress name."""
    keywords = []
    # Extract the abbreviation (text before first parenthesis or the whole name)
    if "(" in name:
        abbrev = name.split("(")[0].strip()
        full = name.split("(")[1].rstrip(")")
        keywords.append(abbrev.lower())
        # Add meaningful words from the full name
        for word in full.lower().split():
            if len(word) > 4 and word not in ("society", "association", "european", "american", "deutsche", "gesellschaft"):
                keywords.append(word)
    else:
        keywords.append(name.lower())
    return keywords


def _count_related_articles(topic: str, specialty: str, days_back: int = 30) -> int:
    """Count articles related to a topic in the DB using LIKE search on title."""
    # Determine search terms
    search_terms = _SEASONAL_SEARCH_KEYS.get(topic, [])
    if not search_terms:
        search_terms = _extract_search_keywords(topic)
    if not search_terms:
        # Fallback: use first significant word
        for word in topic.split():
            if len(word) > 3:
                search_terms.append(word.lower())
                break

    if not search_terms:
        return 0

    cutoff = date.today() - timedelta(days=days_back)
    try:
        with get_session() as session:
            from sqlalchemy import or_
            # Build OR conditions for all search terms (title + abstract)
            conditions = []
            for term in search_terms:
                pattern = f"%{term}%"
                conditions.append(Article.title.ilike(pattern))  # type: ignore[union-attr]
                conditions.append(Article.abstract.ilike(pattern))  # type: ignore[union-attr]

            stmt = (
                select(func.count(func.distinct(Article.id)))
                .select_from(Article)
                .where(
                    Article.pub_date >= cutoff,
                    or_(*conditions),
                )
            )
            return session.exec(stmt).one()
    except Exception as exc:
        logger.debug("Error counting related articles for '%s': %s", topic, exc)
        return 0


def get_related_articles(topic: str, specialty: str = "", days_back: int = 30, limit: int = 10) -> list:
    """Get actual articles related to a seasonal topic.

    Returns list of Article objects matching the topic's search keywords.
    """
    search_terms = _SEASONAL_SEARCH_KEYS.get(topic, [])
    if not search_terms:
        search_terms = _extract_search_keywords(topic)
    if not search_terms:
        for word in topic.split():
            if len(word) > 3:
                search_terms.append(word.lower())
                break

    if not search_terms:
        return []

    cutoff = date.today() - timedelta(days=days_back)
    articles = []
    seen_ids = set()
    try:
        with get_session() as session:
            for term in search_terms:
                pattern = f"%{term}%"
                from sqlalchemy import or_
                stmt = (
                    select(Article)
                    .where(
                        Article.pub_date >= cutoff,
                        or_(
                            Article.title.ilike(pattern),  # type: ignore[union-attr]
                            Article.abstract.ilike(pattern),  # type: ignore[union-attr]
                        ),
                    )
                    .order_by(Article.relevance_score.desc())
                    .limit(limit)
                )
                results = session.exec(stmt).all()
                for a in results:
                    if a.id not in seen_ids:
                        seen_ids.add(a.id)
                        articles.append(a.detach())
            # Sort by score descending
            articles.sort(key=lambda a: a.relevance_score, reverse=True)
    except Exception as exc:
        logger.debug("Error fetching related articles for '%s': %s", topic, exc)
        return []

    return articles[:limit]


def get_calendar(months_ahead: int = 3) -> list[CalendarMonth]:
    """Generate editorial calendar for the next N months."""
    today = date.today()
    months: list[CalendarMonth] = []

    for offset in range(months_ahead):
        # Calculate target month
        m = today.month + offset
        y = today.year
        while m > 12:
            m -= 12
            y += 1

        cal_month = CalendarMonth(year=y, month=m)

        # Add seasonal topics for this month
        cal_month.seasonal_topics = SEASONAL_TOPICS.get(m, [])

        # Add congress events
        for c_month, c_name, c_spec, c_dur in MEDICAL_CONGRESSES:
            if c_month == m:
                start, end = _estimate_congress_date(m, y, c_dur)
                article_count = _count_related_articles(c_name, c_spec)
                relevance = _CONGRESS_RELEVANCE.get(c_spec, 3)

                event = CalendarEvent(
                    date_start=start,
                    date_end=end,
                    title=c_name,
                    category="congress",
                    specialty=c_spec,
                    description_de=f"Medizinkongress — {c_dur} Tage, Fachgebiet {c_spec}",
                    prep_reminder_de=f"2 Wochen vorher: Trend-Check zu {c_spec} starten, aktuelle Studien sichten",
                    relevance_score=relevance,
                    related_article_count=article_count,
                )
                cal_month.events.append(event)

        # Add seasonal events
        for topic in cal_month.seasonal_topics:
            start = date(y, m, 1)
            article_count = _count_related_articles(topic, "")

            event = CalendarEvent(
                date_start=start,
                date_end=date(y, m, calendar.monthrange(y, m)[1]),
                title=topic,
                category="seasonal",
                specialty="Allgemeinmedizin",
                description_de=f"Saisonales Thema — relevant für redaktionelle Planung",
                prep_reminder_de=f"Redaktions-Tipp: Artikel zu '{topic}' vorbereiten",
                relevance_score=2,
                related_article_count=article_count,
            )
            cal_month.events.append(event)

        # Sort events by date
        cal_month.events.sort(key=lambda e: e.date_start)
        months.append(cal_month)

    return months


def get_upcoming_events(days_ahead: int = 30) -> list[CalendarEvent]:
    """Get events in the next N days, sorted by date."""
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
    events: list[CalendarEvent] = []

    # Collect months that fall within the range
    months_needed: set[int] = set()
    d = today
    while d <= end_date:
        months_needed.add(d.month)
        d += timedelta(days=28)
    months_needed.add(end_date.month)

    year = today.year

    for m in months_needed:
        y = year if m >= today.month else year + 1

        # Congress events
        for c_month, c_name, c_spec, c_dur in MEDICAL_CONGRESSES:
            if c_month == m:
                start, end = _estimate_congress_date(m, y, c_dur)
                if start > end_date or end < today:
                    continue
                article_count = _count_related_articles(c_name, c_spec)
                relevance = _CONGRESS_RELEVANCE.get(c_spec, 3)

                events.append(CalendarEvent(
                    date_start=start,
                    date_end=end,
                    title=c_name,
                    category="congress",
                    specialty=c_spec,
                    description_de=f"Medizinkongress — {c_dur} Tage, Fachgebiet {c_spec}",
                    prep_reminder_de=f"2 Wochen vorher: Trend-Check zu {c_spec} starten, aktuelle Studien sichten",
                    relevance_score=relevance,
                    related_article_count=article_count,
                ))

        # Seasonal events
        for topic in SEASONAL_TOPICS.get(m, []):
            topic_start = date(y, m, 1)
            topic_end = date(y, m, calendar.monthrange(y, m)[1])
            if topic_start > end_date or topic_end < today:
                continue
            article_count = _count_related_articles(topic, "")

            events.append(CalendarEvent(
                date_start=max(topic_start, today),
                date_end=min(topic_end, end_date),
                title=topic,
                category="seasonal",
                specialty="Allgemeinmedizin",
                description_de=f"Saisonales Thema — relevant für redaktionelle Planung",
                prep_reminder_de=f"Redaktions-Tipp: Artikel zu '{topic}' vorbereiten",
                relevance_score=2,
                related_article_count=article_count,
            ))

    events.sort(key=lambda e: e.date_start)
    return events


def get_seasonal_suggestions(month: int = 0) -> list[dict]:
    """Get seasonal topic suggestions for current or specified month.

    Returns [{topic, specialty, recent_article_count, suggestion_de}]
    """
    if month == 0:
        month = date.today().month

    topics = SEASONAL_TOPICS.get(month, [])
    suggestions: list[dict] = []

    for topic in topics:
        article_count = _count_related_articles(topic, "", days_back=30)

        if article_count > 5:
            suggestion = (
                f"{article_count} Artikel zu diesem Thema in der DB "
                f"— guter Zeitpunkt für einen Überblicksartikel"
            )
        elif article_count > 0:
            suggestion = (
                f"{article_count} Artikel vorhanden "
                f"— Thema beobachten und bei Bedarf aufgreifen"
            )
        else:
            suggestion = "Noch keine Artikel in der DB — Recherche empfohlen"

        suggestions.append({
            "topic": topic,
            "specialty": "Allgemeinmedizin",
            "recent_article_count": article_count,
            "suggestion_de": suggestion,
        })

    return suggestions


# ============================================================================
# SAISONAL — Seasonal topics for practicing physicians
# ============================================================================

@dataclass
class SeasonalTopic:
    """A seasonal medical topic with month-range and search keywords."""
    id: str
    name_de: str
    cluster: str
    months_active: List[int]
    peak_months: List[int]
    search_keys: List[str]
    icon: str


@dataclass
class TopicCluster:
    """A group of related seasonal topics."""
    id: str
    name_de: str
    icon: str
    color: str
    color_light: str
    topics: List[SeasonalTopic]


@dataclass
class AwarenessDay:
    """A health awareness day/week."""
    month: int
    day: int
    name_de: str
    description_de: str
    specialty: str
    search_keys: List[str]


@dataclass
class RegulatoryDate:
    """A regulatory deadline relevant for physicians."""
    month: int
    day: int
    title_de: str
    description_de: str
    category: str  # "EBM", "AMNOG", "Rabattvertrag", "KBV"


# ---------------------------------------------------------------------------
# Static data: 6 Topic Clusters
# ---------------------------------------------------------------------------

TOPIC_CLUSTERS: List[TopicCluster] = [
    TopicCluster(
        id="atemwege_infektionen",
        name_de="Atemwege & Infektionen",
        icon="\U0001fac1",  # 🫁
        color="#3b82f6",
        color_light="rgba(59,130,246,0.12)",
        topics=[
            SeasonalTopic("grippe", "Grippe-Saison", "atemwege_infektionen",
                          [10, 11, 12, 1, 2, 3], [1, 2],
                          ["grippe", "influenza", "flu"], "\U0001f912"),
            SeasonalTopic("rsv", "RSV-Saison", "atemwege_infektionen",
                          [10, 11, 12, 1], [12, 1],
                          ["rsv", "respiratory syncytial", "bronchiolitis"], "\U0001f476"),
            SeasonalTopic("norovirus", "Norovirus", "atemwege_infektionen",
                          [11, 12, 1, 2], [12, 1],
                          ["norovirus", "gastroenteritis", "magen-darm"], "\U0001f922"),
            SeasonalTopic("pneumonie", "Pneumonie-Saison", "atemwege_infektionen",
                          [11, 12, 1, 2, 3], [1, 2],
                          ["pneumoni", "lungenentzündung", "pneumonia"], "\U0001f637"),
            SeasonalTopic("erkaeltung", "Erkältungswelle", "atemwege_infektionen",
                          [10, 11, 12, 1, 2, 3], [11, 12],
                          ["erkältung", "cold", "rhinovirus", "infekt"], "\U0001f927"),
        ],
    ),
    TopicCluster(
        id="allergie_umwelt",
        name_de="Allergie & Umwelt",
        icon="\U0001f33f",  # 🌿
        color="#22c55e",
        color_light="rgba(34,197,94,0.12)",
        topics=[
            SeasonalTopic("pollenflug", "Pollenflug", "allergie_umwelt",
                          [3, 4, 5, 6, 7], [4, 5],
                          ["pollen", "allergi", "heuschnupfen", "hay fever"], "\U0001f33c"),
            SeasonalTopic("fsme_zecken", "FSME/Zeckensaison", "allergie_umwelt",
                          [3, 4, 5, 6, 7, 8, 9], [5, 6, 7],
                          ["fsme", "zecken", "borreliose", "lyme", "tick"], "\U0001fab2"),
            SeasonalTopic("uv_schutz", "UV-Schutz & Sonnenbrand", "allergie_umwelt",
                          [5, 6, 7, 8], [6, 7],
                          ["uv", "sonnenschutz", "sonnenbrand", "melanom", "hautkrebs"], "\u2600\ufe0f"),
            SeasonalTopic("hitzewellen", "Hitzewellen", "allergie_umwelt",
                          [6, 7, 8], [7],
                          ["hitze", "heat", "hitzschlag", "dehydrat"], "\U0001f321\ufe0f"),
            SeasonalTopic("reisemedizin", "Reisemedizin", "allergie_umwelt",
                          [5, 6, 7, 8, 9], [6, 7],
                          ["reisemedizin", "travel medicine", "malaria", "reisedurchfall"], "\u2708\ufe0f"),
        ],
    ),
    TopicCluster(
        id="psyche_praevention",
        name_de="Psyche & Prävention",
        icon="\U0001f9e0",  # 🧠
        color="#a78bfa",
        color_light="rgba(167,139,250,0.12)",
        topics=[
            SeasonalTopic("winterdepression", "Winterdepression / SAD", "psyche_praevention",
                          [10, 11, 12, 1, 2], [12, 1],
                          ["depression", "seasonal affective", "winterdepression", "sad"], "\U0001f636\u200d\U0001f32b\ufe0f"),
            SeasonalTopic("herbstdepression", "Herbst-Depression", "psyche_praevention",
                          [9, 10, 11], [10],
                          ["depression", "mental health", "seasonal"], "\U0001f342"),
            SeasonalTopic("fruehjahrsmuedigkeit", "Frühjahrsmüdigkeit", "psyche_praevention",
                          [3, 4], [3],
                          ["müdigkeit", "fatigue", "frühjahrsmüdigkeit"], "\U0001f971"),
        ],
    ),
    TopicCluster(
        id="impf_kalender",
        name_de="Impf-Kalender",
        icon="\U0001f489",  # 💉
        color="#4ade80",
        color_light="rgba(74,222,128,0.12)",
        topics=[
            SeasonalTopic("grippe_impfung", "Grippe-Impfung", "impf_kalender",
                          [9, 10, 11], [10],
                          ["grippeimpfung", "influenza impf", "flu vaccin"], "\U0001f489"),
            SeasonalTopic("fsme_impfung", "FSME-Grundimmunisierung", "impf_kalender",
                          [1, 2, 3], [2, 3],
                          ["fsme", "zecken", "impfung", "vaccination"], "\U0001fab2"),
            SeasonalTopic("covid_booster", "COVID-Booster (Herbst)", "impf_kalender",
                          [9, 10, 11], [10],
                          ["covid", "booster", "impfung", "sars-cov"], "\U0001f9ea"),
            SeasonalTopic("reiseimpfungen", "Reiseimpfungen", "impf_kalender",
                          [4, 5, 6], [5],
                          ["reiseimpfung", "travel vaccin", "impfberatung"], "\U0001f30d"),
            SeasonalTopic("schulstart_impfcheck", "Schulstart-Impfcheck", "impf_kalender",
                          [7, 8], [8],
                          ["impfung", "vaccine", "schulstart", "einschulung", "immunis"], "\U0001f392"),
        ],
    ),
    TopicCluster(
        id="dermatologie_saisonal",
        name_de="Dermatologie & Saisonal",
        icon="\u2600\ufe0f",
        color="#f472b6",
        color_light="rgba(244,114,182,0.12)",
        topics=[
            SeasonalTopic("sonnenbrand", "Sonnenbrand-Prävention", "dermatologie_saisonal",
                          [5, 6, 7, 8], [6, 7],
                          ["sonnenbrand", "sunburn", "uv", "sonnenschutz"], "\U0001f31e"),
            SeasonalTopic("winterhaut", "Winterhaut / Ekzeme", "dermatologie_saisonal",
                          [10, 11, 12, 1, 2], [12, 1],
                          ["haut", "skin", "dermat", "neurodermitis", "ekzem", "trocken"], "\u2744\ufe0f"),
            SeasonalTopic("vitamin_d", "Vitamin-D-Mangel", "dermatologie_saisonal",
                          [10, 11, 12, 1, 2, 3], [1, 2],
                          ["vitamin d", "vitamin-d", "supplement", "cholecalciferol"], "\U0001f31e"),
        ],
    ),
    TopicCluster(
        id="praxis_organisation",
        name_de="Praxis-Organisation",
        icon="\U0001f4cb",  # 📋
        color="#fbbf24",
        color_light="rgba(251,191,36,0.12)",
        topics=[
            SeasonalTopic("quartalsabrechnung", "Quartalsabrechnung", "praxis_organisation",
                          [1, 4, 7, 10], [1, 4, 7, 10],
                          ["abrechnung", "ebm", "quartal", "honorar"], "\U0001f4b0"),
            SeasonalTopic("ebm_aenderungen", "Neue EBM-Ziffern", "praxis_organisation",
                          [1, 4, 7, 10], [1, 4, 7, 10],
                          ["ebm", "gebührenordnung", "ziffer", "vergütung"], "\U0001f4dd"),
            SeasonalTopic("regress", "Regress-Prüfung", "praxis_organisation",
                          [3, 6, 9, 12], [3, 6, 9, 12],
                          ["regress", "wirtschaftlichkeit", "prüfung", "richtgrößen"], "\u26a0\ufe0f"),
        ],
    ),
]

# Flat lookup: topic_id → SeasonalTopic
_ALL_TOPICS: dict[str, SeasonalTopic] = {}
for _cluster in TOPIC_CLUSTERS:
    for _topic in _cluster.topics:
        _ALL_TOPICS[_topic.id] = _topic

# ---------------------------------------------------------------------------
# Awareness days
# ---------------------------------------------------------------------------

AWARENESS_DAYS: List[AwarenessDay] = [
    AwarenessDay(2, 4, "Weltkrebstag", "Aufklärung über Prävention und Früherkennung", "Onkologie",
                 ["krebs", "cancer", "prävention", "screening"]),
    AwarenessDay(3, 24, "Welt-Tuberkulose-Tag", "Globale TB-Bekämpfung, Resistenzen", "Infektiologie",
                 ["tuberkulose", "tuberculosis", "tbc"]),
    AwarenessDay(4, 7, "Weltgesundheitstag", "WHO-Jahresthema zur globalen Gesundheit", "Allgemeinmedizin",
                 ["gesundheit", "who", "global health"]),
    AwarenessDay(4, 11, "Welt-Parkinson-Tag", "Aufklärung über Parkinson-Erkrankung", "Neurologie",
                 ["parkinson", "tremor", "neurodegenerat"]),
    AwarenessDay(5, 31, "Welt-Nichtrauchertag", "Tabakprävention und Raucherentwöhnung", "Pneumologie",
                 ["rauchen", "tabak", "smoking", "nikotin", "lung cancer"]),
    AwarenessDay(6, 14, "Weltblutspendetag", "Blutspende-Aufklärung und Bedarf", "Allgemeinmedizin",
                 ["blutspende", "blood donation", "transfusion"]),
    AwarenessDay(9, 10, "Welt-Suizidpräventionstag", "Prävention und Entstigmatisierung", "Psychiatrie",
                 ["suizid", "suicide", "prävention", "mental health"]),
    AwarenessDay(9, 21, "Welt-Alzheimertag", "Demenz-Aufklärung und neue Therapien", "Neurologie",
                 ["alzheimer", "demenz", "dementia", "kognitiv"]),
    AwarenessDay(9, 29, "Weltherztag", "Kardiovaskuläre Prävention", "Kardiologie",
                 ["herz", "heart", "kardiovaskulär", "prävention"]),
    AwarenessDay(10, 10, "Welttag seelische Gesundheit", "Entstigmatisierung psychischer Erkrankungen", "Psychiatrie",
                 ["mental health", "psychisch", "depression", "angst"]),
    AwarenessDay(10, 29, "Welt-Schlaganfalltag", "Schlaganfall-Prävention und Akutversorgung", "Neurologie",
                 ["schlaganfall", "stroke", "apoplex"]),
    AwarenessDay(11, 14, "Weltdiabetestag", "Diabetes-Prävention und neue Therapien", "Diabetologie/Endokrinologie",
                 ["diabetes", "insulin", "hba1c", "glp-1"]),
    AwarenessDay(11, 17, "Deutsche Herzwoche", "Aufklärungswoche der Deutschen Herzstiftung", "Kardiologie",
                 ["herz", "heart", "herzwoche", "herzstiftung"]),
    AwarenessDay(12, 1, "Welt-AIDS-Tag", "HIV-Prävention und Therapie-Fortschritte", "Infektiologie",
                 ["hiv", "aids", "antiretroviral"]),
]

# ---------------------------------------------------------------------------
# Regulatory dates (recurring quarterly + annual)
# ---------------------------------------------------------------------------

REGULATORY_DATES: List[RegulatoryDate] = [
    RegulatoryDate(1, 1, "Neue EBM-Ziffern Q1", "Quartalsbeginn: Neue und geänderte EBM-Ziffern treten in Kraft", "EBM"),
    RegulatoryDate(1, 1, "Neue Rabattverträge Q1", "Neue Rabattverträge für häufig verordnete Wirkstoffe", "Rabattvertrag"),
    RegulatoryDate(4, 1, "Neue EBM-Ziffern Q2", "Quartalsbeginn: EBM-Anpassungen treten in Kraft", "EBM"),
    RegulatoryDate(4, 1, "Neue Rabattverträge Q2", "Aktualisierte Rabattverträge zum Quartalsbeginn", "Rabattvertrag"),
    RegulatoryDate(7, 1, "Neue EBM-Ziffern Q3", "Halbjahres-EBM-Update und AMNOG-Beschlüsse", "EBM"),
    RegulatoryDate(7, 1, "Halbjahres-AMNOG-Beschlüsse", "G-BA-Beschlüsse zur Nutzenbewertung treten in Kraft", "AMNOG"),
    RegulatoryDate(10, 1, "Neue EBM-Ziffern Q4", "Herbst-EBM-Update zum Quartalsbeginn", "EBM"),
    RegulatoryDate(10, 1, "Neue Rabattverträge Q4", "Aktualisierte Rabattverträge zum Quartalsbeginn", "Rabattvertrag"),
]


# ---------------------------------------------------------------------------
# Saisonal query functions
# ---------------------------------------------------------------------------

def get_topic_relevance(topic: SeasonalTopic, month: int) -> str:
    """Return 'peak', 'active', or 'off' for a topic in a given month."""
    if month in topic.peak_months:
        return "peak"
    if month in topic.months_active:
        return "active"
    return "off"


def get_cluster_status(cluster: TopicCluster, month: int) -> str:
    """Return the highest relevance status of any topic in the cluster."""
    statuses = [get_topic_relevance(t, month) for t in cluster.topics]
    if "peak" in statuses:
        return "peak"
    if "active" in statuses:
        return "active"
    return "off"


def get_seasonal_hero(month: int = 0, days_back: int = 7) -> dict:
    """Return hero section data for the Saisonal tab.

    Returns dict with: month, year, month_name, active_topics, peak_topics,
    total_articles_7d, active_cluster_count.
    """
    if month == 0:
        month = date.today().month
    year = date.today().year

    _MONTH_NAMES = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April",
        5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
    }

    active_topics: list[dict] = []
    peak_topics: list[dict] = []
    total_articles = 0
    active_clusters = set()

    for cluster in TOPIC_CLUSTERS:
        for topic in cluster.topics:
            relevance = get_topic_relevance(topic, month)
            if relevance == "off":
                continue

            article_count = _count_related_articles(topic.name_de, "", days_back=days_back)
            total_articles += article_count
            active_clusters.add(cluster.id)

            entry = {
                "id": topic.id,
                "name_de": topic.name_de,
                "icon": topic.icon,
                "cluster_id": cluster.id,
                "cluster_color": cluster.color,
                "cluster_color_light": cluster.color_light,
                "relevance": relevance,
                "article_count": article_count,
            }
            active_topics.append(entry)
            if relevance == "peak":
                peak_topics.append(entry)

    return {
        "month": month,
        "year": year,
        "month_name": _MONTH_NAMES.get(month, str(month)),
        "active_topics": active_topics,
        "peak_topics": peak_topics,
        "total_articles_7d": total_articles,
        "active_count": len(active_topics),
        "peak_count": len(peak_topics),
        "active_cluster_count": len(active_clusters),
    }


def get_timeline_data(year: int = 0) -> list[dict]:
    """Return 12-month timeline data for the Gantt visualization.

    Each month entry contains: month, month_name, is_current, topics list
    with (topic_id, name, cluster_color, relevance).
    """
    if year == 0:
        year = date.today().year
    current_month = date.today().month

    _MONTH_SHORT = {
        1: "Jan", 2: "Feb", 3: "Mär", 4: "Apr", 5: "Mai", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez",
    }

    months = []
    for m in range(1, 13):
        topics = []
        for cluster in TOPIC_CLUSTERS:
            for topic in cluster.topics:
                rel = get_topic_relevance(topic, m)
                if rel != "off":
                    topics.append({
                        "topic_id": topic.id,
                        "name_de": topic.name_de,
                        "cluster_id": cluster.id,
                        "cluster_color": cluster.color,
                        "relevance": rel,
                    })

        months.append({
            "month": m,
            "month_short": _MONTH_SHORT[m],
            "is_current": m == current_month,
            "topic_count": len(topics),
            "topics": topics,
        })
    return months


def get_cluster_cards(month: int = 0) -> list[dict]:
    """Return cluster card data for the given month.

    Each cluster: id, name_de, icon, color, color_light, status,
    topics (with individual status), total_article_count.
    """
    if month == 0:
        month = date.today().month

    cards = []
    for cluster in TOPIC_CLUSTERS:
        cluster_status = get_cluster_status(cluster, month)
        total_articles = 0
        topic_entries = []

        for topic in cluster.topics:
            rel = get_topic_relevance(topic, month)
            article_count = _count_related_articles(topic.name_de, "", days_back=30) if rel != "off" else 0
            total_articles += article_count
            topic_entries.append({
                "id": topic.id,
                "name_de": topic.name_de,
                "icon": topic.icon,
                "relevance": rel,
                "article_count": article_count,
                "search_keys": topic.search_keys,
            })

        # Collect all search keys for the cluster
        all_search_keys = []
        for t in cluster.topics:
            if get_topic_relevance(t, month) != "off":
                all_search_keys.extend(t.search_keys[:2])

        cards.append({
            "id": cluster.id,
            "name_de": cluster.name_de,
            "icon": cluster.icon,
            "color": cluster.color,
            "color_light": cluster.color_light,
            "status": cluster_status,
            "topics": topic_entries,
            "total_article_count": total_articles,
            "search_query": " ".join(all_search_keys[:4]),
        })

    return cards


def get_upcoming_awareness(days_ahead: int = 90) -> list[dict]:
    """Return upcoming awareness days within the next N days."""
    today = date.today()
    year = today.year
    results = []

    for ad in AWARENESS_DAYS:
        try:
            ad_date = date(year, ad.month, ad.day)
        except ValueError:
            continue
        # If past this year, check next year
        if ad_date < today:
            ad_date = date(year + 1, ad.month, ad.day)

        days_until = (ad_date - today).days
        if days_until > days_ahead:
            continue

        article_count = _count_related_articles(ad.name_de, ad.specialty, days_back=30)

        results.append({
            "date": ad_date.isoformat(),
            "date_formatted": f"{ad.day}. {_month_name(ad.month)}",
            "name_de": ad.name_de,
            "description_de": ad.description_de,
            "specialty": ad.specialty,
            "days_until": days_until,
            "article_count": article_count,
            "search_keys": ad.search_keys,
        })

    results.sort(key=lambda x: x["days_until"])
    return results


def get_upcoming_regulatory(days_ahead: int = 90) -> list[dict]:
    """Return upcoming regulatory dates within the next N days."""
    today = date.today()
    year = today.year
    results = []

    for rd in REGULATORY_DATES:
        try:
            rd_date = date(year, rd.month, rd.day)
        except ValueError:
            continue
        if rd_date < today:
            rd_date = date(year + 1, rd.month, rd.day)

        days_until = (rd_date - today).days
        if days_until > days_ahead:
            continue

        results.append({
            "date": rd_date.isoformat(),
            "date_formatted": f"{rd.day}. {_month_name(rd.month)} {rd_date.year}",
            "title_de": rd.title_de,
            "description_de": rd.description_de,
            "category": rd.category,
            "days_until": days_until,
        })

    results.sort(key=lambda x: x["days_until"])
    return results


def get_4week_forecast() -> list[dict]:
    """Return a 4-week lookahead of upcoming seasonal topics with actions.

    Each entry: {week_label, topics: [{name, icon, cluster, color, status,
    action_de, article_count}]}. Topics are grouped by week and sorted by
    relevance (peak first, then active).
    """
    today = date.today()
    results = []

    for week_offset in range(4):
        week_start = today + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)
        target_month = week_start.month

        if week_offset == 0:
            week_label = "Diese Woche"
        elif week_offset == 1:
            week_label = "Nächste Woche"
        else:
            week_label = f"In {week_offset} Wochen ({week_start.strftime('%d.%m.')}–{week_end.strftime('%d.%m.')})"

        topics = []
        for cluster in TOPIC_CLUSTERS:
            for topic in cluster.topics:
                rel = get_topic_relevance(topic, target_month)
                if rel == "off":
                    continue

                # Check if topic is about to start (next month = peak start)
                next_month = target_month + 1 if target_month < 12 else 1
                next_rel = get_topic_relevance(topic, next_month)
                is_upcoming = rel == "active" and next_rel == "peak"

                # Generate concrete action
                if rel == "peak":
                    action = f"Peak-Phase: Artikel zu {topic.name_de} jetzt veröffentlichen"
                elif is_upcoming:
                    action = f"Vorbereiten: {topic.name_de} erreicht bald Peak-Phase"
                else:
                    action = f"Beobachten: {topic.name_de} ist aktiv"

                article_count = _count_related_articles(topic.name_de, "", days_back=14)

                topics.append({
                    "id": topic.id,
                    "name_de": topic.name_de,
                    "icon": topic.icon,
                    "cluster_name": cluster.name_de,
                    "cluster_color": cluster.color,
                    "relevance": rel,
                    "is_upcoming": is_upcoming,
                    "action_de": action,
                    "article_count": article_count,
                    "search_keys": topic.search_keys[:3],
                })

        # Sort: peak first, then upcoming, then active
        topics.sort(key=lambda t: (
            0 if t["relevance"] == "peak" else (1 if t["is_upcoming"] else 2),
            -t["article_count"],
        ))

        # Limit to top 5 per week to keep it focused
        results.append({
            "week_label": week_label,
            "week_start": week_start.isoformat(),
            "topics": topics[:5],
        })

    return results


def _month_name(month: int) -> str:
    """Return German month name."""
    return {
        1: "Januar", 2: "Februar", 3: "März", 4: "April",
        5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
    }.get(month, str(month))

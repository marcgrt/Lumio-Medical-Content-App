"""Redaktionskalender — Intelligente Themenplanung für die Redaktion."""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional
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
    count = 0
    try:
        with get_session() as session:
            for term in search_terms:
                pattern = f"%{term}%"
                stmt = (
                    select(func.count())
                    .select_from(Article)
                    .where(
                        Article.pub_date >= cutoff,
                        Article.title.ilike(pattern),  # type: ignore[union-attr]
                    )
                )
                result = session.exec(stmt).one()
                count += result
            # Deduplicate roughly: if multiple terms matched, articles may overlap
            # Use conservative estimate
            if len(search_terms) > 1:
                count = max(1, count // len(search_terms)) if count > 0 else 0
    except Exception as exc:
        logger.debug("Error counting related articles for '%s': %s", topic, exc)
        return 0

    return count


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

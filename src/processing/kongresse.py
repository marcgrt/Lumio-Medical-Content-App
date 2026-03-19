"""Kongresse — Datenlogik fuer den Kongressplan-Tab."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import select, func
from src.models import Article, get_session

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "kongresse_2026.json"


@dataclass
class Congress:
    """Einzelner Kongress mit allen Metadaten."""
    id: str
    name: str
    short: str
    date_start: date
    date_end: date
    city: str
    country: str
    venue: str
    website: str
    specialty: str
    congress_type: str  # "national" | "international"
    cme_points: Optional[int]
    estimated_attendees: int
    abstract_deadline: Optional[date]
    registration_deadline: Optional[date]
    description_de: str
    keywords: list[str] = field(default_factory=list)
    related_article_count: int = 0

    @property
    def days_until(self) -> int:
        """Tage bis zum Kongressbeginn (negativ = bereits vorbei)."""
        return (self.date_start - date.today()).days

    @property
    def duration_days(self) -> int:
        return (self.date_end - self.date_start).days + 1

    @property
    def is_upcoming(self) -> bool:
        return self.date_start >= date.today()

    @property
    def is_running(self) -> bool:
        return self.date_start <= date.today() <= self.date_end

    @property
    def is_past(self) -> bool:
        return self.date_end < date.today()

    @property
    def abstract_deadline_passed(self) -> bool:
        if not self.abstract_deadline:
            return True
        return self.abstract_deadline < date.today()

    @property
    def days_until_abstract_deadline(self) -> Optional[int]:
        if not self.abstract_deadline:
            return None
        return (self.abstract_deadline - date.today()).days

    @property
    def status(self) -> str:
        """'running' | 'upcoming' | 'past'."""
        if self.is_running:
            return "running"
        if self.is_upcoming:
            return "upcoming"
        return "past"

    @property
    def month_key(self) -> str:
        """'2026-03' etc."""
        return self.date_start.strftime("%Y-%m")

    def to_ics(self) -> str:
        """Generiere iCalendar-Event."""
        uid = f"{self.id}@lumio"
        dtstart = self.date_start.strftime("%Y%m%d")
        dtend = (self.date_end + timedelta(days=1)).strftime("%Y%m%d")
        now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        summary = f"{self.short} — {self.name}"
        location = f"{self.venue}, {self.city}, {self.country}"
        desc = self.description_de
        if self.cme_points:
            desc += f"\\nCME: {self.cme_points} Punkte"
        if self.website:
            desc += f"\\nWebsite: {self.website}"

        lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"DTEND;VALUE=DATE:{dtend}",
            f"SUMMARY:{summary}",
            f"LOCATION:{location}",
            f"DESCRIPTION:{desc}",
            f"URL:{self.website}",
            "END:VEVENT",
        ]
        return "\r\n".join(lines)


def _load_raw() -> list[dict]:
    """Load raw JSON data."""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load congress data from %s: %s", _DATA_FILE, exc)
        return []


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _count_related_articles(keywords: list[str], days_back: int = 60) -> int:
    """Zaehle Artikel in der DB die zu Kongress-Keywords passen."""
    if not keywords:
        return 0
    cutoff = date.today() - timedelta(days=days_back)
    count = 0
    try:
        with get_session() as session:
            for kw in keywords[:4]:  # max 4 keywords to limit queries
                pattern = f"%{kw}%"
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
            if len(keywords) > 1 and count > 0:
                count = max(1, count // min(len(keywords), 4))
    except Exception as exc:
        logger.debug("Error counting articles for congress keywords: %s", exc)
        return 0
    return count


def load_congresses(with_articles: bool = True) -> list[Congress]:
    """Lade alle Kongresse aus JSON und reichere mit DB-Daten an."""
    raw = _load_raw()
    congresses = []
    for item in raw:
        try:
            c = Congress(
                id=item["id"],
                name=item["name"],
                short=item["short"],
                date_start=_parse_date(item["date_start"]),  # type: ignore
                date_end=_parse_date(item["date_end"]),  # type: ignore
                city=item["city"],
                country=item["country"],
                venue=item.get("venue", ""),
                website=item.get("website", ""),
                specialty=item["specialty"],
                congress_type=item.get("type", "international"),
                cme_points=item.get("cme_points"),
                estimated_attendees=item.get("estimated_attendees", 0),
                abstract_deadline=_parse_date(item.get("abstract_deadline")),
                registration_deadline=_parse_date(item.get("registration_deadline")),
                description_de=item.get("description_de", ""),
                keywords=item.get("keywords", []),
            )
            if with_articles:
                c.related_article_count = _count_related_articles(c.keywords)
            congresses.append(c)
        except Exception as exc:
            logger.warning("Skipping congress entry: %s", exc)
            continue

    congresses.sort(key=lambda c: c.date_start)
    return congresses


def get_next_congress(congresses: list[Congress]) -> Optional[Congress]:
    """Naechster anstehender Kongress (oder aktuell laufender)."""
    for c in congresses:
        if c.is_running:
            return c
        if c.is_upcoming:
            return c
    return None


def get_congresses_by_month(congresses: list[Congress]) -> dict[str, list[Congress]]:
    """Gruppiere Kongresse nach Monat."""
    from collections import defaultdict
    by_month: dict[str, list[Congress]] = defaultdict(list)
    for c in congresses:
        by_month[c.month_key].append(c)
    return dict(by_month)


def get_specialties(congresses: list[Congress]) -> list[str]:
    """Alle Fachgebiete (sortiert)."""
    specs = sorted({c.specialty for c in congresses})
    return specs


def get_countries(congresses: list[Congress]) -> list[str]:
    """Alle Laender (sortiert)."""
    return sorted({c.country for c in congresses})


def generate_ics_calendar(congresses: list[Congress]) -> str:
    """Generiere kompletten iCalendar-String."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lumio//Kongressplan//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Lumio Kongressplan 2026",
    ]
    for c in congresses:
        lines.append(c.to_ics())
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def get_upcoming_deadlines(congresses: list[Congress], days_ahead: int = 60) -> list[Congress]:
    """Kongresse mit bald ablaufender Abstract-Deadline."""
    result = []
    for c in congresses:
        dl = c.days_until_abstract_deadline
        if dl is not None and 0 < dl <= days_ahead:
            result.append(c)
    result.sort(key=lambda c: c.abstract_deadline or date.max)
    return result

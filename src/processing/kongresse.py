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

# Static city→coordinates lookup (no geocoding API needed)
_CITY_COORDS: dict[tuple[str, str], tuple[float, float]] = {
    ("Barcelona", "Spanien"): (41.389, 2.159),
    ("Berlin", "Deutschland"): (52.520, 13.405),
    ("Boston", "USA"): (42.360, -71.059),
    ("Chicago", "USA"): (41.878, -87.630),
    ("Düsseldorf", "Deutschland"): (51.227, 6.774),
    ("Florenz", "Italien"): (43.770, 11.249),
    ("Frankfurt", "Deutschland"): (50.111, 8.682),
    ("Hamburg", "Deutschland"): (53.551, 9.994),
    ("Heidelberg", "Deutschland"): (49.399, 8.672),
    ("Helsinki", "Finnland"): (60.170, 24.941),
    ("Kopenhagen", "Dänemark"): (55.676, 12.568),
    ("Leipzig", "Deutschland"): (51.340, 12.375),
    ("Lübeck", "Deutschland"): (53.866, 10.687),
    ("Madrid", "Spanien"): (40.417, -3.704),
    ("Mannheim", "Deutschland"): (49.489, 8.467),
    ("München", "Deutschland"): (48.137, 11.576),
    ("New Orleans", "USA"): (29.951, -90.072),
    ("Orlando", "USA"): (28.538, -81.379),
    ("Riyadh", "Saudi-Arabien"): (24.713, 46.675),
    ("Rom", "Italien"): (41.903, 12.496),
    ("Rostock", "Deutschland"): (54.089, 12.140),
    ("Salzburg", "Österreich"): (47.810, 13.055),
    ("San Antonio", "USA"): (29.425, -98.494),
    ("San Diego", "USA"): (32.716, -117.161),
    ("San Francisco", "USA"): (37.775, -122.419),
    ("Valencia", "Spanien"): (39.470, -0.376),
    ("Washington D.C.", "USA"): (38.908, -77.036),
    ("Wien", "Österreich"): (48.208, 16.373),
    ("Wiesbaden", "Deutschland"): (50.083, 8.240),
    ("Würzburg", "Deutschland"): (49.794, 9.929),
}


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

    @property
    def lat(self) -> Optional[float]:
        coords = _CITY_COORDS.get((self.city, self.country))
        return coords[0] if coords else None

    @property
    def lon(self) -> Optional[float]:
        coords = _CITY_COORDS.get((self.city, self.country))
        return coords[1] if coords else None

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
    """Zaehle Artikel per ILIKE auf title (präziser als FTS5 über 9 Felder)."""
    if not keywords:
        return 0
    cutoff = date.today() - timedelta(days=days_back)
    try:
        with get_session() as session:
            from sqlalchemy import or_
            conditions = [
                Article.title.ilike(f"%{kw}%")  # type: ignore[union-attr]
                for kw in keywords[:4]
            ]
            stmt = (
                select(func.count(Article.id.distinct()))
                .select_from(Article)
                .where(Article.pub_date >= cutoff, or_(*conditions))
            )
            return session.exec(stmt).one()
    except Exception as exc:
        logger.debug("Error counting articles for congress keywords: %s", exc)
        return 0


def get_related_article_ids(keywords: list[str], days_back: int = 60) -> list[int]:
    """Hole Artikel-IDs per ILIKE auf title — identisch zur Count-Logik."""
    if not keywords:
        return []
    cutoff = date.today() - timedelta(days=days_back)
    try:
        with get_session() as session:
            from sqlalchemy import or_
            conditions = [
                Article.title.ilike(f"%{kw}%")  # type: ignore[union-attr]
                for kw in keywords[:4]
            ]
            stmt = (
                select(Article.id)
                .where(Article.pub_date >= cutoff, or_(*conditions))
                .distinct()
            )
            return list(session.exec(stmt))
    except Exception as exc:
        logger.debug("Error fetching article IDs for congress keywords: %s", exc)
        return []


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
            congresses.append(c)
        except Exception as exc:
            logger.warning("Skipping congress entry: %s", exc)
            continue

    # Batch-count related articles (1 query instead of N)
    if with_articles:
        _batch_count_related_articles(congresses)

    congresses.sort(key=lambda c: c.date_start)
    return congresses


def _batch_count_related_articles(congresses: list) -> None:
    """Count related articles for all congresses in a single DB query."""
    cutoff = date.today() - timedelta(days=60)
    try:
        with get_session() as session:
            from sqlalchemy import or_
            # Collect ALL keywords from all congresses
            all_conditions = []
            for c in congresses:
                kws = c.keywords[:4] if c.keywords else []
                for kw in kws:
                    all_conditions.append(Article.title.ilike(f"%{kw}%"))

            if not all_conditions:
                for c in congresses:
                    c.related_article_count = 0
                return

            # Get all matching article IDs + titles in one query
            matching = session.exec(
                select(Article.id, Article.title)
                .where(Article.pub_date >= cutoff, or_(*all_conditions))
            ).all()

            # Build a title lookup for per-congress counting
            for c in congresses:
                kws = [kw.lower() for kw in (c.keywords[:4] if c.keywords else [])]
                if not kws:
                    c.related_article_count = 0
                    continue
                count = 0
                for aid, title in matching:
                    t = (title or "").lower()
                    if any(kw in t for kw in kws):
                        count += 1
                c.related_article_count = count
    except Exception as exc:
        logger.debug("Batch article count failed: %s", exc)
        for c in congresses:
            c.related_article_count = 0


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


# ---------------------------------------------------------------------------
# Favoriten
# ---------------------------------------------------------------------------

def get_favorite_ids(user_id: int = 1) -> set[str]:
    """Alle favorisierten Kongress-IDs fuer einen User."""
    from src.models import CongressFavorite
    try:
        with get_session() as session:
            stmt = select(CongressFavorite.congress_id).where(
                CongressFavorite.user_id == user_id
            )
            return set(session.exec(stmt).all())
    except Exception as exc:
        logger.debug("Error loading congress favorites: %s", exc)
        return set()


def toggle_favorite(congress_id: str, user_id: int = 1) -> bool:
    """Toggle Favorit. Gibt True zurueck wenn jetzt favorisiert, False wenn entfernt."""
    from src.models import CongressFavorite
    with get_session() as session:
        stmt = select(CongressFavorite).where(
            CongressFavorite.user_id == user_id,
            CongressFavorite.congress_id == congress_id,
        )
        existing = session.exec(stmt).first()
        if existing:
            session.delete(existing)
            session.commit()
            return False
        else:
            fav = CongressFavorite(user_id=user_id, congress_id=congress_id)
            session.add(fav)
            session.commit()
            return True


# ---------------------------------------------------------------------------
# Ueberlappungs-Erkennung
# ---------------------------------------------------------------------------

def detect_overlaps(congresses: list[Congress]) -> list[tuple[Congress, Congress]]:
    """Finde ueberlappende Kongresse."""
    overlaps = []
    upcoming = [c for c in congresses if c.status != "past"]
    for i, a in enumerate(upcoming):
        for b in upcoming[i + 1:]:
            if a.date_start <= b.date_end and b.date_start <= a.date_end:
                overlaps.append((a, b))
    return overlaps


# ---------------------------------------------------------------------------
# Kongress-Watchlist
# ---------------------------------------------------------------------------

def create_congress_watchlist(congress_id: str) -> int | None:
    """Erstelle eine Watchlist basierend auf Kongress-Keywords. Gibt Watchlist-ID zurueck."""
    from src.models import Watchlist
    raw = _load_raw()
    item = next((r for r in raw if r["id"] == congress_id), None)
    if not item:
        return None
    keywords = item.get("keywords", [])
    name = f"Kongress: {item.get('short', item['name'])}"
    specialty = item.get("specialty")
    with get_session() as session:
        # Check if already exists
        stmt = select(Watchlist).where(Watchlist.name == name)
        existing = session.exec(stmt).first()
        if existing:
            return existing.id
        wl = Watchlist(
            name=name,
            keywords=", ".join(keywords),
            specialty_filter=specialty,
            active=True,
        )
        session.add(wl)
        session.commit()
        session.refresh(wl)
        return wl.id


# ---------------------------------------------------------------------------
# Redaktionsplan-Integration
# ---------------------------------------------------------------------------

def add_congress_to_editorial(congress_id: str) -> int | None:
    """Fuege einen Kongress als Thema in den Redaktionsplan ein."""
    from src.models import EditorialTopic
    raw = _load_raw()
    item = next((r for r in raw if r["id"] == congress_id), None)
    if not item:
        return None
    ds = _parse_date(item["date_start"])
    if not ds:
        return None
    # Plan topic 7 days before congress starts
    planned = ds - timedelta(days=7)
    if planned < date.today():
        planned = date.today()
    title = f"Kongress-Vorbereitung: {item.get('short', item['name'])}"
    with get_session() as session:
        # Check if already exists
        stmt = select(EditorialTopic).where(EditorialTopic.congress_id == congress_id)
        existing = session.exec(stmt).first()
        if existing:
            return existing.id
        topic = EditorialTopic(
            title=title,
            description=f"Artikel-Vorbereitung für {item['name']} ({item['date_start']} bis {item['date_end']}, {item['city']})",
            planned_date=planned,
            congress_id=congress_id,
            specialty=item.get("specialty"),
        )
        session.add(topic)
        session.commit()
        session.refresh(topic)
        return topic.id


def get_editorial_topics(upcoming_only: bool = True) -> list[dict]:
    """Lade alle Redaktionsplan-Themen."""
    from src.models import EditorialTopic
    try:
        with get_session() as session:
            stmt = select(EditorialTopic).order_by(EditorialTopic.planned_date)
            if upcoming_only:
                stmt = stmt.where(EditorialTopic.planned_date >= date.today())
            results = session.exec(stmt).all()
            return [
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "planned_date": t.planned_date.isoformat(),
                    "congress_id": t.congress_id,
                    "specialty": t.specialty,
                    "status": t.status,
                }
                for t in results
            ]
    except Exception as exc:
        logger.debug("Error loading editorial topics: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Karten-GeoJSON
# ---------------------------------------------------------------------------

def build_map_geojson(congresses: list[Congress], favorites: set[str] | None = None) -> str:
    """Konvertiere Kongress-Liste zu GeoJSON fuer Leaflet."""
    favorites = favorites or set()
    features = []
    for c in congresses:
        if c.lat is None or c.lon is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
            "properties": {
                "id": c.id,
                "name": c.name,
                "short": c.short,
                "city": c.city,
                "country": c.country,
                "specialty": c.specialty,
                "date_start": c.date_start.isoformat(),
                "date_end": c.date_end.isoformat(),
                "status": c.status,
                "cme": c.cme_points or 0,
                "attendees": c.estimated_attendees,
                "articles": c.related_article_count,
                "website": c.website,
                "is_fav": c.id in favorites,
                "congress_type": c.congress_type,
            },
        })
    return json.dumps({"type": "FeatureCollection", "features": features})

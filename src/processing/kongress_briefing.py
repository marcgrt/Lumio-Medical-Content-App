"""Kongress-Briefing — KI-generiertes 1-Seiten-Briefing vor einem Kongress.

Generates a structured briefing based on recent articles matching the
congress keywords. Pattern follows artikel_entwurf.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from html import escape as _esc
from typing import Optional

from src.config import get_provider_chain
from src.llm_client import cached_chat_completion

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Du bist ein medizinischer Kongressexperte, der Aerzte auf bevorstehende Kongresse vorbereitet.
Erstelle ein kompaktes, strukturiertes Briefing basierend auf den aktuellsten Artikeln zum Thema.

Schreibe auf Deutsch, praezise, informativ, mit klarem Praxisbezug.
Zielgruppe: Praktizierende Aerzte, die sich effizient vorbereiten wollen.

Antworte EXAKT in diesem Format:

KONTEXT:
[2-3 Saetze: Was ist der Kongress, warum ist er wichtig, was erwartet die Teilnehmer]
;;;
TOP_THEMEN:
- [Thema 1: Kurze Beschreibung des heissesten Themas]
- [Thema 2: Weiteres aktuelles Thema]
- [Thema 3: Drittes relevantes Thema]
- [Optional: Thema 4-5]
;;;
KONTROVERSEN:
- [Aktuelle Debatte 1 im Fachgebiet]
- [Aktuelle Debatte 2 — falls vorhanden]
;;;
STUDIEN_HIGHLIGHTS:
- [Wichtigste neue Studie 1: Titel + Kernaussage]
- [Wichtigste neue Studie 2: Titel + Kernaussage]
- [Wichtigste neue Studie 3: Titel + Kernaussage]
;;;
PRAXIS_VORSCHAU:
[2-3 Saetze: Was koennte sich fuer die klinische Praxis aendern? Welche Themen sollte man im Blick behalten?]
"""


@dataclass
class KongressBriefing:
    """Structured congress briefing."""
    congress_name: str
    congress_short: str
    kontext: str = ""
    top_themen: list[str] = field(default_factory=list)
    kontroversen: list[str] = field(default_factory=list)
    studien_highlights: list[str] = field(default_factory=list)
    praxis_vorschau: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    model_used: str = ""
    article_count: int = 0


def _get_related_articles(keywords: list[str], days_back: int = 60, limit: int = 30) -> list:
    """Fetch recent articles matching congress keywords."""
    from src.models import Article, get_engine, get_session
    from sqlmodel import select, col, or_

    get_engine()
    cutoff = date.today() - timedelta(days=days_back)

    with get_session() as session:
        conditions = []
        for kw in keywords:
            kw_lower = kw.lower()
            conditions.append(col(Article.title).ilike(f"%{kw_lower}%"))
            conditions.append(col(Article.abstract).ilike(f"%{kw_lower}%"))

        if not conditions:
            return []

        stmt = (
            select(Article)
            .where(or_(*conditions))
            .where(Article.pub_date >= cutoff)
            .order_by(col(Article.relevance_score).desc())
            .limit(limit)
        )
        return session.exec(stmt).all()


def _build_prompt(congress: dict, articles: list) -> str:
    """Build the user prompt with congress info and article summaries."""
    name = congress.get("name", "")
    short = congress.get("short", "")
    specialty = congress.get("specialty", "")
    city = congress.get("city", "")
    country = congress.get("country", "")
    date_start = congress.get("date_start", "")
    date_end = congress.get("date_end", "")
    description = congress.get("description_de", "")
    cme = congress.get("cme_points", "")
    attendees = congress.get("estimated_attendees", "")

    prompt = f"""Erstelle ein Kongress-Briefing fuer:

Kongress: {name} ({short})
Fachgebiet: {specialty}
Datum: {date_start} bis {date_end}
Ort: {city}, {country}
Teilnehmer: ca. {attendees}
CME-Punkte: {cme or 'k.A.'}
Beschreibung: {description}

Hier sind die {len(articles)} aktuellsten Artikel zum Thema:\n\n"""

    for i, a in enumerate(articles[:25], 1):
        score = a.relevance_score or 0
        title = (a.title or "")[:120]
        journal = a.journal or a.source or ""
        summary = ""
        if a.summary_de:
            parts = a.summary_de.split(";;;")
            kern = parts[0].replace("KERN:", "").strip() if parts else ""
            summary = kern[:200]
        prompt += f"{i}. [{score:.0f}] {title} ({journal})\n"
        if summary:
            prompt += f"   {summary}\n"

    return prompt


def _parse_briefing(raw: str, congress: dict) -> KongressBriefing:
    """Parse the LLM response into a structured briefing."""
    briefing = KongressBriefing(
        congress_name=congress.get("name", ""),
        congress_short=congress.get("short", ""),
    )

    sections = raw.split(";;;")
    for section in sections:
        section = section.strip()
        if section.startswith("KONTEXT:"):
            briefing.kontext = section[8:].strip()
        elif section.startswith("TOP_THEMEN:"):
            lines = section[11:].strip().splitlines()
            briefing.top_themen = [l.lstrip("- ").strip() for l in lines if l.strip().startswith("-")]
        elif section.startswith("KONTROVERSEN:"):
            lines = section[13:].strip().splitlines()
            briefing.kontroversen = [l.lstrip("- ").strip() for l in lines if l.strip().startswith("-")]
        elif section.startswith("STUDIEN_HIGHLIGHTS:"):
            lines = section[19:].strip().splitlines()
            briefing.studien_highlights = [l.lstrip("- ").strip() for l in lines if l.strip().startswith("-")]
        elif section.startswith("PRAXIS_VORSCHAU:"):
            briefing.praxis_vorschau = section[16:].strip()

    return briefing


def generate_congress_briefing(congress: dict) -> Optional[KongressBriefing]:
    """Generate a KI briefing for a congress.

    Args:
        congress: Congress dict from _cached_congresses().

    Returns:
        KongressBriefing or None on failure.
    """
    keywords = congress.get("keywords", [])
    if not keywords:
        # Fallback: use congress name words
        keywords = [w for w in congress.get("name", "").split() if len(w) > 3]

    articles = _get_related_articles(keywords, days_back=60, limit=30)
    if not articles:
        logger.warning("No articles found for congress %s", congress.get("short"))

    prompt = _build_prompt(congress, articles)
    providers = get_provider_chain("kongress_briefing") or get_provider_chain("article_draft")

    raw = cached_chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM_PROMPT,
        max_tokens=2048,
    )

    if not raw or "KONTEXT:" not in raw:
        logger.warning("Briefing generation failed for %s", congress.get("short"))
        return None

    briefing = _parse_briefing(raw, congress)
    briefing.article_count = len(articles)
    return briefing


def briefing_to_markdown(briefing: KongressBriefing) -> str:
    """Convert briefing to downloadable Markdown."""
    lines = [
        f"# Was Sie zum {briefing.congress_short} wissen muessen",
        f"*{briefing.congress_name}*",
        f"*Generiert am {briefing.generated_at.strftime('%d.%m.%Y')} "
        f"| Basierend auf {briefing.article_count} aktuellen Artikeln*",
        "",
    ]

    if briefing.kontext:
        lines += ["## Kontext", briefing.kontext, ""]

    if briefing.top_themen:
        lines += ["## Top-Themen"]
        for t in briefing.top_themen:
            lines.append(f"- {t}")
        lines.append("")

    if briefing.kontroversen:
        lines += ["## Aktuelle Kontroversen"]
        for k in briefing.kontroversen:
            lines.append(f"- {k}")
        lines.append("")

    if briefing.studien_highlights:
        lines += ["## Studien-Highlights"]
        for s in briefing.studien_highlights:
            lines.append(f"- {s}")
        lines.append("")

    if briefing.praxis_vorschau:
        lines += ["## Praxis-Vorschau", briefing.praxis_vorschau, ""]

    lines.append("---")
    lines.append("*Erstellt mit Lumio Medical Intelligence*")
    return "\n".join(lines)


def briefing_to_html(briefing: KongressBriefing) -> str:
    """Convert briefing to HTML for display in Streamlit."""

    def _bullets(items: list[str]) -> str:
        if not items:
            return ""
        return "".join(f'<li style="margin-bottom:4px">{_esc(item)}</li>' for item in items)

    sections = []

    if briefing.kontext:
        sections.append(
            f'<div style="font-size:0.85rem;color:var(--c-text-secondary);line-height:1.6;'
            f'margin-bottom:14px">{_esc(briefing.kontext)}</div>'
        )

    if briefing.top_themen:
        sections.append(
            f'<div style="margin-bottom:12px">'
            f'<div style="font-size:0.7rem;font-weight:700;color:var(--c-accent);'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Top-Themen</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:0.82rem;color:var(--c-text);'
            f'line-height:1.6">{_bullets(briefing.top_themen)}</ul></div>'
        )

    if briefing.kontroversen:
        sections.append(
            f'<div style="margin-bottom:12px">'
            f'<div style="font-size:0.7rem;font-weight:700;color:#f59e0b;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Kontroversen</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:0.82rem;color:var(--c-text);'
            f'line-height:1.6">{_bullets(briefing.kontroversen)}</ul></div>'
        )

    if briefing.studien_highlights:
        sections.append(
            f'<div style="margin-bottom:12px">'
            f'<div style="font-size:0.7rem;font-weight:700;color:#3b82f6;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Studien-Highlights</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:0.82rem;color:var(--c-text);'
            f'line-height:1.6">{_bullets(briefing.studien_highlights)}</ul></div>'
        )

    if briefing.praxis_vorschau:
        sections.append(
            f'<div style="padding:10px 14px;border-left:2px solid var(--c-accent);'
            f'border-radius:0 8px 8px 0;background:rgba(132,204,22,0.04);margin-top:8px">'
            f'<div style="font-size:0.7rem;font-weight:700;color:var(--c-accent);'
            f'margin-bottom:4px">Praxis-Vorschau</div>'
            f'<div style="font-size:0.82rem;color:var(--c-text);line-height:1.6">'
            f'{_esc(briefing.praxis_vorschau)}</div></div>'
        )

    header = (
        f'<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:10px">'
        f'Basierend auf {briefing.article_count} Artikeln der letzten 60 Tage</div>'
    )

    return header + "\n".join(sections)

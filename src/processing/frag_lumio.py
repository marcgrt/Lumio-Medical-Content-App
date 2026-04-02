"""Frag Lumio — Natürlichsprachliche Recherche über die Artikel-Datenbank."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import select, col, or_
from src.models import Article, get_session, fts5_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# German time expressions → days_back / date range
# ---------------------------------------------------------------------------
_TIME_PATTERNS: list[tuple[str, int]] = [
    (r"\bgestern\b", 1),
    (r"\bheute\b", 0),
    (r"\bdiese[rn]?\s+woche\b", 7),
    (r"\bletzte[rn]?\s+woche\b", 7),
    (r"\bdiese[rn]?\s+monat\b", 30),
    (r"\bletzte[rn]?\s+monat\b", 30),
    (r"\bletzte[rn]?\s+(\d+)\s+tage?\b", -1),  # group(1) = N
    (r"\bletzte[rn]?\s+(\d+)\s+wochen?\b", -2),  # group(1) = N weeks
    (r"\bletzte[rn]?\s+(\d+)\s+monate?\b", -3),  # group(1) = N months
    (r"\bdieses\s+jahr\b", 365),
    (r"\bletztes\s+jahr\b", 365),
]

_MONTH_MAP = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}

# Study type keywords (German + English)
_STUDY_TYPE_MAP: dict[str, str] = {
    "rct": "RCT",
    "randomisiert": "RCT",
    "randomized": "RCT",
    "meta-analyse": "Meta-Analyse",
    "meta-analysis": "Meta-Analyse",
    "metaanalyse": "Meta-Analyse",
    "systematic review": "Systematischer Review",
    "systematischer review": "Systematischer Review",
    "systematische übersicht": "Systematischer Review",
    "leitlinie": "Leitlinie",
    "guideline": "Leitlinie",
    "kohortenstudie": "Kohortenstudie",
    "cohort": "Kohortenstudie",
    "fallbericht": "Fallbericht",
    "case report": "Fallbericht",
}

# Specialty aliases (German colloquial → canonical SPECIALTY_MESH key)
_SPECIALTY_ALIASES: dict[str, str] = {
    "herz": "Kardiologie",
    "kardio": "Kardiologie",
    "kardiologie": "Kardiologie",
    "krebs": "Onkologie",
    "onko": "Onkologie",
    "onkologie": "Onkologie",
    "tumor": "Onkologie",
    "neuro": "Neurologie",
    "neurologie": "Neurologie",
    "gehirn": "Neurologie",
    "diabetes": "Diabetologie/Endokrinologie",
    "diabetologie": "Diabetologie/Endokrinologie",
    "endokrinologie": "Diabetologie/Endokrinologie",
    "lunge": "Pneumologie",
    "pneumologie": "Pneumologie",
    "magen": "Gastroenterologie",
    "darm": "Gastroenterologie",
    "gastro": "Gastroenterologie",
    "gastroenterologie": "Gastroenterologie",
    "leber": "Gastroenterologie",
    "infektion": "Infektiologie",
    "infektiologie": "Infektiologie",
    "antibiotika": "Infektiologie",
    "haut": "Dermatologie",
    "dermatologie": "Dermatologie",
    "psych": "Psychiatrie",
    "psychiatrie": "Psychiatrie",
    "depression": "Psychiatrie",
    "allgemeinmedizin": "Allgemeinmedizin",
    "hausarzt": "Allgemeinmedizin",
    "orthopädie": "Orthopädie",
    "knochen": "Orthopädie",
    "urologie": "Urologie",
    "pädiatrie": "Pädiatrie",
    "kinder": "Pädiatrie",
    "gynäkologie": "Gynäkologie",
    "frauenarzt": "Gynäkologie",
    "geburtshilfe": "Gynäkologie",
    "schwangerschaft": "Gynäkologie",
    "rheumatologie": "Rheumatologie",
    "rheuma": "Rheumatologie",
    "chirurgie": "Chirurgie",
    "operation": "Chirurgie",
    "nephrologie": "Nephrologie",
    "niere": "Nephrologie",
    "dialyse": "Nephrologie",
    "anästhesiologie": "Anästhesiologie",
    "narkose": "Anästhesiologie",
    "intensivmedizin": "Intensivmedizin",
    "intensiv": "Intensivmedizin",
    "hno": "HNO",
    "ohren": "HNO",
    "augenheilkunde": "Augenheilkunde",
    "augen": "Augenheilkunde",
    "geriatrie": "Geriatrie",
    "altersmedizin": "Geriatrie",
    "notfallmedizin": "Notfallmedizin",
    "notfall": "Notfallmedizin",
    "radiologie": "Radiologie",
    "bildgebung": "Radiologie",
    "palliativmedizin": "Palliativmedizin",
    "palliativ": "Palliativmedizin",
    "allergologie": "Allergologie",
    "allergie": "Allergologie",
}

# Words to strip from keyword extraction (German stop words + question words)
_STOP_WORDS = frozenset(
    "der die das ein eine eines einem einen einer zu zum zur und oder "
    "in im von vom für mit auf an aus bei über unter nach vor wie was "
    "welche welcher welches gibt es gab sind ist war hat haben wurde "
    "werden kann können neue neuen neuer neues aktuelle aktuellen "
    "aktueller letzten letzte letzter dieser diese dieses diesen "
    "diesem dazu darüber dabei welchem welchen top besten wichtigsten "
    "denn noch auch schon etwas viel viele mehr sehr nur etwa rund "
    "bereits alle allem allen aller alles mein dein sein ihr unser "
    "euer wir sie er du ich man nicht kein keine keinen keiner keinem "
    "studien studie artikel evidenz vergleich vergleiche zeige finde "
    "suche nenne liste zusammenfassung fassen fasse".split()
)


@dataclass
class LumioAntwort:
    """Structured answer from Frag Lumio."""
    answer_de: str
    sources: list[dict]
    query_interpretation: str
    search_stats: dict
    follow_up_suggestions: list[str]
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ask_lumio(question: str, max_sources: int = 10) -> LumioAntwort:
    """Process a natural language question against the article database."""
    # Step 1: Extract search intent
    params = _extract_search_params(question)
    logger.info("Frag Lumio — params: %s", params)

    # Step 2: Search the database
    articles = _search_articles(params, limit=max(max_sources * 3, 30))

    # Step 3: Build context + generate answer
    if not articles:
        return LumioAntwort(
            answer_de=(
                "Zu dieser Frage habe ich leider keine passenden Artikel "
                "in der Datenbank gefunden. Versuche es mit anderen "
                "Suchbegriffen oder einem weiteren Zeitraum."
            ),
            sources=[],
            query_interpretation=_format_interpretation(params),
            search_stats={"total_found": 0, "date_range": None, "specialties": []},
            follow_up_suggestions=_generate_follow_ups_no_results(question),
            generated_at=datetime.now(),
        )

    system_prompt, user_prompt = _build_answer_prompt(question, articles[:max_sources])

    # Step 4: Call LLM
    from src.config import get_provider_chain
    from src.llm_client import chat_completion

    providers = get_provider_chain("frag_lumio")
    raw = chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
        max_tokens=1500,
    )

    # Step 5: Parse response
    answer_text = raw.strip() if raw else (
        "Entschuldigung, ich konnte gerade keine Antwort generieren. "
        "Bitte versuche es erneut."
    )

    # Build source list
    sources = []
    for a in articles[:max_sources]:
        sources.append({
            "id": a.id,
            "title": a.title,
            "score": a.relevance_score,
            "journal": a.journal or "",
            "url": a.url or "",
            "pub_date": str(a.pub_date) if a.pub_date else "",
            "specialty": a.specialty or "",
        })

    # Collect stats
    specialties_found = list({a.specialty for a in articles if a.specialty})
    dates = [a.pub_date for a in articles if a.pub_date]
    date_range = None
    if dates:
        date_range = f"{min(dates)} – {max(dates)}"

    follow_ups = _generate_follow_ups(question, answer_text, articles)

    return LumioAntwort(
        answer_de=answer_text,
        sources=sources,
        query_interpretation=_format_interpretation(params),
        search_stats={
            "total_found": len(articles),
            "date_range": date_range,
            "specialties": specialties_found,
        },
        follow_up_suggestions=follow_ups,
        generated_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

def _extract_search_params(question: str) -> dict:
    """Extract search parameters from a German natural language question."""
    q_lower = question.lower().strip()

    # --- Time frame ---
    days_back = 30  # default
    date_from = None
    date_to = None

    for pattern, value in _TIME_PATTERNS:
        m = re.search(pattern, q_lower)
        if m:
            if value == -1:
                days_back = int(m.group(1))
            elif value == -2:
                days_back = int(m.group(1)) * 7
            elif value == -3:
                days_back = int(m.group(1)) * 30
            elif value == 0:
                days_back = 1
            else:
                days_back = value
            break

    # Explicit year: "2026", "2025"
    year_match = re.search(r"\b(20[2-3]\d)\b", q_lower)
    if year_match:
        year = int(year_match.group(1))
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        days_back = None

    # Explicit "Monat Jahr": "März 2026"
    for month_name, month_num in _MONTH_MAP.items():
        month_pat = rf"\b{month_name}\s+(20[2-3]\d)\b"
        mm = re.search(month_pat, q_lower)
        if mm:
            year = int(mm.group(1))
            date_from = date(year, month_num, 1)
            if month_num == 12:
                date_to = date(year, 12, 31)
            else:
                date_to = date(year, month_num + 1, 1) - timedelta(days=1)
            days_back = None
            break

    # If days_back is set (no explicit date range), compute date_from
    if days_back is not None:
        date_from = date.today() - timedelta(days=days_back)
        date_to = date.today()

    # --- Study types ---
    study_types = []
    for trigger, canonical in _STUDY_TYPE_MAP.items():
        if trigger in q_lower and canonical not in study_types:
            study_types.append(canonical)

    # --- Specialties ---
    specialties = []
    for alias, canonical in _SPECIALTY_ALIASES.items():
        if alias in q_lower and canonical not in specialties:
            specialties.append(canonical)

    # --- Keywords (everything not stop words / time / study type / specialty) ---
    # Tokenise, remove stop words and known patterns
    tokens = re.findall(r"[a-zäöüß0-9\-]+", q_lower)
    known_patterns = set()
    # Add all matched patterns to exclude
    for alias in _SPECIALTY_ALIASES:
        if alias in q_lower:
            known_patterns.update(alias.split())
    for trigger in _STUDY_TYPE_MAP:
        if trigger in q_lower:
            known_patterns.update(trigger.split("-"))
            known_patterns.update(trigger.split())
    for month_name in _MONTH_MAP:
        known_patterns.add(month_name)

    keywords = []
    for t in tokens:
        if (
            t not in _STOP_WORDS
            and t not in known_patterns
            and len(t) >= 3
            and not re.match(r"^20[2-3]\d$", t)
        ):
            keywords.append(t)

    # Deduplicate while preserving order
    seen = set()
    unique_kw = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_kw.append(kw)

    return {
        "keywords": unique_kw,
        "date_from": date_from,
        "date_to": date_to,
        "days_back": days_back,
        "study_types": study_types,
        "specialties": specialties,
        "original_question": question,
    }


def _format_interpretation(params: dict) -> str:
    """Format the extracted parameters as a human-readable interpretation."""
    parts = []
    if params["keywords"]:
        parts.append(f"Suchbegriffe: {', '.join(params['keywords'])}")
    if params["date_from"] and params["date_to"]:
        parts.append(f"Zeitraum: {params['date_from']} bis {params['date_to']}")
    elif params["days_back"] is not None:
        parts.append(f"Letzte {params['days_back']} Tage")
    if params["specialties"]:
        parts.append(f"Fachgebiete: {', '.join(params['specialties'])}")
    if params["study_types"]:
        parts.append(f"Studientypen: {', '.join(params['study_types'])}")
    return " | ".join(parts) if parts else "Allgemeine Suche"


# ---------------------------------------------------------------------------
# Database search
# ---------------------------------------------------------------------------

def _search_articles(params: dict, limit: int = 30) -> list[Article]:
    """Search articles based on extracted parameters."""
    keywords = params.get("keywords", [])
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    specialties = params.get("specialties", [])
    study_types = params.get("study_types", [])

    # Try FTS5 first if we have keywords
    fts_ids: list[int] = []
    if keywords:
        fts_query = " OR ".join(keywords)
        fts_ids = fts5_search(fts_query, limit=limit * 2)

    with get_session() as session:
        stmt = select(Article)

        if fts_ids:
            stmt = stmt.where(col(Article.id).in_(fts_ids))
        elif keywords:
            # Fallback: ILIKE search
            conditions = []
            for kw in keywords:
                pattern = f"%{kw}%"
                conditions.append(col(Article.title).ilike(pattern))
                conditions.append(col(Article.abstract).ilike(pattern))
                conditions.append(col(Article.summary_de).ilike(pattern))
            stmt = stmt.where(or_(*conditions))

        # Date range
        if date_from:
            stmt = stmt.where(Article.pub_date >= date_from)
        if date_to:
            stmt = stmt.where(Article.pub_date <= date_to)

        # Specialty filter
        if specialties:
            stmt = stmt.where(col(Article.specialty).in_(specialties))

        # Study type filter (from highlight_tags or study_type field)
        if study_types:
            type_conditions = []
            for st_ in study_types:
                type_conditions.append(col(Article.study_type).ilike(f"%{st_}%"))
                type_conditions.append(
                    col(Article.highlight_tags).contains(f"Studientyp: {st_}")
                )
            stmt = stmt.where(or_(*type_conditions))

        # Sort by relevance_score (unless FTS provides ranking)
        if not fts_ids:
            stmt = stmt.order_by(col(Article.relevance_score).desc())

        stmt = stmt.limit(limit)
        articles = session.exec(stmt).all()

        # Detach from session
        result = [a.detach() for a in articles]

    # Re-sort by FTS rank if applicable, then by score
    if fts_ids:
        id_rank = {aid: rank for rank, aid in enumerate(fts_ids)}
        result.sort(key=lambda a: id_rank.get(a.id, 999999))

    return result


# ---------------------------------------------------------------------------
# LLM prompt construction
# ---------------------------------------------------------------------------

def _build_answer_prompt(question: str, articles: list[Article]) -> tuple[str, str]:
    """Build system + user prompts for the LLM answer generation."""
    system_prompt = (
        "Du bist Lumio, ein KI-Recherche-Assistent für eine medizinische "
        "Fachredaktion. Du antwortest auf Deutsch basierend auf den Artikeln "
        "in deiner Datenbank.\n\n"
        "Regeln:\n"
        "- Antworte präzise und fachlich korrekt\n"
        "- Zitiere immer die Quellen mit [Titel, Journal]\n"
        "- Wenn die Evidenz begrenzt ist, sage das ehrlich\n"
        "- Strukturiere die Antwort mit Absätzen\n"
        "- Fasse die wichtigsten Erkenntnisse zusammen\n"
        "- Nenne am Ende die Evidenzqualität\n"
        "- Antworte immer auf Deutsch"
    )

    # Build article context
    article_context_parts = []
    for i, a in enumerate(articles, 1):
        parts = [f"[{i}] {a.title}"]
        if a.journal:
            parts.append(f"   Journal: {a.journal}")
        if a.pub_date:
            parts.append(f"   Datum: {a.pub_date}")
        if a.relevance_score:
            parts.append(f"   Score: {a.relevance_score:.0f}")
        if a.specialty:
            parts.append(f"   Fachgebiet: {a.specialty}")
        if a.study_type:
            parts.append(f"   Studientyp: {a.study_type}")
        if a.summary_de:
            # Use first 300 chars of summary
            snip = a.summary_de[:300]
            if len(a.summary_de) > 300:
                snip += "..."
            parts.append(f"   Zusammenfassung: {snip}")
        elif a.abstract:
            snip = a.abstract[:300]
            if len(a.abstract) > 300:
                snip += "..."
            parts.append(f"   Abstract: {snip}")
        article_context_parts.append("\n".join(parts))

    article_context = "\n\n".join(article_context_parts)

    user_prompt = (
        f"Frage: {question}\n\n"
        f"--- Artikel in der Datenbank ({len(articles)} Treffer) ---\n\n"
        f"{article_context}\n\n"
        f"Beantworte die Frage basierend auf diesen Artikeln. "
        f"Zitiere die Quellen als [Nummer]."
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Follow-up suggestions
# ---------------------------------------------------------------------------

def _generate_follow_ups(
    question: str, answer: str, articles: list[Article]
) -> list[str]:
    """Generate 2-3 follow-up question suggestions based on context."""
    suggestions = []
    q_lower = question.lower()

    # Collect unique keywords from articles for context
    specialties = list({a.specialty for a in articles if a.specialty})
    keywords_in_titles = set()
    for a in articles:
        # Extract drug/treatment names (capitalised words with 4+ chars)
        words = re.findall(r"\b[A-Z][a-zäöü]{3,}\b", a.title or "")
        keywords_in_titles.update(words[:3])

    # Strategy 1: If about a specific drug → side effects / alternatives
    drug_names = [
        kw for kw in keywords_in_titles
        if kw.lower() not in ("studie", "study", "trial", "review", "analyse",
                               "patient", "treatment", "therapy", "clinical",
                               "ergebnis", "ergebnisse", "wirkung", "effect")
    ]
    if drug_names:
        drug = drug_names[0]
        if "nebenwirkung" not in q_lower and "safety" not in q_lower:
            suggestions.append(f"Welche Nebenwirkungen hat {drug}?")
        if "meta" not in q_lower:
            suggestions.append(f"Gibt es Meta-Analysen zu {drug}?")
        if "leitlinie" not in q_lower:
            suggestions.append(f"Was sagen aktuelle Leitlinien zu {drug}?")

    # Strategy 2: Specialty-based
    if specialties and len(suggestions) < 3:
        spec = specialties[0]
        suggestions.append(
            f"Was sind die wichtigsten {spec}-Artikel diesen Monat?"
        )

    # Strategy 3: Time-based extension
    if "woche" in q_lower and len(suggestions) < 3:
        suggestions.append(
            question.replace("Woche", "Monat").replace("woche", "monat")
        )
    elif "monat" in q_lower and len(suggestions) < 3:
        suggestions.append(
            "Welche Trends zeigen sich im letzten Quartal?"
        )

    # Strategy 4: Generic fallbacks
    generic = [
        "Welche RCTs gab es diese Woche?",
        "Was sind die Top-bewerteten Artikel heute?",
        "Gibt es aktuelle Arzneimittelwarnungen?",
    ]
    while len(suggestions) < 3:
        for g in generic:
            if g not in suggestions and len(suggestions) < 3:
                suggestions.append(g)

    return suggestions[:3]


def _generate_follow_ups_no_results(question: str) -> list[str]:
    """Follow-up suggestions when no results were found."""
    return [
        "Welche Artikel gibt es diese Woche?",
        "Was sind die Top-bewerteten Artikel?",
        "Zeige alle Artikel zu Kardiologie",
    ]

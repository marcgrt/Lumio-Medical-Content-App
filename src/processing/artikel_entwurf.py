"""Artikel-Entwurf — LLM-generierter Erstentwurf fuer Redakteure."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.config import get_provider_chain
from src.llm_client import cached_chat_completion
from src.models import Article, get_session

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Du bist ein erfahrener Medizinredakteur, der Fachartikel fuer praktizierende Aerzte schreibt.
Erstelle einen strukturierten Artikelentwurf basierend auf der folgenden Studie/Nachricht.

Schreibe auf Deutsch, medizinisch praezise aber verstaendlich.
Der Artikel ist fuer ein aerztliches Fachpublikum bestimmt.

Antworte EXAKT in diesem Format:

HEADLINES:
1. [Headline-Option 1 — max 80 Zeichen, informativ]
2. [Headline-Option 2 — max 80 Zeichen, mit Praxis-Bezug]
3. [Headline-Option 3 — max 80 Zeichen, mit Nachrichten-Hook]
;;;
LEAD:
[2-3 Saetze: Was ist passiert, warum ist es wichtig, was aendert sich?]
;;;
KERNAUSSAGEN:
- [Kernaussage 1: Wichtigstes Ergebnis]
- [Kernaussage 2: Zweitwichtigstes Ergebnis]
- [Kernaussage 3: Klinisch relevanter Befund]
;;;
METHODIK:
[2-3 Saetze: Studiendesign, Population, Endpunkte — nur bei Studien, sonst "Nicht zutreffend"]
;;;
PRAXIS:
[2-3 Saetze: Was bedeutet das konkret fuer den behandelnden Arzt? Handlungsempfehlung.]
;;;
EINORDNUNG:
[2-3 Saetze: Evidenzlevel, Limitationen, Einordnung in den aktuellen Forschungsstand]
;;;
QUELLEN:
[Vollstaendige Quellenangabe: Autoren, Journal, Datum, DOI wenn verfuegbar]"""


@dataclass
class ArtikelEntwurf:
    """A generated article draft."""

    headline_options: list[str]      # 3 headline suggestions
    lead: str                         # 2-3 sentence lead/teaser
    kernaussagen: list[str]          # 3-5 bullet points: key findings
    methodik_zusammenfassung: str    # Brief methodology summary
    praxis_box: str                  # "Was bedeutet das fuer die Praxis?" box
    einordnung: str                  # Context/limitations paragraph
    quellen_hinweis: str             # Source citation note
    article_id: int
    generated_at: datetime = field(default_factory=datetime.now)
    model_used: str = ""


def generate_draft(article_id: int) -> Optional[ArtikelEntwurf]:
    """Generate a structured article draft from an article in the DB."""
    with get_session() as session:
        article = session.get(Article, article_id)
        if not article:
            logger.warning("Artikel-Entwurf: Article %d not found", article_id)
            return None
        # Detach so we can use outside session
        article = article.detach()

    prompt = _build_draft_prompt(article)
    providers = get_provider_chain("article_draft")
    if not providers:
        logger.error("Artikel-Entwurf: No providers configured for 'article_draft'")
        return None

    response = cached_chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM_PROMPT,
        max_tokens=2048,
    )
    if not response:
        logger.warning("Artikel-Entwurf: LLM returned no response for article %d", article_id)
        return None

    draft = _parse_draft_response(response, article_id)
    if draft:
        draft.model_used = providers[0].model if providers else "unknown"
    return draft


def _build_draft_prompt(article: Article) -> str:
    """Build the user prompt for draft generation."""
    parts = [f"Titel: {article.title}"]

    if article.abstract:
        parts.append(f"Abstract: {article.abstract[:2000]}")

    if article.summary_de:
        parts.append(f"AI-Zusammenfassung: {article.summary_de}")

    if article.journal:
        parts.append(f"Journal: {article.journal}")

    if article.study_type:
        parts.append(f"Studientyp: {article.study_type}")

    if article.specialty:
        parts.append(f"Fachgebiet: {article.specialty}")

    if article.authors:
        parts.append(f"Autoren: {article.authors}")

    if article.pub_date:
        parts.append(f"Publikationsdatum: {article.pub_date}")

    if article.doi:
        parts.append(f"DOI: {article.doi}")

    if article.score_breakdown:
        try:
            bd = json.loads(article.score_breakdown)
            parts.append(f"Score-Breakdown: {json.dumps(bd, ensure_ascii=False)}")
        except (json.JSONDecodeError, TypeError):
            pass

    return "\n\n".join(parts)


def _parse_draft_response(response: str, article_id: int) -> Optional[ArtikelEntwurf]:
    """Parse LLM response into ArtikelEntwurf dataclass."""
    sections: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []

    for line in response.split("\n"):
        stripped = line.strip()

        # Check for section separator
        if stripped == ";;;":
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = None
            current_lines = []
            continue

        # Check for section headers
        for key in ("HEADLINES:", "LEAD:", "KERNAUSSAGEN:", "METHODIK:", "PRAXIS:", "EINORDNUNG:", "QUELLEN:"):
            if stripped.startswith(key):
                if current_key:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = key.rstrip(":")
                rest = stripped[len(key):].strip()
                current_lines = [rest] if rest else []
                break
        else:
            current_lines.append(line)

    # Capture last section
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    if not sections:
        logger.warning("Artikel-Entwurf: Could not parse LLM response for article %d", article_id)
        return None

    # Parse headlines
    headlines_raw = sections.get("HEADLINES", "")
    headlines = []
    for hl_line in headlines_raw.split("\n"):
        hl_line = hl_line.strip()
        if hl_line and hl_line[0].isdigit():
            # Strip leading "1. ", "2. ", "3. "
            for prefix in ("1.", "2.", "3."):
                if hl_line.startswith(prefix):
                    hl_line = hl_line[len(prefix):].strip()
                    break
            # Strip surrounding brackets if present
            if hl_line.startswith("[") and hl_line.endswith("]"):
                hl_line = hl_line[1:-1]
            headlines.append(hl_line)
    if not headlines:
        headlines = [headlines_raw.strip()] if headlines_raw.strip() else ["(Keine Headline generiert)"]

    # Parse Kernaussagen (bullet points)
    kern_raw = sections.get("KERNAUSSAGEN", "")
    kernaussagen = []
    for kl in kern_raw.split("\n"):
        kl = kl.strip()
        if kl.startswith("- "):
            kl = kl[2:].strip()
        elif kl.startswith("* "):
            kl = kl[2:].strip()
        if kl:
            # Strip surrounding brackets
            if kl.startswith("[") and kl.endswith("]"):
                kl = kl[1:-1]
            kernaussagen.append(kl)

    return ArtikelEntwurf(
        headline_options=headlines,
        lead=sections.get("LEAD", "").strip(),
        kernaussagen=kernaussagen,
        methodik_zusammenfassung=sections.get("METHODIK", "").strip(),
        praxis_box=sections.get("PRAXIS", "").strip(),
        einordnung=sections.get("EINORDNUNG", "").strip(),
        quellen_hinweis=sections.get("QUELLEN", "").strip(),
        article_id=article_id,
    )


def draft_to_markdown(draft: ArtikelEntwurf) -> str:
    """Convert draft to copyable Markdown text."""
    lines = []
    lines.append("# Artikelentwurf\n")

    lines.append("## Headline-Optionen")
    for i, hl in enumerate(draft.headline_options, 1):
        lines.append(f"{i}. {hl}")
    lines.append("")

    lines.append("## Lead")
    lines.append(draft.lead)
    lines.append("")

    lines.append("## Kernaussagen")
    for ka in draft.kernaussagen:
        lines.append(f"- {ka}")
    lines.append("")

    lines.append("## Methodik")
    lines.append(draft.methodik_zusammenfassung)
    lines.append("")

    lines.append("## Was bedeutet das fuer die Praxis?")
    lines.append(draft.praxis_box)
    lines.append("")

    lines.append("## Einordnung")
    lines.append(draft.einordnung)
    lines.append("")

    lines.append("## Quellen")
    lines.append(draft.quellen_hinweis)
    lines.append("")

    lines.append(f"---\n*Generiert am {draft.generated_at:%d.%m.%Y %H:%M} "
                 f"mit {draft.model_used}*")

    return "\n".join(lines)


def draft_to_clipboard_text(draft: ArtikelEntwurf) -> str:
    """Convert draft to plain text for clipboard."""
    lines = []
    lines.append("ARTIKELENTWURF")
    lines.append("=" * 40)
    lines.append("")

    lines.append("HEADLINE-OPTIONEN:")
    for i, hl in enumerate(draft.headline_options, 1):
        lines.append(f"  {i}. {hl}")
    lines.append("")

    lines.append("LEAD:")
    lines.append(draft.lead)
    lines.append("")

    lines.append("KERNAUSSAGEN:")
    for ka in draft.kernaussagen:
        lines.append(f"  - {ka}")
    lines.append("")

    lines.append("METHODIK:")
    lines.append(draft.methodik_zusammenfassung)
    lines.append("")

    lines.append("PRAXIS:")
    lines.append(draft.praxis_box)
    lines.append("")

    lines.append("EINORDNUNG:")
    lines.append(draft.einordnung)
    lines.append("")

    lines.append("QUELLEN:")
    lines.append(draft.quellen_hinweis)

    return "\n".join(lines)

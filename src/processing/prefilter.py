"""LLM-based pre-filtering — removes irrelevant articles before scoring.

Uses Gemini 2.5 Flash-Lite (free tier, 1 000 req/day) to classify articles
as relevant or irrelevant and to assign a medical specialty.

Supports **batch mode**: up to 5 articles per LLM call (reduces API usage
by ~80%). Falls back to single-article mode on parse failure.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from src.config import SPECIALTY_MESH, get_provider_chain
from src.llm_client import chat_completion
from src.models import Article

logger = logging.getLogger(__name__)

# The 13 specialty names the LLM can choose from — must match config.
_SPECIALTIES = list(SPECIALTY_MESH.keys()) + ["Sonstige"]

# How many articles to send in one LLM call
BATCH_SIZE = 5

_PREFILTER_SYSTEM_PROMPT = f"""\
Du bist ein medizinischer Relevanzfilter für ein Ärzte-Dashboard.
Bewerte, ob ein Artikel für praktizierende Ärzte im deutschsprachigen Raum \
relevant ist.

Antworte IMMER mit exakt einem JSON-Objekt (kein Markdown, kein Text davor/danach):
{{"relevant": true, "fachgebiet": "<Fachgebiet>"}}
oder
{{"relevant": false, "fachgebiet": "<Fachgebiet>"}}

Fachgebiet MUSS einer dieser Werte sein:
{', '.join(_SPECIALTIES)}

Setze "relevant" auf false für klar irrelevante Artikel. Sei konservativ — \
im Zweifel behalten. Aber diese Kategorien sind IMMER irrelevant:

IRRELEVANT (relevant: false):
- Rein präklinische Grundlagenforschung ohne Patientenbezug
- Reine Tiermodell-Studien (Maus, Ratte, Zebrafisch etc.) ohne klinische Translation
- Studienprotokolle ohne Ergebnisse
- Laborchemische Methodik ohne klinische Anwendung
- Bioinformatik/Genomik ohne therapeutische Implikation
- Reine Politiknachrichten ohne klinischen/praktischen Bezug für Ärzte \
(z.B. Parteistreit, Wahlkampf, allgemeine politische Kommentare)
- Meinungsartikel und Kommentare ohne medizinischen Inhalt
- Veterinärmedizin
- Reine Wirtschafts-/Börsennachrichten über Pharmafirmen

RELEVANT (relevant: true):
- Klinische Studien mit Patientendaten
- Leitlinien-Updates
- Therapie-Neuerungen, neue Medikamentenzulassungen
- Arzneimittel-Sicherheit, Rückrufe, Warnungen
- Epidemiologie mit Praxisrelevanz
- Gesundheitspolitik mit konkretem Bezug zum Praxisalltag"""

_BATCH_SYSTEM_PROMPT = f"""\
Du bist ein medizinischer Relevanzfilter für ein Ärzte-Dashboard.
Bewerte für JEDEN Artikel, ob er für praktizierende Ärzte im deutschsprachigen \
Raum relevant ist.

Antworte IMMER mit einem JSON-Array — ein Objekt pro Artikel, in der gleichen \
Reihenfolge (kein Markdown, kein Text davor/danach):
[{{"id": 1, "relevant": true, "fachgebiet": "<Fachgebiet>"}}, {{"id": 2, "relevant": false, "fachgebiet": "Sonstige"}}]

Fachgebiet MUSS einer dieser Werte sein:
{', '.join(_SPECIALTIES)}

Setze "relevant" auf false für klar irrelevante Artikel. Sei konservativ — \
im Zweifel behalten. Aber diese Kategorien sind IMMER irrelevant:

IRRELEVANT (relevant: false):
- Rein präklinische Grundlagenforschung ohne Patientenbezug
- Reine Tiermodell-Studien (Maus, Ratte, Zebrafisch etc.) ohne klinische Translation
- Studienprotokolle ohne Ergebnisse
- Laborchemische Methodik ohne klinische Anwendung
- Bioinformatik/Genomik ohne therapeutische Implikation
- Reine Politiknachrichten ohne klinischen/praktischen Bezug für Ärzte
- Meinungsartikel und Kommentare ohne medizinischen Inhalt
- Veterinärmedizin
- Reine Wirtschafts-/Börsennachrichten über Pharmafirmen

RELEVANT (relevant: true):
- Klinische Studien mit Patientendaten
- Leitlinien-Updates
- Therapie-Neuerungen, neue Medikamentenzulassungen
- Arzneimittel-Sicherheit, Rückrufe, Warnungen
- Epidemiologie mit Praxisrelevanz
- Gesundheitspolitik mit konkretem Bezug zum Praxisalltag"""

_FEW_SHOT_EXAMPLES = [
    # Relevant: RCT with patient outcomes
    {
        "role": "user",
        "content": (
            "Titel: Empagliflozin in Heart Failure with a Preserved Ejection Fraction\n"
            "Abstract: In this randomized trial, empagliflozin reduced the combined "
            "risk of cardiovascular death or hospitalization for heart failure in "
            "patients with heart failure and preserved ejection fraction (HR 0.79).\n"
            "MeSH: Heart Failure; Sodium-Glucose Transporter 2 Inhibitors; "
            "Randomized Controlled Trial"
        ),
    },
    {
        "role": "assistant",
        "content": '{"relevant": true, "fachgebiet": "Kardiologie"}',
    },
    # Relevant: guideline update
    {
        "role": "user",
        "content": (
            "Titel: Neue S3-Leitlinie zur Diagnostik und Therapie des Prostatakarzinoms\n"
            "Abstract: Die aktualisierte Leitlinie empfiehlt bei Niedrigrisiko-Tumoren "
            "Active Surveillance als bevorzugte Strategie. Für das metastasierte "
            "kastrationsresistente Karzinom werden neue Kombinationstherapien empfohlen.\n"
            "MeSH: Prostatic Neoplasms; Practice Guidelines; Drug Therapy, Combination"
        ),
    },
    {
        "role": "assistant",
        "content": '{"relevant": true, "fachgebiet": "Urologie"}',
    },
    # Irrelevant: pure animal study
    {
        "role": "user",
        "content": (
            "Titel: CRISPR-Cas9 Editing of the PCSK9 Gene in Mice Reduces "
            "LDL Cholesterol\n"
            "Abstract: Using an adeno-associated virus vector, we delivered "
            "CRISPR-Cas9 to the liver of C57BL/6 mice, achieving 40% reduction "
            "in circulating PCSK9 and 35% reduction in LDL cholesterol.\n"
            "MeSH: CRISPR-Cas Systems; Mice; PCSK9 protein, mouse; Gene Editing"
        ),
    },
    {
        "role": "assistant",
        "content": '{"relevant": false, "fachgebiet": "Sonstige"}',
    },
    # Irrelevant: study protocol without results
    {
        "role": "user",
        "content": (
            "Titel: Study Protocol for a Randomized Trial of Mindfulness-Based "
            "Cognitive Therapy in Recurrent Depression\n"
            "Abstract: This paper describes the design of a multi-centre RCT "
            "comparing MBCT plus TAU vs TAU alone. Primary outcome is time to "
            "relapse over 24 months. Recruitment will begin in Q3 2026.\n"
            "MeSH: Mindfulness; Depressive Disorder; Randomized Controlled "
            "Trials as Topic; Research Design"
        ),
    },
    {
        "role": "assistant",
        "content": '{"relevant": false, "fachgebiet": "Psychiatrie"}',
    },
    # Irrelevant: non-medical news / opinion about healthcare politics
    {
        "role": "user",
        "content": (
            "Titel: Gesundheitsminister verteidigt Krankenhausreform im Bundestag\n"
            "Quelle: Google News\n"
            "Abstract: In einer hitzigen Debatte verteidigte der Gesundheitsminister "
            "die geplante Krankenhausreform. Die Opposition kritisierte die Pläne als "
            "unzureichend. Patientenvertreter forderten Nachbesserungen.\n"
            "MeSH: "
        ),
    },
    {
        "role": "assistant",
        "content": '{"relevant": false, "fachgebiet": "Sonstige"}',
    },
    # Irrelevant: animal-only bioRxiv preprint
    {
        "role": "user",
        "content": (
            "Titel: Novel AAV Vector Delivers Transgene to Retinal Ganglion Cells "
            "in Non-Human Primates\n"
            "Quelle: bioRxiv\n"
            "Abstract: We developed a novel adeno-associated virus variant that "
            "efficiently transduces retinal ganglion cells in macaques following "
            "intravitreal injection. Transgene expression was sustained for 6 months.\n"
            "MeSH: Dependovirus; Retinal Ganglion Cells; Primates; Genetic Vectors"
        ),
    },
    {
        "role": "assistant",
        "content": '{"relevant": false, "fachgebiet": "Sonstige"}',
    },
]

# Batch few-shot: a mini-batch example so the LLM sees the expected array format
_BATCH_FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": (
            "--- Artikel 1 ---\n"
            "Titel: Empagliflozin in Heart Failure with a Preserved Ejection Fraction\n"
            "Quelle: NEJM\n"
            "Abstract: In this randomized trial, empagliflozin reduced the combined "
            "risk of cardiovascular death or hospitalization for heart failure.\n"
            "MeSH: Heart Failure; Sodium-Glucose Transporter 2 Inhibitors\n\n"
            "--- Artikel 2 ---\n"
            "Titel: CRISPR-Cas9 Editing of the PCSK9 Gene in Mice Reduces "
            "LDL Cholesterol\n"
            "Quelle: bioRxiv\n"
            "Abstract: Using an adeno-associated virus vector, we delivered "
            "CRISPR-Cas9 to the liver of C57BL/6 mice, achieving 40% reduction "
            "in circulating PCSK9.\n"
            "MeSH: CRISPR-Cas Systems; Mice; Gene Editing\n\n"
            "--- Artikel 3 ---\n"
            "Titel: Koalition streitet über Apothekenreform\n"
            "Quelle: Google News\n"
            "Abstract: Die Regierungskoalition konnte sich nicht auf einen "
            "gemeinsamen Entwurf zur Apothekenreform einigen. Vertreter beider "
            "Parteien warfen sich gegenseitig Blockade vor."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '[{"id": 1, "relevant": true, "fachgebiet": "Kardiologie"}, '
            '{"id": 2, "relevant": false, "fachgebiet": "Sonstige"}, '
            '{"id": 3, "relevant": false, "fachgebiet": "Sonstige"}]'
        ),
    },
]


def _build_user_message(article: Article) -> str:
    """Build the user prompt for a single article."""
    parts = [f"Titel: {article.title or ''}"]
    if article.source:
        parts.append(f"Quelle: {article.source}")
    if article.abstract:
        parts.append(f"Abstract: {article.abstract[:1500]}")
    if article.mesh_terms:
        parts.append(f"MeSH: {article.mesh_terms}")
    return "\n".join(parts)


def _build_batch_message(articles: List[Article]) -> str:
    """Build a single user prompt containing multiple numbered articles."""
    parts = []
    for i, article in enumerate(articles, 1):
        block = [f"--- Artikel {i} ---"]
        block.append(f"Titel: {article.title or ''}")
        if article.source:
            block.append(f"Quelle: {article.source}")
        if article.abstract:
            block.append(f"Abstract: {article.abstract[:800]}")
        if article.mesh_terms:
            block.append(f"MeSH: {article.mesh_terms}")
        parts.append("\n".join(block))
    return "\n\n".join(parts)


def _coerce_bool(value) -> bool:
    """Safely coerce a value to bool, handling string 'false'/'true'.

    ``bool("false")`` is ``True`` in Python, so we must handle string
    representations explicitly.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "nein")
    return bool(value)


def _parse_response(text: str) -> Tuple[bool, Optional[str]]:
    """Parse the LLM JSON response for a single article.

    Returns ``(relevant, fachgebiet)`` or ``(True, None)`` as safe default
    if parsing fails (we keep the article rather than lose it).
    """
    cleaned = _strip_markdown_fences(text)

    try:
        data = json.loads(cleaned)
        relevant = _coerce_bool(data.get("relevant", True))
        fachgebiet = data.get("fachgebiet")

        # Validate specialty
        if fachgebiet and fachgebiet not in _SPECIALTIES:
            fachgebiet = None

        return relevant, fachgebiet
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning("Could not parse prefilter response: %s", text[:120])
        return True, None  # keep article on parse failure


def _parse_batch_response(
    text: str, count: int,
) -> Optional[List[Tuple[bool, Optional[str]]]]:
    """Parse the LLM JSON array response for a batch of articles.

    Returns a list of ``(relevant, fachgebiet)`` tuples, one per article,
    or ``None`` if parsing fails entirely (caller should fall back to
    single-article mode).
    """
    cleaned = _strip_markdown_fences(text)

    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse batch prefilter response: %s", text[:200])
        return None

    # Accept both a JSON array and a dict wrapping an array
    if isinstance(data, dict):
        # Try common wrapper keys
        for key in ("results", "articles", "ergebnisse"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            return None

    if not isinstance(data, list):
        return None

    # Map by id (1-indexed) or by position
    results: List[Tuple[bool, Optional[str]]] = []
    by_id: Dict[int, dict] = {}
    for item in data:
        if isinstance(item, dict) and "id" in item:
            by_id[int(item["id"])] = item

    for i in range(1, count + 1):
        item = by_id.get(i) if by_id else (data[i - 1] if i - 1 < len(data) else None)
        if item and isinstance(item, dict):
            relevant = _coerce_bool(item.get("relevant", True))
            fachgebiet = item.get("fachgebiet")
            if fachgebiet and fachgebiet not in _SPECIALTIES:
                fachgebiet = None
            results.append((relevant, fachgebiet))
        else:
            results.append((True, None))  # safe default

    return results


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences that some models wrap JSON in."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def prefilter_article(article: Article) -> Tuple[bool, Optional[str]]:
    """Pre-filter a single article using the LLM.

    Returns ``(keep, fachgebiet)``.  If no LLM is available the article
    is kept (``True, None``).
    """
    providers = get_provider_chain("prefilter")
    if not providers:
        return True, None

    user_msg = _build_user_message(article)

    messages = list(_FEW_SHOT_EXAMPLES) + [
        {"role": "user", "content": user_msg},
    ]

    raw = chat_completion(
        providers=providers,
        messages=messages,
        system=_PREFILTER_SYSTEM_PROMPT,
        max_tokens=60,
    )
    if raw is None:
        return True, None  # keep on failure

    return _parse_response(raw)


def _prefilter_batch(
    articles: List[Article], providers,
) -> List[Tuple[bool, Optional[str]]]:
    """Pre-filter a batch of articles in a single LLM call.

    Falls back to per-article calls if batch parsing fails.
    """
    user_msg = _build_batch_message(articles)

    # Include few-shot examples so the LLM is calibrated on what to filter.
    messages = list(_BATCH_FEW_SHOT_EXAMPLES) + [
        {"role": "user", "content": user_msg},
    ]

    # Batch needs more tokens: ~60 per article
    max_tokens = 60 * len(articles) + 20

    raw = chat_completion(
        providers=providers,
        messages=messages,
        system=_BATCH_SYSTEM_PROMPT,
        max_tokens=max_tokens,
    )

    if raw is None:
        # All providers failed — fall back to single-article mode
        logger.debug("Batch prefilter failed — falling back to single-article mode")
        return [prefilter_article(a) for a in articles]

    results = _parse_batch_response(raw, len(articles))
    if results is None:
        # Parse failure — fall back to single-article mode
        logger.warning("Batch parse failed — falling back to single-article mode")
        return [prefilter_article(a) for a in articles]

    return results


def prefilter_articles(articles: List[Article]) -> List[Article]:
    """Pre-filter a list of articles — remove irrelevant ones.

    Uses batch mode (5 articles per LLM call) to reduce API usage.
    Falls back to single-article mode on batch parse failure.

    Also assigns ``article.specialty`` when the LLM provides one and the
    article doesn't have a specialty yet.

    If no prefilter providers are configured (no API key), all articles
    pass through unchanged.
    """
    providers = get_provider_chain("prefilter")
    if not providers:
        logger.info("No prefilter providers configured — skipping pre-filter")
        return articles

    kept: List[Article] = []
    removed = 0
    batch_calls = 0

    # Process in batches
    for start in range(0, len(articles), BATCH_SIZE):
        batch = articles[start : start + BATCH_SIZE]

        if len(batch) >= 2:
            # Batch mode (2+ articles)
            results = _prefilter_batch(batch, providers)
            batch_calls += 1
        else:
            # Single article — use direct call
            results = [prefilter_article(batch[0])]

        for article, (relevant, fachgebiet) in zip(batch, results):
            if relevant:
                if fachgebiet and fachgebiet != "Sonstige" and not article.specialty:
                    article.specialty = fachgebiet
                kept.append(article)
            else:
                removed += 1
                logger.debug("Prefilter removed: %s", (article.title or "")[:80])

    logger.info(
        "Prefilter: %d kept, %d removed (of %d total, %d batch calls)",
        len(kept), removed, len(articles), batch_calls,
    )
    return kept

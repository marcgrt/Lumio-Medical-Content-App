"""Multi-tier relevance scoring for medical articles."""

import json
import logging
import math
from datetime import date
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from src.config import (
    JOURNAL_TIERS,
    DEFAULT_JOURNAL_SCORE,
    STUDY_DESIGN_KEYWORDS,
    DEFAULT_STUDY_DESIGN_SCORE,
    WEIGHT_JOURNAL,
    WEIGHT_STUDY_DESIGN,
    WEIGHT_RECENCY,
    WEIGHT_KEYWORD_BOOST,
    WEIGHT_ARZTRELEVANZ,
    SAFETY_KEYWORDS,
    GUIDELINE_KEYWORDS,
    LANDMARK_KEYWORDS,
    SAFETY_BOOST,
    GUIDELINE_BOOST,
    LANDMARK_BOOST,
    ARZTRELEVANZ_KEYWORDS,
    REDAKTIONS_BONUS,
)
from src.models import Article


def _journal_score(article: Article) -> float:
    """Score based on journal tier."""
    journal = (article.journal or "").lower()
    for fragment, score in JOURNAL_TIERS.items():
        if fragment in journal:
            return score
    return DEFAULT_JOURNAL_SCORE


def _study_design_score(article: Article, _text: str = "") -> float:
    """Score based on detected study design."""
    text = f"{_text} {(article.study_type or '').lower()}" if _text else \
        f"{article.title or ''} {article.abstract or ''} {article.study_type or ''}".lower()
    for keywords, score in STUDY_DESIGN_KEYWORDS:
        if any(kw in text for kw in keywords):
            return score
    return DEFAULT_STUDY_DESIGN_SCORE


def _recency_score(article: Article) -> float:
    """Exponential decay: today=100, -10/day."""
    if not article.pub_date:
        return 50.0  # unknown date → middle value
    days_old = max(0, (date.today() - article.pub_date).days)
    return 100.0 * math.exp(-0.1 * days_old)


def _keyword_boost(article: Article, _text: str = "") -> float:
    """Bonus points for safety, guideline, and landmark keywords."""
    text = _text or f"{article.title or ''} {article.abstract or ''}".lower()
    boost = 0.0
    if any(kw in text for kw in SAFETY_KEYWORDS):
        boost = max(boost, SAFETY_BOOST)
    if any(kw in text for kw in GUIDELINE_KEYWORDS):
        boost = max(boost, GUIDELINE_BOOST)
    if any(kw in text for kw in LANDMARK_KEYWORDS):
        boost = max(boost, LANDMARK_BOOST)
    return boost


def _arztrelevanz_score(article: Article, _text: str = "") -> float:
    """Score based on relevance for practicing German physicians.

    Scans title and abstract for therapy, diagnosis, health-policy,
    and practice-management keywords.  Returns the highest matching
    tier, scaled to 0-100 for the weighted formula.
    """
    text = _text or f"{article.title or ''} {article.abstract or ''}".lower()

    best = 0
    for keywords, raw_score in ARZTRELEVANZ_KEYWORDS:
        if any(kw in text for kw in keywords):
            best = max(best, raw_score)

    # Scale: raw scores are 10-15; map to 0-100.
    # 15 → 100, 12 → 80, 10 → 67.  No match → 0.
    return round((best / 15) * 100, 1) if best > 0 else 0.0


def _redaktions_bonus(article: Article) -> float:
    """Flat bonus for articles from editorially curated physician sources.

    Reflects that editors at Ärzteblatt, Ärzte Zeitung etc. actively
    select and prepare content for practicing physicians.
    """
    journal = (article.journal or "").lower()
    for fragment, bonus in REDAKTIONS_BONUS.items():
        if fragment in journal:
            return float(bonus)
    return 0.0


def _interdisciplinary_bonus(article: Article, _text: str = "") -> float:
    """Bonus for articles spanning multiple specialties (often more interesting)."""
    from src.config import SPECIALTY_MESH

    text = f"{_text} {(article.mesh_terms or '').lower()}" if _text else (
        f"{article.title or ''} {article.abstract or ''} "
        f"{article.mesh_terms or ''}"
    ).lower()

    hit_count = 0
    for keywords in SPECIALTY_MESH.values():
        if any(kw in text for kw in keywords):
            hit_count += 1

    # Bonus kicks in at 2+ specialties
    if hit_count >= 3:
        return 10.0
    elif hit_count >= 2:
        return 5.0
    return 0.0


def _abstract_length_modifier(article: Article, _text: str = "") -> float:
    """Malus for very short abstracts (editorials, comments).

    Only applies to journal articles — news articles, clinical reviews
    and editorials naturally have shorter or no structured abstracts.
    """
    source = (article.source or "").lower()
    # Don't penalize news sources or German clinical press
    if any(kw in source for kw in ["google news", "who ", "ärzte zeitung",
                                     "ärzteblatt", "apotheke", "pharma"]):
        return 0.0

    abstract = article.abstract or ""
    text_lower = _text or f"{article.title or ''} {abstract}".lower()

    # Don't penalize clinical reviews / Fachartikel / editorials
    review_signals = [
        "clinical review", "klinische übersicht", "narrative review",
        "übersichtsarbeit", "fachartikel", "fortbildung",
        "editorial", "perspective", "viewpoint", "kommentar",
    ]
    if any(sig in text_lower for sig in review_signals):
        return 0.0

    word_count = len(abstract.split())
    if word_count < 50:
        return -5.0  # likely comment / no real abstract
    return 0.0


# ---------------------------------------------------------------------------
# Quality rewards — signal rigour and accessibility
# ---------------------------------------------------------------------------

def _open_access_bonus(article: Article) -> float:
    """Bonus for freely accessible articles (PMC, PubMed Central, known OA).

    Open-access articles are immediately useful — no subscription needed.
    """
    url = (article.url or "").lower()
    if any(sig in url for sig in ["/pmc/", "pmc.ncbi", "europepmc", "/full"]):
        return 5.0
    # Known OA journals
    journal = (article.journal or "").lower()
    if any(oa in journal for oa in ["plos", "bmc ", "frontiers", "elife",
                                      "nature communications", "scientific reports"]):
        return 5.0
    return 0.0


def _structured_abstract_bonus(article: Article) -> float:
    """Bonus for articles with structured abstracts (IMRAD format).

    Background/Methods/Results/Conclusion sections indicate proper
    research methodology — higher quality than narrative summaries.
    """
    abstract = (article.abstract or "").lower()
    if len(abstract) < 200:
        return 0.0

    section_markers = [
        "background:", "objective:", "objectives:", "aim:", "aims:",
        "purpose:", "introduction:", "hintergrund:", "zielsetzung:",
        "methods:", "method:", "design:", "methoden:", "methodik:",
        "results:", "findings:", "ergebnisse:",
        "conclusion:", "conclusions:", "discussion:",
        "schlussfolgerung:", "fazit:",
    ]
    hits = sum(1 for m in section_markers if m in abstract)
    if hits >= 3:
        return 4.0   # Full structured abstract
    if hits >= 2:
        return 2.0   # Partially structured
    return 0.0


def _doi_bonus(article: Article) -> float:
    """Small bonus for articles with DOI (indicates peer review)."""
    if article.doi and len(article.doi) > 5:
        return 2.0
    return 0.0


# ---------------------------------------------------------------------------
# Paywall penalty — devalue articles with no usable content
# ---------------------------------------------------------------------------

_PAYWALL_JOURNALS = {
    "nejm", "new england journal of medicine",
    "jama", "journal of the american medical association",
    "annals of internal medicine",
    "circulation", "european heart journal",
    "journal of clinical oncology", "jco",
    "gut", "blood", "brain", "chest",
}


def _paywall_modifier(article: Article) -> float:
    """Penalty for paywall articles without usable abstract.

    High-prestige journals behind paywalls are useless if the team
    can't read them.  We detect this via:
    - Journal name matches known paywall sources  AND
    - Abstract is missing, very short, or just a citation stub
    """
    journal = (article.journal or "").lower()
    is_paywall_source = any(pw in journal for pw in _PAYWALL_JOURNALS)
    if not is_paywall_source:
        return 0.0

    abstract = (article.abstract or "").strip()
    # Citation stubs look like "New England Journal of Medicine, Volume ..."
    is_citation_stub = (
        abstract.lower().startswith(("new england", "jama", "the lancet",
                                      "annals of", "circulation", "european"))
        and "volume" in abstract.lower()
    )
    word_count = len(abstract.split())

    if word_count < 30 or is_citation_stub:
        return -15.0  # No usable content → strong penalty
    if word_count < 80:
        return -8.0   # Very short abstract → moderate penalty
    return 0.0


# ---------------------------------------------------------------------------
# Industry/business news penalty
# ---------------------------------------------------------------------------

_INDUSTRY_KEYWORDS = [
    "milliarden", "millionen dollar", "millionen euro",
    "übernahme", "ankauf", "akquisition", "acquisition",
    "börse", "aktie", "aktienkurs", "ipo",
    "umsatz", "gewinn", "quartalszahlen", "geschäftsjahr",
    "investor", "investition", "deal",
    "merger", "takeover", "buyout",
]

_INDUSTRY_EXEMPT_KEYWORDS = [
    # Don't penalize if clinical relevance is clear
    "zulassung", "approval", "fda", "ema", "bfarm",
    "phase iii", "phase 3", "phase ii", "phase 2",
    "klinische studie", "clinical trial",
    "rückruf", "warnung",
]


def _industry_news_modifier(article: Article, _text: str = "") -> float:
    """Penalty for pharma business/financial news without clinical relevance.

    M&A deals, quarterly earnings, stock prices etc. are not useful
    for practicing physicians even when published in trusted medical press.
    """
    text = _text or f"{article.title or ''} {article.abstract or ''}".lower()

    has_industry = any(kw in text for kw in _INDUSTRY_KEYWORDS)
    if not has_industry:
        return 0.0

    # Exempt if article also has clear clinical relevance
    has_clinical = any(kw in text for kw in _INDUSTRY_EXEMPT_KEYWORDS)
    if has_clinical:
        return 0.0

    return -12.0


def compute_relevance_score(article: Article) -> Tuple[float, dict]:
    """Compute composite relevance score (0-100) and breakdown dict."""
    # Build text once, pass to sub-functions to avoid redundant construction
    _text = f"{article.title or ''} {article.abstract or ''}".lower()

    j = _journal_score(article)
    s = _study_design_score(article, _text)
    r = _recency_score(article)
    k = _keyword_boost(article, _text)
    a = _arztrelevanz_score(article, _text)

    wj = round(WEIGHT_JOURNAL * j, 1)
    ws = round(WEIGHT_STUDY_DESIGN * s, 1)
    wr = round(WEIGHT_RECENCY * r, 1)
    wk = round(WEIGHT_KEYWORD_BOOST * k, 1)
    wa = round(WEIGHT_ARZTRELEVANZ * a, 1)

    score = wj + ws + wr + wk + wa

    # Additional modifiers (flat bonuses/penalties, not weighted)
    inter = _interdisciplinary_bonus(article, _text)
    abstr = _abstract_length_modifier(article, _text)
    redak = _redaktions_bonus(article)
    paywall = _paywall_modifier(article)
    industry = _industry_news_modifier(article, _text)
    oa = _open_access_bonus(article)
    struct = _structured_abstract_bonus(article)
    doi = _doi_bonus(article)
    bonus = round(inter + abstr + redak + paywall + industry + oa + struct + doi, 1)

    score += bonus

    final = round(min(100.0, max(0.0, score)), 1)

    breakdown = {
        "journal": wj,
        "design": ws,
        "recency": wr,
        "keywords": wk,
        "arztrelevanz": wa,
        "bonus": bonus,
        "total": final,
    }

    return final, breakdown


# ---------------------------------------------------------------------------
# LLM-based scoring (esanum 5-dimension model)
# ---------------------------------------------------------------------------

_LLM_SCORING_SYSTEM_PROMPT = """\
Du bist ein medizinischer Relevanz-Scorer für ein Ärzte-Dashboard.
Bewerte den Artikel in 5 Dimensionen (je 0-20 Punkte).

Antworte IMMER mit exakt einem JSON-Objekt (kein Markdown, kein Text davor/danach):
{"studientyp": <0-20>, "klinische_relevanz": <0-20>, "neuigkeitswert": <0-20>, \
"zielgruppen_fit": <0-20>, "quellenqualitaet": <0-20>, \
"begr_studientyp": "<1 Satz>", "begr_klinische_relevanz": "<1 Satz>", \
"begr_neuigkeitswert": "<1 Satz>", "begr_zielgruppen_fit": "<1 Satz>", \
"begr_quellenqualitaet": "<1 Satz>"}

Bewertungslogik:
1. STUDIENTYP (0-20): Meta-Analyse/Systematic Review: 20. RCT: 18. \
Kohortenstudie: 14. Fall-Kontroll: 10. Case Report: 6. Editorial: 4. \
Pressemitteilung: 2.
2. KLINISCHE RELEVANZ (0-20): Ändert Leitlinien: 20. Neue Therapie mit \
Evidenz: 16. Bestätigt Praxis: 10. Frühe Phase: 4.
3. NEUIGKEITSWERT (0-20): Erstmalige Ergebnisse: 20. Phase-III-Update: 14. \
Zwischenanalyse: 10. Bestätigung bekannter Daten: 6.
4. ZIELGRUPPEN-FIT (0-20): Häufige Erkrankung, breite Praxisrelevanz: 20. \
Spezialistenthema: 14. Seltene Erkrankung: 8. Rein akademisch: 4.
5. QUELLENQUALITÄT (0-20): NEJM/Lancet/BMJ/JAMA: 20. IF>5 Journal: 16. \
Ärzteblatt/Ärztezeitung: 14. IF 2-5: 12. Allgemeine News: 6."""


def _build_scoring_prompt(article: Article) -> str:
    """Build the user message for LLM scoring."""
    parts = [f"Titel: {article.title or ''}"]
    if article.abstract:
        parts.append(f"Abstract: {article.abstract[:1500]}")
    if article.journal:
        parts.append(f"Journal: {article.journal}")
    if article.study_type and article.study_type != "Unbekannt":
        parts.append(f"Studientyp: {article.study_type}")
    if article.mesh_terms:
        parts.append(f"MeSH: {article.mesh_terms}")
    if article.pub_date:
        parts.append(f"Publikationsdatum: {article.pub_date.isoformat()}")
    return "\n".join(parts)


def _parse_llm_score(text: str) -> Optional[dict]:
    """Parse LLM scoring response into a breakdown dict.

    Returns ``None`` on parse failure.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse LLM score JSON: %s", text[:120])
        return None

    # Validate that the 5 dimension keys exist and are numeric
    dim_keys = [
        "studientyp", "klinische_relevanz", "neuigkeitswert",
        "zielgruppen_fit", "quellenqualitaet",
    ]
    scores = {}
    for key in dim_keys:
        val = data.get(key)
        if val is None:
            logger.warning("LLM score missing dimension: %s", key)
            return None
        scores[key] = max(0, min(20, float(val)))

    total = round(sum(scores.values()), 1)

    breakdown = {
        "scorer": "llm",
        "studientyp": scores["studientyp"],
        "klinische_relevanz": scores["klinische_relevanz"],
        "neuigkeitswert": scores["neuigkeitswert"],
        "zielgruppen_fit": scores["zielgruppen_fit"],
        "quellenqualitaet": scores["quellenqualitaet"],
        "total": total,
    }

    # Add reasoning strings if present
    for key in dim_keys:
        begr_key = f"begr_{key}"
        if begr_key in data and isinstance(data[begr_key], str):
            breakdown[begr_key] = data[begr_key][:200]

    return breakdown


# Cache for feedback examples (loaded once per pipeline run)
_feedback_cache: Optional[dict] = None
_feedback_loaded = False


def _get_feedback_examples() -> Optional[list]:
    """Load feedback few-shot examples (cached per pipeline run)."""
    global _feedback_cache, _feedback_loaded
    if _feedback_loaded:
        return _feedback_cache

    _feedback_loaded = True
    try:
        from src.processing.feedback import get_feedback_examples, build_few_shot_messages
        feedback = get_feedback_examples()
        if feedback is not None:
            _feedback_cache = build_few_shot_messages(feedback)
        else:
            _feedback_cache = None
    except Exception as exc:
        logger.warning("Could not load feedback examples: %s", exc)
        _feedback_cache = None

    return _feedback_cache


def llm_score_article(article: Article) -> Optional[Tuple[float, dict]]:
    """Score an article using an LLM (Gemini Flash).

    If enough Approve/Reject decisions exist, injects few-shot examples
    from real editorial decisions into the prompt for calibration.

    Returns ``(score, breakdown)`` or ``None`` if LLM is unavailable or fails.
    """
    from src.config import get_provider_chain
    from src.llm_client import chat_completion

    providers = get_provider_chain("scoring")
    if not providers:
        return None

    # Build messages: optional few-shot examples + current article
    messages = []

    # Inject feedback few-shot examples (approved/rejected)
    few_shot = _get_feedback_examples()
    if few_shot:
        messages.extend(few_shot)

    # Current article to score
    user_msg = _build_scoring_prompt(article)
    messages.append({"role": "user", "content": user_msg})

    raw = chat_completion(
        providers=providers,
        messages=messages,
        system=_LLM_SCORING_SYSTEM_PROMPT,
        # No max_tokens override — use provider default.
        # Gemini 2.5 Flash needs high limit (8192) because thinking
        # tokens count against the budget internally.
    )
    if raw is None:
        return None

    breakdown = _parse_llm_score(raw)
    if breakdown is None:
        return None

    return breakdown["total"], breakdown


def score_articles(articles: list[Article]) -> list[Article]:
    """Score articles — LLM for pre-filtered set, rule-based as fallback.

    Uses concurrent threads (max 4) when LLM scoring is enabled to
    parallelise API calls.  Falls back to the rule-based scorer for
    individual articles where the LLM fails.
    """
    global _feedback_cache, _feedback_loaded
    from src.config import get_provider_chain

    # Reset feedback cache for this pipeline run
    _feedback_cache = None
    _feedback_loaded = False

    use_llm = bool(get_provider_chain("scoring"))
    llm_count = 0
    rule_count = 0

    if use_llm and len(articles) > 2:
        # Warm up feedback cache in main thread before spawning workers
        _get_feedback_examples()

        from src.llm_client import map_concurrent

        llm_results = map_concurrent(llm_score_article, articles, max_workers=4)

        for article, llm_result in zip(articles, llm_results):
            if llm_result is not None:
                score, breakdown = llm_result
                rb_score, _ = compute_relevance_score(article)
                breakdown["rule_based_score"] = rb_score
                article.relevance_score = score
                article.score_breakdown = json.dumps(breakdown)
                llm_count += 1
            else:
                score, breakdown = compute_relevance_score(article)
                article.relevance_score = score
                article.score_breakdown = json.dumps(breakdown)
                rule_count += 1
    else:
        for article in articles:
            llm_result = None
            if use_llm:
                llm_result = llm_score_article(article)

            if llm_result is not None:
                score, breakdown = llm_result
                rb_score, _ = compute_relevance_score(article)
                breakdown["rule_based_score"] = rb_score
                article.relevance_score = score
                article.score_breakdown = json.dumps(breakdown)
                llm_count += 1
            else:
                score, breakdown = compute_relevance_score(article)
                article.relevance_score = score
                article.score_breakdown = json.dumps(breakdown)
                rule_count += 1

    articles.sort(key=lambda a: a.relevance_score, reverse=True)

    if use_llm:
        logger.info("Scoring: %d via LLM, %d via rule-based (concurrent)", llm_count, rule_count)
    else:
        logger.info("Scoring: %d articles (rule-based)", rule_count)

    return articles

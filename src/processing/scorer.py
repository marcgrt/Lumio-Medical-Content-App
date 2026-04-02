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
        boost += SAFETY_BOOST
    if any(kw in text for kw in GUIDELINE_KEYWORDS):
        boost += GUIDELINE_BOOST
    if any(kw in text for kw in LANDMARK_KEYWORDS):
        boost += LANDMARK_BOOST
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


def compute_relevance_score_v1(article: Article) -> Tuple[float, dict]:
    """Compute v1 composite relevance score (0-100) and breakdown dict.

    Kept for backward compatibility — renamed from compute_relevance_score.
    """
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


# Alias for backward compatibility
compute_relevance_score = compute_relevance_score_v1


# ---------------------------------------------------------------------------
# Rule-based v2 scoring (6-dimension fallback)
# ---------------------------------------------------------------------------

# clinical_action_relevance keyword tiers
_CAR_HIGH_KW = [
    "rückruf", "rote-hand-brief", "rote hand brief", "dosierung",
    "kontraindikation", "leitlinie", "neue therapie", "zulassung",
]
_CAR_MEDIUM_KW = [
    "therapie", "behandlung", "diagnostik", "screening", "prävention",
]
_CAR_LOW_KW = [
    "studie zeigt", "daten", "ergebnisse", "analyse",
]

# topic_appeal keyword tiers
_TA_VERY_HIGH_KW = [
    "ärztemangel", "honorar", "burnout", "arbeitszeitgesetz",
    "krankenhausreform", "regress", "kassenzulassung",
]
_TA_HIGH_KW = [
    "epa", "digitalisierung", "telematik", "bürokratie",
    "work-life-balance", "ki diagnostik",
]
_TA_MEDIUM_KW = [
    "leitlinie", "kongress", "fortbildung", "cme",
]

# novelty keyword tiers
_NOV_HIGH_KW = [
    "first-in-class", "erstmals", "first", "breakthrough", "neuartig",
]
_NOV_MED_HIGH_KW = [
    "phase iii", "phase 3", "zulassung", "approval",
]
_NOV_MED_KW = [
    "update", "neue daten",
]
_NOV_LOW_KW = [
    "übersicht", "review", "zusammenfassung",
]

# Source authority tiers (journal fragment → score 0-12)
_SA_TIERS: dict[str, int] = {
    # Tier 1 (12)
    "new england journal of medicine": 12, "nejm": 12,
    "lancet": 12, "jama": 12, "bmj": 12,
    "nature medicine": 12, "nature": 12,
    # Tier 2 (10)
    "circulation": 10, "journal of clinical oncology": 10, "jco": 10,
    "european heart journal": 10, "annals of internal medicine": 10,
    # Tier 2b (9)
    "deutsches ärzteblatt": 9, "deutsches arzteblatt": 9, "aerzteblatt": 9,
    # Tier 3 (8)
    "gut": 8, "blood": 8, "diabetes care": 8, "brain": 8, "chest": 8,
    # Tier 3b (7)
    "ärzte zeitung": 7, "aerztezeitung": 7, "pharmazeutische zeitung": 7,
    # Tier 5 — preprints (3)
    "medrxiv": 3, "biorxiv": 3,
}


def compute_relevance_score_v2(article: Article) -> Tuple[float, dict]:
    """Compute v2 rule-based fallback score (6 dimensions, sum = 0-100).

    Produces approximate v2 scores when LLM scoring is unavailable.
    """
    _text = f"{article.title or ''} {article.abstract or ''}".lower()
    abstract = article.abstract or ""
    abstract_words = len(abstract.split())

    # --- 1. clinical_action_relevance (0-20) ---
    car = 6  # default
    if any(kw in _text for kw in _CAR_HIGH_KW):
        car = 16  # midpoint of 15-18
    elif any(kw in _text for kw in _CAR_MEDIUM_KW):
        car = 11  # midpoint of 9-14
    elif any(kw in _text for kw in _CAR_LOW_KW):
        car = 6   # midpoint of 4-8

    # --- 2. evidence_depth (0-20) ---
    ed = 8  # default
    text_with_type = f"{_text} {(article.study_type or '').lower()}"
    if any(kw in text_with_type for kw in ["meta-analysis", "meta analysis", "systematic review"]):
        ed = 18
    elif any(kw in text_with_type for kw in ["randomized", "randomised", "rct"]):
        ed = 16
    elif "cohort study" in text_with_type or "cohort" in text_with_type:
        ed = 12
    elif any(kw in text_with_type for kw in ["editorial", "review", "übersichtsarbeit"]):
        ed = 11
    elif any(kw in text_with_type for kw in ["case-control", "case control"]):
        ed = 10
    elif any(kw in text_with_type for kw in ["case report", "case series"]):
        ed = 6
    elif any(kw in text_with_type for kw in ["press release", "pressemitteilung"]):
        ed = 4

    # Bonus: abstract >200 words AND ≥3 citation signals
    citation_signals = sum(1 for sig in ["et al.", "et al,", "references", "bibliography", "cited"]
                          if sig in _text)
    if abstract_words > 200 and citation_signals >= 3:
        ed = min(20, ed + 2)

    # --- 3. topic_appeal (0-20) ---
    ta = 9  # default
    if any(kw in _text for kw in _TA_VERY_HIGH_KW):
        ta = 17  # midpoint of 16-19
    elif any(kw in _text for kw in _TA_HIGH_KW):
        ta = 13  # midpoint of 12-15
    elif any(kw in _text for kw in _TA_MEDIUM_KW):
        ta = 9   # midpoint of 8-11

    # Interdisciplinary bonus
    from src.config import SPECIALTY_MESH
    text_for_spec = f"{_text} {(article.mesh_terms or '').lower()}"
    spec_hits = sum(1 for keywords in SPECIALTY_MESH.values()
                    if any(kw in text_for_spec for kw in keywords))
    if spec_hits >= 3:
        ta = min(20, ta + 4)
    elif spec_hits >= 2:
        ta = min(20, ta + 2)

    # --- 4. novelty (0-16) ---
    nov = 7  # default
    if any(kw in _text for kw in _NOV_HIGH_KW):
        nov = 14
    elif any(kw in _text for kw in _NOV_MED_HIGH_KW):
        nov = 11
    elif any(kw in _text for kw in _NOV_MED_KW):
        nov = 9
    elif any(kw in _text for kw in _NOV_LOW_KW):
        nov = 5

    # Date modifier
    if article.pub_date:
        days_old = max(0, (date.today() - article.pub_date).days)
        if days_old == 0:
            date_mult = 1.0
        elif days_old <= 3:
            date_mult = 0.95
        elif days_old <= 7:
            date_mult = 0.85
        elif days_old <= 14:
            date_mult = 0.70
        else:
            date_mult = 0.55
        nov = round(nov * date_mult)

    nov = min(16, max(0, nov))

    # --- 5. source_authority (0-12) ---
    sa = 5  # default (peer-reviewed)
    journal_lower = (article.journal or "").lower()
    source_lower = (article.source or "").lower()

    # Check for press release in text/source
    if any(kw in _text or kw in source_lower for kw in ["press release", "pressemitteilung"]):
        sa = 1
    else:
        for fragment, score in _SA_TIERS.items():
            if fragment in journal_lower or fragment in source_lower:
                sa = score
                break

    # --- 6. presentation_quality (0-12) ---
    pq = 4  # default base

    # Abstract length bonus
    if abstract_words >= 200:
        pq += 4
    elif abstract_words >= 80:
        pq += 2

    # IMRAD detection
    imrad_markers = [
        "background:", "objective:", "methods:", "method:", "results:",
        "conclusion:", "conclusions:", "hintergrund:", "methoden:",
        "ergebnisse:", "schlussfolgerung:", "design:", "findings:",
        "aim:", "purpose:", "discussion:", "fazit:",
    ]
    imrad_hits = sum(1 for m in imrad_markers if m in abstract.lower())
    if imrad_hits >= 2:
        pq += 3

    # DOI present
    if article.doi and len(article.doi) > 5:
        pq += 1

    # Paywall penalty
    if abstract_words < 30:
        is_paywall = any(pw in journal_lower for pw in [
            "nejm", "new england", "jama", "lancet", "annals of internal",
            "circulation", "european heart",
        ])
        if is_paywall:
            pq -= 4

    pq = min(12, max(0, pq))

    # --- Total ---
    total = round(min(100.0, max(0.0, float(car + ed + ta + nov + sa + pq))), 1)

    if total >= 70:
        tier = "TOP"
    elif total >= 45:
        tier = "RELEVANT"
    else:
        tier = "MONITOR"

    breakdown = {
        "scorer": "rule_v2",
        "scoring_version": "v2",
        "estimated": True,
        "scores": {
            "clinical_action_relevance": {"score": car, "reason": "Rule-based estimate"},
            "evidence_depth": {"score": ed, "reason": "Rule-based estimate"},
            "topic_appeal": {"score": ta, "reason": "Rule-based estimate"},
            "novelty": {"score": nov, "reason": "Rule-based estimate"},
            "source_authority": {"score": sa, "reason": "Rule-based estimate"},
            "presentation_quality": {"score": pq, "reason": "Rule-based estimate"},
        },
        "total": total,
        "tier": tier,
        "one_line_summary": "",
    }

    return total, breakdown


# ---------------------------------------------------------------------------
# LLM-based scoring (v2: 6-dimension model)
# ---------------------------------------------------------------------------

_LLM_SCORING_SYSTEM_PROMPT_V1 = """\
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

_LLM_SCORING_SYSTEM_PROMPT = """\
Du bist ein medizinischer Relevanz-Scorer für eine Ärzteplattform mit 369.000 registrierten Ärzten in Deutschland.

Bewerte den folgenden Artikel in 6 Dimensionen. Vergib für jede Dimension einen Score UND eine Begründung in 1–2 Sätzen.

DIMENSIONEN:
1. Klinische Handlungsrelevanz (0–20): Kann ein Arzt nach dem Lesen konkret etwas anders machen?
   18–20: Sofortige Handlungsänderung (Rote-Hand-Brief, neue Dosierung, Zulassungsentzug, Kontraindikation, neue Dokumentationspflicht).
   14–17: Handlungsänderung wahrscheinlich (neue Leitlinie, neue Therapieoption, Vergütungsänderung, große RCT zu Erstlinie).
   9–13: Beeinflusst Entscheidungen indirekt (Registerdaten, Vergleichsstudien, epidemiologische Trends).
   4–8: Hintergrundwissen (Phase I/II, Grundlagenforschung, akademische Debatte).
   0–3: Keine ärztliche Relevanz.

2. Evidenz- & Recherchetiefe (0–20): Wie methodisch solide ist die Grundlage — egal ob Studie oder Journalismus?
   18–20: Meta-Analyse/Systematic Review PRISMA-konform, große multizentrische RCT, Cochrane Review. Oder: investigativ recherchiert mit ≥4 unabhängigen Quellen und eigener Datenanalyse.
   14–17: RCT monozentrisch/Surrogat, große Kohorte >10.000. Oder: 2–3 unabhängige Quellen mit Faktengrundlage.
   9–13: Kleinere Kohorten, retrospektive Analysen. Oder: 1–2 Quellen, korrekt aber ohne eigene Analyse.
   4–8: Fallberichte, Pilotstudien <50. Oder: Einzelquelle ohne Gegenposition.
   0–3: Unbelegte Behauptungen, reine Spekulation.

3. Thematische Zugkraft (0–20): Wie stark wollen Ärzte das lesen, teilen und diskutieren?
   18–20: Maximale Zugkraft (Ärztemangel, Klinikschließungen, Honorarreform, Sicherheitsalarm häufiges Medikament, spaltendes Thema).
   14–17: Starke Zugkraft (Burnout, Digitalisierung ePA, Bürokratie, kontroverse Therapie häufige Erkrankung).
   9–13: Moderate Zugkraft (Leitlinien-Update, Kongressbericht, Fortbildung).
   4–8: Geringe Zugkraft (seltene Erkrankung ohne Medienkontext, Nischenthema <5% Ärzte).
   0–3: Keine Zugkraft.

4. Neuigkeitswert (0–16): Bringt das genuinely neue Information?
   14–16: Erstmalig, überraschend oder paradigmenwechselnd (Erstpublikation, unerwartetes Ergebnis, First-in-Class, exklusive Recherche).
   10–13: Relevantes Update (Phase-III nach Phase-II, Zulassung, neue Leitlinienversion, neuer Blickwinkel).
   5–9: Bestätigung oder Zusammenfassung (bekannte Praxis bestätigt, Übersichtsartikel).
   0–4: Nichts Neues (redundante Berichterstattung).

5. Quellenautorität (0–12): Wie vertrauenswürdig ist die Quelle?
   11–12: NEJM, Lancet, JAMA, BMJ, Nature Medicine, Nature, Science, Cochrane, BfArM, EMA, FDA, RKI, WHO.
   9–10: Führende Fachjournale (Circulation, JCO, EHJ, Annals), Ärzteblatt Originalbeitrag, offizielle Fachgesellschaften.
   7–8: Solide Fachjournale IF>5, Ärzte Zeitung eigene Recherche, Pharmazeutische Zeitung, Medscape.
   5–6: Peer-reviewed IF 2–5, Kongressabstracts großer Kongresse.
   3–4: Niedrig-IF Journale, Preprints.
   0–2: Pressemitteilungen, Unternehmens-PR, Blogs.

6. Aufbereitungsqualität (0–12): Wie gut für Ärzte aufbereitet?
   11–12: Exzellent (Kernbotschaft sofort, klinische Implikationen explizit, NNT/ARR, strukturiert, Praxistipps).
   8–10: Gut (strukturiertes Abstract, Endpunkte klar, gut lesbar).
   5–7: Akzeptabel (fachlich korrekt aber sperrig, keine klinische Einordnung).
   2–4: Mangelhaft (schwer zugänglich, Paywall ohne Abstract).
   0–1: Nicht verwertbar (kein Inhalt zugänglich).

WICHTIGE REGELN:
- Wissenschaftliche Studien und journalistische Artikel werden auf DERSELBEN Skala bewertet.
- Ein investigativer Ärzteblatt-Beitrag KANN denselben Score erreichen wie eine NEJM-Studie.
- Bewerte die QUALITÄT der Beweisführung, nicht den Studientyp.
- Quellenautorität ist ein Vertrauenssignal (max 12 Punkte), kein dominanter Faktor.
- Zugkraft misst Engagement-Potenzial bei Ärzten, nicht klinische Wichtigkeit.

KALIBRIERUNGS-ANKER (A–H):
A) NEJM Meta-Analyse, neue Erstlinientherapie Diabetes: ~87 (H:19 E:19 Z:15 N:15 Q:12 A:7)
B) Ärzteblatt investigativ, Krankenhausreform-Folgen für Ärzte: ~84 (H:17 E:16 Z:19 N:12 Q:9 A:11)
C) Rote-Hand-Brief häufiges Medikament (Ärzte Zeitung): ~81 (H:20 E:11 Z:18 N:16 Q:7 A:9)
D) Case Report seltene UAW, Nischenjournal: ~31 (H:4 E:5 Z:4 N:8 Q:4 A:6)
E) Pharma-Pressemitteilung Phase II Onkologie: ~30 (H:3 E:4 Z:7 N:11 Q:1 A:4)
F) Nature Medicine Grundlagenforschung Alzheimer: ~69 (H:5 E:18 Z:14 N:15 Q:12 A:5)
G) Ärzteblatt CME Herzinsuffizienz: ~65 (H:14 E:13 Z:11 N:6 Q:9 A:12)
H) Medscape Burnout-Umfrage Klinikärzte: ~66 (H:8 E:12 Z:18 N:11 Q:7 A:10)"""


def _build_scoring_prompt(article: Article) -> str:
    """Build the v2 user message for LLM scoring.

    Uses template variables from docs/scoring-v2.md:
    {{source}}, {{journal}}, {{title}}, {{abstract}}, {{date}}, {{doi}}
    Plus {{FEEDBACK_EXAMPLES}} placeholder.
    """
    # Build feedback examples block
    few_shot_block = ""
    few_shot = _get_feedback_examples()
    if few_shot:
        # few_shot is a list of message dicts — we don't inline them here
        # (they're injected as separate messages), so leave placeholder empty
        pass

    prompt = (
        f"{{{{FEEDBACK_EXAMPLES}}}}\n\n"
        f"ARTIKEL:\n"
        f"Quelle: {article.source or ''}\n"
        f"Journal: {article.journal or ''}\n"
        f"Titel: {article.title or ''}\n"
        f"Abstract/Text: {(article.abstract or '')[:2000]}\n"
        f"Datum: {article.pub_date.isoformat() if article.pub_date else ''}\n"
        f"DOI: {article.doi or ''}\n\n"
        f'Antworte AUSSCHLIESSLICH in diesem JSON-Format:\n'
        f'{{\n'
        f'  "scores": {{\n'
        f'    "clinical_action_relevance": {{"score": 0, "reason": ""}},\n'
        f'    "evidence_depth": {{"score": 0, "reason": ""}},\n'
        f'    "topic_appeal": {{"score": 0, "reason": ""}},\n'
        f'    "novelty": {{"score": 0, "reason": ""}},\n'
        f'    "source_authority": {{"score": 0, "reason": ""}},\n'
        f'    "presentation_quality": {{"score": 0, "reason": ""}}\n'
        f'  }},\n'
        f'  "total_score": 0,\n'
        f'  "tier": "TOP|RELEVANT|MONITOR",\n'
        f'  "one_line_summary": "Kernaussage in einem Satz für die Redaktion"\n'
        f'}}'
    )
    return prompt


def _build_scoring_prompt_v1(article: Article) -> str:
    """Build the v1 user message for LLM scoring (backward compat)."""
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


def _parse_llm_score_v1(text: str) -> Optional[dict]:
    """Parse v1 LLM scoring response (5 dimensions, flat JSON).

    Kept for backward compatibility.  Returns ``None`` on parse failure.
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
        logger.warning("Could not parse LLM v1 score JSON: %s", text[:120])
        return None

    dim_keys = [
        "studientyp", "klinische_relevanz", "neuigkeitswert",
        "zielgruppen_fit", "quellenqualitaet",
    ]
    scores = {}
    for key in dim_keys:
        val = data.get(key)
        if val is None:
            logger.warning("LLM v1 score missing dimension: %s", key)
            return None
        scores[key] = max(0, min(20, float(val)))

    total = round(sum(scores.values()), 1)

    breakdown = {
        "scorer": "llm",
        "scoring_version": "v1",
        "studientyp": scores["studientyp"],
        "klinische_relevanz": scores["klinische_relevanz"],
        "neuigkeitswert": scores["neuigkeitswert"],
        "zielgruppen_fit": scores["zielgruppen_fit"],
        "quellenqualitaet": scores["quellenqualitaet"],
        "total": total,
    }

    for key in dim_keys:
        begr_key = f"begr_{key}"
        if begr_key in data and isinstance(data[begr_key], str):
            breakdown[begr_key] = data[begr_key][:200]

    return breakdown


# v2 dimension definitions: field → max score
_V2_DIMS = {
    "clinical_action_relevance": 20,
    "evidence_depth": 20,
    "topic_appeal": 20,
    "novelty": 16,
    "source_authority": 12,
    "presentation_quality": 12,
}


def _parse_llm_score(text: str) -> Optional[dict]:
    """Parse v2 LLM scoring response (6 dimensions, nested JSON).

    Expected format::

        {
          "scores": {
            "clinical_action_relevance": {"score": N, "reason": "..."},
            ...
          },
          "total_score": N,
          "tier": "TOP|RELEVANT|MONITOR",
          "one_line_summary": "..."
        }

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

    scores_obj = data.get("scores")
    if not isinstance(scores_obj, dict):
        # Maybe it's a v1 response — try that parser
        logger.debug("No 'scores' key — trying v1 parser")
        return _parse_llm_score_v1(text)

    dim_scores = {}
    dim_reasons = {}

    for dim_key, dim_max in _V2_DIMS.items():
        dim_data = scores_obj.get(dim_key)
        if not isinstance(dim_data, dict):
            logger.warning("v2 score missing or malformed dimension: %s", dim_key)
            return None
        raw_score = dim_data.get("score")
        if raw_score is None:
            logger.warning("v2 score missing score value for: %s", dim_key)
            return None
        # Cap at dimension max
        dim_scores[dim_key] = max(0, min(dim_max, float(raw_score)))
        reason = dim_data.get("reason", "")
        if isinstance(reason, str):
            dim_reasons[dim_key] = reason[:300]

    # Calculate total from individual scores (don't trust LLM's total)
    total = round(sum(dim_scores.values()), 1)

    # Derive tier from calculated total
    if total >= 70:
        tier = "TOP"
    elif total >= 45:
        tier = "RELEVANT"
    else:
        tier = "MONITOR"

    one_line_summary = ""
    if isinstance(data.get("one_line_summary"), str):
        one_line_summary = data["one_line_summary"][:500]

    breakdown = {
        "scorer": "llm",
        "scoring_version": "v2",
        "scores": {
            dim_key: {
                "score": dim_scores[dim_key],
                "reason": dim_reasons.get(dim_key, ""),
            }
            for dim_key in _V2_DIMS
        },
        "total": total,
        "tier": tier,
        "one_line_summary": one_line_summary,
    }

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
    """Score articles using v2 scoring — LLM primary, rule-based v2 fallback.

    Uses concurrent threads (max 4) when LLM scoring is enabled to
    parallelise API calls.  Falls back to the v2 rule-based scorer for
    individual articles where the LLM fails.

    All newly scored articles get ``scoring_version = "v2"``.
    """
    global _feedback_cache, _feedback_loaded
    from src.config import get_provider_chain

    # Reset feedback cache for this pipeline run
    _feedback_cache = None
    _feedback_loaded = False

    use_llm = bool(get_provider_chain("scoring"))
    llm_count = 0
    rule_count = 0

    def _apply_score(article: Article, llm_result, use_v2_fallback=True):
        """Apply LLM result or fallback to article."""
        nonlocal llm_count, rule_count
        if llm_result is not None:
            score, breakdown = llm_result
            rb_score, _ = compute_relevance_score_v2(article)
            breakdown["rule_based_score"] = rb_score
            article.relevance_score = score
            article.score_breakdown = json.dumps(breakdown)
            article.scoring_version = "v2"
            llm_count += 1
        else:
            score, breakdown = compute_relevance_score_v2(article)
            article.relevance_score = score
            article.score_breakdown = json.dumps(breakdown)
            article.scoring_version = "v2"
            rule_count += 1

    if use_llm and len(articles) > 2:
        # Warm up feedback cache in main thread before spawning workers
        _get_feedback_examples()

        from src.llm_client import map_concurrent

        llm_results = map_concurrent(llm_score_article, articles, max_workers=4)

        for article, llm_result in zip(articles, llm_results):
            _apply_score(article, llm_result)
    else:
        for article in articles:
            llm_result = None
            if use_llm:
                llm_result = llm_score_article(article)
            _apply_score(article, llm_result)

    articles.sort(key=lambda a: a.relevance_score, reverse=True)

    if use_llm:
        logger.info("Scoring v2: %d via LLM, %d via rule-based (concurrent)", llm_count, rule_count)
    else:
        logger.info("Scoring v2: %d articles (rule-based)", rule_count)

    return articles

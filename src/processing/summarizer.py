"""Summarizer with LLM (Claude) + template fallback + highlight tag generator."""

import logging
import re
from typing import Optional

from src.config import (
    SAFETY_KEYWORDS,
    GUIDELINE_KEYWORDS,
    LANDMARK_KEYWORDS,
    SPECIALTY_MESH,
    LLM_MAX_ARTICLES_PER_RUN,
    LLM_SUMMARY_SYSTEM_PROMPT,
)
from src.models import Article

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Title cleaning — strip journal prefixes like [Articles], [Comment], etc.
# ---------------------------------------------------------------------------
_TITLE_PREFIX_RE = re.compile(
    r"^\s*\[[A-Za-z\s]+\]\s*",  # strip any "[Word]" or "[Two Words]" prefix
)


def clean_title(raw_title: str) -> str:
    """Strip journal-specific prefixes like [Articles], [Comment], etc."""
    return _TITLE_PREFIX_RE.sub("", raw_title).strip()


# ---------------------------------------------------------------------------
# Abstract cleaning — split stuck-together section headers
# ---------------------------------------------------------------------------
_SECTION_HEADERS = re.compile(
    r"(Background|Objectives?|Methods?|Results?|Conclusions?|Purpose|"
    r"Introduction|Findings|Interpretation|Aims?|Design|Setting|"
    r"Participants?|Interventions?|Measurements?|Outcomes?|Funding|"
    r"Context|Significance|Importance|Summary|Discussion|"
    r"Trial\s*registration|What\s*is\s*known|What\s*is\s*new|"
    r"Clinical\s*implications|Key\s*(?:points|messages|findings|results)|"
    r"Limitations?|Strengths?|Zusammenfassung|Ergebnisse|Schlussfolgerungen?|"
    r"Methoden|Hintergrund)"
    r"(?=[A-Z])",  # followed by an uppercase letter without space
)


def _clean_abstract(abstract: str) -> str:
    """Fix common abstract formatting issues."""
    if not abstract:
        return ""
    # 1. Handle "word.SectionHeader" → "word. SectionHeader"
    text = re.sub(
        r"(\w)\.(Background|Objectives?|Methods?|Results?|Conclusions?|Purpose|"
        r"Introduction|Findings|Interpretation|Summary|Discussion|"
        r"Significance|Importance|Limitations?|Ergebnisse|Schlussfolgerungen?)",
        r"\1. \2",
        abstract,
    )
    # 2. Handle "SectionHeaderUppercase" → "SectionHeader. Uppercase"
    text = _SECTION_HEADERS.sub(r"\1. ", text)
    # 3. Collapse multiple spaces/periods
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    return text.strip()


# ---------------------------------------------------------------------------
# LLM-based summary generation
# ---------------------------------------------------------------------------


def _validate_summary(raw: str, title: str) -> Optional[str]:
    """Validate and normalise the LLM summary format.

    Expects ``KERN: ...;;;PRAXIS: ...;;;EINORDNUNG: ...``.
    Returns the normalised string or ``None`` if invalid.
    """
    if "KERN:" not in raw:
        logger.warning("LLM response missing KERN: for '%s'", title[:50])
        return None

    # Normalise: ensure ;;; separators (LLMs sometimes use newlines)
    if ";;;" not in raw:
        raw = raw.replace("\nPRAXIS:", ";;;PRAXIS:")
        raw = raw.replace("\nEINORDNUNG:", ";;;EINORDNUNG:")

    return raw


def generate_llm_summary(article: Article) -> Optional[str]:
    """Generate a German summary via LLM.

    Uses the multi-provider chain (Groq/Mistral) with automatic
    Anthropic SDK fallback (handled inside ``cached_chat_completion``).
    Responses are cached for 24 h to avoid redundant API calls.
    Returns ``None`` on failure.
    """
    title = clean_title(article.title or "")
    abstract = _clean_abstract(article.abstract or "")
    journal = article.journal or "Unbekannt"
    study_type = article.study_type or ""

    # Build user message with article context
    user_msg = f"Titel: {title}\n"
    if journal:
        user_msg += f"Journal: {journal}\n"
    if study_type and study_type != "Unbekannt":
        user_msg += f"Studientyp: {study_type}\n"
    if abstract:
        # Truncate very long abstracts to save tokens
        user_msg += f"\nAbstract:\n{abstract[:2000]}"
    else:
        user_msg += "\nKein Abstract verfügbar — fasse basierend auf dem Titel zusammen."

    from src.config import get_provider_chain
    from src.llm_client import cached_chat_completion

    providers = get_provider_chain("summary")
    raw = cached_chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": user_msg}],
        system=LLM_SUMMARY_SYSTEM_PROMPT,
        max_tokens=1024,
    )
    if raw:
        return _validate_summary(raw, title)
    return None


# ---------------------------------------------------------------------------
# Highlight tag generator — "Warum ist dieser Artikel relevant?"
# ---------------------------------------------------------------------------
_TOP_JOURNALS = {"nejm", "lancet", "jama", "bmj", "nature medicine", "nature"}


def generate_highlight_tags(article: Article) -> str:
    """Generate pipe-separated relevance tags explaining why this article matters."""
    tags: list[str] = []
    journal_lower = (article.journal or "").lower()
    text_lower = (
        f"{article.title or ''} {article.abstract or ''} "
        f"{article.study_type or ''}"
    ).lower()

    # 1. Top-Quelle?
    for fragment in _TOP_JOURNALS:
        if fragment in journal_lower:
            nice_name = article.journal or fragment.upper()
            tags.append(f"Top-Quelle: {nice_name}")
            break

    # 1b. German curated source? (only if not already a top journal)
    if not tags:
        _german_sources = {
            "ärzteblatt": "Dt. Ärzteblatt",
            "aerzteblatt": "Dt. Ärzteblatt",
            "ärzte zeitung": "Ärzte Zeitung",
            "aerztezeitung": "Ärzte Zeitung",
            "pharmazeutische zeitung": "Pharm. Zeitung",
        }
        for fragment, label in _german_sources.items():
            if fragment in journal_lower:
                tags.append(f"Fachquelle: {label}")
                break

    # 2. Strong study design?
    strong_designs = {
        "meta-analysis": "Meta-Analyse",
        "meta analysis": "Meta-Analyse",
        "systematic review": "Syst. Review",
        "randomized": "RCT",
        "randomised": "RCT",
        "rct": "RCT",
        "phase iii": "Phase-III-Studie",
        "phase 3": "Phase-III-Studie",
        "cohort": "Kohortenstudie",
        "case-control": "Fall-Kontroll-Studie",
        "cross-sectional": "Querschnittstudie",
        "observational": "Beobachtungsstudie",
    }
    design_tag = None
    for kw, label in strong_designs.items():
        if kw in text_lower:
            design_tag = f"Studientyp: {label}"
            break

    # 2b. Clinical content types (only if no study design detected)
    if not design_tag:
        _clinical_types = [
            (["leitlinie", "guideline", "s3-leitlinie", "awmf",
              "practice guideline"], "Leitlinie"),
            (["clinical review", "klinische übersicht", "narrative review",
              "übersichtsarbeit", "state of the art",
              "current concepts"], "Klinisches Review"),
            (["fachartikel", "fortbildung", "therapieübersicht",
              "aktuelle therapie", "therapie des", "therapie der",
              "behandlung von", "diagnostik und therapie"], "Fachartikel"),
            (["editorial", "perspective", "viewpoint",
              "kommentar"], "Expertenkommentar"),
        ]
        for keywords, label in _clinical_types:
            if any(kw in text_lower for kw in keywords):
                design_tag = f"Artikeltyp: {label}"
                break

    if design_tag:
        tags.append(design_tag)

    # 3. Safety-relevant?
    if any(kw in text_lower for kw in SAFETY_KEYWORDS):
        tags.append("Sicherheitsrelevant")

    # 4. Guideline-relevant?
    if any(kw in text_lower for kw in GUIDELINE_KEYWORDS):
        tags.append("Leitlinien-Relevanz")

    # 5. Breakthrough / Landmark?
    if any(kw in text_lower for kw in LANDMARK_KEYWORDS):
        tags.append("Durchbruch-Studie")

    # 5b. Health policy / professional politics?
    _policy_kw = [
        "krankenhausreform", "gesundheitspolitik", "ärztemangel",
        "honorar", "vergütung", "kbv", "kassenärztlich", "gkv", "pkv",
        "budgetierung", "berufspolitik", "versorgungsstruktur",
        "notfallreform", "klinikreform", "gesundheitsminister",
        "health policy",
    ]
    if any(kw in text_lower for kw in _policy_kw):
        if len(tags) < 3:
            tags.append("Gesundheitspolitik")

    # 5c. Practice relevance?
    _praxis_kw = [
        "therapie", "therapy", "treatment", "behandlung",
        "dosierung", "dosing", "verschreibung", "prescription",
        "first-line", "second-line", "diagnose", "diagnosis",
        "patient care", "patientenversorgung", "klinischer alltag",
        "clinical practice",
    ]
    if any(kw in text_lower for kw in _praxis_kw):
        if len(tags) < 3:
            tags.append("Praxisrelevant")

    # 6. Interdisciplinary?
    hit_count = 0
    for keywords in SPECIALTY_MESH.values():
        if any(kw in text_lower for kw in keywords):
            hit_count += 1
    if hit_count >= 2:
        tags.append("Fachübergreifend")

    # 7. German source?
    if article.language == "de":
        tags.append("Deutsche Quelle")

    # 8. Source-based tag (for articles without other tags)
    source_lower = (article.source or "").lower()
    if not tags:
        if "europe pmc" in source_lower or "medrxiv" in source_lower or "biorxiv" in source_lower:
            tags.append("Peer-Reviewed")
        elif "google news" in source_lower:
            tags.append("Nachrichtenquelle")
        elif "who" in source_lower:
            tags.append("WHO-Bericht")
        elif "rss" in source_lower or any(j in source_lower for j in ["ärzteblatt", "ärztezeitung", "pharma"]):
            tags.append("Fachpresse")

    # 9. Recent publication bonus
    if not tags:
        from datetime import date as date_cls
        if article.pub_date:
            days_old = (date_cls.today() - article.pub_date).days
            if days_old <= 1:
                tags.append("Brandaktuell")
            elif days_old <= 3:
                tags.append("Aktuell")
            else:
                tags.append("Medizinartikel")

    # Keep max 3 most important tags
    return "|".join(tags[:3])


# ---------------------------------------------------------------------------
# Template-based summary generator (fallback)
# ---------------------------------------------------------------------------
def generate_template_summary(article: Article) -> str:
    """Generate a structured summary with ;;; separators.

    Format: KERN: ...;;;DESIGN: ...;;;DETAIL: ...
    KERN = Concise key finding from the abstract (not the title!)
    DETAIL = A *different* supporting sentence adding context.
    """
    abstract = article.abstract or ""
    study = article.study_type or ""
    journal = article.journal or "Unbekannte Quelle"

    text = _clean_abstract(abstract)
    sentences = re.split(r'\.\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 25]

    # Classify sentences into categories
    kern_sent, detail_sent = _pick_kern_and_detail(sentences)

    parts = []

    # KERN: Key finding
    if kern_sent:
        kern = kern_sent.rstrip(".")
        if len(kern) > 200:
            kern = kern[:197] + "..."
        parts.append(f"KERN: {kern}")
    else:
        parts.append(f"KERN: {clean_title(article.title or 'Kein Titel').rstrip('.')}")

    # DESIGN: Study design + source
    if study and study != "Unbekannt":
        parts.append(f"DESIGN: {study} — {journal}")
    else:
        parts.append(f"DESIGN: {journal}")

    # DETAIL: Supporting sentence (must differ from KERN)
    if detail_sent:
        det = detail_sent.rstrip(".")
        if len(det) > 250:
            det = det[:247] + "..."
        parts.append(f"DETAIL: {det}.")
    elif not kern_sent:
        parts.append("DETAIL: Kein Abstract verfügbar — Originalartikel prüfen.")

    return ";;;".join(parts)


def _pick_kern_and_detail(sentences: list) -> tuple:
    """Pick two distinct sentences: one for KERN (key finding) and one for DETAIL.

    Returns (kern_sentence, detail_sentence) — either can be None.
    """
    if not sentences:
        return None, None

    # Keywords indicating result/conclusion (best for KERN)
    result_kw = [
        "conclusion", "conclude", "found that", "showed that",
        "demonstrate", "our results", "these findings", "in summary",
        "this study shows", "our data suggest", "we found",
        "the results indicate", "these data", "we conclude",
        "significantly", "associated with", "effective",
        "ergebnis", "zusammenfassung", "schlussfolgerung",
    ]
    # Background sentences (least useful)
    background_kw = [
        "background", "introduction", "purpose", "little is known",
        "remains unclear", "the aim", "the objective", "we aimed",
        "hintergrund", "ziel der studie", "einleitung",
    ]
    # Methods/design keywords (good for DETAIL)
    methods_kw = [
        "methods", "participants", "patients were", "enrolled",
        "we conducted", "we performed", "trial", "study design",
        "between", "randomised", "randomized", "prospective",
        "retrospective", "follow-up", "median age",
    ]

    # Score each sentence
    scored = []
    for i, sent in enumerate(sentences):
        s_lower = sent.lower()
        r_score = 0
        if any(kw in s_lower for kw in result_kw):
            r_score += 10
        if any(kw in s_lower for kw in background_kw):
            r_score -= 8
        if any(kw in s_lower for kw in methods_kw):
            r_score += 3  # decent for DETAIL
        # Later sentences are often more result-y
        r_score += min(i * 0.5, 3)
        scored.append((r_score, i, sent))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    # KERN = highest-scored sentence (usually a result/conclusion)
    kern_idx = scored[0][1]
    kern_sent = scored[0][2]

    # DETAIL = second-best sentence that's NOT the same as KERN
    detail_sent = None
    for _, idx, sent in scored[1:]:
        if idx != kern_idx:
            detail_sent = sent
            break

    return kern_sent, detail_sent


# ---------------------------------------------------------------------------
# Batch processors
# ---------------------------------------------------------------------------
def summarize_articles(articles: list[Article]) -> list[Article]:
    """Summarize articles: LLM for top-scored, template for the rest.

    LLM summarization runs in parallel (4 concurrent workers) using the
    same ``map_concurrent`` helper that the scorer uses.
    """
    from src.config import get_provider_chain
    from src.llm_client import _get_anthropic_client, map_concurrent

    # Check if any LLM provider is available (multi-provider OR Anthropic)
    has_new_providers = bool(get_provider_chain("summary"))
    has_anthropic = _get_anthropic_client() is not None
    use_llm = has_new_providers or has_anthropic

    if use_llm:
        provider_name = "Multi-Provider" if has_new_providers else "Claude"
        logger.info("%s API available — using LLM for top %d articles",
                     provider_name, LLM_MAX_ARTICLES_PER_RUN)
    else:
        logger.info("No LLM API keys configured — using template summaries only")

    # Split articles into those needing summaries
    needs_summary = [a for a in articles if not a.summary_de]

    # LLM candidates = articles with score >= threshold (saves calls for low-score articles)
    from src.config import SCORE_MIN_LLM_SUMMARY
    if use_llm:
        llm_candidates = [a for a in needs_summary
                          if a.relevance_score >= SCORE_MIN_LLM_SUMMARY][:LLM_MAX_ARTICLES_PER_RUN]
    else:
        llm_candidates = []
    _llm_ids = {a.id for a in llm_candidates}
    template_candidates = [a for a in needs_summary if a.id not in _llm_ids]

    llm_count = 0

    if llm_candidates:
        # Parallel LLM summarization (4 concurrent workers)
        llm_results = map_concurrent(generate_llm_summary, llm_candidates, max_workers=4)

        for article, llm_summary in zip(llm_candidates, llm_results):
            if llm_summary:
                article.summary_de = llm_summary
                llm_count += 1
            else:
                # LLM failed for this article — use template
                template_candidates.append(article)

    # Template fallback for remaining articles
    template_count = 0
    for article in template_candidates:
        article.summary_de = generate_template_summary(article)
        template_count += 1

    logger.info("Summaries: %d via LLM, %d via template", llm_count, template_count)
    return articles


def highlight_articles(articles: list[Article]) -> list[Article]:
    """Generate highlight tags for all articles."""
    for article in articles:
        if not article.highlight_tags:
            article.highlight_tags = generate_highlight_tags(article)
    return articles

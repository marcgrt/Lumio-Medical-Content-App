"""Themen-Radar 2.0: Multi-signal trend detection with AI synthesis.

Identifies trending topics by clustering recent articles using keyword
extraction. Computes momentum, evidence-level tracking, cross-specialty
expansion, and clinical impact scores. Generates German-language smart
labels and trend summaries via Claude Haiku.

Graceful fallback: If sentence-transformers is not installed, uses
keyword-based clustering only.
"""

import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
from sqlmodel import select, col

from src.models import Article, get_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evidence hierarchy (for evidence-level tracking)
# ---------------------------------------------------------------------------
_EVIDENCE_HIERARCHY: dict[str, int] = {
    "meta-analysis": 7, "meta analysis": 7, "systematic review": 7,
    "rct": 6, "randomized": 6, "randomised": 6,
    "leitlinie": 5, "guideline": 5,
    "review": 4, "clinical review": 4, "cohort": 4,
    "case-control": 3, "cross-sectional": 3,
    "case report": 2, "case series": 2,
    "editorial": 1, "news": 1, "opinion": 1,
}

_EVIDENCE_LABEL_MAP: dict[str, str] = {
    "meta-analysis": "Meta-Analyse", "meta analysis": "Meta-Analyse",
    "systematic review": "Systematic Review",
    "rct": "RCT", "randomized": "RCT", "randomised": "RCT",
    "leitlinie": "Leitlinie", "guideline": "Leitlinie",
    "review": "Review", "clinical review": "Review",
    "cohort": "Kohorte",
    "case-control": "Fall-Kontroll", "cross-sectional": "Querschnitt",
    "case report": "Fallbericht", "case series": "Fallserie",
    "editorial": "Editorial", "news": "News", "opinion": "Meinung",
}


@dataclass
class TrendCluster:
    """A detected trending topic cluster with multi-signal intelligence."""

    topic_label: str  # e.g. "GLP-1 + Herzinsuffizienz"
    article_ids: list[int] = field(default_factory=list)
    count_current: int = 0
    count_previous: int = 0
    growth_rate: float = 0.0
    avg_score: float = 0.0
    top_journals: list[str] = field(default_factory=list)
    trend_summary_de: str = ""
    specialties: list[str] = field(default_factory=list)

    # Smart Labels (Claude-generiert)
    smart_label_de: str = ""          # "GLP-1 erobert die Nephrologie"
    warum_wichtig_de: str = ""        # 1 Satz: Warum sollte ein Arzt das wissen?

    # Multi-Signal Intelligence
    avg_journal_score: float = 0.0    # avg score_breakdown["journal"]
    avg_design_score: float = 0.0     # avg score_breakdown["design"]
    avg_arztrelevanz: float = 0.0     # avg score_breakdown["arztrelevanz"]
    high_tier_count: int = 0          # Artikel aus Top-Quellen
    high_tier_ratio: float = 0.0      # Anteil Top-Quellen-Artikel

    # Momentum (3-Perioden-Vergleich)
    momentum: str = "stable"          # "exploding" | "rising" | "stable" | "falling"
    velocity: float = 0.0             # Beschleunigung des Wachstums
    count_period_minus2: int = 0      # Artikel Tage 15-21

    # Evidenz-Level Tracking
    evidence_levels: dict = field(default_factory=dict)  # {"RCT": 3, "Meta-Analyse": 1}
    evidence_trend: str = "stable"    # "rising" | "stable" | "falling"
    dominant_study_type: str = ""

    # Cross-Specialty Detection
    is_cross_specialty: bool = False
    specialty_spread: str = ""        # "Von Kardiologie nach Nephrologie"
    specialty_counts: dict = field(default_factory=dict)  # {"Kardiologie": 5}

    # Clinical Impact Signal
    clinical_impact_score: float = 0.0

    # Rang
    rank: int = 0                     # 1 = Hero


# ---------------------------------------------------------------------------
# Article fetching
# ---------------------------------------------------------------------------

def _get_recent_articles(days: int = 7) -> list[Article]:
    """Fetch articles from the last N days."""
    cutoff = date.today() - timedelta(days=days)
    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.pub_date >= cutoff)
            .order_by(col(Article.relevance_score).desc())
        )
        articles = session.exec(stmt).all()
        # Detach from session — include score_breakdown for signal analysis
        return [
            Article(
                id=a.id, title=a.title, abstract=a.abstract, url=a.url,
                source=a.source, journal=a.journal, pub_date=a.pub_date,
                relevance_score=a.relevance_score, specialty=a.specialty,
                summary_de=a.summary_de, highlight_tags=a.highlight_tags,
                mesh_terms=a.mesh_terms, study_type=a.study_type,
                status=a.status, authors=a.authors, doi=a.doi,
                score_breakdown=a.score_breakdown,
            )
            for a in articles
        ]


def _get_previous_articles(days: int = 7) -> list[Article]:
    """Fetch articles from the period before 'recent' (e.g. days 8-14)."""
    end = date.today() - timedelta(days=days)
    start = end - timedelta(days=days)
    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.pub_date >= start)
            .where(Article.pub_date < end)
        )
        articles = session.exec(stmt).all()
        return [
            Article(
                id=a.id, title=a.title, abstract=a.abstract, url=a.url,
                source=a.source, journal=a.journal, pub_date=a.pub_date,
                relevance_score=a.relevance_score, specialty=a.specialty,
                mesh_terms=a.mesh_terms, study_type=a.study_type,
                score_breakdown=a.score_breakdown,
            )
            for a in articles
        ]


def _get_period_minus2_articles(days: int = 7) -> list[Article]:
    """Fetch articles from 2 periods ago (e.g. days 15-21) for velocity."""
    end = date.today() - timedelta(days=days * 2)
    start = end - timedelta(days=days)
    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.pub_date >= start)
            .where(Article.pub_date < end)
        )
        articles = session.exec(stmt).all()
        return [
            Article(
                id=a.id, title=a.title, mesh_terms=a.mesh_terms,
                specialty=a.specialty,
            )
            for a in articles
        ]


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

# Medical terms to look for (drug classes, conditions, procedures, policy)
# NOTE: "cancer" alone is too generic — use specific cancer types instead.
# NOTE: Short keywords (≤4 chars) use word-boundary matching to avoid
#       false positives (e.g. "ki" matching "kidney", "skin", "making").
_MEDICAL_ENTITIES = [
    # Drug classes
    "sglt2", "glp-1", "semaglutide", "tirzepatide", "ozempic",
    "empagliflozin", "dapagliflozin", "car-t", "checkpoint inhibitor",
    "immunotherapy", "mrna", "vaccine", "antibiotic", "statin",
    "ace inhibitor", "beta blocker", "insulin", "metformin",
    "pembrolizumab", "nivolumab", "rituximab", "trastuzumab",
    # Conditions — specific, not overly broad
    "heart failure", "herzinsuffizienz", "diabetes", "hypertension",
    "obesity", "adipositas", "stroke", "schlaganfall",
    "copd", "asthma", "sepsis", "covid", "influenza",
    "alzheimer", "parkinson", "depression",
    "atrial fibrillation", "vorhofflimmern", "myocardial infarction",
    "breast cancer", "lung cancer", "colorectal cancer", "prostate cancer",
    "leukemia", "lymphoma", "melanoma", "pancreatic cancer",
    "ovarian cancer", "hepatocellular carcinoma",
    # Procedures / tech — no "ki" (too short, matches kidney/skin/etc.)
    "künstliche intelligenz", "artificial intelligence",
    "machine learning", "deep learning", "ki-gestützt", "ki-basiert",
    "telemedicine", "telemedizin", "biomarker",
    "gene therapy", "gentherapie", "crispr", "genome editing",
    "clinical trial",
    "meta-analysis", "systematic review",
    # Gesundheitspolitik & Versorgung (für deutsche Ärzte hochrelevant)
    "krankenhausreform", "klinikreform", "gesundheitspolitik",
    "ärztemangel", "ärztestreik", "physician shortage",
    "notfallreform", "notaufnahme", "notfallversorgung",
    "budgetierung", "honorar", "vergütung", "arzthaftung",
    "digitalisierung", "elektronische patientenakte",
    "leitlinie", "guideline",
    # Screening & Prävention
    "screening", "vorsorge", "prävention", "impfung", "impfpflicht",
    # Psychische Gesundheit (breiteres Spektrum)
    "burnout", "angststörung", "psychotherapie",
    # Antibiotikaresistenz (globales Thema)
    "antibiotikaresistenz", "antimicrobial resistance", "mrsa",
]

# Keywords that need word-boundary matching (short or ambiguous terms)
_WORD_BOUNDARY_KEYWORDS = {
    "mrna", "copd", "sglt2", "mrsa",
}


def _extract_keywords(article: Article) -> list[str]:
    """Extract medical keywords from article text.

    Uses word-boundary matching for short/ambiguous keywords to prevent
    false positives (e.g. "ki" in "kidney").
    """
    text = " ".join(
        (field or "").lower()
        for field in [
            article.title, article.abstract,
            article.mesh_terms, article.highlight_tags,
        ]
    )
    found = []
    for kw in _MEDICAL_ENTITIES:
        if kw in _WORD_BOUNDARY_KEYWORDS:
            # Word-boundary match: check that chars before/after are not letters
            idx = text.find(kw)
            while idx != -1:
                before_ok = (idx == 0 or not text[idx - 1].isalpha())
                after_pos = idx + len(kw)
                after_ok = (after_pos >= len(text) or not text[after_pos].isalpha())
                if before_ok and after_ok:
                    found.append(kw)
                    break
                idx = text.find(kw, idx + 1)
        else:
            if kw in text:
                found.append(kw)
    return found


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def _cluster_by_keywords(
    articles: list[Article],
    min_cluster_size: int = 3,
    max_cluster_size: int = 40,
) -> list[TrendCluster]:
    """Cluster articles by co-occurring medical keywords.

    Prefers specific keywords over broad ones: sorts by "sweet spot"
    score that favors clusters of 5-25 articles over mega-clusters.
    max_cluster_size caps any single cluster to prevent domination.
    """
    # Count keyword frequency
    kw_articles: dict[str, list[Article]] = {}
    for a in articles:
        kws = _extract_keywords(a)
        for kw in kws:
            kw_articles.setdefault(kw, []).append(a)

    # Filter to keywords with enough articles
    clusters = []
    seen_article_ids: set[int] = set()

    # Sort by specificity sweet-spot: prefer 5-25 articles over mega-clusters
    # Score: penalize both too small (< 5) and too large (> 30) clusters
    def _specificity_score(count):
        if count < min_cluster_size:
            return -1
        if count <= 25:
            return count  # prefer bigger within sweet spot
        return 25 - (count - 25) * 0.3  # penalize mega-clusters

    sorted_kws = sorted(
        kw_articles.items(),
        key=lambda x: _specificity_score(len(x[1])),
        reverse=True,
    )

    for kw, arts in sorted_kws:
        if len(arts) < min_cluster_size:
            continue

        # Deduplicate articles already assigned to a higher-priority cluster
        unique_arts = [a for a in arts if a.id not in seen_article_ids]
        if len(unique_arts) < min_cluster_size:
            continue

        # Cap cluster size: take highest-scored articles
        if len(unique_arts) > max_cluster_size:
            unique_arts = sorted(
                unique_arts, key=lambda a: a.relevance_score, reverse=True
            )[:max_cluster_size]

        # Find secondary keywords for better label
        sub_kws = Counter()
        for a in unique_arts:
            for skw in _extract_keywords(a):
                if skw != kw:
                    sub_kws[skw] += 1

        # Build topic label
        label = kw.replace("_", " ").title()
        if sub_kws:
            top_sub = sub_kws.most_common(1)[0]
            if top_sub[1] >= 2:
                label = f"{label} + {top_sub[0].replace('_', ' ').title()}"

        # Specialty distribution
        specs = [a.specialty for a in unique_arts if a.specialty]
        spec_counts = Counter(specs)

        # Top journals
        journals = [a.journal for a in unique_arts if a.journal]
        journal_counts = Counter(journals)

        cluster = TrendCluster(
            topic_label=label,
            article_ids=[a.id for a in unique_arts],
            count_current=len(unique_arts),
            avg_score=round(
                sum(a.relevance_score for a in unique_arts) / len(unique_arts), 1
            ),
            top_journals=[j for j, _ in journal_counts.most_common(3)],
            specialties=[s for s, _ in spec_counts.most_common(3)],
            specialty_counts={s: c for s, c in spec_counts.items()},
        )
        clusters.append(cluster)

        for a in unique_arts:
            seen_article_ids.add(a.id)

    return clusters


def _cluster_by_embeddings(
    articles: list[Article],
    min_cluster_size: int = 3,
    similarity_threshold: float = 0.45,
) -> list[TrendCluster]:
    """Cluster articles using sentence-transformer embeddings + agglomerative clustering."""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import AgglomerativeClustering
    except ImportError:
        logger.debug("sentence-transformers/sklearn not installed — using keyword clustering")
        return _cluster_by_keywords(articles, min_cluster_size)

    if len(articles) < min_cluster_size:
        return []

    # Generate embeddings
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [
        f"{a.title or ''} {(a.abstract or '')[:500]}"
        for a in articles
    ]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms

    # Agglomerative clustering with cosine distance
    distance_threshold = 1.0 - similarity_threshold
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(normalized)

    # Group articles by cluster
    cluster_map: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        cluster_map.setdefault(int(label), []).append(idx)

    clusters = []
    for cluster_id, indices in cluster_map.items():
        if len(indices) < min_cluster_size:
            continue

        cluster_articles = [articles[i] for i in indices]

        # Generate label from most common keywords
        all_kws = Counter()
        for a in cluster_articles:
            for kw in _extract_keywords(a):
                all_kws[kw] += 1

        if all_kws:
            top_kws = all_kws.most_common(2)
            label = " + ".join(kw.replace("_", " ").title() for kw, _ in top_kws)
        else:
            # Fallback: use most common words from titles
            title_words = Counter()
            for a in cluster_articles:
                for word in (a.title or "").lower().split():
                    if len(word) > 4:
                        title_words[word] += 1
            top_words = title_words.most_common(2)
            label = " + ".join(w.title() for w, _ in top_words) if top_words else f"Thema {cluster_id + 1}"

        specs = [a.specialty for a in cluster_articles if a.specialty]
        spec_counts = Counter(specs)
        journals = [a.journal for a in cluster_articles if a.journal]

        cluster = TrendCluster(
            topic_label=label,
            article_ids=[a.id for a in cluster_articles],
            count_current=len(cluster_articles),
            avg_score=round(
                sum(a.relevance_score for a in cluster_articles) / len(cluster_articles), 1
            ),
            top_journals=[j for j, _ in Counter(journals).most_common(3)],
            specialties=[s for s, _ in Counter(specs).most_common(3)],
            specialty_counts={s: c for s, c in spec_counts.items()},
        )
        clusters.append(cluster)

    # Sort by article count (biggest clusters first)
    clusters.sort(key=lambda c: c.count_current, reverse=True)
    return clusters


# ---------------------------------------------------------------------------
# Multi-Signal Score Analysis (Schritt 2b)
# ---------------------------------------------------------------------------

def _compute_signal_scores(cluster: TrendCluster, articles: list[Article]):
    """Parse score_breakdown JSON and compute avg journal/design/arztrelevanz scores."""
    journal_scores = []
    design_scores = []
    arztrelevanz_scores = []
    high_tier = 0

    for a in articles:
        if not a.score_breakdown:
            continue
        try:
            bd = json.loads(a.score_breakdown)
        except (json.JSONDecodeError, TypeError):
            continue

        j = bd.get("journal", 0.0)
        d = bd.get("design", 0.0)
        ar = bd.get("arztrelevanz", 0.0)

        journal_scores.append(j)
        design_scores.append(d)
        arztrelevanz_scores.append(ar)

        # High-tier: journal weighted score >= 23 (top journals with WEIGHT_JOURNAL=0.30)
        if j >= 23:
            high_tier += 1

    n = len(articles) or 1
    cluster.avg_journal_score = round(sum(journal_scores) / max(len(journal_scores), 1), 1)
    cluster.avg_design_score = round(sum(design_scores) / max(len(design_scores), 1), 1)
    cluster.avg_arztrelevanz = round(sum(arztrelevanz_scores) / max(len(arztrelevanz_scores), 1), 1)
    cluster.high_tier_count = high_tier
    cluster.high_tier_ratio = round(high_tier / n, 2)


# ---------------------------------------------------------------------------
# Momentum & Velocity (Schritt 2c)
# ---------------------------------------------------------------------------

def _compute_growth_rates(
    clusters: list[TrendCluster],
    previous_articles: list[Article],
    period_minus2_articles: list[Article],
):
    """Compute growth rates + momentum using 3-period comparison."""
    prev_kws: dict[str, int] = Counter()
    for a in previous_articles:
        for kw in _extract_keywords(a):
            prev_kws[kw] += 1

    p2_kws: dict[str, int] = Counter()
    for a in period_minus2_articles:
        for kw in _extract_keywords(a):
            p2_kws[kw] += 1

    for cluster in clusters:
        label_parts = cluster.topic_label.lower().split(" + ")

        # Previous period count
        prev_count = 0
        for part in label_parts:
            part_clean = part.strip()
            prev_count = max(prev_count, prev_kws.get(part_clean, 0))

        # Period minus 2 count
        p2_count = 0
        for part in label_parts:
            part_clean = part.strip()
            p2_count = max(p2_count, p2_kws.get(part_clean, 0))

        cluster.count_previous = prev_count
        cluster.count_period_minus2 = p2_count

        # Growth rate (current vs previous)
        if prev_count > 0:
            cluster.growth_rate = round(cluster.count_current / prev_count, 2)
        else:
            cluster.growth_rate = float(cluster.count_current)  # new topic

        # Previous growth rate (previous vs period_minus2)
        if p2_count > 0:
            prev_growth = prev_count / p2_count
        else:
            prev_growth = float(prev_count) if prev_count > 0 else 1.0

        # Velocity = acceleration of growth
        cluster.velocity = round(cluster.growth_rate - prev_growth, 2)

        # Momentum classification
        is_new = cluster.count_previous == 0 and cluster.count_current >= 3
        if is_new or cluster.growth_rate >= 3.0 or (cluster.growth_rate >= 2.0 and cluster.velocity > 0.5):
            cluster.momentum = "exploding"
        elif cluster.growth_rate >= 1.3 or cluster.velocity > 0.2:
            cluster.momentum = "rising"
        elif cluster.growth_rate <= 0.5 and cluster.count_previous > 0:
            cluster.momentum = "falling"
        else:
            cluster.momentum = "stable"


# ---------------------------------------------------------------------------
# Evidence-Level Tracking (Schritt 2d)
# ---------------------------------------------------------------------------

def _detect_study_type(article: Article) -> tuple[str, int]:
    """Detect the highest evidence level term in an article. Returns (label, score)."""
    text = f"{article.title or ''} {article.abstract or ''} {article.study_type or ''}".lower()
    best_label = ""
    best_score = 0
    for term, score in _EVIDENCE_HIERARCHY.items():
        if term in text and score > best_score:
            best_score = score
            best_label = _EVIDENCE_LABEL_MAP.get(term, term.title())
    return best_label, best_score


def _compute_evidence_levels(
    cluster: TrendCluster,
    current_articles: list[Article],
    previous_articles: list[Article],
):
    """Count study types in cluster, detect dominant type and evidence trend."""
    # Current period evidence
    level_counts: dict[str, int] = Counter()
    current_scores = []
    for a in current_articles:
        label, score = _detect_study_type(a)
        if label:
            level_counts[label] += 1
            current_scores.append(score)

    cluster.evidence_levels = dict(level_counts)

    # Dominant study type
    if level_counts:
        cluster.dominant_study_type = level_counts.most_common(1)[0][0]

    # Compare average evidence level with previous period
    prev_cluster_ids = set()
    label_parts = cluster.topic_label.lower().split(" + ")
    for a in previous_articles:
        kws = _extract_keywords(a)
        if any(part.strip() in kws for part in label_parts):
            prev_cluster_ids.add(a.id)

    prev_scores = []
    for a in previous_articles:
        if a.id in prev_cluster_ids:
            _, score = _detect_study_type(a)
            if score > 0:
                prev_scores.append(score)

    avg_current = sum(current_scores) / max(len(current_scores), 1)
    avg_prev = sum(prev_scores) / max(len(prev_scores), 1)

    if avg_current > avg_prev + 0.5 and current_scores:
        cluster.evidence_trend = "rising"
    elif avg_current < avg_prev - 0.5 and prev_scores:
        cluster.evidence_trend = "falling"
    else:
        cluster.evidence_trend = "stable"


# ---------------------------------------------------------------------------
# Cross-Specialty Detection (Schritt 2e)
# ---------------------------------------------------------------------------

def _compute_cross_specialty(
    cluster: TrendCluster,
    current_articles: list[Article],
    previous_articles: list[Article],
):
    """Detect cross-specialty expansion."""
    # Current specialties
    curr_specs = Counter(a.specialty for a in current_articles if a.specialty)
    cluster.specialty_counts = dict(curr_specs)
    cluster.is_cross_specialty = len(curr_specs) >= 2

    if not cluster.is_cross_specialty:
        return

    # Previous specialties for this topic
    label_parts = cluster.topic_label.lower().split(" + ")
    prev_specs = Counter()
    for a in previous_articles:
        kws = _extract_keywords(a)
        if any(part.strip() in kws for part in label_parts) and a.specialty:
            prev_specs[a.specialty] += 1

    # Detect expansion: new specialties this week
    new_specs = set(curr_specs.keys()) - set(prev_specs.keys())
    old_specs = set(prev_specs.keys())

    if new_specs and old_specs:
        old_main = max(old_specs, key=lambda s: prev_specs.get(s, 0))
        new_main = max(new_specs, key=lambda s: curr_specs.get(s, 0))
        cluster.specialty_spread = f"Von {old_main} nach {new_main}"
    elif len(curr_specs) >= 2:
        top2 = curr_specs.most_common(2)
        cluster.specialty_spread = f"{top2[0][0]} + {top2[1][0]}"


# ---------------------------------------------------------------------------
# Clinical Impact Signal (Schritt 2f)
# ---------------------------------------------------------------------------

def _compute_clinical_impact(cluster: TrendCluster, articles: list[Article]):
    """Compute clinical impact from arztrelevanz."""
    if not articles:
        return
    # Scale weighted arztrelevanz score back to 0-100
    cluster.clinical_impact_score = round(cluster.avg_arztrelevanz * 10, 1)


# ---------------------------------------------------------------------------
# LLM trend synthesis (Schritt 2g — upgraded)
# ---------------------------------------------------------------------------

def _generate_trend_summary_v2(cluster: TrendCluster, articles: list[Article]):
    """Generate smart_label + warum_wichtig + trend_summary via single LLM call."""

    # Build article context
    article_list = "\n".join(
        f"- {a.title} ({a.journal or 'Unbekannt'}, Score {a.relevance_score:.0f})"
        for a in articles[:8]
    )

    # Momentum context
    momentum_text = {
        "exploding": "stark steigend",
        "rising": "steigend",
        "stable": "stabil",
        "falling": "rückläufig",
    }.get(cluster.momentum, "stabil")

    growth_text = ""
    if cluster.count_previous > 0:
        growth_text = f"Vorwoche: {cluster.count_previous} Artikel, diese Woche: {cluster.count_current} ({momentum_text})."
    else:
        growth_text = f"Neues Thema diese Woche mit {cluster.count_current} Artikeln."

    evidence_text = ""
    if cluster.evidence_levels:
        ev_parts = [f"{k}: {v}" for k, v in sorted(cluster.evidence_levels.items(), key=lambda x: -x[1])]
        evidence_text = f"Studientypen: {', '.join(ev_parts[:4])}"

    cross_text = ""
    if cluster.is_cross_specialty and cluster.specialty_spread:
        cross_text = f"Cross-Specialty: {cluster.specialty_spread}"

    prompt = f"""Du bist ein medizinischer Trendanalyst. Analysiere den folgenden Thementrend.

Thema: {cluster.topic_label}
Fachgebiete: {', '.join(cluster.specialties) or 'Diverse'}
{growth_text}
{evidence_text}
{cross_text}
Durchschnittlicher Relevanz-Score: {cluster.avg_score:.0f}/100
Top-Quellen: {', '.join(cluster.top_journals[:3]) or 'Diverse'}

Artikel:
{article_list}

Antworte EXAKT in diesem Format (3 Teile getrennt durch ;;;):
LABEL: [Catchy 3-6 Wort Trendname auf Deutsch, z.B. "GLP-1 erobert die Nephrologie"];;;WICHTIG: [1 Satz: Warum sollte ein praktizierender Arzt das wissen?];;;ZUSAMMENFASSUNG: [2 Sätze: Was ist der Trend + Was bedeutet das klinisch?]"""

    # ------------------------------------------------------------------
    # Multi-provider + Anthropic fallback (with 24 h cache)
    # ------------------------------------------------------------------
    from src.config import get_provider_chain
    from src.llm_client import cached_chat_completion

    providers = get_provider_chain("trend_summary")
    text = cached_chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
    )

    # ------------------------------------------------------------------
    # Parse or fall back to template
    # ------------------------------------------------------------------
    if text is None:
        _fallback_summary_v2(cluster, articles)
        return

    parts = text.split(";;;")
    for part in parts:
        part = part.strip()
        if part.upper().startswith("LABEL:"):
            cluster.smart_label_de = part[6:].strip().strip('"')
        elif part.upper().startswith("WICHTIG:"):
            cluster.warum_wichtig_de = part[8:].strip()
        elif part.upper().startswith("ZUSAMMENFASSUNG:"):
            cluster.trend_summary_de = part[16:].strip()

    # Fallback if parsing failed
    if not cluster.smart_label_de:
        cluster.smart_label_de = cluster.topic_label
    if not cluster.trend_summary_de:
        cluster.trend_summary_de = text  # use full response


def _fallback_summary_v2(cluster: TrendCluster, articles: list[Article]):
    """Template-based trend outputs when LLM is unavailable."""
    topic = cluster.topic_label
    count = cluster.count_current
    specs = ", ".join(cluster.specialties[:2]) or "diverse Fachgebiete"
    journals = ", ".join(cluster.top_journals[:2]) or "verschiedene Quellen"

    # Smart label = topic label as-is
    cluster.smart_label_de = topic

    # Warum wichtig
    if cluster.momentum == "exploding":
        cluster.warum_wichtig_de = f"Stark steigendes Thema mit {count} neuen Artikeln — klinische Relevanz prüfen."
    elif cluster.is_cross_specialty:
        cluster.warum_wichtig_de = f"Thema breitet sich über Fachgrenzen aus ({cluster.specialty_spread})."
    elif cluster.dominant_study_type in ("Meta-Analyse", "RCT", "Leitlinie"):
        cluster.warum_wichtig_de = f"Hochwertige Evidenz ({cluster.dominant_study_type}) — praxisrelevant."
    else:
        cluster.warum_wichtig_de = f"{count} aktuelle Artikel in {specs}."

    # Trend summary
    if cluster.count_previous > 0 and cluster.growth_rate > 1.5:
        cluster.trend_summary_de = (
            f"Deutlicher Anstieg bei {topic}: {count} neue Artikel "
            f"(Vorwoche: {cluster.count_previous}). "
            f"Schwerpunkt in {specs}, publiziert u.a. in {journals}."
        )
    elif cluster.count_previous == 0:
        cluster.trend_summary_de = (
            f"Neues Trendthema {topic} mit {count} Artikeln. "
            f"Betrifft {specs}, erschienen in {journals}."
        )
    else:
        cluster.trend_summary_de = (
            f"{count} Artikel zu {topic} diese Woche. "
            f"Erschienen in {journals}, Schwerpunkt {specs}."
        )


# ---------------------------------------------------------------------------
# Weekly overview (Schritt 2h)
# ---------------------------------------------------------------------------

def _generate_weekly_overview(clusters: list[TrendCluster]) -> str:
    """Generate 1-sentence German weekly overview via LLM."""
    if not clusters:
        return ""

    cluster_list = "\n".join(
        f"- {c.smart_label_de or c.topic_label} ({c.count_current} Art., "
        f"Momentum: {c.momentum}, Score: {c.avg_score:.0f})"
        for c in clusters[:6]
    )

    prompt = f"""Fasse diese medizinischen Wochentrends in EXAKT 1 Satz auf Deutsch zusammen.
Der Satz soll die 1-2 wichtigsten Trends hervorheben und die Woche einordnen.

Trends:
{cluster_list}

Beispiel: "Diese Woche dominiert GLP-1 in der Nephrologie, während neue Leitlinien zur Herzinsuffizienz die Praxis verändern."

Antworte mit genau 1 Satz:"""

    # ------------------------------------------------------------------
    # Multi-provider + Anthropic fallback (with 24 h cache)
    # ------------------------------------------------------------------
    from src.config import get_provider_chain
    from src.llm_client import cached_chat_completion

    providers = get_provider_chain("weekly_overview")
    text = cached_chat_completion(
        providers=providers,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
    )
    if text:
        return text

    return _fallback_weekly_overview(clusters)


def _fallback_weekly_overview(clusters: list[TrendCluster]) -> str:
    """Template-based weekly overview."""
    if not clusters:
        return ""
    top = clusters[0]
    name = top.smart_label_de or top.topic_label
    if len(clusters) >= 2:
        second = clusters[1]
        name2 = second.smart_label_de or second.topic_label
        return f"Diese Woche dominiert {name} ({top.count_current} Artikel), gefolgt von {name2}."
    return f"Im Fokus diese Woche: {name} mit {top.count_current} neuen Artikeln."


# ---------------------------------------------------------------------------
# Public API (Schritt 2i)
# ---------------------------------------------------------------------------

def compute_trends(
    days: int = 7,
    min_cluster_size: int = 3,
    use_embeddings: bool = True,
    max_clusters: int = 8,
) -> tuple[list[TrendCluster], str]:
    """Compute trending topics from recent articles.

    Returns (clusters sorted by composite score, weekly_overview string).
    """
    current = _get_recent_articles(days)
    if len(current) < min_cluster_size:
        logger.info("Not enough recent articles (%d) for trend detection", len(current))
        return [], ""

    previous = _get_previous_articles(days)
    period_minus2 = _get_period_minus2_articles(days)
    logger.info(
        "Trend detection: %d current, %d previous, %d p-2 articles",
        len(current), len(previous), len(period_minus2),
    )

    # Cluster
    if use_embeddings:
        clusters = _cluster_by_embeddings(current, min_cluster_size)
    else:
        clusters = _cluster_by_keywords(current, min_cluster_size)

    if not clusters:
        logger.info("No clusters found")
        return [], ""

    # Compute growth rates + momentum (3-period)
    _compute_growth_rates(clusters, previous, period_minus2)

    # Enrich each cluster with intelligence signals
    for cluster in clusters:
        cluster_articles = [a for a in current if a.id in set(cluster.article_ids)]

        # Multi-signal scores
        _compute_signal_scores(cluster, cluster_articles)

        # Evidence levels
        _compute_evidence_levels(cluster, cluster_articles, previous)

        # Cross-specialty
        _compute_cross_specialty(cluster, cluster_articles, previous)

        # Clinical impact
        _compute_clinical_impact(cluster, cluster_articles)

    # Sort by composite: momentum + clinical_impact + growth + avg_score + volume
    import math
    momentum_weights = {"exploding": 3, "rising": 2, "stable": 1, "falling": 0}
    clusters.sort(
        key=lambda c: (
            momentum_weights.get(c.momentum, 1) * 10
            + c.clinical_impact_score
            + c.growth_rate * 5
            + c.avg_score
            + math.log2(max(c.count_current, 1)) * 3
        ),
        reverse=True,
    )

    # Limit
    clusters = clusters[:max_clusters]

    # Assign ranks
    for i, cluster in enumerate(clusters):
        cluster.rank = i + 1

    # Generate smart summaries (LLM calls)
    for cluster in clusters:
        cluster_articles = [a for a in current if a.id in set(cluster.article_ids)]
        _generate_trend_summary_v2(cluster, cluster_articles)

    # Weekly overview (1 additional LLM call)
    weekly_overview = _generate_weekly_overview(clusters)

    logger.info("Found %d trend clusters", len(clusters))
    return clusters, weekly_overview


def get_trend_articles(article_ids: list[int]) -> list[Article]:
    """Fetch full article objects for a trend cluster."""
    if not article_ids:
        return []
    with get_session() as session:
        stmt = (
            select(Article)
            .where(col(Article.id).in_(article_ids))
            .order_by(col(Article.relevance_score).desc())
        )
        return list(session.exec(stmt).all())

"""Lumio — Helper functions, data access, and rendering utilities."""

import html as html_mod
import json
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import altair as alt
import pandas as pd
import streamlit as st
from sqlmodel import select, func, col

from src.models import Article, get_engine, get_session
from src.config import SPECIALTY_MESH, SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MID
from src.processing.summarizer import clean_title


# ---------------------------------------------------------------------------
# Altair theme — Apple-inspired
# ---------------------------------------------------------------------------
ALTAIR_FONT = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
APPLE_BLUE = "#60a5fa"
APPLE_GREEN = "#4ade80"
APPLE_ORANGE = "#fbbf24"
APPLE_RED = "#f87171"
APPLE_PURPLE = "#a78bfa"
CHART_COLORS = ["#a3e635", "#22d3ee", "#f472b6", "#a78bfa", "#fbbf24",
                 "#60a5fa", "#4ade80", "#fb923c", "#e879f9", "#f87171"]

# Dark-mode Altair axis/view config reusable
DARK_AXIS_CONFIG = alt.AxisConfig(
    labelFontSize=11, gridColor="rgba(255,255,255,0.05)",
    domainColor="rgba(255,255,255,0.08)", labelColor="#8b8ba0",
    titleColor="#a0a0b8",
)
DARK_VIEW_CONFIG = alt.ViewConfig(strokeWidth=0)


# ---------------------------------------------------------------------------
# Specialty colors
# ---------------------------------------------------------------------------
SPECIALTY_COLORS = {
    "Kardiologie": ("#f87171", "rgba(248,113,113,0.10)"),
    "Onkologie": ("#a78bfa", "rgba(167,139,250,0.10)"),
    "Neurologie": ("#60a5fa", "rgba(96,165,250,0.10)"),
    "Diabetologie/Endokrinologie": ("#fbbf24", "rgba(251,191,36,0.10)"),
    "Pneumologie": ("#22d3ee", "rgba(34,211,238,0.10)"),
    "Gastroenterologie": ("#4ade80", "rgba(74,222,128,0.10)"),
    "Infektiologie": ("#fb923c", "rgba(251,146,60,0.10)"),
    "Dermatologie": ("#f472b6", "rgba(244,114,182,0.10)"),
    "Psychiatrie": ("#818cf8", "rgba(129,140,248,0.10)"),
    "Allgemeinmedizin": ("#2dd4bf", "rgba(45,212,191,0.10)"),
    "Orthopädie": ("#8b8ba0", "rgba(139,139,160,0.10)"),
    "Urologie": ("#c084fc", "rgba(192,132,252,0.10)"),
    "Pädiatrie": ("#fb923c", "rgba(251,146,60,0.10)"),
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def _esc(text: str) -> str:
    """HTML-escape user-generated content."""
    if not text:
        return ""
    return html_mod.escape(text, quote=True)


def _detach_article(a: Article) -> Article:
    """Create a detached copy of a session-bound Article."""
    return Article(
        id=a.id, title=a.title, abstract=a.abstract,
        url=a.url, source=a.source, journal=a.journal,
        pub_date=a.pub_date, authors=a.authors, doi=a.doi,
        study_type=a.study_type, mesh_terms=a.mesh_terms,
        language=a.language, relevance_score=a.relevance_score,
        score_breakdown=a.score_breakdown,
        specialty=a.specialty, summary_de=a.summary_de,
        highlight_tags=a.highlight_tags,
        status=a.status, created_at=a.created_at,
        alert_acknowledged_at=a.alert_acknowledged_at,
    )


# ---------------------------------------------------------------------------
# Data access (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=180, show_spinner=False)
def get_articles(
    specialties: Optional[tuple] = None,
    sources: Optional[tuple] = None,
    min_score: float = 0.0,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search_query: str = "",
    status_filter: str = "ALL",
    language: Optional[str] = None,
    study_types: Optional[tuple] = None,
    open_access_only: bool = False,
) -> list[Article]:
    """Query articles with filters. Uses FTS5 for search when available."""
    from src.models import fts5_search
    fts_ids: list = []

    with get_session() as session:
        stmt = select(Article)
        if specialties:
            stmt = stmt.where(col(Article.specialty).in_(specialties))
        if sources:
            stmt = stmt.where(col(Article.source).in_(sources))
        if min_score > 0:
            stmt = stmt.where(Article.relevance_score >= min_score)
        if date_from:
            stmt = stmt.where(Article.pub_date >= date_from)
        if date_to:
            stmt = stmt.where(Article.pub_date <= date_to)

        # Language filter
        if language and language != "Alle":
            lang_code = "de" if language == "Deutsch" else "en"
            stmt = stmt.where(Article.language == lang_code)

        # Study type filter (from highlight_tags)
        if study_types:
            from sqlalchemy import or_
            tag_conditions = [
                col(Article.highlight_tags).contains(f"Studientyp: {st_}")
                for st_ in study_types
            ]
            stmt = stmt.where(or_(*tag_conditions))

        # Open Access filter (URL/journal-based detection)
        if open_access_only:
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    col(Article.url).contains("/pmc/"),
                    col(Article.url).contains("pmc.ncbi"),
                    col(Article.url).contains("europepmc"),
                    col(Article.url).contains("/full"),
                    col(Article.journal).contains("PLOS"),
                    col(Article.journal).contains("BMC "),
                    col(Article.journal).contains("Frontiers"),
                    col(Article.journal).contains("eLife"),
                )
            )

        # Search: FTS5 with BM25 ranking, ILIKE fallback
        if search_query:
            fts_ids = fts5_search(search_query)
            if fts_ids:
                stmt = stmt.where(col(Article.id).in_(fts_ids))
            else:
                pattern = f"%{search_query}%"
                stmt = stmt.where(
                    col(Article.title).ilike(pattern)
                    | col(Article.abstract).ilike(pattern)
                )

        if status_filter and status_filter not in ("ALL", "Alle", "Alle Status"):
            stmt = stmt.where(Article.status == status_filter)

        # Sort by relevance_score unless FTS provides its own ranking
        if not fts_ids:
            stmt = stmt.order_by(col(Article.relevance_score).desc())
        has_filter = (min_score > 0 or specialties or sources or search_query
                      or status_filter != "ALL" or date_from or language
                      or study_types or open_access_only)
        if has_filter:
            stmt = stmt.limit(500)
        else:
            stmt = stmt.limit(2000)  # analytics needs all articles
        articles = session.exec(stmt).all()
        result = [_detach_article(a) for a in articles]

    # Re-sort by BM25 rank if FTS was used
    if fts_ids:
        id_rank = {aid: rank for rank, aid in enumerate(fts_ids)}
        result.sort(key=lambda a: id_rank.get(a.id, 999999))
    else:
        # Decay-based feed ranking: score × time_decay
        # New articles float to the top, old ones sink even if high-scoring
        import math
        _today = date.today()

        def _feed_rank(a):
            score = a.relevance_score or 0
            if a.pub_date:
                age_days = (_today - a.pub_date).days
            else:
                age_days = 30  # unknown date → treat as old
            # Half-life of ~7 days: decay = 0.5^(age/7)
            decay = math.pow(0.5, age_days / 7.0)
            return score * decay

        result.sort(key=_feed_rank, reverse=True)

    return result


def update_article_status(article_id: int, new_status: str):
    """Update article status and log the change."""
    from src.models import StatusChange
    with get_session() as session:
        article = session.get(Article, article_id)
        if article:
            old_status = article.status
            article.status = new_status
            session.add(StatusChange(
                article_id=article_id,
                old_status=old_status,
                new_status=new_status,
            ))
            session.commit()
    # Invalidate caches after status change
    get_articles.clear()
    get_stats.clear()


def acknowledge_alerts(article_ids: list[int]):
    """Persistently mark alerts as acknowledged in the database."""
    with get_session() as session:
        for aid in article_ids:
            article = session.get(Article, aid)
            if article:
                article.alert_acknowledged_at = datetime.now(timezone.utc)
        session.commit()
    get_unacknowledged_alerts.clear()


@st.cache_data(ttl=900, show_spinner=False)
def get_unique_values(column_name: str) -> list[str]:
    """Get distinct non-null values for a column."""
    column = getattr(Article, column_name)
    with get_session() as session:
        results = session.exec(
            select(column).where(column.isnot(None)).distinct()
        ).all()
        return sorted([r for r in results if r])


@st.cache_data(ttl=600, show_spinner=False)
def get_stats() -> dict:
    """Get dashboard statistics (optimised: 3 queries instead of 8)."""
    with get_session() as session:
        # Query 1: grouped counts by status (covers total, approved, rejected,
        #          saved, pending in a single round-trip)
        from sqlalchemy import case as sa_case
        row = session.exec(
            select(
                func.count(Article.id).label("total"),
                func.count(sa_case(
                    (Article.pub_date == date.today(), Article.id),
                )).label("today"),
                func.count(sa_case(
                    (Article.status == "APPROVED", Article.id),
                )).label("approved"),
                func.count(sa_case(
                    (Article.status == "REJECTED", Article.id),
                )).label("rejected"),
                func.count(sa_case(
                    (Article.status == "SAVED", Article.id),
                )).label("saved"),
                func.count(sa_case(
                    (Article.status == "NEW", Article.id),
                )).label("pending"),
                func.count(sa_case(
                    (Article.relevance_score >= SCORE_THRESHOLD_HIGH, Article.id),
                )).label("hq"),
            )
        ).one()

        # Query 2: unacknowledged alerts (needs complex WHERE)
        _alert_cutoff = date.today() - timedelta(days=30)
        alerts = session.exec(
            select(func.count(Article.id)).where(
                Article.status == "ALERT",
                Article.alert_acknowledged_at.is_(None),
                (Article.pub_date >= _alert_cutoff) | (Article.pub_date.is_(None)),
            )
        ).one()

        return {
            "total": row.total, "today": row.today,
            "approved": row.approved, "rejected": row.rejected,
            "alerts": alerts, "saved": row.saved, "pending": row.pending,
            "hq": row.hq,
        }


@st.cache_data(ttl=600, show_spinner=False)
def get_dashboard_kpis() -> dict:
    """Compute extended KPIs: last-7-days vs previous-7-days counts, avg score,
    top journal, unreviewed high-score articles, and 30-day sparkline data."""
    from collections import Counter
    today = date.today()
    week_start = today - timedelta(days=6)      # last 7 days (incl. today)
    last_week_start = week_start - timedelta(days=7)  # previous 7 days

    with get_session() as session:
        # All articles from last 30 days for sparkline
        cutoff_30d = today - timedelta(days=30)
        recent = session.exec(
            select(Article.pub_date, Article.relevance_score, Article.journal,
                   Article.specialty, Article.status)
            .where(Article.pub_date >= cutoff_30d)
        ).all()

        # Bucket by day for sparkline
        day_counts: dict[date, int] = {}
        day_scores: dict[date, list] = {}
        this_week = 0
        last_week = 0
        this_week_scores = []
        last_week_scores = []
        journal_counter: Counter = Counter()
        unreviewed_hq = 0

        for pub_date, score, journal, specialty, status in recent:
            if pub_date is None:
                continue
            d = pub_date if isinstance(pub_date, date) else pub_date.date() if hasattr(pub_date, 'date') else pub_date
            day_counts[d] = day_counts.get(d, 0) + 1
            day_scores.setdefault(d, []).append(score or 0)

            if d >= week_start:
                this_week += 1
                this_week_scores.append(score or 0)
                if journal:
                    journal_counter[journal] += 1
            elif d >= last_week_start:
                last_week += 1
                last_week_scores.append(score or 0)

            if status == "NEW" and (score or 0) >= SCORE_THRESHOLD_HIGH:
                unreviewed_hq += 1

        # Build 30-day sparkline array (one value per day)
        sparkline = []
        for i in range(30):
            d = today - timedelta(days=29 - i)
            sparkline.append(day_counts.get(d, 0))

        avg_score_week = round(sum(this_week_scores) / len(this_week_scores), 1) if this_week_scores else 0
        avg_score_last = round(sum(last_week_scores) / len(last_week_scores), 1) if last_week_scores else 0
        top_journal = journal_counter.most_common(1)[0][0] if journal_counter else "\u2014"
        top_journal_n = journal_counter.most_common(1)[0][1] if journal_counter else 0

        # Week-over-week delta
        if last_week > 0:
            wow_delta = round((this_week - last_week) / last_week * 100)
        else:
            wow_delta = 100 if this_week > 0 else 0

        return {
            "this_week": this_week,
            "last_week": last_week,
            "wow_delta": wow_delta,
            "avg_score_week": avg_score_week,
            "avg_score_last": avg_score_last,
            "top_journal": top_journal,
            "top_journal_n": top_journal_n,
            "unreviewed_hq": unreviewed_hq,
            "sparkline": sparkline,
        }


@st.cache_data(ttl=3600, show_spinner=False)
def get_heatmap_data() -> "pd.DataFrame":
    """Build a Fachgebiet x Woche matrix for the trend heatmap.
    Returns DataFrame with columns: Woche, Fachgebiet, Anzahl, Avg_Score."""
    today = date.today()
    cutoff = today - timedelta(days=8 * 7)  # last 8 weeks

    with get_session() as session:
        rows = session.exec(
            select(Article.pub_date, Article.specialty, Article.relevance_score)
            .where(Article.pub_date >= cutoff)
            .where(Article.specialty.is_not(None))
        ).all()

    if not rows:
        return pd.DataFrame()

    # Build records per calendar week
    records = []
    for pub_date, specialty, score in rows:
        if pub_date is None or specialty is None:
            continue
        d = pub_date if isinstance(pub_date, date) else pub_date
        # ISO calendar week label
        iso = d.isocalendar()
        wk_label = f"KW{iso[1]:02d}"
        records.append({"Woche": wk_label, "week_num": iso[1], "year": iso[0],
                        "Fachgebiet": specialty, "Score": score or 0})

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # Sort weeks chronologically
    df["sort_key"] = df["year"] * 100 + df["week_num"]
    agg = (df.groupby(["Woche", "Fachgebiet", "sort_key"])
           .agg(Anzahl=("Score", "size"), Avg_Score=("Score", "mean"))
           .reset_index()
           .sort_values("sort_key"))
    agg["Avg_Score"] = agg["Avg_Score"].round(1)
    return agg


@st.cache_data(ttl=120, show_spinner=False)
def get_unacknowledged_alerts() -> list:
    """Get recent ALERT articles not yet acknowledged in the DB (last 30d)."""
    _cutoff = date.today() - timedelta(days=30)
    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.status == "ALERT")
            .where(Article.alert_acknowledged_at.is_(None))
            .where(
                (Article.pub_date >= _cutoff) | (Article.pub_date.is_(None))
            )
            .order_by(col(Article.pub_date).desc())
        )
        alerts = session.exec(stmt).all()
        return [_detach_article(a) for a in alerts]


# ---------------------------------------------------------------------------
# Badge / rendering helpers
# ---------------------------------------------------------------------------
def score_badge(score: float) -> str:
    # Color class for text
    cls = ("a-score-high" if score >= SCORE_THRESHOLD_HIGH
           else "a-score-mid" if score >= SCORE_THRESHOLD_MID
           else "a-score-low")
    # Color class for ring stroke
    ring_cls = ("ring-high" if score >= SCORE_THRESHOLD_HIGH
                else "ring-mid" if score >= SCORE_THRESHOLD_MID
                else "ring-low")
    # Ring offset: 125.66 = full circumference (2*pi*r, r=20)
    pct = min(score / 100, 1.0)
    offset = 125.66 * (1 - pct)
    hq = f'<span class="a-hq-badge">{SCORE_THRESHOLD_HIGH}\u2191</span>' if score >= SCORE_THRESHOLD_HIGH else ""
    return (
        f'<div class="a-score-ring">'
        f'<svg viewBox="0 0 48 48">'
        f'<circle class="ring-bg" cx="24" cy="24" r="20"/>'
        f'<circle class="ring-fill {ring_cls}" cx="24" cy="24" r="20" '
        f'style="stroke-dashoffset:{offset:.1f}"/>'
        f'</svg>'
        f'<span class="a-score-val {cls}">{score:.0f}</span>'
        f'{hq}</div>'
    )


def score_pill(score: float) -> str:
    cls = ("score-high" if score >= SCORE_THRESHOLD_HIGH
           else "score-mid" if score >= SCORE_THRESHOLD_MID
           else "score-low")
    if score >= SCORE_THRESHOLD_HIGH:
        tip = "Hohe Relevanz — Artikel mit starker Evidenz und Praxisbezug"
    elif score >= SCORE_THRESHOLD_MID:
        tip = "Mittlere Relevanz — lesenswert, aber nicht top-priorisiert"
    else:
        tip = "Niedrige Relevanz — geringe klinische Bedeutung oder schwache Evidenz"
    return (
        f'<span class="score-pill {cls}" data-tip="{_esc(tip)}" '
        f'style="cursor:help;position:relative">{score:.0f}</span>'
    )


def spec_pill(specialty: str) -> str:
    fg, bg = SPECIALTY_COLORS.get(specialty, ("#8b8ba0", "rgba(139,139,160,0.10)"))
    return f'<span class="a-spec" style="color:{fg};background:{bg}">{specialty}</span>'


def status_badge(status: str) -> str:
    labels = {
        "NEW": ("Neu", "status-new"), "APPROVED": ("Gemerkt", "status-approved"),
        "REJECTED": ("Ausgeblendet", "status-rejected"), "SAVED": ("Gemerkt", "status-saved"),
        "ALERT": ("Alert", "status-alert"),
    }
    label, cls = labels.get(status, (status, "status-new"))
    return f'<span class="status-badge {cls}">{label}</span>'


def momentum_badge(momentum: str, growth_rate: float) -> str:
    """Return an HTML badge for trend momentum."""
    cfg = {
        "exploding": ("momentum-exploding", "Stark steigend"),
        "rising": ("momentum-rising", "Steigend"),
        "stable": ("momentum-stable", "Stabil"),
        "falling": ("momentum-falling", "Rückläufig"),
    }
    cls, label = cfg.get(momentum, ("momentum-stable", "Stabil"))
    icons = {"exploding": "\U0001f525", "rising": "\u2197", "stable": "\u2192", "falling": "\u2198"}
    icon = icons.get(momentum, "\u2192")
    extra = ""
    if growth_rate > 1 and momentum in ("exploding", "rising"):
        extra = f" {growth_rate:.1f}x"
    return f'<span class="momentum-badge {cls}">{icon} {label}{extra}</span>'


def evidence_badge(evidence_trend: str, dominant_type: str) -> str:
    """Return an HTML badge for evidence level."""
    if not dominant_type:
        return ""
    cls = "evidence-badge-rising" if evidence_trend == "rising" else "evidence-badge-default"
    arrow = " \u2191" if evidence_trend == "rising" else ""
    return f'<span class="evidence-badge {cls}">{_esc(dominant_type)}{arrow}</span>'


def cross_specialty_badge(spread: str) -> str:
    """Return an HTML badge for cross-specialty expansion."""
    if not spread:
        return ""
    return f'<span class="cross-spec-badge">\U0001f500 {_esc(spread)}</span>'


def _parse_summary(raw: str) -> tuple:
    """Parse structured summary into (core, detail, praxis) tuple.

    Supports three formats:
    - LLM format: KERN:...;;;PRAXIS:...;;;EINORDNUNG:...
    - Template format: KERN:...;;;DESIGN:...;;;DETAIL:...
    - Legacy format: Kernbefund:... | Details:...
    """
    core = ""
    detail = ""
    praxis = ""
    if not raw:
        return core, detail, praxis
    # Structured format with ;;; separators
    if ";;;" in raw:
        for part in raw.split(";;;"):
            part = part.strip()
            if part.startswith("KERN:"):
                core = part[5:].strip()
            elif part.startswith("PRAXIS:"):
                praxis = part[7:].strip()
            elif part.startswith("EINORDNUNG:"):
                detail = part[11:].strip()
            elif part.startswith("DETAIL:"):
                detail = part[7:].strip()
            # DESIGN is intentionally skipped — already shown in meta line
    # Legacy format: Kernbefund: ... | Details: ...
    elif " | " in raw:
        for part in raw.split(" | "):
            part = part.strip()
            if part.startswith("Kernbefund:"):
                core = part[11:].strip()
            elif part.startswith("Details:"):
                detail = part[8:].strip()
    else:
        core = raw[:150]
    return core, detail, praxis


def _render_score_breakdown(breakdown_json) -> str:
    """Render score breakdown as inline HTML bar chart.

    Supports two formats:
    - Rule-based: journal, design, recency, keywords, arztrelevanz, bonus
    - LLM-based (scorer=llm): studientyp, klinische_relevanz,
      neuigkeitswert, zielgruppen_fit, quellenqualitaet + reasoning
    """
    if not breakdown_json:
        return ""
    try:
        bd = json.loads(breakdown_json)
    except (json.JSONDecodeError, TypeError):
        return ""

    is_llm = bd.get("scorer") == "llm"

    if is_llm:
        items = [
            ("Studientyp", bd.get("studientyp", 0), 20, "#a78bfa"),
            ("Klin. Relevanz", bd.get("klinische_relevanz", 0), 20, "#60a5fa"),
            ("Neuigkeit", bd.get("neuigkeitswert", 0), 20, "#22d3ee"),
            ("Zielgruppe", bd.get("zielgruppen_fit", 0), 20, "#fbbf24"),
            ("Quelle", bd.get("quellenqualitaet", 0), 20, "#4ade80"),
        ]
    else:
        items = [
            ("Journal", bd.get("journal", 0), 30, "#60a5fa"),
            ("Design", bd.get("design", 0), 25, "#a78bfa"),
            ("Aktualität", bd.get("recency", 0), 20, "#22d3ee"),
            ("Keywords", bd.get("keywords", 0), 15, "#fbbf24"),
            ("Arztrel.", bd.get("arztrelevanz", 0), 10, "#4ade80"),
            ("Bonus", bd.get("bonus", 0), 10, "#8b8ba0"),
            ("Präferenz", bd.get("preference", 0), 15, "#f472b6"),
        ]

    # Tooltip explanations for rule-based scoring
    _tooltips = {
        "Journal": "Gewicht: 30 %\nTop-Quellen (NEJM, Lancet, BMJ, JAMA) "
                   "erhalten die h\u00f6chste Punktzahl.\nMittlere Journals "
                   "(Fachzeitschriften) scoren moderat.\nPreprints und "
                   "unbekannte Quellen scoren niedrig.",
        "Design": "Gewicht: 25 %\nMeta-Analyse & Syst. Review: h\u00f6chste "
                  "Punktzahl.\nRCT & Leitlinie: hoch.\nKohortenstudie & "
                  "Review: mittel.\nFallbericht & Editorial: niedrig.",
        "Aktualit\u00e4t": "Gewicht: 20 %\nArtikel der letzten 7 Tage "
                           "erhalten volle Punktzahl.\nMit zunehmendem Alter "
                           "sinkt der Score.\nNach 90 Tagen: minimaler Beitrag.",
        "Keywords": "Gewicht: 15 %\nBonus f\u00fcr Schl\u00fcsselw\u00f6rter "
                    "wie: Sicherheit, Leitlinie, Landmark, Durchbruch, "
                    "First-in-Class.\nJedes Keyword erh\u00f6ht den Score.",
        "Arztrel.": "Gewicht: 10 %\nBewertet die direkte Praxisrelevanz: "
                    "Therapie\u00e4nderung, Diagnostik, Pr\u00e4vention, "
                    "Gesundheitspolitik.\nH\u00f6here Scores f\u00fcr "
                    "unmittelbar handlungsrelevante Artikel.",
        "Bonus": "Zusatzpunkte f\u00fcr besondere Merkmale:\nDeutscher Artikel "
                 "(+3), Open Access (+2), Safety-Alert (+5),\n"
                 "Leitlinien-Relevanz (+3).",
        "Pr\u00e4ferenz": "Pers\u00f6nliche Gewichtung basierend auf\n"
                          "Watchlist-Keywords und Fachgebiet-Pr\u00e4ferenzen.",
        # LLM-based
        "Studientyp": "Gewicht: 20 %\nKI-Bewertung des Studiendesigns\n"
                      "und der methodischen Qualit\u00e4t.",
        "Klin. Relevanz": "Gewicht: 20 %\nKI-Bewertung der klinischen\n"
                          "Bedeutsamkeit f\u00fcr die Patientenversorgung.",
        "Neuigkeit": "Gewicht: 20 %\nKI-Bewertung des Neuigkeitswerts\n"
                     "und der Innovation gegen\u00fcber bekanntem Wissen.",
        "Zielgruppe": "Gewicht: 20 %\nKI-Bewertung der Relevanz f\u00fcr\n"
                      "niedergelassene \u00c4rzte und Kliniker.",
        "Quelle": "Gewicht: 20 %\nKI-Bewertung der Quellenqualit\u00e4t,\n"
                  "Reputation und Peer-Review-Status.",
    }

    # Bars
    html_parts = []
    for label, value, max_val, color in items:
        if value == 0 and label in ("Bonus", "Pr\u00e4ferenz"):
            continue
        pct = min(100, (value / max_val) * 100) if max_val > 0 else 0
        tooltip = _tooltips.get(label, "")
        tip_attr = f' data-tip="{_esc(tooltip)}"' if tooltip else ""
        html_parts.append(
            f'<div class="sb-item"{tip_attr}>'
            f'<div class="sb-bar-track">'
            f'<div class="sb-bar-fill" style="width:{pct:.0f}%;background:{color}"></div>'
            f'</div>'
            f'<div class="sb-value">{value:.1f}</div>'
            f'<div class="sb-label">{label}</div>'
            f'</div>'
        )

    # LLM reasoning tooltips
    if is_llm:
        reasoning_keys = [
            ("begr_studientyp", "Studientyp"),
            ("begr_klinische_relevanz", "Klin. Relevanz"),
            ("begr_neuigkeitswert", "Neuigkeit"),
            ("begr_zielgruppen_fit", "Zielgruppe"),
            ("begr_quellenqualitaet", "Quelle"),
        ]
        reasons = []
        for key, label in reasoning_keys:
            if key in bd and bd[key]:
                reasons.append(
                    f'<div style="font-size:0.75rem;color:var(--c-text-muted);margin-top:2px">'
                    f'<b>{label}:</b> {_esc(str(bd[key]))}</div>'
                )
        if reasons:
            html_parts.append(
                '<div style="margin-top:6px;border-top:1px solid rgba(255,255,255,0.06);'
                'padding-top:4px">' + "".join(reasons) + '</div>'
            )

        # Show rule-based comparison if available
        rb = bd.get("rule_based_score")
        if rb is not None:
            html_parts.append(
                f'<div style="font-size:0.7rem;color:var(--c-text-tertiary);margin-top:4px">'
                f'Rule-based Score: {rb:.1f}</div>'
            )

    return f'<div class="score-breakdown">{"".join(html_parts)}</div>'


def _render_artikel_entwurf(draft, article_id: int, idx: int):
    """Render a generated Artikel-Entwurf below the article card."""
    from src.processing.artikel_entwurf import draft_to_markdown

    with st.expander("\u270d\ufe0f Artikel-Entwurf", expanded=True):
        # Headline options
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin-bottom:6px">Headline-Optionen</div>',
            unsafe_allow_html=True,
        )
        _hl_key = f"entwurf_hl_{article_id}_{idx}"
        if draft.headline_options:
            st.radio(
                "Headline w\u00e4hlen",
                draft.headline_options,
                key=_hl_key,
                label_visibility="collapsed",
            )

        # Lead
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin:12px 0 4px 0">Lead</div>'
            f'<div style="font-size:0.82rem;color:var(--c-text);line-height:1.5;'
            f'padding:6px 0">{_esc(draft.lead)}</div>',
            unsafe_allow_html=True,
        )

        # Kernaussagen
        _kern_items = "".join(
            f'<li style="margin-bottom:4px">{_esc(k)}</li>'
            for k in draft.kernaussagen
        )
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin:12px 0 4px 0">Kernaussagen</div>'
            f'<ul style="font-size:0.82rem;color:var(--c-text);line-height:1.5;'
            f'padding-left:20px;margin:0">{_kern_items}</ul>',
            unsafe_allow_html=True,
        )

        # Methodik (subtle box)
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin:12px 0 4px 0">Methodik</div>'
            f'<div style="font-size:0.78rem;color:var(--c-text-muted);'
            f'background:var(--c-surface);padding:8px 10px;border-radius:6px;'
            f'line-height:1.4">{_esc(draft.methodik_zusammenfassung)}</div>',
            unsafe_allow_html=True,
        )

        # Praxis-Box (green left border)
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin:12px 0 4px 0">Was bedeutet das f\u00fcr die Praxis?</div>'
            f'<div style="font-size:0.82rem;color:var(--c-text);line-height:1.5;'
            f'padding:8px 12px;border-left:3px solid #4ade80;'
            f'background:rgba(74,222,128,0.06);border-radius:0 6px 6px 0">'
            f'{_esc(draft.praxis_box)}</div>',
            unsafe_allow_html=True,
        )

        # Einordnung
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin:12px 0 4px 0">Einordnung</div>'
            f'<div style="font-size:0.82rem;color:var(--c-text);line-height:1.5;'
            f'padding:6px 0">{_esc(draft.einordnung)}</div>',
            unsafe_allow_html=True,
        )

        # Quellen
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:700;color:var(--c-text);'
            'margin:12px 0 4px 0">Quellen</div>'
            f'<div style="font-size:0.75rem;color:var(--c-text-muted);'
            f'line-height:1.4;padding:4px 0">{_esc(draft.quellen_hinweis)}</div>',
            unsafe_allow_html=True,
        )

        # Action buttons: Markdown view + copy
        _md_text = draft_to_markdown(draft)
        _btn_c1, _btn_c2, _btn_c3 = st.columns([1, 1, 6])
        with _btn_c1:
            _md_key = f"entwurf_md_{article_id}_{idx}"
            if st.button("\U0001f4dd Als Markdown", key=_md_key, type="secondary"):
                st.session_state.artikel_entwuerfe[f"show_md_{article_id}"] = True
        with _btn_c2:
            _cp_key = f"entwurf_cp_{article_id}_{idx}"
            if st.button("\U0001f4cb Kopieren", key=_cp_key, type="secondary"):
                st.session_state.artikel_entwuerfe[f"show_md_{article_id}"] = True

        if st.session_state.artikel_entwuerfe.get(f"show_md_{article_id}"):
            st.code(_md_text, language="markdown")

        # Generation metadata
        st.markdown(
            f'<div style="font-size:0.65rem;color:var(--c-text-tertiary);margin-top:8px">'
            f'Generiert am {draft.generated_at:%d.%m.%Y %H:%M} '
            f'mit {_esc(draft.model_used)}</div>',
            unsafe_allow_html=True,
        )


@st.cache_data(ttl=600, show_spinner=False)
def _load_memory_batch(article_ids: tuple) -> dict:
    """Load editorial memory for a batch of articles (cached 10 min)."""
    try:
        from src.processing.redaktions_gedaechtnis import get_memory_batch
        memories = get_memory_batch(list(article_ids))
        # Convert to serializable dict for st.cache_data
        result = {}
        for aid, mem in memories.items():
            result[aid] = {
                "days_since": mem.days_since_last_coverage,
                "suggestion": mem.coverage_suggestion,
                "detail": mem.suggestion_detail_de,
                "similar_count": len(mem.similar_approved),
                "top_score": mem.similar_approved[0]["score"] if mem.similar_approved else 0,
            }
        return result
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).debug("Memory batch load failed: %s", exc)
        return {}


def _memory_badge_html(memory_info: dict) -> str:
    """Generate a small HTML badge for editorial memory context."""
    if not memory_info:
        return ""

    suggestion = memory_info.get("suggestion", "")
    days = memory_info.get("days_since", -1)
    similar_count = memory_info.get("similar_count", 0)
    top_score = memory_info.get("top_score", 0)
    detail = memory_info.get("detail", "")

    if suggestion == "Neues Thema":
        return (
            '<span class="memory-badge memory-new" '
            f'title="{_esc(detail)}">'
            '&#x1F195; Neues Thema</span>'
        )
    elif suggestion == "Kuerzlich berichtet":
        return (
            '<span class="memory-badge memory-recent" '
            f'title="{_esc(detail)}">'
            f'&#x1F504; vor {days}d berichtet (Score {top_score:.0f})</span>'
        )
    elif suggestion == "Thema laeuft":
        return (
            '<span class="memory-badge memory-followup" '
            f'title="{_esc(detail)}">'
            f'&#x1F504; vor {days}d berichtet</span>'
        )
    elif suggestion == "Update faellig":
        return (
            '<span class="memory-badge memory-stale" '
            f'title="{_esc(detail)}">'
            f'&#x1F504; {days}d her &mdash; Update?</span>'
        )
    return ""


def render_article_card(article: Article, idx: int, memory_info: dict = None):
    """Render a clean article card — Linear/Asana style (v3).

    Args:
        article: The article to render.
        idx: Index for unique widget keys.
        memory_info: Optional pre-loaded editorial memory dict for this article.
    """
    # Meta line
    meta_items = []
    if article.journal:
        meta_items.append(_esc(article.journal))
    if article.pub_date:
        meta_items.append(article.pub_date.strftime("%d. %b %Y"))
    if article.study_type and article.study_type != "Unbekannt":
        meta_items.append(_esc(article.study_type))
    if article.language:
        meta_items.append("DE" if article.language == "de" else "EN")
    meta_html = " &middot; ".join(meta_items)

    # Specialty as inline dot-chip in meta
    spec_html = ""
    if article.specialty:
        fg, bg = SPECIALTY_COLORS.get(article.specialty, ("#8b8ba0", "rgba(139,139,160,0.10)"))
        spec_html = (
            f' &middot; <span class="a-spec-dot" style="color:{fg};background:{bg}">'
            f'{_esc(article.specialty)}</span>'
        )

    # Memory badge (Redaktions-Gedaechtnis)
    mem_html = ""
    if memory_info:
        mem_html = _memory_badge_html(memory_info)

    # Title
    safe_title = _esc(clean_title(article.title))
    safe_url = _esc(article.url) if article.url else ""
    title_el = (
        f'<a href="{safe_url}" target="_blank" class="a-title">{safe_title}</a>'
        if safe_url else f'<span class="a-title">{safe_title}</span>'
    )

    # Highlight tags — inline
    tags_html = ""
    if article.highlight_tags:
        tag_parts = [t.strip() for t in article.highlight_tags.split("|") if t.strip()]
        if tag_parts:
            tags_inner = "".join(
                f'<span class="a-tag">&#10022; {_esc(t)}</span>' for t in tag_parts
            )
            tags_html = f'<div class="a-tags-inline">{tags_inner}</div>'

    # Summary — KERN + PRAXIS only (compact)
    core, detail, praxis = _parse_summary(article.summary_de)
    summary_html = ""
    if core or praxis:
        summary_html = '<div class="a-summary">'
        if core:
            summary_html += f'<div class="a-summary-core">{_esc(core)}</div>'
        if praxis:
            summary_html += (
                f'<div class="a-summary-praxis">'
                f'<span style="font-weight:600;color:var(--c-praxis);font-size:0.7rem">'
                f'Praxis:</span> {_esc(praxis)}</div>'
            )
        summary_html += '</div>'

    # Status badge (top-right, only if not NEW)
    status_html = ""
    if article.status != "NEW":
        status_html = f'<div class="a-status-indicator">{status_badge(article.status)}</div>'

    # Render card — specialty accent on hover
    _spec_fg, _ = SPECIALTY_COLORS.get(article.specialty or "", ("#8b8ba0", ""))
    _card_style = f'--card-accent:{_spec_fg};--card-accent-to:rgba(163,230,53,0.4)'
    st.markdown(
        f'<div class="a-card" style="{_card_style}">'
        f'{status_html}'
        f'<div class="a-header">'
        f'{score_badge(article.relevance_score)}'
        f'<div style="flex:1;min-width:0">'
        f'{title_el}'
        f'<div class="a-meta">{meta_html}{spec_html}{" " + mem_html if mem_html else ""}</div>'
        f'{tags_html}'
        f'</div></div>'
        f'{summary_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Selection checkbox + action buttons — compact icon row
    if "selected_articles" not in st.session_state:
        st.session_state.selected_articles = set()

    if article.status != "NEW":
        btn_cols = st.columns([1, 1, 1, 1, 2, 6])
    else:
        btn_cols = st.columns([1, 1, 1, 2, 7])

    with btn_cols[0]:
        _sel_gen = st.session_state.get("_sel_gen", 0)
        _is_selected = st.checkbox(
            "Sel", value=article.id in st.session_state.selected_articles,
            key=f"sel_{article.id}_{idx}_g{_sel_gen}", label_visibility="collapsed",
        )
        if _is_selected:
            st.session_state.selected_articles.add(article.id)
        else:
            st.session_state.selected_articles.discard(article.id)

    with btn_cols[1]:
        if st.button("\u2606", key=f"sv_{article.id}_{idx}", help="Merken",
                      use_container_width=True):
            update_article_status(article.id, "SAVED")
            st.toast("Gemerkt")
            st.rerun()

    with btn_cols[2]:
        if st.button("\u2717", key=f"rj_{article.id}_{idx}", help="Ausblenden",
                      use_container_width=True):
            update_article_status(article.id, "REJECTED")
            st.toast("Ausgeblendet")
            st.rerun()

    _draft_col = 3
    if article.status != "NEW":
        with btn_cols[3]:
            if st.button("\u21a9", key=f"un_{article.id}_{idx}", help="Zur\u00fccksetzen",
                          use_container_width=True):
                update_article_status(article.id, "NEW")
                st.toast("Zur\u00fcckgesetzt")
                st.rerun()
        _draft_col = 4

    with btn_cols[_draft_col]:
        if st.button("\u270d\ufe0f Entwurf", key=f"draft_{article.id}_{idx}",
                      help="KI-Entwurf generieren", use_container_width=True):
            if "artikel_entwuerfe" not in st.session_state:
                st.session_state.artikel_entwuerfe = {}
            st.session_state.artikel_entwuerfe[f"gen_{article.id}"] = True
            st.rerun()

    # Score breakdown expander
    if article.score_breakdown:
        with st.expander("Score-Details", expanded=False):
            breakdown_html = _render_score_breakdown(article.score_breakdown)
            if breakdown_html:
                st.markdown(breakdown_html, unsafe_allow_html=True)

    # Artikel-Entwurf generation and display
    if "artikel_entwuerfe" not in st.session_state:
        st.session_state.artikel_entwuerfe = {}

    _draft_store = st.session_state.artikel_entwuerfe
    _gen_flag = _draft_store.get(f"gen_{article.id}", False)
    _cached_draft = _draft_store.get(f"draft_{article.id}")

    if _gen_flag and not _cached_draft:
        with st.spinner("Entwurf wird generiert..."):
            from src.processing.artikel_entwurf import generate_draft as _gen_draft
            _draft = _gen_draft(article.id)
            if _draft:
                _draft_store[f"draft_{article.id}"] = _draft
                _draft_store.pop(f"gen_{article.id}", None)
                st.rerun()
            else:
                _draft_store.pop(f"gen_{article.id}", None)
                st.warning("Entwurf konnte nicht generiert werden.")

    if _cached_draft:
        _render_artikel_entwurf(_cached_draft, article.id, idx)

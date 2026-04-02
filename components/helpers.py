"""Lumio — Helper functions, data access, and rendering utilities."""

import html as html_mod
import json
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import streamlit as st

# Lazy imports for heavy libraries (~750ms combined)
_alt = None
_pd = None

def _get_alt():
    global _alt
    if _alt is None:
        import altair
        _alt = altair
    return _alt

def _get_pd():
    global _pd
    if _pd is None:
        import pandas
        _pd = pandas
    return _pd
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

# Dark-mode Altair axis/view config — lazy to avoid 250ms import at startup
_DARK_AXIS_CONFIG = None
_DARK_VIEW_CONFIG = None
_ESANUM_AXIS_CONFIG = None

def get_dark_axis_config():
    """Return theme-aware Altair axis config."""
    is_esanum = st.session_state.get("theme", "dark") == "esanum"
    if is_esanum:
        global _ESANUM_AXIS_CONFIG
        if _ESANUM_AXIS_CONFIG is None:
            alt = _get_alt()
            _ESANUM_AXIS_CONFIG = alt.AxisConfig(
                labelFontSize=11, gridColor="rgba(0,0,0,0.06)",
                domainColor="rgba(0,0,0,0.10)", labelColor="#737373",
                titleColor="#444444",
            )
        return _ESANUM_AXIS_CONFIG

    global _DARK_AXIS_CONFIG
    if _DARK_AXIS_CONFIG is None:
        alt = _get_alt()
        _DARK_AXIS_CONFIG = alt.AxisConfig(
            labelFontSize=11, gridColor="rgba(255,255,255,0.05)",
            domainColor="rgba(255,255,255,0.08)", labelColor="#8b8ba0",
            titleColor="#a0a0b8",
        )
    return _DARK_AXIS_CONFIG

def get_dark_view_config():
    global _DARK_VIEW_CONFIG
    if _DARK_VIEW_CONFIG is None:
        _DARK_VIEW_CONFIG = _get_alt().ViewConfig(strokeWidth=0)
    return _DARK_VIEW_CONFIG


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
    "Pädiatrie": ("#38bdf8", "rgba(56,189,248,0.10)"),
    "Gynäkologie": ("#f472b6", "rgba(244,114,182,0.10)"),
    "Rheumatologie": ("#ec4899", "rgba(236,72,153,0.10)"),
    "Chirurgie": ("#64748b", "rgba(100,116,139,0.10)"),
    "Nephrologie": ("#0ea5e9", "rgba(14,165,233,0.10)"),
    "Anästhesiologie": ("#e879f9", "rgba(232,121,249,0.10)"),
    "Intensivmedizin": ("#f43f5e", "rgba(244,63,94,0.10)"),
    "HNO": ("#d946ef", "rgba(217,70,239,0.10)"),
    "Augenheilkunde": ("#2dd4bf", "rgba(45,212,191,0.10)"),
    "Geriatrie": ("#a3a3a3", "rgba(163,163,163,0.10)"),
    "Notfallmedizin": ("#fb7185", "rgba(251,113,133,0.10)"),
    "Radiologie": ("#6366f1", "rgba(99,102,241,0.10)"),
    "Palliativmedizin": ("#c084fc", "rgba(192,132,252,0.10)"),
    "Allergologie": ("#fbbf24", "rgba(251,191,36,0.10)"),
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
    """Create a detached copy of a session-bound Article.

    Uses the model's built-in detach() which copies ALL columns
    (including source_category, paywall, full_text_url, etc.).
    """
    return a.detach()


# ---------------------------------------------------------------------------
# LLM-based search query expansion (DE↔EN + synonyms)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def expand_search_query(query: str) -> tuple:
    """Expand a medical search term with translations and synonyms via LLM.

    Returns (expanded_fts_query, expansion_terms) where:
    - expanded_fts_query: FTS5-compatible OR query string
    - expansion_terms: list of added synonyms (for UI display)

    Falls back to (original_query, []) on any error.
    """
    import logging
    _logger = logging.getLogger("lumio.search_expansion")

    query = query.strip()
    if not query or len(query) < 2:
        return query, []

    try:
        from src.llm_client import cached_chat_completion
        from src.config import get_provider_chain

        providers = get_provider_chain("search_expansion")
        if not providers:
            return query, []

        system_prompt = (
            "Du bist ein medizinischer Suchassistent. "
            "Für den gegebenen medizinischen Suchbegriff: liefere die englische Übersetzung "
            "und bis zu 5 wichtige Synonyme oder Abkürzungen (DE und EN gemischt). "
            "Antworte NUR mit einer kommaseparierten Liste, OHNE den Originalbegriff, "
            "OHNE Nummerierung, OHNE Erklärungen. "
            "Beispiel — Eingabe: Herzinsuffizienz → heart failure, HFrEF, HFpEF, cardiac insufficiency, Herzschwäche"
        )

        response = cached_chat_completion(
            providers=providers,
            messages=[{"role": "user", "content": query}],
            system=system_prompt,
            max_tokens=100,
        )

        if not response:
            return query, []

        # Parse comma-separated terms
        raw_terms = [t.strip().strip('"').strip("'") for t in response.split(",")]
        # Filter empty, duplicates, and the original query itself
        seen = {query.lower()}
        expansion_terms = []
        for term in raw_terms:
            if not term or len(term) < 2:
                continue
            if term.lower() in seen:
                continue
            seen.add(term.lower())
            expansion_terms.append(term)

        if not expansion_terms:
            return query, []

        # Build FTS5 OR query — multi-word terms get quoted
        parts = [query]
        for term in expansion_terms:
            if " " in term:
                parts.append(f'"{term}"')
            else:
                parts.append(term)
        fts_query = " OR ".join(parts)

        _logger.info("Search expansion: '%s' → %s", query, fts_query)
        return fts_query, expansion_terms

    except Exception as exc:
        import logging
        logging.getLogger("lumio.search_expansion").debug(
            "Search expansion failed: %s", exc
        )
        return query, []


# ---------------------------------------------------------------------------
# Data access (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def get_articles(
    specialties: Optional[tuple] = None,
    sources: Optional[tuple] = None,
    source_categories: Optional[tuple] = None,
    min_score: float = 0.0,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search_query: str = "",
    status_filter: str = "ALL",
    language: Optional[str] = None,
    study_types: Optional[tuple] = None,
    open_access_only: bool = False,
    sort_by: str = "score",  # "score" | "date" | "source"
    has_summary_only: bool = False,
    skip_expansion: bool = False,
) -> list[Article]:
    """Query articles with filters. Uses FTS5 for search when available."""
    from src.models import fts5_search
    fts_ids: list = []

    with get_session() as session:
        stmt = select(Article)
        if specialties:
            # Match primary OR secondary specialties (cross-cutting articles)
            from sqlalchemy import or_
            _spec_conditions = [col(Article.specialty).in_(specialties)]
            for _sp in specialties:
                _spec_conditions.append(
                    col(Article.secondary_specialties).contains(_sp)
                )
            stmt = stmt.where(or_(*_spec_conditions))
        if sources:
            # Expand "Google News" back to all variants
            expanded_sources = list(sources)
            if "Google News" in expanded_sources:
                expanded_sources.remove("Google News")
                from sqlalchemy import or_
                stmt = stmt.where(
                    or_(
                        col(Article.source).in_(expanded_sources) if expanded_sources else False,
                        col(Article.source).startswith("Google News"),
                    )
                )
            else:
                stmt = stmt.where(col(Article.source).in_(expanded_sources))
        if source_categories:
            stmt = stmt.where(col(Article.source_category).in_(source_categories))
        if min_score > 0:
            stmt = stmt.where(Article.relevance_score >= min_score)
        if date_from:
            stmt = stmt.where(Article.pub_date >= date_from)
        if date_to:
            stmt = stmt.where(Article.pub_date <= date_to)

        # Language filter
        if language and language != "Alle":
            lang_code = "de" if language in ("Deutsch", "DE") else "en"
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

        # Search: LLM-expanded query → FTS5 with BM25 ranking → ILIKE fallback
        if search_query:
            if skip_expansion:
                expanded_query, _exp_terms = search_query, []
            else:
                expanded_query, _exp_terms = expand_search_query(search_query)
            fts_ids = fts5_search(expanded_query)
            if not fts_ids and expanded_query != search_query:
                # Fallback: try original query if expansion returned no results
                fts_ids = fts5_search(search_query)
            if fts_ids:
                stmt = stmt.where(col(Article.id).in_(fts_ids))
            else:
                # ILIKE fallback with all terms (original + expansions)
                from sqlalchemy import or_ as _or
                _all_terms = [search_query] + list(_exp_terms)
                _ilike_conditions = []
                for _term in _all_terms:
                    _pat = f"%{_term}%"
                    _ilike_conditions.append(col(Article.title).ilike(_pat))
                    _ilike_conditions.append(col(Article.abstract).ilike(_pat))
                stmt = stmt.where(_or(*_ilike_conditions))

        if status_filter and status_filter not in ("ALL", "Alle", "Alle Status"):
            if status_filter == "ARCHIVED":
                stmt = stmt.where(Article.status == "ARCHIVED")
            else:
                stmt = stmt.where(Article.status == status_filter)
        else:
            # Default: exclude archived articles unless explicitly requested
            stmt = stmt.where(Article.status != "ARCHIVED")

        # Has summary filter
        if has_summary_only:
            stmt = stmt.where(
                col(Article.summary_de).isnot(None),
                col(Article.summary_de) != "",
            )

        # Sort by chosen field unless FTS provides its own ranking
        if not fts_ids:
            if sort_by == "date":
                stmt = stmt.order_by(col(Article.pub_date).desc(), col(Article.created_at).desc())
            elif sort_by == "source":
                stmt = stmt.order_by(col(Article.source), col(Article.pub_date).desc())
            else:  # "score" (default)
                stmt = stmt.order_by(col(Article.relevance_score).desc())
        has_filter = (min_score > 0 or specialties or sources or source_categories
                      or search_query or status_filter != "ALL" or date_from
                      or language or study_types or open_access_only)
        if has_filter:
            stmt = stmt.limit(2000)
        else:
            stmt = stmt.limit(3000)  # analytics needs all articles
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


def archive_old_articles(days: int = 180, dry_run: bool = False) -> dict:
    """Archive articles older than `days` that are not protected.

    Protected articles (never archived):
    - In a collection (collectionarticle)
    - Bookmarked by any user (articlebookmark)
    - Score >= 80
    - Leitlinien / Guidelines (study_type or highlight_tags)
    - Already archived or manually saved/rejected

    Returns dict with counts.
    """
    from src.db import get_raw_conn
    from sqlalchemy import text

    with get_raw_conn() as conn:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        # Find candidates: old + status NEW or ALERT
        candidates = conn.execute(text("""
            SELECT a.id FROM article a
            WHERE a.pub_date < :cutoff
              AND a.status IN ('NEW', 'ALERT')
              AND a.id NOT IN (SELECT article_id FROM collectionarticle)
              AND a.id NOT IN (SELECT article_id FROM articlebookmark)
              AND (a.relevance_score IS NULL OR a.relevance_score < 80)
              AND LOWER(COALESCE(a.study_type, '')) NOT ILIKE '%leitlinie%'
              AND LOWER(COALESCE(a.study_type, '')) NOT ILIKE '%guideline%'
              AND LOWER(COALESCE(a.highlight_tags, '')) NOT ILIKE '%leitlinie%'
        """), {"cutoff": cutoff}).fetchall()

        candidate_ids = [r[0] for r in candidates]

        # Count protected articles for reporting
        total_old = conn.execute(
            text("SELECT COUNT(*) FROM article WHERE pub_date < :cutoff AND status IN ('NEW', 'ALERT')"),
            {"cutoff": cutoff},
        ).fetchone()[0]
        protected = total_old - len(candidate_ids)

        if not dry_run and candidate_ids:
            # Archive in batches of 500
            for i in range(0, len(candidate_ids), 500):
                batch = candidate_ids[i:i + 500]
                _params = {f"id_{j}": aid for j, aid in enumerate(batch)}
                _in_clause = ", ".join(f":id_{j}" for j in range(len(batch)))
                conn.execute(
                    text(f"UPDATE article SET status = 'ARCHIVED' WHERE id IN ({_in_clause})"),
                    _params,
                )
            # Clear caches
            get_articles.clear()

        return {
            "cutoff_date": cutoff,
            "days": days,
            "total_old": total_old,
            "protected": protected,
            "archived": len(candidate_ids) if not dry_run else 0,
            "would_archive": len(candidate_ids),
            "dry_run": dry_run,
        }


# ---------------------------------------------------------------------------
# Per-user bookmarks (personal "Merken")
# ---------------------------------------------------------------------------

def _get_current_user_id() -> int:
    """Return current user ID from session state, default to 1."""
    return st.session_state.get("current_user_id", 1)


def toggle_bookmark(article_id: int, user_id: Optional[int] = None) -> bool:
    """Toggle a personal bookmark (atomic). Returns True if now bookmarked."""
    from src.db import get_raw_conn
    from sqlalchemy import text
    from datetime import datetime as _dt, timezone as _tz
    if user_id is None:
        user_id = _get_current_user_id()
    with get_raw_conn() as conn:
        # Atomic: try to delete first; if no rows affected, insert
        deleted = conn.execute(
            text("DELETE FROM articlebookmark WHERE user_id = :uid AND article_id = :aid"),
            {"uid": user_id, "aid": article_id},
        ).rowcount
        if deleted:
            return False
        # No existing row — insert (ON CONFLICT handles rare race with concurrent insert)
        _now = _dt.now(_tz.utc).isoformat()
        conn.execute(
            text("INSERT INTO articlebookmark (user_id, article_id, created_at) "
                 "VALUES (:uid, :aid, :now) ON CONFLICT DO NOTHING"),
            {"uid": user_id, "aid": article_id, "now": _now},
        )
        return True


def is_bookmarked(article_id: int, user_id: Optional[int] = None) -> bool:
    """Check if article is bookmarked by user."""
    from src.models import ArticleBookmark
    if user_id is None:
        user_id = _get_current_user_id()
    with get_session() as session:
        return session.exec(
            select(ArticleBookmark).where(
                ArticleBookmark.user_id == user_id,
                ArticleBookmark.article_id == article_id,
            )
        ).first() is not None


def get_bookmarked_article_ids(user_id: Optional[int] = None) -> set[int]:
    """Get all bookmarked article IDs for a user."""
    from src.db import get_raw_conn
    from sqlalchemy import text
    if user_id is None:
        user_id = _get_current_user_id()
    with get_raw_conn() as conn:
        rows = conn.execute(
            text("SELECT article_id FROM articlebookmark WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchall()
        return set(r[0] for r in rows)


def get_bookmarked_articles(user_id: Optional[int] = None) -> list:
    """Get full Article objects for all bookmarks of a user."""
    bm_ids = get_bookmarked_article_ids(user_id)
    if not bm_ids:
        return []
    with get_session() as session:
        articles = session.exec(
            select(Article).where(Article.id.in_(bm_ids))
        ).all()
        return [_detach_article(a) for a in articles]


def acknowledge_alerts(article_ids: list[int]):
    """Mark alerts as acknowledged — per user via session state.

    Does NOT modify the article in the DB, so other users still see the alert.
    """
    if "_dismissed_alerts" not in st.session_state:
        st.session_state["_dismissed_alerts"] = set()
    st.session_state["_dismissed_alerts"].update(article_ids)
    get_unacknowledged_alerts.clear()


@st.cache_data(ttl=900, show_spinner=False)
def get_unique_values(column_name: str) -> list[str]:
    """Get distinct non-null values for a column.

    For 'source': consolidates all 'Google News (X)' variants into one 'Google News' entry.
    """
    column = getattr(Article, column_name)
    with get_session() as session:
        results = session.exec(
            select(column).where(column.isnot(None)).distinct()
        ).all()
        values = sorted([r for r in results if r])

        # Consolidate Google News variants
        if column_name == "source":
            has_gn = False
            consolidated = []
            for v in values:
                if v.startswith("Google News"):
                    if not has_gn:
                        consolidated.append("Google News")
                        has_gn = True
                else:
                    consolidated.append(v)
            return consolidated

        return values


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
                if journal and journal.lower() not in ("biorxiv", "medrxiv"):
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
        return _get_pd().DataFrame()

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
        return _get_pd().DataFrame()

    df = _get_pd().DataFrame(records)
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
    """Get recent ALERT articles not yet dismissed by this user (last 30d)."""
    _cutoff = date.today() - timedelta(days=30)
    _dismissed = st.session_state.get("_dismissed_alerts", set())
    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.status == "ALERT")
            .where(
                (Article.pub_date >= _cutoff) | (Article.pub_date.is_(None))
            )
            .order_by(col(Article.pub_date).desc())
        )
        alerts = session.exec(stmt).all()
        # Filter out alerts this user has already dismissed
        return [_detach_article(a) for a in alerts if a.id not in _dismissed]


# ---------------------------------------------------------------------------
# Badge / rendering helpers
# ---------------------------------------------------------------------------
def score_badge(score: float, score_breakdown: str = None) -> str:  # score_breakdown kept for compat
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


def score_pill(score: float, scoring_version: str = "", show_tip: bool = True) -> str:
    cls = ("score-high" if score >= SCORE_THRESHOLD_HIGH
           else "score-mid" if score >= SCORE_THRESHOLD_MID
           else "score-low")
    if show_tip:
        if score >= SCORE_THRESHOLD_HIGH:
            tip = "TOP \u2014 Hohe Relevanz, starke Grundlage, Praxisbezug"
        elif score >= SCORE_THRESHOLD_MID:
            tip = "RELEVANT \u2014 Solider Inhalt, selektiv aufgreifen"
        else:
            tip = "MONITOR \u2014 Nachrichtenwert oder Nischenthema"
        tip_attr = f' data-tip="{_esc(tip)}" style="cursor:help;position:relative"'
    else:
        tip_attr = ' style="position:relative"'
    return f'<span class="score-pill {cls}"{tip_attr}>{score:.0f}</span>'


def get_one_line_summary(article) -> str:
    """Extract v2 one_line_summary from article's score_breakdown JSON."""
    if not getattr(article, 'score_breakdown', None):
        return ""
    try:
        bd = json.loads(article.score_breakdown)
        return bd.get("one_line_summary", "")
    except (json.JSONDecodeError, TypeError):
        return ""


def get_scoring_version(article) -> str:
    """Get scoring version from article (field or breakdown)."""
    v = getattr(article, 'scoring_version', None)
    if v:
        return v
    if not getattr(article, 'score_breakdown', None):
        return "v1"
    try:
        bd = json.loads(article.score_breakdown)
        return bd.get("scoring_version", "v1")
    except (json.JSONDecodeError, TypeError):
        return "v1"


def spec_pill(specialty: str) -> str:
    fg, bg = SPECIALTY_COLORS.get(specialty, ("#8b8ba0", "rgba(139,139,160,0.10)"))
    return f'<span class="a-spec" style="color:{fg};background:{bg}">{_esc(specialty)}</span>'


def status_badge(status: str) -> str:
    labels = {
        "NEW": ("Neu", "status-new"), "APPROVED": ("Gemerkt", "status-approved"),
        "REJECTED": ("Ausgeblendet", "status-rejected"), "SAVED": ("Gemerkt", "status-saved"),
        "ALERT": ("Alert", "status-alert"),
    }
    label, cls = labels.get(status, (_esc(status), "status-new"))
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
    # Normalize spread text:
    # "A + B" (exactly 2) stays as "A + B"
    # "Von A nach B" → "A + B"
    # 3+ specialties → "A bis C"
    _s = spread
    if _s.lower().startswith("von ") and " nach " in _s.lower():
        parts = _s.split(" nach ", 1)
        _s = parts[0].replace("Von ", "").replace("von ", "") + " + " + parts[1]
    return f'<span class="cross-spec-badge">{_esc(_s)}</span>'


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

    Supports three formats:
    - v2 LLM (scoring_version=v2): 6 dimensions with variable maxima
    - v2 rule-based (scorer=rule_v2): 6 dimensions, estimated
    - v1 LLM (scorer=llm): 5 dimensions × 0–20 (legacy)
    - v1 rule-based: journal, design, recency, keywords, arztrelevanz, bonus
    """
    if not breakdown_json:
        return ""
    try:
        bd = json.loads(breakdown_json)
    except (json.JSONDecodeError, TypeError):
        return ""

    is_v2 = bd.get("scoring_version") == "v2" or bd.get("scorer") == "rule_v2"
    is_llm_v1 = bd.get("scorer") == "llm" and not is_v2

    if is_v2:
        # --- v2: 6 Dimensions with variable maxima ---
        scores = bd.get("scores", bd)  # nested or flat
        def _v2_score(dim):
            v = scores.get(dim, {})
            return v.get("score", v) if isinstance(v, dict) else (v if isinstance(v, (int, float)) else 0)

        items = [
            ("Handlungsrel.", _v2_score("clinical_action_relevance"), 20, "#ef4444"),
            ("Evidenztiefe", _v2_score("evidence_depth"), 20, "#a78bfa"),
            ("Zugkraft", _v2_score("topic_appeal"), 20, "#f59e0b"),
            ("Neuigkeit", _v2_score("novelty"), 16, "#22d3ee"),
            ("Quellenaut.", _v2_score("source_authority"), 12, "#4ade80"),
            ("Aufbereitung", _v2_score("presentation_quality"), 12, "#60a5fa"),
        ]
    elif is_llm_v1:
        # --- v1 LLM: 5 Dimensions × 0–20 ---
        items = [
            ("Studiendesign", bd.get("studientyp", 0), 20, "#a78bfa"),
            ("Klin. Relevanz", bd.get("klinische_relevanz", 0), 20, "#60a5fa"),
            ("Neuigkeit", bd.get("neuigkeitswert", 0), 20, "#22d3ee"),
            ("Zielgruppe", bd.get("zielgruppen_fit", 0), 20, "#fbbf24"),
            ("Quelle", bd.get("quellenqualitaet", 0), 20, "#4ade80"),
        ]
    else:
        # --- v1 rule-based ---
        items = [
            ("Journal", bd.get("journal", 0), 30, "#60a5fa"),
            ("Design", bd.get("design", 0), 25, "#a78bfa"),
            ("Aktualität", bd.get("recency", 0), 20, "#22d3ee"),
            ("Keywords", bd.get("keywords", 0), 15, "#fbbf24"),
            ("Arztrel.", bd.get("arztrelevanz", 0), 10, "#4ade80"),
            ("Bonus", bd.get("bonus", 0), 10, "#8b8ba0"),
        ]

    # Tooltip explanations
    _tooltips = {
        # v2 dimensions
        "Handlungsrel.": "Max 20 Punkte\nKann der Arzt danach konkret etwas \u00e4ndern?\n"
                         "Sofortige Handlung = 18\u201320\nIndirekt = 9\u201313\nHintergrund = 4\u20138",
        "Evidenztiefe": "Max 20 Punkte\nWie methodisch solide ist die Grundlage?\n"
                        "Meta-Analyse/Investigativ = 18\u201320\nRCT/Solide = 14\u201317\nModerat = 9\u201313",
        "Zugkraft": "Max 20 Punkte\nWollen \u00c4rzte das lesen, teilen, diskutieren?\n"
                    "Existenzthemen = 18\u201320\nBurnout/Digitalisierung = 14\u201317",
        "Neuigkeit": "Max 16 Punkte\nBringt das genuinely neue Information?\n"
                     "Erstmalig = 14\u201316\nUpdate = 10\u201313\nBest\u00e4tigung = 5\u20139",
        "Quellenaut.": "Max 12 Punkte\nWie vertrauensw\u00fcrdig ist die Quelle?\n"
                       "NEJM/Lancet = 11\u201312\n\u00c4rzteblatt = 9\u201310\nPreprint = 3\u20134",
        "Aufbereitung": "Max 12 Punkte\nWie gut f\u00fcr \u00c4rzte aufbereitet?\n"
                        "CME-optimiert = 11\u201312\nGut lesbar = 8\u201310\nSperrig = 5\u20137",
        # v1 dimensions (legacy)
        "Studiendesign": "Gewicht: 20 %\nKI-Bewertung des Studiendesigns.",
        "Klin. Relevanz": "v1 \u2014 Gewicht: 20 %\nKlinische Bedeutsamkeit.",
        "Zielgruppe": "v1 \u2014 Gewicht: 20 %\nRelevanz f\u00fcr niedergelassene \u00c4rzte.",
        "Quelle": "v1 \u2014 Gewicht: 20 %\nQuellenqualit\u00e4t und Reputation.",
        "Journal": "v1 \u2014 Gewicht: 30 %\nJournal-Tier Score.",
        "Design": "v1 \u2014 Gewicht: 25 %\nStudiendesign-Bewertung.",
        "Aktualit\u00e4t": "v1 \u2014 Gewicht: 20 %\nAktualit\u00e4t der Publikation.",
        "Keywords": "v1 \u2014 Gewicht: 15 %\nSicherheit, Leitlinie, Landmark.",
        "Arztrel.": "v1 \u2014 Gewicht: 10 %\nDirekte Praxisrelevanz.",
        "Bonus": "v1 \u2014 Zusatzpunkte f\u00fcr Open Access, DOI, Redaktionsbonus.",
    }

    html_parts = []

    # One-line summary for v2
    if is_v2:
        summary = bd.get("one_line_summary", "")
        if summary:
            html_parts.append(
                f'<div style="font-size:0.78rem;font-style:italic;color:var(--c-text);'
                f'margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid var(--c-border)">'
                f'{_esc(summary)}</div>'
            )
        estimated = bd.get("estimated", False)
        scorer_label = "KI" if not estimated else "Gesch\u00e4tzt"
        version_label = "v2" if is_v2 else "v1"
        html_parts.append(
            f'<div style="font-size:0.6rem;color:var(--c-text-muted);margin-bottom:4px">'
            f'{scorer_label} \u00b7 {version_label}</div>'
        )

    # Bars
    for label, value, max_val, color in items:
        if value == 0 and label == "Bonus":
            continue
        val = float(value) if isinstance(value, (int, float)) else 0
        pct = min(100, (val / max_val) * 100) if max_val > 0 else 0
        tooltip = _tooltips.get(label, "")
        tip_attr = f' data-tip="{_esc(tooltip)}"' if tooltip else ""
        html_parts.append(
            f'<div class="sb-item"{tip_attr}>'
            f'<div class="sb-bar-track">'
            f'<div class="sb-bar-fill" style="width:{pct:.0f}%;background:{color}"></div>'
            f'</div>'
            f'<div class="sb-value">{val:.0f}/{max_val}</div>'
            f'<div class="sb-label">{label}</div>'
            f'</div>'
        )

    # v2 LLM reasoning
    if is_v2:
        scores = bd.get("scores", {})
        _v2_reason_keys = [
            ("clinical_action_relevance", "Handlungsrel."),
            ("evidence_depth", "Evidenztiefe"),
            ("topic_appeal", "Zugkraft"),
            ("novelty", "Neuigkeit"),
            ("source_authority", "Quellenaut."),
            ("presentation_quality", "Aufbereitung"),
        ]
        reasons = []
        for key, label in _v2_reason_keys:
            dim = scores.get(key, {})
            reason = dim.get("reason", "") if isinstance(dim, dict) else ""
            if reason:
                reasons.append(
                    f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:2px">'
                    f'<b>{label}:</b> {_esc(str(reason))}</div>'
                )
        if reasons:
            html_parts.append(
                '<div style="margin-top:6px;border-top:1px solid var(--c-border);'
                'padding-top:4px">' + "".join(reasons) + '</div>'
            )

    # v1 LLM reasoning (legacy)
    elif is_llm_v1:
        reasoning_keys = [
            ("begr_studientyp", "Studiendesign"),
            ("begr_klinische_relevanz", "Klin. Relevanz"),
            ("begr_neuigkeitswert", "Neuigkeit"),
            ("begr_zielgruppen_fit", "Zielgruppe"),
            ("begr_quellenqualitaet", "Quelle"),
        ]
        reasons = []
        for key, label in reasoning_keys:
            if key in bd and bd[key]:
                reasons.append(
                    f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:2px">'
                    f'<b>{label}:</b> {_esc(str(bd[key]))}</div>'
                )
        if reasons:
            html_parts.append(
                '<div style="margin-top:6px;border-top:1px solid var(--c-border);'
                'padding-top:4px">' + "".join(reasons) + '</div>'
            )

    # Tier badge for v2
    tier = bd.get("tier", "")
    if tier:
        tier_colors = {"TOP": "var(--c-success)", "RELEVANT": "var(--c-warn)", "MONITOR": "var(--c-text-muted)"}
        html_parts.append(
            f'<div style="font-size:0.65rem;font-weight:700;color:{tier_colors.get(tier, "var(--c-text-muted)")};'
            f'margin-top:4px">{tier}</div>'
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
            f'title="Noch nicht auf esanum berichtet — neues Thema für die Redaktion">'
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

    # "NEU" badge — articles imported within last 48 hours
    new_badge = ""
    if article.created_at:
        try:
            from datetime import datetime, timezone, timedelta
            _art_ts = str(article.created_at)[:19]
            _cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%S")
            if _art_ts > _cutoff:
                new_badge = '<span class="new-theme-badge" style="font-size:0.55rem;padding:1px 6px;margin-left:4px" title="In den letzten 48h importiert">🆕 Neu</span>'
        except Exception:
            pass

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

    # Summary — KERN always, PRAXIS only for clinically actionable articles
    core, detail, praxis = _parse_summary(article.summary_de)
    summary_html = ""
    if core or praxis:
        summary_html = '<div class="a-summary">'
        if core:
            summary_html += f'<div class="a-summary-core">{_esc(core)}</div>'
        if praxis:
            # Show PRAXIS only for clinical studies, guidelines, safety alerts
            tags_lower = (article.highlight_tags or "").lower()
            text_lower = f"{article.title or ''} {article.abstract or ''}".lower()
            is_clinical = any(signal in tags_lower for signal in [
                "studientyp", "rct", "leitlinie", "top-quelle", "praxisrelevant",
            ]) or any(signal in text_lower for signal in [
                "rückruf", "rote-hand", "warnung", "leitlinie", "guideline",
                "randomized", "randomised", "clinical trial", "meta-analysis",
                "systematic review", "therapie", "treatment", "dosierung",
            ])
            if is_clinical:
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

    # Collection badge — show if article is in any active collection
    coll_badge_html = ""
    coll_map = st.session_state.get("_article_collection_map", {})
    coll_info = coll_map.get(article.id)
    if coll_info:
        coll_name = _esc(coll_info["name"])
        coll_status = coll_info["status"]
        if coll_status == "publiziert":
            coll_badge_html = (
                f'<span class="coll-badge coll-badge-pub" '
                f'title="Veröffentlicht: {coll_name}">Veröffentlicht</span>'
            )
        else:
            coll_badge_html = (
                f'<span class="coll-badge coll-badge-wip" '
                f'title="In Arbeit: {coll_name}">In Arbeit</span>'
            )

    # Render card
    _spec_fg, _ = SPECIALTY_COLORS.get(article.specialty or "", ("#8b8ba0", ""))
    _card_style = f'--card-accent:{_spec_fg};--card-accent-to:rgba(163,230,53,0.4)'
    st.markdown(
        f'<div class="a-card" style="{_card_style}">'
        f'{status_html}{coll_badge_html}'
        f'<div class="a-header">'
        f'{score_badge(article.relevance_score, article.score_breakdown)}'
        f'<div style="flex:1;min-width:0">'
        f'{title_el}'
        f'<div class="a-meta">{meta_html}{spec_html}{" " + mem_html if mem_html else ""}{new_badge}</div>'
        f'{tags_html}'
        f'</div></div>'
        f'{summary_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Action buttons — single compact row
    if "selected_articles" not in st.session_state:
        st.session_state.selected_articles = set()

    if article.status != "NEW":
        btn_cols = st.columns([1, 1, 1, 1, 6])
    else:
        btn_cols = st.columns([1, 1, 1, 6])

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

    # --- Merken: personal bookmark toggle ---
    _bm_key = f"_bookmarked_ids"
    if _bm_key not in st.session_state:
        st.session_state[_bm_key] = get_bookmarked_article_ids()
    _is_bm = article.id in st.session_state[_bm_key]

    with btn_cols[1]:
        _bm_label = "★" if _is_bm else "☆"
        _bm_help = "Gemerkt – klicken zum Entfernen" if _is_bm else "Merken"
        if st.button(_bm_label, key=f"sv_{article.id}_{idx}", help=_bm_help,
                      use_container_width=True):
            now_bookmarked = toggle_bookmark(article.id)
            from components.auth import track_activity
            if now_bookmarked:
                st.session_state[_bm_key].add(article.id)
                track_activity("bookmark", f"article_id={article.id}")
                st.toast("Gemerkt ☆")
            else:
                st.session_state[_bm_key].discard(article.id)
                track_activity("unbookmark", f"article_id={article.id}")
                st.toast("Aus Merkliste entfernt")
            st.rerun()

    # --- Ausblenden: global with confirmation ---
    _confirm_key = f"_confirm_reject_{article.id}"
    with btn_cols[2]:
        if st.session_state.get(_confirm_key):
            # Second click = confirmed
            if st.button("⚠ Sicher?", key=f"rj_confirm_{article.id}_{idx}",
                          help="Klicken = für alle ausblenden", use_container_width=True):
                update_article_status(article.id, "REJECTED")
                st.session_state.pop(_confirm_key, None)
                from components.auth import track_activity
                track_activity("dismiss", f"article_id={article.id}")
                st.toast("Für alle ausgeblendet")
                st.rerun()
        else:
            if st.button("✗", key=f"rj_{article.id}_{idx}", help="Für alle ausblenden",
                          use_container_width=True):
                st.session_state[_confirm_key] = True
                st.rerun()

    if article.status == "REJECTED":
        with btn_cols[3]:
            if st.button("↩", key=f"un_{article.id}_{idx}", help="Zurücksetzen",
                          use_container_width=True):
                update_article_status(article.id, "NEW")
                st.toast("Zurückgesetzt")
                st.rerun()

    # Score breakdown expander
    if article.score_breakdown:
        with st.expander("Score-Details", expanded=False):
            breakdown_html = _render_score_breakdown(article.score_breakdown)
            if breakdown_html:
                st.markdown(breakdown_html, unsafe_allow_html=True)

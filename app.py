"""MedIntel — Tägliches Medical Intelligence Briefing Dashboard."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import List, Optional
from sqlmodel import select, func, col

from src.models import Article, get_engine, get_session
from src.config import SPECIALTY_MESH

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedIntel — Medical Intelligence",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialise DB
# ---------------------------------------------------------------------------
get_engine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_articles(
    specialties: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    min_score: float = 0.0,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search_query: str = "",
    status_filter: str = "ALL",
) -> list[Article]:
    """Query articles with filters."""
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
        if search_query:
            pattern = f"%{search_query}%"
            stmt = stmt.where(
                col(Article.title).ilike(pattern)
                | col(Article.abstract).ilike(pattern)
            )
        if status_filter != "ALL":
            stmt = stmt.where(Article.status == status_filter)

        stmt = stmt.order_by(col(Article.relevance_score).desc()).limit(200)
        articles = session.exec(stmt).all()
        # Detach from session by accessing all attributes
        result = []
        for a in articles:
            result.append(Article(
                id=a.id,
                title=a.title,
                abstract=a.abstract,
                url=a.url,
                source=a.source,
                journal=a.journal,
                pub_date=a.pub_date,
                authors=a.authors,
                doi=a.doi,
                study_type=a.study_type,
                mesh_terms=a.mesh_terms,
                language=a.language,
                relevance_score=a.relevance_score,
                specialty=a.specialty,
                summary_de=a.summary_de,
                status=a.status,
                created_at=a.created_at,
            ))
        return result


def update_article_status(article_id: int, new_status: str):
    """Update article status (APPROVED, REJECTED, SAVED)."""
    with get_session() as session:
        article = session.get(Article, article_id)
        if article:
            article.status = new_status
            session.commit()


def get_unique_values(column) -> list[str]:
    """Get distinct non-null values for a column."""
    with get_session() as session:
        results = session.exec(
            select(column).where(column.isnot(None)).distinct()
        ).all()
        return sorted([r for r in results if r])


def get_stats() -> dict:
    """Get dashboard statistics."""
    with get_session() as session:
        total = session.exec(select(func.count(Article.id))).one()
        today_count = session.exec(
            select(func.count(Article.id)).where(Article.pub_date == date.today())
        ).one()
        approved = session.exec(
            select(func.count(Article.id)).where(Article.status == "APPROVED")
        ).one()
        rejected = session.exec(
            select(func.count(Article.id)).where(Article.status == "REJECTED")
        ).one()
        alerts = session.exec(
            select(func.count(Article.id)).where(Article.status == "ALERT")
        ).one()
        return {
            "total": total,
            "today": today_count,
            "approved": approved,
            "rejected": rejected,
            "alerts": alerts,
        }


def score_color(score: float) -> str:
    if score >= 75:
        return "🟢"
    elif score >= 50:
        return "🟡"
    return "🔴"


def score_badge_html(score: float) -> str:
    if score >= 75:
        color = "#22c55e"
    elif score >= 50:
        color = "#eab308"
    else:
        color = "#ef4444"
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:12px;font-weight:bold;font-size:0.85em">'
        f'{score:.0f}</span>'
    )


SPECIALTY_COLORS = {
    "Kardiologie": "#ef4444",
    "Onkologie": "#8b5cf6",
    "Neurologie": "#3b82f6",
    "Diabetologie/Endokrinologie": "#f59e0b",
    "Pneumologie": "#06b6d4",
    "Gastroenterologie": "#84cc16",
    "Infektiologie": "#f97316",
    "Dermatologie": "#ec4899",
    "Psychiatrie": "#6366f1",
    "Allgemeinmedizin": "#14b8a6",
    "Orthopädie": "#78716c",
    "Urologie": "#a855f7",
    "Pädiatrie": "#fb923c",
}


def specialty_badge_html(specialty: str) -> str:
    color = SPECIALTY_COLORS.get(specialty, "#6b7280")
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:12px;font-size:0.8em">{specialty}</span>'
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🩺 MedIntel")
    st.caption("Medical Intelligence Briefing")

    st.divider()

    # Filters
    st.subheader("Filter")

    # Specialties
    all_specialties = get_unique_values(Article.specialty)
    selected_specialties = st.multiselect(
        "Fachgebiet",
        options=all_specialties,
        default=[],
        placeholder="Alle Fachgebiete",
    )

    # Time range
    time_range = st.selectbox(
        "Zeitraum",
        ["Heute", "Letzte 7 Tage", "Letzte 30 Tage", "Alle"],
        index=1,
    )
    date_from = None
    date_to = date.today()
    if time_range == "Heute":
        date_from = date.today()
    elif time_range == "Letzte 7 Tage":
        date_from = date.today() - timedelta(days=7)
    elif time_range == "Letzte 30 Tage":
        date_from = date.today() - timedelta(days=30)

    # Min score
    min_score = st.slider("Mindest-Score", 0, 100, 0, 5)

    # Sources
    all_sources = get_unique_values(Article.source)
    selected_sources = st.multiselect(
        "Quellen",
        options=all_sources,
        default=[],
        placeholder="Alle Quellen",
    )

    # Status
    status_filter = st.selectbox(
        "Status",
        ["ALL", "NEW", "APPROVED", "REJECTED", "SAVED", "ALERT"],
        index=0,
    )

    # Search
    search_query = st.text_input("🔍 Suche", placeholder="Suchbegriff...")

    st.divider()

    # Stats
    stats = get_stats()
    st.metric("Artikel gesamt", stats["total"])
    col1, col2 = st.columns(2)
    col1.metric("Heute", stats["today"])
    col2.metric("Alerts", stats["alerts"])
    col1.metric("Freigegeben", stats["approved"])
    col2.metric("Abgelehnt", stats["rejected"])


# ---------------------------------------------------------------------------
# Breaking Alerts Banner
# ---------------------------------------------------------------------------
alert_articles = get_articles(status_filter="ALERT")
if alert_articles:
    st.markdown(
        f"""<div style="background:#fef2f2;border:2px solid #ef4444;
        border-radius:8px;padding:12px 16px;margin-bottom:16px">
        <strong style="color:#ef4444">🚨 {len(alert_articles)} Breaking Alert(s)</strong>
        </div>""",
        unsafe_allow_html=True,
    )
    for alert in alert_articles[:3]:
        st.markdown(
            f"- 🚨 **[{alert.title}]({alert.url})** "
            f"({alert.journal or alert.source})"
        )

# ---------------------------------------------------------------------------
# Main area — Tabs
# ---------------------------------------------------------------------------
tab_briefing, tab_search, tab_stats, tab_digest = st.tabs(
    ["📋 Tages-Briefing", "🔍 Suche", "📊 Statistik", "📧 Digest-Preview"]
)

# ---- Tab: Briefing --------------------------------------------------------
with tab_briefing:
    st.header(f"Tages-Briefing — {date.today().strftime('%d.%m.%Y')}")

    articles = get_articles(
        specialties=selected_specialties or None,
        sources=selected_sources or None,
        min_score=min_score,
        date_from=date_from,
        date_to=date_to,
        search_query=search_query,
        status_filter=status_filter,
    )

    if not articles:
        st.info("Keine Artikel gefunden. Passe die Filter an oder führe die Pipeline aus.")
    else:
        st.caption(f"{len(articles)} Artikel gefunden")

        for article in articles:
            with st.container():
                # Header row
                cols = st.columns([1, 8, 3])

                with cols[0]:
                    st.markdown(
                        score_badge_html(article.relevance_score),
                        unsafe_allow_html=True,
                    )

                with cols[1]:
                    # Title as link
                    title_display = article.title
                    if article.status == "ALERT":
                        title_display = f"🚨 {title_display}"

                    if article.url:
                        st.markdown(f"**[{title_display}]({article.url})**")
                    else:
                        st.markdown(f"**{title_display}**")

                    # Meta line
                    meta_parts = []
                    if article.journal:
                        meta_parts.append(f"📰 {article.journal}")
                    if article.pub_date:
                        meta_parts.append(f"📅 {article.pub_date.strftime('%d.%m.%Y')}")
                    if article.study_type:
                        meta_parts.append(f"🔬 {article.study_type}")
                    st.caption(" · ".join(meta_parts))

                with cols[2]:
                    if article.specialty:
                        st.markdown(
                            specialty_badge_html(article.specialty),
                            unsafe_allow_html=True,
                        )

                # Summary
                if article.summary_de:
                    # Split template summary into parts for better display
                    parts = article.summary_de.split(" | ")
                    for part in parts:
                        st.text(part)

                # Action buttons
                btn_cols = st.columns([1, 1, 1, 6])
                with btn_cols[0]:
                    if st.button("✅", key=f"approve_{article.id}", help="Freigeben"):
                        update_article_status(article.id, "APPROVED")
                        st.rerun()
                with btn_cols[1]:
                    if st.button("❌", key=f"reject_{article.id}", help="Ablehnen"):
                        update_article_status(article.id, "REJECTED")
                        st.rerun()
                with btn_cols[2]:
                    if st.button("📌", key=f"save_{article.id}", help="Merken"):
                        update_article_status(article.id, "SAVED")
                        st.rerun()

                st.divider()


# ---- Tab: Search ----------------------------------------------------------
with tab_search:
    st.header("Volltextsuche")

    search_input = st.text_input(
        "Suchbegriff eingeben",
        key="fulltext_search",
        placeholder="z.B. GLP-1, SGLT2, Immuntherapie...",
    )

    if search_input:
        results = get_articles(search_query=search_input, min_score=0)
        st.caption(f"{len(results)} Treffer")

        for a in results:
            score_icon = score_color(a.relevance_score)
            spec = f" [{a.specialty}]" if a.specialty else ""
            pub = f" — {a.pub_date.strftime('%d.%m.%Y')}" if a.pub_date else ""

            if a.url:
                st.markdown(
                    f"{score_icon} **{a.relevance_score:.0f}** · "
                    f"[{a.title}]({a.url}){spec}{pub}"
                )
            else:
                st.markdown(
                    f"{score_icon} **{a.relevance_score:.0f}** · "
                    f"{a.title}{spec}{pub}"
                )

            if a.summary_de:
                st.caption(a.summary_de[:200])
    else:
        st.info("Gib einen Suchbegriff ein, um Artikel zu finden.")


# ---- Tab: Stats -----------------------------------------------------------
with tab_stats:
    st.header("Statistik")

    all_articles = get_articles(min_score=0)

    if all_articles:
        df = pd.DataFrame([
            {
                "Fachgebiet": a.specialty or "Unklassifiziert",
                "Quelle": a.source,
                "Score": a.relevance_score,
                "Status": a.status,
                "Datum": a.pub_date,
                "Journal": a.journal or "Unbekannt",
            }
            for a in all_articles
        ])

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Artikel pro Fachgebiet")
            spec_counts = df["Fachgebiet"].value_counts()
            st.bar_chart(spec_counts)

        with col2:
            st.subheader("Artikel pro Quelle")
            source_counts = df["Quelle"].value_counts().head(10)
            st.bar_chart(source_counts)

        col3, col4 = st.columns(2)

        with col3:
            st.subheader("Score-Verteilung")
            st.bar_chart(df["Score"].value_counts(bins=10).sort_index())

        with col4:
            st.subheader("Status-Verteilung")
            status_counts = df["Status"].value_counts()
            st.bar_chart(status_counts)

        # Approve/Reject rate
        reviewed = len(df[df["Status"].isin(["APPROVED", "REJECTED"])])
        if reviewed > 0:
            approved = len(df[df["Status"] == "APPROVED"])
            st.metric(
                "Approve-Rate",
                f"{approved / reviewed * 100:.0f}%",
                help=f"{approved} von {reviewed} bewerteten Artikeln",
            )

        # CSV export
        st.subheader("Export")
        approved_df = df[df["Status"] == "APPROVED"]
        if len(approved_df) > 0:
            csv = approved_df.to_csv(index=False)
            st.download_button(
                "📥 Freigegebene Artikel als CSV",
                csv,
                "medintel_approved.csv",
                "text/csv",
            )
        else:
            st.info("Noch keine freigegebenen Artikel zum Exportieren.")
    else:
        st.info("Noch keine Daten vorhanden. Führe zuerst die Pipeline aus.")


# ---- Tab: Digest Preview --------------------------------------------------
with tab_digest:
    st.header("E-Mail-Digest Preview")
    st.caption(
        "Vorschau des täglichen E-Mail-Briefings (Top 10 nach Relevanz-Score)"
    )

    from src.digest import get_top_articles, _build_html

    digest_articles = get_top_articles(10)
    if digest_articles:
        html = _build_html(digest_articles, date.today())
        st.components.v1.html(html, height=800, scrolling=True)

        # Manual pipeline run
        st.divider()
        st.subheader("Pipeline manuell starten")
        col_run1, col_run2 = st.columns([1, 3])
        with col_run1:
            days = st.number_input("Tage zurück", min_value=1, max_value=30, value=2)
        with col_run2:
            if st.button("🔄 Pipeline jetzt ausführen"):
                with st.spinner("Pipeline läuft..."):
                    import asyncio
                    from src.pipeline import run_pipeline
                    stats = asyncio.run(run_pipeline(days_back=days))
                    st.success(
                        f"Pipeline fertig! {stats.get('ingested', 0)} Artikel "
                        f"→ {stats.get('stored', 0)} neu gespeichert "
                        f"({stats.get('elapsed_seconds', 0)}s)"
                    )
                    st.rerun()
    else:
        st.info("Noch keine Artikel vorhanden.")

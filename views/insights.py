"""Lumio — Insights tab: analytics, charts, heatmap, exports."""
from __future__ import annotations

import logging

import altair as alt
import pandas as pd
import streamlit as st

from src.config import SPECIALTY_MESH, SCORE_THRESHOLD_HIGH


def _chart_config() -> dict:
    """Return Altair .configure() kwargs based on current theme."""
    is_esanum = st.session_state.get("theme") == "esanum"
    if is_esanum:
        return dict(
            background="#FFFFFF",
            axis=alt.AxisConfig(
                labelFontSize=11,
                gridColor="rgba(0,0,0,0.06)",
                domainColor="rgba(0,0,0,0.12)",
                labelColor="#555555",
                titleColor="#333333",
            ),
            legend=alt.LegendConfig(labelColor="#555555", titleColor="#333333"),
            title=alt.TitleConfig(color="#333333"),
            view=alt.ViewConfig(strokeWidth=0),
        )
    else:
        return dict(
            axis=alt.AxisConfig(
                labelFontSize=11,
                gridColor="rgba(255,255,255,0.05)",
                domainColor="rgba(255,255,255,0.08)",
                labelColor="#8b8ba0",
            ),
            view=alt.ViewConfig(strokeWidth=0),
        )

from components.helpers import (
    _esc, get_articles, get_heatmap_data, score_pill, spec_pill,
    SPECIALTY_COLORS,
    ALTAIR_FONT, APPLE_BLUE, APPLE_RED, APPLE_PURPLE,
)
logger = logging.getLogger(__name__)


def render_insights(filters: dict):
    """Render the Insights tab content."""
    all_articles = get_articles(
        specialties=tuple(filters["selected_specialties"]) if filters["selected_specialties"] else None,
        sources=tuple(filters["selected_sources"]) if filters["selected_sources"] else None,
        min_score=0,
        date_from=filters["date_from"], date_to=filters["date_to"],
        status_filter=filters["status_filter"],
        language=filters["language_filter"],
        study_types=tuple(filters["selected_study_types"]) if filters["selected_study_types"] else None,
        open_access_only=filters["open_access_only"],
    )

    if not all_articles:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📊</div>
                <div class="empty-state-text">Noch keine Daten für diesen Zeitraum</div>
                <div style="font-size:0.8rem;color:var(--c-text-muted);margin-top:8px">
                    Versuche einen längeren Zeitraum in der Seitenleiste zu wählen,
                    oder prüfe ob die Artikel-Pipeline aktiv ist.
                </div>
            </div>
        """, unsafe_allow_html=True)
        return

    # Expand articles into multiple rows for secondary specialties
    # so each cross-cutting article counts in ALL relevant specialties
    # Expand articles: each cross-cutting article counts in ALL relevant specialties
    _article_rows = []
    for a in all_articles:
        _base = {
            "Quelle": a.source,
            "Score": a.relevance_score,
            "Status": a.status,
            "Datum": a.pub_date,
            "Journal": a.journal or "Unbekannt",
            "Titel": a.title,
            "URL": a.url or "",
            "Artikeltyp": a.study_type or "Unbekannt",
            "Sprache": a.language or "?",
            "Quellenkategorie": a.source_category,
        }
        _base["Fachgebiet"] = a.specialty or "Unklassifiziert"
        _article_rows.append({**_base})
        if a.secondary_specialties:
            for _sec in a.secondary_specialties.split(","):
                _sec = _sec.strip()
                if _sec and _sec != a.specialty:
                    _article_rows.append({**_base, "Fachgebiet": _sec})

    df = pd.DataFrame(_article_rows)
    df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")

    total = len(df)
    reviewed = len(df[df["Status"].isin(["APPROVED", "REJECTED"])])
    approved_n = len(df[df["Status"] == "APPROVED"])
    avg_score = df["Score"].mean()
    high_q = len(df[df["Score"] >= SCORE_THRESHOLD_HIGH])
    de_count = len(df[df["Sprache"] == "de"])

    # --- KPI Header ---
    st.markdown('<div class="page-header">Insights</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Quellenqualit\u00e4t, Fachgebiete und Scoring auf einen Blick</div>', unsafe_allow_html=True)

    _reviewed_display = str(reviewed) if reviewed else "\u2014"
    _approval_rate = f"{approved_n/reviewed*100:.0f}%" if reviewed else "\u2014"
    _hq_pct = f"{high_q/total*100:.0f}" if total else "0"
    _de_pct = f"{de_count/total*100:.0f}" if total else "0"

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:28px">
        <div class="kpi-card">
            <div class="kpi-value">{total}</div>
            <div class="kpi-label">Artikel</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{avg_score:.0f}</div>
            <div class="kpi-label">\u00d8 Score</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{high_q}</div>
            <div class="kpi-label">Top-Evidenz</div>
            <div class="kpi-delta" style="color:var(--c-success)">{_hq_pct}% der Artikel</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{de_count}</div>
            <div class="kpi-label">Deutsch</div>
            <div class="kpi-delta" style="color:var(--c-accent)">{_de_pct}% Anteil</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{approved_n}/{_reviewed_display}</div>
            <div class="kpi-label">Freigegeben</div>
            <div class="kpi-delta" style="color:var(--c-success)">{_approval_rate} Rate</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Trend-Heatmap: Fachgebiet x Woche ---
    _render_heatmap()

    # --- Quellen-Qualitat ---
    _render_source_quality(df)

    # --- Fachgebiet + Score side by side ---
    _render_specialty_and_coverage(df)

    # --- Score Distribution + Top Articles ---
    _render_score_distribution(df, avg_score)

    # --- Workflow + Study Types ---
    _render_workflow_and_types(df, total, reviewed, approved_n)

    # --- Export ---
    _render_export(df)


# NOTE: Redaktions-Gedächtnis, Lücken-Detektor, and Konkurrenz-Radar
# have been moved to views/redaktion.py — dead code removed.



# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------

def _render_heatmap():
    """Render the trend heatmap."""
    _hm_data = get_heatmap_data()
    if _hm_data.empty or len(_hm_data) <= 3:
        return

    st.markdown(
        '<div class="section-header">\U0001f525 Trend-Heatmap</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-sub">Artikelvolumen pro Fachgebiet und Kalenderwoche \u2014 dunkler = mehr Artikel</div>',
        unsafe_allow_html=True,
    )

    # Sort weeks chronologically, keep only last 8
    _hm_weeks = _hm_data.sort_values("sort_key")["Woche"].unique()
    if len(_hm_weeks) > 8:
        _hm_weeks = _hm_weeks[-8:]
        _hm_data = _hm_data[_hm_data["Woche"].isin(_hm_weeks)]

    # Sort specialties by total article count (most active at top)
    _spec_order = (
        _hm_data.groupby("Fachgebiet")["Anzahl"].sum()
        .sort_values(ascending=False).index.tolist()
    )

    # Build animated HTML heatmap grid
    _hm_lookup = {}
    _hm_max = max(_hm_data["Anzahl"].max(), 1)
    for _, r in _hm_data.iterrows():
        _hm_lookup[(r["Fachgebiet"], r["Woche"])] = (r["Anzahl"], r.get("Avg_Score", 0))

    # Viridis-inspired color stops (dark -> bright)
    def _hm_color(val, mx):
        t = val / mx if mx else 0
        if t < 0.25:
            return f"rgba(68, 1, 84, {0.3 + t * 2})"
        elif t < 0.5:
            return f"rgba(59, 82, 139, {0.5 + t})"
        elif t < 0.75:
            return f"rgba(33, 145, 140, {0.6 + t * 0.4})"
        else:
            return f"rgba(94, 201, 98, {0.7 + t * 0.3})"

    _n_cols = len(_hm_weeks)
    _grid_cols_css = f"120px repeat({_n_cols}, 1fr)"
    _header_row = '<div class="hm-label"></div>'  # empty corner
    for wk in _hm_weeks:
        _header_row += f'<div class="hm-col-header">{wk}</div>'

    _body_rows = ""
    for spec in _spec_order:
        _body_rows += f'<div class="hm-label">{_esc(spec)}</div>'
        for ci, wk in enumerate(_hm_weeks):
            count, avg = _hm_lookup.get((spec, wk), (0, 0))
            _empty_bg = "rgba(0,0,0,0.03)" if st.session_state.get("theme") == "esanum" else "rgba(255,255,255,0.03)"
            bg = _hm_color(count, _hm_max) if count > 0 else _empty_bg
            delay = ci * 0.12
            label = str(count) if count > 0 else ""
            title_attr = f'title="{spec} \u00b7 {wk}: {count} Artikel, \u00d8 {avg:.0f}"' if count else ""
            _body_rows += (
                f'<div class="hm-cell" style="background:{bg};'
                f'animation-delay:{delay:.2f}s" {title_attr}>{label}</div>'
            )

    st.markdown(
        f'<div class="hm-grid" style="grid-template-columns:{_grid_cols_css}">'
        f'{_header_row}{_body_rows}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


def _render_source_quality(df: pd.DataFrame):
    """Render the source quality table."""
    st.markdown('<div class="section-header">Quellen-Qualit\u00e4t</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Welche Quellen liefern die relevantesten Artikel?</div>', unsafe_allow_html=True)

    source_quality = (
        df.groupby("Journal")
        .agg(Anzahl=("Score", "size"), Avg=("Score", "mean"),
             Max=("Score", "max"), HQ=("Score", lambda x: (x >= SCORE_THRESHOLD_HIGH).sum()))
        .sort_values("Avg", ascending=False).head(20)
    )
    source_quality.index.name = "Quelle"
    source_quality["Avg"] = source_quality["Avg"].round(1)
    source_quality["Max"] = source_quality["Max"].round(1)
    source_quality["HQ%"] = (source_quality["HQ"] / source_quality["Anzahl"].replace(0, 1) * 100).round(0).astype(int).astype(str) + "%"

    sq_display = source_quality[["Anzahl", "Avg", "Max", "HQ%"]].copy()
    sq_display.columns = ["Artikel", "Avg Score", "Max Score", "Score ≥70"]
    # Use Streamlit's native table for better theme compatibility
    if st.session_state.get("theme") == "esanum":
        st.table(sq_display)
    else:
        st.dataframe(sq_display, use_container_width=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


def _render_specialty_and_coverage(df: pd.DataFrame):
    """Render specialty distribution chart and coverage check."""
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<div class="section-header">Fachgebiet-Verteilung</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Artikelzahl und Durchschnitts-Score pro Fachgebiet</div>', unsafe_allow_html=True)

        spec_stats = (
            df.groupby("Fachgebiet", as_index=False)
            .agg(Anzahl=("Score", "size"), Avg_Score=("Score", "mean"))
            .sort_values("Anzahl", ascending=False)
        )
        spec_stats["Avg_Score"] = spec_stats["Avg_Score"].round(1)
        spec_chart_df = spec_stats.reset_index(drop=True)
        # Explicit sort order so Altair doesn't create duplicate rows
        _sort_order = spec_chart_df["Fachgebiet"].tolist()

        bars = alt.Chart(spec_chart_df).mark_bar(
            cornerRadiusTopRight=6, cornerRadiusBottomRight=6
        ).encode(
            x=alt.X("Anzahl:Q", title="Anzahl"),
            y=alt.Y("Fachgebiet:N", sort=_sort_order, title=None),
            color=alt.Color("Avg_Score:Q",
                scale=alt.Scale(scheme="blueorange", domain=[20, 80]),
                legend=alt.Legend(title="Score",
                    labelColor="#555555" if st.session_state.get("theme") == "esanum" else "#8b8ba0",
                    titleColor="#333333" if st.session_state.get("theme") == "esanum" else "#a0a0b8")),
            tooltip=["Fachgebiet", "Anzahl", "Avg_Score"],
        ).properties(height=360).configure(font=ALTAIR_FONT, **_chart_config())
        st.altair_chart(bars, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-header">Abdeckungs-Check</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Haben alle Fachgebiete ausreichend Artikel?</div>', unsafe_allow_html=True)

        all_specialties_config = list(SPECIALTY_MESH.keys())
        found = set(df[df["Fachgebiet"] != "Unklassifiziert"]["Fachgebiet"].unique())

        coverage_rows = []
        for spec in all_specialties_config:
            count = len(df[df["Fachgebiet"] == spec])
            if count == 0:
                icon, label, color = "\u25cb", "Keine", "#f87171"
            elif count < 5:
                icon, label, color = "\u25d0", f"{count} Artikel", "#fbbf24"
            else:
                icon, label, color = "\u25cf", f"{count} Artikel", "#4ade80"
            coverage_rows.append(
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:6px 0;border-bottom:1px solid var(--c-border)">'
                f'<span style="font-size:0.82rem;color:var(--c-text)">{spec}</span>'
                f'<span style="font-size:0.78rem;color:{color};font-weight:600">'
                f'{icon} {label}</span></div>'
            )

        st.markdown(
            f'<div class="med-card">{"".join(coverage_rows)}</div>',
            unsafe_allow_html=True
        )

        uncovered = set(all_specialties_config) - found
        if uncovered:
            st.warning(f"{len(uncovered)} Fachgebiet(e) ohne Abdeckung")
            _uc_list = sorted(uncovered)[:3]
            for uc in _uc_list:
                if st.button(f"🔍 {uc} suchen", key=f"coverage_search_{uc}"):
                    st.session_state["prefill_search"] = uc
                    st.rerun()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


def _render_score_distribution(df: pd.DataFrame, avg_score: float):
    """Render score histogram and top 10 articles."""
    col_hist, col_top = st.columns([3, 2])

    with col_hist:
        st.markdown('<div class="section-header">Score-Verteilung</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Wie verteilen sich die Relevanz-Scores?</div>', unsafe_allow_html=True)

        hist = alt.Chart(df).mark_bar(
            cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
            color=APPLE_BLUE, opacity=0.8,
        ).encode(
            x=alt.X("Score:Q", bin=alt.Bin(step=10), title="Score"),
            y=alt.Y("count()", title="Artikel"),
            tooltip=["count()"],
        ).properties(height=260)

        rule = alt.Chart(df).mark_rule(
            color=APPLE_RED, strokeDash=[6, 4], strokeWidth=2
        ).encode(x=alt.X("mean(Score):Q"))

        chart = (hist + rule).configure(font=ALTAIR_FONT, **_chart_config())
        st.altair_chart(chart, use_container_width=True)
        st.markdown(
            f'<div style="font-size:0.75rem;color:var(--c-text-tertiary);margin-top:-8px">'
            f'Rote Linie = Durchschnitt ({avg_score:.1f})</div>',
            unsafe_allow_html=True
        )

    with col_top:
        st.markdown('<div class="section-header">Top 10</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">H\u00f6chstbewertete Artikel</div>', unsafe_allow_html=True)

        top10 = df.nlargest(10, "Score")
        top_rows = []
        for i, row in enumerate(top10.itertuples(), 1):
            score_val = row.Score
            raw_title = row.Titel[:50] + "..." if len(row.Titel) > 50 else row.Titel
            safe_t = _esc(raw_title)
            safe_u = _esc(row.URL) if row.URL else ""
            title_el = (
                f'<a href="{safe_u}" target="_blank" style="color:var(--c-text);'
                f'text-decoration:none;font-size:0.8rem;font-weight:500">{safe_t}</a>'
                if safe_u
                else f'<span style="font-size:0.8rem">{safe_t}</span>'
            )
            top_rows.append(
                f'<div style="display:flex;align-items:center;gap:10px;'
                f'padding:7px 0;border-bottom:1px solid var(--c-border)">'
                f'<span style="font-size:0.7rem;color:var(--c-text-muted);width:16px">{i}</span>'
                f'{score_pill(score_val)}'
                f'<div style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;'
                f'white-space:nowrap">{title_el}</div></div>'
            )

        st.markdown(
            f'<div class="med-card" style="padding:12px 16px">{"".join(top_rows)}</div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


def _render_workflow_and_types(df: pd.DataFrame, total: int, reviewed: int, approved_n: int):
    """Render workflow donut, progress, and study types charts."""
    col_wf1, col_wf2, col_wf3 = st.columns(3)

    with col_wf1:
        st.markdown('<div class="section-header">Workflow</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Status-Verteilung</div>', unsafe_allow_html=True)

        status_map = {"NEW": "Neu", "APPROVED": "Freigegeben",
                      "REJECTED": "Abgelehnt", "SAVED": "Gemerkt", "ALERT": "Alert"}
        status_df = df["Status"].map(lambda s: status_map.get(s, s)).value_counts().reset_index()
        status_df.columns = ["Status", "Anzahl"]

        donut = alt.Chart(status_df).mark_arc(
            innerRadius=45, outerRadius=80, cornerRadius=4
        ).encode(
            theta=alt.Theta("Anzahl:Q"),
            color=alt.Color("Status:N",
                scale=alt.Scale(
                    domain=["Neu", "Freigegeben", "Abgelehnt", "Gemerkt", "Alert"],
                    range=["#6b6b82", "#4ade80", "#f87171", "#a3e635", "#fbbf24"]),
                legend=alt.Legend(title=None, orient="bottom", columns=3,
                    labelColor="#555555" if st.session_state.get("theme") == "esanum" else "#8b8ba0")),
            tooltip=["Status:N", "Anzahl:Q"],
        ).properties(
            height=260,
            padding={"top": 20, "bottom": 10, "left": 10, "right": 10},
        ).configure(font=ALTAIR_FONT, **_chart_config())
        st.altair_chart(donut, use_container_width=True)

    with col_wf2:
        st.markdown('<div class="section-header">Fortschritt</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Bewertungsquote</div>', unsafe_allow_html=True)

        progress = reviewed / total * 100 if total else 0
        st.markdown(f"""
            <div class="med-card" style="text-align:center;padding:28px 20px">
                <div style="font-size:2.8rem;font-weight:700;color:var(--c-text);
                            letter-spacing:-0.04em;line-height:1">{progress:.0f}%</div>
                <div style="font-size:0.78rem;color:var(--c-text-tertiary);margin:8px 0 16px 0">bewertet</div>
                <div class="progress-track">
                    <div class="progress-fill" style="width:{min(progress, 100)}%"></div>
                </div>
                <div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:8px">
                    {reviewed} von {total} Artikeln
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_wf3:
        st.markdown('<div class="section-header">Artikeltypen</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Verteilung nach Artikelart</div>', unsafe_allow_html=True)

        # Use source_category if available, fall back to study_type
        if "Quellenkategorie" in df.columns and df["Quellenkategorie"].notna().sum() > 0:
            _cat_labels = {
                "top_journal": "Top-Journal",
                "specialty_journal": "Fachjournal",
                "fachpresse_de": "Dt. Fachpresse",
                "fachpresse_aufbereitet": "Aufbereitet",
                "berufspolitik": "Berufspolitik",
                "behoerde": "Behörde",
                "leitlinie": "Leitlinie",
                "fachgesellschaft": "Fachgesellschaft",
                "literaturdatenbank": "Literaturdatenbank",
                "preprint": "Preprint",
                "news_aggregation": "News",
            }
            cat_series = df["Quellenkategorie"].map(lambda x: _cat_labels.get(x, x) if pd.notna(x) else "Unbekannt")
            study_counts = cat_series.value_counts().head(8).reset_index()
            study_counts.columns = ["Quellentyp", "Anzahl"]
        else:
            study_counts = df["Artikeltyp"].value_counts().head(8).reset_index()
            study_counts.columns = ["Quellentyp", "Anzahl"]

        study_chart = alt.Chart(study_counts).mark_bar(
            cornerRadiusTopRight=6, cornerRadiusBottomRight=6,
            color=APPLE_PURPLE, opacity=0.8,
        ).encode(
            x=alt.X("Anzahl:Q", title=None),
            y=alt.Y("Quellentyp:N", sort="-x", title=None),
            tooltip=["Quellentyp:N", "Anzahl:Q"],
        ).properties(height=220).configure(font=ALTAIR_FONT, **_chart_config())
        st.altair_chart(study_chart, use_container_width=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


def _render_export(df: pd.DataFrame):
    """Render the export section."""
    st.markdown('<div class="section-header">Export</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Daten als CSV herunterladen</div>', unsafe_allow_html=True)

    exp1, exp2, exp3 = st.columns(3)
    with exp1:
        approved_df = df[df["Status"] == "APPROVED"]
        if len(approved_df) > 0:
            st.download_button(
                "Freigegebene Artikel",
                approved_df.to_csv(index=False), "lumio_approved.csv", "text/csv",
            )
        else:
            st.caption("Noch keine Freigaben")
    with exp2:
        st.download_button(
            "Alle Artikel",
            df.to_csv(index=False), "lumio_alle.csv", "text/csv",
        )
    with exp3:
        hq_df = df[df["Score"] >= SCORE_THRESHOLD_HIGH]
        st.download_button(
            f"High-Quality ({len(hq_df)})",
            hq_df.to_csv(index=False), "lumio_highquality.csv", "text/csv",
        )

    # ------------------------------------------------------------------
    # GA4 Nutzerverhalten — was Ärzte auf esanum tun
    # ------------------------------------------------------------------
    _render_ga4_insights()


def _render_ga4_insights():
    """Render GA4 user behavior insights from cached signal data."""
    try:
        from src.processing.ga4_signals import get_signal_cache
    except ImportError:
        return

    report = get_signal_cache("ga4_report")
    fachgebiet_data = get_signal_cache("ga4_fachgebiet_engagement")
    peak_data = get_signal_cache("ga4_peak_hours")
    device_data = get_signal_cache("ga4_devices")

    # Only render if we have some data
    if not any([report, fachgebiet_data, peak_data, device_data]):
        st.markdown(
            '<div style="text-align:center;padding:16px;margin-top:24px;'
            'border:1px dashed var(--c-border);border-radius:10px;'
            'color:var(--c-text-tertiary);font-size:0.8rem">'
            '\U0001f4e1 GA4-Daten noch nicht verf\u00fcgbar. '
            'Sie werden beim n\u00e4chsten Pipeline-Run geladen.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div class="page-header" style="margin-top:32px">'
        '\U0001f4e1 Nutzerverhalten (GA4)</div>'
        '<div class="page-sub">Was \u00c4rzte auf esanum suchen, lesen und \u00fcberspringen</div>',
        unsafe_allow_html=True,
    )

    # --- Row 1: KPIs ---
    kpi_cols = st.columns(4)

    if device_data:
        kpi_cols[0].markdown(
            f'<div class="med-card" style="text-align:center;padding:14px">'
            f'<div style="font-size:1.6rem;font-weight:800;color:var(--c-text)">'
            f'{device_data.get("total_sessions", 0):,}</div>'
            f'<div style="font-size:0.65rem;font-weight:600;color:var(--c-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.04em;margin-top:4px">'
            f'Sessions (7d)</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        kpi_cols[1].markdown(
            f'<div class="med-card" style="text-align:center;padding:14px">'
            f'<div style="font-size:1.6rem;font-weight:800;color:#60a5fa">'
            f'{device_data.get("desktop_pct", 0):.0f}%</div>'
            f'<div style="font-size:0.65rem;font-weight:600;color:var(--c-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.04em;margin-top:4px">'
            f'Desktop</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        kpi_cols[2].markdown(
            f'<div class="med-card" style="text-align:center;padding:14px">'
            f'<div style="font-size:1.6rem;font-weight:800;color:#f59e0b">'
            f'{device_data.get("mobile_pct", 0):.0f}%</div>'
            f'<div style="font-size:0.65rem;font-weight:600;color:var(--c-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.04em;margin-top:4px">'
            f'Mobile</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if peak_data and peak_data.get("peak_hours"):
        peak_str = ", ".join(f"{h}:00" for h in peak_data["peak_hours"])
        kpi_cols[3].markdown(
            f'<div class="med-card" style="text-align:center;padding:14px">'
            f'<div style="font-size:1.1rem;font-weight:800;color:#4ade80">'
            f'{peak_str}</div>'
            f'<div style="font-size:0.65rem;font-weight:600;color:var(--c-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.04em;margin-top:4px">'
            f'Peak-Zeiten</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Row 2: Fachgebiet-Engagement ---
    if fachgebiet_data and fachgebiet_data.get("fachgebiete"):
        st.markdown(
            '<div class="section-header" style="margin-top:20px">'
            'Fachgebiet-Nachfrage</div>'
            '<div style="font-size:0.75rem;color:var(--c-text-tertiary);margin-bottom:12px">'
            'Welche Fachbereiche werden am meisten besucht und wie lange lesen \u00c4rzte dort?</div>',
            unsafe_allow_html=True,
        )

        fach_list = fachgebiet_data["fachgebiete"][:15]
        max_sessions = max(f["sessions"] for f in fach_list) if fach_list else 1

        for f in fach_list:
            bar_pct = min(100, f["sessions"] / max_sessions * 100)
            eng_color = "#4ade80" if f["engagement_rate"] >= 0.85 else "#fbbf24" if f["engagement_rate"] >= 0.75 else "#f87171"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;padding:4px 0;'
                f'border-bottom:1px solid rgba(255,255,255,0.04)">'
                f'<span style="font-size:0.78rem;font-weight:600;color:var(--c-text);'
                f'min-width:140px">{f["name"]}</span>'
                f'<div style="flex:1;height:8px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden">'
                f'<div style="width:{bar_pct:.0f}%;height:100%;background:var(--c-accent);'
                f'border-radius:4px;transition:width 0.6s"></div></div>'
                f'<span style="font-size:0.72rem;color:var(--c-text-muted);min-width:60px;text-align:right">'
                f'{f["sessions"]:,}</span>'
                f'<span style="font-size:0.72rem;font-weight:600;color:{eng_color};min-width:45px;text-align:right">'
                f'{f["avg_engagement_seconds"]:.0f}s</span>'
                f'<span style="font-size:0.65rem;color:{eng_color};min-width:40px;text-align:right">'
                f'{f["engagement_rate"]:.0%}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --- Row 3: Nachfrage-Signale (Null-Suchen) ---
    if report and report.get("null_searches"):
        st.markdown(
            '<div class="section-header" style="margin-top:20px">'
            'Nachfrage-Signale</div>'
            '<div style="font-size:0.75rem;color:var(--c-text-tertiary);margin-bottom:12px">'
            'Themen, nach denen Ärzte gesucht haben — inkl. Suchbegriffe ohne Ergebnis</div>',
            unsafe_allow_html=True,
        )

        for ns in report["null_searches"][:10]:
            st.markdown(
                f'<div class="med-card" style="display:flex;align-items:center;gap:10px;'
                f'padding:10px 14px;margin-bottom:4px">'
                f'<span style="font-size:0.82rem;font-weight:600;color:var(--c-text)">'
                f'\u201e{ns["term"]}\u201c</span>'
                f'<span style="margin-left:auto;font-size:0.72rem;font-weight:600;'
                f'color:var(--c-accent);background:rgba(163,230,53,0.1);'
                f'padding:2px 8px;border-radius:6px">'
                f'{ns["session_count"]} Sessions</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --- Row 4: Bounce-Signale (schlecht performende Seiten) ---
    if report and report.get("bounce_signals"):
        st.markdown(
            '<div class="section-header" style="margin-top:20px">'
            'Hohe Absprungrate</div>'
            '<div style="font-size:0.75rem;color:var(--c-text-tertiary);margin-bottom:12px">'
            'Seiten, die \u00c4rzte schnell wieder verlassen (&gt;70% Absprungrate)</div>',
            unsafe_allow_html=True,
        )

        for bs in report["bounce_signals"][:8]:
            bounce_color = "#f87171" if bs["bounce_rate"] > 0.85 else "#fbbf24"
            st.markdown(
                f'<div class="med-card" style="display:flex;align-items:center;gap:10px;'
                f'padding:10px 14px;margin-bottom:4px">'
                f'<span style="font-size:0.78rem;color:var(--c-text);flex:1;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
                f'{bs["page_title"]}</span>'
                f'<span style="font-size:0.72rem;font-weight:600;color:{bounce_color};'
                f'min-width:45px;text-align:right">'
                f'{bs["bounce_rate"]:.0%}</span>'
                f'<span style="font-size:0.72rem;color:var(--c-text-muted);'
                f'min-width:50px;text-align:right">'
                f'{bs["sessions"]} Sess.</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

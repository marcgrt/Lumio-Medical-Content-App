"""Lumio — Redaktion tab: Lücken-Detektor, Redaktions-Gedächtnis, Konkurrenz-Radar."""
from __future__ import annotations

import logging

import altair as alt
import pandas as pd
import streamlit as st

from src.config import SPECIALTY_MESH, SCORE_THRESHOLD_HIGH
from components.helpers import (
    _esc, score_pill, spec_pill, momentum_badge,
    SPECIALTY_COLORS, ALTAIR_FONT, APPLE_BLUE,
)
from src.processing.konkurrenz_radar import (
    generate_konkurrenz_report, KonkurrenzReport, COMPETITOR_SOURCES,
)

logger = logging.getLogger(__name__)


def render_redaktion():
    """Render the Redaktion tab — editorial tools."""
    st.markdown('<div class="page-header">Redaktion</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Lücken-Detektor · Redaktions-Gedächtnis · Konkurrenz-Radar</div>',
        unsafe_allow_html=True,
    )

    # Each section gets its own expander — but they're visible directly, not buried
    _render_luecken_detektor()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    _render_redaktions_gedaechtnis()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    _render_konkurrenz_radar()


# ---------------------------------------------------------------------------
# Redaktions-Gedächtnis
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _load_editorial_memory_report() -> dict:
    """Load editorial memory report (cached 30 min)."""
    try:
        from src.processing.redaktions_gedaechtnis import get_editorial_report
        report = get_editorial_report(days=30)
        return {
            "topics_covered_30d": report.topics_covered_30d,
            "topics_stale": report.topics_stale,
            "most_covered_specialties": report.most_covered_specialties,
            "least_covered_specialties": report.least_covered_specialties,
            "approval_patterns": report.approval_patterns,
        }
    except Exception as e:
        logger.error("Redaktions-Gedaechtnis Fehler: %s", e)
        return {
            "topics_covered_30d": {},
            "topics_stale": [],
            "most_covered_specialties": [],
            "least_covered_specialties": [],
            "approval_patterns": {},
        }


def _render_redaktions_gedaechtnis():
    """Render the Redaktions-Gedächtnis section."""
    report = _load_editorial_memory_report()

    with st.expander("\U0001f9e0 Redaktions-Gedächtnis — Was wurde bereits berichtet?", expanded=False):

        topics_30d = report.get("topics_covered_30d", {})
        stale = report.get("topics_stale", [])
        most_covered = report.get("most_covered_specialties", [])
        least_covered = report.get("least_covered_specialties", [])
        patterns = report.get("approval_patterns", {})

        if not topics_30d and not patterns:
            st.markdown(
                '<div class="med-card" style="text-align:center;padding:20px">'
                '<div style="font-size:1rem;margin-bottom:6px">'
                'Noch keine Daten verfügbar</div>'
                '<div style="font-size:0.8rem;color:var(--c-text-tertiary)">'
                'Gib zuerst Artikel frei, um das Redaktions-Gedächtnis aufzubauen.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        # --- Approval Patterns: KPI row ---
        avg_appr = patterns.get("avg_score_approved", 0)
        avg_rej = patterns.get("avg_score_rejected", 0)
        total_appr = patterns.get("total_approved", 0)
        approval_rate = patterns.get("approval_rate", 0)

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px">
            <div class="kpi-card">
                <div class="kpi-value">{avg_appr:.0f}</div>
                <div class="kpi-label">\u00d8 Score Freigegeben</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{avg_rej:.0f}</div>
                <div class="kpi-label">\u00d8 Score Abgelehnt</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{total_appr}</div>
                <div class="kpi-label">Freigaben (30d)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{approval_rate:.0f}%</div>
                <div class="kpi-label">Freigabe-Rate</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- Two columns: Topics covered + Stale topics ---
        col_topics, col_stale = st.columns(2)

        with col_topics:
            st.markdown(
                '<div class="section-header" style="font-size:0.9rem;margin-bottom:8px">'
                'Berichtete Themen (30 Tage)</div>',
                unsafe_allow_html=True,
            )

            if topics_30d:
                top_topics = dict(list(topics_30d.items())[:15])
                topic_df = pd.DataFrame([
                    {"Thema": t.replace("_", " ").title(), "Artikel": c}
                    for t, c in top_topics.items()
                ])
                topic_chart = alt.Chart(topic_df).mark_bar(
                    cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                    color=APPLE_BLUE, opacity=0.8,
                ).encode(
                    x=alt.X("Artikel:Q", title=None),
                    y=alt.Y("Thema:N", sort="-x", title=None),
                    tooltip=["Thema:N", "Artikel:Q"],
                ).properties(height=min(len(top_topics) * 24, 360)).configure(
                    font=ALTAIR_FONT,
                    axis=alt.AxisConfig(
                        labelFontSize=10, gridColor="rgba(255,255,255,0.05)",
                        domainColor="rgba(255,255,255,0.08)", labelColor="#8b8ba0",
                    ),
                    view=alt.ViewConfig(strokeWidth=0),
                )
                st.altair_chart(topic_chart, use_container_width=True)
            else:
                st.caption("Noch keine freigegebenen Themen.")

        with col_stale:
            st.markdown(
                '<div class="section-header" style="font-size:0.9rem;margin-bottom:8px">'
                '\u23f0 Update fällig</div>',
                unsafe_allow_html=True,
            )

            if stale:
                for item in stale[:8]:
                    topic = _esc(item["topic"].replace("_", " ").title())
                    days_ago = item.get("days_ago", "?")
                    new_count = item.get("new_article_count", 0)
                    st.markdown(
                        f'<div class="med-card" style="padding:8px 12px;margin-bottom:6px">'
                        f'<div style="display:flex;align-items:center;justify-content:space-between">'
                        f'<span style="font-size:0.82rem;font-weight:600;color:var(--c-text)">'
                        f'{topic}</span>'
                        f'<span style="font-size:0.7rem;color:#f87171;font-weight:600">'
                        f'{days_ago}d her</span>'
                        f'</div>'
                        f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:3px">'
                        f'{new_count} neue Artikel warten auf Review</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="font-size:0.8rem;color:var(--c-text-tertiary);'
                    'padding:12px 0">Alle Themen aktuell abgedeckt.</div>',
                    unsafe_allow_html=True,
                )

        # --- Specialty coverage balance ---
        st.markdown(
            '<div class="section-header" style="font-size:0.9rem;margin-top:16px;margin-bottom:8px">'
            'Fachgebiet-Balance (Freigaben 30d)</div>',
            unsafe_allow_html=True,
        )

        col_most, col_least = st.columns(2)

        with col_most:
            st.markdown(
                '<div style="font-size:0.78rem;color:var(--c-text-muted);margin-bottom:6px">'
                '\u2705 Am meisten berichtet</div>',
                unsafe_allow_html=True,
            )
            for spec, count in most_covered:
                pill = spec_pill(spec)
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0">'
                    f'{pill} '
                    f'<span style="font-size:0.78rem;color:var(--c-text)">{count} Freigaben</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        with col_least:
            st.markdown(
                '<div style="font-size:0.78rem;color:var(--c-text-muted);margin-bottom:6px">'
                '\u26a0\ufe0f Am wenigsten berichtet</div>',
                unsafe_allow_html=True,
            )
            for spec, count in least_covered:
                pill = spec_pill(spec)
                label = f"{count} Freigaben" if count > 0 else "Keine Freigaben"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0">'
                    f'{pill} '
                    f'<span style="font-size:0.78rem;color:var(--c-text)">{label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Lücken-Detektor
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _load_gap_report() -> dict:
    """Lade den Lücken-Report (gecacht für 30 Minuten)."""
    try:
        from src.processing.luecken_detektor import get_full_gap_report
        return get_full_gap_report(days=7)
    except Exception as e:
        logger.error("Lücken-Detektor Fehler: %s", e)
        return {
            "coverage_gaps": [],
            "topic_gaps": [],
            "summary_stats": {
                "total_specialties": len(SPECIALTY_MESH),
                "underserved_count": 0,
                "trending_uncovered": 0,
                "biggest_gap": None,
            },
            "generated_at": None,
        }


def _render_luecken_detektor():
    """Rendert den Lücken-Detektor — redaktionelle Blindstellen."""
    report = _load_gap_report()
    coverage_gaps = report.get("coverage_gaps", [])
    topic_gaps = report.get("topic_gaps", [])
    stats = report.get("summary_stats", {})

    with st.expander("\U0001f50d Lücken-Detektor — Redaktionelle Blindstellen", expanded=True):

        underserved = stats.get("underserved_count", 0)
        uncovered = stats.get("trending_uncovered", 0)

        if underserved == 0 and uncovered == 0:
            st.markdown(
                '<div class="med-card" style="text-align:center;padding:20px">'
                '<div style="font-size:1.2rem;margin-bottom:6px">'
                'Keine Lücken erkannt — gute redaktionelle Abdeckung! \U0001f389</div>'
                '<div style="font-size:0.8rem;color:var(--c-text-tertiary)">'
                'Alle Fachgebiete und Trend-Themen sind redaktionell betreut.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        biggest = stats.get("biggest_gap") or "\u2014"
        st.markdown(
            f'<div class="med-card" style="padding:12px 16px;margin-bottom:16px;'
            f'display:flex;gap:24px;align-items:center;flex-wrap:wrap">'
            f'<div style="font-size:0.85rem;color:var(--c-text)">'
            f'\U0001f534 <b>{underserved}</b> Fachgebiet(e) unterversorgt</div>'
            f'<div style="font-size:0.85rem;color:var(--c-text)">'
            f'\U0001f7e1 <b>{uncovered}</b> Trend-Themen unbearbeitet</div>'
            f'<div style="font-size:0.78rem;color:var(--c-text-tertiary)">'
            f'Größte Lücke: {_esc(biggest)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if coverage_gaps:
            st.markdown(
                '<div class="section-header" style="font-size:0.95rem;margin-bottom:8px">'
                'Fachgebiet-Lücken</div>',
                unsafe_allow_html=True,
            )
            for gap in coverage_gaps:
                _render_coverage_gap_card(gap)

        if topic_gaps:
            st.markdown(
                '<div class="section-header" style="font-size:0.95rem;margin-top:16px;margin-bottom:8px">'
                'Trend-Themen ohne Freigabe</div>',
                unsafe_allow_html=True,
            )
            for tgap in topic_gaps:
                _render_topic_gap_card(tgap)


def _render_coverage_gap_card(gap):
    """Rendert eine einzelne Fachgebiet-Lücken-Karte."""
    severity_icons = {"critical": "\U0001f534", "warning": "\U0001f7e1", "info": "\U0001f535"}
    icon = severity_icons.get(gap.severity, "\U0001f535")
    rate_pct = round(gap.approval_rate * 100)

    if gap.severity == "critical":
        bar_color = "#f87171"
    elif gap.severity == "warning":
        bar_color = "#fbbf24"
    else:
        bar_color = "#60a5fa"

    spec_html = spec_pill(gap.specialty)

    articles_html = ""
    if gap.top_unreviewed:
        items = []
        for art in gap.top_unreviewed[:3]:
            title = _esc(art["title"])
            score = art["score"]
            journal = _esc(art["journal"])
            items.append(
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'padding:4px 0;font-size:0.78rem">'
                f'{score_pill(score)}'
                f'<span style="color:var(--c-text);flex:1;overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap">{title}</span>'
                f'<span style="color:var(--c-text-tertiary);font-size:0.72rem;'
                f'white-space:nowrap">{journal}</span>'
                f'</div>'
            )
        articles_html = (
            '<div style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);'
            'padding-top:6px">'
            + "".join(items)
            + '</div>'
        )

    st.markdown(
        f'<div class="med-card" style="padding:12px 16px;margin-bottom:8px">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
        f'<span style="font-size:1rem">{icon}</span>'
        f'{spec_html}'
        f'<span style="font-size:0.8rem;color:var(--c-text-muted)">'
        f'{gap.total_articles} Artikel, {gap.high_quality_count} HQ, '
        f'{gap.approved_count} freigegeben</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
        f'<span style="font-size:0.72rem;color:var(--c-text-tertiary);width:70px">'
        f'Freigabe:</span>'
        f'<div class="progress-track" style="flex:1;height:6px">'
        f'<div style="width:{min(rate_pct, 100)}%;height:100%;'
        f'background:{bar_color};border-radius:3px;transition:width 0.6s"></div>'
        f'</div>'
        f'<span style="font-size:0.75rem;color:{bar_color};font-weight:600;'
        f'min-width:36px;text-align:right">{rate_pct}%</span>'
        f'</div>'
        f'<div style="font-size:0.78rem;color:var(--c-text-muted);line-height:1.4">'
        f'{_esc(gap.suggestion_de)}</div>'
        f'{articles_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_topic_gap_card(tgap):
    """Rendert eine einzelne Topic-Lücken-Karte."""
    mbadge = momentum_badge(tgap.momentum, 0.0)
    spec_pills_html = " ".join(spec_pill(s) for s in tgap.specialties) if tgap.specialties else ""
    days_text = (
        f'{tgap.days_unreviewed}d unbearbeitet'
        if tgap.days_unreviewed > 0 else "Neu"
    )

    st.markdown(
        f'<div class="med-card" style="padding:12px 16px;margin-bottom:8px">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap">'
        f'{mbadge}'
        f'<span style="font-size:0.88rem;font-weight:600;color:var(--c-text)">'
        f'{_esc(tgap.topic)}</span>'
        f'<span style="font-size:0.75rem;color:var(--c-text-tertiary)">'
        f'{tgap.article_count} Artikel &middot; \u00d8 {tgap.avg_score:.0f}</span>'
        f'<span style="font-size:0.72rem;color:var(--c-text-muted);'
        f'margin-left:auto">{days_text}</span>'
        f'</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">'
        f'{spec_pills_html}</div>'
        f'<div style="font-size:0.78rem;color:var(--c-text-muted);line-height:1.4">'
        f'{_esc(tgap.suggestion_de)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Konkurrenz-Radar
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _load_konkurrenz_report() -> dict | None:
    """Lade den Konkurrenz-Report (gecacht für 30 Minuten)."""
    try:
        report = generate_konkurrenz_report(days=7)
        return {
            "period_days": report.period_days,
            "competitor_stats": [
                {
                    "source_name": cs.source_name,
                    "article_count": cs.article_count,
                    "top_specialties": cs.top_specialties,
                    "top_topics": cs.top_topics,
                    "exclusive_topics": cs.exclusive_topics,
                    "avg_score": cs.avg_score,
                }
                for cs in report.competitor_stats
            ],
            "topic_overlaps": [
                {
                    "topic": o.topic,
                    "our_coverage": o.our_coverage,
                    "competitor_coverage": o.competitor_coverage,
                    "total_competitor_articles": o.total_competitor_articles,
                    "we_covered_first": o.we_covered_first,
                    "gap_days": o.gap_days,
                    "status": o.status,
                }
                for o in report.topic_overlaps
            ],
            "our_exclusives": report.our_exclusives,
            "their_exclusives": report.their_exclusives,
            "speed_analysis": report.speed_analysis,
            "summary_de": report.summary_de,
            "generated_at": report.generated_at.isoformat(),
        }
    except Exception as e:
        logger.error("Konkurrenz-Radar Fehler: %s", e)
        return None


def _render_konkurrenz_radar():
    """Rendert den Konkurrenz-Radar — Wettbewerbsanalyse."""
    with st.expander("\U0001f4e1 Konkurrenz-Radar — Wettbewerbsanalyse", expanded=False):
        report = _load_konkurrenz_report()

        if report is None:
            st.markdown(
                '<div class="med-card" style="text-align:center;padding:20px">'
                '<div style="font-size:1rem;color:var(--c-text-muted)">'
                'Konkurrenz-Radar konnte nicht geladen werden.</div></div>',
                unsafe_allow_html=True,
            )
            return

        comp_stats = report["competitor_stats"]
        overlaps = report["topic_overlaps"]
        our_excl = report["our_exclusives"]
        their_excl = report["their_exclusives"]
        speed = report["speed_analysis"]
        summary = report["summary_de"]

        if not comp_stats and not overlaps:
            st.markdown(
                '<div class="med-card" style="text-align:center;padding:20px">'
                '<div style="font-size:1rem;margin-bottom:6px">'
                'Keine Konkurrenz-Daten im Zeitraum</div>'
                '<div style="font-size:0.8rem;color:var(--c-text-tertiary)">'
                'Es wurden keine Artikel von Konkurrenzquellen gefunden.</div></div>',
                unsafe_allow_html=True,
            )
            return

        # --- Executive Summary ---
        st.markdown(
            f'<div class="med-card" style="padding:14px 18px;margin-bottom:16px;'
            f'border-left:3px solid {APPLE_BLUE}">'
            f'<div style="font-size:0.78rem;color:var(--c-text-tertiary);'
            f'margin-bottom:6px;text-transform:uppercase;letter-spacing:0.05em">'
            f'Zusammenfassung</div>'
            f'<div style="font-size:0.88rem;color:var(--c-text);line-height:1.5">'
            f'{_esc(summary)}</div></div>',
            unsafe_allow_html=True,
        )

        _render_competitor_cards(comp_stats)
        _render_topic_overlap_matrix(overlaps, our_excl, their_excl)
        _render_speed_analysis(speed)
        _render_recommendations(their_excl)


def _render_competitor_cards(comp_stats: list[dict]):
    """Render competitor overview cards."""
    if not comp_stats:
        return

    st.markdown(
        '<div class="section-header" style="font-size:0.95rem;margin-bottom:10px">'
        'Konkurrenz-Übersicht</div>',
        unsafe_allow_html=True,
    )

    n_cols = min(len(comp_stats), 3)
    cols = st.columns(n_cols)

    for i, cs in enumerate(comp_stats):
        with cols[i % n_cols]:
            spec_pills = " ".join(
                spec_pill(s) for s, _ in cs["top_specialties"][:3]
            ) if cs["top_specialties"] else ""

            topics_html = ", ".join(
                f'<span style="color:var(--c-text);font-weight:500">{_esc(t)}</span>'
                f'<span style="color:var(--c-text-tertiary)">({c})</span>'
                for t, c in cs["top_topics"][:5]
            )

            score_html = score_pill(cs["avg_score"]) if cs["avg_score"] > 0 else ""

            st.markdown(
                f'<div class="med-card" style="padding:14px 16px;margin-bottom:10px">'
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
                f'<span style="font-size:0.92rem;font-weight:600;color:var(--c-text)">'
                f'{_esc(cs["source_name"])}</span>'
                f'{score_html}'
                f'</div>'
                f'<div style="font-size:0.82rem;color:var(--c-text-muted);margin-bottom:6px">'
                f'{cs["article_count"]} Artikel</div>'
                f'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">'
                f'{spec_pills}</div>'
                f'<div style="font-size:0.75rem;line-height:1.6">'
                f'{topics_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_topic_overlap_matrix(overlaps: list[dict], our_excl: list[str], their_excl: list[dict]):
    """Render the topic overlap visualization."""
    if not overlaps:
        return

    st.markdown(
        '<div class="section-header" style="font-size:0.95rem;margin-top:16px;margin-bottom:10px">'
        'Themen-Overlap</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="display:flex;gap:16px;margin-bottom:12px;font-size:0.78rem">'
        '<span>\U0001f7e2 Nur wir</span>'
        '<span>\U0001f534 Nur Konkurrenz</span>'
        '<span>\U0001f7e1 Overlap</span>'
        '<span>\u26a0\ufe0f Wir waren langsamer</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    rows_html = []
    for o in overlaps[:20]:
        topic = _esc(o["topic"])
        status = o["status"]

        if status == "exclusive_ours":
            icon, label, label_color = "\U0001f7e2", "Nur wir", "#4ade80"
        elif status == "exclusive_theirs":
            icon, label, label_color = "\U0001f534", "Nur Konkurrenz", "#f87171"
        elif status == "gap":
            icon, label, label_color = "\u26a0\ufe0f", f"+{o['gap_days']}d langsamer", "#fbbf24"
        else:
            icon = "\U0001f7e1"
            if o["we_covered_first"]:
                label, label_color = "Wir zuerst", "#4ade80"
            else:
                label, label_color = "Gleichzeitig", "#60a5fa"

        sources_text = ""
        if o["competitor_coverage"]:
            src_parts = [f'{_esc(s)}({c})' for s, c in o["competitor_coverage"].items()]
            sources_text = " ".join(src_parts)

        our_count_text = f'Wir: {o["our_coverage"]}' if o["our_coverage"] > 0 else ""

        rows_html.append(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06)">'
            f'<span style="font-size:0.9rem;width:24px">{icon}</span>'
            f'<span style="font-size:0.85rem;font-weight:600;color:var(--c-text);'
            f'min-width:120px">{topic}</span>'
            f'<span style="font-size:0.75rem;color:{label_color};font-weight:500;'
            f'min-width:100px">{label}</span>'
            f'<span style="font-size:0.72rem;color:var(--c-text-tertiary);flex:1">'
            f'{our_count_text}'
            f'{" | " if our_count_text and sources_text else ""}'
            f'{sources_text}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div class="med-card" style="padding:12px 16px">{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )


def _render_speed_analysis(speed: dict):
    """Render speed-to-coverage stats."""
    total = speed.get("total_overlap_topics", 0)
    if total == 0:
        return

    st.markdown(
        '<div class="section-header" style="font-size:0.95rem;margin-top:16px;margin-bottom:10px">'
        'Speed-to-Coverage</div>',
        unsafe_allow_html=True,
    )

    first = speed["times_first"]
    behind = speed["times_behind"]
    avg_gap = speed["avg_gap_days"]

    if first > behind:
        perf_color, perf_icon = "#4ade80", "\u2705"
        perf_text = "Wir sind meistens schneller!"
    elif behind > first:
        perf_color, perf_icon = "#fbbf24", "\u26a0\ufe0f"
        perf_text = f"Konkurrenz oft schneller (\u00d8 {avg_gap} Tage Vorsprung)"
    else:
        perf_color, perf_icon = "#60a5fa", "\u2696\ufe0f"
        perf_text = "Ausgeglichen"

    st.markdown(
        f'<div class="med-card" style="padding:14px 18px;margin-bottom:10px">'
        f'<div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap">'
        f'<div style="text-align:center">'
        f'<div style="font-size:1.8rem;font-weight:700;color:#4ade80">{first}</div>'
        f'<div style="font-size:0.75rem;color:var(--c-text-tertiary)">x schneller</div>'
        f'</div>'
        f'<div style="text-align:center">'
        f'<div style="font-size:1.8rem;font-weight:700;color:#f87171">{behind}</div>'
        f'<div style="font-size:0.75rem;color:var(--c-text-tertiary)">x langsamer</div>'
        f'</div>'
        f'<div style="text-align:center">'
        f'<div style="font-size:1.8rem;font-weight:700;color:var(--c-text)">{avg_gap}</div>'
        f'<div style="font-size:0.75rem;color:var(--c-text-tertiary)">\u00d8 Tage Abstand</div>'
        f'</div>'
        f'<div style="margin-left:auto;font-size:0.88rem;color:{perf_color}">'
        f'{perf_icon} {perf_text}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_recommendations(their_excl: list[dict]):
    """Render editorial recommendations based on competitor exclusives."""
    if not their_excl:
        return

    st.markdown(
        '<div class="section-header" style="font-size:0.95rem;margin-top:16px;margin-bottom:10px">'
        'Handlungsempfehlungen</div>',
        unsafe_allow_html=True,
    )

    top_missing = sorted(their_excl, key=lambda x: x["article_count"], reverse=True)[:5]

    rows_html = []
    for i, item in enumerate(top_missing, 1):
        topic = _esc(item["topic"])
        sources = ", ".join(_esc(s) for s in item["sources"])
        count = item["article_count"]

        rows_html.append(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.06)">'
            f'<span style="font-size:0.85rem;font-weight:700;color:#f87171;width:20px">'
            f'{i}.</span>'
            f'<div style="flex:1">'
            f'<div style="font-size:0.88rem;font-weight:600;color:var(--c-text)">'
            f'{topic}</div>'
            f'<div style="font-size:0.75rem;color:var(--c-text-tertiary)">'
            f'{count} Artikel bei: {sources}</div>'
            f'</div>'
            f'<span style="font-size:0.72rem;color:#f87171;font-weight:500;'
            f'white-space:nowrap">Thema aufgreifen</span>'
            f'</div>'
        )

    st.markdown(
        f'<div class="med-card" style="padding:12px 16px">'
        f'<div style="font-size:0.8rem;color:var(--c-text-muted);margin-bottom:8px">'
        f'Diese Themen deckt nur die Konkurrenz ab \u2014 mögliche redaktionelle Lücken:</div>'
        f'{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )

"""Lumio -- Search tab: full-text article search + Artikel-Werkbank."""

import json
import streamlit as st

from components.helpers import (
    _esc, get_articles, score_pill, spec_pill,
    _render_score_breakdown, SPECIALTY_COLORS,
)
from src.config import SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MID


def render_search(filters: dict):
    """Render the Search tab content."""
    st.markdown('<div class="page-header">Suche</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Volltextsuche &uuml;ber alle Artikelfelder '
        '&mdash; mit Recherche-Werkbank</div>',
        unsafe_allow_html=True,
    )

    search_input = st.text_input(
        "Suche",
        key="fulltext_search",
        placeholder="z.B. GLP-1, SGLT2, Immuntherapie, Leitlinie...",
        label_visibility="collapsed",
    )

    if search_input:
        results = get_articles(
            search_query=search_input,
            specialties=tuple(filters["selected_specialties"]) if filters["selected_specialties"] else None,
            sources=tuple(filters["selected_sources"]) if filters["selected_sources"] else None,
            min_score=0,
            date_from=filters["date_from"], date_to=filters["date_to"],
            status_filter=filters["status_filter"],
            language=filters["language_filter"],
            study_types=tuple(filters["selected_study_types"]) if filters["selected_study_types"] else None,
            open_access_only=filters["open_access_only"],
        )
        st.markdown(
            f'<div style="font-size:0.8rem;color:var(--c-text-tertiary);font-weight:500;'
            f'margin-bottom:16px">{len(results)} Treffer</div>',
            unsafe_allow_html=True,
        )

        if results:
            tab_liste, tab_werkbank = st.tabs(["Liste", "Werkbank"])

            with tab_liste:
                _render_flat_list(results)

            with tab_werkbank:
                _render_werkbank(search_input, results)
        else:
            st.info("Keine Treffer gefunden.")
    else:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">\U0001f50d</div>
                <div class="empty-state-text">Suchbegriff eingeben</div>
                <div style="font-size:0.8rem;color:var(--c-text-muted);margin-top:4px">
                    Durchsucht Titel, Abstracts, Zusammenfassungen, Tags, Autoren, Journals und MeSH-Begriffe
                </div>
            </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 1: Flat list (original view, unchanged)
# ---------------------------------------------------------------------------

def _render_flat_list(results):
    """Render the original flat search results list."""
    for idx, a in enumerate(results):
        meta_parts = []
        if a.journal:
            meta_parts.append(_esc(a.journal))
        if a.pub_date:
            meta_parts.append(a.pub_date.strftime("%d.%m.%Y"))
        meta = " &middot; ".join(meta_parts)

        safe_t = _esc(a.title)
        safe_u = _esc(a.url) if a.url else ""
        title_el = (
            f'<a href="{safe_u}" target="_blank" class="a-title">{safe_t}</a>'
            if safe_u else f'<span class="a-title">{safe_t}</span>'
        )

        summary_snip = ""
        if a.summary_de:
            snip = _esc(a.summary_de[:180])
            if len(a.summary_de) > 180:
                snip += "..."
            summary_snip = (
                f'<div style="font-size:0.78rem;color:var(--c-text-muted);'
                f'margin-top:4px">{snip}</div>'
            )

        spec_html = spec_pill(a.specialty) if a.specialty else ""

        st.markdown(
            f'<div class="a-card" style="margin-bottom:8px;padding:12px 16px">'
            f'<div style="display:flex;align-items:flex-start;gap:12px">'
            f'<div style="flex-shrink:0;padding-top:2px">{score_pill(a.relevance_score)}</div>'
            f'<div style="flex:1;min-width:0">{title_el}'
            f'<div class="a-meta">{meta}'
            f'{" " + spec_html if spec_html else ""}'
            f'</div>{summary_snip}</div></div></div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Tab 2: Werkbank (structured research dossier)
# ---------------------------------------------------------------------------

# Tier colors and icons for the evidence pyramid
_TIER_STYLES = {
    1: {"color": "#4ade80", "bg": "rgba(74,222,128,0.08)", "icon": "\u2B50", "width": 0.4},
    2: {"color": "#60a5fa", "bg": "rgba(96,165,250,0.08)", "icon": "\U0001F9EA", "width": 0.5},
    3: {"color": "#a78bfa", "bg": "rgba(167,139,250,0.08)", "icon": "\U0001F4CB", "width": 0.6},
    4: {"color": "#fbbf24", "bg": "rgba(251,191,36,0.08)", "icon": "\U0001F4CA", "width": 0.7},
    5: {"color": "#fb923c", "bg": "rgba(251,146,60,0.08)", "icon": "\U0001F4DD", "width": 0.85},
    6: {"color": "#8b8ba0", "bg": "rgba(139,139,160,0.08)", "icon": "\U0001F4F0", "width": 1.0},
}


def _render_werkbank(query: str, results: list):
    """Render the Artikel-Werkbank structured research view."""
    from src.processing.werkbank import build_dossier

    dossier = build_dossier(query, articles=results)

    # --- Layout: main content + sidebar-like stats ---
    col_main, col_stats = st.columns([3, 1])

    # --- Right column: Recherche-Statistik ---
    with col_stats:
        _render_recherche_statistik(dossier)
        st.markdown("---")
        _render_watchlist_schnellstart(dossier)

    # --- Left column: Evidenz-Pyramide ---
    with col_main:
        st.markdown(
            '<div style="font-size:1rem;font-weight:600;margin-bottom:12px">'
            'Evidenz-Pyramide</div>',
            unsafe_allow_html=True,
        )
        _render_evidence_pyramid(dossier)


def _render_evidence_pyramid(dossier):
    """Render the visual evidence pyramid with expandable article lists."""
    for tier in dossier.evidence_pyramid:
        if tier.count == 0:
            continue

        style = _TIER_STYLES.get(tier.level, _TIER_STYLES[6])
        width_pct = int(style["width"] * 100)

        # Pyramid row: centered block with decreasing width
        count_badge = (
            f'<span style="display:inline-block;background:{style["color"]}20;'
            f'color:{style["color"]};font-size:0.72rem;font-weight:600;'
            f'padding:2px 8px;border-radius:10px;margin-left:8px">'
            f'{tier.count}</span>'
        )

        st.markdown(
            f'<div style="max-width:{width_pct}%;margin:0 auto 4px auto;'
            f'background:{style["bg"]};border:1px solid {style["color"]}20;'
            f'border-radius:8px;padding:8px 14px;text-align:center">'
            f'<span style="font-size:0.82rem;font-weight:600;color:{style["color"]}">'
            f'{style["icon"]} Tier {tier.level}: {_esc(tier.name)}'
            f'</span>{count_badge}</div>',
            unsafe_allow_html=True,
        )

        # Expandable article list within this tier
        with st.expander(
            f"{tier.name} -- {tier.count} Artikel",
            expanded=(tier.level <= 2),
        ):
            for art in tier.articles:
                _render_werkbank_article(art)


def _render_werkbank_article(art: dict):
    """Render a single article within the Werkbank pyramid tier."""
    score = art.get("relevance_score", 0)
    title = art.get("title", "")
    journal = art.get("journal", "")
    pub_date = art.get("pub_date")
    specialty = art.get("specialty", "")
    url = art.get("url", "")
    summary = art.get("summary_de", "")
    breakdown_json = art.get("score_breakdown", "")
    study_type = art.get("study_type", "")

    # Meta line
    meta_parts = []
    if journal:
        meta_parts.append(_esc(journal))
    if pub_date:
        try:
            meta_parts.append(pub_date.strftime("%d.%m.%Y"))
        except AttributeError:
            meta_parts.append(str(pub_date))
    if study_type and study_type != "Unbekannt":
        meta_parts.append(_esc(study_type))
    meta = " &middot; ".join(meta_parts)

    # Title
    safe_t = _esc(title)
    safe_u = _esc(url) if url else ""
    title_el = (
        f'<a href="{safe_u}" target="_blank" class="a-title">{safe_t}</a>'
        if safe_u else f'<span class="a-title">{safe_t}</span>'
    )

    # Specialty pill
    spec_html = ""
    if specialty:
        fg, bg = SPECIALTY_COLORS.get(specialty, ("#8b8ba0", "rgba(139,139,160,0.10)"))
        spec_html = (
            f' &middot; <span style="color:{fg};background:{bg};'
            f'padding:1px 6px;border-radius:6px;font-size:0.7rem">'
            f'{_esc(specialty)}</span>'
        )

    # Summary snippet
    summary_snip = ""
    if summary:
        snip = _esc(summary[:160])
        if len(summary) > 160:
            snip += "..."
        summary_snip = (
            f'<div style="font-size:0.76rem;color:var(--c-text-muted);'
            f'margin-top:3px">{snip}</div>'
        )

    # Score breakdown preview (compact inline)
    breakdown_preview = _render_score_breakdown_compact(art.get("score_details", {}))

    st.markdown(
        f'<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04)">'
        f'<div style="display:flex;align-items:flex-start;gap:10px">'
        f'<div style="flex-shrink:0;padding-top:2px">{score_pill(score)}</div>'
        f'<div style="flex:1;min-width:0">{title_el}'
        f'<div class="a-meta">{meta}{spec_html}</div>'
        f'{summary_snip}'
        f'{breakdown_preview}'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )


def _render_score_breakdown_compact(score_details: dict) -> str:
    """Render a compact inline score breakdown preview."""
    if not score_details:
        return ""

    parts = []
    colors = {
        "Journal": "#60a5fa",
        "Studiendesign": "#a78bfa",
        "Studientyp": "#a78bfa",
        "Aktualitaet": "#22d3ee",
        "Klinische Relevanz": "#60a5fa",
        "Neuigkeitswert": "#22d3ee",
        "Zielgruppen-Fit": "#fbbf24",
        "Quellenqualitaet": "#4ade80",
        "Keyword-Boost": "#fbbf24",
        "Arztrelevanz": "#4ade80",
        "Redaktions-Bonus": "#8b8ba0",
        "Praeferenz-Bonus": "#f472b6",
    }

    for label, info in score_details.items():
        score_val = info.get("score", 0)
        max_val = info.get("max", 1)
        if score_val == 0:
            continue
        color = colors.get(label, "#8b8ba0")
        pct = min(100, (score_val / max_val) * 100) if max_val > 0 else 0
        parts.append(
            f'<span style="display:inline-flex;align-items:center;gap:3px;'
            f'font-size:0.68rem;color:var(--c-text-muted);margin-right:8px">'
            f'<span style="display:inline-block;width:24px;height:4px;'
            f'border-radius:2px;background:rgba(255,255,255,0.06);position:relative;'
            f'overflow:hidden"><span style="position:absolute;left:0;top:0;height:100%;'
            f'width:{pct:.0f}%;background:{color};border-radius:2px"></span></span>'
            f'{_esc(label)}&nbsp;{score_val:.0f}</span>'
        )

    if not parts:
        return ""

    return (
        f'<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:2px">'
        f'{"".join(parts)}</div>'
    )


# ---------------------------------------------------------------------------
# Recherche-Statistik (sidebar)
# ---------------------------------------------------------------------------

def _render_recherche_statistik(dossier):
    """Render the research statistics panel."""
    st.markdown(
        '<div style="font-size:0.9rem;font-weight:600;margin-bottom:8px">'
        'Recherche-Statistik</div>',
        unsafe_allow_html=True,
    )

    # Total + score range
    stats = dossier.score_stats
    st.markdown(
        f'<div style="font-size:0.78rem;color:var(--c-text-muted);margin-bottom:12px">'
        f'<b>{dossier.total_results}</b> Artikel &middot; '
        f'Score {stats["min"]}&ndash;{stats["max"]} '
        f'(&#216; {stats["avg"]}, Median {stats["median"]})</div>',
        unsafe_allow_html=True,
    )

    # Evidence tier distribution
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:500;margin-bottom:6px">'
        'Evidenz-Verteilung</div>',
        unsafe_allow_html=True,
    )
    total = max(dossier.total_results, 1)
    for tier in dossier.evidence_pyramid:
        if tier.count == 0:
            continue
        style = _TIER_STYLES.get(tier.level, _TIER_STYLES[6])
        pct = (tier.count / total) * 100
        st.markdown(
            f'<div style="margin-bottom:4px">'
            f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;'
            f'color:var(--c-text-muted)">'
            f'<span>T{tier.level}</span><span>{tier.count}</span></div>'
            f'<div style="height:5px;border-radius:3px;background:rgba(255,255,255,0.06)">'
            f'<div style="width:{pct:.0f}%;height:100%;border-radius:3px;'
            f'background:{style["color"]}"></div></div></div>',
            unsafe_allow_html=True,
        )

    # Specialty distribution
    if dossier.specialty_breakdown:
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:500;margin:12px 0 6px">'
            'Fachgebiete</div>',
            unsafe_allow_html=True,
        )
        max_count = max(dossier.specialty_breakdown.values()) if dossier.specialty_breakdown else 1
        for spec, count in list(dossier.specialty_breakdown.items())[:8]:
            fg, bg = SPECIALTY_COLORS.get(spec, ("#8b8ba0", "rgba(139,139,160,0.10)"))
            bar_pct = (count / max_count) * 100
            st.markdown(
                f'<div style="margin-bottom:3px">'
                f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;'
                f'color:var(--c-text-muted)">'
                f'<span style="color:{fg}">{_esc(spec)}</span>'
                f'<span>{count}</span></div>'
                f'<div style="height:4px;border-radius:2px;background:rgba(255,255,255,0.06)">'
                f'<div style="width:{bar_pct:.0f}%;height:100%;border-radius:2px;'
                f'background:{fg}"></div></div></div>',
                unsafe_allow_html=True,
            )

    # Journal distribution (top 5)
    if dossier.journal_breakdown:
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:500;margin:12px 0 6px">'
            'Top-Quellen</div>',
            unsafe_allow_html=True,
        )
        for jrnl, count in list(dossier.journal_breakdown.items())[:5]:
            st.markdown(
                f'<div style="font-size:0.7rem;color:var(--c-text-muted);'
                f'display:flex;justify-content:space-between;margin-bottom:2px">'
                f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
                f'max-width:80%">{_esc(jrnl)}</span>'
                f'<span style="font-weight:500">{count}</span></div>',
                unsafe_allow_html=True,
            )

    # Time range
    tr = dossier.time_range
    if tr.get("earliest") and tr.get("latest"):
        try:
            earliest_str = tr["earliest"].strftime("%d.%m.%Y")
            latest_str = tr["latest"].strftime("%d.%m.%Y")
        except AttributeError:
            earliest_str = str(tr["earliest"])
            latest_str = str(tr["latest"])
        st.markdown(
            f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:10px">'
            f'Zeitraum: {earliest_str} &ndash; {latest_str}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Watchlist-Schnellstart
# ---------------------------------------------------------------------------

def _render_watchlist_schnellstart(dossier):
    """Render the one-click watchlist creation section."""
    st.markdown(
        '<div style="font-size:0.9rem;font-weight:600;margin-bottom:8px">'
        'Watchlist-Schnellstart</div>',
        unsafe_allow_html=True,
    )

    keywords = dossier.suggested_watchlist_keywords
    if not keywords:
        st.markdown(
            '<div style="font-size:0.75rem;color:var(--c-text-muted)">'
            'Keine Keywords vorgeschlagen.</div>',
            unsafe_allow_html=True,
        )
        return

    # Display suggested keywords as editable chips
    st.markdown(
        '<div style="font-size:0.75rem;color:var(--c-text-muted);margin-bottom:6px">'
        'Vorgeschlagene Keywords:</div>',
        unsafe_allow_html=True,
    )

    # Show keywords as styled pills
    kw_pills = " ".join(
        f'<span style="display:inline-block;background:rgba(96,165,250,0.12);'
        f'color:#60a5fa;font-size:0.72rem;padding:2px 8px;border-radius:8px;'
        f'margin:2px 2px">{_esc(kw)}</span>'
        for kw in keywords
    )
    st.markdown(
        f'<div style="margin-bottom:10px">{kw_pills}</div>',
        unsafe_allow_html=True,
    )

    # Editable watchlist name
    default_name = f"Recherche: {dossier.query}"
    wl_name = st.text_input(
        "Watchlist-Name",
        value=default_name,
        key="werkbank_wl_name",
        label_visibility="collapsed",
    )

    # Editable keywords
    kw_text = st.text_input(
        "Keywords",
        value=", ".join(keywords),
        key="werkbank_wl_keywords",
        label_visibility="collapsed",
        help="Komma-getrennte Suchbegriffe",
    )

    # Optional: specialty filter from dominant specialty
    spec_filter = None
    if dossier.specialty_breakdown:
        top_spec = next(iter(dossier.specialty_breakdown))
        spec_options = ["Alle"] + list(dossier.specialty_breakdown.keys())
        spec_choice = st.selectbox(
            "Fachgebiet-Filter",
            spec_options,
            key="werkbank_wl_spec",
            label_visibility="collapsed",
        )
        if spec_choice != "Alle":
            spec_filter = spec_choice

    # Min score slider
    min_score = st.slider(
        "Min. Score",
        min_value=0,
        max_value=100,
        value=int(dossier.score_stats.get("median", 40)),
        step=5,
        key="werkbank_wl_minscore",
        help="Nur Artikel mit mindestens diesem Score melden",
    )

    # Save button
    if st.button("Als Watchlist speichern", key="werkbank_save_wl", type="primary"):
        _save_watchlist(wl_name, kw_text, spec_filter, min_score)


def _save_watchlist(name: str, keywords_csv: str, specialty=None, min_score: float = 0.0):
    """Persist a new watchlist to the database."""
    from src.models import Watchlist, get_session

    if not name.strip() or not keywords_csv.strip():
        st.warning("Bitte Name und Keywords angeben.")
        return

    with get_session() as session:
        wl = Watchlist(
            name=name.strip(),
            keywords=keywords_csv.strip(),
            specialty_filter=specialty,
            min_score=min_score,
            notify_email=False,
            active=True,
        )
        session.add(wl)
        session.commit()

    st.success(f"Watchlist \"{name}\" gespeichert.")

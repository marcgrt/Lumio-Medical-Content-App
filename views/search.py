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
        '&mdash; mit Recherche-Analyse</div>',
        unsafe_allow_html=True,
    )

    # --- Feature 6: Recent & Saved Searches ---
    _render_recent_searches()

    # --- Feature 1: Popular topics (Smart-Suggest alternative) ---
    if "fulltext_search" not in st.session_state or not st.session_state.get("fulltext_search"):
        _render_popular_topics()

    # Deep-Link from Kongress tab or recent search click
    _prefill = st.session_state.pop("prefill_search", "") or st.session_state.pop("_search_query", "")
    # If there's a prefill, inject it into the key's session state slot
    if _prefill:
        st.session_state["fulltext_search"] = _prefill

    _srch_col, _help_col = st.columns([20, 1])
    with _srch_col:
        search_input = st.text_input(
            "Suche",
            key="fulltext_search",
            placeholder="z.B. GLP-1, SGLT2, Immuntherapie, Leitlinie...",
            label_visibility="collapsed",
        )
    with _help_col:
        with st.popover("ℹ️", use_container_width=True):
            st.markdown("""**Suchtipps**

• **Einzelbegriff:** `SGLT2` — findet alle Artikel mit diesem Begriff
• **Mehrere Begriffe:** `SGLT2 Herzinsuffizienz` — findet Artikel mit beiden Begriffen
• **Phrasen:** `"heart failure"` — exakte Wortfolge
• **Fachgebiet:** `Kardiologie` — durchsucht auch Fachgebiet-Tags
• **Quelle:** `JAMA` oder `Lancet` — findet Artikel aus dieser Quelle
• **Autor:** `Müller` — durchsucht Autorenliste

*Die Suche durchsucht Titel, Abstracts, Zusammenfassungen, Tags, Autoren, Quellen und MeSH-Begriffe gleichzeitig.*
""")

    if search_input:
        from components.auth import track_activity
        track_activity("search", search_input[:100])
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

        # --- Show query expansion info ---
        from components.helpers import expand_search_query
        _, _expansion_terms = expand_search_query(search_input)
        if _expansion_terms:
            _exp_display = ", ".join(_expansion_terms)
            st.markdown(
                f'<div style="font-size:0.72rem;color:var(--c-text-muted);'
                f'margin-bottom:8px;padding:4px 8px;'
                f'background:var(--c-surface);border-radius:6px;display:inline-block">'
                f'🔍 Suche erweitert: <b>{search_input}</b> → + {_exp_display}</div>',
                unsafe_allow_html=True,
            )

        # --- Feature 4: Trend Sparkline ---
        _render_trend_sparkline(search_input)

        # --- Feature 5: Related Searches ---
        _render_related_searches(search_input, results)

        st.markdown(
            f'<div style="font-size:0.8rem;color:var(--c-text-tertiary);font-weight:500;'
            f'margin-bottom:16px">{len(results)} Treffer</div>',
            unsafe_allow_html=True,
        )

        if results:
            tab_liste, tab_analyse, tab_vergleich = st.tabs(
                ["Liste", "Deep Dive", "Vergleich"]
            )

            with tab_liste:
                _render_flat_list(results, enable_collection=True)
                # Show collection action bar if articles are selected
                _sel_ids = st.session_state.get("_search_selected_ids", set())
                if _sel_ids:
                    st.markdown("---")
                    import sqlite3 as _s3
                    from src.config import DB_PATH as _dp
                    _uid = st.session_state.get("current_user_id", 0)

                    _ac1, _ac2 = st.columns([1, 2])
                    with _ac1:
                        st.markdown(
                            f'<span style="font-size:0.75rem;font-weight:600">'
                            f'{len(_sel_ids)} Artikel ausgewählt</span>',
                            unsafe_allow_html=True,
                        )
                    with _ac2:
                        _cc = _s3.connect(str(_dp))
                        try:
                            _my_colls = _cc.execute(
                                "SELECT id, name FROM collection WHERE user_id = ? "
                                "AND status NOT IN ('published','veroeffentlicht') "
                                "ORDER BY updated_at DESC", (_uid,)
                            ).fetchall()
                        finally:
                            _cc.close()
                        _coll_opts = [("0", "+ Neue Sammlung")] + [(str(c[0]), c[1]) for c in _my_colls]
                        _chosen = st.selectbox(
                            "Sammlung", _coll_opts,
                            format_func=lambda x: x[1],
                            key="_search_coll_target",
                            label_visibility="collapsed",
                        )

                    # Name field for new collections
                    _new_coll_name = ""
                    if _chosen[0] == "0":
                        _new_coll_name = st.text_input(
                            "Name der neuen Sammlung",
                            value=f"Recherche: {search_input[:40]}",
                            key="_search_new_coll_name",
                        )

                    if st.button("📁 Zur Sammlung hinzufügen", key="_search_add_to_coll",
                                 use_container_width=True):
                        _cc2 = _s3.connect(str(_dp))
                        _cc2.execute("BEGIN IMMEDIATE")
                        try:
                            if _chosen[0] == "0":
                                _coll_name = _new_coll_name.strip() or f"Recherche: {search_input[:40]}"
                                _cc2.execute(
                                    "INSERT INTO collection (user_id, name, status, created_at, updated_at) "
                                    "VALUES (?, ?, 'recherche', datetime('now'), datetime('now'))",
                                    (_uid, _coll_name),
                                )
                                _new_cid = _cc2.execute("SELECT last_insert_rowid()").fetchone()[0]
                                if not _new_cid or _new_cid == 0:
                                    _cc2.rollback()
                                    _cc2.close()
                                    st.error("Sammlung konnte nicht erstellt werden.")
                                    return
                            else:
                                _new_cid = int(_chosen[0])
                            for _aid in _sel_ids:
                                _cc2.execute(
                                    "INSERT OR IGNORE INTO collectionarticle "
                                    "(collection_id, article_id, added_at) VALUES (?, ?, datetime('now'))",
                                    (_new_cid, _aid),
                                )
                            _cc2.commit()
                        except Exception:
                            _cc2.rollback()
                            raise
                        finally:
                            _cc2.close()
                        from components.auth import track_activity
                        track_activity("search_to_collection",
                                       f"coll={_new_cid},articles={len(_sel_ids)}")
                        st.session_state["_search_selected_ids"] = set()
                        st.success(f"{len(_sel_ids)} Artikel zur Sammlung hinzugefügt!")
                        st.rerun()

            with tab_analyse:
                _render_werkbank(search_input, results)

            with tab_vergleich:
                _render_comparison(results)
        else:
            st.info("Keine Treffer gefunden. Versuche einen allgemeineren Begriff oder prüfe die Schreibweise.")
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

def _render_flat_list(results, enable_collection: bool = False):
    """Render the flat search results list with optional collection checkboxes."""
    # Feature 2: Collection support
    if enable_collection:
        selected_key = "_search_selected_ids"
        if selected_key not in st.session_state:
            st.session_state[selected_key] = set()

        # Scroll anchor — after checkbox toggle Streamlit reruns and jumps to
        # bottom (Insights). This JS keeps the viewport at the search results.
        _did_toggle = st.session_state.pop("_search_checkbox_toggled", False)
        if _did_toggle:
            st.components.v1.html("""<script>
                window.parent.document.getElementById('search-results-anchor')
                    ?.scrollIntoView({behavior:'instant', block:'start'});
            </script>""", height=0)

    # Invisible anchor right before the results list
    st.markdown('<div id="search-results-anchor"></div>', unsafe_allow_html=True)

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

        # Card with optional checkbox
        if enable_collection:
            c1, c2 = st.columns([0.05, 0.95])
            with c1:
                _prev = a.id in st.session_state.get(selected_key, set())
                checked = st.checkbox(
                    "sel", key=f"search_sel_{a.id}",
                    value=_prev,
                    label_visibility="collapsed",
                )
                if checked != _prev:
                    st.session_state["_search_checkbox_toggled"] = True
                if checked:
                    st.session_state.setdefault(selected_key, set()).add(a.id)
                else:
                    st.session_state.get(selected_key, set()).discard(a.id)
            with c2:
                st.markdown(
                    f'<div class="a-card" style="margin-bottom:8px;padding:12px 16px">'
                    f'<div style="display:flex;align-items:flex-start;gap:12px">'
                    f'<div style="flex-shrink:0;padding-top:2px">{score_pill(a.relevance_score, show_tip=False)}</div>'
                    f'<div style="flex:1;min-width:0">{title_el}'
                    f'<div class="a-meta">{meta}'
                    f'{" " + spec_html if spec_html else ""}'
                    f'</div>{summary_snip}</div></div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div class="a-card" style="margin-bottom:8px;padding:12px 16px">'
                f'<div style="display:flex;align-items:flex-start;gap:12px">'
                f'<div style="flex-shrink:0;padding-top:2px">{score_pill(a.relevance_score, show_tip=False)}</div>'
                f'<div style="flex:1;min-width:0">{title_el}'
                f'<div class="a-meta">{meta}'
                f'{" " + spec_html if spec_html else ""}'
                f'</div>{summary_snip}</div></div></div>',
                unsafe_allow_html=True,
            )

    # Feature 2: Collection bar is rendered inline after _render_flat_list in render_search()


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
            'Inhalts-Pyramide</div>',
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
            f'<span style="font-size:0.82rem;font-weight:600;color:{style["color"]}"'
            f' title="Klassifiziert anhand von Schlüsselwörtern in Titel, Abstract und Artikeltyp">'
            f'{style["icon"]} {_esc(tier.name)}'
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
        f'<div style="padding:8px 0;border-bottom:1px solid var(--c-border-subtle)">'
        f'<div style="display:flex;align-items:flex-start;gap:10px">'
        f'<div style="flex-shrink:0;padding-top:2px">{score_pill(score, show_tip=False)}</div>'
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
        "Quelle": "#60a5fa",
        "Studiendesign": "#a78bfa",
        "Studientyp": "#a78bfa",
        "Artikeltyp": "#a78bfa",
        "Aktualitaet": "#22d3ee",
        "Klinische Relevanz": "#60a5fa",
        "Neuigkeitswert": "#22d3ee",
        "Zielgruppen-Fit": "#fbbf24",
        "Quellenqualität": "#4ade80",
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
            f'border-radius:2px;background:var(--c-border);position:relative;'
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

    # Evidence tier distribution with legend
    _tier_legend = {
        1: "Meta-Analysen & Syst. Reviews",
        2: "Klinische Studien (RCT)",
        3: "Leitlinien & Empfehlungen",
        4: "Beobachtungsstudien & Register",
        5: "Übersichtsartikel & Expertenmeinungen",
        6: "Nachrichten & Sonstiges",
    }
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
        tier_label = _tier_legend.get(tier.level, f"T{tier.level}")
        st.markdown(
            f'<div style="margin-bottom:4px">'
            f'<div style="display:flex;justify-content:space-between;font-size:0.7rem;'
            f'color:var(--c-text-muted)">'
            f'<span title="{_esc(tier.name)}">{_esc(tier_label)}</span>'
            f'<span>{tier.count}</span></div>'
            f'<div style="height:5px;border-radius:3px;background:var(--c-border)">'
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
                f'<div style="height:4px;border-radius:2px;background:var(--c-border)">'
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


# ===========================================================================
# Feature 1: Popular Topics (Smart-Suggest)
# ===========================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def _get_popular_topics() -> list[str]:
    """Get popular search topics from article specialties and frequent terms."""
    import sqlite3
    from src.config import DB_PATH

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # Top specialties
        specs = conn.execute(
            "SELECT specialty, COUNT(*) as cnt FROM article "
            "WHERE specialty IS NOT NULL AND specialty != '' "
            "AND pub_date >= date('now', '-30 days') "
            "GROUP BY specialty ORDER BY cnt DESC LIMIT 6"
        ).fetchall()

        # Top journals
        journals = conn.execute(
            "SELECT journal, COUNT(*) as cnt FROM article "
            "WHERE journal IS NOT NULL AND journal != '' "
            "AND pub_date >= date('now', '-30 days') "
            "GROUP BY journal ORDER BY cnt DESC LIMIT 3"
        ).fetchall()

        # Popular user searches
        searches = conn.execute(
            "SELECT detail, COUNT(*) as cnt FROM useractivity "
            "WHERE action = 'search' AND detail IS NOT NULL "
            "GROUP BY detail ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()

    topics = []
    for s in searches:
        if s[0] and len(s[0].strip()) > 2:
            topics.append(s[0].strip())
    for s in specs:
        if s[0] not in topics:
            topics.append(s[0])
    for j in journals:
        if j[0] not in topics:
            topics.append(j[0])
    return topics[:10]


def _render_popular_topics():
    """Show popular topics as compact clickable pills."""
    topics = _get_popular_topics()
    if not topics:
        return

    # Render as compact pill-row using st.pills (Streamlit 1.41+) or fallback
    try:
        chosen = st.pills(
            "Beliebte Themen",
            topics[:10],
            key="popular_pills",
            label_visibility="visible",
        )
        if chosen:
            st.session_state["_search_query"] = chosen
            # Reset pill selection to prevent infinite rerun loop
            del st.session_state["popular_pills"]
            st.rerun()
    except (AttributeError, TypeError):
        # Fallback: columns with buttons
        _pc = st.columns([1.5] + [1] * min(len(topics), 10))
        with _pc[0]:
            st.markdown(
                '<span style="font-size:0.65rem;color:var(--c-text-muted);line-height:2.5">'
                'Beliebte Themen:</span>',
                unsafe_allow_html=True,
            )
        for i, t in enumerate(topics[:10]):
            with _pc[i + 1]:
                if st.button(t[:15], key=f"popular_topic_{i}"):
                    st.session_state["_search_query"] = t
                    st.rerun()


# ===========================================================================
# Feature 2: Add to Collection from Search
# ===========================================================================

def _render_search_collection_bar(selected_ids: set):
    """Show action bar when articles are selected in search results."""
    import sqlite3
    from src.config import DB_PATH

    user_id = st.session_state.get("current_user_id", 0)
    count = len(selected_ids)

    st.markdown(
        f'<div style="padding:10px 16px;background:var(--c-surface);'
        f'border:1px solid var(--c-border);border-radius:10px;margin:12px 0;'
        f'display:flex;align-items:center;gap:12px">'
        f'<span style="font-weight:700;font-size:0.85rem">{count} Artikel ausgewählt</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Get existing collections
    conn = sqlite3.connect(str(DB_PATH))
    try:
        colls = conn.execute(
            "SELECT id, name FROM collection WHERE user_id = ? AND status != 'published' "
            "ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    coll_options = {"0": "+ Neue Sammlung"}
    for cid, cname in colls:
        coll_options[str(cid)] = cname

    c1, c2 = st.columns([3, 1])
    with c1:
        choice = st.selectbox(
            "Sammlung",
            options=list(coll_options.keys()),
            format_func=lambda x: coll_options[x],
            key="search_coll_choice",
            label_visibility="collapsed",
        )
    with c2:
        if st.button("📁 Hinzufügen", key="search_add_to_coll", use_container_width=True):
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("BEGIN IMMEDIATE")
            try:
                if choice == "0":
                    # Create new collection
                    conn.execute(
                        "INSERT INTO collection (user_id, name, status, created_at, updated_at) "
                        "VALUES (?, ?, 'research', datetime('now'), datetime('now'))",
                        (user_id, f"Suche ({len(selected_ids)} Artikel)"),
                    )
                    coll_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    if not coll_id or coll_id == 0:
                        conn.rollback()
                        conn.close()
                        st.error("Sammlung konnte nicht erstellt werden.")
                        return
                else:
                    coll_id = int(choice)

                for aid in selected_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO collectionarticle (collection_id, article_id, added_at) "
                        "VALUES (?, ?, datetime('now'))",
                        (coll_id, aid),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            st.session_state["_search_selected_ids"] = set()
            from components.auth import track_activity
            track_activity("search_add_to_collection", f"coll={coll_id},count={count}")
            st.success(f"{count} Artikel zur Sammlung hinzugefügt!")
            st.rerun()


# ===========================================================================
# Feature 6: Recent & Saved Searches
# ===========================================================================

def _render_recent_searches():
    """Show recent search terms as clickable chips."""
    import sqlite3
    from src.config import DB_PATH

    user_id = st.session_state.get("current_user_id", 0)
    if not user_id:
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT DISTINCT detail FROM useractivity "
            "WHERE user_id = ? AND action = 'search' AND detail IS NOT NULL "
            "ORDER BY timestamp DESC LIMIT 8",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return

    terms = [r[0] for r in rows if r[0] and len(r[0].strip()) > 1]
    if not terms:
        return

    try:
        chosen = st.pills(
            "Letzte Suchen",
            terms[:8],
            key="recent_pills",
            label_visibility="visible",
        )
        if chosen:
            st.session_state["_search_query"] = chosen
            # Reset pill selection to prevent infinite rerun loop
            del st.session_state["recent_pills"]
            st.rerun()
    except (AttributeError, TypeError):
        _cols = st.columns([1.5] + [1] * min(len(terms), 8))
        with _cols[0]:
            st.markdown(
                '<span style="font-size:0.65rem;color:var(--c-text-muted);line-height:2.5">'
                'Letzte Suchen:</span>',
                unsafe_allow_html=True,
            )
        for i, t in enumerate(terms[:8]):
            with _cols[i + 1]:
                if st.button(t[:15], key=f"recent_search_{i}"):
                    st.session_state["_search_query"] = t
                    st.rerun()


# ===========================================================================
# Feature 4: Trend Sparkline
# ===========================================================================

@st.cache_data(ttl=600, show_spinner=False)
def _get_sparkline_counts(query: str) -> tuple:
    """Cached: weekly article counts for sparkline + previous period total."""
    import sqlite3
    from src.config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    try:
        pat = f"%{query}%"
        rows = conn.execute("""
            SELECT strftime('%Y-%W', pub_date) as week, COUNT(*) as cnt
            FROM article
            WHERE (title LIKE ? OR abstract LIKE ? OR summary_de LIKE ?)
              AND pub_date >= date('now', '-90 days')
            GROUP BY week ORDER BY week
        """, (pat, pat, pat)).fetchall()
        prev_count = conn.execute("""
            SELECT COUNT(*) FROM article
            WHERE (title LIKE ? OR abstract LIKE ? OR summary_de LIKE ?)
              AND pub_date >= date('now', '-180 days')
              AND pub_date < date('now', '-90 days')
        """, (pat, pat, pat)).fetchone()[0]
    finally:
        conn.close()
    return rows, prev_count


def _render_trend_sparkline(query: str):
    """Show article count over last 90 days as sparkline for search term."""
    rows, prev_count = _get_sparkline_counts(query)

    total_90d = sum(r[1] for r in rows) if rows else 0

    if total_90d == 0:
        return

    # Trend direction
    if prev_count > 0:
        change_pct = ((total_90d - prev_count) / prev_count) * 100
        if change_pct > 10:
            trend_icon = "🔥"
            trend_text = f"Steigend (+{change_pct:.0f}%)"
            trend_color = "var(--c-success, #4ade80)"
        elif change_pct < -10:
            trend_icon = "📉"
            trend_text = f"Rückläufig ({change_pct:.0f}%)"
            trend_color = "var(--c-error, #f87171)"
        else:
            trend_icon = "➡️"
            trend_text = "Stabil"
            trend_color = "var(--c-text-muted)"
    else:
        trend_icon = "🆕"
        trend_text = "Neues Thema"
        trend_color = "var(--c-accent, #005461)"

    # Mini sparkline from weekly counts
    counts = [r[1] for r in rows]
    max_c = max(counts) if counts else 1
    bars = ""
    for c in counts[-12:]:  # last 12 weeks
        h = max(2, int((c / max_c) * 16))
        bars += (
            f'<span style="display:inline-block;width:4px;height:{h}px;'
            f'background:var(--c-accent, #005461);border-radius:1px;margin:0 1px;'
            f'vertical-align:bottom"></span>'
        )

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;'
        f'padding:8px 14px;background:var(--c-surface);border:1px solid var(--c-border);'
        f'border-radius:10px;margin-bottom:12px;font-size:0.78rem">'
        f'<span style="font-weight:600">"{_esc(query)}"</span>'
        f'<span style="color:var(--c-text-muted)">{total_90d} Artikel (90 Tage)</span>'
        f'<span style="display:inline-flex;align-items:flex-end;height:18px">{bars}</span>'
        f'<span style="color:{trend_color};font-weight:600">{trend_icon} {trend_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ===========================================================================
# Feature 5: Related Searches
# ===========================================================================

def _render_related_searches(query: str, results: list):
    """Show related search terms based on co-occurring specialties and MeSH terms."""
    if not results:
        return

    # Collect specialties and frequent terms from results
    specialties = set()
    terms = {}
    for art in results[:30]:
        sp = getattr(art, "specialty", "") or ""
        if sp:
            specialties.add(sp)
        # Extract MeSH terms
        mesh = getattr(art, "mesh_terms", "") or ""
        if mesh:
            for m in mesh.split(","):
                m = m.strip()
                if m and m.lower() != query.lower() and len(m) > 3:
                    terms[m] = terms.get(m, 0) + 1

    # Top co-occurring terms (not the query itself)
    top_terms = sorted(terms.items(), key=lambda x: -x[1])[:6]
    related = [t[0] for t in top_terms]

    # Add specialties as related if not too generic
    for sp in list(specialties)[:3]:
        if sp.lower() != query.lower() and sp not in related:
            related.append(sp)

    if not related:
        return

    pills = " ".join(
        f'<span style="display:inline-block;background:var(--c-surface);'
        f'border:1px solid var(--c-border);font-size:0.70rem;padding:2px 9px;'
        f'border-radius:10px;margin:2px;color:var(--c-text-secondary);cursor:default">'
        f'{_esc(r[:25])}</span>'
        for r in related[:8]
    )
    st.markdown(
        f'<div style="margin-bottom:8px">'
        f'<span style="font-size:0.68rem;color:var(--c-text-muted);margin-right:6px">'
        f'Verwandt:</span>{pills}</div>',
        unsafe_allow_html=True,
    )


# ===========================================================================
# Feature 3: Comparison View
# ===========================================================================

def _render_comparison(results: list):
    """Render side-by-side comparison of selected articles."""
    if len(results) < 2:
        st.info("Mindestens 2 Artikel nötig für den Vergleich.")
        return

    # Let user pick 2-4 articles
    st.markdown(
        '<div style="font-size:0.85rem;font-weight:600;margin-bottom:8px">'
        'Wähle 2–4 Artikel zum Vergleichen:</div>',
        unsafe_allow_html=True,
    )

    options = {}
    for art in results[:20]:
        title = getattr(art, "title", "?")[:60]
        score = getattr(art, "relevance_score", 0)
        aid = getattr(art, "id", 0)
        options[aid] = f"[{score:.0f}] {title}"

    selected_ids = st.multiselect(
        "Artikel auswählen",
        options=list(options.keys()),
        format_func=lambda x: options.get(x, str(x)),
        max_selections=4,
        default=list(options.keys())[:2] if len(options) >= 2 else [],
        key="compare_select",
        label_visibility="collapsed",
    )

    if len(selected_ids) < 2:
        st.caption("Wähle mindestens 2 Artikel aus.")
        return

    selected = [a for a in results if getattr(a, "id", 0) in selected_ids]

    # Build comparison table
    rows_data = [
        ("Score", [f"**{getattr(a, 'relevance_score', 0):.0f}**" for a in selected]),
        ("Quelle", [getattr(a, "journal", "—") or "—" for a in selected]),
        ("Datum", [str(getattr(a, "pub_date", "—") or "—")[:10] for a in selected]),
        ("Artikeltyp", [getattr(a, "study_type", "—") or "—" for a in selected]),
        ("Fachgebiet", [getattr(a, "specialty", "—") or "—" for a in selected]),
        ("Sprache", [getattr(a, "language", "—") or "—" for a in selected]),
    ]

    # Header row
    cols = st.columns([1] + [2] * len(selected))
    with cols[0]:
        st.markdown("**Kriterium**")
    for i, art in enumerate(selected):
        with cols[i + 1]:
            title = getattr(art, "title", "?")[:50]
            url = getattr(art, "url", "")
            if url:
                st.markdown(f"**[{_esc(title)}]({url})**")
            else:
                st.markdown(f"**{_esc(title)}**")

    st.markdown("---")

    for label, values in rows_data:
        cols = st.columns([1] + [2] * len(selected))
        with cols[0]:
            st.markdown(f"*{label}*")
        for i, val in enumerate(values):
            with cols[i + 1]:
                st.markdown(str(val)[:60])

    # KERN comparison
    st.markdown("---")
    st.markdown("**Kernergebnis**")
    for art in selected:
        summary = getattr(art, "summary_de", "") or ""
        kern = ""
        for line in summary.split(";;;"):
            if line.strip().startswith("KERN:"):
                kern = line.strip()[5:].strip()[:200]
                break
        if not kern:
            kern = summary[:200] if summary else "—"
        title_short = getattr(art, "title", "?")[:40]
        st.markdown(f"**{_esc(title_short)}**: {_esc(kern)}")

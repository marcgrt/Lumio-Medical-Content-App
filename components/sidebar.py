"""Lumio — Sidebar with filters, KPIs, watchlists, favorites, and score info."""

from datetime import date, timedelta
from pathlib import Path
import base64

import streamlit as st
# sqlmodel.delete is only needed for watchlist deletion — import lazily
# from sqlmodel import delete  # moved to lazy import inside function

from src.models import Watchlist, WatchlistMatch, get_session
from src.processing.watchlist import (
    get_active_watchlists, get_watchlist_counts,
    run_watchlist_matching,
)
from components.helpers import (
    _esc, get_articles, get_stats, get_unique_values,
    update_article_status, score_pill,
)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@st.cache_resource
def _load_static_b64(_v=3) -> tuple:
    """Load & base64-encode logo ONCE (cached forever). Bump _v to bust cache.

    Audio is loaded lazily via static file serving (app/static/news_flow.mp3)
    to avoid embedding ~970KB base64 in every HTML payload.
    """
    logo_b64 = ""
    logo_path = _STATIC_DIR / "logo.png"
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    # audio_b64 no longer needed — served via Streamlit static files
    return logo_b64, ""


def render_sidebar() -> dict:
    """Render the sidebar and return the current filter state as a dict.

    Returns a dict with keys:
        date_from, date_to, selected_specialties, selected_sources,
        min_score, language_filter, selected_study_types,
        open_access_only, status_filter, search_query,
        wl_all, wl_counts
    """
    with st.sidebar:
        # --- Logo + "Lumio" (pure HTML, no JS, no st.image) ---
        _logo_b64, _audio_b64 = _load_static_b64()

        _logo_img = (
            f'<img src="data:image/png;base64,{_logo_b64}" '
            f'width="120" style="display:block;margin:0 auto" />'
        ) if _logo_b64 else ""

        st.markdown(
            f'<div id="lumio-logo-block" style="text-align:center;padding:10px 0 4px 0">'
            f'{_logo_img}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # --- Easter Egg: 3× click on Logo → Confetti + Sound ---
        # Uses event delegation on parent document so Streamlit re-renders
        # don't break the click handler (no direct element binding needed).
        st.components.v1.html(f"""
        <script>
        (function(){{
          var pd = window.parent.document;
          var pw = window.parent;

          // Only register delegation once per parent window
          if (pw.__ee_delegated) return;
          pw.__ee_delegated = true;
          pw.__ee_clicks = 0;
          pw.__ee_timer = null;

          // Event delegation — survives Streamlit re-renders
          pd.addEventListener('click', function(e) {{
            var logo = e.target.closest('#lumio-logo-block');
            if (!logo) return;

            // Reset click counter after 2s of inactivity
            clearTimeout(pw.__ee_timer);
            pw.__ee_timer = setTimeout(function(){{ pw.__ee_clicks = 0; }}, 2000);

            pw.__ee_clicks++;
            var old = pd.getElementById('ee-hint');
            if (old) old.remove();

            if (pw.__ee_clicks === 1) {{
              var h = pd.createElement('div');
              h.id = 'ee-hint';
              h.style.cssText = 'text-align:center;font-size:0.75rem;opacity:0.4;padding:2px 0;color:#888';
              h.textContent = '\u00b7';
              logo.appendChild(h);
            }} else if (pw.__ee_clicks === 2) {{
              var h = pd.createElement('div');
              h.id = 'ee-hint';
              h.style.cssText = 'text-align:center;font-size:0.75rem;opacity:0.8;padding:2px 0;color:#bbb';
              h.textContent = String.fromCodePoint(0x1FAE3) + ' Noch einmal ' + String.fromCodePoint(0x2026);
              logo.appendChild(h);
            }} else if (pw.__ee_clicks >= 3) {{
              pw.__ee_clicks = 0;
              launchParty();
            }}
          }});

          // Set cursor on logo (re-applies after Streamlit re-renders)
          setInterval(function(){{
            var logo = pd.getElementById('lumio-logo-block');
            if (logo && logo.style.cursor !== 'pointer') logo.style.cursor = 'pointer';
          }}, 1000);

          function launchParty() {{
            // Clean up any previous party before starting new one
            var oldCss = pd.getElementById('ee-party-css'); if(oldCss) oldCss.remove();
            var oldConf = pd.getElementById('ee-confetti'); if(oldConf) oldConf.remove();
            var oldBanner = pd.querySelector('.ee-banner'); if(oldBanner) oldBanner.remove();

            var style = pd.createElement('style');
            style.id = 'ee-party-css';
            style.textContent = '\\
              @keyframes ee-hue {{ 0%{{filter:hue-rotate(0deg)}} 100%{{filter:hue-rotate(360deg)}} }}\\
              @keyframes ee-pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.85}} }}\\
              @keyframes ee-float {{\\
                0%{{transform:translateY(0) rotate(0deg)}}\\
                50%{{transform:translateY(-8px) rotate(2deg)}}\\
                100%{{transform:translateY(0) rotate(0deg)}}\\
              }}\\
              @keyframes ee-confetti-fall {{\\
                0% {{ transform:translateY(0) rotate(0deg); opacity:1; }}\\
                100% {{ transform:translateY(105vh) rotate(720deg); opacity:0; }}\\
              }}\\
              .ee-party .a-score-ring svg {{ animation:ee-hue 3s linear infinite, ee-float 2s ease-in-out infinite !important; }}\\
              .ee-party .a-card {{ animation:ee-pulse 1.5s ease-in-out infinite !important; }}\\
              .ee-party .dash-card,.ee-party .kpi-card,.ee-party .trend-hero {{ animation:ee-float 2.5s ease-in-out infinite !important; }}\\
              .ee-party [data-testid="stSidebar"] {{ animation:ee-hue 4s linear infinite !important; }}\\
              .ee-banner {{\\
                position:fixed;bottom:24px;left:50%;transform:translateX(-50%);\\
                background:linear-gradient(135deg,#a3e635,#22d3ee);\\
                color:#0a0a1a;padding:12px 32px;border-radius:16px;\\
                font-weight:800;font-size:0.85rem;letter-spacing:0.02em;\\
                z-index:999999;box-shadow:0 4px 24px rgba(163,230,53,0.35);\\
                cursor:pointer;font-family:Inter,sans-serif;\\
                text-align:center;line-height:1.5;white-space:nowrap;\\
              }}\\
              .ee-banner:hover {{ filter:brightness(1.15);transform:translateX(-50%) scale(1.03); }}\\
            ';
            pd.head.appendChild(style);

            var appRoot = pd.querySelector('[data-testid="stAppViewContainer"]') || pd.querySelector('.main');
            if (appRoot) appRoot.classList.add('ee-party');

            var confetti = pd.createElement('div');
            confetti.id = 'ee-confetti';
            confetti.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:999998;overflow:hidden;';
            pd.body.appendChild(confetti);
            var colors = ['#a3e635','#22d3ee','#fbbf24','#f87171','#a78bfa','#fb923c'];
            for (var i = 0; i < 80; i++) {{
              var c = pd.createElement('div');
              var sz = Math.random()*8+4;
              c.style.cssText = 'position:absolute;width:'+sz+'px;height:'+sz+'px;background:'+colors[i%colors.length]+';border-radius:'+(Math.random()>0.5?'50%':'2px')+';left:'+(Math.random()*100)+'vw;top:-20px;opacity:0.9;animation:ee-confetti-fall '+(Math.random()*2+2)+'s ease-in '+(Math.random()*1.5)+'s forwards;';
              confetti.appendChild(c);
            }}
            setTimeout(function(){{ if(confetti) confetti.innerHTML=''; }}, 5000);

            pw.__ee_audio = new Audio('app/static/onboarding_track.mp3');
            pw.__ee_audio.loop = true;
            pw.__ee_playing = false;

            var banner = pd.createElement('div');
            banner.className = 'ee-banner';
            banner.innerHTML = '<span style="display:block;font-size:1rem">' + String.fromCodePoint(0x1F3B5) + ' News Flow</span><span style="display:block;font-size:0.72rem;font-weight:600;opacity:0.7">Klick zum Abspielen</span>';
            banner.addEventListener('click', function() {{
              if (!pw.__ee_playing) {{
                if (pw.__ee_audio) {{ pw.__ee_audio.play(); pw.__ee_playing = true; }}
                this.querySelector('span:last-child').textContent = 'Nochmal klicken zum Stoppen';
              }} else {{
                if (pw.__ee_audio) {{ pw.__ee_audio.pause(); pw.__ee_audio = null; pw.__ee_playing = false; }}
                var r = pd.querySelector('[data-testid="stAppViewContainer"]') || pd.querySelector('.main');
                if (r) r.classList.remove('ee-party');
                var s = pd.getElementById('ee-party-css'); if(s) s.remove();
                var cf = pd.getElementById('ee-confetti'); if(cf) cf.remove();
                this.remove();
              }}
            }});
            pd.body.appendChild(banner);
          }}
          // --- Help button (injected inline, same iframe) ---
          var sidebar=pd.querySelector('[data-testid="stSidebar"]');
          if(sidebar && !pd.getElementById('lumio-help-btn')) {{
            var btn=pd.createElement('div');
            btn.id='lumio-help-btn';
            btn.title='Tour starten';
            btn.textContent='?';
            var cs=window.parent.getComputedStyle(pd.documentElement);
            var cBorder=cs.getPropertyValue('--c-border').trim()||'rgba(255,255,255,0.07)';
            var cMuted=cs.getPropertyValue('--c-text-muted').trim()||'#6b6b82';
            var cAccent=cs.getPropertyValue('--c-accent').trim()||'#a3e635';
            var cAccentLight=cs.getPropertyValue('--c-accent-light').trim()||'rgba(132,204,22,0.12)';
            btn.style.cssText='position:fixed;top:14px;right:14px;width:28px;height:28px;border-radius:50%;'+
              'background:var(--c-surface);border:1px solid '+cBorder+';'+
              'color:'+cMuted+';font-size:0.78rem;font-weight:700;display:flex;align-items:center;'+
              'justify-content:center;cursor:pointer;z-index:10;transition:background 0.2s,border-color 0.2s,color 0.2s;';
            btn.onmouseenter=function(){{btn.style.background=cAccentLight;btn.style.borderColor=cAccent;btn.style.color=cAccent;}};
            btn.onmouseleave=function(){{btn.style.background='var(--c-surface)';btn.style.borderColor=cBorder;btn.style.color=cMuted;}};
            btn.addEventListener('click',function(){{
              if(window.parent.__lumioRestartTour) window.parent.__lumioRestartTour();
            }});
            sidebar.appendChild(btn);
          }}
        }})();
        </script>
        """, height=0)

        # --- Compact KPI bar ---
        stats = get_stats()
        st.markdown(f"""
            <div class="sidebar-kpi-bar">
                <div class="sidebar-kpi-item">
                    <div class="sidebar-kpi-num" style="color:var(--c-text)">{stats['total']}</div>
                    <div class="sidebar-kpi-lbl">Gesamt</div>
                </div>
                <div class="sidebar-kpi-item">
                    <div class="sidebar-kpi-num" style="color:var(--c-success)">{stats['hq']}</div>
                    <div class="sidebar-kpi-lbl">Score \u226570</div>
                </div>
                <div class="sidebar-kpi-item">
                    <div class="sidebar-kpi-num" style="color:var(--c-danger)">{stats['alerts']}</div>
                    <div class="sidebar-kpi-lbl">Alerts</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.divider()

        # --- Zeitraum: Schnellauswahl + Fein-Regler ---
        st.markdown('<div class="filter-label">Zeitraum</div>', unsafe_allow_html=True)

        # --- Zeitraum: Radio pills + fine slider, synced via session_state ---
        _QUICK_OPTIONS = ["1T", "7T", "14T", "30T", "3M", "\u221e"]
        _QUICK_TO_DAYS = {"1T": 1, "7T": 7, "14T": 14, "30T": 30, "3M": 90, "\u221e": 0}
        _TIME_STOPS = [
            (1, "1 Tag"), (2, "2 Tage"), (3, "3 Tage"), (5, "5 Tage"),
            (7, "1 Woche"), (10, "10 Tage"), (14, "2 Wochen"),
            (21, "3 Wochen"), (30, "30 Tage"),
            (60, "2 Monate"), (90, "3 Monate"), (120, "4 Monate"),
            (180, "6 Monate"), (270, "9 Monate"), (365, "12 Monate"),
            (0, "Gesamt"),
        ]
        _stop_values = [s[0] for s in _TIME_STOPS]
        _stop_labels = {s[0]: s[1] for s in _TIME_STOPS}

        # Initialise single source of truth
        if "_time_days" not in st.session_state:
            st.session_state["_time_days"] = 7

        # Use on_change callbacks to avoid double-rerun issues
        def _on_radio_change():
            val = st.session_state.get("_time_radio_widget", "7T")
            st.session_state["_time_days"] = _QUICK_TO_DAYS.get(val, 7)

        def _on_slider_change():
            st.session_state["_time_days"] = st.session_state.get("_time_slider_widget", 7)

        # Compute current radio index from _time_days
        _current_days = st.session_state["_time_days"]
        _radio_match = next((k for k, v in _QUICK_TO_DAYS.items() if v == _current_days), None)
        _radio_idx = _QUICK_OPTIONS.index(_radio_match) if _radio_match in _QUICK_OPTIONS else 1

        st.radio(
            "Zeitraum",
            _QUICK_OPTIONS,
            index=_radio_idx,
            horizontal=True,
            label_visibility="collapsed",
            key="_time_radio_widget",
            on_change=_on_radio_change,
        )

        st.select_slider(
            "Zeitraum fein",
            options=_stop_values,
            value=_current_days if _current_days in _stop_values else 7,
            format_func=lambda v: _stop_labels.get(v, str(v)),
            key="_time_slider_widget",
            label_visibility="collapsed",
            on_change=_on_slider_change,
        )

        # Convert to date_from
        _days_val = st.session_state.get("_time_days", 7)
        date_from = None
        date_to = date.today()
        if _days_val == 0:
            date_from = None  # Gesamt = kein Limit
        else:
            date_from = date.today() - timedelta(days=_days_val)

        # --- Fachgebiet ---
        st.markdown('<div class="filter-label">Fachgebiet</div>', unsafe_allow_html=True)
        all_specialties = get_unique_values("specialty")
        selected_specialties = st.multiselect(
            "Fachgebiet", options=all_specialties, default=[],
            placeholder="Alle Fachgebiete", label_visibility="collapsed",
        )

        # --- Quellen (hochgezogen) ---
        st.markdown('<div class="filter-label">Quellen</div>', unsafe_allow_html=True)
        all_sources = get_unique_values("source")
        selected_sources = st.multiselect(
            "Quellen", options=all_sources, default=[],
            placeholder="Alle Quellen", label_visibility="collapsed",
        )

        # --- Sprache (einzeilig) ---
        st.markdown('<div class="filter-label">Sprache</div>', unsafe_allow_html=True)
        language_filter = st.radio(
            "Sprache",
            ["Alle", "DE", "EN"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )

        # --- Sortierung ---
        _SORT_OPTIONS = [
            "\U0001f525 Trending",
            "\U0001f3af High Score",
            "\U0001f552 Neueste zuerst",
            "\U0001f4d1 Quelle A\u2013Z",
            "\u2728 Redaktions-Tipp",
            "\U0001f48e Unentdeckte Perlen",
            "\U0001fa7a Klinische Dringlichkeit",
        ]
        _SORT_KEY_MAP = {
            "\U0001f525 Trending": "score",
            "\U0001f3af High Score": "high_score",
            "\U0001f552 Neueste zuerst": "date",
            "\U0001f4d1 Quelle A\u2013Z": "source",
            "\u2728 Redaktions-Tipp": "editorial",
            "\U0001f48e Unentdeckte Perlen": "hidden_gems",
            "\U0001fa7a Klinische Dringlichkeit": "clinical",
        }
        _sort_label = st.selectbox(
            "Sortierung",
            _SORT_OPTIONS,
            index=0,
            help="🔥 Trending = Score × Aktualität  \n🎯 High Score = Reiner Score  \n✨ Redaktions-Tipp = Score × Frische  \n💎 Perlen = Seltene Quellen  \n🩺 Klinisch = Handlungsrelevanz",
        )
        sort_by_value = _SORT_KEY_MAP.get(_sort_label, "score")

        # Track sort change
        if st.session_state.get("_last_sort") != sort_by_value:
            from components.auth import track_activity
            track_activity("sort_change", f"sort:{sort_by_value}")
            st.session_state["_last_sort"] = sort_by_value

        # --- Quellenkategorie (prominent) ---
        st.markdown('<div class="filter-label">Quellenkategorie</div>', unsafe_allow_html=True)
        _SOURCE_CATEGORY_LABELS = {
            "top_journal": "Top-Journals",
            "specialty_journal": "Specialty-Journals",
            "fachpresse_de": "Deutsche Fachpresse",
            "fachpresse_aufbereitet": "Aufbereitete Quellen",
            "berufspolitik": "Berufspolitik",
            "behoerde": "Beh\u00f6rden",
            "leitlinie": "Leitlinien",
            "fachgesellschaft": "Fachgesellschaften",
            "literaturdatenbank": "Literaturdatenbanken",
            "preprint": "Preprints",
            "news_aggregation": "News",
        }
        all_categories = get_unique_values("source_category")
        selected_categories = st.multiselect(
            "Quellenkategorie",
            options=all_categories,
            default=[],
            format_func=lambda x: _SOURCE_CATEGORY_LABELS.get(x, x),
            placeholder="Alle Kategorien",
            label_visibility="collapsed",
        )

        # --- Status (prominent) ---
        st.markdown('<div class="filter-label">Status</div>', unsafe_allow_html=True)
        status_filter = st.radio(
            "Status",
            ["ALL", "NEW", "SAVED", "ALERT", "ARCHIVED"],
            format_func=lambda x: {
                "ALL": "Alle", "NEW": "Neu",
                "SAVED": "Gemerkt", "ALERT": "Warnungen",
                "ARCHIVED": "Archiv",
            }.get(x, x),
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )

        # --- Weitere Filter (collapsed) ---
        # Default values for widgets inside expander (needed when collapsed)
        min_score = 0
        with st.expander("Weitere Filter", expanded=False):
            # --- Mindest-Score ---
            min_score = st.slider("Mindest-Score", 0, 100, 0, 5)

            # --- Artikeltyp ---
            _study_type_options = get_unique_values("study_type")
            selected_study_types = st.multiselect(
                "Artikeltyp", options=_study_type_options, default=[],
                placeholder="Alle Artikeltypen", label_visibility="collapsed",
            )

            # --- Hat Zusammenfassung ---
            has_summary_only = st.checkbox("Nur mit Zusammenfassung", value=False)

            # --- Open Access ---
            open_access_only = st.checkbox("Nur Open Access", value=False)

        # Search removed from sidebar — use "Suche & Insights" tab
        search_query = ""

        st.divider()

        # --- Gemerkt (grouped by specialty, most-recently-saved first) ---
        _fav_n = stats['saved'] + stats['approved']
        _fav_label = f"\u2b50 Gemerkt ({_fav_n})" if _fav_n > 0 else "\u2b50 Gemerkt"
        with st.expander(_fav_label, expanded=False):
            _fav_saved = get_articles(status_filter="SAVED", min_score=0)
            _fav_approved = get_articles(status_filter="APPROVED", min_score=0)
            _fav_all = _fav_saved + _fav_approved
            if not _fav_all:
                st.markdown(
                    '<div style="text-align:center;padding:12px 8px;color:var(--c-text-muted);'
                    'font-size:0.8rem">'
                    'Noch keine gemerkten Artikel.<br>'
                    'Nutze <b>\u2606</b> (Merken) bei Artikeln, '
                    'um sie hier zu sammeln.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                # Sort: most recently saved first (created_at descending)
                _fav_all.sort(key=lambda a: a.created_at, reverse=True)

                # Group by specialty (OrderedDict preserves insertion = recency order)
                from collections import OrderedDict
                _spec_groups: OrderedDict[str, list] = OrderedDict()
                for a in _fav_all:
                    spec = a.specialty or "Sonstige"
                    _spec_groups.setdefault(spec, []).append(a)

                # Render each specialty as a nested st.expander
                _ri = 0
                for spec, articles in _spec_groups.items():
                    with st.expander(f"{spec} ({len(articles)})", expanded=False):
                        for a in articles:
                            safe_t = _esc(a.title[:80])
                            safe_u = _esc(a.url) if a.url else ""
                            title_el = (
                                f'<a href="{safe_u}" target="_blank" '
                                f'style="font-size:0.72rem;color:var(--c-text);'
                                f'text-decoration:none;line-height:1.3">{safe_t}</a>'
                                if safe_u
                                else f'<span style="font-size:0.72rem;line-height:1.3">{safe_t}</span>'
                            )
                            st.markdown(
                                f'<div style="display:flex;align-items:start;gap:5px;'
                                f'padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.04)">'
                                f'{score_pill(a.relevance_score)}'
                                f'<span style="flex:1;min-width:0">{title_el}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            if st.button("\u21a9", key=f"sb_fav_un_{a.id}_{_ri}",
                                          help="Zurücksetzen auf Neu"):
                                update_article_status(a.id, "NEW")
                                st.toast("Zurückgesetzt")
                                st.rerun()
                            _ri += 1

        # --- Watchlists (cached, per user) ---
        _current_uid = st.session_state.get("user_id")

        @st.cache_data(ttl=300, show_spinner=False)
        def _cached_watchlists(_uid=None):
            return get_active_watchlists(user_id=_uid)

        @st.cache_data(ttl=300, show_spinner=False)
        def _cached_wl_counts(_uid=None):
            return get_watchlist_counts(user_id=_uid)

        _wl_all = _cached_watchlists(_current_uid)
        _wl_counts = _cached_wl_counts(_current_uid) if _wl_all else {}

        # Keep expander open after deletion
        _wl_expanded = st.session_state.get("_wl_expanded", False)
        with st.expander(
            f"\U0001f3af Watchlists ({len(_wl_all)})" if _wl_all else "\U0001f3af Watchlists",
            expanded=_wl_expanded,
        ):
            if not _wl_all:
                st.markdown(
                    '<div style="text-align:center;padding:12px 8px;color:var(--c-text-muted);'
                    'font-size:0.8rem">'
                    'Keine Watchlists.<br>'
                    'Erstelle unten eine neue Watchlist, um Themen gezielt zu verfolgen.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                _active_wl = st.session_state.get("active_watchlist_id")

                # Info banner when a watchlist filter is active
                if _active_wl:
                    _active_wl_name = next(
                        (w.name for w in _wl_all if w.id == _active_wl), ""
                    )
                    st.markdown(
                        f'<div style="background:var(--c-accent);color:#fff;'
                        f'border-radius:8px;padding:10px 12px;margin-bottom:8px;'
                        f'font-size:0.82rem;line-height:1.4">'
                        f'<div style="font-weight:600">🎯 {_esc(_active_wl_name)}</div>'
                        f'<div style="font-size:0.72rem;opacity:0.85;margin-top:2px">'
                        f'Watchlist-Filter aktiv · ✅ erneut klicken zum Aufheben</div></div>',
                        unsafe_allow_html=True,
                    )

                for wl in _wl_all:
                    cnt = _wl_counts.get(wl.id, 0)
                    kw_short = wl.keywords[:40] + ("..." if len(wl.keywords) > 40 else "")
                    _is_active = (_active_wl == wl.id)

                    # Watchlist name + count — use native Streamlit for reliability
                    _wl_label = f"**{wl.name}**  {cnt} Treffer"
                    if _is_active:
                        _wl_label = f"**🎯 {wl.name}**  {cnt} Treffer"
                    st.markdown(_wl_label)
                    st.caption(kw_short)

                    # Action icons — side by side
                    _ic1, _ic2 = st.columns(2)
                    with _ic1:
                        _f_icon = "✅" if _is_active else "🔍"
                        _f_help = "Filter deaktivieren" if _is_active else "Im Feed filtern"
                        if st.button(_f_icon, key=f"wl_filter_{wl.id}",
                                     help=_f_help, use_container_width=True):
                            if _is_active:
                                st.session_state.pop("active_watchlist_id", None)
                            else:
                                st.session_state["active_watchlist_id"] = wl.id
                            st.session_state["_wl_expanded"] = True
                            st.rerun()
                    with _ic2:
                        if st.button("🗑️", key=f"del_wl_{wl.id}",
                                     help="Watchlist löschen", use_container_width=True):
                            with get_session() as session:
                                from sqlmodel import delete as _sqlmodel_delete
                                session.exec(_sqlmodel_delete(WatchlistMatch).where(WatchlistMatch.watchlist_id == wl.id))
                                _wl_obj = session.get(Watchlist, wl.id)
                                if _wl_obj:
                                    session.delete(_wl_obj)
                                session.commit()
                            _cached_watchlists.clear()
                            _cached_wl_counts.clear()
                            if _active_wl == wl.id:
                                st.session_state.pop("active_watchlist_id", None)
                            st.session_state["_wl_expanded"] = True
                            st.toast(f"Watchlist '{wl.name}' gelöscht")
                            st.rerun()

        # --- Neue Watchlist erstellen ---
        with st.expander("\u2795 Neue Watchlist erstellen", expanded=False):
            with st.form("watchlist_form", clear_on_submit=True):
                wl_name = st.text_input("Name", placeholder="z.B. GLP-1 Agonisten")
                wl_keywords = st.text_input(
                    "Stichwörter (kommagetrennt)",
                    placeholder="glp-1, semaglutide, tirzepatide",
                )
                all_specs = get_unique_values("specialty")
                wl_spec = st.selectbox(
                    "Fachgebiet (optional)", ["Alle"] + all_specs
                )
                wl_min_score = st.number_input(
                    "Mindest-Score", min_value=0, max_value=100, value=0, step=5
                )
                wl_submitted = st.form_submit_button("Watchlist anlegen")

                if wl_submitted and wl_name and wl_keywords:
                    with get_session() as session:
                        session.add(Watchlist(
                            user_id=st.session_state.get("user_id"),
                            name=wl_name.strip(),
                            keywords=wl_keywords.strip(),
                            specialty_filter=wl_spec if wl_spec != "Alle" else None,
                            min_score=float(wl_min_score),
                        ))
                        session.commit()
                    _existing_articles = get_articles(min_score=0)
                    run_watchlist_matching(article_count=len(_existing_articles))
                    _cached_watchlists.clear()
                    _cached_wl_counts.clear()
                    st.toast(f"Watchlist '{wl_name}' erstellt!")
                    st.rerun()

        # --- Score Info ---
        from src.config import SCORE_THRESHOLD_HIGH as _STH
        with st.expander("\u2139\ufe0f Score-Info"):
            st.markdown("""
<div style="font-size:0.75rem;line-height:1.5;color:var(--c-text)">
<div style="font-weight:700;margin-bottom:6px">Relevanz-Score v2 (0\u2013100)</div>

<div style="font-size:0.68rem;font-weight:600;color:var(--c-accent);margin:8px 0 4px;text-transform:uppercase;letter-spacing:0.5px">\U0001f916 KI-Scoring (prim\u00e4r)</div>
<div style="font-size:0.68rem;color:var(--c-text-muted);margin-bottom:6px">6 Dimensionen mit variablen Maxima via LLM (Summe = 100)</div>

<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Klinische Handlungsrelevanz</span><span style="color:var(--c-text-muted)">0\u201320</span>
</div>
<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:3px">Sofortige Handlung 20 \u203a Wahrscheinlich 15 \u203a Indirekt 11 \u203a Hintergrund 6</div>

<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Evidenz- &amp; Recherchetiefe</span><span style="color:var(--c-text-muted)">0\u201320</span>
</div>
<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:3px">Meta-Analyse/Investigativ 19 \u203a RCT/Solide 15 \u203a Moderat 11 \u203a Schwach 6</div>

<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Thematische Zugkraft</span><span style="color:var(--c-text-muted)">0\u201320</span>
</div>
<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:3px">Maximal 19 \u203a Stark 15 \u203a Moderat 11 \u203a Gering 6</div>

<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Neuigkeitswert</span><span style="color:var(--c-text-muted)">0\u201316</span>
</div>
<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:3px">Erstmalig 15 \u203a Update 11 \u203a Best\u00e4tigung 7 \u203a Nichts Neues 2</div>

<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Quellenautori\u00e4t</span><span style="color:var(--c-text-muted)">0\u201312</span>
</div>
<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:3px">NEJM/Lancet 12 \u203a Fachjournal 10 \u203a \u00c4rzteblatt 9 \u203a Preprint 3</div>

<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Aufbereitungsqualit\u00e4t</span><span style="color:var(--c-text-muted)">0\u201312</span>
</div>
<div style="font-size:0.65rem;color:var(--c-text-muted);margin-bottom:6px">Exzellent 12 \u203a Gut 9 \u203a Akzeptabel 6 \u203a Mangelhaft 3</div>

<div style="font-size:0.68rem;font-weight:600;color:var(--c-text-muted);margin:8px 0 4px;text-transform:uppercase;letter-spacing:0.5px">\U0001f4cf Regelbasiert (Fallback)</div>
<div style="font-size:0.68rem;color:var(--c-text-muted);margin-bottom:6px">Keyword-basierte Sch\u00e4tzung der 6 Dimensionen</div>

<div style="display:flex;gap:10px;font-size:0.72rem;font-weight:600;margin-top:8px;padding-top:6px;border-top:1px solid var(--c-border-subtle)">
    <span>\U0001f7e2 \u226570 TOP</span>
    <span>\U0001f7e1 45\u201369 RELEVANT</span>
    <span>\u26aa &lt;45 MONITOR</span>
</div>
</div>
            """, unsafe_allow_html=True)

    # Human-readable period label for feed subtitle
    _days = st.session_state.get("_time_days", 7)
    _period_labels = {0: "Alle Artikel", 1: "Heute", 7: "Letzte 7 Tage",
                      14: "Letzte 14 Tage", 30: "Letzte 30 Tage", 90: "Letzte 3 Monate"}
    _period_label = _period_labels.get(_days, f"Letzte {_days} Tage")

    return {
        "date_from": date_from,
        "date_to": date_to,
        "selected_specialties": selected_specialties,
        "selected_sources": selected_sources,
        "selected_categories": selected_categories,
        "min_score": min_score,
        "language_filter": language_filter,
        "sort_by": sort_by_value,
        "selected_study_types": selected_study_types,
        "has_summary_only": has_summary_only,
        "open_access_only": open_access_only,
        "status_filter": status_filter,
        "search_query": search_query,
        "wl_all": _wl_all,
        "wl_counts": _wl_counts,
        "period_label": _period_label,
    }

"""Lumio — Sidebar with filters, KPIs, watchlists, and score info."""

from datetime import date, timedelta
from pathlib import Path
import base64

import streamlit as st
from sqlmodel import delete

from src.models import Watchlist, WatchlistMatch, get_session
from src.processing.watchlist import (
    get_active_watchlists, get_watchlist_counts,
)
from components.helpers import (
    _esc, get_stats, get_unique_values,
)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@st.cache_resource
def _load_static_b64(_v=2) -> tuple:
    """Load & base64-encode logo + audio ONCE (cached forever). Bump _v to bust cache."""
    logo_b64 = ""
    logo_path = _STATIC_DIR / "logo.png"
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    audio_b64 = ""
    audio_path = _STATIC_DIR / "news_flow.mp3"
    if audio_path.exists():
        audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()

    return logo_b64, audio_b64


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

            var audioUri = 'data:audio/mpeg;base64,{_audio_b64}';
            pw.__ee_audio = new Audio(audioUri);
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
        }})();
        </script>
        """, height=0)

        # --- Help button (injected via JS so onclick works) ---
        st.components.v1.html("""
        <script>
        (function(){
          var pd=window.parent.document;
          var sidebar=pd.querySelector('[data-testid="stSidebar"]');
          if(!sidebar || pd.getElementById('lumio-help-btn')) return;
          var btn=pd.createElement('div');
          btn.id='lumio-help-btn';
          btn.title='Tour starten';
          btn.textContent='?';
          btn.style.cssText='position:fixed;top:14px;right:14px;width:28px;height:28px;border-radius:50%;'+
            'background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.07);'+
            'color:#6b6b82;font-size:0.78rem;font-weight:700;display:flex;align-items:center;'+
            'justify-content:center;cursor:pointer;z-index:10;transition:all 0.2s;';
          btn.onmouseenter=function(){btn.style.background='rgba(163,230,53,0.12)';btn.style.borderColor='#a3e635';btn.style.color='#a3e635';};
          btn.onmouseleave=function(){btn.style.background='rgba(255,255,255,0.06)';btn.style.borderColor='rgba(255,255,255,0.07)';btn.style.color='#6b6b82';};
          btn.addEventListener('click',function(){
            if(window.parent.__lumioRestartTour) window.parent.__lumioRestartTour();
          });
          sidebar.appendChild(btn);
        })();
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
                    <div class="sidebar-kpi-lbl">Top-Evidenz</div>
                </div>
                <div class="sidebar-kpi-item">
                    <div class="sidebar-kpi-num" style="color:var(--c-danger)">{stats['alerts']}</div>
                    <div class="sidebar-kpi-lbl">Alerts</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.divider()

        # --- Zeitraum (radio pills) ---
        st.markdown('<div class="filter-label">Zeitraum</div>', unsafe_allow_html=True)
        time_range = st.radio(
            "Zeitraum",
            ["Heute", "7 Tage", "30 Tage", "Alle"],
            index=1,
            horizontal=True,
            label_visibility="collapsed",
        )
        date_from = None
        date_to = date.today()
        if time_range == "Heute":
            date_from = date.today()
        elif time_range == "7 Tage":
            date_from = date.today() - timedelta(days=7)
        elif time_range == "30 Tage":
            date_from = date.today() - timedelta(days=30)

        # --- Fachgebiet ---
        st.markdown('<div class="filter-label">Fachgebiet</div>', unsafe_allow_html=True)
        all_specialties = get_unique_values("specialty")
        selected_specialties = st.multiselect(
            "Fachgebiet", options=all_specialties, default=[],
            placeholder="Alle Fachgebiete", label_visibility="collapsed",
        )

        # --- Score ---
        st.markdown('<div class="filter-label">Mindest-Score</div>', unsafe_allow_html=True)
        min_score = st.slider("Mindest-Score", 0, 100, 0, 5, label_visibility="collapsed")

        # --- Sprache ---
        st.markdown('<div class="filter-label">Sprache</div>', unsafe_allow_html=True)
        language_filter = st.radio(
            "Sprache",
            ["Alle", "Deutsch", "English"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )

        # --- Weitere Filter (collapsed) ---
        with st.expander("Weitere Filter", expanded=False):
            all_sources = get_unique_values("source")
            selected_sources = st.multiselect(
                "Quellen", options=all_sources, default=[],
                placeholder="Alle Quellen", label_visibility="collapsed",
            )

            # --- Studientyp ---
            _study_type_options = get_unique_values("study_type")
            selected_study_types = st.multiselect(
                "Studientyp", options=_study_type_options, default=[],
                placeholder="Alle Studientypen", label_visibility="collapsed",
            )

            # --- Open Access ---
            open_access_only = st.checkbox("Nur Open Access", value=False)

            status_filter = st.selectbox(
                "Status",
                ["ALL", "NEW", "SAVED", "REJECTED", "ALERT"],
                format_func=lambda x: {
                    "ALL": "Alle Status", "NEW": "Neu",
                    "SAVED": "Gemerkt", "REJECTED": "Ausgeblendet",
                    "ALERT": "Alerts",
                }.get(x, x),
            )
            search_query = st.text_input(
                "Suche", placeholder="Stichwort eingeben...",
                label_visibility="collapsed",
            )

        st.divider()

        # --- Gemerkt shortcut (immer sichtbar) ---
        _fav_n = stats['saved'] + stats['approved']
        _fav_count_html = f'{_fav_n}' if _fav_n > 0 else '\u2014'
        st.markdown(f"""
            <div class="fav-link">
                <span style="font-size:0.85rem">\u2606</span>
                <span style="font-size:0.78rem;font-weight:500;color:var(--c-text);flex:1">
                    Gemerkt</span>
                <span class="fav-count">{_fav_count_html}</span>
            </div>
        """, unsafe_allow_html=True)

        # --- Watchlists (cached) ---
        @st.cache_data(ttl=300, show_spinner=False)
        def _cached_watchlists():
            return get_active_watchlists()

        @st.cache_data(ttl=300, show_spinner=False)
        def _cached_wl_counts():
            return get_watchlist_counts()

        _wl_all = _cached_watchlists()
        _wl_counts = _cached_wl_counts() if _wl_all else {}

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
                    'Erstelle eine im <b>Feed</b>-Tab, um Themen gezielt zu verfolgen.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                _active_wl = st.session_state.get("active_watchlist_id")

                # "All articles" reset button when a watchlist filter is active
                if _active_wl:
                    if st.button("\u2190 Alle Artikel", key="wl_reset",
                                 use_container_width=True):
                        st.session_state.pop("active_watchlist_id", None)
                        st.session_state["_wl_expanded"] = True
                        st.rerun()

                for wl in _wl_all:
                    cnt = _wl_counts.get(wl.id, 0)
                    kw_short = wl.keywords[:30] + ("..." if len(wl.keywords) > 30 else "")
                    _is_active = (_active_wl == wl.id)

                    # Watchlist name button + count badge + delete button
                    _wl_cols = st.columns([5, 1])
                    with _wl_cols[0]:
                        # Highlight active watchlist
                        _border = "var(--c-accent)" if _is_active else "var(--c-border)"
                        _bg = "rgba(163,230,53,0.06)" if _is_active else "transparent"
                        st.markdown(
                            f'<div style="display:flex;justify-content:space-between;align-items:center;'
                            f'padding:4px 0;font-size:0.78rem">'
                            f'<span style="font-weight:600">{_esc(wl.name)}</span>'
                            f'<span style="background:var(--c-accent);color:var(--c-bg);font-size:0.6rem;'
                            f'font-weight:700;padding:2px 8px;border-radius:10px">{cnt}</span>'
                            f'</div>'
                            f'<div style="font-size:0.62rem;color:var(--c-text-muted);margin-bottom:2px">'
                            f'{_esc(kw_short)}</div>',
                            unsafe_allow_html=True,
                        )
                        # Clickable "Filter" / "Aktiv" button
                        _btn_label = "\u2714 Aktiv" if _is_active else "Filtern"
                        if st.button(_btn_label, key=f"wl_filter_{wl.id}",
                                     use_container_width=True):
                            if _is_active:
                                # Deactivate
                                st.session_state.pop("active_watchlist_id", None)
                            else:
                                st.session_state["active_watchlist_id"] = wl.id
                            st.session_state["_wl_expanded"] = True
                            st.rerun()

                    with _wl_cols[1]:
                        if st.button("\u2715", key=f"del_wl_{wl.id}",
                                     help="Watchlist l\u00f6schen"):
                            with get_session() as session:
                                session.exec(delete(WatchlistMatch).where(WatchlistMatch.watchlist_id == wl.id))
                                _wl_obj = session.get(Watchlist, wl.id)
                                if _wl_obj:
                                    session.delete(_wl_obj)
                                session.commit()
                            _cached_watchlists.clear()
                            _cached_wl_counts.clear()
                            # Clear active filter if deleted watchlist was active
                            if _active_wl == wl.id:
                                st.session_state.pop("active_watchlist_id", None)
                            st.session_state["_wl_expanded"] = True
                            st.toast(f"Watchlist '{wl.name}' gel\u00f6scht")
                            st.rerun()

        # --- Score Info ---
        from src.config import SCORE_THRESHOLD_HIGH as _STH
        with st.expander("\u2139\ufe0f Score-Info"):
            st.markdown("""
<div style="font-size:0.78rem;line-height:1.6;color:var(--c-text)">
<div style="font-weight:700;margin-bottom:6px">Relevanz-Score (0\u2013100)</div>
<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Journal</span><span style="color:var(--c-text-muted)">30 %</span>
</div>
<div style="font-size:0.7rem;color:var(--c-text-muted);margin-bottom:4px">NEJM, Lancet, \u00c4rzteblatt \u2026</div>
<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Studiendesign</span><span style="color:var(--c-text-muted)">25 %</span>
</div>
<div style="font-size:0.7rem;color:var(--c-text-muted);margin-bottom:4px">Meta-Analyse \u203a RCT \u203a Leitlinie \u203a Review \u203a News</div>
<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Aktualit\u00e4t</span><span style="color:var(--c-text-muted)">20 %</span>
</div>
<div style="font-size:0.7rem;color:var(--c-text-muted);margin-bottom:4px">Neuere Artikel scoren h\u00f6her</div>
<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Keywords</span><span style="color:var(--c-text-muted)">15 %</span>
</div>
<div style="font-size:0.7rem;color:var(--c-text-muted);margin-bottom:4px">Sicherheit, Leitlinien, Landmark</div>
<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--c-border-subtle)">
    <span style="font-weight:600">Arztrelevanz</span><span style="color:var(--c-text-muted)">10 %</span>
</div>
<div style="font-size:0.7rem;color:var(--c-text-muted);margin-bottom:8px">Therapie, Diagnostik, Gesundheitspolitik</div>
<div style="display:flex;gap:12px;font-size:0.75rem;font-weight:600">
    <span>\U0001f7e2 \u226565 Top</span>
    <span>\U0001f7e1 40\u201364 Solide</span>
    <span>\u26aa &lt;40 News</span>
</div>
</div>
            """, unsafe_allow_html=True)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "selected_specialties": selected_specialties,
        "selected_sources": selected_sources,
        "min_score": min_score,
        "language_filter": language_filter,
        "selected_study_types": selected_study_types,
        "open_access_only": open_access_only,
        "status_filter": status_filter,
        "search_query": search_query,
        "wl_all": _wl_all,
        "wl_counts": _wl_counts,
    }

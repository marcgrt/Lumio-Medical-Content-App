"""Lumio — Tägliches Medical Evidence Dashboard."""

from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from src.models import get_engine, get_session

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
_favicon_path = Path(__file__).parent / "static" / "favicon.png"
try:
    from PIL import Image as _PILImage
    _favicon = _PILImage.open(_favicon_path) if _favicon_path.exists() else "\u2728"
except Exception:
    _favicon = str(_favicon_path) if _favicon_path.exists() else "\u2728"
st.set_page_config(
    page_title="Lumio",
    page_icon=_favicon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure DB + tables exist
get_engine()

# ---------------------------------------------------------------------------
# Authentication — must be before any content rendering
# ---------------------------------------------------------------------------
from components.auth import (
    require_login, show_user_menu, track_activity, is_admin,
    load_theme_preference, show_theme_toggle, _save_theme_preference,
)
current_user = require_login()  # blocks with login form if not authenticated

# Load saved theme preference (after login, before CSS injection)
if "theme" not in st.session_state:
    st.session_state["theme"] = load_theme_preference(current_user["id"])

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
from components.css import inject_css
inject_css()

# ---------------------------------------------------------------------------
# Theme toggle — no hidden button, uses query_params for rerun trigger
# ---------------------------------------------------------------------------
if st.query_params.get("_toggle_theme") == "1":
    st.query_params.pop("_toggle_theme")
    cur = st.session_state.get("theme", "dark")
    new = "esanum" if cur == "dark" else "dark"
    st.session_state["theme"] = new
    track_activity("theme_change", f"theme:{new}")
    _save_theme_preference(current_user["id"], new)
    st.rerun()

show_theme_toggle()

# ---------------------------------------------------------------------------
# Initialise DB (engine already created above, just init FTS5)
# ---------------------------------------------------------------------------
if "fts_initialized" not in st.session_state:
    from src.models import init_fts5, populate_fts5
    init_fts5()
    populate_fts5()
    st.session_state.fts_initialized = True

# ---------------------------------------------------------------------------
# Splash video (plays once on first visit, then auto-dismisses)
# ---------------------------------------------------------------------------
from components.splash import inject_splash
inject_splash()

# ---------------------------------------------------------------------------
# Onboarding (JS-based spotlight tour — auto-shows on first visit)
# ---------------------------------------------------------------------------
from components.onboarding import inject_onboarding_tour
inject_onboarding_tour()

# ---------------------------------------------------------------------------
# Sidebar (with user menu at top)
# ---------------------------------------------------------------------------
show_user_menu()
from components.sidebar import render_sidebar
filters = render_sidebar()

# ---------------------------------------------------------------------------
# Sicherheitshinweise (Alerts) — persistent acknowledgment
# ---------------------------------------------------------------------------
from components.helpers import (
    _esc, acknowledge_alerts, get_unacknowledged_alerts,
)

if "banner_dismissed" not in st.session_state:
    st.session_state.banner_dismissed = False
if "alerts_expanded" not in st.session_state:
    st.session_state.alerts_expanded = False

if not st.session_state.banner_dismissed:
    _alert_articles = get_unacknowledged_alerts()
    if _alert_articles:
        _alert_count = len(_alert_articles)
        _show_all = st.session_state.alerts_expanded or _alert_count <= 3

        def _fmt_alert(a):
            if a.url:
                return (f'<a href="{_esc(a.url)}" target="_blank" '
                        f'style="color:var(--c-alert-text);text-decoration:none;font-weight:500">'
                        f'{_esc(a.title[:80])}</a>')
            return _esc(a.title[:80])

        if _show_all:
            _alert_html = " &bull; ".join(_fmt_alert(a) for a in _alert_articles)
            _toggle_html = ""
        else:
            _alert_html = " &bull; ".join(_fmt_alert(a) for a in _alert_articles[:3])
            _toggle_html = (
                f' <span id="alert-expand-trigger" style="color:var(--c-accent);font-size:0.75rem;'
                f'cursor:pointer;text-decoration:underline;font-weight:600">'
                f'(+{_alert_count - 3} weitere anzeigen)</span>'
            )

        st.markdown(f"""
            <div class="alert-banner">
                <div class="alert-dot"></div>
                <div style="flex:1">
                    <div style="font-weight:600;color:var(--c-alert-text);font-size:0.85rem;margin-bottom:4px">
                        {_alert_count} Arzneimittelwarnung{'en' if _alert_count > 1 else ''}
                    </div>
                    <div style="font-size:0.8rem;color:var(--c-text-muted)">{_alert_html}{_toggle_html}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        _bcols = st.columns([7, 1, 1, 1])
        # Hidden expand button triggered by JS click on "(+N weitere)"
        with _bcols[0]:
            if not _show_all and _alert_count > 3:
                if st.button("alle anzeigen", key="alert_expand",
                             help="Alle Warnungen anzeigen"):
                    st.session_state.alerts_expanded = True
                    st.rerun()
        with _bcols[1]:
            if _show_all and _alert_count > 3:
                if st.button("einklappen", key="alert_collapse",
                             help="Nur 3 anzeigen"):
                    st.session_state.alerts_expanded = False
                    st.rerun()
        with _bcols[2]:
            if st.button("Gelesen \u2713", key="alert_ack_all",
                         help="Alle Alerts als gelesen markieren (dauerhaft)"):
                acknowledge_alerts([a.id for a in _alert_articles])
                st.rerun()
        with _bcols[3]:
            if st.button("\u2715", key="alert_dismiss_banner",
                         help="Banner vor\u00fcbergehend ausblenden"):
                st.session_state.banner_dismissed = True
                st.rerun()

        # JS: hide the native expand button + make the "(+N weitere)" span click it
        if not _show_all and _alert_count > 3:
            st.components.v1.html("""<script>
            (function(){
                var pd = window.parent.document;
                // Hide the native "alle anzeigen" button
                var btns = pd.querySelectorAll('button');
                for(var i=0;i<btns.length;i++){
                    if(btns[i].textContent.trim()==='alle anzeigen'){
                        var block = btns[i].closest('[data-testid="stHorizontalBlock"]');
                        if(block) btns[i].style.cssText='position:absolute;opacity:0;pointer-events:none;height:0;overflow:hidden';
                        // Wire up the HTML span to click this button
                        var trigger = pd.getElementById('alert-expand-trigger');
                        if(trigger){
                            trigger.onclick = function(){ btns[i].click(); };
                        }
                        break;
                    }
                }
            })();
            </script>""", height=0)


# ---------------------------------------------------------------------------
# Main tabs (6 tabs)
# ---------------------------------------------------------------------------
_tab_names = ["Feed", "Suche & Insights", "Saisonale Themen", "Kongresse", "Redaktion", "Versand", "Themen-Radar"]
if is_admin():
    _tab_names.append("Team")
_tabs = st.tabs(_tab_names)

# Persist active tab across reloads via URL query param + JS
_saved_tab = st.query_params.get("tab", "")
if _saved_tab:
    # Find tab index by name
    _tab_idx = next((i for i, n in enumerate(_tab_names) if n == _saved_tab), -1)
    # Combined: restore saved tab + track tab changes (single iframe)
    st.components.v1.html(f"""<script>
    (function() {{
        var pd = window.parent.document;
        var tabs = pd.querySelectorAll('[role="tab"]');
        // Restore saved tab
        var idx = {_tab_idx if _tab_idx > 0 else 0};
        if (idx > 0 && tabs.length > idx) {{ tabs[idx].click(); }}
        // Track tab clicks → URL param
        tabs.forEach(function(tab) {{
            tab.addEventListener('click', function() {{
                var url = new URL(window.parent.location);
                url.searchParams.set('tab', this.textContent.trim());
                window.parent.history.replaceState({{}}, '', url);
            }});
        }});
    }})();
    </script>""", height=0)
tab_feed, tab_search_insights, tab_saisonal, tab_kongresse, tab_cowork, tab_versand, tab_radar = _tabs[:7]
tab_admin = _tabs[7] if is_admin() else None

# ---------------------------------------------------------------------------
# Track page view (once per session)
# ---------------------------------------------------------------------------
if "page_view_tracked" not in st.session_state:
    track_activity("page_view", "app_load")
    st.session_state.page_view_tracked = True

# ---------------------------------------------------------------------------
# Render tabs — Feed always loads, other tabs only on demand
# ---------------------------------------------------------------------------
_active_tab = st.query_params.get("tab", "Feed")

with tab_feed:
    try:
        from views.feed import render_feed
        render_feed(filters)
    except Exception as _feed_exc:
        import logging as _logging
        _logging.getLogger(__name__).exception("Feed rendering failed")
        st.error(f"Feed-Rendering fehlgeschlagen: {type(_feed_exc).__name__}: {_feed_exc}")

def _deferred_placeholder(label: str):
    """Show a lightweight placeholder for tabs not yet visited."""
    st.markdown(
        f'<div style="text-align:center;padding:40px 20px;color:var(--c-text-muted)">'
        f'<div style="font-size:1.2rem;margin-bottom:8px">⏳</div>'
        f'<div style="font-size:0.85rem">{label} wird geladen...</div></div>',
        unsafe_allow_html=True,
    )

with tab_search_insights:
    from views.search import render_search
    from views.insights import render_insights
    render_search(filters)
    st.markdown("""
    <div style="margin:48px 0 32px;position:relative;text-align:center">
        <hr style="border:none;border-top:2px solid var(--c-border);margin:0">
        <span style="position:relative;top:-13px;background:var(--c-bg);padding:0 20px;
            font-size:0.72rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
            color:var(--c-text-muted)">📊 Redaktions-Insights</span>
    </div>
    """, unsafe_allow_html=True)
    render_insights(filters)

with tab_saisonal:
    if _active_tab == "Saisonale Themen":
        from views.saisonal import render_saisonal
        render_saisonal()
    else:
        _deferred_placeholder("Saisonale Themen")

with tab_kongresse:
    if _active_tab == "Kongresse":
        from views.kongresse import render_kongresse
        render_kongresse()
    else:
        _deferred_placeholder("Kongresse")

with tab_cowork:
    if _active_tab == "Redaktion":
        from views.cowork import render_cowork
        render_cowork()
    else:
        _deferred_placeholder("Redaktion")

with tab_versand:
    if _active_tab == "Versand":
        from views.versand import render_versand
        render_versand()
    else:
        _deferred_placeholder("Versand")

with tab_radar:
    if _active_tab == "Themen-Radar":
        from views.feed import _render_themen_radar
        st.markdown('<div class="page-header">Themen-Radar</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="page-sub">Aktuelle Trend-Cluster und ihre Entwicklung</div>',
            unsafe_allow_html=True,
        )
        _render_themen_radar(filters)
    else:
        _deferred_placeholder("Themen-Radar")

# ---------------------------------------------------------------------------
# Admin-only: Usage Dashboard
# ---------------------------------------------------------------------------
if is_admin() and tab_admin is not None:
    with tab_admin:
        if _active_tab == "Team":
            from views.admin_usage import render_admin_usage
            render_admin_usage()
        else:
            _deferred_placeholder("Team")

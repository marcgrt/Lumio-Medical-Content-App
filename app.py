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
    _favicon = _PILImage.open(_favicon_path) if _favicon_path.exists() else "✨"
except Exception:
    _favicon = str(_favicon_path) if _favicon_path.exists() else "✨"
st.set_page_config(
    page_title="Lumio",
    page_icon=_favicon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure DB + tables exist
get_engine()

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
from components.css import inject_css
inject_css()

# ---------------------------------------------------------------------------
# Initialise DB (engine already created above, just init FTS5)
# ---------------------------------------------------------------------------
if "fts_initialized" not in st.session_state:
    from src.models import init_fts5, populate_fts5
    init_fts5()
    populate_fts5()
    st.session_state.fts_initialized = True

# ---------------------------------------------------------------------------
# Onboarding (JS-based spotlight tour — auto-shows on first visit)
# ---------------------------------------------------------------------------
from components.onboarding import inject_onboarding_tour
inject_onboarding_tour()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
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

if not st.session_state.banner_dismissed:
    _alert_articles = get_unacknowledged_alerts()
    if _alert_articles:
        _alert_count = len(_alert_articles)
        _alert_titles = " &bull; ".join(
            f'<a href="{_esc(a.url)}" style="color:var(--c-alert-text);text-decoration:none;font-weight:500">'
            f'{_esc(a.title[:60])}</a>'
            if a.url else _esc(a.title[:60])
            for a in _alert_articles[:3]
        )
        _more = (
            f' <span style="color:var(--c-text-tertiary);font-size:0.75rem">'
            f'(+{_alert_count - 3} weitere)</span>'
            if _alert_count > 3 else ""
        )

        st.markdown(f"""
            <div class="alert-banner">
                <div class="alert-dot"></div>
                <div style="flex:1">
                    <div style="font-weight:600;color:var(--c-alert-text);font-size:0.85rem;margin-bottom:4px">
                        {_alert_count} Arzneimittelwarnung{'en' if _alert_count > 1 else ''}
                    </div>
                    <div style="font-size:0.8rem;color:var(--c-text-muted)">{_alert_titles}{_more}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        _bcols = st.columns([8, 1, 1])
        with _bcols[1]:
            if st.button("Gelesen ✓", key="alert_ack_all",
                         help="Alle Alerts als gelesen markieren (dauerhaft)"):
                acknowledge_alerts([a.id for a in _alert_articles])
                st.rerun()
        with _bcols[2]:
            if st.button("✕", key="alert_dismiss_banner",
                         help="Banner vorübergehend ausblenden"):
                st.session_state.banner_dismissed = True
                st.rerun()


# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------
tab_feed, tab_search, tab_insights, tab_redaktion, tab_versand, tab_kongresse, tab_kalender = st.tabs([
    "Feed", "Suche", "Insights", "Redaktion", "Versand", "Kongresse", "Kalender"
])

# Lazy-load views — only import the module when its tab renders
with tab_feed:
    from views.feed import render_feed
    render_feed(filters)

with tab_search:
    from views.search import render_search
    render_search(filters)

with tab_insights:
    from views.insights import render_insights
    render_insights(filters)

with tab_redaktion:
    from views.redaktion import render_redaktion
    render_redaktion()

with tab_versand:
    from views.versand import render_versand
    render_versand()

with tab_kongresse:
    from views.kongresse import render_kongresse
    render_kongresse()

with tab_kalender:
    from views.kalender import render_kalender
    render_kalender()

# Easter Egg is now fully handled in JS (components/sidebar.py) — no Python code needed

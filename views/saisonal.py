"""Lumio — Saisonal tab: Saisonale Themen & klinische Schwerpunkte für Ärzte.

Motion-enhanced version with pulse ring, heatmap timeline, live dots,
departure-board countdowns, and progress indicators.
"""

from datetime import date, timedelta
from html import escape as _esc

import streamlit as st


def _find_cluster_articles(search_keys: list, days_back: int = 30, limit: int = 50) -> list:
    """Find articles matching any of the search keys (LIKE on title + abstract).

    Uses the same logic as _count_related_articles in redaktionskalender.py
    but returns the actual Article objects, sorted by score descending.
    """
    if not search_keys:
        return []
    try:
        from sqlmodel import select, col
        from sqlalchemy import or_
        from src.models import Article, get_session

        cutoff = date.today() - timedelta(days=days_back)
        with get_session() as session:
            conditions = []
            for term in search_keys:
                t = term.strip().lower()
                if len(t) < 3:
                    continue
                pattern = f"%{t}%"
                conditions.append(Article.title.ilike(pattern))
                conditions.append(Article.abstract.ilike(pattern))

            if not conditions:
                return []

            stmt = (
                select(Article)
                .where(Article.pub_date >= cutoff)
                .where(or_(*conditions))
                .order_by(col(Article.relevance_score).desc())
                .limit(limit)
            )
            return list(session.exec(stmt).all())
    except Exception:
        return []

_MONTH_SHORT_DE = {
    1: "Jan", 2: "Feb", 3: "Mär", 4: "Apr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez",
}

# Season gradients for hero top-bar
_SEASON_GRADIENTS = {
    "winter": ("#3b82f6", "#22d3ee"),   # Dec-Feb: blue → cyan
    "spring": ("#22c55e", "#84cc16"),   # Mar-May: green → lime
    "summer": ("#f59e0b", "#f97316"),   # Jun-Aug: amber → orange
    "autumn": ("#f97316", "#a78bfa"),   # Sep-Nov: orange → violet
}

_SEASON_EMOJI = {
    1: "\u2744\ufe0f", 2: "\u2744\ufe0f", 3: "\U0001f33f",
    4: "\U0001f33c", 5: "\U0001f33b", 6: "\u2600\ufe0f",
    7: "\U0001f321\ufe0f", 8: "\U0001f321\ufe0f", 9: "\U0001f342",
    10: "\U0001f343", 11: "\U0001f32b\ufe0f", 12: "\u2744\ufe0f",
}


def _get_season(month: int):
    if month in (12, 1, 2):
        return _SEASON_GRADIENTS["winter"]
    if month in (3, 4, 5):
        return _SEASON_GRADIENTS["spring"]
    if month in (6, 7, 8):
        return _SEASON_GRADIENTS["summer"]
    return _SEASON_GRADIENTS["autumn"]


# ---------------------------------------------------------------------------
# Cached data wrappers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_hero(month: int):
    from src.processing.redaktionskalender import get_seasonal_hero
    return get_seasonal_hero(month=month)

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_forecast():
    from src.processing.redaktionskalender import get_4week_forecast
    return get_4week_forecast()

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_clusters(month: int):
    from src.processing.redaktionskalender import get_cluster_cards
    return get_cluster_cards(month=month)

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_awareness(days_ahead: int = 90):
    from src.processing.redaktionskalender import get_upcoming_awareness
    return get_upcoming_awareness(days_ahead=days_ahead)

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_regulatory(days_ahead: int = 90):
    from src.processing.redaktionskalender import get_upcoming_regulatory
    return get_upcoming_regulatory(days_ahead=days_ahead)


# ---------------------------------------------------------------------------
# Section 1: Hero with SVG Pulse Ring + Season Gradient
# ---------------------------------------------------------------------------

def _render_hero(month: int):
    hero = _cached_hero(month)
    season_emoji = _SEASON_EMOJI.get(hero["month"], "\U0001f33f")
    grad_from, grad_to = _get_season(month)

    # Pulse ring: intensity = active_count / 26 total topics
    intensity = min(hero["active_count"] / 26 * 100, 100)
    ring_r = 42
    circumference = 2 * 3.14159 * ring_r  # ~263.9
    dash_offset = circumference - (circumference * intensity / 100)
    ring_color = "#f87171" if intensity > 60 else ("#fbbf24" if intensity > 30 else "#4ade80")

    # Build topic pills with staggered cascade
    pills_html = ""
    for i, t in enumerate(hero["active_topics"]):
        delay = 0.3 + i * 0.05
        pills_html += (
            f'<span class="saisonal-topic-pill" '
            f'style="background:{_esc(t["cluster_color_light"])};color:{_esc(t["cluster_color"])};'
            f'animation-delay:{delay:.2f}s">'
            f'{_esc(t["icon"])} {_esc(t["name_de"])}'
            f'</span> '
        )

    st.markdown(f"""
    <div class="saisonal-hero" style="--s-grad-from:{grad_from};--s-grad-to:{grad_to}">
        <!-- Ambient Particles -->
        <div class="saisonal-particles">
            <span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;position:relative;z-index:1">
            <div style="display:flex;align-items:center;gap:20px;flex:1;min-width:280px">
                <!-- Pulse Ring SVG -->
                <svg class="saisonal-pulse-ring" width="96" height="96" viewBox="0 0 100 100"
                     style="--ring-color:{ring_color};flex-shrink:0">
                    <defs>
                        <linearGradient id="ring-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stop-color="{ring_color}" stop-opacity="1"/>
                            <stop offset="100%" stop-color="{ring_color}" stop-opacity="0.4"/>
                        </linearGradient>
                        <filter id="ring-glow">
                            <feGaussianBlur stdDeviation="3" result="blur"/>
                            <feMerge>
                                <feMergeNode in="blur"/>
                                <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                        </filter>
                    </defs>
                    <circle class="track" cx="50" cy="50" r="{ring_r}"/>
                    <circle class="value" cx="50" cy="50" r="{ring_r}"
                            stroke="url(#ring-grad)"
                            stroke-linecap="round"
                            stroke-dasharray="{circumference:.1f}"
                            stroke-dashoffset="{dash_offset:.1f}"
                            filter="url(#ring-glow)"
                            style="transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1.2s cubic-bezier(0.22,1,0.36,1)"/>
                    <text class="ring-label" x="50" y="46">{hero["active_count"]}</text>
                    <text class="ring-sub" x="50" y="58">aktiv</text>
                </svg>
                <div>
                    <div style="font-size:0.6rem;font-weight:700;color:{grad_from};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">
                        Jetzt relevant &mdash; {_esc(str(hero["month_name"]))} {hero["year"]}
                    </div>
                    <div style="font-size:1.1rem;font-weight:700;color:var(--c-text);line-height:1.3;margin-bottom:3px">
                        {season_emoji} Saisonale Schwerpunkte
                    </div>
                    <div style="font-size:0.75rem;color:var(--c-text-muted)">
                        {hero["active_count"]} Themen aus {hero["active_cluster_count"]} Clustern
                    </div>
                </div>
            </div>
            <div style="text-align:center;min-width:90px">
                <div class="saisonal-hero-stat-value" style="font-size:2.2rem;color:var(--c-accent);animation-delay:0.4s">
                    {hero["total_articles_7d"]}
                </div>
                <div class="saisonal-hero-stat-label">Artikel (7d)</div>
            </div>
        </div>
        <!-- Topic pills cascade -->
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:16px">
            {pills_html}
        </div>
        <!-- Stats row -->
        <div style="display:flex;gap:28px;margin-top:16px;padding-top:12px;border-top:1px solid var(--c-border)">
            <div style="text-align:center">
                <div class="saisonal-hero-stat-value" style="color:#f87171;animation-delay:0.5s">{hero["peak_count"]}</div>
                <div class="saisonal-hero-stat-label">Peak</div>
            </div>
            <div style="text-align:center">
                <div class="saisonal-hero-stat-value" style="color:#fbbf24;animation-delay:0.6s">{hero["active_count"] - hero["peak_count"]}</div>
                <div class="saisonal-hero-stat-label">Aktiv</div>
            </div>
            <div style="text-align:center">
                <div class="saisonal-hero-stat-value" style="color:var(--c-text-secondary);animation-delay:0.7s">{hero["active_cluster_count"]}</div>
                <div class="saisonal-hero-stat-label">Cluster</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 2: Heatmap Timeline with Glow Playhead
# ---------------------------------------------------------------------------

def _render_forecast():
    """Section 2: 4-Wochen-Vorausschau — was kommt auf dich zu?"""
    st.markdown(
        '<div class="section-header">4-Wochen-Vorausschau</div>',
        unsafe_allow_html=True,
    )

    forecast = _cached_forecast()
    if not forecast:
        st.info("Keine Vorausschau-Daten verfügbar.")
        return

    for week in forecast:
        if not week["topics"]:
            continue

        st.markdown(
            f'<div style="font-size:0.75rem;font-weight:700;color:var(--c-accent);'
            f'text-transform:uppercase;letter-spacing:0.06em;margin:16px 0 8px">'
            f'{week["week_label"]}</div>',
            unsafe_allow_html=True,
        )

        for ti, t in enumerate(week["topics"]):
            rel = t["relevance"]
            is_upcoming = t.get("is_upcoming", False)
            has_articles = t["article_count"] > 0

            # Status indicator
            if rel == "peak":
                dot_color = "#f87171"
                dot_glow = "box-shadow:0 0 6px rgba(248,113,113,0.5)"
                border_color = "rgba(248,113,113,0.3)"
            elif is_upcoming:
                dot_color = "#fbbf24"
                dot_glow = "box-shadow:0 0 6px rgba(251,191,36,0.4)"
                border_color = "rgba(251,191,36,0.2)"
            else:
                dot_color = "var(--c-text-muted)"
                dot_glow = ""
                border_color = "var(--c-border)"

            # Article badge
            article_badge = ""
            if has_articles:
                article_badge = (
                    f'<span style="background:rgba(59,130,246,0.12);color:#3b82f6;'
                    f'padding:2px 8px;border-radius:8px;font-size:0.65rem;font-weight:600;'
                    f'margin-left:auto;white-space:nowrap">{t["article_count"]} Artikel</span>'
                )

            # Unique key for this topic
            topic_key = f"fc_{week['week_label'][:2]}_{ti}_{t['name_de'][:10]}"

            if has_articles:
                # Clickable: use st.expander to show articles
                with st.expander(
                    f"{t['icon']} {t['name_de']}  ·  {t['cluster_name']}  ·  {t['article_count']} Artikel",
                    expanded=False,
                ):
                    # Action hint
                    st.markdown(
                        f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-bottom:8px">'
                        f'{_esc(t["action_de"])}</div>',
                        unsafe_allow_html=True,
                    )

                    # Fetch and display related articles
                    from src.processing.redaktionskalender import get_related_articles
                    related = get_related_articles(t["name_de"], days_back=30, limit=8)

                    if related:
                        for ra in related:
                            _url = ra.url or ""
                            _title = (ra.title or "")[:100]
                            _source = ra.source or ""
                            _score = ra.relevance_score or 0
                            _pub = ra.pub_date.strftime("%d.%m.") if ra.pub_date else ""

                            # Score color
                            if _score >= 70:
                                sc_color = "#4ade80"
                            elif _score >= 45:
                                sc_color = "#fbbf24"
                            else:
                                sc_color = "#8b8ba0"

                            st.markdown(f"""
                            <div style="display:flex;align-items:center;gap:8px;padding:6px 0;
                                border-bottom:1px solid var(--c-border-subtle)">
                                <span style="font-size:0.7rem;font-weight:700;color:{sc_color};
                                    min-width:28px;text-align:center">{_score:.0f}</span>
                                <div style="flex:1;min-width:0">
                                    <a href="{_esc(_url)}" target="_blank" style="font-size:0.78rem;
                                        color:var(--c-text);text-decoration:none;
                                        line-height:1.3">{_esc(_title)}</a>
                                    <div style="font-size:0.62rem;color:var(--c-text-muted)">{_esc(_source)} · {_esc(_pub)}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown(
                            '<div style="font-size:0.72rem;color:var(--c-text-muted);padding:8px">'
                            'Keine passenden Artikel gefunden.</div>',
                            unsafe_allow_html=True,
                        )
            else:
                # Not clickable: static card
                dot_html = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:8px;{dot_glow}"></span>'
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;
                    border:1px solid {border_color};border-radius:var(--c-radius-sm);
                    background:var(--c-surface);margin-bottom:6px;
                    transition:all 0.2s ease">
                    {dot_html}
                    <div style="flex:1;min-width:0">
                        <div style="display:flex;align-items:center;gap:6px">
                            <span style="font-size:0.82rem;font-weight:600;color:var(--c-text)">{_esc(t["icon"])} {_esc(t["name_de"])}</span>
                            <span style="font-size:0.58rem;font-weight:600;padding:1px 6px;border-radius:6px;
                                background:{_esc(t['cluster_color'])}1a;color:{_esc(t['cluster_color'])}">{_esc(t["cluster_name"])}</span>
                        </div>
                        <div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:2px">{_esc(t["action_de"])}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 3: Cluster Cards with Live Dot + Progress Bar
# ---------------------------------------------------------------------------

def _render_clusters(month: int):
    st.markdown(
        '<div class="section-header">Themen-Cluster</div>',
        unsafe_allow_html=True,
    )

    clusters = _cached_clusters(month)

    for row_start in range(0, len(clusters), 3):
        row = clusters[row_start:row_start + 3]
        cols = st.columns(len(row))

        for col, cluster in zip(cols, row):
            with col:
                # Topic pills
                topic_pills = ""
                active_count = 0
                for t in cluster["topics"]:
                    rel = t["relevance"]
                    if rel != "off":
                        active_count += 1
                    topic_pills += (
                        f'<span class="saisonal-status-pill saisonal-status-{_esc(rel)}">'
                        f'{_esc(t["icon"])} {_esc(t["name_de"])}'
                        f'</span>'
                    )

                # Article count
                ac = cluster["total_article_count"]
                ac_color = "var(--c-success)" if ac > 5 else ("var(--c-text-secondary)" if ac > 0 else "var(--c-text-muted)")

                # Live dot
                status = cluster["status"]
                dot_cls = status  # "peak", "active", or "off"

                # Progress bar (active topics / total topics)
                total_topics = len(cluster["topics"])
                progress_pct = (active_count / total_topics * 100) if total_topics > 0 else 0

                st.markdown(f"""
                <div class="saisonal-cluster-card {'is-peak' if status == 'peak' else ''}" style="--spec-color:{cluster['color']};--cluster-color:{cluster['color']}">
                    <div class="accent-bar"></div>
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                        <div>
                            <div style="font-size:0.65rem;font-weight:700;color:{_esc(cluster['color'])};text-transform:uppercase;letter-spacing:0.06em">
                                {_esc(cluster['icon'])} {_esc(cluster['name_de'])}
                                <span class="saisonal-live-dot {dot_cls}"></span>
                            </div>
                        </div>
                        <div style="text-align:right">
                            <div style="font-size:1.3rem;font-weight:800;color:{ac_color};letter-spacing:-0.03em;line-height:1">{ac}</div>
                            <div style="font-size:0.55rem;font-weight:600;color:var(--c-text-muted);text-transform:uppercase">Artikel</div>
                        </div>
                    </div>
                    <div style="display:flex;gap:4px;flex-wrap:wrap">
                        {topic_pills}
                    </div>
                    <div class="saisonal-progress-track">
                        <div class="saisonal-progress-fill" style="width:{progress_pct:.0f}%;background:{cluster['color']}"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                _ac = cluster["total_article_count"]
                if _ac > 0:
                    with st.expander(f"\U0001f50d {_ac} Artikel anzeigen", expanded=False):
                        # Collect search keys only from ACTIVE topics (same as counter)
                        _all_keys = []
                        for _t in cluster["topics"]:
                            if _t.get("relevance") != "off" and _t.get("search_keys"):
                                _all_keys.extend(_t["search_keys"])

                        # Same 30-day window as the counter uses
                        _saisonal_arts = _find_cluster_articles(_all_keys, days_back=30, limit=_ac)
                        if _saisonal_arts:
                            for _sa in _saisonal_arts:
                                _score_color = "#4ade80" if (_sa.relevance_score or 0) >= 70 else "#f59e0b" if (_sa.relevance_score or 0) >= 50 else "var(--c-text-muted)"
                                st.markdown(
                                    f'<div style="padding:6px 0;border-bottom:1px solid var(--c-border-subtle);font-size:0.78rem">'
                                    f'<span style="color:{_score_color};font-weight:700">{_sa.relevance_score or 0:.0f}</span> '
                                    f'<a href="{_esc(_sa.url or "#")}" target="_blank" style="color:var(--c-accent)">'
                                    f'{_esc(_sa.title[:80])}</a>'
                                    f' <span style="color:var(--c-text-muted);font-size:0.68rem">'
                                    f'{_sa.journal or ""} · {_sa.pub_date.strftime("%d.%m.%Y") if _sa.pub_date else ""}</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.caption("Keine Treffer im aktuellen Zeitraum.")


# ---------------------------------------------------------------------------
# Section 4: Awareness (Departure Board Style)
# ---------------------------------------------------------------------------

def _render_awareness():
    st.markdown(
        '<div class="section-header">Awareness-Tage</div>',
        unsafe_allow_html=True,
    )

    awareness = _cached_awareness(90)
    if not awareness:
        st.info("Keine Awareness-Tage in den nächsten 90 Tagen.")
        return

    for i, ad in enumerate(awareness):
        days = ad["days_until"]
        if days <= 0:
            countdown_text = "JETZT"
            countdown_cls = "urgent"
        elif days <= 7:
            countdown_text = f"{days}d"
            countdown_cls = "urgent"
        elif days <= 30:
            countdown_text = f"{days}d"
            countdown_cls = "soon"
        else:
            countdown_text = f"{days}d"
            countdown_cls = "normal"

        flip_delay = 0.1 + i * 0.08
        article_badge = ""
        if ad["article_count"] > 0:
            article_badge = (
                f'<span class="saisonal-article-badge">'
                f'{ad["article_count"]} Artikel</span>'
            )

        bald_badge = ""
        if days <= 7 and days > 0:
            bald_badge = (
                '<span style="background:rgba(248,113,113,0.15);color:#f87171;'
                'padding:1px 6px;border-radius:6px;font-size:0.55rem;font-weight:700;'
                'margin-left:6px">BALD</span>'
            )

        st.markdown(f"""
        <div class="saisonal-awareness-item">
            <div class="saisonal-flip-badge {countdown_cls}" style="animation-delay:{flip_delay:.2f}s">{countdown_text}</div>
            <div style="flex:1;min-width:0">
                <div style="font-size:0.82rem;font-weight:600;color:var(--c-text)">{_esc(ad["name_de"])}{bald_badge}</div>
                <div style="font-size:0.7rem;color:var(--c-text-muted)">{_esc(ad["date_formatted"])} &mdash; {_esc(ad["description_de"])}</div>
            </div>
            {article_badge}
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 5: Regulatory with Drain Bar
# ---------------------------------------------------------------------------

def _render_regulatory():
    st.markdown(
        '<div class="section-header">Regulatorische Stichtage</div>',
        unsafe_allow_html=True,
    )

    regulatory = _cached_regulatory(90)
    if not regulatory:
        st.info("Keine regulatorischen Stichtage in den nächsten 90 Tagen.")
        return

    _CAT_COLORS = {
        "EBM": ("rgba(59,130,246,0.12)", "#3b82f6"),
        "AMNOG": ("rgba(167,139,250,0.12)", "#a78bfa"),
        "Rabattvertrag": ("rgba(251,191,36,0.12)", "#fbbf24"),
        "KBV": ("rgba(74,222,128,0.12)", "#4ade80"),
    }

    for i, rd in enumerate(regulatory):
        days = rd["days_until"]
        if days <= 14:
            countdown_cls = "urgent"
        elif days <= 30:
            countdown_cls = "soon"
        else:
            countdown_cls = "normal"
        countdown_text = "JETZT" if days <= 0 else f"{days}d"

        cat_bg, cat_color = _CAT_COLORS.get(rd["category"], ("var(--c-border)", "#8b8ba0"))
        flip_delay = 0.1 + i * 0.08

        # Drain bar: 100% at 90d → 0% at 0d
        drain_pct = max(0, min(100, days / 90 * 100))
        drain_color = "#4ade80" if drain_pct > 60 else ("#fbbf24" if drain_pct > 25 else "#f87171")

        st.markdown(f"""
        <div class="saisonal-regulatory-item">
            <div class="saisonal-countdown {countdown_cls}" style="animation-delay:{flip_delay:.2f}s">{countdown_text}</div>
            <div style="flex:1;min-width:0">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                    <span style="font-size:0.82rem;font-weight:600;color:var(--c-text)">{_esc(rd["title_de"])}</span>
                    <span class="saisonal-cat-badge" style="background:{cat_bg};color:{cat_color}">{_esc(rd["category"])}</span>
                </div>
                <div style="font-size:0.7rem;color:var(--c-text-muted)">{_esc(rd["date_formatted"])} &mdash; {_esc(rd["description_de"])}</div>
                <div class="saisonal-drain-track">
                    <div class="saisonal-drain-fill" style="width:{drain_pct:.0f}%;background:{drain_color}"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_saisonal():
    """Render the Saisonal tab content."""
    current_month = date.today().month

    st.markdown('<div class="page-header">Saisonale Themen</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Saisonale Themen &amp; klinische Schwerpunkte '
        '&mdash; was jetzt f\u00fcr die Praxis relevant ist</div>',
        unsafe_allow_html=True,
    )

    # Section 1: Hero (instant)
    _render_hero(current_month)

    # Section 2: Forecast (reveal delay 0.15s)
    st.markdown('<div class="saisonal-section-reveal" style="animation-delay:0.15s">', unsafe_allow_html=True)
    _render_forecast()
    st.markdown('</div>', unsafe_allow_html=True)

    # Section 3: Clusters (reveal delay 0.3s)
    st.markdown('<div class="saisonal-section-reveal" style="animation-delay:0.3s">', unsafe_allow_html=True)
    _render_clusters(current_month)
    st.markdown('</div>', unsafe_allow_html=True)

    # Section 4+5: Awareness + Regulatory (reveal delay 0.45s)
    st.markdown('<div class="saisonal-section-reveal" style="animation-delay:0.45s">', unsafe_allow_html=True)
    col_aw, col_reg = st.columns(2)
    with col_aw:
        _render_awareness()
    with col_reg:
        _render_regulatory()
    st.markdown('</div>', unsafe_allow_html=True)

"""Lumio — Feed Admin: monitor feed health, enable/disable feeds, trigger manual fetches."""

import html as html_mod

import streamlit as st

from src.config import FEED_REGISTRY
from src.processing.feed_monitor import get_all_feed_statuses


_STATUS_DOTS = {
    "green": "\U0001f7e2",
    "yellow": "\U0001f7e1",
    "red": "\U0001f534",
    "gray": "\u26ab",
}

_SOURCE_CATEGORY_LABELS = {
    "top_journal": "Top-Journals",
    "specialty_journal": "Specialty-Journals",
    "fachpresse_de": "Deutsche Fachpresse",
    "fachpresse_aufbereitet": "Aufbereitete Quellen",
    "berufspolitik": "Berufspolitik",
    "behoerde": "Behörden",
    "leitlinie": "Leitlinien",
    "fachgesellschaft": "Fachgesellschaften",
    "literaturdatenbank": "Literaturdatenbanken",
    "preprint": "Preprints",
    "news_aggregation": "News",
}


def render_feed_admin():
    """Render the Feed Admin tab."""
    st.markdown('<div class="page-header">Feed-Verwaltung</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Status aller konfigurierten Feeds</div>',
        unsafe_allow_html=True,
    )

    # Get live statuses from DB
    db_statuses = {s["feed_name"]: s for s in get_all_feed_statuses()}

    # Build combined view from registry + DB status
    rows = []
    for name, cfg in FEED_REGISTRY.items():
        db = db_statuses.get(name, {})
        color = db.get("status_color", "gray" if not cfg.active else "yellow")
        if not cfg.active:
            color = "gray"

        rows.append({
            "name": name,
            "url": cfg.url[:60] + ("..." if len(cfg.url) > 60 else ""),
            "category": _SOURCE_CATEGORY_LABELS.get(cfg.source_category, cfg.source_category),
            "feed_type": cfg.feed_type.upper(),
            "wave": cfg.wave,
            "active": cfg.active,
            "status_dot": _STATUS_DOTS.get(color, "\u26ab"),
            "articles_24h": db.get("articles_last_24h", "-"),
            "articles_7d": db.get("articles_last_7d", "-"),
            "last_error": db.get("last_error", ""),
            "consecutive_failures": db.get("consecutive_failures", 0),
        })

    # Summary KPIs
    total = len(rows)
    active = sum(1 for r in rows if r["active"])
    errors = sum(1 for r in rows if r["consecutive_failures"] >= 3)

    cols = st.columns(4)
    cols[0].metric("Gesamt", total)
    cols[1].metric("Aktiv", active)
    cols[2].metric("Inaktiv", total - active)
    cols[3].metric("Fehler (3+)", errors)

    st.divider()

    # Feed table
    for row in rows:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([0.3, 2, 1.5, 0.8, 0.8])
            c1.markdown(row["status_dot"])
            c2.markdown(
                f"**{row['name']}**  \n"
                f"<span style='font-size:0.7rem;color:var(--c-text-muted)'>{row['url']}</span>",
                unsafe_allow_html=True,
            )
            c3.markdown(
                f"<span style='font-size:0.8rem'>{row['category']}</span>  \n"
                f"<span style='font-size:0.65rem;color:var(--c-text-muted)'>"
                f"{row['feed_type']} · Welle {row['wave']}</span>",
                unsafe_allow_html=True,
            )
            c4.markdown(
                f"<span style='font-size:0.8rem'>"
                f"24h: **{row['articles_24h']}** · 7d: **{row['articles_7d']}**"
                f"</span>",
                unsafe_allow_html=True,
            )
            if row["last_error"]:
                _err_escaped = html_mod.escape(row["last_error"][:200])
                _fail_count = row["consecutive_failures"]
                c5.markdown(
                    f"<span style='font-size:0.65rem;color:var(--c-danger)' title='{_err_escaped}'>"
                    f"Fehler ({_fail_count}x)</span>",
                    unsafe_allow_html=True,
                )
            elif not row["active"]:
                c5.markdown(
                    "<span style='font-size:0.7rem;color:var(--c-text-muted)'>Deaktiviert</span>",
                    unsafe_allow_html=True,
                )
            else:
                c5.markdown(
                    "<span style='font-size:0.7rem;color:var(--c-success)'>OK</span>",
                    unsafe_allow_html=True,
                )

    # Legend
    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.7rem;color:var(--c-text-muted)'>"
        f"{_STATUS_DOTS['green']} Letzter Fetch &lt;24h · "
        f"{_STATUS_DOTS['yellow']} 24–72h oder Fehler · "
        f"{_STATUS_DOTS['red']} &gt;72h oder 3+ Fehler · "
        f"{_STATUS_DOTS['gray']} Deaktiviert"
        "</div>",
        unsafe_allow_html=True,
    )

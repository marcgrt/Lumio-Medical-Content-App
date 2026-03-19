"""Lumio — Redaktionskalender tab: Kongresse, saisonale Themen, redaktionelle Planung."""

from datetime import date

import streamlit as st


_CATEGORY_ICONS = {
    "congress": "\U0001f3db",
    "seasonal": "\U0001f321",
    "guideline": "\U0001f4cb",
    "reminder": "\U0001f514",
}

_MONTH_NAMES_DE = {
    1: "Januar", 2: "Februar", 3: "M\u00e4rz", 4: "April",
    5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}


@st.cache_data(ttl=3600)
def _cached_upcoming_events(days_ahead: int = 30):
    """Cached wrapper for get_upcoming_events."""
    from src.processing.redaktionskalender import get_upcoming_events
    events = get_upcoming_events(days_ahead=days_ahead)
    return [
        {
            "date_start": e.date_start.isoformat(),
            "date_end": e.date_end.isoformat() if e.date_end else None,
            "title": e.title,
            "category": e.category,
            "specialty": e.specialty,
            "description_de": e.description_de,
            "prep_reminder_de": e.prep_reminder_de,
            "relevance_score": e.relevance_score,
            "related_article_count": e.related_article_count,
        }
        for e in events
    ]


@st.cache_data(ttl=3600)
def _cached_calendar(months_ahead: int = 3):
    """Cached wrapper for get_calendar."""
    from src.processing.redaktionskalender import get_calendar
    months = get_calendar(months_ahead=months_ahead)
    return [
        {
            "year": m.year,
            "month": m.month,
            "seasonal_topics": m.seasonal_topics,
            "events": [
                {
                    "date_start": e.date_start.isoformat(),
                    "date_end": e.date_end.isoformat() if e.date_end else None,
                    "title": e.title,
                    "category": e.category,
                    "specialty": e.specialty,
                    "description_de": e.description_de,
                    "prep_reminder_de": e.prep_reminder_de,
                    "relevance_score": e.relevance_score,
                    "related_article_count": e.related_article_count,
                }
                for e in m.events
            ],
        }
        for m in months
    ]


@st.cache_data(ttl=3600)
def _cached_seasonal_suggestions(month: int = 0):
    """Cached wrapper for get_seasonal_suggestions."""
    from src.processing.redaktionskalender import get_seasonal_suggestions
    return get_seasonal_suggestions(month=month)


def render_kalender():
    """Render the Redaktionskalender tab content."""
    from components.helpers import spec_pill

    st.markdown(
        '<div class="page-header">Redaktionskalender</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="page-sub">Kongresse, saisonale Themen und redaktionelle Planung</div>',
        unsafe_allow_html=True,
    )

    # ---- N\u00e4chste 30 Tage ----
    st.markdown(
        '<div class="section-header">N\u00e4chste 30 Tage</div>',
        unsafe_allow_html=True,
    )

    upcoming = _cached_upcoming_events(30)

    if not upcoming:
        st.info("Keine Ereignisse in den n\u00e4chsten 30 Tagen.")
    else:
        for ev in upcoming:
            icon = _CATEGORY_ICONS.get(ev["category"], "")
            stars = ev["relevance_score"] * "\u2605" + (5 - ev["relevance_score"]) * "\u2606"
            spec_html = spec_pill(ev["specialty"])
            date_str = ev["date_start"]
            if ev["date_end"] and ev["date_end"] != ev["date_start"]:
                date_str += f' \u2013 {ev["date_end"]}'

            article_badge = ""
            if ev["related_article_count"] > 0:
                article_badge = (
                    f'<span style="background:rgba(59,130,246,0.12);color:#3b82f6;'
                    f'padding:2px 8px;border-radius:8px;font-size:0.75rem;margin-left:8px">'
                    f'{ev["related_article_count"]} Artikel</span>'
                )

            st.markdown(
                f'<div style="border-left:3px solid {"#3b82f6" if ev["category"] == "congress" else "#f59e0b"};'
                f'padding:8px 12px;margin-bottom:8px;border-radius:0 6px 6px 0;'
                f'background:rgba(255,255,255,0.03)">'
                f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                f'<span style="font-size:0.75rem;color:#888">{date_str}</span>'
                f'{icon} <strong>{ev["title"]}</strong> {spec_html}{article_badge}'
                f'<span style="font-size:0.75rem;color:#d4a017">{stars}</span>'
                f'</div>'
                f'<div style="font-size:0.78rem;color:#999;margin-top:4px">'
                f'{ev["prep_reminder_de"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ---- Monats-\u00dcbersicht (next 3 months) ----
    st.markdown(
        '<div class="section-header">Monats-\u00dcbersicht</div>',
        unsafe_allow_html=True,
    )

    cal_months = _cached_calendar(3)

    for cm in cal_months:
        month_name = _MONTH_NAMES_DE.get(cm["month"], str(cm["month"]))
        label = f"{month_name} {cm['year']}"
        congress_count = sum(1 for e in cm["events"] if e["category"] == "congress")
        seasonal_count = len(cm["seasonal_topics"])

        with st.expander(f"{label} \u2014 {congress_count} Kongresse, {seasonal_count} saisonale Themen"):
            if cm["events"]:
                for ev in cm["events"]:
                    icon = _CATEGORY_ICONS.get(ev["category"], "")
                    spec_html = spec_pill(ev["specialty"])
                    article_info = ""
                    if ev["related_article_count"] > 0:
                        article_info = f" ({ev['related_article_count']} Artikel in DB)"

                    st.markdown(
                        f'{icon} **{ev["title"]}** {spec_html}'
                        f'<span style="font-size:0.78rem;color:#888">{article_info}</span>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<span style="color:#888;font-size:0.85rem">Keine Kongresse in diesem Monat</span>',
                    unsafe_allow_html=True,
                )

            if cm["seasonal_topics"]:
                tags_html = " ".join(
                    f'<span style="background:rgba(245,158,11,0.12);color:#f59e0b;'
                    f'padding:2px 10px;border-radius:12px;font-size:0.75rem;'
                    f'display:inline-block;margin:2px 4px 2px 0">{t}</span>'
                    for t in cm["seasonal_topics"]
                )
                st.markdown(
                    f'<div style="margin-top:8px">Saisonale Themen: {tags_html}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ---- Saisonale Themen \u2014 current month ----
    current_month = date.today().month
    month_name = _MONTH_NAMES_DE.get(current_month, str(current_month))

    st.markdown(
        f'<div class="section-header">Saisonale Themen \u2014 {month_name}</div>',
        unsafe_allow_html=True,
    )

    suggestions = _cached_seasonal_suggestions(current_month)

    if not suggestions:
        st.info("Keine saisonalen Themen f\u00fcr diesen Monat.")
    else:
        for sug in suggestions:
            count = sug["recent_article_count"]
            color = "#22c55e" if count > 5 else "#f59e0b" if count > 0 else "#888"

            st.markdown(
                f'<div style="border:1px solid var(--c-border);border-radius:10px;'
                f'padding:12px 16px;margin-bottom:8px;background:var(--c-surface);'
                f'display:flex;align-items:center;justify-content:space-between">'
                f'<div>'
                f'<div style="font-weight:600;font-size:0.85rem">{sug["topic"]}</div>'
                f'<div style="font-size:0.75rem;color:var(--c-text-muted);margin-top:2px">'
                f'{sug["suggestion_de"]}</div>'
                f'</div>'
                f'<span style="font-size:1.2rem;font-weight:700;color:{color};min-width:50px;'
                f'text-align:center">{count}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

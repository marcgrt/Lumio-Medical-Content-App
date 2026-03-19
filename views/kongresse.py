"""Lumio — Kongressplan Tab: Alle wichtigen Aerztekongresse auf einen Blick."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

_MONTH_NAMES_DE = {
    1: "Januar", 2: "Februar", 3: "Maerz", 4: "April",
    5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}

_SPEC_COLORS: dict[str, str] = {
    "Kardiologie": "#ef4444",
    "Onkologie": "#a855f7",
    "Neurologie": "#3b82f6",
    "Diabetologie/Endokrinologie": "#f59e0b",
    "Pneumologie": "#06b6d4",
    "Gastroenterologie": "#22c55e",
    "Rheumatologie": "#ec4899",
    "Allgemeinmedizin": "#84cc16",
    "Radiologie": "#6366f1",
    "Urologie": "#14b8a6",
    "Gynaekologie": "#f472b6",
    "Dermatologie": "#fb923c",
    "Paediatrie": "#38bdf8",
    "Chirurgie": "#64748b",
    "Infektiologie": "#facc15",
    "Psychiatrie": "#8b5cf6",
    "Health Economics": "#94a3b8",
}


def _spec_color(specialty: str) -> str:
    return _SPEC_COLORS.get(specialty, "#8b8ba0")


def _esc(s: str) -> str:
    """Escape HTML."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


@st.cache_data(ttl=3600)
def _cached_congresses():
    """Lade Kongresse (cached fuer 1h)."""
    from src.processing.kongresse import load_congresses
    congresses = load_congresses(with_articles=True)
    # Serialize for Streamlit cache
    return [
        {
            "id": c.id,
            "name": c.name,
            "short": c.short,
            "date_start": c.date_start.isoformat(),
            "date_end": c.date_end.isoformat(),
            "city": c.city,
            "country": c.country,
            "venue": c.venue,
            "website": c.website,
            "specialty": c.specialty,
            "congress_type": c.congress_type,
            "cme_points": c.cme_points,
            "estimated_attendees": c.estimated_attendees,
            "abstract_deadline": c.abstract_deadline.isoformat() if c.abstract_deadline else None,
            "registration_deadline": c.registration_deadline.isoformat() if c.registration_deadline else None,
            "description_de": c.description_de,
            "keywords": c.keywords,
            "related_article_count": c.related_article_count,
            "days_until": c.days_until,
            "duration_days": c.duration_days,
            "status": c.status,
            "month_key": c.month_key,
            "abstract_deadline_passed": c.abstract_deadline_passed,
            "days_until_abstract_deadline": c.days_until_abstract_deadline,
        }
        for c in congresses
    ]


def _render_hero_countdown(congress: dict):
    """Hero-Card fuer den naechsten Kongress."""
    if not congress:
        return

    days = congress["days_until"]
    status = congress["status"]
    sc = _spec_color(congress["specialty"])

    if status == "running":
        countdown_html = '<span style="color:#4ade80;font-size:2.4rem;font-weight:800">LIVE</span>'
        countdown_label = "Kongress laeuft gerade!"
    elif days == 0:
        countdown_html = '<span style="color:#fbbf24;font-size:2.4rem;font-weight:800">HEUTE</span>'
        countdown_label = "Startet heute!"
    elif days <= 7:
        countdown_html = f'<span style="color:#f59e0b;font-size:2.4rem;font-weight:800">{days}</span>'
        countdown_label = f"Tag{'e' if days != 1 else ''} bis zum Start"
    else:
        countdown_html = f'<span style="color:var(--c-text);font-size:2.4rem;font-weight:800">{days}</span>'
        countdown_label = "Tage bis zum Start"

    # Badges
    badges = []
    if congress["congress_type"] == "national":
        badges.append('<span class="kongress-badge kongress-badge-national">DE</span>')
    else:
        badges.append('<span class="kongress-badge kongress-badge-intl">INT</span>')

    if congress["cme_points"]:
        badges.append(f'<span class="kongress-badge kongress-badge-cme">{congress["cme_points"]} CME</span>')

    if congress["related_article_count"] > 0:
        badges.append(
            f'<span class="kongress-badge kongress-badge-articles">'
            f'{congress["related_article_count"]} Artikel</span>'
        )

    badges_html = " ".join(badges)

    # Abstract deadline warning
    deadline_html = ""
    dl = congress["days_until_abstract_deadline"]
    if dl is not None and dl > 0:
        if dl <= 14:
            deadline_html = (
                f'<div style="margin-top:10px;padding:6px 12px;background:rgba(248,113,113,0.12);'
                f'border-radius:8px;font-size:0.75rem;color:#f87171;display:inline-block">'
                f'Abstract-Deadline in {dl} Tagen!</div>'
            )
        elif dl <= 30:
            deadline_html = (
                f'<div style="margin-top:10px;padding:6px 12px;background:rgba(251,191,36,0.12);'
                f'border-radius:8px;font-size:0.75rem;color:#fbbf24;display:inline-block">'
                f'Abstract-Deadline in {dl} Tagen</div>'
            )

    name_esc = _esc(congress['name'])
    city_esc = _esc(congress['city'])
    country_esc = _esc(congress['country'])
    desc_esc = _esc(congress['description_de'])
    spec_esc = _esc(congress['specialty'])
    attendees = f"{congress['estimated_attendees']:,}"

    hero_html = (
        f'<div class="kongress-hero" style="--hero-accent:{sc}">'
        f'<div class="kongress-hero-accent" style="background:linear-gradient(90deg,{sc},{sc}88)"></div>'
        f'<div class="kongress-hero-body">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">'
        f'<div style="flex:1;min-width:200px">'
        f'<div style="font-size:0.65rem;font-weight:700;color:{sc};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">Naechster Kongress</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:var(--c-text);letter-spacing:-0.02em;line-height:1.3;margin-bottom:8px">{name_esc}</div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">'
        f'<span style="font-size:0.78rem;color:var(--c-text-secondary)">{congress["date_start"]} &mdash; {congress["date_end"]}</span>'
        f'<span style="color:var(--c-text-muted)">&bull;</span>'
        f'<span style="font-size:0.78rem;color:var(--c-text-secondary)">{city_esc}, {country_esc}</span>'
        f'</div>'
        f'<div style="font-size:0.78rem;color:var(--c-text-muted);margin-bottom:8px">{desc_esc}</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">'
        f'<span style="background:{sc}20;color:{sc};padding:2px 10px;border-radius:10px;font-size:0.68rem;font-weight:600">{spec_esc}</span>'
        f'{badges_html}'
        f'</div>'
        f'{deadline_html}'
        f'</div>'
        f'<div style="text-align:center;min-width:120px">'
        f'<div>{countdown_html}</div>'
        f'<div style="font-size:0.68rem;font-weight:600;color:var(--c-text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-top:4px">{countdown_label}</div>'
        f'<div style="margin-top:10px;font-size:0.72rem;color:var(--c-text-muted)">{congress["duration_days"]} Tage &bull; ~{attendees} Teiln.</div>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    st.markdown(hero_html, unsafe_allow_html=True)


def _render_timeline(congresses: list[dict]):
    """Mini-Timeline-Visualisierung (Monatsuebersicht)."""
    months_data: dict[int, list[dict]] = {}
    for c in congresses:
        if c["status"] == "past":
            continue
        m = int(c["date_start"].split("-")[1])
        months_data.setdefault(m, []).append(c)

    if not months_data:
        return

    st.markdown(
        '<div class="section-header">Jahres-Timeline 2026</div>',
        unsafe_allow_html=True,
    )

    cells = []
    for month_num in range(1, 13):
        name = _MONTH_NAMES_DE[month_num][:3]
        items = months_data.get(month_num, [])
        count = len(items)

        is_current = month_num == date.today().month and date.today().year == 2026
        bg = "rgba(132,204,22,0.12)" if is_current else "rgba(255,255,255,0.03)"
        border = "1px solid rgba(132,204,22,0.3)" if is_current else "1px solid var(--c-border)"

        # Color dots for specialties
        dots = ""
        for item in items[:4]:
            sc = _spec_color(item["specialty"])
            dots += f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{sc};margin:1px"></span>'
        if count > 4:
            dots += f'<span style="font-size:0.55rem;color:var(--c-text-muted)">+{count-4}</span>'

        cell = (
            f'<div style="text-align:center;padding:8px 4px;background:{bg};border:{border};'
            f'border-radius:8px;min-width:0">'
            f'<div style="font-size:0.65rem;font-weight:700;color:{"var(--c-accent)" if is_current else "var(--c-text-muted)"};'
            f'text-transform:uppercase;letter-spacing:0.04em">{name}</div>'
            f'<div style="font-size:1.1rem;font-weight:800;color:var(--c-text);margin:2px 0">{count}</div>'
            f'<div style="display:flex;gap:2px;justify-content:center;flex-wrap:wrap;min-height:10px">{dots}</div>'
            f'</div>'
        )
        cells.append(cell)

    grid_html = (
        '<div style="display:grid;grid-template-columns:repeat(12,1fr);gap:6px;margin-bottom:24px">'
        + "".join(cells)
        + '</div>'
    )
    st.markdown(grid_html, unsafe_allow_html=True)


def _render_congress_card(c: dict, expanded: bool = False):
    """Einzelne Kongress-Karte."""
    sc = _spec_color(c["specialty"])
    status = c["status"]

    # Status indicator
    if status == "running":
        status_html = '<span style="color:#4ade80;font-size:0.65rem;font-weight:700">● LIVE</span>'
    elif status == "past":
        status_html = '<span style="color:var(--c-text-muted);font-size:0.65rem">Vorbei</span>'
    else:
        days = c["days_until"]
        if days <= 7:
            status_html = f'<span style="color:#f59e0b;font-size:0.65rem;font-weight:600">In {days}d</span>'
        elif days <= 30:
            status_html = f'<span style="color:var(--c-text-secondary);font-size:0.65rem">{days}d</span>'
        else:
            status_html = f'<span style="color:var(--c-text-muted);font-size:0.65rem">{days}d</span>'

    # Badges
    badges = []
    if c["congress_type"] == "national":
        badges.append('<span class="kongress-badge kongress-badge-national">DE</span>')
    else:
        badges.append('<span class="kongress-badge kongress-badge-intl">INT</span>')

    if c["cme_points"]:
        badges.append(f'<span class="kongress-badge kongress-badge-cme">{c["cme_points"]} CME</span>')

    if c["related_article_count"] > 0:
        badges.append(
            f'<span class="kongress-badge kongress-badge-articles">'
            f'{c["related_article_count"]} Artikel</span>'
        )

    # Abstract deadline warning
    dl = c["days_until_abstract_deadline"]
    if dl is not None and 0 < dl <= 30:
        color = "#f87171" if dl <= 14 else "#fbbf24"
        badges.append(
            f'<span style="background:{color}18;color:{color};padding:2px 8px;'
            f'border-radius:10px;font-size:0.6rem;font-weight:600">'
            f'Deadline {dl}d</span>'
        )

    badges_html = " ".join(badges)

    opacity = "0.55" if status == "past" else "1"

    spec_esc = _esc(c['specialty'])
    short_esc = _esc(c['short'])
    full_name = c['name'].split(' — ')[-1] if ' — ' in c['name'] else c['name']
    full_esc = _esc(full_name)
    city_esc = _esc(c['city'])
    country_esc = _esc(c['country'])
    venue_part = (' &bull; ' + _esc(c['venue'])) if c['venue'] else ''
    attendees = f"{c['estimated_attendees']:,}"

    card_html = (
        f'<div class="kongress-card" style="--spec-color:{sc};opacity:{opacity}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        f'<div style="flex:1;min-width:0">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
        f'<span style="background:{sc}20;color:{sc};padding:2px 10px;border-radius:10px;font-size:0.62rem;font-weight:600;white-space:nowrap">{spec_esc}</span>'
        f'<span style="font-size:0.72rem;color:var(--c-text-muted)">{c["date_start"]} &mdash; {c["date_end"]}</span>'
        f'{status_html}'
        f'</div>'
        f'<div style="font-size:0.88rem;font-weight:700;color:var(--c-text);line-height:1.3;margin-bottom:4px">{short_esc} <span style="font-weight:400;color:var(--c-text-secondary);font-size:0.82rem">&mdash; {full_esc}</span></div>'
        f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-bottom:6px">{city_esc}, {country_esc}{venue_part} &bull; {c["duration_days"]}d &bull; ~{attendees} Teiln.</div>'
        f'<div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">{badges_html}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)


def _render_deadline_alerts(congresses: list[dict]):
    """Warnungen fuer bald ablaufende Deadlines."""
    deadlines = []
    for c in congresses:
        dl = c["days_until_abstract_deadline"]
        if dl is not None and 0 < dl <= 60:
            deadlines.append(c)
    deadlines.sort(key=lambda c: c["days_until_abstract_deadline"] or 999)

    if not deadlines:
        return

    st.markdown(
        '<div class="section-header">Abstract-Deadlines</div>'
        '<div class="section-sub">Bald ablaufende Einreichungsfristen</div>',
        unsafe_allow_html=True,
    )

    for c in deadlines[:6]:
        dl = c["days_until_abstract_deadline"]
        color = "#f87171" if dl <= 14 else "#fbbf24" if dl <= 30 else "var(--c-text-secondary)"
        bg = "rgba(248,113,113,0.06)" if dl <= 14 else "rgba(251,191,36,0.06)" if dl <= 30 else "rgba(255,255,255,0.03)"

        short_esc = _esc(c['short'])
        urgency = 'Dringend' if dl <= 14 else 'Bald' if dl <= 30 else f'{dl} Tage'
        dl_html = (
            f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
            f'background:{bg};border:1px solid var(--c-border);border-radius:10px;margin-bottom:6px">'
            f'<div style="font-size:1.3rem;font-weight:800;color:{color};min-width:40px;text-align:center">{dl}</div>'
            f'<div style="flex:1">'
            f'<div style="font-size:0.8rem;font-weight:600;color:var(--c-text)">{short_esc}</div>'
            f'<div style="font-size:0.68rem;color:var(--c-text-muted)">Abstract-Deadline: {c["abstract_deadline"]}</div>'
            f'</div>'
            f'<div style="font-size:0.65rem;font-weight:600;color:{color};text-transform:uppercase">{urgency}</div>'
            f'</div>'
        )
        st.markdown(dl_html, unsafe_allow_html=True)


def render_kongresse():
    """Render the Kongressplan tab."""
    st.markdown(
        '<div class="page-header">Kongressplan 2026</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="page-sub">Alle wichtigen Aerztekongresse auf einen Blick — Termine, CME, Deadlines</div>',
        unsafe_allow_html=True,
    )

    all_congresses = _cached_congresses()

    if not all_congresses:
        st.warning("Keine Kongressdaten geladen.")
        return

    # ---- Hero Countdown ----
    next_c = None
    for c in all_congresses:
        if c["status"] == "running":
            next_c = c
            break
        if c["status"] == "upcoming":
            next_c = c
            break

    _render_hero_countdown(next_c)

    # ---- KPI Bar ----
    total = len(all_congresses)
    upcoming_count = sum(1 for c in all_congresses if c["status"] in ("upcoming", "running"))
    national_count = sum(1 for c in all_congresses if c["congress_type"] == "national")
    intl_count = total - national_count
    total_cme = sum(c["cme_points"] or 0 for c in all_congresses if c["status"] != "past")

    st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0 20px 0">
            <div class="kpi-card" style="animation-delay:0s">
                <div class="kpi-value">{total}</div>
                <div class="kpi-label">Kongresse gesamt</div>
            </div>
            <div class="kpi-card" style="animation-delay:0.08s">
                <div class="kpi-value">{upcoming_count}</div>
                <div class="kpi-label">Ausstehend</div>
            </div>
            <div class="kpi-card" style="animation-delay:0.16s">
                <div class="kpi-value">{national_count} / {intl_count}</div>
                <div class="kpi-label">National / Int'l</div>
            </div>
            <div class="kpi-card" style="animation-delay:0.24s">
                <div class="kpi-value">{total_cme:,}</div>
                <div class="kpi-label">CME-Punkte verf.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- Timeline ----
    _render_timeline(all_congresses)

    # ---- Filters ----
    st.markdown(
        '<div class="section-divider"><span class="section-divider-label">Filter & Uebersicht</span></div>',
        unsafe_allow_html=True,
    )

    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])

    specs = sorted({c["specialty"] for c in all_congresses})
    countries = sorted({c["country"] for c in all_congresses})
    months = sorted({int(c["date_start"].split("-")[1]) for c in all_congresses})
    month_options = {m: _MONTH_NAMES_DE.get(m, str(m)) for m in months}

    with col_f1:
        sel_spec = st.multiselect(
            "Fachgebiet",
            options=specs,
            default=[],
            key="kongress_filter_spec",
        )
    with col_f2:
        sel_country = st.multiselect(
            "Land",
            options=countries,
            default=[],
            key="kongress_filter_country",
        )
    with col_f3:
        sel_months = st.multiselect(
            "Monat",
            options=list(month_options.keys()),
            format_func=lambda x: month_options[x],
            default=[],
            key="kongress_filter_month",
        )
    with col_f4:
        sel_type = st.selectbox(
            "Typ",
            options=["Alle", "National", "International"],
            key="kongress_filter_type",
        )

    # Apply filters
    filtered = all_congresses
    if sel_spec:
        filtered = [c for c in filtered if c["specialty"] in sel_spec]
    if sel_country:
        filtered = [c for c in filtered if c["country"] in sel_country]
    if sel_months:
        filtered = [c for c in filtered if int(c["date_start"].split("-")[1]) in sel_months]
    if sel_type == "National":
        filtered = [c for c in filtered if c["congress_type"] == "national"]
    elif sel_type == "International":
        filtered = [c for c in filtered if c["congress_type"] == "international"]

    # Show/hide past congresses
    show_past = st.checkbox("Vergangene Kongresse anzeigen", value=False, key="kongress_show_past")
    if not show_past:
        filtered = [c for c in filtered if c["status"] != "past"]

    st.markdown(
        f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-bottom:12px">'
        f'{len(filtered)} Kongresse gefunden</div>',
        unsafe_allow_html=True,
    )

    # ---- Abstract Deadline Warnings ----
    _render_deadline_alerts(filtered)

    # ---- Congress Cards ----
    # Group by month
    current_month = ""
    for c in filtered:
        mk = c["month_key"]
        if mk != current_month:
            current_month = mk
            m_num = int(mk.split("-")[1])
            m_name = _MONTH_NAMES_DE.get(m_num, mk)
            year = mk.split("-")[0]
            month_count = sum(1 for x in filtered if x["month_key"] == mk)
            st.markdown(
                f'<div class="section-divider">'
                f'<span class="section-divider-label">{m_name} {year} &mdash; {month_count} Kongresse</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        _render_congress_card(c)

        # Expander with details + website link
        with st.expander(f"Details: {c['short']}", expanded=False):
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                st.markdown(f"**Fachgebiet:** {c['specialty']}")
                st.markdown(f"**Ort:** {c['venue']}, {c['city']}, {c['country']}")
                st.markdown(f"**Dauer:** {c['duration_days']} Tage ({c['date_start']} bis {c['date_end']})")
                if c["cme_points"]:
                    st.markdown(f"**CME-Punkte:** {c['cme_points']}")
            with dcol2:
                st.markdown(f"**Teilnehmer:** ~{c['estimated_attendees']:,}")
                if c["abstract_deadline"]:
                    st.markdown(f"**Abstract-Deadline:** {c['abstract_deadline']}")
                if c["registration_deadline"]:
                    st.markdown(f"**Registrierung bis:** {c['registration_deadline']}")
                if c["related_article_count"] > 0:
                    st.markdown(f"**Verwandte Artikel in DB:** {c['related_article_count']}")
            st.markdown(f"_{c['description_de']}_")
            if c["website"]:
                st.markdown(f"[Website aufrufen]({c['website']})")

    # ---- .ics Export ----
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="section-divider"><span class="section-divider-label">Export</span></div>',
        unsafe_allow_html=True,
    )

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        # Generate ICS for filtered congresses
        from src.processing.kongresse import load_congresses, generate_ics_calendar
        if st.button("Kalender exportieren (.ics)", key="kongress_ics_export", type="primary"):
            congresses_obj = load_congresses(with_articles=False)
            # Filter to match current view
            filtered_ids = {c["id"] for c in filtered}
            export_list = [c for c in congresses_obj if c.id in filtered_ids]
            if export_list:
                ics_data = generate_ics_calendar(export_list)
                st.download_button(
                    label=f"Download {len(export_list)} Kongresse als .ics",
                    data=ics_data,
                    file_name="lumio_kongresse_2026.ics",
                    mime="text/calendar",
                    key="kongress_ics_download",
                )
            else:
                st.info("Keine Kongresse zum Exportieren.")

    with exp_col2:
        st.markdown(
            '<div style="font-size:0.75rem;color:var(--c-text-muted);padding-top:8px">'
            'Exportiert alle gefilterten Kongresse als .ics-Datei.<br>'
            'Importierbar in Apple Kalender, Google Calendar, Outlook.'
            '</div>',
            unsafe_allow_html=True,
        )

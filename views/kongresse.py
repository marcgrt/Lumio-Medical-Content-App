"""Lumio — Kongressplan Tab: Alle wichtigen Ärztekongresse auf einen Blick."""
from __future__ import annotations

import calendar
import json
from datetime import date, timedelta

import streamlit as st

_MONTH_NAMES_DE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April",
    5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}

_DAY_NAMES_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

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
    "Gynäkologie": "#f472b6",
    "Dermatologie": "#fb923c",
    "Pädiatrie": "#38bdf8",
    "Chirurgie": "#64748b",
    "Infektiologie": "#facc15",
    "Psychiatrie": "#8b5cf6",
    "Health Economics": "#94a3b8",
    "Orthopädie": "#78716c",
    "Anästhesiologie": "#e879f9",
    "Intensivmedizin": "#f43f5e",
    "Nephrologie": "#0ea5e9",
    "HNO": "#d946ef",
    "Augenheilkunde": "#2dd4bf",
    "Geriatrie": "#a3a3a3",
    "Ernährungsmedizin": "#65a30d",
    "Palliativmedizin": "#c084fc",
    "Allergologie": "#fbbf24",
    "Nuklearmedizin": "#818cf8",
    "Notfallmedizin": "#fb7185",
}


def _spec_color(specialty: str) -> str:
    return _SPEC_COLORS.get(specialty, "#8b8ba0")


from components.helpers import _esc


@st.cache_data(ttl=3600)
def _cached_congresses():
    """Lade Kongresse (cached für 1h)."""
    from src.processing.kongresse import load_congresses
    congresses = load_congresses(with_articles=True)
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


# ---------------------------------------------------------------------------
# Favoriten Helper
# ---------------------------------------------------------------------------

def _get_favorites() -> set[str]:
    """Lade Favoriten aus Session-State (mit DB-Sync)."""
    if "kongress_favorites" not in st.session_state:
        from src.processing.kongresse import get_favorite_ids
        st.session_state.kongress_favorites = get_favorite_ids()
    return st.session_state.kongress_favorites


def _toggle_fav(congress_id: str):
    """Toggle und sync mit DB."""
    from src.processing.kongresse import toggle_favorite
    is_fav = toggle_favorite(congress_id)
    favs = st.session_state.get("kongress_favorites", set())
    if is_fav:
        favs.add(congress_id)
    else:
        favs.discard(congress_id)
    st.session_state.kongress_favorites = favs


# ---------------------------------------------------------------------------
# Render: Hero Countdown
# ---------------------------------------------------------------------------

def _render_hero_countdown(congress: dict):
    """Hero-Card für den nächsten Kongress."""
    if not congress:
        return

    days = congress["days_until"]
    status = congress["status"]
    sc = _spec_color(congress["specialty"])

    if status == "running":
        countdown_html = '<span class="kongress-hero-countdown" style="color:#4ade80;font-size:2.4rem;font-weight:800">LIVE</span>'
        countdown_label = "Kongress läuft gerade!"
    elif days == 0:
        countdown_html = '<span class="kongress-hero-countdown" style="color:#fbbf24;font-size:2.4rem;font-weight:800">HEUTE</span>'
        countdown_label = "Startet heute!"
    elif days <= 7:
        countdown_html = f'<span class="kongress-hero-countdown" style="color:#f59e0b;font-size:2.4rem;font-weight:800">{days}</span>'
        countdown_label = f"Tag{'e' if days != 1 else ''} bis zum Start"
    else:
        countdown_html = f'<span class="kongress-hero-countdown" style="color:var(--c-text);font-size:2.4rem;font-weight:800">{days}</span>'
        countdown_label = "Tage bis zum Start"

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
        f'<div style="font-size:0.65rem;font-weight:700;color:{sc};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">Nächster Kongress</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:var(--c-text);letter-spacing:-0.02em;line-height:1.3;margin-bottom:8px">{name_esc}</div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">'
        f'<span style="font-size:0.78rem;color:var(--c-text-secondary)">{congress["date_start"]} &mdash; {congress["date_end"]}</span>'
        f'<span style="color:var(--c-text-muted)">&bull;</span>'
        f'<span style="font-size:0.78rem;color:var(--c-text-secondary)">{city_esc}, {country_esc}</span>'
        f'</div>'
        f'<div style="font-size:0.78rem;color:var(--c-text-muted);margin-bottom:8px">{desc_esc}</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">'
        f'<span class="kongress-spec-pill" style="background:{sc}20;color:{sc}">{spec_esc}</span>'
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


# ---------------------------------------------------------------------------
# Render: Timeline
# ---------------------------------------------------------------------------

def _render_timeline(congresses: list[dict]):
    """Mini-Timeline-Visualisierung (Monatsübersicht)."""
    months_data: dict[int, list[dict]] = {}
    for c in congresses:
        if c["status"] == "past":
            continue
        m = int(c["date_start"].split("-")[1])
        months_data.setdefault(m, []).append(c)

    if not months_data:
        return

    # Determine data year from congresses
    data_year = int(congresses[0]["date_start"].split("-")[0]) if congresses else date.today().year

    st.markdown(
        f'<div class="section-header">Jahres-Timeline {data_year}</div>',
        unsafe_allow_html=True,
    )

    cells = []
    for month_num in range(1, 13):
        name = _MONTH_NAMES_DE[month_num][:3]
        items = months_data.get(month_num, [])
        count = len(items)

        is_current = month_num == date.today().month and date.today().year == data_year
        bg = "var(--c-accent-light)" if is_current else "var(--c-surface)"
        border = "1px solid var(--c-accent)" if is_current else "1px solid var(--c-border)"

        dots = ""
        for item in items[:4]:
            sc = _spec_color(item["specialty"])
            dots += f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{sc};margin:1px"></span>'
        if count > 4:
            dots += f'<span style="font-size:0.55rem;color:var(--c-text-muted)">+{count-4}</span>'

        cell = (
            f'<div class="kongress-tl-cell" style="background:{bg};border:{border}">'
            f'<div style="font-size:0.65rem;font-weight:700;color:{"var(--c-accent)" if is_current else "var(--c-text-muted)"};'
            f'text-transform:uppercase;letter-spacing:0.04em">{name}</div>'
            f'<div class="kongress-tl-count">{count}</div>'
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


# ---------------------------------------------------------------------------
# Feature 2: Überlappungs-Warnung
# ---------------------------------------------------------------------------

def _render_overlap_warnings(congresses: list[dict]):
    """Zeige Warnungen für überlappende Kongresse — kompakt hinter Icon."""
    # Build overlap pairs from dict data
    upcoming = [c for c in congresses if c["status"] != "past"]
    overlaps = []
    for i, a in enumerate(upcoming):
        for b in upcoming[i + 1:]:
            a_start = date.fromisoformat(a["date_start"])
            a_end = date.fromisoformat(a["date_end"])
            b_start = date.fromisoformat(b["date_start"])
            b_end = date.fromisoformat(b["date_end"])
            if a_start <= b_end and b_start <= a_end:
                overlaps.append((a, b))

    if not overlaps:
        return

    # Build overlap row helper
    def _overlap_row(a, b):
        sc_a = _spec_color(a["specialty"])
        sc_b = _spec_color(b["specialty"])
        return (
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;'
            f'padding:6px 0;border-bottom:1px solid var(--c-border-subtle)">'
            f'<span style="font-size:0.78rem;font-weight:600;color:{sc_a}">{_esc(a["short"])}</span>'
            f'<span style="font-size:0.68rem;color:var(--c-text-muted)">{a["date_start"]} — {a["date_end"]}</span>'
            f'<span style="color:var(--c-text-muted);font-size:0.68rem">×</span>'
            f'<span style="font-size:0.78rem;font-weight:600;color:{sc_b}">{_esc(b["short"])}</span>'
            f'<span style="font-size:0.68rem;color:var(--c-text-muted)">{b["date_start"]} — {b["date_end"]}</span>'
            f'</div>'
        )

    # First 8 always visible
    rows_html = "".join(_overlap_row(a, b) for a, b in overlaps[:8])

    # Remaining ones inside a nested <details>
    rest = len(overlaps) - 8
    if rest > 0:
        extra_rows = "".join(_overlap_row(a, b) for a, b in overlaps[8:])
        rows_html += (
            f'<details class="overlap-more" style="margin-top:6px">'
            f'<summary style="'
            f'display:inline-flex;align-items:center;gap:5px;'
            f'cursor:pointer;list-style:none;'
            f'font-size:0.70rem;font-weight:600;color:#eab308;'
            f'padding:4px 10px;border-radius:6px;'
            f'background:rgba(234,179,8,0.06);'
            f'border:1px solid rgba(234,179,8,0.12);'
            f'transition:background 0.2s ease;user-select:none;'
            f'">'
            f'+{rest} weitere'
            f'<svg class="more-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none"'
            f' stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"'
            f' style="transition:transform 0.25s ease"><polyline points="6 9 12 15 18 9"/></svg>'
            f'</summary>'
            f'<div style="margin-top:4px">{extra_rows}</div>'
            f'</details>'
        )

    n = len(overlaps)
    label = f'{n} Terminüberschneidung{"en" if n != 1 else ""}'

    # Compact collapsible badge — click to expand
    st.markdown(f"""
        <details style="margin:10px 0 4px 0">
            <summary style="
                display:inline-flex;align-items:center;gap:6px;
                cursor:pointer;list-style:none;
                background:rgba(234,179,8,0.08);
                border:1px solid rgba(234,179,8,0.18);
                border-radius:8px;padding:6px 14px;
                font-size:0.76rem;font-weight:600;color:#eab308;
                transition:background 0.2s ease,border-color 0.2s ease;
                user-select:none;
            ">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                     stroke="#eab308" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                {label}
                <svg class="overlap-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
                     style="transition:transform 0.25s ease">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </summary>
            <div style="
                margin-top:8px;padding:10px 14px;
                background:rgba(234,179,8,0.04);
                border:1px solid rgba(234,179,8,0.10);
                border-radius:8px;
            ">
                {rows_html}
            </div>
        </details>
        <style>
            details[open] > summary .overlap-chevron {{ transform: rotate(180deg); }}
            details.overlap-more[open] > summary .more-chevron {{ transform: rotate(180deg); }}
            details summary::-webkit-details-marker {{ display: none; }}
            details summary::marker {{ display: none; content: ''; }}
            details summary:hover {{
                background: rgba(234,179,8,0.13) !important;
                border-color: rgba(234,179,8,0.28) !important;
            }}
        </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Feature 4: Monatskalender-Ansicht
# ---------------------------------------------------------------------------

def _render_month_calendar(congresses: list[dict], year: int, month: int):
    """Render einen Monat als Mo–So Grid mit Kongress-Balken."""
    cal = calendar.monthcalendar(year, month)
    m_name = _MONTH_NAMES_DE.get(month, str(month))

    # Find congresses overlapping this month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    month_congresses = []
    for c in congresses:
        cs = date.fromisoformat(c["date_start"])
        ce = date.fromisoformat(c["date_end"])
        if cs <= month_end and ce >= month_start:
            month_congresses.append(c)

    today = date.today()

    # Header
    header_cells = "".join(
        f'<div class="kongress-cal-header">{d}</div>' for d in _DAY_NAMES_DE
    )

    # Day cells
    day_cells = ""
    for week in cal:
        for day_num in week:
            if day_num == 0:
                day_cells += '<div class="kongress-cal-day empty"></div>'
                continue

            current = date(year, month, day_num)
            is_today = current == today
            today_cls = " today" if is_today else ""

            # Congress bars for this day
            bars = ""
            for c in month_congresses:
                cs = date.fromisoformat(c["date_start"])
                ce = date.fromisoformat(c["date_end"])
                if cs <= current <= ce:
                    sc = _spec_color(c["specialty"])
                    bars += (
                        f'<span class="kongress-cal-bar" style="background:{sc}" '
                        f'title="{_esc(c["short"])}: {c["date_start"]} — {c["date_end"]}"></span>'
                    )

            day_cells += (
                f'<div class="kongress-cal-day{today_cls}">'
                f'<div class="kongress-cal-day-num">{day_num}</div>'
                f'{bars}'
                f'</div>'
            )

    return (
        f'<div style="margin-bottom:16px">'
        f'<div style="font-size:0.82rem;font-weight:700;color:var(--c-text);margin-bottom:6px">'
        f'{m_name} {year}'
        f'<span style="font-size:0.68rem;font-weight:400;color:var(--c-text-muted);margin-left:8px">'
        f'{len(month_congresses)} Kongresse</span>'
        f'</div>'
        f'<div class="kongress-cal-grid">'
        f'{header_cells}'
        f'{day_cells}'
        f'</div>'
        f'</div>'
    )


def _render_calendar_view(congresses: list[dict]):
    """Render die komplette Kalender-Ansicht (3 Monate)."""
    today = date.today()
    # Show current month + next 2
    months_to_show = []
    for offset in range(3):
        m = today.month + offset
        y = today.year
        if m > 12:
            m -= 12
            y += 1
        months_to_show.append((y, m))

    cols = st.columns(3)
    for idx, (y, m) in enumerate(months_to_show):
        with cols[idx]:
            cal_html = _render_month_calendar(congresses, y, m)
            st.markdown(cal_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Feature 1: Meine Kongresse (Favoriten)
# ---------------------------------------------------------------------------

def _render_favorites_section(congresses: list[dict], favorites: set[str]):
    """Render 'Meine Kongresse' Favoriten-Sektion."""
    fav_congresses = [c for c in congresses if c["id"] in favorites and c["status"] != "past"]
    if not fav_congresses:
        return

    st.markdown(
        '<div class="section-header">⭐ Meine Kongresse</div>'
        f'<div class="section-sub">{len(fav_congresses)} favorisierte Kongresse</div>',
        unsafe_allow_html=True,
    )

    fav_html_parts = []
    for c in fav_congresses[:6]:
        sc = _spec_color(c["specialty"])
        days = c["days_until"]
        if c["status"] == "running":
            day_label = '<span style="color:#4ade80;font-weight:700">LIVE</span>'
        elif days <= 7:
            day_label = f'<span style="color:#f59e0b;font-weight:700">{days}d</span>'
        else:
            day_label = f'<span style="color:var(--c-text-muted)">{days}d</span>'

        fav_html_parts.append(
            f'<div class="kongress-fav-card" style="border-left:3px solid {sc}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<div style="font-size:0.78rem;font-weight:700;color:var(--c-text)">{_esc(c["short"])}</div>'
            f'<div style="font-size:0.65rem;color:var(--c-text-muted)">{c["date_start"]} · {_esc(c["city"])}</div>'
            f'</div>'
            f'<div class="kongress-fav-days" style="text-align:right">{day_label}</div>'
            f'</div>'
            f'</div>'
        )

    grid_html = (
        '<div class="kongress-favs-section">'
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px">'
        + "".join(fav_html_parts)
        + '</div></div>'
    )
    st.markdown(grid_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Render: Congress Card (with features)
# ---------------------------------------------------------------------------

def _render_congress_card(c: dict, is_fav: bool = False):
    """Einzelne Kongress-Karte."""
    sc = _spec_color(c["specialty"])
    status = c["status"]

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

    # Favorit-Stern
    star = "⭐" if is_fav else "☆"
    star_style = "opacity:1;filter:none" if is_fav else "opacity:0.3;filter:grayscale(100%)"

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
        f'<span class="kongress-spec-pill" style="background:{sc}20;color:{sc}">{spec_esc}</span>'
        f'<span style="font-size:0.72rem;color:var(--c-text-muted)">{c["date_start"]} &mdash; {c["date_end"]}</span>'
        f'{status_html}'
        f'</div>'
        f'<div style="font-size:0.88rem;font-weight:700;color:var(--c-text);line-height:1.3;margin-bottom:4px">'
        f'<span style="{star_style};margin-right:4px;font-size:0.78rem">{star}</span>'
        f'{short_esc} <span style="font-weight:400;color:var(--c-text-secondary);font-size:0.82rem">&mdash; {full_esc}</span></div>'
        f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-bottom:6px">{city_esc}, {country_esc}{venue_part} &bull; {c["duration_days"]}d &bull; ~{attendees} Teiln.</div>'
        f'<div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">{badges_html}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Render: Deadline Alerts
# ---------------------------------------------------------------------------

def _render_deadline_alerts(congresses: list[dict]):
    """Warnungen für bald ablaufende Deadlines."""
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
        bg = "rgba(248,113,113,0.06)" if dl <= 14 else "rgba(251,191,36,0.06)" if dl <= 30 else "var(--c-surface)"

        short_esc = _esc(c['short'])
        urgency = 'Dringend' if dl <= 14 else 'Bald' if dl <= 30 else f'{dl} Tage'
        dl_html = (
            f'<div class="kongress-deadline-item" style="background:{bg}">'
            f'<div class="kongress-deadline-num" style="color:{color}">{dl}</div>'
            f'<div style="flex:1">'
            f'<div style="font-size:0.8rem;font-weight:600;color:var(--c-text)">{short_esc}</div>'
            f'<div style="font-size:0.68rem;color:var(--c-text-muted)">Abstract-Deadline: {c["abstract_deadline"]}</div>'
            f'</div>'
            f'<div style="font-size:0.65rem;font-weight:600;color:{color};text-transform:uppercase">{urgency}</div>'
            f'</div>'
        )
        st.markdown(dl_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Interactive World Map
# ---------------------------------------------------------------------------

def _render_map_view(congresses: list[dict], favorites: set[str]):
    """Render interactive Leaflet world map with congress pins — premium edition."""
    from src.processing.kongresse import _CITY_COORDS

    # Build GeoJSON directly from dict data
    features = []
    for c in congresses:
        coords = _CITY_COORDS.get((c["city"], c["country"]))
        if not coords:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [coords[1], coords[0]]},
            "properties": {
                "id": c["id"], "name": c["name"], "short": c["short"],
                "city": c["city"], "country": c["country"],
                "specialty": c["specialty"],
                "date_start": c["date_start"], "date_end": c["date_end"],
                "status": c["status"],
                "cme": c.get("cme_points") or 0,
                "attendees": c.get("estimated_attendees", 0),
                "articles": c.get("related_article_count", 0),
                "website": c.get("website", ""),
                "is_fav": c["id"] in favorites,
                "congress_type": c.get("congress_type", "national"),
            },
        })
    geojson = json.dumps({"type": "FeatureCollection", "features": features})
    spec_colors_json = json.dumps(_SPEC_COLORS)

    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      body {{ background: transparent; font-family: 'Inter', -apple-system, sans-serif; }}

      /* --- Accessibility: reduced motion --- */
      @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.01ms !important;
        }}
      }}

      /* --- Map container with fade-in --- */
      .map-wrap {{ position: relative; border-radius: 14px; overflow: hidden; }}
      #map {{
        width: 100%; height: 520px;
        border-radius: 14px; border: 1px solid var(--c-border);
        opacity: 0; transition: opacity 0.8s ease;
      }}
      #map.loaded {{ opacity: 1; }}

      /* --- Vignette + aurora overlay --- */
      .map-overlay {{
        position: absolute; inset: 0; z-index: 800;
        pointer-events: none; border-radius: 14px;
        box-shadow: inset 0 0 80px 20px rgba(10,10,26,0.55);
      }}
      .map-overlay::before {{
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 80px;
        background: linear-gradient(180deg,
          rgba(132,204,22,0.03) 0%, rgba(59,130,246,0.02) 50%, transparent 100%);
        border-radius: 14px 14px 0 0;
      }}
      .map-overlay::after {{
        content: ''; position: absolute; inset: 0;
        background-image:
          linear-gradient(var(--c-border-subtle) 1px, transparent 1px),
          linear-gradient(90deg, var(--c-border-subtle) 1px, transparent 1px);
        background-size: 60px 60px; border-radius: 14px; opacity: 0.4;
      }}

      /* --- Dark Leaflet overrides --- */
      .leaflet-container {{ background: var(--c-bg); }}
      .leaflet-control-zoom a {{
        background: var(--c-border) !important;
        color: var(--c-text) !important;
        border-color: var(--c-border) !important;
        backdrop-filter: blur(12px);
      }}
      .leaflet-control-zoom a:hover {{ background: rgba(132,204,22,0.15) !important; }}
      .leaflet-control-attribution {{ display: none; }}

      /* --- Custom info panel (replaces Leaflet popup) --- */
      .info-panel {{
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%) scale(0.92);
        z-index: 1100; max-width: 360px; min-width: 260px; width: 90%;
        background: linear-gradient(135deg,
          rgba(20,20,40,0.95) 0%, rgba(15,15,30,0.98) 100%);
        backdrop-filter: blur(20px) saturate(1.4);
        -webkit-backdrop-filter: blur(20px) saturate(1.4);
        border: 1px solid var(--c-border-hover);
        border-radius: 16px;
        box-shadow: 0 12px 48px rgba(0,0,0,0.6), 0 0 0 1px var(--c-border-subtle);
        color: var(--c-text); opacity: 0;
        pointer-events: none;
        transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.34,1.56,0.64,1);
      }}
      .info-panel.visible {{
        opacity: 1; pointer-events: auto;
        transform: translate(-50%, -50%) scale(1);
      }}
      .info-panel-close {{
        position: absolute; top: 10px; right: 12px;
        background: none; border: none; color: var(--c-text-muted);
        font-size: 18px; cursor: pointer; padding: 4px 8px;
        border-radius: 6px; transition: color 0.2s, background 0.2s;
        z-index: 2; line-height: 1;
      }}
      .info-panel-close:hover {{ color: var(--c-text); background: var(--c-border); }}
      /* Hide Leaflet default popups entirely */
      .leaflet-popup {{ display: none !important; }}

      /* --- Popup content --- */
      .pop {{ padding: 14px 16px; }}
      .pop-top {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
      .pop-spec {{
        font-size: 0.65rem; font-weight: 600; padding: 2px 8px;
        border-radius: 6px; white-space: nowrap;
      }}
      .pop-status {{
        font-size: 0.62rem; font-weight: 700; padding: 2px 6px;
        border-radius: 4px; text-transform: uppercase;
      }}
      .pop-status.live {{ background: rgba(239,68,68,0.20); color: #f87171; }}
      .pop-status.upcoming {{ background: rgba(132,204,22,0.15); color: #a3e635; }}
      .pop-status.past {{ background: rgba(107,107,130,0.20); color: var(--c-text-muted); }}
      .pop-name {{
        font-size: 0.88rem; font-weight: 700; color: var(--c-text);
        line-height: 1.3; margin-bottom: 4px;
      }}
      .pop-meta {{ font-size: 0.72rem; color: var(--c-text-secondary); margin-bottom: 10px; }}
      .pop-badges {{
        display: flex; gap: 6px; flex-wrap: wrap;
        font-size: 0.65rem; color: var(--c-text-tertiary);
      }}
      .pop-badges span {{
        background: var(--c-border-subtle); padding: 2px 7px;
        border-radius: 5px;
        transition: background 0.2s ease, transform 0.2s ease;
        cursor: default;
      }}
      .pop-badges span:hover {{
        background: var(--c-border); transform: translateY(-1px);
      }}
      .pop-link {{
        display: block; margin-top: 10px; text-align: center;
        font-size: 0.72rem; font-weight: 600; color: #84cc16;
        text-decoration: none; padding: 6px;
        border-top: 1px solid var(--c-border);
        transition: color 0.2s ease;
      }}
      .pop-link:hover {{ color: #a3e635; }}

      /* --- Progress bar in popup --- */
      .pop-progress {{
        height: 3px; background: var(--c-border);
        border-radius: 2px; margin: 10px 0 4px; overflow: hidden;
      }}
      .pop-progress-bar {{
        height: 100%; border-radius: 2px;
        transition: width 0.8s cubic-bezier(0.4,0,0.2,1);
      }}
      .pop-progress-label, .pop-countdown {{
        font-size: 0.62rem; color: var(--c-text-tertiary); margin-bottom: 2px;
      }}

      /* --- DivIcon marker system --- */
      .lumio-marker-icon {{
        background: transparent !important;
        border: none !important;
        cursor: pointer !important;
      }}
      .lumio-pin {{
        position: relative;
        display: flex; align-items: center; justify-content: center;
      }}
      .pin-core {{
        width: 14px; height: 14px; border-radius: 50%;
        background: var(--color);
        border: 2px solid var(--c-border-hover);
        transition: transform 0.25s cubic-bezier(0.34,1.56,0.64,1),
                    box-shadow 0.25s ease;
        will-change: transform, box-shadow;
        position: relative; z-index: 2;
      }}
      .lumio-pin.live .pin-core {{
        animation: pulse-live 2s ease-in-out infinite;
        border-color: var(--c-border-hover);
      }}
      .lumio-pin.upcoming .pin-core {{
        animation: breathe 3s ease-in-out infinite;
      }}
      .lumio-pin.past .pin-core {{ opacity: 0.35; }}
      .lumio-pin.fav .pin-core {{
        border-color: #fbbf24; border-width: 2.5px;
      }}

      /* Gold orbital ring for favorites */
      .pin-orbit {{
        position: absolute; inset: -5px;
        border: 1.5px dashed rgba(251,191,36,0.45);
        border-radius: 50%;
        animation: orbit 8s linear infinite;
        z-index: 1;
      }}

      /* Hover: scale + glow */
      .lumio-pin:hover .pin-core {{
        transform: scale(1.6);
        box-shadow: 0 0 20px 6px var(--glow);
      }}
      .lumio-pin:hover .pin-orbit {{ animation-play-state: paused; }}

      /* --- Marker keyframes --- */
      @keyframes pulse-live {{
        0%   {{ box-shadow: 0 0 4px 2px var(--glow); transform: scale(1); }}
        50%  {{ box-shadow: 0 0 18px 8px var(--glow); transform: scale(1.18); }}
        100% {{ box-shadow: 0 0 4px 2px var(--glow); transform: scale(1); }}
      }}
      @keyframes breathe {{
        0%, 100% {{ box-shadow: 0 0 3px 1px var(--glow); opacity: 0.85; }}
        50%      {{ box-shadow: 0 0 10px 4px var(--glow); opacity: 1; }}
      }}
      @keyframes orbit {{
        from {{ transform: rotate(0deg); }}
        to   {{ transform: rotate(360deg); }}
      }}
      @keyframes marker-appear {{
        from {{ opacity: 0; transform: scale(0.3); }}
        to   {{ opacity: 1; transform: scale(1); }}
      }}

      /* --- Cluster donut ring --- */
      .cluster-ring {{
        width: 42px; height: 42px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1);
        box-shadow: 0 0 12px rgba(0,0,0,0.3);
      }}
      .cluster-ring:hover {{ transform: scale(1.18); }}
      .cluster-inner {{
        width: 28px; height: 28px; border-radius: 50%;
        background: rgba(10,10,26,0.88);
        backdrop-filter: blur(8px);
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 11px; color: var(--c-text);
        border: 1px solid var(--c-border);
      }}

      /* --- Interactive legend --- */
      .legend {{
        position: absolute; bottom: 14px; right: 14px; z-index: 1000;
        background: linear-gradient(135deg,
          rgba(20,20,40,0.90) 0%, rgba(15,15,30,0.95) 100%);
        backdrop-filter: blur(12px); border: 1px solid var(--c-border);
        border-radius: 10px; padding: 10px 14px;
        font-size: 0.68rem; color: var(--c-text-secondary); max-width: 200px;
        user-select: none;
      }}
      .legend-title {{
        font-weight: 700; color: var(--c-text); margin-bottom: 6px;
        font-size: 0.72rem; display: flex; align-items: center; gap: 5px;
      }}
      .legend-item {{
        display: flex; align-items: center; gap: 6px; padding: 3px 4px;
        border-radius: 6px; cursor: pointer;
        border-left: 3px solid transparent;
        transition: all 0.25s ease;
      }}
      .legend-item:hover {{ background: var(--c-border-subtle); }}
      .legend-item.active {{ border-left-color: var(--lc); background: var(--c-surface); }}
      .legend-item.dimmed {{ opacity: 0.3; }}
      .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
      .legend-count {{ color: var(--c-text-muted); font-size: 0.62rem; margin-top: 8px; }}
      .legend-reset {{
        display: none; margin-top: 6px; padding: 4px 8px;
        background: rgba(132,204,22,0.12); border: 1px solid rgba(132,204,22,0.25);
        border-radius: 6px; color: #a3e635; font-size: 0.6rem;
        cursor: pointer; text-align: center; transition: all 0.2s ease;
      }}
      .legend-reset:hover {{ background: rgba(132,204,22,0.20); }}
      .legend-reset.visible {{ display: block; }}

      /* --- Timeline slider --- */
      .timeline-bar {{
        position: absolute; bottom: 14px; left: 14px; right: 220px;
        z-index: 1000; padding: 8px 14px 4px;
        background: linear-gradient(135deg,
          rgba(20,20,40,0.88) 0%, rgba(15,15,30,0.92) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid var(--c-border);
        border-radius: 10px;
      }}
      .timeline-bar input[type=range] {{
        width: 100%; height: 3px;
        -webkit-appearance: none; appearance: none;
        background: var(--c-border);
        border-radius: 2px; outline: none;
      }}
      .timeline-bar input[type=range]::-webkit-slider-thumb {{
        -webkit-appearance: none; appearance: none;
        width: 14px; height: 14px; border-radius: 50%;
        background: #84cc16; cursor: pointer;
        box-shadow: 0 0 8px rgba(132,204,22,0.4);
        transition: box-shadow 0.2s ease;
      }}
      .timeline-bar input[type=range]::-webkit-slider-thumb:hover {{
        box-shadow: 0 0 14px rgba(132,204,22,0.6);
      }}
      .timeline-labels {{
        display: flex; justify-content: space-between;
        font-size: 0.52rem; color: var(--c-text-muted); margin-top: 2px;
        pointer-events: none;
      }}
      .timeline-month {{ transition: color 0.2s ease; }}
      .timeline-month.active {{ color: #84cc16; font-weight: 600; }}

      /* --- Tooltip --- */
      .dark-tooltip {{
        background: rgba(20,20,40,0.90) !important;
        color: var(--c-text) !important;
        border: 1px solid var(--c-border) !important;
        border-radius: 8px !important; font-size: 0.72rem !important;
        padding: 4px 10px !important; font-family: Inter,sans-serif !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important;
      }}
      .dark-tooltip::before {{ border-top-color: rgba(20,20,40,0.90) !important; }}
    </style>
    </head>
    <body>
    <div class="map-wrap">
      <div id="map"></div>
      <div class="map-overlay"></div>
      <div id="info-panel" class="info-panel">
        <button class="info-panel-close" id="info-close">&times;</button>
        <div id="info-content"></div>
      </div>
    </div>
    <script>
    (function() {{
      var data = {geojson};
      var specColors = {spec_colors_json};
      var defaultColor = '#8b8ba0';
      var months = ['Jan','Feb','Mar','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];

      // --- Map init (start zoomed out for fly-in) ---
      var map = L.map('map', {{
        center: [30, 10],
        zoom: 2,
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: true,
      }});

      var tileLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        maxZoom: 18, subdomains: 'abcd'
      }}).addTo(map);

      // Fade-in on tile load
      tileLayer.on('load', function() {{
        document.getElementById('map').classList.add('loaded');
      }});
      setTimeout(function() {{
        document.getElementById('map').classList.add('loaded');
      }}, 500);

      // --- Info panel close logic ---
      function closeInfoPanel() {{
        document.getElementById('info-panel').classList.remove('visible');
      }}
      document.getElementById('info-close').addEventListener('click', function(e) {{
        e.stopPropagation();
        closeInfoPanel();
      }});
      map.on('click', closeInfoPanel);

      // --- Cluster group with donut ring ---
      var markers = L.markerClusterGroup({{
        maxClusterRadius: 28,
        spiderfyOnMaxZoom: true,
        spiderfyDistanceMultiplier: 2.0,
        showCoverageOnHover: false,
        disableClusteringAtZoom: 8,
        animate: true,
        iconCreateFunction: function(cluster) {{
          var children = cluster.getAllChildMarkers();
          var colorCounts = {{}};
          children.forEach(function(m) {{
            var c = m.options._specColor || defaultColor;
            colorCounts[c] = (colorCounts[c] || 0) + 1;
          }});
          var sorted = Object.entries(colorCounts).sort(function(a,b) {{ return b[1]-a[1]; }});
          var total = children.length;

          // Build conic-gradient stops
          var stops = []; var cumul = 0;
          sorted.forEach(function(entry) {{
            var start = (cumul / total) * 360;
            cumul += entry[1];
            var end = (cumul / total) * 360;
            stops.push(entry[0] + ' ' + start.toFixed(1) + 'deg ' + end.toFixed(1) + 'deg');
          }});
          var gradient = 'conic-gradient(' + stops.join(', ') + ')';

          return L.divIcon({{
            html: '<div class="cluster-ring" style="background:' + gradient + '">'
              + '<div class="cluster-inner">' + total + '</div></div>',
            className: '', iconSize: [42, 42], iconAnchor: [21, 21]
          }});
        }}
      }});

      var statusLabels = {{ running: 'LIVE', upcoming: 'Bevorstehend', past: 'Vorbei' }};
      var statusClasses = {{ running: 'live', upcoming: 'upcoming', past: 'past' }};

      // Specialty counts for legend
      var specCounts = {{}};
      // All markers for filtering
      var allMarkers = [];
      var markerSpecMap = [];

      data.features.forEach(function(f, idx) {{
        var p = f.properties;
        var coords = f.geometry.coordinates;
        var color = specColors[p.specialty] || defaultColor;

        specCounts[p.specialty] = (specCounts[p.specialty] || 0) + 1;

        // Size by status
        var sz = p.status === 'running' ? 22 : (p.status === 'past' ? 16 : 18);
        var statusClass = statusClasses[p.status] || 'upcoming';

        // Build DivIcon HTML
        var pinHtml = '<div class="lumio-pin ' + statusClass + (p.is_fav ? ' fav' : '') + '"'
          + ' style="--color:' + color + ';--glow:' + color + '55">'
          + '<div class="pin-core"></div>'
          + (p.is_fav ? '<div class="pin-orbit"></div>' : '')
          + '</div>';

        var icon = L.divIcon({{
          html: pinHtml,
          className: 'lumio-marker-icon',
          iconSize: [sz, sz],
          iconAnchor: [sz/2, sz/2]
        }});

        var marker = L.marker([coords[1], coords[0]], {{
          icon: icon,
          interactive: true,
          bubblingMouseEvents: false,
          _specColor: color,
          _specialty: p.specialty,
          _status: p.status,
          _dateStart: p.date_start,
          _dateEnd: p.date_end
        }});

        // Tooltip on hover
        marker.bindTooltip(p.short + ' — ' + p.city, {{
          className: 'dark-tooltip',
          direction: 'top', offset: [0, -12]
        }});

        // Popup content
        var ds = new Date(p.date_start);
        var de = new Date(p.date_end);
        var fmt = function(d) {{ return d.getDate() + '.' + (d.getMonth()+1) + '.' + d.getFullYear(); }};
        var dateStr = fmt(ds) + ' – ' + fmt(de);

        // Status badge (SVG dot instead of emoji for LIVE)
        var liveDot = p.status === 'running'
          ? '<svg width="6" height="6" style="margin-right:2px;vertical-align:middle"><circle cx="3" cy="3" r="3" fill="#f87171"/></svg> '
          : '';
        var statusHtml = '<span class="pop-status ' + statusClasses[p.status] + '">'
          + liveDot + statusLabels[p.status] + '</span>';

        // Badges (no emojis — CSS icons)
        var badges = '';
        if (p.congress_type === 'international') badges += '<span>Intl.</span>';
        else badges += '<span>National</span>';
        if (p.cme > 0) badges += '<span>' + p.cme + ' CME</span>';
        if (p.attendees > 0) badges += '<span>' + (p.attendees >= 1000 ? Math.round(p.attendees/1000) + 'k' : p.attendees) + ' Teiln.</span>';
        if (p.articles > 0) badges += '<span>' + p.articles + ' Artikel</span>';

        // Progress bar / countdown
        var progressHtml = '';
        var now = Date.now();
        if (p.status === 'running') {{
          var pct = Math.min(100, Math.max(0, ((now - ds.getTime()) / (de.getTime() - ds.getTime())) * 100));
          progressHtml = '<div class="pop-progress">'
            + '<div class="pop-progress-bar" style="width:' + pct.toFixed(1) + '%;background:' + color + '"></div>'
            + '</div><div class="pop-progress-label">' + Math.round(pct) + '% abgeschlossen</div>';
        }} else if (p.status === 'upcoming') {{
          var days = Math.ceil((ds.getTime() - now) / 86400000);
          if (days > 0) progressHtml = '<div class="pop-countdown">Noch ' + days + ' Tag' + (days !== 1 ? 'e' : '') + '</div>';
        }}

        var linkHtml = p.website
          ? '<a class="pop-link" href="' + p.website + '" target="_blank">Website &#8594;</a>'
          : '';

        var favStar = p.is_fav
          ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="#fbbf24" stroke="none" style="flex-shrink:0">'
            + '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>'
          : '';

        var popupHtml = '<div class="pop">'
          + '<div class="pop-top">'
          + '<span class="pop-spec" style="background:' + color + '22;color:' + color + ';border:1px solid ' + color + '44">' + p.specialty + '</span>'
          + statusHtml + favStar
          + '</div>'
          + '<div class="pop-name">' + p.name + '</div>'
          + '<div class="pop-meta">' + p.city + ', ' + p.country + ' &middot; ' + dateStr + '</div>'
          + progressHtml
          + '<div class="pop-badges">' + badges + '</div>'
          + linkHtml
          + '</div>';

        // Store popup data for custom info-panel
        marker._popupHtml = popupHtml;
        marker._specColor = color;

        marker.on('click', function() {{
          var panel = document.getElementById('info-panel');
          var content = document.getElementById('info-content');
          content.innerHTML = this._popupHtml;
          // Apply specialty glow to panel border-top
          panel.style.borderTopColor = this._specColor + '44';
          panel.style.boxShadow = '0 12px 48px rgba(0,0,0,0.6), 0 -2px 14px ' + this._specColor + '33';
          panel.classList.add('visible');
        }});

        allMarkers.push(marker);
        markerSpecMap.push({{ marker: marker, color: color, specialty: p.specialty, month: ds.getMonth() }});
      }});

      // --- Staggered marker entry ---
      var delay = 0;
      allMarkers.forEach(function(m) {{
        setTimeout(function() {{ markers.addLayer(m); }}, delay);
        delay += 20;
      }});
      map.addLayer(markers);

      // --- Fly to bounds after entry ---
      if (data.features.length > 0) {{
        setTimeout(function() {{
          try {{
            map.flyToBounds(markers.getBounds(), {{
              padding: [30, 30], maxZoom: 5, duration: 1.4
            }});
          }} catch(e) {{}}
        }}, 800);
      }}

      // --- Interactive legend ---
      var sorted = Object.entries(specCounts).sort(function(a,b) {{ return b[1]-a[1]; }});
      var activeFilters = new Set();

      function updateMarkerVisibility() {{
        allMarkers.forEach(function(m) {{
          var el = m.getElement ? m.getElement() : null;
          if (!el) return;
          if (activeFilters.size === 0 || activeFilters.has(m.options._specialty)) {{
            el.style.opacity = '1';
            el.style.transition = 'opacity 0.4s ease';
          }} else {{
            el.style.opacity = '0.07';
            el.style.transition = 'opacity 0.4s ease';
          }}
        }});
        // Update legend item states
        document.querySelectorAll('.legend-item[data-spec]').forEach(function(item) {{
          var spec = item.getAttribute('data-spec');
          if (activeFilters.size === 0) {{
            item.classList.remove('active', 'dimmed');
          }} else if (activeFilters.has(spec)) {{
            item.classList.add('active');
            item.classList.remove('dimmed');
          }} else {{
            item.classList.add('dimmed');
            item.classList.remove('active');
          }}
        }});
        var resetBtn = document.getElementById('legend-reset');
        if (resetBtn) {{
          resetBtn.classList.toggle('visible', activeFilters.size > 0);
        }}
      }}

      var legendHtml = '<div class="legend-title">'
        + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#84cc16" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l2 2"/></svg>'
        + ' Fachgebiete</div>';
      sorted.slice(0, 10).forEach(function(entry) {{
        var spec = entry[0], count = entry[1];
        var c = specColors[spec] || defaultColor;
        legendHtml += '<div class="legend-item" data-spec="' + spec + '" style="--lc:' + c + '">'
          + '<span class="legend-dot" style="background:' + c + '"></span>'
          + '<span>' + spec + ' (' + count + ')</span></div>';
      }});
      if (sorted.length > 10) {{
        legendHtml += '<div class="legend-count">+' + (sorted.length - 10) + ' weitere</div>';
      }}
      legendHtml += '<div id="legend-reset" class="legend-reset">Filter zuruecksetzen</div>';
      legendHtml += '<div class="legend-count" style="margin-top:6px;border-top:1px solid var(--c-border);padding-top:6px">'
        + data.features.length + ' Kongresse</div>';

      var legendDiv = document.createElement('div');
      legendDiv.className = 'legend';
      legendDiv.innerHTML = legendHtml;
      document.getElementById('map').appendChild(legendDiv);

      // Event delegation for legend clicks (avoids inline onclick quoting issues)
      legendDiv.addEventListener('click', function(e) {{
        var item = e.target.closest('.legend-item[data-spec]');
        if (item) {{
          var spec = item.getAttribute('data-spec');
          if (activeFilters.has(spec)) activeFilters.delete(spec);
          else activeFilters.add(spec);
          updateMarkerVisibility();
          return;
        }}
        if (e.target.closest('#legend-reset')) {{
          activeFilters.clear();
          updateMarkerVisibility();
        }}
      }});

      // --- Timeline slider ---
      var now = new Date();
      var curMonth = now.getMonth();
      var timeWrap = document.createElement('div');
      timeWrap.className = 'timeline-bar';
      var labels = months.map(function(m, i) {{
        return '<span class="timeline-month' + (i === curMonth ? ' active' : '') + '">' + m + '</span>';
      }}).join('');
      timeWrap.innerHTML = '<input type="range" id="timeSlider" min="0" max="12" value="12" title="Monat filtern">'
        + '<div class="timeline-labels">' + labels + '</div>';
      document.getElementById('map').appendChild(timeWrap);

      document.getElementById('timeSlider').addEventListener('input', function(e) {{
        var val = parseInt(e.target.value);
        var tLabels = document.querySelectorAll('.timeline-month');
        tLabels.forEach(function(l, i) {{
          l.classList.toggle('active', val === 12 || i === val);
        }});
        // Filter markers by month (12 = show all)
        allMarkers.forEach(function(m, idx) {{
          var info = markerSpecMap[idx];
          var el = m.getElement ? m.getElement() : null;
          if (!el) return;
          if (val === 12 || info.month === val) {{
            el.style.opacity = (activeFilters.size === 0 || activeFilters.has(m.options._specialty)) ? '1' : '0.07';
            el.style.transition = 'opacity 0.35s ease';
          }} else {{
            el.style.opacity = '0.04';
            el.style.transition = 'opacity 0.35s ease';
          }}
        }});
      }});

      // --- Keyboard navigation ---
      var focusIdx = -1;
      document.addEventListener('keydown', function(e) {{
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {{
          e.preventDefault();
          focusIdx = (focusIdx + 1) % allMarkers.length;
          var m = allMarkers[focusIdx];
          map.panTo(m.getLatLng());
          m.openTooltip();
        }} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {{
          e.preventDefault();
          focusIdx = (focusIdx - 1 + allMarkers.length) % allMarkers.length;
          var m = allMarkers[focusIdx];
          map.panTo(m.getLatLng());
          m.openTooltip();
        }} else if (e.key === 'Enter' && focusIdx >= 0) {{
          allMarkers[focusIdx].fire('click');
        }} else if (e.key === 'Escape') {{
          closeInfoPanel();
        }}
      }});
    }})();
    </script>
    </body>
    </html>
    """
    st.components.v1.html(map_html, height=560)


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_kongresse():
    """Render the Kongressplan tab."""
    st.markdown(
        '<div class="page-header">Kongressplan 2026</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="page-sub">Alle wichtigen Ärztekongresse auf einen Blick — Termine, CME, Deadlines</div>',
        unsafe_allow_html=True,
    )

    all_congresses = _cached_congresses()

    if not all_congresses:
        st.warning("Keine Kongressdaten geladen.")
        return

    favorites = _get_favorites()

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
    fav_count = len(favorites)

    st.markdown(f"""
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:16px 0 20px 0">
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
            <div class="kpi-card" style="animation-delay:0.32s">
                <div class="kpi-value">⭐ {fav_count}</div>
                <div class="kpi-label">Favoriten</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ---- Meine Kongresse (Favoriten) ----
    _render_favorites_section(all_congresses, favorites)

    # ---- View Toggle: Timeline vs. Kalender vs. Weltkarte ----
    view_mode = st.radio(
        "Ansicht",
        options=["Timeline", "Kalender", "\U0001f5fa Weltkarte"],
        horizontal=True,
        key="kongress_view_mode",
        label_visibility="collapsed",
    )

    if view_mode == "Timeline":
        _render_timeline(all_congresses)
    elif view_mode == "Kalender":
        _render_calendar_view(all_congresses)
    else:
        _render_map_view(all_congresses, favorites)

    # ---- Überlappungs-Warnungen ----
    _render_overlap_warnings(all_congresses)

    # ---- Filters ----
    st.markdown(
        '<div class="section-divider"><span class="section-divider-label">Filter & Übersicht</span></div>',
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
            placeholder="Alle Fachgebiete",
            key="kongress_filter_spec",
        )
    with col_f2:
        sel_country = st.multiselect(
            "Land",
            options=countries,
            default=[],
            placeholder="Alle Länder",
            key="kongress_filter_country",
        )
    with col_f3:
        sel_months = st.multiselect(
            "Monat",
            options=list(month_options.keys()),
            format_func=lambda x: month_options[x],
            default=[],
            placeholder="Alle Monate",
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

    # Extra filter: Favoriten only
    col_past, col_fav = st.columns(2)
    with col_past:
        show_past = st.checkbox("Vergangene Kongresse anzeigen", value=False, key="kongress_show_past")
    with col_fav:
        only_favs = st.checkbox("Nur Favoriten anzeigen", value=False, key="kongress_only_favs")

    if not show_past:
        filtered = [c for c in filtered if c["status"] != "past"]
    if only_favs:
        filtered = [c for c in filtered if c["id"] in favorites]

    st.markdown(
        f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-bottom:12px">'
        f'{len(filtered)} Kongresse gefunden</div>',
        unsafe_allow_html=True,
    )

    # ---- Abstract Deadline Warnings ----
    _render_deadline_alerts(filtered)

    # ---- Congress Cards ----
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

        is_fav = c["id"] in favorites
        _render_congress_card(c, is_fav=is_fav)

        # Expander with details + action buttons
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

            # --- Action Buttons Row ---
            st.markdown("---")
            btn_cols = st.columns(5)

            # Feature 1: Favorit-Toggle
            with btn_cols[0]:
                fav_label = "\u2605 Entfernen" if is_fav else "\u2606 Favorit"
                if st.button(fav_label, key=f"fav_{c['id']}", type="secondary"):
                    _toggle_fav(c["id"])
                    st.rerun()

            # Feature 3: Artikel anzeigen (inline statt Tab-Wechsel)
            with btn_cols[1]:
                if c["related_article_count"] > 0:
                    _art_key = f"_show_arts_{c['id']}"
                    if st.button(f"\U0001f50d {c['related_article_count']} Artikel", key=f"art_{c['id']}"):
                        st.session_state[_art_key] = not st.session_state.get(_art_key, False)
                        st.rerun()

            # Feature 6: Watchlist erstellen
            with btn_cols[2]:
                if c["keywords"]:
                    if st.button("\U0001f4cb Watchlist", key=f"wl_{c['id']}"):
                        from src.processing.kongresse import create_congress_watchlist
                        wl_id = create_congress_watchlist(c["id"])
                        if wl_id:
                            st.success(f"Watchlist erstellt: {c['short']} (ID {wl_id})")
                        else:
                            st.warning("Watchlist konnte nicht erstellt werden.")

            # Feature 8: Redaktionsplan
            with btn_cols[3]:
                if st.button("\U0001f4c5 Redaktion", key=f"ed_{c['id']}"):
                    from src.processing.kongresse import add_congress_to_editorial
                    topic_id = add_congress_to_editorial(c["id"])
                    if topic_id:
                        st.success(f"Thema im Redaktionsplan: {c['short']}")
                    else:
                        st.warning("Redaktionsplan-Eintrag konnte nicht erstellt werden.")

            # Feature NEW: KI-Kongress-Briefing
            with btn_cols[4]:
                if c["status"] != "past":
                    if st.button("\U0001f916 KI-Briefing", key=f"brief_{c['id']}"):
                        if "kongress_briefings" not in st.session_state:
                            st.session_state.kongress_briefings = {}
                        st.session_state.kongress_briefings[c["id"]] = "generate"
                        st.rerun()

            # Show related articles inline
            _art_key = f"_show_arts_{c['id']}"
            if st.session_state.get(_art_key) and c["related_article_count"] > 0:
                _kw_list = c["keywords"][:4] if c["keywords"] else [c["short"]]
                with st.expander(f"🔍 Artikel zu {c['short']}", expanded=True):
                    # Gleiche ILIKE-auf-title Logik wie _count_related_articles()
                    from src.processing.kongresse import get_related_article_ids
                    from src.models import Article as _Art, get_session
                    from sqlmodel import col as _col
                    _rel_ids = get_related_article_ids(_kw_list)
                    _kongress_arts = []
                    if _rel_ids:
                        with get_session() as _ks:
                            from sqlmodel import select as _ksel
                            _kongress_arts = list(_ks.exec(
                                _ksel(_Art).where(_col(_Art.id).in_(_rel_ids))
                                .order_by(_Art.relevance_score.desc())  # type: ignore
                            ))[:15]
                    if _kongress_arts:
                        for _ka in _kongress_arts:
                            _ksc = "#4ade80" if (_ka.relevance_score or 0) >= 70 else "#f59e0b" if (_ka.relevance_score or 0) >= 50 else "var(--c-text-muted)"
                            st.markdown(
                                f'<div style="padding:5px 0;border-bottom:1px solid var(--c-border-subtle);font-size:0.78rem">'
                                f'<span style="color:{_ksc};font-weight:700">{_ka.relevance_score or 0:.0f}</span> '
                                f'<a href="{_ka.url or "#"}" target="_blank" style="color:var(--c-accent)">'
                                f'{_ka.title[:80]}</a>'
                                f' <span style="color:var(--c-text-muted);font-size:0.68rem">'
                                f'{_ka.journal or ""} · {_ka.pub_date.strftime("%d.%m.%Y") if _ka.pub_date else ""}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("Keine verwandten Artikel gefunden.")

            # Show briefing if requested
            if st.session_state.get("kongress_briefings", {}).get(c["id"]) == "generate":
                with st.spinner(f"KI-Briefing f\u00fcr {c['short']} wird generiert..."):
                    from src.processing.kongress_briefing import (
                        generate_congress_briefing, briefing_to_html, briefing_to_markdown,
                    )
                    briefing = generate_congress_briefing(c)
                    if briefing:
                        st.session_state.kongress_briefings[c["id"]] = briefing
                        st.rerun()
                    else:
                        st.error(
                            "⚠️ **KI-Briefing konnte nicht generiert werden.**\n\n"
                            "Die KI-Schnittstelle ist gerade nicht erreichbar "
                            "(z.B. Tages-Limit erreicht oder Dienst überlastet). "
                            "Bitte versuche es in 10–15 Minuten erneut."
                        )
                        st.session_state.kongress_briefings[c["id"]] = None

            _briefing = st.session_state.get("kongress_briefings", {}).get(c["id"])
            if _briefing and _briefing not in ("generate", None):
                from src.processing.kongress_briefing import briefing_to_html, briefing_to_markdown
                with st.expander(f"\U0001f916 KI-Briefing: Was Sie zum {_esc(c['short'])} wissen m\u00fcssen", expanded=True):
                    st.markdown(briefing_to_html(_briefing), unsafe_allow_html=True)
                    st.download_button(
                        label="\u2b07 Briefing als Markdown",
                        data=briefing_to_markdown(_briefing),
                        file_name=f"lumio_briefing_{c['short'].lower().replace(' ', '_')}.md",
                        mime="text/markdown",
                        key=f"brief_dl_{c['id']}",
                    )

    # ---- .ics Export ----
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="section-divider"><span class="section-divider-label">Export</span></div>',
        unsafe_allow_html=True,
    )

    exp_col1, exp_col2, exp_col3 = st.columns(3)

    # .ics Export
    with exp_col1:
        from src.processing.kongresse import load_congresses, generate_ics_calendar
        if st.button("\U0001f4c5 Kalender (.ics)", key="kongress_ics_export", type="primary",
                     use_container_width=True):
            congresses_obj = load_congresses(with_articles=False)
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

    # PDF Jahresplan
    with exp_col2:
        _pdf_group = st.selectbox(
            "Gruppierung",
            ["Nach Monat", "Nach Fachgebiet"],
            index=0, label_visibility="collapsed",
            key="pdf_grouping",
        )
        if st.button("\U0001f4c4 PDF Jahresplan (A3)", key="kongress_pdf_export", type="primary",
                     use_container_width=True):
            with st.spinner("PDF wird generiert..."):
                from src.congress_pdf import generate_congress_pdf
                group_by = "specialty" if "Fachgebiet" in _pdf_group else "month"
                pdf_bytes = generate_congress_pdf(congresses, year=2026, group_by=group_by)
                st.download_button(
                    label=f"Download Kongresskalender 2026.pdf",
                    data=pdf_bytes,
                    file_name="lumio_kongresskalender_2026.pdf",
                    mime="application/pdf",
                    key="kongress_pdf_download",
                )

    with exp_col3:
        st.markdown(
            '<div style="font-size:0.72rem;color:var(--c-text-muted);padding-top:4px">'
            '<b>.ics</b> \u2014 Apple/Google/Outlook Kalender<br>'
            '<b>.pdf</b> \u2014 Druckbarer A3-Jahresplan'
            '</div>',
            unsafe_allow_html=True,
        )

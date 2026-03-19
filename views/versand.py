"""Lumio — Versand tab: digest preview & Themen-Pakete."""

from datetime import date

import streamlit as st


def _copy_html_button(html_content: str, button_label: str, key: str):
    """Render a button that copies HTML content to clipboard via JS."""
    import base64
    b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    st.components.v1.html(f"""
    <button id="btn_{key}" style="
        background: #84cc16; color: #0a0a1a; border: none; border-radius: 8px;
        padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer;
        width: 100%; transition: background 0.2s;
        font-family: Inter, -apple-system, 'Segoe UI', sans-serif;
    " onmouseover="this.style.background='#a3e635'"
      onmouseout="this.style.background='#84cc16'"
      onclick="
        try {{
            const html = atob('{b64}');
            const blob = new Blob([html], {{type: 'text/html'}});
            const item = new ClipboardItem({{'text/html': blob, 'text/plain': new Blob([html], {{type: 'text/plain'}})}});
            navigator.clipboard.write([item]).then(() => {{
                this.textContent = 'Kopiert!';
                this.style.background = '#22c55e';
                setTimeout(() => {{
                    this.textContent = '{button_label}';
                    this.style.background = '#84cc16';
                }}, 2000);
            }}).catch(() => {{
                const ta = document.createElement('textarea');
                ta.value = html;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                this.textContent = 'Kopiert!';
                this.style.background = '#22c55e';
                setTimeout(() => {{
                    this.textContent = '{button_label}';
                    this.style.background = '#84cc16';
                }}, 2000);
            }});
        }} catch(e) {{
            this.textContent = 'Fehler';
            setTimeout(() => {{ this.textContent = '{button_label}'; }}, 2000);
        }}
    ">{button_label}</button>
    """, height=50)


def _download_html_button(html_content: str, button_label: str, filename: str, key: str):
    """Render a button that triggers a browser download of HTML content."""
    import base64
    b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    st.components.v1.html(f"""
    <button id="btn_{key}" style="
        background: #84cc16; color: #0a0a1a; border: none; border-radius: 8px;
        padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer;
        width: 100%; transition: background 0.2s;
        font-family: Inter, -apple-system, 'Segoe UI', sans-serif;
    " onmouseover="this.style.background='#a3e635'"
      onmouseout="this.style.background='#84cc16'"
      onclick="
        try {{
            const html = atob('{b64}');
            const blob = new Blob([html], {{type: 'text/html'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '{filename}';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.textContent = 'Heruntergeladen!';
            this.style.background = '#22c55e';
            setTimeout(() => {{
                this.textContent = '{button_label}';
                this.style.background = '#84cc16';
            }}, 2000);
        }} catch(e) {{
            this.textContent = 'Fehler';
            setTimeout(() => {{ this.textContent = '{button_label}'; }}, 2000);
        }}
    ">{button_label}</button>
    """, height=50)


def render_versand():
    """Render the Versand tab content."""
    st.markdown('<div class="page-header">Versand</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Digest &middot; Themen-Pakete</div>', unsafe_allow_html=True)

    from src.digest import get_top_articles, _build_html

    # --- Digest preview (cached) ---
    @st.cache_data(ttl=600, show_spinner=False)
    def _cached_top_articles():
        return get_top_articles(10)

    digest_articles = _cached_top_articles()
    if digest_articles:
        st.markdown('<div class="section-header">Digest-Vorschau</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-sub">Top 10 Artikel nach Relevanz &middot; E-Mail-Vorlage</div>',
            unsafe_allow_html=True,
        )
        digest_html = _build_html(digest_articles, date.today())
        st.components.v1.html(digest_html, height=800, scrolling=True)

        # --- Digest action buttons ---
        _dc1, _dc2 = st.columns(2)
        with _dc1:
            _copy_html_button(
                digest_html,
                "\U0001f4cb In Zwischenablage kopieren",
                "digest_copy",
            )
        with _dc2:
            _today = date.today().strftime("%Y-%m-%d")
            _download_html_button(
                digest_html,
                "\u2b07\ufe0f Als HTML herunterladen",
                f"lumio-digest-{_today}.html",
                "digest_dl",
            )

    else:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">\U0001f4e7</div>
                <div class="empty-state-text">Noch keine Artikel vorhanden</div>
                <div style="font-size:0.8rem;color:var(--c-text-muted);margin-top:4px">
                    Die Pipeline importiert automatisch alle 6 Stunden neue Artikel
                </div>
            </div>
        """, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Themen-Pakete
    # ------------------------------------------------------------------
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">\U0001f4e6 Themen-Pakete</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">W\u00f6chentliche Recherche-Pakete pro Watchlist (letzte 7 Tage)</div>',
        unsafe_allow_html=True,
    )

    from src.processing.watchlist import get_active_watchlists, get_watchlist_counts
    from src.themen_paket import generate_paket, generate_all_pakete, _build_paket_html
    from components.helpers import _esc

    _PAKET_DAYS = 7  # Fixed: weekly packages

    watchlists = get_active_watchlists()
    wl_counts = get_watchlist_counts()

    if not watchlists:
        st.markdown(
            '<div style="text-align:center;padding:24px 12px;color:var(--c-text-muted);font-size:0.85rem">'
            'Keine Watchlists vorhanden.<br>'
            'Erstelle eine im <b>Feed</b>-Tab, um Themen-Pakete zu generieren.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # Watchlist overview cards
        for wl in watchlists:
            cnt = wl_counts.get(wl.id, 0)
            kw_short = wl.keywords[:50] + ("..." if len(wl.keywords) > 50 else "")
            st.markdown(
                f'<div style="border:1px solid var(--c-border);border-radius:10px;'
                f'padding:14px 18px;margin-bottom:10px;background:var(--c-surface)">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div>'
                f'<span style="font-weight:700;font-size:0.9rem">{_esc(wl.name)}</span>'
                f'<span style="font-size:0.72rem;color:var(--c-text-muted);margin-left:8px">'
                f'{_esc(kw_short)}</span>'
                f'</div>'
                f'<span style="background:var(--c-accent);color:var(--c-bg);font-size:0.68rem;'
                f'font-weight:700;padding:3px 10px;border-radius:10px">{cnt} Treffer</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Two clear actions
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        _ac1, _ac2 = st.columns(2)
        with _ac1:
            if st.button("\U0001f4cb Kopieren", key="btn_paket_copy_all",
                          type="primary", use_container_width=True,
                          help="Alle Pakete generieren und in die Zwischenablage kopieren"):
                with st.spinner("Pakete werden erstellt..."):
                    pakete = generate_all_pakete(days_back=_PAKET_DAYS)
                if pakete:
                    combined_html = "".join(_build_paket_html(p) for p in pakete)
                    _copy_html_button(combined_html, "Kopiert! Nochmal kopieren?", "all_pakete_cp")
                    st.success(f"{len(pakete)} Pakete in Zwischenablage kopiert")
                else:
                    st.warning("Keine Treffer in den letzten {0} Tagen.".format(_PAKET_DAYS))

        with _ac2:
            if st.button("\u2b07\ufe0f Herunterladen", key="btn_paket_dl_all",
                          type="primary", use_container_width=True,
                          help="Alle Pakete als HTML-Dateien herunterladen"):
                with st.spinner("Pakete werden erstellt..."):
                    pakete = generate_all_pakete(days_back=_PAKET_DAYS)
                if pakete:
                    for p in pakete:
                        paket_html = _build_paket_html(p)
                        _slug = p.watchlist_name.lower().replace(" ", "-")
                        _download_html_button(
                            paket_html,
                            f"Heruntergeladen: {_esc(p.watchlist_name)}",
                            f"paket-{_slug}.html",
                            f"adl_{_slug}",
                        )
                    st.success(f"{len(pakete)} Pakete heruntergeladen")
                else:
                    st.warning("Keine Treffer in den letzten {0} Tagen.".format(_PAKET_DAYS))

        # Optional: Preview per watchlist for those who want to peek
        with st.expander("Vorschau einzelner Pakete", expanded=False):
            _preview_wl = st.selectbox(
                "Watchlist",
                watchlists,
                format_func=lambda w: w.name,
                key="paket_preview_wl",
                label_visibility="collapsed",
            )
            if st.button("Vorschau laden", key="btn_paket_preview", use_container_width=True):
                with st.spinner("Wird geladen..."):
                    paket = generate_paket(_preview_wl, days_back=_PAKET_DAYS)
                if paket and paket.total_matches > 0:
                    paket_html = _build_paket_html(paket)
                    st.components.v1.html(paket_html, height=600, scrolling=True)
                else:
                    st.info(f"Keine Treffer f\u00fcr '{_esc(_preview_wl.name)}' in den letzten {_PAKET_DAYS} Tagen.")

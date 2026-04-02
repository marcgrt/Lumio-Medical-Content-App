"""Lumio — Versand tab: digest preview & Themen-Pakete."""

from datetime import date

import streamlit as st


# Glass button inline CSS + JS for iframe-embedded buttons
# (matches main app glass morphism style)
def _glass_btn_css():
    """Return glass button CSS, theme-aware."""
    import streamlit as st
    is_esanum = st.session_state.get("theme", "dark") == "esanum"
    if is_esanum:
        return """<style>
  body { margin: 0; background: transparent; }
  .glass-btn {
    position: relative; overflow: hidden;
    font-family: 'Inter','Open Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    border-radius: 9999px; font-weight: 600; font-size: 0.82rem;
    padding: 8px 20px; white-space: nowrap; min-height: 36px;
    cursor: pointer; width: 100%;
    transition: transform 0.25s ease, box-shadow 0.3s ease, background 0.3s ease;
    border: 1px solid #005461; background: #005461; color: #FFFFFF;
    box-shadow: 0 2px 8px rgba(0,84,97,0.15); backdrop-filter: none;
  }
  .glass-btn:hover { background: #003E48; border-color: #003E48; color: #FFFFFF;
    transform: translateY(-1px); box-shadow: 0 4px 16px rgba(0,84,97,0.25); }
  .glass-btn:active { transform: translateY(0) scale(0.97); }
  .glass-btn.success { background: #49661E; border-color: #49661E; color: #FFFFFF; }
</style>"""
    return """<style>
  body { margin: 0; background: transparent; }
  .glass-btn {
    position: relative;
    overflow: hidden;
    font-family: 'Inter', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    border-radius: 9999px;
    font-weight: 600;
    font-size: 0.82rem;
    padding: 8px 20px;
    white-space: nowrap;
    min-height: 36px;
    cursor: pointer;
    width: 100%;
    transition: transform 0.25s ease, box-shadow 0.3s ease,
        border-color 0.3s ease, background 0.3s ease;
    border: 1px solid rgba(132,204,22,0.30);
    background: linear-gradient(135deg,
        rgba(132,204,22,0.25) 0%, rgba(132,204,22,0.12) 50%,
        rgba(132,204,22,0.20) 100%);
    backdrop-filter: blur(12px) saturate(1.4);
    color: #d9f99d;
    box-shadow: 0 0 12px rgba(132,204,22,0.10),
        0 2px 8px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.10);
  }
  .glass-btn:hover {
    transform: translateY(-1px);
    border-color: rgba(132,204,22,0.50);
    background: linear-gradient(135deg,
        rgba(132,204,22,0.35) 0%, rgba(132,204,22,0.18) 50%,
        rgba(132,204,22,0.30) 100%);
    box-shadow: 0 0 28px rgba(132,204,22,0.22),
        0 4px 16px rgba(0,0,0,0.25);
    color: #ecfccb;
  }
  .glass-btn:active { transform: translateY(0) scale(0.97); }
  .glass-btn.success {
    border-color: rgba(34,197,94,0.50);
    background: linear-gradient(135deg, rgba(34,197,94,0.30), rgba(34,197,94,0.15));
    color: #bbf7d0;
  }
</style>"""


def _get_glass_btn_css():
    return _glass_btn_css()


def _copy_html_button(html_content: str, button_label: str, key: str):
    """Render a glass-style button that copies HTML content to clipboard via JS."""
    import base64
    b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    st.components.v1.html(f"""
    {_get_glass_btn_css()}
    <button id="btn_{key}" class="glass-btn"
      onclick="
        var self = this;
        try {{
            var html = atob('{b64}');
            var blob = new Blob([html], {{type: 'text/html'}});
            var item = new ClipboardItem({{'text/html': blob, 'text/plain': new Blob([html], {{type: 'text/plain'}})}});
            navigator.clipboard.write([item]).then(function() {{
                self.textContent = '\u2705 Kopiert!';
                self.classList.add('success');
                setTimeout(function() {{
                    self.textContent = '{button_label}';
                    self.classList.remove('success');
                }}, 2000);
            }}).catch(function() {{
                var ta = document.createElement('textarea');
                ta.value = html;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                self.textContent = '\u2705 Kopiert!';
                self.classList.add('success');
                setTimeout(function() {{
                    self.textContent = '{button_label}';
                    self.classList.remove('success');
                }}, 2000);
            }});
        }} catch(e) {{
            self.textContent = 'Kopieren fehlgeschlagen';
            setTimeout(function() {{ self.textContent = '{button_label}'; }}, 3000);
        }}
    ">{button_label}</button>
    """, height=50)


def _download_html_button(html_content: str, button_label: str, filename: str, key: str):
    """Glass-style button that triggers download via data-URI in parent window."""
    import base64
    b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    st.components.v1.html(f"""
    {_get_glass_btn_css()}
    <button id="btn_{key}" class="glass-btn"
      onclick="
        var self = this;
        try {{
            var b64 = '{b64}';
            var html = atob(b64);
            var dataUri = 'data:text/html;base64,' + b64;
            var a = window.parent.document.createElement('a');
            a.href = dataUri;
            a.download = '{filename}';
            a.style.display = 'none';
            window.parent.document.body.appendChild(a);
            a.click();
            window.parent.document.body.removeChild(a);
            self.textContent = '\u2705 Heruntergeladen!';
            self.classList.add('success');
            setTimeout(function() {{
                self.textContent = '{button_label}';
                self.classList.remove('success');
            }}, 2000);
        }} catch(e) {{
            self.textContent = '\u274c Fehlgeschlagen';
            setTimeout(function() {{ self.textContent = '{button_label}'; }}, 3000);
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
            'Erstelle eine in der <b>Seitenleiste</b>, um Themen-Pakete zu generieren.'
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

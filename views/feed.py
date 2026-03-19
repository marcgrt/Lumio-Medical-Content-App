"""Lumio — Feed tab: Dashboard KPIs, Themen-Radar, article feed, favorites & watchlists."""

from datetime import date

import streamlit as st

from src.config import SCORE_THRESHOLD_HIGH
from src.models import Watchlist, WatchlistMatch, get_session
from src.processing.watchlist import (
    get_watchlist_matches, run_watchlist_matching,
)

from components.helpers import (
    _esc, get_articles, get_dashboard_kpis, get_unique_values,
    update_article_status,
    render_article_card, score_pill, spec_pill,
    momentum_badge, evidence_badge, cross_specialty_badge,
    _load_memory_batch,
    SPECIALTY_COLORS,
)


def render_feed(filters: dict):
    """Render the Feed tab content."""
    today_str = date.today().strftime("%d. %B %Y")
    st.markdown('<div class="page-header">Feed</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="page-sub">{today_str} &middot; Die relevantesten medizinischen Artikel des Tages</div>',
        unsafe_allow_html=True,
    )

    # --- Dashboard KPI Hero Bar ---
    _dkpi = get_dashboard_kpis()

    # Build sparkline bars (pure CSS, no JS)
    _spark = _dkpi["sparkline"]
    _spark_max = max(_spark) if _spark and max(_spark) > 0 else 1
    _spark_html_parts = []
    for idx, v in enumerate(_spark):
        h = max(2, int(v / _spark_max * 36))
        opacity = "1" if idx >= 23 else "0.5"  # last 7 days brighter
        _spark_html_parts.append(
            f'<span class="sparkline-bar" style="height:{h}px;background:var(--c-accent);opacity:{opacity}"></span>'
        )
    _spark_html = "".join(_spark_html_parts)

    # WoW delta arrow
    _wow = _dkpi["wow_delta"]
    if _wow > 0:
        _wow_cls, _wow_arrow = "kpi-delta-up", f"\u2191 {_wow}%"
    elif _wow < 0:
        _wow_cls, _wow_arrow = "kpi-delta-down", f"\u2193 {abs(_wow)}%"
    else:
        _wow_cls, _wow_arrow = "kpi-delta-flat", "\u2192 0%"

    # Score delta
    _sdelta = round(_dkpi["avg_score_week"] - _dkpi["avg_score_last"], 1)
    if _sdelta > 0:
        _s_cls, _s_txt = "kpi-delta-up", f"\u2191 {_sdelta}"
    elif _sdelta < 0:
        _s_cls, _s_txt = "kpi-delta-down", f"\u2193 {abs(_sdelta)}"
    else:
        _s_cls, _s_txt = "kpi-delta-flat", "\u2192 0"

    st.markdown(f"""
    <div class="dash-bar">
        <div class="dash-card dash-card-accent">
            <div class="dash-value">{_dkpi['this_week']}</div>
            <div class="dash-label">Letzte 7 Tage</div>
            <div class="dash-sub {_wow_cls}">{_wow_arrow} vs. davor</div>
        </div>
        <div class="dash-card">
            <div class="dash-value">{_dkpi['avg_score_week']:.0f}</div>
            <div class="dash-label">\u00d8 Score</div>
            <div class="dash-sub {_s_cls}">{_s_txt} vs. davor</div>
        </div>
        <div class="dash-card">
            <div class="dash-value" style="color:var(--c-danger)">{_dkpi['unreviewed_hq']}</div>
            <div class="dash-label">Unbearbeitet HQ</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">Score \u2265 {SCORE_THRESHOLD_HIGH}</div>
        </div>
        <div class="dash-card">
            <div class="dash-value" style="font-size:1rem;font-weight:700;margin-top:4px">{_esc(_dkpi['top_journal'][:22])}</div>
            <div class="dash-label">Top-Quelle</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">{_dkpi['top_journal_n']} Artikel (7d)</div>
        </div>
        <div class="dash-card">
            <div style="display:flex;align-items:flex-end;height:36px;margin-bottom:4px;overflow:hidden">{_spark_html}</div>
            <div class="dash-label">30 Tage</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Themen-Radar 2.0 ---
    _render_themen_radar(filters)

    # --- Story-Radar ---
    _render_story_radar()

    # -- SECTION 2: ARTIKEL-FEED --
    _active_wl_id = st.session_state.get("active_watchlist_id")
    _wl_name = ""
    _wl_article_ids = set()  # Always defined — prevents NameError

    if _active_wl_id:
        # Validate watchlist still exists + get matches
        from sqlmodel import select as _sel
        with get_session() as _s:
            _wl_obj = _s.get(Watchlist, _active_wl_id)
            if _wl_obj:
                _wl_name = _wl_obj.name
                _wl_article_ids = set(
                    r.article_id for r in
                    _s.exec(_sel(WatchlistMatch.article_id).where(
                        WatchlistMatch.watchlist_id == _active_wl_id))
                )
            else:
                # Watchlist was deleted — clear stale filter
                st.session_state.pop("active_watchlist_id", None)
                _active_wl_id = None

    if _active_wl_id and _wl_article_ids:
        st.markdown(
            f'<div class="section-divider">'
            f'<span class="section-divider-label">'
            f'\U0001f3af {_esc(_wl_name)}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:0.75rem;color:var(--c-text-muted);margin:-8px 0 12px 0">'
            'Watchlist-Filter aktiv &middot; Zur\u00fcck \u00fcber die Sidebar</div>',
            unsafe_allow_html=True,
        )
    elif _active_wl_id and not _wl_article_ids:
        # Watchlist exists but has 0 matches — show message + fall back to normal feed
        st.session_state.pop("active_watchlist_id", None)
        _active_wl_id = None
        st.markdown(
            '<div class="section-divider">'
            '<span class="section-divider-label">Artikel-Feed</span></div>',
            unsafe_allow_html=True,
        )
        st.info(f"Keine Treffer f\u00fcr \u00bb{_wl_name}\u00ab \u2014 zeige alle Artikel.")
    else:
        st.markdown(
            '<div class="section-divider">'
            '<span class="section-divider-label">Artikel-Feed</span></div>',
            unsafe_allow_html=True,
        )

    articles = _get_filtered_articles(filters)

    # Apply watchlist filter only if active AND has matches
    if _active_wl_id and _wl_article_ids:
        articles = [a for a in articles if a.id in _wl_article_ids]

    # --- PromptLab Export ---
    if "selected_articles" not in st.session_state:
        st.session_state.selected_articles = set()

    _sel_ids = st.session_state.selected_articles

    # Always clean up ALL JS-injected export elements from previous renders
    if not st.session_state.get("_promptlab_export"):
        st.components.v1.html("""
        <script>
        (function(){
          var pd=window.parent.document;
          ['lumio-export-actions','lumio-export-banner'].forEach(function(id){
            var el=pd.getElementById(id); if(el) el.remove();
          });
          // Also remove any stuck overlay/dimming elements
          pd.querySelectorAll('.lumio-export-overlay').forEach(function(el){el.remove()});
        })();
        </script>
        """, height=0)

    # Show export result if just generated
    if st.session_state.get("_promptlab_export"):
        # Auto-scroll to export section + toast on first render
        if st.session_state.pop("_export_just_done", False):
            st.toast("Export erstellt!", icon="\u2705")

        # Anchor for auto-scroll
        st.markdown('<div id="lumio-export-result"></div>', unsafe_allow_html=True)

        # Action bar as styled HTML buttons
        _n_articles = st.session_state["_promptlab_export"].count("## Artikel")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:14px 18px;
            background:rgba(163,230,53,0.06);border:1px solid rgba(163,230,53,0.15);
            border-radius:12px;margin-bottom:12px">
          <div style="flex:1">
            <div style="font-weight:700;font-size:0.9rem;color:var(--c-text)">
              Export bereit</div>
            <div style="font-size:0.75rem;color:var(--c-text-muted);margin-top:2px">
              {_n_articles} Artikel &middot; In PromptLab einf\u00fcgen (FreeFlow oder Content-Task)</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.code(st.session_state["_promptlab_export"], language="markdown")

        # Hidden close button (triggered by JS) — also resets selection
        def _close_export():
            st.session_state.pop("_promptlab_export", None)
            st.session_state.selected_articles = set()
            st.session_state["_sel_gen"] = st.session_state.get("_sel_gen", 0) + 1
            for key in list(st.session_state.keys()):
                if key.startswith("sel_"):
                    del st.session_state[key]
        st.button("\u200b\u200b\u200b\u200b", key="close_export", on_click=_close_export)

        # JS: auto-scroll, styled action bar, clipboard copy, hide trigger button
        import json as _json
        _safe_export = _json.dumps(st.session_state["_promptlab_export"])
        st.components.v1.html(f"""
        <script>
        (function(){{
          var pd=window.parent.document;

          // Scroll to export
          var anchor=pd.getElementById('lumio-export-result');
          if(anchor) anchor.scrollIntoView({{behavior:'smooth',block:'start'}});

          // Find and hide the close trigger button (4x zero-width space)
          var closeBtn=null;
          var allBtns=pd.querySelectorAll('[data-testid="stAppViewContainer"] button');
          for(var i=0;i<allBtns.length;i++){{
            var raw=allBtns[i].textContent;
            var zwsp=raw.replace(/[^\\u200b]/g,'');
            if(zwsp.length===4){{
              closeBtn=allBtns[i];
              var wrap=closeBtn.closest('[class*="stButton"]')||
                       closeBtn.closest('[data-testid*="stBaseButton"]')||
                       closeBtn.parentElement;
              if(wrap) wrap.style.cssText='position:absolute;left:-9999px;height:0;overflow:hidden;';
              break;
            }}
          }}

          // Remove old action bar
          var oldBar=pd.getElementById('lumio-export-actions');
          if(oldBar) oldBar.remove();

          // Insert styled action bar after the code block
          var codeBlocks=pd.querySelectorAll('[data-testid="stAppViewContainer"] [data-testid="stCode"]');
          var lastCode=codeBlocks[codeBlocks.length-1];
          if(!lastCode) return;

          var bar=pd.createElement('div');
          bar.id='lumio-export-actions';
          bar.style.cssText='display:flex;gap:10px;padding:12px 0 20px 0;';

          var copyBtn=pd.createElement('button');
          copyBtn.textContent='In Zwischenablage kopieren';
          copyBtn.style.cssText='padding:10px 24px;border-radius:10px;border:none;cursor:pointer;'+
            'background:linear-gradient(135deg,#a3e635,#22d3ee);color:#0a0a1a;'+
            'font-size:0.82rem;font-weight:700;font-family:Inter,system-ui,sans-serif;'+
            'transition:all .15s;white-space:nowrap;';
          copyBtn.onmouseenter=function(){{this.style.filter='brightness(1.15)';this.style.transform='translateY(-1px)'}};
          copyBtn.onmouseleave=function(){{this.style.filter='none';this.style.transform='none'}};
          copyBtn.addEventListener('click',function(){{
            // Copy using textarea fallback (works in iframes without clipboard API permission)
            var exportText={_safe_export};
            var ta=pd.createElement('textarea');
            ta.value=exportText;
            ta.style.cssText='position:fixed;left:-9999px;top:-9999px;opacity:0';
            pd.body.appendChild(ta);
            ta.select();
            var ok=false;
            try {{ ok=pd.execCommand('copy'); }} catch(e) {{}}
            ta.remove();

            // Fallback to clipboard API on parent window if execCommand failed
            if(!ok && window.parent.navigator.clipboard) {{
              window.parent.navigator.clipboard.writeText(exportText).catch(function(){{}});
              ok=true;
            }}

            // Visual feedback
            copyBtn.textContent='Kopiert!';
            copyBtn.style.background='rgba(34,197,94,0.95)';
            setTimeout(function(){{
              copyBtn.textContent='In Zwischenablage kopieren';
              copyBtn.style.background='linear-gradient(135deg,#a3e635,#22d3ee)';
            }},3000);

            // Success toast
            var toast=pd.createElement('div');
            toast.style.cssText='position:fixed;top:24px;left:50%;transform:translateX(-50%) translateY(-20px);'+
              'z-index:99999;padding:14px 28px;border-radius:12px;'+
              'background:rgba(34,197,94,0.95);color:#fff;font-weight:700;font-size:0.85rem;'+
              'font-family:Inter,system-ui,sans-serif;box-shadow:0 8px 32px rgba(34,197,94,0.3);'+
              'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);'+
              'display:flex;align-items:center;gap:10px;'+
              'opacity:0;transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1);';
            toast.innerHTML=String.fromCodePoint(0x2705)+' Export erfolgreich in deine Zwischenablage kopiert';
            pd.body.appendChild(toast);
            setTimeout(function(){{toast.style.opacity='1';toast.style.transform='translateX(-50%) translateY(0)'}},10);
            setTimeout(function(){{
              toast.style.opacity='0';toast.style.transform='translateX(-50%) translateY(-20px)';
              setTimeout(function(){{toast.remove()}},300);
            }},3000);
          }});

          var clsBtn=pd.createElement('button');
          clsBtn.textContent='Schliessen';
          clsBtn.style.cssText='padding:10px 24px;border-radius:10px;cursor:pointer;'+
            'background:transparent;color:#b8b8cc;'+
            'border:1px solid rgba(255,255,255,0.10);'+
            'font-size:0.82rem;font-weight:600;font-family:Inter,system-ui,sans-serif;'+
            'transition:all .15s;white-space:nowrap;';
          clsBtn.onmouseenter=function(){{this.style.borderColor='rgba(255,255,255,0.25)';this.style.color='#e8e8f0'}};
          clsBtn.onmouseleave=function(){{this.style.borderColor='rgba(255,255,255,0.10)';this.style.color='#b8b8cc'}};
          clsBtn.addEventListener('click',function(){{
            // Remove injected elements immediately before Streamlit reruns
            var b=pd.getElementById('lumio-export-actions');if(b)b.remove();
            var eb=pd.getElementById('lumio-export-banner');if(eb)eb.remove();
            if(closeBtn) closeBtn.click();
          }});

          bar.appendChild(copyBtn);
          bar.appendChild(clsBtn);
          lastCode.parentElement.insertBefore(bar,lastCode.nextSibling);
        }})();
        </script>
        """, height=0)

    # Hidden Streamlit trigger buttons (space text = invisible to user)
    def _do_export():
        st.session_state["_promptlab_export"] = _build_promptlab_export(
            _get_filtered_articles(filters),
            st.session_state.get("selected_articles", set()),
        )
        st.session_state["_export_just_done"] = True

    def _do_deselect():
        # Clear set + bump generation counter so checkbox keys change → fresh widgets
        st.session_state.selected_articles = set()
        st.session_state["_sel_gen"] = st.session_state.get("_sel_gen", 0) + 1
        # Also delete old checkbox states
        for key in list(st.session_state.keys()):
            if key.startswith("sel_"):
                del st.session_state[key]

    # Two hidden trigger buttons (rendered here, BEFORE article loop)
    st.button("\u200b\u200b", key="export_promptlab", on_click=_do_export)    # 2x zero-width space
    st.button("\u200b\u200b\u200b", key="deselect_all", on_click=_do_deselect)  # 3x zero-width space

    if not articles:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">\U0001f4ed</div>
                <div class="empty-state-text">Keine Artikel gefunden</div>
                <div style="font-size:0.8rem;color:var(--c-text-muted);margin-top:4px">
                    Passe die Filter an oder starte die Pipeline im Versand-Tab
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Pagination
        ITEMS_PER_PAGE = 30
        if "show_count" not in st.session_state:
            st.session_state.show_count = ITEMS_PER_PAGE

        visible = articles[:st.session_state.show_count]

        # Batch-load editorial memory for visible articles
        visible_ids = tuple(a.id for a in visible if a.id is not None)
        memory_data = _load_memory_batch(visible_ids) if visible_ids else {}

        st.markdown(
            f'<div style="font-size:0.78rem;color:var(--c-text-muted);font-weight:500;'
            f'margin-bottom:14px">{len(visible)} von {len(articles)} Artikeln</div>',
            unsafe_allow_html=True,
        )

        for idx, article in enumerate(visible):
            mem_info = memory_data.get(article.id)
            render_article_card(article, idx, memory_info=mem_info)

        if len(articles) > st.session_state.show_count:
            remaining = len(articles) - st.session_state.show_count
            if st.button(f"\u2b07 Weitere {min(remaining, ITEMS_PER_PAGE)} Artikel laden",
                         type="primary", key="load_more"):
                st.session_state.show_count += ITEMS_PER_PAGE
                st.rerun()

    # -- SECTION 3: FAVORITEN & WATCHLISTS --
    _render_favorites_and_watchlists(filters)

    # -- EXPORT BANNER (after article loop so _sel_ids reflects current checkbox state) --
    _sel_count = len(st.session_state.get("selected_articles", set()))
    st.components.v1.html("""
    <script>
    (function(){
      var pd=window.parent.document;
      var main=pd.querySelector('[data-testid="stAppViewContainer"]');
      if(!main) return;

      // Find hidden trigger buttons by their zero-width space text length
      var exportBtn=null, deselectBtn=null;
      var allBtns=main.querySelectorAll('button');
      for(var i=0;i<allBtns.length;i++){
        var raw=allBtns[i].textContent;
        var zwsp=raw.replace(/[^\\u200b]/g,'');
        if(zwsp.length===2 && !exportBtn) exportBtn=allBtns[i];
        else if(zwsp.length===3 && !deselectBtn) deselectBtn=allBtns[i];
        // Hide any zero-width-space-only button
        if(zwsp.length>=2 && raw.trim().length===0){
          var wrap=allBtns[i].closest('[class*="stButton"]')||
                   allBtns[i].closest('[data-testid*="stBaseButton"]')||
                   allBtns[i].parentElement;
          if(wrap) wrap.style.cssText='position:absolute;left:-9999px;height:0;overflow:hidden;';
        }
      }

      // Always remove old banner + overlays IMMEDIATELY on every render.
      // This prevents the "sticky banner" when quickly selecting/deselecting.
      ['lumio-export-banner','lumio-export-actions'].forEach(function(id){
        var el=pd.getElementById(id); if(el) el.remove();
      });
      // Also set up a MutationObserver to remove the banner if Streamlit
      // updates the DOM while the banner is still visible with stale count.
      if(!window.parent.__exportBannerObserver){
        window.parent.__exportBannerObserver=true;
        var mo=new MutationObserver(function(){
          // Debounce: remove banner on any Streamlit DOM update,
          // the next render cycle will re-create it with correct count
          var b=pd.getElementById('lumio-export-banner');
          if(b && b.__stale){ b.remove(); }
        });
        mo.observe(main,{childList:true,subtree:true});
      }
      // Mark any existing banner as stale so observer can remove it
      var oldB=pd.getElementById('lumio-export-banner');
      if(oldB) oldB.__stale=true;

      var count=""" + str(_sel_count) + """;
      if(count===0) return;

      var banner=pd.createElement('div');
      banner.id='lumio-export-banner';
      banner.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:9999;'+
        'padding:14px 28px;display:flex;align-items:center;justify-content:space-between;'+
        'background:rgba(10,10,26,0.96);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);'+
        'border-top:1px solid rgba(163,230,53,0.2);box-shadow:0 -4px 24px rgba(0,0,0,0.5);'+
        'font-family:Inter,system-ui,sans-serif;';

      var left=pd.createElement('div');
      left.style.cssText='display:flex;align-items:center;gap:10px;';
      left.innerHTML='<span style="background:linear-gradient(135deg,#a3e635,#22d3ee);'+
        'color:#0a0a1a;font-weight:800;padding:4px 14px;border-radius:12px;font-size:0.85rem">'+
        count+'</span><span style="font-size:0.85rem;color:#b8b8cc;font-weight:600">'+
        'Artikel ausgew\\u00e4hlt</span>';

      var right=pd.createElement('div');
      right.style.cssText='display:flex;gap:10px;';

      var eb=pd.createElement('button');
      eb.innerHTML='F\\u00fcr PromptLab kopieren';
      eb.style.cssText='padding:8px 20px;border-radius:8px;border:none;cursor:pointer;'+
        'background:linear-gradient(135deg,#a3e635,#22d3ee);color:#0a0a1a;'+
        'font-size:12px;font-weight:700;font-family:inherit;transition:all .15s;';
      eb.onmouseenter=function(){this.style.filter='brightness(1.15)'};
      eb.onmouseleave=function(){this.style.filter='none'};
      eb.addEventListener('click',function(){
        if(exportBtn) exportBtn.click();
      });

      var cb=pd.createElement('button');
      cb.innerHTML='\\u2717 Auswahl aufheben';
      cb.style.cssText='padding:8px 16px;border-radius:8px;cursor:pointer;'+
        'background:none;border:1px solid rgba(255,255,255,0.10);color:#b8b8cc;'+
        'font-size:12px;font-weight:600;font-family:inherit;transition:all .15s;';
      cb.onmouseenter=function(){this.style.borderColor='rgba(255,255,255,0.25)'};
      cb.onmouseleave=function(){this.style.borderColor='rgba(255,255,255,0.10)'};
      cb.addEventListener('click',function(){
        if(deselectBtn) deselectBtn.click();
      });

      right.appendChild(eb);
      right.appendChild(cb);
      banner.appendChild(left);
      banner.appendChild(right);
      pd.body.appendChild(banner);
    })();
    </script>
    """, height=0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_filtered_articles(filters: dict):
    """Build the article query from filter dict."""
    return get_articles(
        specialties=tuple(filters["selected_specialties"]) if filters["selected_specialties"] else None,
        sources=tuple(filters["selected_sources"]) if filters["selected_sources"] else None,
        min_score=filters["min_score"],
        date_from=filters["date_from"], date_to=filters["date_to"],
        search_query=filters["search_query"],
        status_filter=filters["status_filter"],
        language=filters["language_filter"],
        study_types=tuple(filters["selected_study_types"]) if filters["selected_study_types"] else None,
        open_access_only=filters["open_access_only"],
    )


def _render_themen_radar(filters: dict):
    """Render the Themen-Radar 2.0 section."""
    from src.processing.trends import compute_trends, get_trend_articles

    # Safe attribute access — protects against stale cache objects
    def _tc(trend, attr, default=""):
        return getattr(trend, attr, default)

    @st.cache_data(ttl=3600, show_spinner=False)
    def _cached_trends(_version=3):
        """Version param busts old cache entries automatically."""
        result = compute_trends(days=7, min_cluster_size=3, use_embeddings=False, max_clusters=6)
        if isinstance(result, tuple):
            return result
        return result, ""

    _trends_result = _cached_trends()
    _trends, _weekly_overview = _trends_result

    if _trends:
        # Section header + legend
        _hdr_col, _legend_col = st.columns([3, 1])
        with _hdr_col:
            st.markdown(
                '<div style="font-size:1.05rem;font-weight:700;margin:16px 0 8px 0">'
                '\U0001f4e1 Themen-Radar</div>'
                '<div style="font-size:0.72rem;color:var(--c-text-muted);margin-bottom:12px">'
                'Automatisch erkannte Trends der letzten 7 Tage</div>',
                unsafe_allow_html=True,
            )
        with _legend_col:
            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            with st.popover("\u2139\ufe0f Legende", use_container_width=False):
                st.markdown(
                    '<div style="font-size:0.78rem;line-height:1.8">'
                    f'<b>\U0001f4ca Dashboard-KPIs</b><br>'
                    f'\u2022 <b>Letzte 7 Tage</b> \u2014 Artikelzahl + Trend vs. vorherige 7 Tage<br>'
                    f'\u2022 <b>\u00d8 Score</b> \u2014 Durchschnittlicher Relevanz-Score der Woche<br>'
                    f'\u2022 <b>Unbearbeitet HQ</b> \u2014 Artikel mit Score \u2265 {SCORE_THRESHOLD_HIGH}, Status \u00abNeu\u00bb<br>'
                    '\u2022 <b>Top-Quelle</b> \u2014 Journal mit den meisten Artikeln (7 Tage)<br>'
                    '\u2022 <b>Sparkline</b> \u2014 Artikel pro Tag, letzte 30 Tage<br>'
                    '<br>'
                    '<b>\U0001f4e1 Themen-Radar</b><br>'
                    '<b>Momentum</b> \u2014 Vergleich der Artikelzahl \u00fcber 3 Wochen:<br>'
                    '\U0001f525 <b>Stark steigend</b> \u2014 3\u00d7 mehr als Vorwoche oder neues Thema<br>'
                    '\u2197 <b>Steigend</b> \u2014 30%+ mehr als Vorwoche<br>'
                    '\u2192 <b>Stabil</b> \u2014 gleichbleibendes Niveau<br>'
                    '\u2198 <b>R\u00fcckl\u00e4ufig</b> \u2014 deutlich weniger Artikel<br>'
                    '<br>'
                    '<b>Studientyp-Badge</b> \u2014 h\u00e4ufigster Evidenztyp im Cluster<br>'
                    '&nbsp;&nbsp;\u2191 = Evidenzlevel steigt gegen\u00fcber Vorwoche<br>'
                    '<br>'
                    '\U0001f500 <b>Cross-Specialty</b> \u2014 Thema breitet sich auf neue Fachgebiete aus<br>'
                    '<br>'
                    '<b>Im Detail-Panel:</b><br>'
                    '\u2022 <b>Journal-Score</b> \u2014 \u00d8 gewichteter Journal-Rang<br>'
                    '\u2022 <b>Arztrelevanz</b> \u2014 \u00d8 Praxis-Relevanz-Score<br>'
                    '\u2022 <b>High-Tier</b> \u2014 Artikel in Top-Quellen (NEJM, Lancet\u2026)<br>'
                    '\u2022 <b>Approval</b> \u2014 Anteil gemerkter Artikel (ab 3 Entscheidungen)<br>'
                    '<br>'
                    '<b>\U0001f525 Trend-Heatmap</b> \u2192 im Insights-Tab'
                    '</div>',
                    unsafe_allow_html=True,
                )

        # Weekly overview banner
        if _weekly_overview:
            st.markdown(
                f'<div class="radar-overview">'
                f'<span class="radar-overview-icon">\U0001f4ca</span>'
                f'<span class="radar-overview-text">{_esc(_weekly_overview)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Hero card — Trend #1
        _hero = _trends[0]
        _hero_label = _esc(_tc(_hero, "smart_label_de") or _hero.topic_label)
        _hero_why = _esc(_tc(_hero, "warum_wichtig_de")) if _tc(_hero, "warum_wichtig_de") else ""
        _hero_summary = _esc(_hero.trend_summary_de[:250]) if _hero.trend_summary_de else ""
        _hero_specs = _hero.specialties[:2]
        _hero_accent_from = SPECIALTY_COLORS.get(_hero_specs[0], ("#a3e635", "rgba(163,230,53,0.10)"))[0] if _hero_specs else "#a3e635"
        _hero_accent_to = SPECIALTY_COLORS.get(_hero_specs[1], ("#22d3ee", "rgba(34,211,238,0.10)"))[0] if len(_hero_specs) > 1 else "#22d3ee"

        _hero_momentum_html = momentum_badge(_tc(_hero, "momentum", "stable"), _hero.growth_rate)
        _hero_evidence_html = evidence_badge(_tc(_hero, "evidence_trend", "stable"), _tc(_hero, "dominant_study_type"))
        _hero_cross_html = cross_specialty_badge(_tc(_hero, "specialty_spread")) if _tc(_hero, "is_cross_specialty", False) else ""

        _hero_badges = f'{_hero_momentum_html} {_hero_evidence_html} {_hero_cross_html}'.strip()

        _hero_why_html = (
            f'<div class="trend-hero-sublabel">Warum wichtig: {_hero_why}</div>'
            if _hero_why else ""
        )
        _hero_summary_html = (
            f'<div class="trend-hero-summary">{_hero_summary}</div>'
            if _hero_summary else ""
        )

        # Stats row
        _hero_spec_counts = _tc(_hero, "specialty_counts", {})
        _n_specs = len(_hero_spec_counts) if _hero_spec_counts else len(_hero.specialties)
        _hero_ht = _tc(_hero, "high_tier_count", 0)
        st.markdown(
            f'<div class="trend-hero" style="--accent-from:{_hero_accent_from};--accent-to:{_hero_accent_to}">'
            f'<div class="trend-hero-accent"></div>'
            f'<div class="trend-hero-body">'
            f'<div class="trend-hero-top">'
            f'<span class="trend-hero-label">{_hero_label}</span>'
            f'<span>{_hero_badges}</span>'
            f'</div>'
            f'{_hero_why_html}'
            f'{_hero_summary_html}'
            f'<div class="trend-hero-stats">'
            f'<div class="trend-hero-stat">'
            f'<span class="trend-hero-stat-value">{_hero.count_current}</span>'
            f'<span class="trend-hero-stat-label">Artikel</span></div>'
            f'<div class="trend-hero-stat">'
            f'<span class="trend-hero-stat-value">\u2300 {_hero.avg_score:.0f}</span>'
            f'<span class="trend-hero-stat-label">Score</span></div>'
            f'<div class="trend-hero-stat">'
            f'<span class="trend-hero-stat-value">{_hero_ht}</span>'
            f'<span class="trend-hero-stat-label">Top-Quelle</span></div>'
            f'<div class="trend-hero-stat">'
            f'<span class="trend-hero-stat-value">{_n_specs}</span>'
            f'<span class="trend-hero-stat-label">Fachgebiete</span></div>'
            f'</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # 3-column grid for trends #2+
        _remaining = _trends[1:7]
        if _remaining:
            _grid_cols = st.columns(min(len(_remaining), 3))
            for ti, trend in enumerate(_remaining):
                col_idx = ti % 3
                with _grid_cols[col_idx]:
                    _t_label = _esc(_tc(trend, "smart_label_de") or trend.topic_label)
                    _t_why_raw = _tc(trend, "warum_wichtig_de")
                    _t_why = _esc(_t_why_raw[:120]) if _t_why_raw else ""
                    _t_spec = trend.specialties[0] if trend.specialties else ""
                    _t_color = SPECIALTY_COLORS.get(_t_spec, ("#8b8ba0", "rgba(139,139,160,0.10)"))[0]

                    _t_mom = momentum_badge(_tc(trend, "momentum", "stable"), trend.growth_rate)
                    _t_ev = evidence_badge(_tc(trend, "evidence_trend", "stable"), _tc(trend, "dominant_study_type"))
                    _t_cross = cross_specialty_badge(_tc(trend, "specialty_spread")) if _tc(trend, "is_cross_specialty", False) else ""

                    _t_why_html = (
                        f'<div class="trend-card-why">{_t_why}</div>'
                        if _t_why else ""
                    )

                    st.markdown(
                        f'<div class="trend-card" style="--spec-color:{_t_color}">'
                        f'<div class="trend-card-label">{_t_label}</div>'
                        f'{_t_why_html}'
                        f'<div class="trend-card-badges">'
                        f'{_t_mom} {_t_ev} {_t_cross}'
                        f'<span class="trend-card-meta">'
                        f'{trend.count_current} Art. &middot; \u2300 {trend.avg_score:.0f}</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

        # Expandable drill-down for each trend
        for trend in _trends[:6]:
            _dl = _tc(trend, "smart_label_de") or trend.topic_label
            with st.expander(
                f"\U0001f4e1 {_dl} ({trend.count_current} Artikel)",
                expanded=False,
            ):
                # Full summary
                if trend.trend_summary_de:
                    st.markdown(
                        f'<div style="font-size:0.8rem;color:var(--c-text);padding:4px 0 8px 0;'
                        f'border-bottom:1px solid var(--c-border);margin-bottom:12px">'
                        f'{_esc(trend.trend_summary_de)}</div>',
                        unsafe_allow_html=True,
                    )

                # 3-column detail grid: Studientypen | Top-Quellen | Signale
                _ev_items = ""
                _ev_levels = _tc(trend, "evidence_levels", {})
                for etype, ecount in sorted(
                    _ev_levels.items(), key=lambda x: -x[1]
                )[:5]:
                    _ev_items += (
                        f'<div class="trend-detail-col-item">'
                        f'<span>{_esc(etype)}</span>'
                        f'<span class="trend-detail-col-value">{ecount}</span></div>'
                    )
                if not _ev_items:
                    _ev_items = '<div class="trend-detail-col-item"><span style="color:var(--c-text-muted)">\u2014</span></div>'

                _tj_items = ""
                for j in trend.top_journals[:4]:
                    _tj_items += (
                        f'<div class="trend-detail-col-item">'
                        f'<span>{_esc(j[:30])}</span></div>'
                    )
                if not _tj_items:
                    _tj_items = '<div class="trend-detail-col-item"><span style="color:var(--c-text-muted)">\u2014</span></div>'

                _sig_items = (
                    f'<div class="trend-detail-col-item">'
                    f'<span>Journal-Score</span>'
                    f'<span class="trend-detail-col-value">{_tc(trend, "avg_journal_score", 0):.1f}</span></div>'
                    f'<div class="trend-detail-col-item">'
                    f'<span>Arztrelevanz</span>'
                    f'<span class="trend-detail-col-value">{_tc(trend, "avg_arztrelevanz", 0):.1f}</span></div>'
                    f'<div class="trend-detail-col-item">'
                    f'<span>High-Tier</span>'
                    f'<span class="trend-detail-col-value">{_tc(trend, "high_tier_count", 0)}/{trend.count_current}</span></div>'
                )
                _td = _tc(trend, "total_decisions", 0)
                if _td >= 3:
                    _sig_items += (
                        f'<div class="trend-detail-col-item">'
                        f'<span>Approval</span>'
                        f'<span class="trend-detail-col-value">{_tc(trend, "approval_rate", 0):.0%}</span></div>'
                    )

                st.markdown(
                    f'<div class="trend-detail-grid">'
                    f'<div class="trend-detail-col">'
                    f'<div class="trend-detail-col-title">Typ</div>{_ev_items}</div>'
                    f'<div class="trend-detail-col">'
                    f'<div class="trend-detail-col-title">Top-Quellen</div>{_tj_items}</div>'
                    f'<div class="trend-detail-col">'
                    f'<div class="trend-detail-col-title">Signale</div>{_sig_items}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Article list
                _trend_arts = get_trend_articles(trend.article_ids[:10])
                for ta in _trend_arts:
                    safe_t = _esc(ta.title)
                    safe_u = _esc(ta.url) if ta.url else ""
                    title_el = (
                        f'<a href="{safe_u}" target="_blank" class="a-title" '
                        f'style="font-size:0.82rem">{safe_t}</a>'
                        if safe_u else f'<span class="a-title" style="font-size:0.82rem">{safe_t}</span>'
                    )
                    _st_type = ""
                    if ta.study_type:
                        _st_type = (
                            f'<span style="font-size:0.6rem;color:var(--c-text-muted);'
                            f'margin-left:4px">{_esc(ta.study_type)}</span>'
                        )
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0">'
                        f'{score_pill(ta.relevance_score)}'
                        f'<span style="flex:1;min-width:0">{title_el}{_st_type}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown('<div style="margin-bottom:16px"></div>', unsafe_allow_html=True)

    else:
        # Empty state for Themen-Radar
        st.markdown(
            '<div style="font-size:1.05rem;font-weight:700;margin:16px 0 8px 0">'
            '\U0001f4e1 Themen-Radar</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="trend-empty">'
            '<div class="trend-empty-icon">\U0001f4e1</div>'
            '<div class="trend-empty-text">Noch keine Trends erkannt</div>'
            '<div class="trend-empty-sub">'
            'Sobald gen\u00fcgend Artikel vorliegen, erkennt Lumio automatisch medizinische Trends.</div>'
            '</div>',
            unsafe_allow_html=True,
        )


def _render_story_radar():
    """Render the Story-Radar section with editorial pitches."""
    from src.processing.story_radar import get_story_pitches, StoryPitch

    @st.cache_data(ttl=3600, show_spinner=False)
    def _cached_pitches():
        return get_story_pitches(days=7, max_pitches=3)

    with st.expander("\U0001f4e1 Story-Radar \u2014 Redaktions-Pitches", expanded=False):
        try:
            pitches = _cached_pitches()
        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).warning("Story-Radar failed: %s", exc)
            pitches = []

        if not pitches:
            st.markdown(
                '<div style="text-align:center;padding:16px 8px;color:var(--c-text-muted);'
                'font-size:0.82rem">'
                'Keine Story-Pitches verf\u00fcgbar \u2014 ben\u00f6tigt Trend-Daten'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        for pi, pitch in enumerate(pitches):
            # Pitch-Score Badge
            if pitch.pitch_score >= 70:
                _ps_cls = "score-high"
            elif pitch.pitch_score >= 40:
                _ps_cls = "score-mid"
            else:
                _ps_cls = "score-low"

            _ps_badge = (
                f'<span class="{_ps_cls}" style="font-size:0.68rem;padding:2px 8px;'
                f'border-radius:6px;font-weight:700">'
                f'Pitch-Score {pitch.pitch_score:.0f}</span>'
            )

            # Headline
            _headline = _esc(pitch.headline_de)

            # Hook
            _hook = _esc(pitch.hook_de)

            # Evidence summary
            _evidence = _esc(pitch.evidence_summary_de)

            # Angle suggestions
            _angles_html = ""
            for ai, angle in enumerate(pitch.angle_suggestions[:3], 1):
                _angles_html += (
                    f'<div style="font-size:0.78rem;color:var(--c-text);'
                    f'padding:2px 0 2px 8px;border-left:2px solid var(--c-accent)">'
                    f'<b>{ai}.</b> {_esc(angle)}</div>'
                )

            # Separator between pitches
            _sep = (
                '<div style="border-top:1px solid var(--c-border);margin:14px 0"></div>'
                if pi > 0 else ""
            )

            st.markdown(
                f'{_sep}'
                f'<div style="margin-bottom:12px">'
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
                f'<span style="font-size:1.0rem;font-weight:700;color:var(--c-text)">'
                f'{_headline}</span>'
                f'{_ps_badge}'
                f'</div>'
                f'<div style="font-size:0.82rem;color:var(--c-text);line-height:1.5;'
                f'margin-bottom:8px">{_hook}</div>'
                f'<div style="font-size:0.75rem;color:var(--c-text-muted);'
                f'background:var(--c-surface);padding:8px 10px;border-radius:6px;'
                f'margin-bottom:8px;line-height:1.4">{_evidence}</div>'
                f'<div style="font-size:0.72rem;font-weight:600;color:var(--c-text-muted);'
                f'margin-bottom:4px">Angles:</div>'
                f'{_angles_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Expandable source articles
            n_sources = len(pitch.source_articles)
            if n_sources > 0:
                with st.expander(
                    f"\U0001f4ce {n_sources} Quell-Artikel",
                    expanded=False,
                ):
                    from src.processing.trends import get_trend_articles
                    _src_arts = get_trend_articles(pitch.source_articles[:10])
                    for sa in _src_arts:
                        safe_t = _esc(sa.title)
                        safe_u = _esc(sa.url) if sa.url else ""
                        title_el = (
                            f'<a href="{safe_u}" target="_blank" class="a-title" '
                            f'style="font-size:0.82rem">{safe_t}</a>'
                            if safe_u
                            else f'<span class="a-title" style="font-size:0.82rem">{safe_t}</span>'
                        )
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0">'
                            f'{score_pill(sa.relevance_score)}'
                            f'<span style="flex:1;min-width:0">{title_el}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )


def _render_favorites_and_watchlists(filters: dict):
    """Render favorites and watchlists sections."""
    st.markdown(
        '<div class="section-divider">'
        '<span class="section-divider-label">Favoriten & Watchlists</span></div>',
        unsafe_allow_html=True,
    )

    # Favoriten = SAVED + legacy APPROVED (both count as "gemerkt")
    _fav_saved = get_articles(status_filter="SAVED", min_score=0)
    _fav_approved = get_articles(status_filter="APPROVED", min_score=0)
    _fav_all = _fav_saved + _fav_approved

    _fav_label = f"\u2b50 Gemerkt ({len(_fav_all)})" if _fav_all else "\u2b50 Gemerkt"
    with st.expander(_fav_label, expanded=False):
        if not _fav_all:
            st.markdown(
                '<div style="text-align:center;padding:12px 8px;color:var(--c-text-muted);'
                'font-size:0.8rem">'
                'Noch keine gemerkten Artikel.<br>'
                'Nutze <b>\u2606</b> (Merken) bei Artikeln, '
                'um sie hier zu sammeln.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            for ri, a in enumerate(_fav_all):
                safe_t = _esc(a.title)
                safe_u = _esc(a.url) if a.url else ""
                title_el = (
                    f'<a href="{safe_u}" target="_blank" class="a-title" '
                    f'style="font-size:0.82rem">{safe_t}</a>'
                    if safe_u else f'<span class="a-title" style="font-size:0.82rem">{safe_t}</span>'
                )
                spec_html = (
                    f' <span class="a-spec" style="font-size:0.6rem">{_esc(a.specialty)}</span>'
                    if a.specialty else ""
                )
                rc1, rc2 = st.columns([12, 1])
                with rc1:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0">'
                        f'{score_pill(a.relevance_score)}'
                        f'<span style="flex:1;min-width:0">{title_el}{spec_html}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with rc2:
                    if st.button("\u21a9", key=f"fav_un_{a.id}_{ri}",
                                  type="secondary", help="Zur\u00fccksetzen auf Neu"):
                        update_article_status(a.id, "NEW")
                        st.toast("Zur\u00fcckgesetzt")
                        st.rerun()

    # --- Watchlists ---
    _wl_all = filters.get("wl_all", [])
    _wl_counts = filters.get("wl_counts", {})

    if _wl_all:
        for wl in _wl_all:
            cnt = _wl_counts.get(wl.id, 0)
            if cnt == 0:
                continue
            wl_label = f"\U0001f3af {wl.name} ({cnt})"
            with st.expander(wl_label, expanded=False):
                _wl_articles = get_watchlist_matches(wl.id, limit=20)
                for wi, a in enumerate(_wl_articles):
                    safe_t = _esc(a.title)
                    safe_u = _esc(a.url) if a.url else ""
                    title_el = (
                        f'<a href="{safe_u}" target="_blank" class="a-title" '
                        f'style="font-size:0.82rem">{safe_t}</a>'
                        if safe_u else f'<span class="a-title" style="font-size:0.82rem">{safe_t}</span>'
                    )
                    spec_html = (
                        f' <span class="a-spec" style="font-size:0.6rem">{_esc(a.specialty)}</span>'
                        if a.specialty else ""
                    )
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0">'
                        f'{score_pill(a.relevance_score)}'
                        f'<span style="flex:1;min-width:0">{title_el}{spec_html}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # --- Watchlist erstellen ---
    with st.expander("\u2795 Neue Watchlist erstellen", expanded=False):
        with st.form("watchlist_form", clear_on_submit=True):
            wl_name = st.text_input("Name", placeholder="z.B. GLP-1 Agonisten")
            wl_keywords = st.text_input(
                "Stichw\u00f6rter (kommagetrennt)",
                placeholder="glp-1, semaglutide, tirzepatide",
            )
            wl_cols = st.columns(2)
            with wl_cols[0]:
                all_specs = get_unique_values("specialty")
                wl_spec = st.selectbox(
                    "Fachgebiet (optional)", ["Alle"] + all_specs
                )
            with wl_cols[1]:
                wl_min_score = st.number_input(
                    "Mindest-Score", min_value=0, max_value=100, value=0, step=5
                )
            wl_submitted = st.form_submit_button("Watchlist anlegen")

            if wl_submitted and wl_name and wl_keywords:
                with get_session() as session:
                    session.add(Watchlist(
                        name=wl_name.strip(),
                        keywords=wl_keywords.strip(),
                        specialty_filter=wl_spec if wl_spec != "Alle" else None,
                        min_score=float(wl_min_score),
                    ))
                    session.commit()
                _existing_articles = get_articles(min_score=0)
                run_watchlist_matching(article_count=len(_existing_articles))
                st.toast(f"Watchlist '{wl_name}' erstellt!")
                st.rerun()


# ---------------------------------------------------------------------------
# PromptLab Export
# ---------------------------------------------------------------------------

def _build_promptlab_export(articles: list, selected_ids: set) -> str:
    """Build a structured Markdown export for PromptLab from selected articles."""
    from components.helpers import _parse_summary

    selected = [a for a in articles if a.id in selected_ids]
    if not selected:
        return ""

    # Sort by score descending
    selected.sort(key=lambda a: a.relevance_score, reverse=True)

    # Detect dominant specialty and topic
    specs = [a.specialty for a in selected if a.specialty]
    main_spec = max(set(specs), key=specs.count) if specs else "Medizin"
    avg_score = sum(a.relevance_score for a in selected) / len(selected)

    # Build evidence summary
    study_types = [a.study_type for a in selected if a.study_type and a.study_type != "Unbekannt"]
    evidence_summary = ", ".join(
        f"{study_types.count(t)}x {t}" for t in dict.fromkeys(study_types)
    ) if study_types else "Diverse"

    lines = [
        f"# Lumio Evidenz-Bundle",
        f"Exportiert: {date.today().strftime('%d.%m.%Y')} | "
        f"Artikel: {len(selected)} | "
        f"Durchschnittl. Score: {avg_score:.0f}/100 | "
        f"Schwerpunkt: {main_spec}",
        f"Evidenz-Mix: {evidence_summary}",
        "",
    ]

    for i, a in enumerate(selected, 1):
        score_label = (
            "Top-Evidenz" if a.relevance_score >= 65
            else "Solide" if a.relevance_score >= 40
            else "News"
        )
        core, detail, praxis = _parse_summary(a.summary_de)

        lines.append(f"## Artikel {i}: {a.title}")
        lines.append(
            f"- **Score:** {a.relevance_score:.0f}/100 ({score_label})"
        )
        if a.journal:
            parts = [a.journal]
            if a.study_type and a.study_type != "Unbekannt":
                parts.append(a.study_type)
            if a.pub_date:
                parts.append(a.pub_date.strftime("%d.%m.%Y"))
            lines.append(f"- **Quelle:** {' | '.join(parts)}")
        if a.specialty:
            lines.append(f"- **Fachgebiet:** {a.specialty}")
        if core:
            lines.append(f"- **KERN:** {core}")
        if praxis:
            lines.append(f"- **PRAXIS:** {praxis}")
        if detail:
            lines.append(f"- **EINORDNUNG:** {detail}")
        if a.doi:
            lines.append(f"- **DOI:** https://doi.org/{a.doi}")
        elif a.url:
            lines.append(f"- **URL:** {a.url}")
        lines.append("")

    return "\n".join(lines)

"""Lumio — Feed tab: Dashboard KPIs, Themen-Radar, article feed, favorites & watchlists."""

from datetime import date

import streamlit as st

from src.config import SCORE_THRESHOLD_HIGH
from src.models import Article, Watchlist, WatchlistMatch, get_session
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


def _load_article_collection_map(article_ids: tuple):
    """Load collection status for a batch of article IDs into session_state."""
    if not article_ids:
        st.session_state["_article_collection_map"] = {}
        return
    from src.db import get_raw_conn
    from sqlalchemy import text
    # Build named params for IN clause
    _params = {f"id_{i}": aid for i, aid in enumerate(article_ids)}
    _in_clause = ", ".join(f":id_{i}" for i in range(len(article_ids)))
    with get_raw_conn() as conn:
        rows = conn.execute(
            text(f"""SELECT ca.article_id, c.name, c.status
                FROM collectionarticle ca
                JOIN collection c ON c.id = ca.collection_id
                WHERE ca.article_id IN ({_in_clause})
                ORDER BY c.updated_at DESC"""),
            _params,
        ).fetchall()
    # Keep first (most recent) collection per article
    coll_map = {}
    for aid, cname, cstatus in rows:
        if aid not in coll_map:
            coll_map[aid] = {"name": cname, "status": cstatus}
    st.session_state["_article_collection_map"] = coll_map


def render_feed(filters: dict):
    """Render the Feed tab content."""
    today_str = date.today().strftime("%d. %B %Y")
    # Dynamic subtitle based on selected time range
    _period_label = filters.get("period_label", "7 Tage")
    _sub_text = f"Dein Feed &middot; {_period_label}"
    st.markdown('<div class="page-header">Feed</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="page-sub">{today_str} &middot; {_sub_text}</div>',
        unsafe_allow_html=True,
    )

    # --- Dashboard KPI Hero Bar (handlungsrelevant) ---
    _dkpi = get_dashboard_kpis()

    # Personal KPIs from DB
    from src.db import get_raw_conn
    from sqlalchemy import text
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    _uid = st.session_state.get("current_user_id", 0)
    _cutoff_48h = (_dt.now(_tz.utc) - _td(hours=48)).isoformat()
    _cutoff_2d = (date.today() - _td(days=2)).isoformat()
    with get_raw_conn() as _kpi_conn:
        # Neu (letzte 48h nach pub_date)
        _new_recent = _kpi_conn.execute(
            text("SELECT COUNT(*) FROM article WHERE created_at >= :cutoff AND status != 'ARCHIVED'"),
            {"cutoff": _cutoff_48h},
        ).fetchone()[0]
        # Fallback: wenn kein Import in 48h, zeige letzte 7 Tage
        if _new_recent == 0:
            _new_recent = _kpi_conn.execute(
                text("SELECT COUNT(*) FROM article WHERE pub_date >= :cutoff AND status != 'ARCHIVED'"),
                {"cutoff": _cutoff_2d},
            ).fetchone()[0]
        _new_label = "seit 48h"

        # Meine Sammlungen (offen)
        _my_colls = _kpi_conn.execute(
            text("SELECT COUNT(*) FROM collection WHERE (user_id = :uid OR assigned_to = :uid) "
                 "AND status NOT IN ('veroeffentlicht', 'verworfen') AND deleted_at IS NULL"),
            {"uid": _uid},
        ).fetchone()[0]

        # Zugewiesen an mich (von anderen erstellt)
        _assigned = _kpi_conn.execute(
            text("SELECT COUNT(*) FROM collection WHERE assigned_to = :uid AND user_id != :uid "
                 "AND status NOT IN ('veroeffentlicht', 'verworfen') AND deleted_at IS NULL"),
            {"uid": _uid},
        ).fetchone()[0]

        # Ungelesene Kommentare / Notifications
        _unread = _kpi_conn.execute(
            text("SELECT COUNT(*) FROM notification WHERE user_id = :uid AND is_read = 0"),
            {"uid": _uid},
        ).fetchone()[0]

    st.markdown(f"""
    <div class="dash-bar">
        <div class="dash-card dash-card-accent" title="Artikel mit Score \u2265 {SCORE_THRESHOLD_HIGH} in deinem aktuellen Zeitraum.">
            <div class="dash-value">{_dkpi['unreviewed_hq']}</div>
            <div class="dash-label">\U0001f525 Top-Artikel</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">Score \u2265 {SCORE_THRESHOLD_HIGH}</div>
        </div>
        <div class="dash-card" title="Neue Artikel der letzten 48 Stunden.">
            <div class="dash-value">{_new_recent}</div>
            <div class="dash-label">\U0001f195 Neu</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">{_new_label}</div>
        </div>
        <div class="dash-card" title="Deine offenen Sammlungen in der Redaktion.">
            <div class="dash-value">{_my_colls}</div>
            <div class="dash-label">\U0001f4c1 Sammlungen</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">offen</div>
        </div>
        <div class="dash-card" title="Sammlungen, die dir von Kollegen zugewiesen wurden.">
            <div class="dash-value">{_assigned}</div>
            <div class="dash-label">\U0001f4cc Zugewiesen</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">von Kollegen</div>
        </div>
        <div class="dash-card" title="Ungelesene Kommentare und Erwähnungen.">
            <div class="dash-value">{_unread}</div>
            <div class="dash-label">\U0001f4ac Kommentare</div>
            <div class="dash-sub" style="color:var(--c-text-muted)">ungelesen</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Themen-Radar moved to end of feed (expander before articles blocks rendering) ---

    # -- TODAY'S HIGHLIGHTS (data-driven, no LLM tokens) --
    @st.cache_data(ttl=300, show_spinner=False)
    def _get_today_highlights():
        from src.db import get_raw_conn
        from sqlalchemy import text
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        _cutoff_48h = (_dt.now(_tz.utc) - _td(hours=48)).isoformat()
        _cutoff_24h = (_dt.now(_tz.utc) - _td(hours=24)).isoformat()
        with get_raw_conn() as conn:
            # Top 5 articles from last 48h by score
            top = conn.execute(text("""
                SELECT title, relevance_score, specialty, journal
                FROM article
                WHERE created_at >= :cutoff_48h
                  AND relevance_score >= 60
                ORDER BY relevance_score DESC
                LIMIT 5
            """), {"cutoff_48h": _cutoff_48h}).fetchall()
            # Count new articles today
            today_count = conn.execute(
                text("SELECT COUNT(*) FROM article WHERE created_at >= :cutoff_24h"),
                {"cutoff_24h": _cutoff_24h},
            ).fetchone()[0]
            # Top specialty today
            top_spec = conn.execute(text("""
                SELECT specialty, COUNT(*) as cnt FROM article
                WHERE created_at >= :cutoff_48h
                  AND specialty IS NOT NULL AND specialty != ''
                GROUP BY specialty ORDER BY cnt DESC LIMIT 1
            """), {"cutoff_48h": _cutoff_48h}).fetchone()
        return top, today_count, top_spec

    _highlights, _today_n, _top_spec = _get_today_highlights()
    if _highlights:
        _hl_items = []
        for title, score, spec, journal in _highlights[:3]:
            _short = title[:65] + ("..." if len(title) > 65 else "")
            _src = f" ({journal})" if journal else ""
            _hl_items.append(f"<b>{score:.0f}</b> {_esc(_short)}{_esc(_src)}")
        _spec_hint = f" · Top-Fachgebiet: {_esc(_top_spec[0])}" if _top_spec else ""
        st.markdown(
            f'<div style="padding:10px 16px;border-radius:10px;margin-bottom:16px;'
            f'background:var(--c-surface);border:1px solid var(--c-border);font-size:0.75rem">'
            f'<b>📌 Heute relevant</b> · {_today_n} neue Artikel{_spec_hint}<br>'
            f'{"  ·  ".join(_hl_items)}'
            f'</div>',
            unsafe_allow_html=True,
        )

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
        _sort_labels = {
            "score": "Trending \U0001f525", "high_score": "High Score \U0001f3af",
            "date": "Datum \u2193", "source": "Quelle A\u2013Z",
            "editorial": "Redaktions-Tipp \u2728", "hidden_gems": "Unentdeckte Perlen \U0001f48e",
            "clinical": "Klinische Dringlichkeit \U0001fa7a",
        }
        _sort_hint = _sort_labels.get(filters.get("sort_by", "score"), "")
        st.markdown(
            f'<div class="section-divider">'
            f'<span class="section-divider-label">Artikel-Feed</span>'
            f'<span style="font-size:0.65rem;color:var(--c-text-muted);margin-left:8px">'
            f'Sortiert nach {_sort_hint}</span></div>',
            unsafe_allow_html=True,
        )


    # When watchlist filter is active, load matched articles directly
    # (bypasses date/score filters that would hide watchlist hits)
    if _active_wl_id and _wl_article_ids:
        from sqlmodel import select as _sel2, col as _col2
        with get_session() as _ws:
            articles = list(_ws.exec(
                _sel2(Article).where(_col2(Article.id).in_(_wl_article_ids))
            ))
        # Still respect language filter if set
        _lang = filters.get("language_filter")
        if _lang and _lang not in ("Alle",):
            _lc = "de" if _lang in ("Deutsch", "DE") else "en"
            articles = [a for a in articles if a.language == _lc]
        articles.sort(key=lambda a: a.relevance_score or 0, reverse=True)
    else:
        articles = _get_filtered_articles(filters)

    # --- PromptLab Export ---
    if "selected_articles" not in st.session_state:
        st.session_state.selected_articles = set()

    _sel_ids = st.session_state.selected_articles

    # Clean up JS-injected export elements (wrapped in try/except for robustness)
    try:
        if not st.session_state.get("_promptlab_export"):
            st.components.v1.html("""
            <script>
            (function(){
              var pd=window.parent.document;
              ['lumio-export-actions','lumio-export-banner'].forEach(function(id){
                var el=pd.getElementById(id); if(el) el.remove();
              });
              pd.querySelectorAll('.lumio-export-overlay').forEach(function(el){el.remove()});
            })();
            </script>
            """, height=0)
    except Exception:
        pass

    # Show export result if just generated
    if st.session_state.get("_promptlab_export"):
        # Auto-scroll to export section + toast on first render
        if st.session_state.pop("_export_just_done", False):
            st.toast("Export erstellt!", icon="\u2705")

        # Anchor for auto-scroll
        st.markdown('<div id="lumio-export-result"></div>', unsafe_allow_html=True)

        _n_articles = st.session_state["_promptlab_export"].count("## Artikel")
        _is_esanum = st.session_state.get("theme", "dark") == "esanum"

        # --- Big copy button + close button ABOVE the code block ---
        _copy_cols = st.columns([5, 2, 1])
        with _copy_cols[0]:
            st.markdown(f"""
            <div style="padding:4px 0">
                <div style="font-weight:700;font-size:0.9rem;color:var(--c-text)">Export bereit</div>
                <div style="font-size:0.75rem;color:var(--c-text-muted);margin-top:2px">
                    {_n_articles} Artikel &middot; In PromptLab einfügen</div>
            </div>""", unsafe_allow_html=True)
        with _copy_cols[1]:
            if st.button("📋 In Zwischenablage kopieren", key="_export_copy_btn",
                         type="primary", use_container_width=True):
                pass  # JS handles the actual copy below
        with _copy_cols[2]:
            if st.button("✕ Schließen", key="_export_close_btn", use_container_width=True):
                st.session_state.pop("_promptlab_export", None)
                st.session_state.selected_articles = set()
                st.session_state["_sel_gen"] = st.session_state.get("_sel_gen", 0) + 1
                for key in list(st.session_state.keys()):
                    if key.startswith("sel_"):
                        del st.session_state[key]
                st.rerun()

        st.code(st.session_state["_promptlab_export"], language="markdown")

        # Close export via query param trigger (legacy support)
        if st.query_params.get("_feed_action") == "close_export":
            st.query_params.pop("_feed_action")
            st.session_state.pop("_promptlab_export", None)
            st.session_state.selected_articles = set()
            st.session_state["_sel_gen"] = st.session_state.get("_sel_gen", 0) + 1
            for key in list(st.session_state.keys()):
                if key.startswith("sel_"):
                    del st.session_state[key]
            st.rerun()

        # JS: auto-scroll + wire the copy button to clipboard
        import json as _json
        _safe_export = _json.dumps(st.session_state["_promptlab_export"])
        st.components.v1.html(f"""
        <script>
        (function(){{
          var pd=window.parent.document;

          // Scroll to export
          var anchor=pd.getElementById('lumio-export-result');
          if(anchor) anchor.scrollIntoView({{behavior:'smooth',block:'start'}});

          // Find the "📋 In Zwischenablage kopieren" button and wire clipboard copy
          var allBtns=pd.querySelectorAll('button');
          var copyBtn=null;
          for(var i=0;i<allBtns.length;i++){{
            if(allBtns[i].textContent.indexOf('Zwischenablage')>=0){{
              copyBtn=allBtns[i]; break;
            }}
          }}
          if(!copyBtn) return;

          // Prevent Streamlit rerun on click — intercept
          copyBtn.addEventListener('click',function(e){{
            e.stopPropagation();

            var exportText={_safe_export};
            var ta=pd.createElement('textarea');
            ta.value=exportText;
            ta.style.cssText='position:fixed;left:-9999px;top:-9999px;opacity:0';
            pd.body.appendChild(ta);
            ta.select();
            var ok=false;
            try {{ ok=pd.execCommand('copy'); }} catch(ex) {{}}
            ta.remove();
            if(!ok && window.parent.navigator.clipboard) {{
              window.parent.navigator.clipboard.writeText(exportText).catch(function(){{}});
              ok=true;
            }}

            // Visual feedback on the button itself
            var origText=copyBtn.textContent;
            copyBtn.textContent='\\u2705 Kopiert!';
            setTimeout(function(){{ copyBtn.textContent=origText; }},2500);

            // Toast
            var toast=pd.createElement('div');
            toast.style.cssText='position:fixed;top:24px;left:50%;transform:translateX(-50%) translateY(-20px);'+
              'z-index:99999;padding:14px 28px;border-radius:12px;'+
              'background:rgba(34,197,94,0.95);color:#fff;font-weight:700;font-size:0.85rem;'+
              'font-family:Inter,system-ui,sans-serif;box-shadow:0 8px 32px rgba(34,197,94,0.3);'+
              'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);'+
              'display:flex;align-items:center;gap:10px;'+
              'opacity:0;transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1);';
            toast.textContent='\\u2705 Export in Zwischenablage kopiert';
            pd.body.appendChild(toast);
            setTimeout(function(){{toast.style.opacity='1';toast.style.transform='translateX(-50%) translateY(0)'}},10);
            setTimeout(function(){{
              toast.style.opacity='0';toast.style.transform='translateX(-50%) translateY(-20px)';
              setTimeout(function(){{toast.remove()}},300);
            }},3000);
          }},true);  // useCapture=true to fire before Streamlit's handler
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

    def _do_add_to_collection():
        """Add selected articles to a collection. Collection ID comes from JS via components.v1.html."""
        # JS sets the collection ID via a tiny HTML component that writes to session state
        coll_id = st.session_state.get("_bulk_collection_id")
        if not coll_id:
            return
        from views.cowork import add_article_to_collection
        from components.auth import track_activity
        added = 0
        for aid in st.session_state.get("selected_articles", set()):
            if add_article_to_collection(coll_id, aid):
                added += 1
        track_activity("collection_bulk_add", f"collection={coll_id} added={added}")
        st.session_state["_bulk_add_result"] = added
        st.session_state.pop("_bulk_collection_id", None)

    # Action triggers via query_params — NO hidden buttons needed
    _qp = st.query_params
    if _qp.get("_feed_action") == "export":
        st.query_params.pop("_feed_action")
        _do_export()
        st.rerun()
    elif _qp.get("_feed_action") == "deselect":
        st.query_params.pop("_feed_action")
        _do_deselect()
        st.rerun()
    elif _qp.get("_feed_action") == "collection":
        st.query_params.pop("_feed_action")
        st.session_state["_show_collection_picker"] = True
        st.rerun()
    elif _qp.get("_feed_action") == "bookmark_all":
        st.query_params.pop("_feed_action")
        from components.helpers import toggle_bookmark, is_bookmarked
        _uid = st.session_state.get("current_user_id", 0)
        _bm_count = 0
        for _aid in list(st.session_state.get("selected_articles", set())):
            if not is_bookmarked(_aid, user_id=_uid):
                toggle_bookmark(_aid, user_id=_uid)
                _bm_count += 1
        # Invalidate bookmark cache so sidebar updates
        st.session_state.pop("_bookmarked_ids", None)
        st.toast(f"{_bm_count} Artikel gemerkt ✓")
        st.session_state.selected_articles = set()
        st.rerun()
    elif _qp.get("_feed_action") == "hide_all":
        st.query_params.pop("_feed_action")
        _hid_count = 0
        for _aid in list(st.session_state.get("selected_articles", set())):
            update_article_status(_aid, "rejected")
            _hid_count += 1
        st.toast(f"{_hid_count} Artikel ausgeblendet")
        st.session_state.selected_articles = set()
        st.rerun()

    # Show toast if bulk add just happened
    if "_bulk_add_result" in st.session_state:
        _added = st.session_state.pop("_bulk_add_result")
        st.toast(f"{_added} Artikel zur Sammlung hinzugefügt ✓")

    # --- Streamlit-native "Zur Sammlung hinzufügen" when articles selected ---
    _sel_count_native = len(st.session_state.get("selected_articles", set()))
    if _sel_count_native > 0 and st.session_state.get("_show_collection_picker"):
        from views.cowork import get_user_collections as _get_user_colls, add_article_to_collection as _add_to_coll
        _my_colls = _get_user_colls(st.session_state.get("current_user_id", 0))

        # Scroll anchor + auto-scroll to this section
        _is_esanum = st.session_state.get("theme", "dark") == "esanum"
        _picker_bg = "rgba(0,84,97,0.04)" if _is_esanum else "rgba(132,204,22,0.06)"
        _picker_border = "rgba(0,84,97,0.15)" if _is_esanum else "rgba(132,204,22,0.15)"
        st.markdown(
            f'<div id="lumio-collection-picker" style="background:{_picker_bg};border:1px solid {_picker_border};'
            f'border-radius:10px;padding:12px 16px;margin-bottom:12px">'
            f'<div style="font-size:0.8rem;font-weight:700;margin-bottom:8px">'
            f'📁 {_sel_count_native} Artikel zur Sammlung hinzufügen</div></div>',
            unsafe_allow_html=True,
        )
        # Auto-scroll to collection picker
        st.components.v1.html("""<script>
        (function(){
            var el = window.parent.document.getElementById('lumio-collection-picker');
            if(el) el.scrollIntoView({behavior:'smooth', block:'center'});
        })();
        </script>""", height=0)

        _cp1, _cp2 = st.columns([3, 1])
        with _cp1:
            if _my_colls:
                _coll_options = [("new", "➕ Neue Sammlung erstellen...")] + [(str(c[0]), c[1]) for c in _my_colls]
                _selected_coll = st.selectbox(
                    "Sammlung",
                    _coll_options,
                    format_func=lambda x: x[1],
                    label_visibility="collapsed",
                    key="_bulk_coll_select",
                )
            else:
                _selected_coll = ("new", "")
                st.info("Noch keine Sammlungen. Erstelle eine neue:")

        with _cp2:
            if _selected_coll[0] == "new":
                _new_name = st.text_input("Name", placeholder="Sammlungsname", key="_new_coll_name",
                                          label_visibility="collapsed")
            else:
                _new_name = None

        _ba1, _ba2 = st.columns(2)
        with _ba1:
            if st.button("✓ Hinzufügen", key="_bulk_add_confirm", use_container_width=True, type="primary"):
                from components.auth import track_activity as _track
                if _selected_coll[0] == "new":
                    if _new_name and _new_name.strip():
                        # Create new collection + add articles in a single transaction
                        from datetime import datetime as _dt, timezone as _tz
                        from src.db import get_raw_conn
                        from sqlalchemy import text as _text
                        _now = _dt.now(_tz.utc).isoformat()
                        _uid = st.session_state.get("current_user_id", 0)
                        with get_raw_conn() as _conn:
                            _row = _conn.execute(
                                _text("INSERT INTO collection (user_id, name, status, created_at, updated_at) "
                                      "VALUES (:uid, :name, 'recherche', :now, :now) RETURNING id"),
                                {"uid": _uid, "name": _new_name.strip(), "now": _now},
                            ).fetchone()
                            _new_coll_id = _row[0]
                            _added = 0
                            for _aid in st.session_state.selected_articles:
                                _conn.execute(
                                    _text("INSERT INTO collectionarticle (collection_id, article_id, added_at) "
                                          "VALUES (:coll_id, :aid, :now) ON CONFLICT DO NOTHING"),
                                    {"coll_id": _new_coll_id, "aid": _aid, "now": _now},
                                )
                                _added += 1
                            _conn.execute(
                                _text("UPDATE collection SET updated_at = :now WHERE id = :cid"),
                                {"now": _now, "cid": _new_coll_id},
                            )
                        _track("collection_create", f"name={_new_name.strip()}")
                        _track("collection_bulk_add", f"collection={_new_coll_id} added={_added}")
                        st.session_state.pop("_show_collection_picker", None)
                        st.toast(f'Sammlung "{_new_name.strip()}" erstellt + {_added} Artikel hinzugefügt ✓')
                        st.rerun()
                    else:
                        st.error("Bitte einen Namen eingeben.")
                else:
                    _coll_id = int(_selected_coll[0])
                    _added = sum(1 for aid in st.session_state.selected_articles if _add_to_coll(_coll_id, aid))
                    _track("collection_bulk_add", f"collection={_coll_id} added={_added}")
                    st.session_state.pop("_show_collection_picker", None)
                    st.toast(f"{_added} Artikel zur Sammlung hinzugefügt ✓")
                    st.rerun()
        with _ba2:
            if st.button("Abbrechen", key="_bulk_add_cancel", use_container_width=True):
                st.session_state.pop("_show_collection_picker", None)
                st.rerun()

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
        ITEMS_INITIAL = 50
        ITEMS_PER_PAGE = 50
        if "show_count" not in st.session_state:
            st.session_state.show_count = ITEMS_INITIAL

        visible = articles[:st.session_state.show_count]

        # Batch-load editorial memory for visible articles
        visible_ids = tuple(a.id for a in visible if a.id is not None)
        memory_data = _load_memory_batch(visible_ids) if visible_ids else {}

        # Load collection status for visible articles (for "In Arbeit" / "Veröffentlicht" badges)
        _load_article_collection_map(visible_ids)

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
            if st.button(f"\u2b07 Weitere {min(remaining, ITEMS_PER_PAGE)} laden ({remaining} verbleibend)",
                         type="primary", key="load_more"):
                st.session_state.show_count += ITEMS_PER_PAGE
                st.rerun()

    # -- Favoriten & Watchlists moved to sidebar --

    # -- NATIVE ACTION BAR (after article loop so selected_articles is current) --
    _sel_ids = st.session_state.get("selected_articles", set())
    _sel_count = len(_sel_ids)

    # Floating action bar — visual HTML in parent DOM + hidden Streamlit buttons for actions
    _sel_ids_final = st.session_state.get("selected_articles", set())
    _sel_count_final = len(_sel_ids_final)

    # Hidden Streamlit buttons — these actually work, the JS bar clicks them
    if _sel_count_final > 0:
        # Place real buttons in a hidden container
        _fab_container = st.container()
        with _fab_container:
            st.markdown('<div id="lumio-fab-buttons" style="display:none">', unsafe_allow_html=True)
            _hc1, _hc2, _hc3, _hc4 = st.columns(4)
            with _hc1:
                if st.button("hd", key="_fab_hide"):
                    for _aid in list(_sel_ids_final):
                        update_article_status(_aid, "REJECTED")
                    st.toast(f"{_sel_count_final} ausgeblendet")
                    st.session_state.selected_articles = set()
                    st.rerun()
            with _hc2:
                if st.button("cl", key="_fab_coll"):
                    st.session_state["_show_collection_picker"] = True
                    st.rerun()
            with _hc3:
                if st.button("ex", key="_fab_export"):
                    _do_export()
                    st.rerun()
            with _hc4:
                if st.button("ds", key="_fab_desel"):
                    _do_deselect()
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Visual floating bar + JS to find and click hidden buttons
    if _sel_count_final > 0:
        _is_esanum = st.session_state.get("theme", "dark") == "esanum"
        st.components.v1.html(f"""
        <script>
        (function(){{
            var pd = window.parent.document;
            var old = pd.getElementById('lumio-fab');
            if(old) old.remove();

            var count = {_sel_count_final};
            var isLight = {'true' if _is_esanum else 'false'};
            var cs = window.parent.getComputedStyle(pd.documentElement);
            var cAccent = cs.getPropertyValue('--c-accent').trim();
            var cBg = cs.getPropertyValue('--c-bg').trim();
            var cText = cs.getPropertyValue('--c-text').trim();
            var cTextSec = cs.getPropertyValue('--c-text-secondary').trim();
            var cBorder = cs.getPropertyValue('--c-border').trim();
            var cSurface = cs.getPropertyValue('--c-surface-solid').trim() || '#0e0e22';

            // Find the hidden Streamlit buttons by their key
            var allBtns = pd.querySelectorAll('button[kind="secondary"]');
            var fabBtns = {{}};
            var keys = ['_fab_bm','_fab_hide','_fab_coll','_fab_export','_fab_desel'];
            allBtns.forEach(function(b) {{
                keys.forEach(function(k) {{
                    if(b.textContent.trim() === k.replace('_fab_','').substring(0,2))
                        fabBtns[k] = b;
                }});
            }});

            var bar = pd.createElement('div');
            bar.id = 'lumio-fab';
            bar.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;'+
                'padding:12px 28px;display:flex;align-items:center;gap:10px;'+
                'font-family:Inter,system-ui,sans-serif;'+
                'background:'+cSurface+';border-top:2px solid '+cAccent+';'+
                (isLight
                    ? 'box-shadow:0 -4px 20px rgba(0,0,0,0.08);'
                    : 'box-shadow:0 -4px 20px rgba(0,0,0,0.4);');

            var badge = pd.createElement('span');
            badge.style.cssText = 'font-weight:800;font-size:0.85rem;padding:4px 14px;border-radius:12px;'+
                'background:'+cAccent+';color:#FFFFFF;';
            badge.textContent = count;
            bar.appendChild(badge);

            var label = pd.createElement('span');
            label.style.cssText = 'font-size:0.82rem;font-weight:600;margin-right:auto;'+
                'color:'+cTextSec+';';
            label.textContent = 'ausgewählt';
            bar.appendChild(label);

            var btnStyle = 'padding:8px 16px;border-radius:8px;font-size:0.78rem;font-weight:600;'+
                'cursor:pointer;font-family:inherit;transition:background .15s,border-color .15s,color .15s;'+
                'border:1px solid '+cBorder+';background:transparent;color:'+cText+';';

            var primaryStyle = 'padding:8px 16px;border-radius:8px;font-size:0.78rem;font-weight:700;'+
                'cursor:pointer;font-family:inherit;border:none;'+
                'background:'+cAccent+';color:#FFFFFF;';

            function mkBtn(text, style, hiddenKey) {{
                var b = pd.createElement('button');
                b.textContent = text;
                b.style.cssText = style;
                b.onclick = function(){{
                    // Find and click the real hidden Streamlit button
                    var real = pd.querySelector('button[data-testid="stBaseButton-secondary"]');
                    // Search all buttons for matching text
                    var allB = pd.querySelectorAll('button');
                    for(var i=0;i<allB.length;i++) {{
                        var txt = allB[i].textContent.trim();
                        if(txt === hiddenKey) {{
                            allB[i].click();
                            return;
                        }}
                    }}
                }};
                return b;
            }}

            bar.appendChild(mkBtn('✕ Ausblenden', btnStyle, 'hd'));
            bar.appendChild(mkBtn('📁 Zur Sammlung', btnStyle, 'cl'));
            bar.appendChild(mkBtn('📋 Für PromptLab', primaryStyle, 'ex'));
            bar.appendChild(mkBtn('✕ Auswahl aufheben', btnStyle, 'ds'));

            pd.body.appendChild(bar);

            // Hide the real buttons container
            var hiddenDiv = pd.getElementById('lumio-fab-buttons');
            if(hiddenDiv) hiddenDiv.style.display = 'none';
            // Also hide parent containers of the hidden buttons
            allBtns.forEach(function(b) {{
                var txt = b.textContent.trim();
                if(['hd','cl','ex','ds'].indexOf(txt) >= 0) {{
                    var p = b.closest('[data-testid="stHorizontalBlock"]');
                    if(p) p.style.display = 'none';
                }}
            }});
        }})();
        </script>
        """, height=0)
    else:
        st.components.v1.html("""
        <script>
        (function(){
            var old = window.parent.document.getElementById('lumio-fab');
            if(old) old.remove();
        })();
        </script>
        """, height=0)

    # Legacy JS banner removed (cleaned up)

    # --- Themen-Radar moved to own tab ---

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_filtered_articles(filters: dict):
    """Build the article query from filter dict, then sort client-side."""
    articles = get_articles(
        specialties=tuple(filters["selected_specialties"]) if filters["selected_specialties"] else None,
        sources=tuple(filters["selected_sources"]) if filters["selected_sources"] else None,
        source_categories=tuple(filters["selected_categories"]) if filters.get("selected_categories") else None,
        min_score=filters["min_score"],
        date_from=filters["date_from"], date_to=filters["date_to"],
        search_query=filters["search_query"],
        status_filter=filters["status_filter"],
        language=filters["language_filter"],
        study_types=tuple(filters["selected_study_types"]) if filters["selected_study_types"] else None,
        has_summary_only=filters.get("has_summary_only", False),
        open_access_only=filters["open_access_only"],
    )

    # Sort client-side (avoids cache miss for each sort change)
    sort_by = filters.get("sort_by", "score")

    if sort_by == "high_score":
        articles.sort(key=lambda a: a.relevance_score or 0, reverse=True)

    elif sort_by == "date":
        articles.sort(key=lambda a: (a.pub_date or date.min, a.created_at), reverse=True)

    elif sort_by == "source":
        articles.sort(key=lambda a: (a.source or "", -(a.pub_date or date.min).toordinal()))

    elif sort_by == "editorial":
        # Redaktions-Tipp: Score * Aktualität * Hat-Zusammenfassung
        # = sofort publizierbar
        today = date.today()
        def _editorial_key(a):
            score = a.relevance_score or 0
            days_old = max(1, (today - (a.pub_date or today)).days + 1)
            freshness = 1.0 / days_old  # neuere Artikel bevorzugt
            has_summary = 1.5 if a.summary_de else 1.0
            return score * freshness * has_summary
        articles.sort(key=_editorial_key, reverse=True)

    elif sort_by == "hidden_gems":
        # Unentdeckte Perlen: Hoher Score + seltene Quelle
        # Quellen-Häufigkeit berechnen
        source_counts: dict = {}
        for a in articles:
            s = a.source or "?"
            source_counts[s] = source_counts.get(s, 0) + 1
        max_count = max(source_counts.values()) if source_counts else 1
        def _gem_key(a):
            score = a.relevance_score or 0
            src = a.source or "?"
            # Seltene Quellen bekommen Bonus (invertierte Häufigkeit)
            rarity = 1.0 - (source_counts.get(src, 1) / max_count)
            return score * (1.0 + rarity * 0.5)
        articles.sort(key=_gem_key, reverse=True)

    elif sort_by == "clinical":
        # Klinische Dringlichkeit: v2 clinical_action_relevance * Neuigkeit
        import json as _json
        today = date.today()
        def _clinical_key(a):
            clinical_score = 0.0
            if a.score_breakdown:
                try:
                    bd = _json.loads(a.score_breakdown)
                    scores = bd.get("scores", {})
                    clin = scores.get("clinical_action_relevance", {})
                    clinical_score = clin.get("score", 0) if isinstance(clin, dict) else 0
                except (ValueError, TypeError, AttributeError):
                    pass
            # Fallback: use overall score as proxy
            if clinical_score == 0:
                clinical_score = (a.relevance_score or 0) * 0.2
            days_old = max(1, (today - (a.pub_date or today)).days + 1)
            freshness = 1.0 / (days_old ** 0.5)  # sanfter Abfall
            return clinical_score * freshness
        articles.sort(key=_clinical_key, reverse=True)

    # else: "score" — already sorted by DB query (default)

    return articles


def _render_themen_radar(filters: dict):
    """Render the Themen-Radar 2.0 section.

    Reads pre-computed trends from TrendCache (filled by pipeline).
    Falls back to live computation only if cache is empty.
    """
    from src.processing.trends import load_trends_cache, compute_trends, get_trend_articles

    # Safe attribute access — protects against stale cache objects
    def _tc(trend, attr, default=""):
        return getattr(trend, attr, default)

    @st.cache_data(ttl=600, show_spinner=False)
    def _cached_trends(_version=7):
        """Load from TrendCache (pipeline pre-computed). Fast: ~5ms."""
        cached = load_trends_cache(max_age_hours=48)
        if cached:
            return cached
        # Fallback: compute live (only if pipeline never ran)
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
            with st.expander("\u2139\ufe0f Legende"):
                st.markdown(
                    '<div style="font-size:0.78rem;line-height:1.8">'
                    '<b>\U0001f4e1 Themen-Radar</b><br>'
                    'Automatisch erkannte Themen-Cluster der letzten 7 Tage.<br><br>'
                    '<b>Momentum</b> zeigt die Entwicklung:<br>'
                    '\U0001f525 <b>Stark steigend</b> \u2013 3\u00d7 mehr Artikel als Vorwoche<br>'
                    '\u2197 <b>Steigend</b> \u2013 sp\u00fcrbarer Anstieg (30%+)<br>'
                    '\u2192 <b>Stabil</b> \u2013 gleichbleibendes Niveau<br>'
                    '\u2198 <b>R\u00fcckl\u00e4ufig</b> \u2013 weniger Artikel als Vorwoche<br>'
                    '<br>'
                    '<b>Typ</b> \u2013 h\u00e4ufigster Studientyp (Review, Leitlinie, RCT, News, ...)<br>'
                    '&nbsp;&nbsp;\u2191 = Evidenzniveau steigt gegen\u00fcber Vorwoche<br>'
                    '<br>'
                    '<b>Im Detail-Bereich:</b><br>'
                    '\u2022 <b>Quellenautorität</b> \u2013 Renommee der Quellen (0\u201312)<br>'
                    '\u2022 <b>Klinische Relevanz</b> \u2013 Praxisrelevanz des Trends (0\u201320)<br>'
                    '\u2022 <b>Top-Quellen</b> \u2013 Anteil aus NEJM, Lancet, JAMA etc.<br>'
                    '\u2022 <b>Approval</b> \u2013 Anteil gemerkter Artikel (ab 3 Bewertungen)<br>'
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
        # Clean summary: strip LABEL:/WICHTIG: prefixed format, show full text
        _hero_summary_raw = _hero.trend_summary_de or ""
        # Remove LABEL:...;;; and WICHTIG: prefixes if present
        if ";;;" in _hero_summary_raw:
            _hero_summary_raw = _hero_summary_raw.split(";;;")[-1].strip()
        if _hero_summary_raw.upper().startswith("WICHTIG:"):
            _hero_summary_raw = _hero_summary_raw[8:].strip()
        if _hero_summary_raw.upper().startswith("LABEL:"):
            _hero_summary_raw = _hero_summary_raw[6:].strip()
        _hero_summary = _esc(_hero_summary_raw) if _hero_summary_raw else ""
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
                    _t_why = _esc(_t_why_raw) if _t_why_raw else ""
                    _t_spec = trend.specialties[0] if trend.specialties else ""
                    _t_color = SPECIALTY_COLORS.get(_t_spec, ("#8b8ba0", "rgba(139,139,160,0.10)"))[0]

                    _t_mom = momentum_badge(_tc(trend, "momentum", "stable"), trend.growth_rate)
                    _t_ev = evidence_badge(_tc(trend, "evidence_trend", "stable"), _tc(trend, "dominant_study_type"))
                    _t_cross = cross_specialty_badge(_tc(trend, "specialty_spread")) if _tc(trend, "is_cross_specialty", False) else ""

                    _t_why_html = (
                        f'<div class="trend-card-why">{_t_why}</div>'
                        if _t_why else ""
                    )

                    # Mini sparkline for card
                    _card_spark = _tc(trend, "sparkline_data", [])
                    _card_spark_html = ""
                    if _card_spark:
                        _csm = max(_card_spark) if max(_card_spark) > 0 else 1
                        _cbars = ""
                        for _ci, _cv in enumerate(_card_spark):
                            _ch = max(2, int(_cv / _csm * 14))
                            _cop = "0.4" if _ci < 3 else "1"
                            _cbars += f'<span class="spark-bar" style="height:{_ch}px;background:#a3e635;opacity:{_cop}"></span>'
                        _card_spark_html = f'<span class="sparkline-mini" style="height:16px;margin-left:6px">{_cbars}</span>'

                    # Urgency dot
                    _card_urg = _tc(trend, "editorial_urgency", "beobachten")
                    _card_urg_html = f'<span class="urgency-dot {_card_urg}" style="margin-right:4px"></span>'

                    st.markdown(
                        f'<div class="trend-card" style="--spec-color:{_t_color}">'
                        f'<div class="trend-card-label">{_card_urg_html}{_t_label}{_card_spark_html}</div>'
                        f'{_t_why_html}'
                        f'<div class="trend-card-badges">'
                        f'{_t_mom} {_t_ev} {_t_cross}'
                        f'<span class="trend-card-meta">'
                        f'{trend.count_current} Art. &middot; \u2300 {trend.avg_score:.0f}</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

        # Expandable drill-down for each trend
        for trend in _trends:
            _dl = _tc(trend, "smart_label_de") or trend.topic_label
            # Urgency indicator in expander title
            _urgency = _tc(trend, "editorial_urgency", "beobachten")
            _urgency_icon = {"sofort": "\U0001f534", "diese_woche": "\U0001f7e1", "beobachten": "\u26aa"}.get(_urgency, "\u26aa")
            with st.expander(
                f"{_urgency_icon} {_dl} ({trend.count_current} Artikel)",
                expanded=False,
            ):
                # --- v2: Editorial Action Banner ---
                _ed_action = _tc(trend, "editorial_action_de", "")
                if _ed_action:
                    st.markdown(
                        f'<div class="editorial-action {_urgency}">'
                        f'<span class="urgency-dot {_urgency}"></span>'
                        f'{_esc(_ed_action)}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # --- v2: Sparkline + Trend Phase + Source Diversity (inline row) ---
                _sparkline = _tc(trend, "sparkline_data", [])
                _phase = _tc(trend, "trend_phase", "")
                _src_rating = _tc(trend, "source_diversity_rating", "niedrig")
                _src_count = _tc(trend, "source_diversity_count", 0)
                _first_mover = _tc(trend, "first_mover_chance", False)

                _spark_html = ""
                if _sparkline:
                    _spark_max = max(_sparkline) if max(_sparkline) > 0 else 1
                    _bars = ""
                    for si, sv in enumerate(_sparkline):
                        h = max(2, int(sv / _spark_max * 18))
                        op = "0.4" if si < 3 else "1"
                        _bars += f'<span class="spark-bar" style="height:{h}px;background:#a3e635;opacity:{op}"></span>'
                    _spark_html = f'<span class="sparkline-mini">{_bars}</span>'

                _phase_html = f'<span class="trend-phase {_phase}">{_phase}</span>' if _phase else ""
                _src_html = f'<span class="src-pill {_src_rating}">{_src_count} Quellen</span>'
                _fm_html = '<span class="first-mover-badge">First Mover</span>' if _first_mover else ""

                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">'
                    f'{_spark_html} {_phase_html} {_src_html} {_fm_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # --- v2: Storyline Pitches ---
                _pitches = _tc(trend, "storyline_pitches", [])
                if _pitches:
                    st.markdown(
                        '<div style="font-size:0.68rem;font-weight:700;color:var(--c-text-muted);'
                        'text-transform:uppercase;letter-spacing:0.5px;margin:8px 0 4px">Artikel-Ideen</div>',
                        unsafe_allow_html=True,
                    )
                    for p in _pitches[:3]:
                        _angle = _esc(p.get("angle_de", ""))
                        _fmt = _esc(p.get("format", ""))
                        if _angle:
                            st.markdown(
                                f'<div class="pitch-card">'
                                f'<span class="pitch-format">{_fmt}</span>'
                                f'<span style="font-size:0.78rem;color:var(--c-text)">{_angle}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                # --- v2: Source Diversity Details ---
                _src_names = _tc(trend, "source_diversity_names", [])
                _has_german = _tc(trend, "has_german_coverage", False)
                if _src_names:
                    _src_pills = " ".join(
                        f'<span style="display:inline-block;padding:1px 6px;border-radius:4px;'
                        f'font-size:0.58rem;font-weight:600;background:rgba(255,255,255,0.06);'
                        f'color:#a0a0b8;margin:1px">{_esc(s[:20])}</span>'
                        for s in _src_names[:6]
                    )
                    _german_badge = (
                        '<span style="font-size:0.6rem;color:#4ade80;font-weight:600;margin-left:6px">'
                        '\u2713 Dt. Fachpresse</span>'
                        if _has_german else
                        '<span style="font-size:0.6rem;color:#22d3ee;font-weight:600;margin-left:6px">'
                        'Noch keine dt. Berichterstattung</span>'
                    )
                    st.markdown(
                        f'<div class="src-diversity">{_src_pills}{_german_badge}</div>',
                        unsafe_allow_html=True,
                    )

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
                    f'<span>Quellenautorität</span>'
                    f'<span class="trend-detail-col-value">{_tc(trend, "avg_journal_score", 0):.1f}/12</span></div>'
                    f'<div class="trend-detail-col-item">'
                    f'<span>Klinische Relevanz</span>'
                    f'<span class="trend-detail-col-value">{_tc(trend, "avg_arztrelevanz", 0):.1f}/20</span></div>'
                    f'<div class="trend-detail-col-item">'
                    f'<span>Top-Quellen</span>'
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

    # Favoriten = personal bookmarks (per user)
    from components.helpers import get_bookmarked_articles, toggle_bookmark
    _fav_all = get_bookmarked_articles()

    _fav_label = f"\u2b50 Meine Merkliste ({len(_fav_all)})" if _fav_all else "\u2b50 Meine Merkliste"
    with st.expander(_fav_label, expanded=False):
        if not _fav_all:
            st.markdown(
                '<div style="text-align:center;padding:12px 8px;color:var(--c-text-muted);'
                'font-size:0.8rem">'
                'Noch keine gemerkten Artikel.<br>'
                'Nutze <b>☆</b> (Merken) bei Artikeln, '
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
                    if st.button("✕", key=f"fav_un_{a.id}_{ri}",
                                  type="secondary", help="Aus Merkliste entfernen"):
                        toggle_bookmark(a.id)
                        # Clear cached bookmark IDs
                        st.session_state.pop("_bookmarked_ids", None)
                        st.toast("Aus Merkliste entfernt")
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

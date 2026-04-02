"""Lumio — Cowork Tab: Redaktions-Feed, Sammlungen, Kommentare, Zuweisungen."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import streamlit as st

from src.config import DB_PATH
from components.auth import track_activity
import re as _re


# ---------------------------------------------------------------------------
# @-Mention helpers
# ---------------------------------------------------------------------------

def _get_all_usernames() -> dict[str, int]:
    """Return {lowercase_username: user_id} mapping, cached."""
    if "_mention_users" not in st.session_state:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute("SELECT id, username, display_name FROM user").fetchall()
        finally:
            conn.close()
        mapping = {}
        for uid, uname, dname in rows:
            mapping[uname.lower()] = uid
            mapping[dname.lower()] = uid
        st.session_state["_mention_users"] = mapping
    return st.session_state["_mention_users"]


def _parse_mentions(text: str) -> set[int]:
    """Extract user IDs from @mentions in text. Returns set of user_ids."""
    users = _get_all_usernames()
    mentioned = set()
    for match in _re.finditer(r'@(\w+)', text):
        name = match.group(1).lower()
        if name in users:
            mentioned.add(users[name])
    return mentioned


def _highlight_mentions(text: str) -> str:
    """Replace @username with styled HTML span."""
    users = _get_all_usernames()

    def _replace(m):
        name = m.group(1)
        if name.lower() in users:
            return f'<span style="color:var(--c-accent);font-weight:600">@{name}</span>'
        return m.group(0)

    return _re.sub(r'@(\w+)', _replace, text)


# ---------------------------------------------------------------------------
# Conflict Radar — detect overlapping collections
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def _check_collection_overlaps(user_id: int):
    """Show warnings for collections with overlapping articles."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        overlaps = conn.execute("""
            SELECT ca1.collection_id, ca2.collection_id,
                   c1.name, c2.name, u1.display_name, u2.display_name,
                   COUNT(*) as shared
            FROM collectionarticle ca1
            JOIN collectionarticle ca2 ON ca1.article_id = ca2.article_id
                AND ca1.collection_id < ca2.collection_id
            JOIN collection c1 ON ca1.collection_id = c1.id AND c1.status NOT IN ('published', 'veröffentlicht') AND c1.deleted_at IS NULL
            JOIN collection c2 ON ca2.collection_id = c2.id AND c2.status NOT IN ('published', 'veröffentlicht') AND c2.deleted_at IS NULL
            JOIN user u1 ON c1.user_id = u1.id
            JOIN user u2 ON c2.user_id = u2.id
            WHERE c1.user_id != c2.user_id
            GROUP BY ca1.collection_id, ca2.collection_id
            HAVING COUNT(*) >= 2
            ORDER BY shared DESC
            LIMIT 5
        """).fetchall()
    finally:
        conn.close()

    if overlaps:
        with st.expander(f"⚠️ {len(overlaps)} Themen-Überschneidungen erkannt", expanded=False):
            for cid1, cid2, name1, name2, author1, author2, shared in overlaps:
                st.markdown(
                    f'<div style="font-size:0.78rem;padding:6px 10px;margin:3px 0;'
                    f'background:rgba(251,191,36,0.08);border-left:3px solid #fbbf24;'
                    f'border-radius:4px">'
                    f'<b>{name1}</b> ({author1}) und <b>{name2}</b> ({author2}) '
                    f'teilen <b>{shared} Artikel</b>. Abstimmung empfohlen.'
                    f'</div>',
                    unsafe_allow_html=True,
                )


def _generate_collection_draft(
    collection_id: int,
    collection_name: str,
    technique: str = "cot",
    pro_modes: set | None = None,
    custom_experts: list | None = None,
    fs_examples: list | None = None,
) -> str | None:
    """Generate an editorial draft using the advanced Prompt Builder system.

    Supports 5 prompting techniques and 12 Pro-Modes for maximum quality.
    """
    try:
        from src.processing.prompt_builder import build_article_prompt

        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute("""
                SELECT a.title, a.abstract, a.journal, a.pub_date, a.summary_de,
                       a.relevance_score, a.url, a.doi
                FROM collectionarticle ca
                JOIN article a ON a.id = ca.article_id
                WHERE ca.collection_id = ?
                ORDER BY a.relevance_score DESC
            """, (collection_id,)).fetchall()

            if len(rows) < 2:
                return None

            # Build article dicts for prompt builder (max 10 articles)
            articles = []
            for row in rows[:10]:
                title, abstract, journal, pub_date, summary_de, score = row[:6]
                url = row[6] if len(row) > 6 else ""
                doi = row[7] if len(row) > 7 else ""
                articles.append({
                    "title": title,
                    "abstract": abstract or "",
                    "journal": journal or "",
                    "pub_date": str(pub_date) if pub_date else "",
                    "summary_de": summary_de or "",
                    "url": url or "",
                    "doi": doi or "",
                })

            # Load briefing data
            briefing_row = conn.execute("""
                SELECT article_format, tonality, target_length, target_audience,
                       key_message, internal_notes
                FROM collection WHERE id = ?
            """, (collection_id,)).fetchone()
        finally:
            conn.close()

        briefing = {}
        if briefing_row:
            briefing = {
                "article_format": briefing_row[0],
                "tonality": briefing_row[1],
                "target_length": briefing_row[2],
                "target_audience": briefing_row[3],
                "key_message": briefing_row[4],
                "internal_notes": briefing_row[5],
            }

        # Build prompt using the advanced prompt builder
        prompt = build_article_prompt(
            articles=articles,
            briefing=briefing,
            collection_name=collection_name,
            technique=technique,
            pro_modes=pro_modes,
            custom_experts=custom_experts,
            fs_examples=fs_examples,
        )

        # Estimate tokens and choose max_tokens accordingly
        input_chars = len(prompt)
        # Rough estimate: 1 token ~ 4 chars
        estimated_input_tokens = input_chars // 4
        # Output should be proportional — at least 2000 tokens for a good article
        max_output = max(2000, min(4000, estimated_input_tokens))

        from src.config import get_provider_chain
        from src.llm_client import cached_chat_completion

        providers = get_provider_chain("artikel_entwurf")
        result = cached_chat_completion(
            providers=providers,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_output,
        )
        return result
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Status config
# ---------------------------------------------------------------------------
_STATUS_CONFIG = {
    "recherche":       ("📋", "Recherche",       "#3b82f6"),
    "in_arbeit":       ("✍️", "In Arbeit",       "#f59e0b"),
    "review":          ("🔍", "Review",           "#f97316"),
    "veroeffentlicht": ("✅", "Veröffentlicht",  "#4ade80"),
    "verworfen":       ("❌", "Verworfen",       "#8b8ba0"),
}


def _conn():
    return sqlite3.connect(str(DB_PATH))


def _get_all_users() -> list[tuple[int, str]]:
    """Return [(id, display_name), ...] for all non-admin users."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, display_name FROM user WHERE role != 'admin' ORDER BY display_name"
    ).fetchall()
    conn.close()
    return rows


@st.cache_data(ttl=300, show_spinner=False)
def _get_all_users_including_admin() -> list[tuple[int, str]]:
    """Return [(id, display_name), ...] for all users. Cached 5min."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, display_name FROM user ORDER BY display_name"
    ).fetchall()
    conn.close()
    return rows


def _create_notification(user_id: int, ntype: str, message: str,
                         collection_id: int | None = None):
    """Create a notification for a user. Fire-and-forget."""
    try:
        conn = _conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO notification (user_id, type, message, link_collection_id, is_read, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (user_id, ntype, message, collection_id, now),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_unread_count(user_id: int) -> int:
    """Get count of unread notifications for a user."""
    conn = _conn()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM notification WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_cowork():
    """Render the Cowork tab — team collaboration overview."""
    user = st.session_state.get("current_user", {})
    user_id = user.get("id", 0)

    # Check for notifications
    unread = get_unread_count(user_id)

    st.markdown(
        '<div class="page-header">Redaktion</div>'
        '<div class="page-sub">Wer arbeitet woran? Sammlungen &amp; Redaktions-Feed</div>',
        unsafe_allow_html=True,
    )

    # Track only once per session, not on every rerun
    if not st.session_state.get("_cowork_tracked"):
        track_activity("page_view", "tab:Redaktion")
        st.session_state["_cowork_tracked"] = True

    # Handle Kanban drag & drop status updates (must run before tabs render)
    _kanban_move_param = st.query_params.get("kanban_move", "")
    if _kanban_move_param and ":" in _kanban_move_param:
        try:
            _km_id, _km_status = _kanban_move_param.split(":", 1)
            _km_cid = int(_km_id)
            del st.query_params["kanban_move"]
            _valid_statuses = ["recherche", "in_arbeit", "review", "veroeffentlicht"]
            if _km_status in _valid_statuses:
                _km_conn = _conn()
                # Verify user owns or is assigned to this collection
                _km_row = _km_conn.execute(
                    "SELECT user_id, assigned_to FROM collection WHERE id = ?",
                    (_km_cid,)
                ).fetchone()
                if _km_row and (_km_row[0] == user_id or (_km_row[1] is not None and _km_row[1] == user_id)):
                    _km_conn.execute(
                        "UPDATE collection SET status = ?, updated_at = datetime('now') WHERE id = ?",
                        (_km_status, _km_cid),
                    )
                    _km_conn.commit()
                    track_activity("kanban_move", f"collection_id={_km_cid} -> {_km_status}")
                _km_conn.close()
                st.cache_data.clear()
                st.rerun()
        except Exception as _km_err:
            st.toast(f"Fehler beim Verschieben: {_km_err}", icon="⚠️")

    # Show notifications banner if any
    if unread > 0:
        _render_notifications(user_id)

    tab_feed, tab_my, tab_kanban, tab_cal, tab_new = st.tabs([
        "📡 Redaktions-Feed", "📁 Meine Sammlungen", "📋 Board",
        "📅 Kalender", "➕ Neue Sammlung"
    ])

    with tab_feed:
        _check_collection_overlaps(user_id)
        _render_team_feed(user_id)

    with tab_my:
        _render_my_collections(user_id)

    with tab_kanban:
        _render_kanban_board(user_id)

    with tab_cal:
        _render_calendar_view(user_id)

    with tab_new:
        _render_create_collection(user_id)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _render_notifications(user_id: int):
    """Show unread notifications — split into team and system banners for admins."""
    conn = _conn()
    try:
        notifs = conn.execute("""
            SELECT id, type, message, link_collection_id, created_at
            FROM notification
            WHERE user_id = ? AND is_read = 0
            ORDER BY created_at DESC
            LIMIT 20
        """, (user_id,)).fetchall()
    finally:
        conn.close()

    if not notifs:
        return

    # Auto-expire old system notifications (>48h) to keep the list clean
    try:
        conn2 = _conn()
        conn2.execute(
            "UPDATE notification SET is_read = 1 "
            "WHERE user_id = ? AND is_read = 0 "
            "AND type = 'health_check' "
            "AND created_at < datetime('now', '-48 hours')",
            (user_id,),
        )
        conn2.commit()
        conn2.close()
    except Exception:
        pass

    # Split into team (assignment, comment, mention) vs system (health_check, etc.)
    team_notifs = [(nid, ntype, msg, coll_id, ts)
                   for nid, ntype, msg, coll_id, ts in notifs
                   if ntype in ("assignment", "comment", "mention")]
    system_notifs = [(nid, ntype, msg, coll_id, ts)
                     for nid, ntype, msg, coll_id, ts in notifs
                     if ntype not in ("assignment", "comment", "mention")]

    _ICON_MAP = {
        "assignment": "👤",
        "comment": "💬",
        "mention": "@",
        "health_check": "⚙️",
    }

    # --- System notifications (admin-only, collapsed by default) ---
    if system_notifs:
        with st.expander(f"⚙️ System ({len(system_notifs)})", expanded=False):
            sys_html = ""
            for nid, ntype, msg, coll_id, ts in system_notifs[:8]:
                ts_short = ts[11:16] if len(ts) > 16 else ts[:10]
                icon = _ICON_MAP.get(ntype, "⚠️")
                sys_html += (
                    f'<div style="font-size:0.7rem;padding:2px 0;line-height:1.4">'
                    f'{icon} {msg[:120]} '
                    f'<span style="color:var(--c-text-muted)">· {ts_short}</span>'
                    f'</div>'
                )
            if len(system_notifs) > 8:
                sys_html += f'<div style="font-size:0.65rem;color:var(--c-text-muted);margin-top:4px">+{len(system_notifs) - 8} weitere</div>'
            st.markdown(sys_html, unsafe_allow_html=True)

    # --- Team notifications (blue banner) ---
    if team_notifs:
        team_html = (
            '<div style="background:var(--c-accent-light);border:1px solid var(--c-accent);'
            'border-radius:8px;padding:10px 14px;margin-bottom:8px">'
            '<div style="font-size:0.75rem;font-weight:700;margin-bottom:6px">'
            f'🔔 Neue Benachrichtigungen ({len(team_notifs)})</div>'
        )
        for nid, ntype, msg, coll_id, ts in team_notifs[:5]:
            ts_short = ts[11:16] if len(ts) > 16 else ts[:10]
            icon = _ICON_MAP.get(ntype, "💬")
            team_html += (
                f'<div style="font-size:0.72rem;padding:2px 0">'
                f'{icon} {msg} '
                f'<span style="color:var(--c-text-muted)">· {ts_short}</span>'
                f'</div>'
            )
        if len(team_notifs) > 5:
            team_html += f'<div style="font-size:0.65rem;color:var(--c-text-muted);margin-top:4px">+{len(team_notifs) - 5} weitere</div>'
        team_html += '</div>'
        st.markdown(team_html, unsafe_allow_html=True)

    if st.button("✓ Alle gelesen", key="mark_read_btn"):
        conn2 = _conn()
        try:
            conn2.execute(
                "UPDATE notification SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn2.commit()
        finally:
            conn2.close()
        st.rerun()


# ---------------------------------------------------------------------------
# Team feed — what everyone is working on
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def _load_digest_data(user_id: int):
    """Load digest data with 60s cache."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        new_colls = conn.execute(
            "SELECT COUNT(*) FROM collection WHERE created_at > ? AND deleted_at IS NULL", (since,)
        ).fetchone()[0]
        new_comments = conn.execute(
            "SELECT COUNT(*) FROM collectioncomment WHERE created_at > ?", (since,)
        ).fetchone()[0]
        status_changes = 0  # Simplified - no status_log table yet
        upcoming = conn.execute("""
            SELECT name, target_date, assigned_to FROM collection
            WHERE target_date BETWEEN date('now') AND date('now', '+2 days')
              AND status NOT IN ('published', 'veröffentlicht')
              AND deleted_at IS NULL
        """).fetchall()
        my_open = conn.execute("""
            SELECT name, status, target_date FROM collection
            WHERE (user_id = ? OR assigned_to = ?)
              AND status NOT IN ('published', 'veröffentlicht')
              AND deleted_at IS NULL
        """, (user_id, user_id)).fetchall()
    finally:
        conn.close()
    return new_colls, new_comments, status_changes, upcoming, my_open


def _render_activity_digest(user_id: int):
    """Show a compact 24h activity summary at top of feed."""
    new_colls, new_comments, status_changes, upcoming, my_open = _load_digest_data(user_id)

    # Only show if there's activity
    if new_colls + new_comments + status_changes == 0 and not upcoming and not my_open:
        return

    parts = []
    if new_colls:
        parts.append(f"📁 {new_colls} neue Sammlung{'en' if new_colls != 1 else ''}")
    if new_comments:
        parts.append(f"💬 {new_comments} Kommentar{'e' if new_comments != 1 else ''}")
    if status_changes:
        parts.append(f"🔄 {status_changes} Status-Update{'s' if status_changes != 1 else ''}")
    n_open = len(my_open) if my_open else 0
    if n_open:
        parts.append(f"📌 {n_open} offene Zuweisung{'en' if n_open != 1 else ''}")

    digest_text = " · ".join(parts)

    deadline_text = ""
    if upcoming:
        dl_items = [f"<b>{n}</b> ({d})" for n, d, _ in upcoming[:3]]
        deadline_text = f'<br>⏰ Fällig: {", ".join(dl_items)}'

    st.markdown(
        f'<div style="background:var(--c-surface);border:1px solid var(--c-border);'
        f'border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.75rem">'
        f'<b>📊 Letzte 24h:</b> {digest_text}{deadline_text}'
        f'</div>',
        unsafe_allow_html=True,
    )


@st.fragment
def _render_team_feed(current_user_id: int):
    """Show a chronological activity feed of all collections."""
    _render_activity_digest(current_user_id)
    conn = _conn()
    c = conn.cursor()

    collections = c.execute("""
        SELECT
            c.id, c.name, c.description, c.status,
            c.target_platform, c.target_date, c.published_url,
            c.created_at, c.updated_at,
            u.display_name,
            (SELECT COUNT(*) FROM collectionarticle ca WHERE ca.collection_id = c.id) as article_count,
            c.assigned_to,
            (SELECT display_name FROM user WHERE id = c.assigned_to) as assignee_name,
            (SELECT COUNT(*) FROM collectioncomment cc WHERE cc.collection_id = c.id) as comment_count
        FROM collection c
        JOIN user u ON c.user_id = u.id
        WHERE c.deleted_at IS NULL
        ORDER BY c.updated_at DESC
    """).fetchall()

    if not collections:
        st.info(
            "Noch keine Sammlungen vorhanden. "
            "Erstelle eine neue Sammlung oder füge Artikel über den Feed hinzu."
        )
        conn.close()
        return

    active = [r for r in collections if r[3] in ("recherche", "in_arbeit")]
    done = [r for r in collections if r[3] == "veroeffentlicht"]

    if active or done:
        st.markdown(
            f'<div style="font-size:0.75rem;color:var(--c-text-muted);margin-bottom:8px">'
            f'🔴 {len(active)} aktive Themen · '
            f'✅ {len(done)} veröffentlicht</div>',
            unsafe_allow_html=True,
        )

    for coll in collections:
        (cid, name, desc, status, platform, target_date, pub_url,
         created, updated, author, art_count, assigned_to,
         assignee_name, comment_count) = coll

        icon, label, color = _STATUS_CONFIG.get(status, ("•", status, "#8b8ba0"))

        # Time display
        try:
            updated_dt = datetime.fromisoformat(updated)
            now = datetime.now(timezone.utc)
            diff = now - updated_dt
            if diff.days == 0:
                time_str = f"Heute, {updated[:16].split('T')[1][:5]}"
            elif diff.days == 1:
                time_str = f"Gestern, {updated[:16].split('T')[1][:5]}"
            elif diff.days < 7:
                time_str = f"Vor {diff.days} Tagen"
            else:
                time_str = updated[:10]
        except Exception:
            time_str = updated[:10] if updated else ""

        platform_str = ""  # always esanum, no need to display
        target_str = f' · Geplant: {target_date}' if target_date else ""
        pub_str = (
            f' · <a href="{pub_url}" target="_blank" '
            f'style="color:#4ade80">🔗 Zum Artikel</a>'
            if pub_url else ""
        )
        assignee_str = f' · 👤 <b>{assignee_name}</b>' if assignee_name else ""
        comment_str = f' · 💬 {comment_count}' if comment_count else ""

        card_html = f"""
        <div style="background:var(--c-surface);border-left:3px solid {color};
            border-radius:8px;padding:12px 16px;margin-bottom:4px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <span style="font-size:0.7rem;color:var(--c-text-muted)">{time_str} — <b>{author}</b></span>
                <span style="font-size:0.7rem;padding:2px 8px;border-radius:4px;
                    background:{color}22;color:{color}">{icon} {label}</span>
            </div>
            <div style="font-size:0.95rem;font-weight:700;margin-bottom:4px">{name}</div>
            <div style="font-size:0.75rem;color:var(--c-text-secondary)">
                📄 {art_count} Artikel{assignee_str}{platform_str}{target_str}{comment_str}{pub_str}
            </div>
        """
        if desc:
            card_html += f'<div style="font-size:0.72rem;color:var(--c-text-muted);margin-top:4px;font-style:italic">{desc}</div>'
        card_html += "</div>"

        st.markdown(card_html, unsafe_allow_html=True)

        # Articles + Comments expander
        with st.expander(f"📄 {art_count} Artikel · 💬 {comment_count} Kommentare", expanded=False):
            # Articles
            articles = c.execute("""
                SELECT a.id, a.title, a.journal, a.pub_date, a.relevance_score, ca.note
                FROM collectionarticle ca
                JOIN article a ON ca.article_id = a.id
                WHERE ca.collection_id = ?
                ORDER BY a.relevance_score DESC
            """, (cid,)).fetchall()

            if articles:
                for art in articles:
                    aid, title, journal, pub_date, score, note = art
                    score_str = f'<span style="color:#4ade80;font-weight:700">{score}</span> ' if score else ""
                    note_str = f' · <i>{note}</i>' if note else ""
                    st.markdown(
                        f'<div style="font-size:0.72rem;padding:3px 0;border-bottom:1px solid var(--c-border-subtle)">'
                        f'{score_str}{title[:80]} '
                        f'<span style="color:var(--c-text-muted)">· {journal or ""} · {pub_date or ""}{note_str}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # Comments
            st.markdown('<div style="margin-top:10px"></div>', unsafe_allow_html=True)
            _render_comments(cid, current_user_id)

    conn.close()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@st.fragment
def _render_comments(collection_id: int, current_user_id: int, ctx: str = "feed"):
    """Render comment thread for a collection. ctx differentiates duplicate keys."""
    conn = _conn()
    comments = conn.execute("""
        SELECT cc.id, cc.text, cc.created_at, u.display_name
        FROM collectioncomment cc
        JOIN user u ON cc.user_id = u.id
        WHERE cc.collection_id = ?
        ORDER BY cc.created_at ASC
    """, (collection_id,)).fetchall()

    if comments:
        for cid, text, ts, author in comments:
            ts_short = ts[11:16] if len(ts) > 16 else ts[:10]
            day = ts[:10] if len(ts) > 10 else ""
            # Highlight @mentions in comment text
            display_text = _highlight_mentions(text)
            st.markdown(
                f'<div style="font-size:0.72rem;padding:4px 8px;margin:2px 0;'
                f'background:var(--c-surface);border-radius:6px">'
                f'<b>{author}</b> '
                f'<span style="color:var(--c-text-muted)">{day} {ts_short}</span><br>'
                f'{display_text}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # New comment input
    _comment_key = f"new_comment_{ctx}_{collection_id}"
    _c1, _c2 = st.columns([4, 1])
    with _c1:
        new_comment = st.text_input(
            "Kommentar",
            placeholder="Kommentar schreiben...",
            key=_comment_key,
            label_visibility="collapsed",
        )
    with _c2:
        if st.button("💬", key=f"send_comment_{ctx}_{collection_id}",
                      use_container_width=True):
            if new_comment and new_comment.strip():
                now = datetime.now(timezone.utc).isoformat()
                conn2 = _conn()
                conn2.execute(
                    "INSERT INTO collectioncomment (collection_id, user_id, text, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (collection_id, current_user_id, new_comment.strip(), now),
                )
                # Update collection timestamp
                conn2.execute(
                    "UPDATE collection SET updated_at = ? WHERE id = ?",
                    (now, collection_id),
                )
                conn2.commit()

                # Notify collection owner + assignee
                current_name = st.session_state.get("current_user", {}).get("display_name", "?")
                coll_info = conn2.execute(
                    "SELECT user_id, assigned_to, name FROM collection WHERE id = ?",
                    (collection_id,),
                ).fetchone()
                conn2.close()

                if coll_info:
                    owner_id, assignee_id, coll_name = coll_info
                    # Standard notifications for owner + assignee
                    notify_ids = {owner_id, assignee_id} - {None, current_user_id}
                    for uid in notify_ids:
                        _create_notification(
                            uid, "comment",
                            f'{current_name} kommentierte "{coll_name}": {new_comment.strip()[:60]}',
                            collection_id,
                        )
                    # @-Mention notifications (targeted)
                    mentioned_ids = _parse_mentions(new_comment.strip())
                    mention_notify = mentioned_ids - notify_ids - {current_user_id}
                    for uid in mention_notify:
                        _create_notification(
                            uid, "mention",
                            f'{current_name} hat dich in "{coll_name}" erwähnt: {new_comment.strip()[:60]}',
                            collection_id,
                        )

                track_activity("comment", f"collection={collection_id}")
                st.rerun()

    conn.close()


# ---------------------------------------------------------------------------
# My collections — manage own collections
# ---------------------------------------------------------------------------

@st.fragment
def _render_my_collections(user_id: int):
    """Show and manage the current user's collections."""
    conn = _conn()

    # Batch: load all collections + counts in one query
    my_colls = conn.execute("""
        SELECT
            c.id, c.name, c.status, c.target_platform, c.target_date,
            c.published_url, c.description, c.assigned_to,
            (SELECT COUNT(*) FROM collectionarticle ca WHERE ca.collection_id = c.id) as cnt,
            u.display_name as owner_name,
            (SELECT display_name FROM user WHERE id = c.assigned_to) as assignee_name
        FROM collection c
        JOIN user u ON c.user_id = u.id
        WHERE (c.user_id = ? OR c.assigned_to = ?)
          AND c.deleted_at IS NULL
        ORDER BY c.updated_at DESC
    """, (user_id, user_id)).fetchall()

    if not my_colls:
        st.info("Du hast noch keine Sammlungen. Erstelle eine im Tab '➕ Neue Sammlung'.")
        conn.close()
        return

    # Batch: preload ALL comments for all my collections in one query
    _coll_ids = [c[0] for c in my_colls]
    _id_placeholders = ",".join("?" * len(_coll_ids))
    _all_comments = {}
    for row in conn.execute(f"""
        SELECT cc.collection_id, cc.user_id, cc.text, cc.created_at, u.display_name
        FROM collectioncomment cc
        JOIN user u ON cc.user_id = u.id
        WHERE cc.collection_id IN ({_id_placeholders})
        ORDER BY cc.created_at ASC
    """, _coll_ids).fetchall():
        _all_comments.setdefault(row[0], []).append(row)

    # Batch: preload ALL draft versions
    _all_drafts = {}
    for row in conn.execute(f"""
        SELECT collection_id, id, version, draft_text, feedback_text,
               generated_at, generated_by_user, generated_by_model, is_active
        FROM collection_draft
        WHERE collection_id IN ({_id_placeholders})
        ORDER BY version DESC
    """, _coll_ids).fetchall():
        _all_drafts.setdefault(row[0], []).append(row)

    conn.close()

    all_users = _get_all_users_including_admin()

    for coll in my_colls:
        cid, name, status, platform, target_date, pub_url, desc, assigned_to, cnt, owner_name, assignee_name = coll
        icon, label, color = _STATUS_CONFIG.get(status, ("•", status, "#8b8ba0"))

        assignee_badge = f' · 👤 {assignee_name}' if assignee_name else ""
        st.markdown(
            f'<div style="background:var(--c-surface);border-left:3px solid {color};'
            f'border-radius:8px;padding:10px 14px;margin-bottom:8px">'
            f'<div style="font-size:0.9rem;font-weight:700">{icon} {name}</div>'
            f'<div style="font-size:0.72rem;color:var(--c-text-muted)">'
            f'📄 {cnt} Artikel · {label} · Von: {owner_name}{assignee_badge}'
            f'{" · " + platform if platform else ""}'
            f'{" · Geplant: " + str(target_date) if target_date else ""}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # Expander header shows current status icon
        _norm_s = status or "recherche"
        _s_aliases = {"research": "recherche", "published": "veroeffentlicht",
                      "in arbeit": "in_arbeit"}
        _norm_s = _s_aliases.get(_norm_s, _norm_s)
        _s_icon = _STATUS_CONFIG.get(_norm_s, ("📋", "Recherche", "#3b82f6"))[0]
        _s_label = _STATUS_CONFIG.get(_norm_s, ("📋", "Recherche", "#3b82f6"))[1]

        with st.expander(f"{_s_icon} {_s_label}: {name}", expanded=False):
            # Editable name
            new_name = st.text_input(
                "Sammlungsname",
                value=name,
                key=f"coll_name_{cid}",
            )
            _ec1, _ec2 = st.columns(2)
            with _ec1:
                # Normalize status to known keys
                _status_keys = list(_STATUS_CONFIG.keys())
                _norm_status = status
                _status_aliases = {
                    "research": "recherche", "published": "veroeffentlicht",
                    "veröffentlicht": "veroeffentlicht", "in_arbeit": "in_arbeit",
                    "in arbeit": "in_arbeit", "draft": "recherche",
                }
                if _norm_status not in _status_keys:
                    _norm_status = _status_aliases.get(_norm_status, "recherche")
                _status_idx = _status_keys.index(_norm_status) if _norm_status in _status_keys else 0

                new_status = st.selectbox(
                    "Status",
                    _status_keys,
                    index=_status_idx,
                    format_func=lambda s: f"{_STATUS_CONFIG[s][0]} {_STATUS_CONFIG[s][1]}",
                    key=f"coll_status_{cid}",
                )
            with _ec2:
                # Assignment dropdown
                user_options = [(0, "— Niemand —")] + all_users
                current_idx = 0
                for i, (uid, uname) in enumerate(user_options):
                    if uid == (assigned_to or 0):
                        current_idx = i
                        break
                new_assignee = st.selectbox(
                    "Zuweisen an",
                    user_options,
                    index=current_idx,
                    format_func=lambda u: u[1],
                    key=f"coll_assign_{cid}",
                )

            new_platform = "esanum"
            new_target = st.date_input(
                "Geplant für",
                value=target_date if target_date else None,
                key=f"coll_date_{cid}",
            )

            _ec5, _ec6 = st.columns(2)
            with _ec5:
                new_url = st.text_input(
                    "Veröffentlichungs-Link",
                    value=pub_url or "",
                    placeholder="https://...",
                    key=f"coll_url_{cid}",
                )
            with _ec6:
                new_desc = st.text_input(
                    "Notiz",
                    value=desc or "",
                    key=f"coll_desc_{cid}",
                )

            # KI-Entwurf — prominent ABOVE comments and save buttons
            if cnt >= 2:
                _render_draft_section(cid, name, cnt, user_id)

            # Comments
            st.markdown("---")
            _render_comments(cid, user_id, ctx="my")
            st.markdown("---")

            # Save/Delete buttons
            _btn1, _btn2 = st.columns([1, 1])
            with _btn1:
                if st.button("💾 Sammlung speichern", key=f"coll_save_{cid}", use_container_width=True):
                    now = datetime.now(timezone.utc).isoformat()
                    new_assigned_id = new_assignee[0] if new_assignee[0] != 0 else None

                    c2 = _conn()
                    _save_name = new_name.strip() if new_name else name
                    c2.execute("""
                        UPDATE collection
                        SET name = ?, status = ?, target_platform = ?, target_date = ?,
                            published_url = ?, description = ?, assigned_to = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        _save_name,
                        new_status,
                        new_platform or None,
                        str(new_target) if new_target else None,
                        new_url or None,
                        new_desc or None,
                        new_assigned_id,
                        now,
                        cid,
                    ))
                    c2.commit()
                    c2.close()

                    # Notify if assigned to someone new
                    if new_assigned_id and new_assigned_id != (assigned_to or 0) and new_assigned_id != user_id:
                        current_name = st.session_state.get("current_user", {}).get("display_name", "?")
                        _create_notification(
                            new_assigned_id, "assignment",
                            f'{current_name} hat dir "{name}" zugewiesen',
                            cid,
                        )

                    track_activity("collection_update", f"id={cid} status={new_status}")
                    st.success("Gespeichert ✓")
                    st.rerun()

            with _btn2:
                if st.button("🗑️ Sammlung löschen", key=f"coll_del_{cid}", use_container_width=True):
                    st.session_state[f"_confirm_del_{cid}"] = True
                    st.rerun()

            if st.session_state.get(f"_confirm_del_{cid}"):
                st.warning(f'Sammlung "{name}" wirklich löschen?')
                _d1, _d2 = st.columns(2)
                with _d1:
                    if st.button("Ja, löschen", key=f"coll_del_yes_{cid}", use_container_width=True):
                        c3 = _conn()
                        c3.execute("UPDATE collection SET deleted_at = datetime('now'), status = 'verworfen' WHERE id = ?", (cid,))
                        c3.commit()
                        c3.close()
                        track_activity("collection_delete", f"id={cid} name={name}")
                        st.session_state.pop(f"_confirm_del_{cid}", None)
                        st.rerun()
                with _d2:
                    if st.button("Abbrechen", key=f"coll_del_no_{cid}", use_container_width=True):
                        st.session_state.pop(f"_confirm_del_{cid}", None)
                        st.rerun()


    conn.close()


# ---------------------------------------------------------------------------
# Kanban Board — visual status overview
# ---------------------------------------------------------------------------

def _render_draft_section(cid: int, name: str, art_count: int, user_id: int):
    """Render versioned draft section with feedback loop."""
    dconn = sqlite3.connect(str(DB_PATH))
    try:
        # Get all versions for this collection
        versions = dconn.execute("""
            SELECT id, version, draft_text, feedback_text, generated_at,
                   generated_by_user, generated_by_model, is_active
            FROM collection_draft
            WHERE collection_id = ?
            ORDER BY version DESC
        """, (cid,)).fetchall()

        # Also check legacy draft_text on collection
        if not versions:
            legacy = dconn.execute(
                "SELECT draft_text, draft_generated_at, draft_generated_by FROM collection WHERE id = ?",
                (cid,)
            ).fetchone()
            if legacy and legacy[0]:
                # Migrate legacy draft to new table
                dconn.execute(
                    "INSERT INTO collection_draft (collection_id, version, draft_text, generated_by_user, generated_at, is_active) "
                    "VALUES (?, 1, ?, ?, ?, 1)",
                    (cid, legacy[0], legacy[2], legacy[1] or datetime.now(timezone.utc).isoformat())
                )
                dconn.commit()
                versions = dconn.execute(
                    "SELECT id, version, draft_text, feedback_text, generated_at, "
                    "generated_by_user, generated_by_model, is_active "
                    "FROM collection_draft WHERE collection_id = ? ORDER BY version DESC",
                    (cid,)
                ).fetchall()
    finally:
        dconn.close()

    active = [v for v in versions if v[7]]  # is_active = 1
    current = active[0] if active else None

    if current:
        _did, _ver, _text, _feedback, _gen_at, _gen_by, _gen_model, _ = current

        st.markdown(f"#### ✍️ Entwurf (Version {_ver})")

        # Version selector if multiple
        if len(versions) > 1:
            ver_options = [f"v{v[1]} — {v[4][:16]}{' (Feedback)' if v[3] else ''}" for v in versions]
            sel_idx = st.selectbox(
                "Version", range(len(ver_options)),
                format_func=lambda i: ver_options[i],
                key=f"draft_ver_{cid}",
            )
            selected = versions[sel_idx]
            _text = selected[2]
            _ver = selected[1]
            _gen_at = selected[4]
            if selected[3]:
                st.caption(f"Feedback für diese Version: *{selected[3]}*")

        # Metadata
        _gen_name = ""
        if _gen_by:
            dconn2 = sqlite3.connect(str(DB_PATH))
            _r = dconn2.execute("SELECT display_name FROM user WHERE id = ?", (_gen_by,)).fetchone()
            _gen_name = f" von {_r[0]}" if _r else ""
            dconn2.close()
        st.caption(f"v{_ver} · Generiert {(_gen_at or '')[:16]}{_gen_name}")

        st.markdown(_text)

        # Feedback input
        feedback = st.text_input(
            "Was soll anders sein?",
            placeholder="z.B. Kürze den Einstieg, mehr Fokus auf Phase-III-Daten",
            key=f"draft_feedback_{cid}",
        )

        # Feedback chips
        _chip_cols = st.columns(5)
        _chip_labels = ["Kürzen", "Mehr Daten", "Einstieg ändern", "Einfacher", "Andere Struktur"]
        for i, lbl in enumerate(_chip_labels):
            with _chip_cols[i]:
                if st.button(lbl, key=f"chip_{cid}_{i}", use_container_width=True):
                    feedback = lbl

        # Action buttons
        _d1, _d2, _d3 = st.columns(3)
        with _d1:
            if st.button("🔄 Überarbeiten", key=f"draft_iterate_{cid}",
                         use_container_width=True, disabled=not feedback):
                if feedback and feedback.strip():
                    with st.spinner("Entwurf wird überarbeitet..."):
                        _new_text = _iterate_draft(cid, name, _text, feedback.strip())
                        if _new_text:
                            new_ver = _ver + 1
                            dconn3 = sqlite3.connect(str(DB_PATH))
                            # Deactivate all, activate new
                            dconn3.execute(
                                "UPDATE collection_draft SET is_active = 0 WHERE collection_id = ?",
                                (cid,)
                            )
                            dconn3.execute(
                                "INSERT INTO collection_draft (collection_id, version, draft_text, "
                                "feedback_text, generated_by_user, generated_at, is_active) "
                                "VALUES (?, ?, ?, ?, ?, datetime('now'), 1)",
                                (cid, new_ver, _new_text, feedback.strip(), user_id)
                            )
                            # Also update legacy field for backward compat
                            dconn3.execute(
                                "UPDATE collection SET draft_text = ?, "
                                "draft_generated_at = datetime('now'), draft_generated_by = ? "
                                "WHERE id = ?",
                                (_new_text, user_id, cid)
                            )
                            dconn3.commit()
                            dconn3.close()
                            track_activity("draft_iterate", f"collection={cid},v={new_ver}")
                            st.rerun()
                        else:
                            st.error(
                                "⚠️ **Überarbeitung fehlgeschlagen.**\n\n"
                                "KI nicht erreichbar. Der bisherige Entwurf bleibt erhalten."
                            )
        with _d2:
            if st.button("🔄 Komplett neu", key=f"draft_regen_{cid}", use_container_width=True):
                with st.spinner("Entwurf wird komplett neu generiert..."):
                    _new_text = _generate_collection_draft(cid, name)
                    if _new_text:
                        new_ver = (versions[0][1] if versions else 0) + 1
                        dconn4 = sqlite3.connect(str(DB_PATH))
                        dconn4.execute(
                            "UPDATE collection_draft SET is_active = 0 WHERE collection_id = ?",
                            (cid,)
                        )
                        dconn4.execute(
                            "INSERT INTO collection_draft (collection_id, version, draft_text, "
                            "generated_by_user, generated_at, is_active) "
                            "VALUES (?, ?, ?, ?, datetime('now'), 1)",
                            (cid, new_ver, _new_text, user_id)
                        )
                        dconn4.execute(
                            "UPDATE collection SET draft_text = ?, "
                            "draft_generated_at = datetime('now'), draft_generated_by = ? "
                            "WHERE id = ?",
                            (_new_text, user_id, cid)
                        )
                        dconn4.commit()
                        dconn4.close()
                        track_activity("draft_regen", f"collection={cid},v={new_ver}")
                        st.rerun()
                    else:
                        st.error("⚠️ **Generierung fehlgeschlagen.** Bitte in 10 Min erneut versuchen.")
        with _d3:
            if st.button("🗑 Verwerfen", key=f"draft_del_{cid}", use_container_width=True):
                dconn5 = sqlite3.connect(str(DB_PATH))
                dconn5.execute("DELETE FROM collection_draft WHERE collection_id = ?", (cid,))
                dconn5.execute(
                    "UPDATE collection SET draft_text = NULL, "
                    "draft_generated_at = NULL, draft_generated_by = NULL WHERE id = ?",
                    (cid,)
                )
                dconn5.commit()
                dconn5.close()
                st.rerun()
    else:
        # No draft yet — show full generation UI
        from src.processing.prompt_builder import (
            TECHNIQUES, PRO_MODES, RECOMMENDED_PRO_MODES,
            DEFAULT_EXPERTS, build_article_prompt,
        )

        with st.expander(f"✍️ Entwurf aus {art_count} Artikeln generieren", expanded=True):

            # --- Section 1: Briefing (inline, for this generation) ---
            st.markdown("**Redaktionelles Briefing**")

            # Row 1: Thema + Zielgruppe
            _b1a, _b1b = st.columns(2)
            with _b1a:
                _gen_theme = st.text_input(
                    "Thema", key=f"gen_theme_{cid}",
                    placeholder="z.B. Neue SGLT2-Inhibitor-Studie, Burnout bei Ärzten",
                )
            with _b1b:
                _gen_audience = st.text_input(
                    "Zielgruppe", key=f"gen_aud_{cid}",
                    placeholder="z.B. Kardiologen, Allgemeinmediziner",
                )

            # Row 2: Format + Tonalität (Dropdowns)
            _b2a, _b2b = st.columns(2)
            with _b2a:
                _FORMAT_OPTIONS = [
                    "—", "Nachricht / Kurzmeldung", "Hintergrundbericht",
                    "Studienzusammenfassung", "Übersichtsartikel / Review",
                    "Kasuistik / Fallbericht", "Meinungsbeitrag / Kommentar",
                    "Kongress-Nachbericht", "Ankündigung / Vorschau",
                    "Leitlinien-Update", "Interview / Expertenmeinung",
                    "How-to / Praxisleitfaden", "Newsletter-Aufmacher",
                    "Listicle / Top-N", "Patienteninformation",
                    "Benutzerdefiniert",
                ]
                _gen_format_sel = st.selectbox(
                    "Artikelformat", _FORMAT_OPTIONS, key=f"gen_fmt_{cid}",
                )
                if _gen_format_sel == "Benutzerdefiniert":
                    _gen_format_sel = st.text_input(
                        "Eigenes Format", key=f"gen_fmt_c_{cid}",
                        placeholder="z.B. FAQ, Fallbericht...",
                    )
                _gen_format = _gen_format_sel
            with _b2b:
                _TONALITY_OPTIONS = [
                    "—", "Fundiert + informativ", "Souverän + evidenzbasiert",
                    "Freundlich + professionell", "Empathisch + vertrauenswürdig",
                    "Sachlich-neutral", "Storytelling + emotional",
                    "Mutig + direkt", "Warm + persönlich",
                    "Locker + gesprächig", "Dringlich + überzeugend",
                    "Humorvoll + nahbar", "Positiv + enthusiastisch",
                    "Benutzerdefiniert",
                ]
                _gen_ton_sel = st.selectbox(
                    "Tonalität", _TONALITY_OPTIONS, key=f"gen_ton_{cid}",
                )
                if _gen_ton_sel == "Benutzerdefiniert":
                    _gen_ton_sel = st.text_input(
                        "Eigene Tonalität", key=f"gen_ton_c_{cid}",
                        placeholder="z.B. Ironisch-aufklärend...",
                    )
                _gen_tonality = _gen_ton_sel

            # Row 3: Länge + Ziel
            _b3a, _b3b = st.columns(2)
            with _b3a:
                _LENGTH_OPTIONS = [
                    "—", "Teaser (~150 Wörter)", "Kurz (~400 Wörter)",
                    "Standard (~800 Wörter)", "Lang (~1.200 Wörter)",
                    "Ausführlich (~2.000 Wörter)", "Benutzerdefiniert",
                ]
                _gen_len_sel = st.selectbox(
                    "Länge", _LENGTH_OPTIONS, key=f"gen_len_{cid}",
                )
                if _gen_len_sel == "Benutzerdefiniert":
                    _gen_len_sel = st.text_input(
                        "Eigene Länge", key=f"gen_len_c_{cid}",
                        placeholder="z.B. 500 Wörter, 3 Absätze...",
                    )
                _gen_length = _gen_len_sel
            with _b3b:
                _gen_goal = st.text_input(
                    "Ziel", key=f"gen_goal_{cid}",
                    placeholder="z.B. SEO-Traffic, Thought Leadership, CME-Vorbereitung",
                )

            # Row 4: Kernaussage + Keywords
            _b4a, _b4b = st.columns(2)
            with _b4a:
                _gen_keymsg = st.text_input(
                    "Kernaussage (optional)", key=f"gen_key_{cid}",
                    placeholder="z.B. Tirzepatid zeigt Überlegenheit bei Gewichtsreduktion",
                    max_chars=280,
                )
            with _b4b:
                _gen_keywords = st.text_input(
                    "Keywords (optional)", key=f"gen_kw_{cid}",
                    placeholder="z.B. SGLT2-Inhibitor Herzinsuffizienz Therapie",
                )

            st.markdown("---")

            # --- Section 2: Technique (styled cards) ---
            tech_options = list(TECHNIQUES.keys())
            tech_vals = list(TECHNIQUES.values())

            # Initialize selected technique in session state
            _tech_ss_key = f"draft_tech_sel_{cid}"
            if _tech_ss_key not in st.session_state:
                st.session_state[_tech_ss_key] = "cot"
            chosen_tech = st.session_state[_tech_ss_key]

            st.markdown(
                '<div style="font-size:0.78rem;font-weight:700;margin-bottom:8px;'
                'color:var(--c-text-muted)">PROMPTING-TECHNIK</div>',
                unsafe_allow_html=True,
            )

            _tech_cols = st.columns(len(tech_options))
            for i, (tid, tval) in enumerate(TECHNIQUES.items()):
                with _tech_cols[i]:
                    _is_active = tid == chosen_tech
                    if st.button(
                        tval['name'],
                        key=f"tech_btn_{cid}_{tid}",
                        use_container_width=True,
                        type="primary" if _is_active else "secondary",
                    ):
                        st.session_state[_tech_ss_key] = tid
                        chosen_tech = tid
                        st.rerun()

            _tdata = TECHNIQUES[chosen_tech]
            st.caption(f"ℹ️ {_tdata.get('help', '')}")

            # ToT: Custom experts (optional, collapsed)
            custom_experts = None
            if chosen_tech == "tot":
                with st.expander("Experten & Perspektiven anpassen (optional)", expanded=False):
                    _experts = []
                    for ei in range(3):
                        _ec1, _ec2 = st.columns(2)
                        with _ec1:
                            _ename = st.text_input(
                                f"Experte {ei+1}", key=f"tot_exp_{cid}_{ei}",
                                value=DEFAULT_EXPERTS[ei][0],
                            )
                        with _ec2:
                            _epov = st.text_input(
                                f"Perspektive {ei+1}", key=f"tot_pov_{cid}_{ei}",
                                value=DEFAULT_EXPERTS[ei][1],
                            )
                        _experts.append((_ename, _epov))
                    # Only use custom if user changed something
                    if any(e != d for e, d in zip(_experts, DEFAULT_EXPERTS)):
                        custom_experts = _experts

            # FS: Example texts
            fs_examples = None
            if chosen_tech == "fs":
                st.markdown("**Referenz-Beispiele** (1-3 Texte im gewünschten Stil)")
                fs_examples = []
                for j in range(3):
                    ex = st.text_area(
                        f"Beispiel {j+1}", key=f"fs_ex_{cid}_{j}",
                        height=80, placeholder="Beispieltext hier einfügen...",
                    )
                    if ex and ex.strip():
                        fs_examples.append(ex)

            st.markdown("---")

            # --- Section 3: Pro-Modes ---
            st.markdown("**Pro-Modes** *(max. 3 — erweitern den Prompt um Zusatz-Module)*")
            _pro_cols = st.columns(4)
            chosen_pro = set()
            for i, (pid, pdata) in enumerate(PRO_MODES.items()):
                with _pro_cols[i % 4]:
                    rec_marker = " ★" if pid in RECOMMENDED_PRO_MODES else ""
                    _pm_label = f"{pdata['emoji']} {pdata['name']}{rec_marker}"
                    _pm_help = pdata.get("tooltip") or pdata.get("subtitle", "")
                    if st.checkbox(
                        _pm_label,
                        key=f"pro_{cid}_{pid}",
                        help=_pm_help,
                    ):
                        chosen_pro.add(pid)

            if len(chosen_pro) > 3:
                st.warning("Maximal 3 Pro-Modes gleichzeitig.")

            st.markdown("---")

            # --- Section 4: Prompt Preview ---
            # Build briefing dict — read from session_state to survive expander reruns
            _gen_briefing = {}
            _ss = st.session_state
            _theme_val = _ss.get(f"gen_theme_{cid}", "") or _gen_theme
            _aud_val = _ss.get(f"gen_aud_{cid}", "") or _gen_audience
            _fmt_val = _gen_format  # already resolved (incl. custom)
            _ton_val = _gen_tonality  # already resolved
            _len_val = _gen_length  # already resolved
            _goal_val = _ss.get(f"gen_goal_{cid}", "") or _gen_goal
            _key_val = _ss.get(f"gen_key_{cid}", "") or _gen_keymsg
            _kw_val = _ss.get(f"gen_kw_{cid}", "") or _gen_keywords

            if _theme_val:
                _gen_briefing["theme"] = _theme_val
            if _aud_val:
                _gen_briefing["target_audience"] = _aud_val
            if _fmt_val and _fmt_val != "—":
                _gen_briefing["article_format"] = _fmt_val
            if _ton_val and _ton_val != "—":
                _gen_briefing["tonality"] = _ton_val
            if _len_val and _len_val != "—":
                _gen_briefing["target_length"] = _len_val
            if _goal_val:
                _gen_briefing["goal"] = _goal_val
            if _key_val:
                _gen_briefing["key_message"] = _key_val
            if _kw_val:
                _gen_briefing["keywords"] = _kw_val

            # Load articles for preview
            _prev_conn = _conn()
            _prev_arts = _prev_conn.execute("""
                SELECT a.title, a.abstract, a.journal, a.pub_date, a.summary_de,
                       a.url, a.doi
                FROM collectionarticle ca JOIN article a ON a.id = ca.article_id
                WHERE ca.collection_id = ? ORDER BY a.relevance_score DESC LIMIT 10
            """, (cid,)).fetchall()
            _prev_conn.close()
            _prev_articles = [
                {"title": r[0], "abstract": r[1] or "", "journal": r[2] or "",
                 "pub_date": str(r[3]) if r[3] else "", "summary_de": r[4] or "",
                 "url": r[5] or "", "doi": r[6] or ""}
                for r in _prev_arts
            ]

            _preview_prompt = build_article_prompt(
                articles=_prev_articles,
                briefing=_gen_briefing,
                collection_name=name,
                technique=chosen_tech,
                pro_modes=chosen_pro if len(chosen_pro) <= 3 else set(),
                custom_experts=custom_experts,
                fs_examples=fs_examples,
            )

            _prompt_tokens = len(_preview_prompt) // 4
            # Use a hash-based key so the preview updates when briefing changes
            _preview_hash = hash(str(_gen_briefing) + chosen_tech + str(sorted(chosen_pro)))
            with st.expander(f"Prompt-Vorschau ({_prompt_tokens:,} Tokens geschätzt)", expanded=False):
                st.code(_preview_prompt, language=None)

            # --- Generate Button ---
            if st.button(
                f"🚀 Entwurf generieren ({TECHNIQUES[chosen_tech]['name']})",
                key=f"coll_draft_gen_{cid}",
                use_container_width=True,
                disabled=len(chosen_pro) > 3,
            ):
                tech_label = TECHNIQUES[chosen_tech]["name"]
                pro_label = ", ".join(PRO_MODES[p]["name"] for p in chosen_pro) if chosen_pro else "keine"
                with st.spinner(f"Entwurf wird generiert ({tech_label} + {pro_label})..."):
                    _draft_text = _generate_collection_draft(
                        cid, name,
                        technique=chosen_tech,
                        pro_modes=chosen_pro if chosen_pro else None,
                        custom_experts=custom_experts,
                        fs_examples=fs_examples,
                    )
                    if _draft_text:
                        dconn6 = sqlite3.connect(str(DB_PATH))
                        try:
                            dconn6.execute(
                                "INSERT INTO collection_draft (collection_id, version, draft_text, "
                                "generated_by_user, generated_at, is_active) "
                                "VALUES (?, 1, ?, ?, datetime('now'), 1)",
                                (cid, _draft_text, user_id)
                            )
                        except Exception:
                            pass
                        dconn6.execute(
                            "UPDATE collection SET draft_text = ?, "
                            "draft_generated_at = datetime('now'), draft_generated_by = ? "
                            "WHERE id = ?",
                            (_draft_text, user_id, cid)
                        )
                        dconn6.commit()
                        dconn6.close()
                        track_activity("collection_draft",
                                       f"collection_id={cid},tech={chosen_tech},pro={pro_label}")
                        st.rerun()
                    else:
                        st.error(
                            "⚠️ **Entwurf konnte nicht generiert werden.**\n\n"
                            "KI nicht erreichbar. Die Sammlung bleibt gespeichert — "
                            "du kannst den Entwurf jederzeit später generieren."
                        )


def _iterate_draft(cid: int, name: str, current_text: str, feedback: str) -> str | None:
    """Generate an improved draft based on feedback."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute("""
                SELECT a.title, a.summary_de
                FROM collectionarticle ca JOIN article a ON a.id = ca.article_id
                WHERE ca.collection_id = ?
                ORDER BY a.relevance_score DESC LIMIT 10
            """, (cid,)).fetchall()
        finally:
            conn.close()

        sources_brief = "\n".join(f"- {t[:60]}" for t, _ in rows)

        prompt = f"""Du hast folgenden redaktionellen Entwurf zum Thema "{name}" geschrieben:

{current_text}

Der Redakteur gibt folgendes Feedback:
{feedback}

Überarbeite den Entwurf entsprechend. Behalte die Grundstruktur bei, sofern das Feedback nicht explizit etwas anderes verlangt. Sprache: Deutsch, fachlich aber verständlich.

Originalquellen zur Referenz:
{sources_brief}"""

        from src.config import get_provider_chain
        from src.llm_client import cached_chat_completion
        providers = get_provider_chain("artikel_entwurf")
        return cached_chat_completion(
            providers=providers,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
    except Exception:
        return None


_STATUS_COLUMNS = [
    ("recherche", "📝 Recherche", "#fbbf24"),
    ("in_arbeit", "🔧 In Arbeit", "#3b82f6"),
    ("review", "👁 Review", "#f97316"),
    ("veroeffentlicht", "✅ Veröffentlicht", "#22c55e"),
]


@st.cache_data(ttl=10, show_spinner=False)
@st.cache_data(ttl=10, show_spinner=False)
def _load_kanban_data():
    """Load kanban data with short cache."""
    conn = _conn()
    try:
        all_colls = conn.execute("""
            SELECT c.id, c.name, c.status, c.target_date, c.assigned_to,
                   u.display_name as creator,
                   au.display_name as assignee_name,
                   (SELECT COUNT(*) FROM collectionarticle WHERE collection_id = c.id) as art_cnt,
                   (SELECT COUNT(*) FROM collectioncomment WHERE collection_id = c.id) as cmt_cnt,
                   c.draft_text IS NOT NULL as has_draft,
                   c.user_id
            FROM collection c
            JOIN user u ON c.user_id = u.id
            LEFT JOIN user au ON c.assigned_to = au.id
            WHERE c.deleted_at IS NULL
            ORDER BY c.updated_at DESC
        """).fetchall()
    finally:
        conn.close()
    return all_colls


@st.fragment
def _render_kanban_board(user_id: int):
    """Render collections as a drag-and-drop Kanban board.

    Users can only drag cards they own or are assigned to.
    Drop triggers a Streamlit rerun with the new status.
    """
    import json as _json

    # Status updates from drag & drop are handled in render_cowork() before tabs

    all_colls = _load_kanban_data()

    # Group by status
    grouped = {s_key: [] for s_key, _, _ in _STATUS_COLUMNS}
    for row in all_colls:
        status = row[2] or "recherche"
        if status in ("veröffentlicht", "published"):
            status = "veroeffentlicht"
        elif status in ("in_arbeit", "in arbeit"):
            status = "in_arbeit"
        grouped.get(status, grouped["recherche"]).append(row)

    # Build card data for JS
    columns_data = []
    for s_key, s_label, s_color in _STATUS_COLUMNS:
        cards = []
        for row in grouped.get(s_key, []):
            cid, name, status, tdate, assignee_id, creator, assignee_name, art_cnt, cmt_cnt, has_draft, owner_id = row
            # User can drag their own cards or cards assigned to them
            can_drag = (owner_id == user_id) or (assignee_id == user_id)

            deadline_str = ""
            deadline_class = ""
            if tdate:
                try:
                    from datetime import date as _date
                    dl = (_date.fromisoformat(str(tdate)) - _date.today()).days
                    if dl < 0:
                        deadline_str = f"⏰ {abs(dl)}d überfällig"
                        deadline_class = "overdue"
                    elif dl <= 2:
                        deadline_str = f"⏰ {dl}d"
                        deadline_class = "soon"
                    else:
                        deadline_str = f"📅 {tdate}"
                except Exception:
                    pass

            cards.append({
                "id": cid,
                "name": name[:35],
                "creator": creator or "",
                "assignee": assignee_name or "",
                "art_cnt": art_cnt or 0,
                "cmt_cnt": cmt_cnt or 0,
                "has_draft": bool(has_draft),
                "can_drag": can_drag,
                "deadline": deadline_str,
                "deadline_class": deadline_class,
            })
        columns_data.append({
            "key": s_key,
            "label": s_label,
            "color": s_color,
            "cards": cards,
        })

    is_esanum = st.session_state.get("theme", "dark") == "esanum"
    theme_class = "esanum" if is_esanum else "dark"

    # Escape JSON for embedding in HTML
    cols_json = _json.dumps(columns_data, ensure_ascii=True)

    kanban_html = f"""
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:transparent; font-family:'Inter','Open Sans',-apple-system,sans-serif; }}
  .kb {{ display:flex; gap:10px; min-height:320px; }}
  .kb-col {{ flex:1; min-width:0; }}
  .kb-header {{ text-align:center; padding:6px 4px; font-size:0.72rem; font-weight:700;
    border-bottom:3px solid var(--col-color); margin-bottom:6px; }}
  .kb-header .count {{ opacity:0.5; font-weight:400; }}
  .kb-drop {{ min-height:250px; padding:4px; border-radius:8px;
    transition: background 0.2s; }}
  .kb-drop.drag-over {{ background: rgba(0,84,97,0.08); }}
  .kb-card {{ border-radius:8px; padding:8px 10px; margin:4px 0; font-size:0.70rem;
    transition: transform 0.15s, box-shadow 0.15s, opacity 0.15s; cursor:default; }}
  .kb-card.draggable {{ cursor:grab; }}
  .kb-card.draggable:active {{ cursor:grabbing; }}
  .kb-card.dragging {{ opacity:0.4; transform:scale(0.95); }}
  .kb-card .name {{ font-weight:700; margin-bottom:2px; }}
  .kb-card .meta {{ opacity:0.6; font-size:0.62rem; }}
  .kb-card .assignee {{ font-size:0.62rem; }}
  .kb-card .deadline {{ font-size:0.58rem; margin-top:2px; }}
  .kb-card .deadline.overdue {{ color:#ef4444; }}
  .kb-card .deadline.soon {{ color:#f59e0b; }}
  .kb-card .draft-icon {{ font-size:0.6rem; }}
  .kb-card .lock {{ font-size:0.55rem; opacity:0.4; float:right; }}
  /* Dark theme */
  .theme-dark .kb-card {{ background:var(--c-border-subtle); border:1px solid var(--c-border); color:var(--c-text); }}
  .theme-dark .kb-card.draggable:hover {{ background:var(--c-border); box-shadow:0 2px 8px rgba(0,0,0,0.3); transform:translateY(-1px); }}
  .theme-dark .kb-header {{ color:var(--c-text); }}
  .theme-dark .kb-empty {{ color:var(--c-text-muted); }}
  /* Esanum theme */
  .theme-esanum .kb-card {{ background:#FFFFFF; border:1px solid #ECECEC; color:#222222; }}
  .theme-esanum .kb-card.draggable:hover {{ background:#F8F8F8; box-shadow:0 2px 8px rgba(0,0,0,0.08); transform:translateY(-1px); }}
  .theme-esanum .kb-header {{ color:#333333; }}
  .theme-esanum .kb-empty {{ color:#999999; }}
  .kb-empty {{ text-align:center; font-size:0.65rem; padding:30px 0; }}
</style>
<div class="theme-{theme_class}">
  <div class="kb" id="kanban-board"></div>
</div>
<script>
(function() {{
  var columns = {cols_json};
  var board = document.getElementById('kanban-board');
  var draggedCard = null;
  var draggedId = null;

  columns.forEach(function(col) {{
    var colDiv = document.createElement('div');
    colDiv.className = 'kb-col';

    var header = document.createElement('div');
    header.className = 'kb-header';
    header.style.setProperty('--col-color', col.color);
    header.style.borderBottom = '3px solid ' + col.color;
    header.innerHTML = col.label + ' <span class="count">(' + col.cards.length + ')</span>';
    colDiv.appendChild(header);

    var dropZone = document.createElement('div');
    dropZone.className = 'kb-drop';
    dropZone.dataset.status = col.key;

    // Drop events
    dropZone.addEventListener('dragover', function(e) {{
      e.preventDefault();
      this.classList.add('drag-over');
    }});
    dropZone.addEventListener('dragleave', function(e) {{
      this.classList.remove('drag-over');
    }});
    dropZone.addEventListener('drop', function(e) {{
      e.preventDefault();
      this.classList.remove('drag-over');
      var newStatus = this.dataset.status;
      if (draggedId && newStatus) {{
        // Visual feedback: move card in DOM immediately
        if (draggedCard && draggedCard.parentNode !== this) {{
          this.appendChild(draggedCard);
          // Remove empty message if present
          var empty = this.querySelector('.kb-empty');
          if (empty) empty.remove();
        }}
        // Visual-only move in DOM (immediate feedback)
        // The real status change happens via Streamlit buttons below the board
        if (draggedCard && draggedCard.parentNode !== this) {{
          this.appendChild(draggedCard);
          var empty = this.querySelector('.kb-empty');
          if (empty) empty.remove();
          // Show inline hint
          var hint = document.createElement('div');
          hint.style.cssText = 'text-align:center;font-size:11px;padding:6px;color:#f97316;font-weight:600';
          hint.textContent = '↓ Klicke unten "Verschieben" um zu speichern';
          this.insertBefore(hint, this.firstChild);
          setTimeout(function(){{ hint.remove(); }}, 4000);
        }}
      }}
      draggedCard = null;
      draggedId = null;
    }});

    if (col.cards.length === 0) {{
      var emptyDiv = document.createElement('div');
      emptyDiv.className = 'kb-empty';
      emptyDiv.textContent = 'Keine Sammlungen';
      dropZone.appendChild(emptyDiv);
    }}

    col.cards.forEach(function(card) {{
      var cardDiv = document.createElement('div');
      cardDiv.className = 'kb-card' + (card.can_drag ? ' draggable' : '');
      if (card.can_drag) {{
        cardDiv.draggable = true;
        cardDiv.addEventListener('dragstart', function(e) {{
          draggedCard = this;
          draggedId = card.id;
          this.classList.add('dragging');
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', card.id);
        }});
        cardDiv.addEventListener('dragend', function() {{
          this.classList.remove('dragging');
        }});
      }}

      var lockHtml = card.can_drag ? '' : '<span class="lock">🔒</span>';
      var draftHtml = card.has_draft ? ' <span class="draft-icon">✍️</span>' : '';
      var assigneeHtml = card.assignee ? '<div class="assignee">→ ' + card.assignee + '</div>' : '';
      var deadlineHtml = card.deadline ? '<div class="deadline ' + card.deadline_class + '">' + card.deadline + '</div>' : '';

      cardDiv.innerHTML = lockHtml +
        '<div class="name">' + card.name + draftHtml + '</div>' +
        '<div class="meta">' + card.creator + ' · ' + card.art_cnt + ' Art. · ' + card.cmt_cnt + ' 💬</div>' +
        assigneeHtml + deadlineHtml;

      dropZone.appendChild(cardDiv);
    }});

    colDiv.appendChild(dropZone);
    board.appendChild(colDiv);
  }});
}})();
</script>
"""

    # Render the Kanban board as HTML component
    # Use a taller height to accommodate cards
    total_cards = sum(len(g) for g in grouped.values())
    # Pure Streamlit Kanban — native widgets, no iframe, guaranteed DB persistence
    status_order = [s[0] for s in _STATUS_COLUMNS]
    status_labels = {s[0]: s[1] for s in _STATUS_COLUMNS}

    _kb_cols = st.columns(len(_STATUS_COLUMNS))
    for col_idx, (s_key, s_label, s_color) in enumerate(_STATUS_COLUMNS):
        with _kb_cols[col_idx]:
            st.markdown(
                f'<div style="border-bottom:3px solid {s_color};padding-bottom:4px;'
                f'margin-bottom:8px;font-weight:700;font-size:0.8rem">'
                f'{s_label} ({len(grouped.get(s_key, []))})</div>',
                unsafe_allow_html=True,
            )
            cards_in_col = grouped.get(s_key, [])
            if not cards_in_col:
                st.caption("—")
            for row in cards_in_col:
                cid = row[0]
                card_name = row[1]
                card_owner_id = row[10]
                card_assigned = row[4]
                card_creator = row[5] or ""
                card_art_cnt = row[7] or 0
                card_cmt_cnt = row[8] or 0
                card_deadline = str(row[3]) if row[3] else ""
                is_mine = (card_owner_id == user_id) or (card_assigned == user_id)

                st.markdown(
                    f'<div style="background:var(--c-surface);border:1px solid var(--c-border);'
                    f'border-left:3px solid {s_color if is_mine else "var(--c-border)"};'
                    f'border-radius:6px;padding:8px 10px;margin-bottom:4px">'
                    f'<div style="font-weight:700;font-size:0.78rem">'
                    f'{"" if is_mine else "🔒 "}{card_name[:30]}</div>'
                    f'<div style="color:var(--c-text-muted);font-size:0.62rem">'
                    f'{card_creator} · {card_art_cnt} Art.'
                    f'{" · 📅 " + card_deadline if card_deadline else ""}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if is_mine:
                    _new_status = st.selectbox(
                        f"Status {card_name[:15]}",
                        status_order,
                        index=status_order.index(s_key) if s_key in status_order else 0,
                        format_func=lambda s: status_labels.get(s, s),
                        key=f"kb_sel_{cid}",
                        label_visibility="collapsed",
                    )
                    if _new_status != s_key:
                        _mv = _conn()
                        _mv.execute(
                            "UPDATE collection SET status = ?, updated_at = datetime('now') WHERE id = ?",
                            (_new_status, cid))
                        _mv.commit()
                        _mv.close()
                        track_activity("kanban_move", f"collection_id={cid} -> {_new_status}")
                        st.rerun()


# ---------------------------------------------------------------------------
# Calendar View
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "recherche": "#fbbf24",
    "in_arbeit": "#3b82f6",
    "review": "#f97316",
    "published": "#22c55e",
    "veröffentlicht": "#22c55e",
}


@st.cache_data(ttl=30, show_spinner=False)
def _load_calendar_data():
    """Load calendar data with caching to avoid re-querying on every render."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        colls = conn.execute("""
            SELECT c.id, c.name, c.status, c.target_date,
                   u.display_name,
                   (SELECT display_name FROM user WHERE id = c.assigned_to) as assignee
            FROM collection c
            JOIN user u ON c.user_id = u.id
            WHERE c.target_date IS NOT NULL
              AND c.deleted_at IS NULL
            ORDER BY c.target_date
        """).fetchall()
        unplanned = conn.execute("""
            SELECT c.name, c.status, u.display_name
            FROM collection c JOIN user u ON c.user_id = u.id
            WHERE (c.target_date IS NULL OR c.target_date = '')
              AND c.status NOT IN ('published', 'veröffentlicht')
              AND c.deleted_at IS NULL
        """).fetchall()
    finally:
        conn.close()
    return colls, unplanned


@st.fragment
def _render_calendar_view(user_id: int):
    """Render collections as a calendar based on target_date."""
    colls, unplanned = _load_calendar_data()

    if not colls and not unplanned:
        st.markdown(
            '<div style="text-align:center;padding:40px 0;color:var(--c-text-muted)">'
            '<div style="font-size:2rem;margin-bottom:8px">📅</div>'
            '<b>Noch keine geplanten Sammlungen</b><br>'
            '<span style="font-size:0.8rem">Erstelle eine Sammlung mit Datum, '
            'um sie hier im Kalender zu sehen.</span></div>',
            unsafe_allow_html=True,
        )
        return

    # Build events list
    events = []
    for cid, name, status, tdate, creator, assignee in colls:
        color = _STATUS_COLORS.get(status, "#6b7280")
        title = f"{name[:30]} ({creator})"
        if assignee:
            title += f" → {assignee}"
        events.append({
            "id": str(cid),
            "title": title,
            "start": str(tdate),
            "backgroundColor": color,
            "borderColor": color,
        })

    # Simple list view (reliable, no flicker)
    st.markdown("##### 📅 Geplante Sammlungen")
    current_month = ""
    for cid, name, status, tdate, creator, assignee in colls:
        month = str(tdate)[:7]
        if month != current_month:
            current_month = month
            st.markdown(f"**{month}**")
        color = _STATUS_COLORS.get(status, "#6b7280")
        assignee_str = f" → {assignee}" if assignee else ""
        st.markdown(
            f'<div style="font-size:0.78rem;padding:6px 10px;margin:3px 0;'
            f'border-left:3px solid {color};background:var(--c-surface);'
            f'border-radius:4px;border:1px solid var(--c-border)">'
            f'<b>{tdate}</b> · {name} ({creator}{assignee_str})'
            f' <span style="background:{color};color:#fff;padding:1px 6px;'
            f'border-radius:4px;font-size:0.6rem">{status}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Ungeplante Sammlungen
    if unplanned:
        st.markdown("---")
        with st.expander(f"📌 {len(unplanned)} Sammlungen ohne Datum", expanded=False):
            for name, status, creator in unplanned:
                st.markdown(f"• **{name}** ({creator}) — {status}")


# ---------------------------------------------------------------------------

@st.fragment
def _render_create_collection(user_id: int):
    """Form to create a new collection."""
    st.markdown("### Neue Sammlung erstellen")

    # Show success banner if just created
    _created_name = st.session_state.pop("_coll_created", None)
    if _created_name:
        st.markdown(
            f'<div class="lumio-dark-bg" style="background:#005461;padding:16px 24px;'
            f'border-radius:12px;margin-bottom:20px;text-align:center;color:#fff !important">'
            f'<p style="margin:0;font-size:1rem;color:#fff !important">✅ <b style="color:#fff !important">Sammlung erstellt:</b> {_created_name}</p>'
            f'<p style="margin:4px 0 0;font-size:0.8rem;color:rgba(255,255,255,0.85) !important">'
            f'Du findest sie unter Meine Sammlungen — füge jetzt Artikel aus dem Feed hinzu.</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    all_users = _get_all_users_including_admin()

    with st.form("create_collection_form", clear_on_submit=True):
        name = st.text_input("Name *", placeholder="z.B. Herzinsuffizienz — SGLT2-Update")

        # Briefing fields
        st.markdown("**Redaktionelles Briefing** *(optional — verbessert KI-Entwürfe)*")

        _bc1, _bc2 = st.columns(2)
        with _bc1:
            _format_options = [
                "—",
                "Nachricht / Kurzmeldung",
                "Hintergrundbericht",
                "Meinungsbeitrag / Kommentar",
                "Kongress-Nachbericht",
                "Leitlinien-Update / Guideline-Summary",
                "Studienzusammenfassung",
                "Interview / Expertenmeinung",
                "Listicle / Top-X",
                "FAQ / Fragen & Antworten",
                "How-to / Praxisleitfaden",
                "Infografik-Text",
                "Newsletter-Aufmacher",
                "Social-Media-Post",
                "Benutzerdefiniert",
            ]
            article_format = st.selectbox(
                "Artikelformat", _format_options, key="coll_format",
            )
            if article_format == "Benutzerdefiniert":
                article_format = st.text_input(
                    "Eigenes Format", key="coll_format_custom",
                    placeholder="z.B. Podcast-Skript, Patientenbrief...",
                )
        with _bc2:
            _tonality_options = [
                "—",
                "Freundlich + professionell",
                "Fundiert + informativ",
                "Dringlich + überzeugend",
                "Locker + gesprächig",
                "Empathisch + vertrauenswürdig",
                "Mutig + direkt",
                "Humorvoll + nahbar",
                "Souverän + evidenzbasiert",
                "Warm + persönlich",
                "Positiv + enthusiastisch",
                "Storytelling + emotional",
                "Sachlich-neutral",
                "Benutzerdefiniert",
            ]
            tonality = st.selectbox(
                "Tonalität", _tonality_options, key="coll_tonality",
            )
            if tonality == "Benutzerdefiniert":
                tonality = st.text_input(
                    "Eigene Tonalität", key="coll_tonality_custom",
                    placeholder="z.B. Ironisch + provokant...",
                )

        _bc3, _bc4 = st.columns(2)
        with _bc3:
            _audience_options = [
                "Allgemeinmedizin", "Innere Medizin", "Kardiologie", "Onkologie",
                "Neurologie", "Pneumologie", "Diabetologie/Endokrinologie",
                "Psychiatrie/Psychotherapie", "Chirurgie", "Orthopädie/Unfallchirurgie",
                "Dermatologie", "Infektiologie", "Gastroenterologie",
                "Urologie", "Gynäkologie/Geburtshilfe", "Pädiatrie",
                "Geriatrie/Palliativmedizin", "Anästhesiologie/Intensivmedizin",
                "Radiologie", "HNO", "Augenheilkunde",
                "Rheumatologie", "Nephrologie", "Hämatologie",
                "Notfallmedizin", "Sportmedizin", "Arbeitsmedizin",
                "Alle Fachrichtungen",
            ]
            target_audience = st.multiselect(
                "Zielgruppe", _audience_options, key="coll_audience",
                placeholder="Fachgruppen auswählen...",
            )
            _custom_aud = st.text_input(
                "Weitere Zielgruppe", key="coll_audience_custom",
                placeholder="z.B. Hausärzte, Assistenzärzte, Fachärzte Innere...",
            )
            if _custom_aud:
                target_audience = target_audience + [_custom_aud.strip()]
        with _bc4:
            _length_options = [
                "—",
                "Teaser (~150 Wörter)",
                "Kurz (~400 Wörter)",
                "Standard (~800 Wörter)",
                "Lang (~1.200 Wörter)",
                "Ausführlich (~2.000 Wörter)",
                "Benutzerdefiniert",
            ]
            target_length = st.selectbox(
                "Gewünschte Länge", _length_options, key="coll_length",
            )
            if target_length == "Benutzerdefiniert":
                target_length = st.text_input(
                    "Eigene Länge", key="coll_length_custom",
                    placeholder="z.B. 500 Wörter, 3 Absätze...",
                )

        key_message = st.text_input(
            "Kernaussage",
            placeholder="z.B. Tirzepatid zeigt Überlegenheit bei Gewichtsreduktion vs. Semaglutid",
            max_chars=280,
        )

        internal_notes = st.text_area(
            "Interne Notizen",
            height=60,
            placeholder="z.B. Soll als Aufmacher für den Freitags-Newsletter dienen",
        )

        _bc5, _bc6 = st.columns(2)
        with _bc5:
            target_date = st.date_input("Geplant für", value=None)
        with _bc6:
            user_options = [(0, "— Niemand —")] + all_users
            assignee = st.selectbox(
                "Zuweisen an",
                user_options,
                format_func=lambda u: u[1],
            )

        submitted = st.form_submit_button("📁 Sammlung erstellen", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Bitte einen Namen eingeben.")
                return

            now = datetime.now(timezone.utc).isoformat()
            assigned_id = assignee[0] if assignee[0] != 0 else None
            _fmt = article_format if article_format != "—" else None
            _ton = tonality if tonality != "—" else None
            _len = target_length if target_length != "—" else None
            _aud = ",".join(target_audience) if target_audience else None

            conn = _conn()
            try:
                conn.execute("""
                    INSERT INTO collection (user_id, name, description, status,
                        target_platform, target_date, assigned_to,
                        article_format, tonality, target_length, target_audience,
                        key_message, internal_notes,
                        created_at, updated_at)
                    VALUES (?, ?, ?, 'recherche', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, name.strip(), None,
                    "esanum",
                    str(target_date) if target_date else None,
                    assigned_id,
                    _fmt, _ton, _len, _aud,
                    key_message.strip() or None,
                    internal_notes.strip() or None,
                    now, now,
                ))
                _new_cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                if not _new_cid or _new_cid == 0:
                    st.error("Sammlung konnte nicht erstellt werden.")
                    return
                conn.commit()
            finally:
                conn.close()

            # Notify assignee
            if assigned_id and assigned_id != user_id:
                current_name = st.session_state.get("current_user", {}).get("display_name", "?")
                _create_notification(
                    assigned_id, "assignment",
                    f'{current_name} hat dir "{name.strip()}" zugewiesen',
                )

            track_activity("collection_create", f"name={name.strip()}")

            # Store success message for display after rerun
            st.session_state["_coll_created"] = name.strip()

            # Clear form fields by removing their keys from session state
            for _fkey in list(st.session_state.keys()):
                if _fkey.startswith("new_coll_"):
                    del st.session_state[_fkey]

            st.rerun()


# ---------------------------------------------------------------------------
# Helper: Add article to collection (called from feed cards)
# ---------------------------------------------------------------------------

def get_user_collections(user_id: int) -> list[tuple[int, str]]:
    """Return [(id, name), ...] for collections the user owns or is assigned to."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, name FROM collection WHERE (user_id = ? OR assigned_to = ?) AND deleted_at IS NULL ORDER BY updated_at DESC",
        (user_id, user_id),
    ).fetchall()
    conn.close()
    return rows


def add_article_to_collection(collection_id: int, article_id: int) -> bool:
    """Add an article to a collection. Returns True if added, False if already exists."""
    conn = _conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO collectionarticle (collection_id, article_id, added_at) VALUES (?, ?, ?)",
            (collection_id, article_id, now),
        )
        conn.execute(
            "UPDATE collection SET updated_at = ? WHERE id = ?",
            (now, collection_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

"""Admin Usage Dashboard — nur sichtbar für Admins."""

from datetime import datetime, timedelta, timezone

import streamlit as st


def _render_user_management():
    """Render user management section (create, delete, reset password)."""
    from components.auth import (
        create_user, delete_user, reset_user_password, get_all_users_safe,
    )

    st.markdown("### 👥 Benutzerverwaltung")

    users = get_all_users_safe()
    current_user = st.session_state.get("current_user")
    current_uid = current_user.get("id") if current_user else None

    # ------------------------------------------------------------------
    # User table
    # ------------------------------------------------------------------
    header_html = (
        '<div style="display:grid;grid-template-columns:1fr 120px 80px 130px 120px;'
        'gap:8px;padding:8px 12px;background:var(--c-surface);border-radius:8px;'
        'font-size:0.70rem;font-weight:600;color:var(--c-text-muted);margin-bottom:4px">'
        '<span>Anzeigename</span><span>Username</span><span>Rolle</span>'
        '<span>Erstellt am</span><span>Aktionen</span></div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    for u in users:
        created = u["created_at"][:10] if u.get("created_at") else "—"
        role_badge = (
            '<span style="background:#005461;color:#fff;padding:1px 6px;'
            'border-radius:4px;font-size:0.62rem">Admin</span>'
            if u["role"] == "admin"
            else '<span style="background:var(--c-surface);padding:1px 6px;'
                 'border-radius:4px;font-size:0.62rem">User</span>'
        )
        row_html = (
            f'<div style="display:grid;grid-template-columns:1fr 120px 80px 130px 120px;'
            f'gap:8px;padding:8px 12px;border-bottom:1px solid var(--c-border-subtle);'
            f'font-size:0.76rem;align-items:center">'
            f'<span style="font-weight:600">{u["display_name"]}</span>'
            f'<span style="color:var(--c-text-muted)">{u["username"]}</span>'
            f'<span>{role_badge}</span>'
            f'<span style="color:var(--c-text-muted);font-size:0.68rem">{created}</span>'
            f'<span id="actions-{u["id"]}"></span>'
            f'</div>'
        )
        st.markdown(row_html, unsafe_allow_html=True)

        # Action buttons in a row
        _btn_cols = st.columns([1, 1, 4])
        with _btn_cols[0]:
            if st.button("🔑 PW", key=f"pw_reset_{u['id']}", use_container_width=True):
                st.session_state["_reset_pw_uid"] = u["id"]
                st.session_state["_reset_pw_name"] = u["display_name"]
                st.session_state.pop("_confirm_delete_uid", None)
        with _btn_cols[1]:
            is_self = u["id"] == current_uid
            if st.button(
                "🗑️ Löschen", key=f"del_user_{u['id']}",
                disabled=is_self, use_container_width=True,
            ):
                st.session_state["_confirm_delete_uid"] = u["id"]
                st.session_state["_confirm_delete_name"] = u["display_name"]
                st.session_state.pop("_reset_pw_uid", None)

        # --- Password reset inline form ---
        if st.session_state.get("_reset_pw_uid") == u["id"]:
            with st.container():
                st.markdown(
                    f'<div style="font-size:0.8rem;font-weight:600;margin-bottom:4px">'
                    f'Passwort zurücksetzen für: {u["display_name"]}</div>',
                    unsafe_allow_html=True,
                )
                _pw_col1, _pw_col2 = st.columns(2)
                with _pw_col1:
                    _new_pw = st.text_input(
                        "Neues Passwort", type="password",
                        key=f"_rpw1_{u['id']}",
                    )
                with _pw_col2:
                    _new_pw2 = st.text_input(
                        "Bestätigen", type="password",
                        key=f"_rpw2_{u['id']}",
                    )
                _pw_action_cols = st.columns([1, 1, 3])
                with _pw_action_cols[0]:
                    if st.button("Speichern", key=f"_rpw_save_{u['id']}", use_container_width=True):
                        if not _new_pw or len(_new_pw) < 6:
                            st.error("Mindestens 6 Zeichen.")
                        elif _new_pw != _new_pw2:
                            st.error("Passwörter stimmen nicht überein.")
                        else:
                            if reset_user_password(u["id"], _new_pw):
                                st.session_state.pop("_reset_pw_uid", None)
                                st.success(f"Passwort für {u['display_name']} geändert.")
                                st.rerun()
                            else:
                                st.error("Fehler beim Speichern.")
                with _pw_action_cols[1]:
                    if st.button("Abbrechen", key=f"_rpw_cancel_{u['id']}", use_container_width=True):
                        st.session_state.pop("_reset_pw_uid", None)
                        st.rerun()

        # --- Delete confirmation ---
        if st.session_state.get("_confirm_delete_uid") == u["id"]:
            st.warning(
                f"**Sicher, dass du {u['display_name']} ({u['username']}) "
                f"endgültig löschen willst?**\n\n"
                f"Alle Daten (Aktivitäten, Profil, Sessions) werden unwiderruflich gelöscht."
            )
            _del_cols = st.columns([1, 1, 3])
            with _del_cols[0]:
                if st.button(
                    "Ja, endgültig löschen",
                    key=f"_del_confirm_{u['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    if delete_user(u["id"]):
                        st.session_state.pop("_confirm_delete_uid", None)
                        st.success(f"{u['display_name']} wurde gelöscht.")
                        st.rerun()
                    else:
                        st.error("Löschen fehlgeschlagen.")
            with _del_cols[1]:
                if st.button("Abbrechen", key=f"_del_cancel_{u['id']}", use_container_width=True):
                    st.session_state.pop("_confirm_delete_uid", None)
                    st.rerun()

    # ------------------------------------------------------------------
    # Create new user
    # ------------------------------------------------------------------
    with st.expander("➕ Neuen User anlegen", expanded=False):
        with st.form("create_user_form", clear_on_submit=True):
            _cu_col1, _cu_col2 = st.columns(2)
            with _cu_col1:
                _cu_username = st.text_input("Username", placeholder="z.B. jdoe")
            with _cu_col2:
                _cu_display = st.text_input("Anzeigename", placeholder="z.B. Dr. Jane Doe")
            _cu_col3, _cu_col4 = st.columns(2)
            with _cu_col3:
                _cu_pw = st.text_input("Passwort", type="password")
            with _cu_col4:
                _cu_pw2 = st.text_input("Passwort bestätigen", type="password")
            _cu_role = st.selectbox("Rolle", ["user", "admin"], index=0)
            _cu_submit = st.form_submit_button("User anlegen", use_container_width=True)

            if _cu_submit:
                existing_usernames = [u["username"] for u in users]
                if not _cu_username or not _cu_display:
                    st.error("Username und Anzeigename sind Pflichtfelder.")
                elif _cu_username in existing_usernames:
                    st.error(f"Username '{_cu_username}' ist bereits vergeben.")
                elif not _cu_pw or len(_cu_pw) < 6:
                    st.error("Passwort muss mindestens 6 Zeichen lang sein.")
                elif _cu_pw != _cu_pw2:
                    st.error("Passwörter stimmen nicht überein.")
                else:
                    try:
                        create_user(_cu_username, _cu_display, _cu_pw, _cu_role)
                        st.success(f"User '{_cu_display}' ({_cu_username}) wurde angelegt.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")


def render_admin_usage():
    """Render the admin usage analytics dashboard."""
    import sqlite3
    from src.config import DB_PATH

    st.markdown(
        '<div class="page-header">Team-Nutzung</div>'
        '<div class="page-sub">Benutzerverwaltung und Nutzungsanalyse</div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # 1. User Management (always visible at top)
    # ------------------------------------------------------------------
    _render_user_management()

    st.divider()

    # ------------------------------------------------------------------
    # 2. Usage Statistics (collapsed by default)
    # ------------------------------------------------------------------
    with st.expander("📊 Nutzungsstatistiken & Aktivitäts-Log", expanded=True):
        conn = sqlite3.connect(str(DB_PATH))
        try:
            c = conn.cursor()

            # ---------------------------------------------------------------
            # Key Metrics
            # ---------------------------------------------------------------
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

            active_today = c.execute(
                "SELECT COUNT(DISTINCT user_id) FROM useractivity WHERE date(timestamp) = ?",
                (today,)
            ).fetchone()[0]
            active_week = c.execute(
                "SELECT COUNT(DISTINCT user_id) FROM useractivity WHERE timestamp >= ?",
                (week_ago,)
            ).fetchone()[0]
            active_month = c.execute(
                "SELECT COUNT(DISTINCT user_id) FROM useractivity WHERE timestamp >= ?",
                (month_ago,)
            ).fetchone()[0]
            total_actions = c.execute("SELECT COUNT(*) FROM useractivity").fetchone()[0]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Aktiv heute", active_today)
            m2.metric("Aktiv diese Woche", active_week)
            m3.metric("Aktiv diesen Monat", active_month)
            m4.metric("Aktionen gesamt", f"{total_actions:,}")

            if total_actions == 0:
                st.info("Noch keine Nutzungsdaten vorhanden.")
                return

            st.divider()

            # ---------------------------------------------------------------
            # Per-User Activity Summary
            # ---------------------------------------------------------------
            st.markdown("### Aktivität pro Mitarbeiter")

            _period_options = [
                "Letzte Stunde", "Heute", "Letzte 7 Tage", "Letzte 14 Tage",
                "Letzte 30 Tage", "Letzte 3 Monate", "Letzte 6 Monate", "Letzte 12 Monate",
            ]
            period = st.selectbox("Zeitraum", _period_options, index=2, key="admin_period")

            _now = datetime.now(timezone.utc)
            _period_map = {
                "Letzte Stunde": (_now - timedelta(hours=1)).isoformat(),
                "Heute": _now.strftime("%Y-%m-%dT00:00:00"),
                "Letzte 7 Tage": (_now - timedelta(days=7)).isoformat(),
                "Letzte 14 Tage": (_now - timedelta(days=14)).isoformat(),
                "Letzte 30 Tage": (_now - timedelta(days=30)).isoformat(),
                "Letzte 3 Monate": (_now - timedelta(days=90)).isoformat(),
                "Letzte 6 Monate": (_now - timedelta(days=180)).isoformat(),
                "Letzte 12 Monate": (_now - timedelta(days=365)).isoformat(),
            }
            since = _period_map.get(period, "2000-01-01")

            user_stats = c.execute("""
                SELECT
                    u.display_name,
                    u.username,
                    COUNT(ua.id) as total_actions,
                    COUNT(DISTINCT date(ua.timestamp)) as active_days,
                    COUNT(DISTINCT ua.session_id) as sessions,
                    SUM(CASE WHEN ua.action = 'login' THEN 1 ELSE 0 END) as logins,
                    SUM(CASE WHEN ua.action = 'bookmark' THEN 1 ELSE 0 END) as bookmarks,
                    SUM(CASE WHEN ua.action = 'dismiss' THEN 1 ELSE 0 END) as dismisses,
                    SUM(CASE WHEN ua.action = 'draft' THEN 1 ELSE 0 END) as drafts,
                    SUM(CASE WHEN ua.action = 'search' THEN 1 ELSE 0 END) as searches,
                    MAX(ua.timestamp) as last_active,
                    u.id as uid
                FROM user u
                LEFT JOIN useractivity ua ON u.id = ua.user_id AND ua.timestamp >= ?
                WHERE u.role != 'admin'
                GROUP BY u.id
                ORDER BY total_actions DESC
            """, (since,)).fetchall()

            def _calc_active_minutes(user_id: int) -> int:
                events = c.execute(
                    "SELECT timestamp FROM useractivity "
                    "WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp",
                    (user_id, since),
                ).fetchall()
                if len(events) < 2:
                    return len(events)
                total_secs = 0
                for i in range(1, len(events)):
                    try:
                        t1 = datetime.fromisoformat(events[i-1][0].replace("Z", "+00:00"))
                        t2 = datetime.fromisoformat(events[i][0].replace("Z", "+00:00"))
                        gap = (t2 - t1).total_seconds()
                        if gap <= 60:
                            total_secs += gap
                    except (ValueError, TypeError):
                        continue
                return max(1, int(total_secs / 60))

            if user_stats:
                header_html = (
                    '<div style="display:grid;grid-template-columns:130px 70px 70px 55px 55px 55px 45px 45px 45px 130px;'
                    'gap:6px;padding:8px 12px;background:var(--c-surface);border-radius:8px;'
                    'font-size:0.68rem;font-weight:600;color:var(--c-text-muted);margin-bottom:4px">'
                    '<span>Name</span><span>Aktionen</span><span>⏱ Aktiv</span><span>Tage</span><span>Sessions</span>'
                    '<span>Logins</span><span>☆</span><span>✗</span><span>✍️</span><span>Zuletzt aktiv</span>'
                    '</div>'
                )
                st.markdown(header_html, unsafe_allow_html=True)

                for row in user_stats:
                    name, uname, actions, days, sessions, logins, bm, dismiss, drafts, searches, last, uid = row
                    actions = actions or 0
                    days = days or 0
                    sessions = sessions or 0

                    if actions >= 50:
                        level_color = "#4ade80"
                    elif actions >= 15:
                        level_color = "#f59e0b"
                    elif actions > 0:
                        level_color = "#8b8ba0"
                    else:
                        level_color = "#ef4444"

                    last_str = last[:16].replace("T", " ") if last else "—"

                    active_min = _calc_active_minutes(uid) if actions else 0
                    if active_min >= 60:
                        active_str = f"{active_min // 60}h {active_min % 60}m"
                    else:
                        active_str = f"{active_min}m"

                    row_html = (
                        f'<div style="display:grid;grid-template-columns:130px 70px 70px 55px 55px 55px 45px 45px 45px 130px;'
                        f'gap:6px;padding:8px 12px;border-bottom:1px solid var(--c-border);'
                        f'font-size:0.76rem;align-items:center">'
                        f'<span style="font-weight:600"><span style="color:{level_color}">●</span> {name}</span>'
                        f'<span style="font-weight:700">{actions}</span>'
                        f'<span style="font-weight:600;color:{"#005461" if st.session_state.get("theme") == "esanum" else "#22d3ee"}">{active_str}</span>'
                        f'<span>{days}</span>'
                        f'<span>{sessions}</span>'
                        f'<span>{logins or 0}</span>'
                        f'<span>{bm or 0}</span>'
                        f'<span>{dismiss or 0}</span>'
                        f'<span>{drafts or 0}</span>'
                        f'<span style="color:var(--c-text-muted);font-size:0.68rem">{last_str}</span>'
                        f'</div>'
                    )
                    st.markdown(row_html, unsafe_allow_html=True)

                st.markdown(
                    '<div style="font-size:0.65rem;color:var(--c-text-muted);margin-top:8px">'
                    '● <span style="color:#4ade80">Power User (50+)</span> · '
                    '<span style="color:#f59e0b">Regulär (15+)</span> · '
                    '<span style="color:#8b8ba0">Wenig aktiv</span> · '
                    '<span style="color:#ef4444">Inaktiv</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

            st.divider()

            # ---------------------------------------------------------------
            # Activity Timeline (actions per day)
            # ---------------------------------------------------------------
            st.markdown("### Tägliche Aktivität")

            daily = c.execute("""
                SELECT date(timestamp) as day, COUNT(*) as actions,
                       COUNT(DISTINCT user_id) as users
                FROM useractivity
                WHERE timestamp >= ?
                GROUP BY date(timestamp)
                ORDER BY day
            """, (since,)).fetchall()

            if daily:
                import pandas as pd
                import altair as alt
                df = pd.DataFrame(daily, columns=["Tag", "Aktionen", "Aktive User"])
                df["Tag"] = pd.to_datetime(df["Tag"])

                is_esanum = st.session_state.get("theme", "dark") == "esanum"
                bar_color = "#005461" if is_esanum else "#a3e635"
                bg_color = "#FFFFFF" if is_esanum else "#0e0e22"
                label_color = "#444444" if is_esanum else "#8b8ba0"
                grid_color = "rgba(0,0,0,0.06)" if is_esanum else "rgba(255,255,255,0.05)"

                chart = alt.Chart(df).mark_bar(
                    cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=bar_color
                ).encode(
                    x=alt.X("Tag:T", title=None, axis=alt.Axis(labelColor=label_color, format="%d.%m")),
                    y=alt.Y("Aktionen:Q", title=None, axis=alt.Axis(labelColor=label_color, labelPadding=12, tickCount=5)),
                    tooltip=["Tag:T", "Aktionen:Q", "Aktive User:Q"],
                ).configure(
                    background=bg_color,
                ).configure_axis(
                    gridColor=grid_color, domainColor=grid_color,
                ).configure_view(
                    strokeWidth=0,
                ).properties(height=250, padding={"left": 50, "right": 10, "top": 10, "bottom": 10})

                st.altair_chart(chart, use_container_width=True)

            # ---------------------------------------------------------------
            # Most Common Actions
            # ---------------------------------------------------------------
            st.markdown("### Beliebteste Aktionen")

            actions_data = c.execute("""
                SELECT action, COUNT(*) as cnt
                FROM useractivity
                WHERE timestamp >= ?
                GROUP BY action
                ORDER BY cnt DESC
            """, (since,)).fetchall()

            if actions_data:
                action_labels = {
                    "login": "🔑 Login",
                    "logout": "🚪 Logout",
                    "page_view": "👁 Seitenaufruf",
                    "bookmark": "☆ Gemerkt",
                    "unbookmark": "✕ Entmerkt",
                    "dismiss": "✗ Ausgeblendet",
                    "draft": "✍️ Entwurf",
                    "search": "🔍 Suche",
                    "export": "📤 Export",
                }
                cols = st.columns(min(len(actions_data), 5))
                for i, (action, cnt) in enumerate(actions_data[:5]):
                    label = action_labels.get(action, action)
                    cols[i % 5].metric(label, cnt)

            # ---------------------------------------------------------------
            # Recent Activity Log
            # ---------------------------------------------------------------
            with st.expander("📋 Letzte 50 Aktionen", expanded=False):
                recent = c.execute("""
                    SELECT u.display_name, ua.action, ua.detail, ua.timestamp
                    FROM useractivity ua
                    JOIN user u ON ua.user_id = u.id
                    ORDER BY ua.timestamp DESC
                    LIMIT 50
                """).fetchall()

                for name, action, detail, ts in recent:
                    ts_short = ts[11:16] if len(ts) > 16 else ts
                    day = ts[:10] if len(ts) > 10 else ""
                    detail_str = f' — {detail}' if detail else ""
                    st.markdown(
                        f'<div style="font-size:0.75rem;padding:2px 0;color:var(--c-text-secondary)">'
                        f'<span style="color:var(--c-text-muted)">{day} {ts_short}</span> · '
                        f'<b>{name}</b> · {action}{detail_str}</div>',
                        unsafe_allow_html=True,
                    )

            st.divider()

            # ---------------------------------------------------------------
            # Granulares Log-File
            # ---------------------------------------------------------------
            st.markdown("### 📊 Granulares Aktivitäts-Log")
            st.caption("Vollständiges Log aller Aktionen — für detaillierte Auswertung")

            _log_col1, _log_col2, _log_col3 = st.columns(3)
            with _log_col1:
                log_user = st.selectbox(
                    "User filtern",
                    ["Alle"] + [r[0] for r in c.execute(
                        "SELECT DISTINCT display_name FROM user WHERE role != 'admin' ORDER BY display_name"
                    ).fetchall()],
                    key="log_user_filter",
                )
            with _log_col2:
                log_action = st.selectbox(
                    "Aktion filtern",
                    ["Alle"] + [r[0] for r in c.execute(
                        "SELECT DISTINCT action FROM useractivity ORDER BY action"
                    ).fetchall()],
                    key="log_action_filter",
                )
            with _log_col3:
                log_days = st.selectbox(
                    "Zeitraum",
                    [7, 14, 30, 90, 365],
                    format_func=lambda d: f"Letzte {d} Tage",
                    key="log_days_filter",
                )

            log_since = (now - timedelta(days=log_days)).strftime("%Y-%m-%d")

            log_query = """
                SELECT
                    ua.timestamp,
                    u.display_name,
                    u.username,
                    ua.action,
                    ua.detail,
                    ua.session_id
                FROM useractivity ua
                JOIN user u ON ua.user_id = u.id
                WHERE ua.timestamp >= ?
            """
            log_params = [log_since]

            if log_user != "Alle":
                log_query += " AND u.display_name = ?"
                log_params.append(log_user)
            if log_action != "Alle":
                log_query += " AND ua.action = ?"
                log_params.append(log_action)

            log_query += " ORDER BY ua.timestamp DESC"

            log_rows = c.execute(log_query, log_params).fetchall()

            if log_rows:
                import pandas as pd
                import io

                df_log = pd.DataFrame(log_rows, columns=[
                    "Zeitstempel", "Name", "Username", "Aktion", "Detail", "Session-ID"
                ])

                st.markdown(
                    f'<div style="font-size:0.75rem;color:var(--c-text-muted);margin-bottom:8px">'
                    f'{len(df_log):,} Einträge gefunden</div>',
                    unsafe_allow_html=True,
                )

                csv_buffer = io.StringIO()
                df_log.to_csv(csv_buffer, index=False, sep=";", encoding="utf-8")
                csv_data = csv_buffer.getvalue()

                _dl_col1, _dl_col2 = st.columns([1, 3])
                with _dl_col1:
                    st.download_button(
                        "📥 CSV Export",
                        data=csv_data,
                        file_name=f"lumio_activity_log_{log_since}_{now.strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

                with st.expander(f"📋 Detail-Log ({len(df_log):,} Einträge)", expanded=True):
                    df_log["Tag"] = df_log["Zeitstempel"].str[:10]
                    df_log["Uhrzeit"] = df_log["Zeitstempel"].str[11:19]

                    for day, day_group in df_log.groupby("Tag", sort=False):
                        st.markdown(
                            f'<div style="font-size:0.8rem;font-weight:700;color:var(--c-accent);'
                            f'margin:12px 0 4px;border-bottom:1px solid var(--c-border);'
                            f'padding-bottom:4px">{day} ({len(day_group)} Aktionen)</div>',
                            unsafe_allow_html=True,
                        )
                        for _, row in day_group.iterrows():
                            _action_icons = {
                                "login": "🔑", "logout": "🚪", "page_view": "👁",
                                "bookmark": "⭐", "unbookmark": "✕", "dismiss": "🚫",
                                "draft": "✍️", "search": "🔍", "sort_change": "↕️",
                                "filter_change": "🎛", "password_change": "🔐",
                                "export": "📤",
                            }
                            icon = _action_icons.get(row["Aktion"], "•")
                            detail = f' — <span style="color:var(--c-text-secondary)">{row["Detail"]}</span>' if row["Detail"] else ""
                            st.markdown(
                                f'<div style="font-size:0.72rem;padding:1px 0;font-family:monospace">'
                                f'<span style="color:var(--c-text-muted)">{row["Uhrzeit"]}</span> '
                                f'{icon} <b>{row["Name"]}</b> '
                                f'<span style="color:var(--c-accent)">{row["Aktion"]}</span>'
                                f'{detail} '
                                f'<span style="color:var(--c-text-muted);font-size:0.6rem">[{row["Session-ID"]}]</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                with st.expander("🔗 Session-Analyse", expanded=False):
                    session_stats = df_log.groupby(["Session-ID", "Name"]).agg(
                        Erste_Aktion=("Zeitstempel", "min"),
                        Letzte_Aktion=("Zeitstempel", "max"),
                        Anzahl_Aktionen=("Aktion", "count"),
                        Aktionen=("Aktion", lambda x: ", ".join(x.unique())),
                    ).reset_index().sort_values("Erste_Aktion", ascending=False)

                    for _, s in session_stats.iterrows():
                        try:
                            t0 = datetime.fromisoformat(s["Erste_Aktion"])
                            t1 = datetime.fromisoformat(s["Letzte_Aktion"])
                            dur = t1 - t0
                            dur_str = f"{dur.seconds // 60}m {dur.seconds % 60}s"
                        except Exception:
                            dur_str = "?"

                        st.markdown(
                            f'<div style="font-size:0.72rem;padding:4px 0;border-bottom:1px solid var(--c-border-subtle)">'
                            f'<b>{s["Name"]}</b> · '
                            f'<span style="color:var(--c-text-muted)">{s["Erste_Aktion"][:16]}</span> · '
                            f'Dauer: <b>{dur_str}</b> · '
                            f'{s["Anzahl_Aktionen"]} Aktionen · '
                            f'<span style="color:var(--c-text-secondary);font-size:0.65rem">{s["Aktionen"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
            else:
                st.info("Keine Log-Einträge für den gewählten Filter.")

        finally:
            conn.close()

    # --- Archive Management ---
    st.markdown("---")
    st.markdown("### 🗄️ Artikel-Archivierung")
    st.caption("Artikel älter als 180 Tage werden archiviert — ausgenommen: Sammlungen, Bookmarks, Score ≥ 80, Leitlinien.")

    _ac1, _ac2 = st.columns(2)
    with _ac1:
        if st.button("🔍 Vorschau (Dry Run)", key="archive_dry", use_container_width=True):
            from components.helpers import archive_old_articles
            result = archive_old_articles(days=180, dry_run=True)
            st.session_state["_archive_preview"] = result
            st.rerun()
    with _ac2:
        if st.button("🗄️ Jetzt archivieren", key="archive_run", use_container_width=True):
            from components.helpers import archive_old_articles
            result = archive_old_articles(days=180, dry_run=False)
            st.session_state["_archive_result"] = result
            st.rerun()

    if "_archive_preview" in st.session_state:
        r = st.session_state.pop("_archive_preview")
        st.info(
            f"**Vorschau (keine Änderungen)**\n\n"
            f"- Cutoff: {r['cutoff_date']} ({r['days']} Tage)\n"
            f"- Alte Artikel gesamt: {r['total_old']}\n"
            f"- Geschützt (Sammlungen/Bookmarks/Score/Leitlinien): {r['protected']}\n"
            f"- **Würden archiviert werden: {r['would_archive']}**"
        )

    if "_archive_result" in st.session_state:
        r = st.session_state.pop("_archive_result")
        st.success(
            f"**Archivierung abgeschlossen**\n\n"
            f"- {r['archived']} Artikel archiviert\n"
            f"- {r['protected']} geschützt (nicht archiviert)\n"
            f"- Cutoff: {r['cutoff_date']}"
        )

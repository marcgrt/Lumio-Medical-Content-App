"""Simple authentication and activity tracking for Lumio."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

import streamlit as st
from sqlalchemy import text
from sqlmodel import select

from src.db import get_raw_conn, is_postgres
from src.models import get_session


# ---------------------------------------------------------------------------
# Lightweight User model access (reads existing 'user' table)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash a password with bcrypt for new users."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash (supports bcrypt and SHA-256)."""
    import bcrypt
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        # bcrypt hash
        try:
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
        except Exception:
            return False
    else:
        # Legacy SHA-256 hash
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash


def _get_all_users() -> list[dict]:
    """Fetch all users from DB."""
    with get_raw_conn() as conn:
        rows = conn.execute(
            text("SELECT id, username, display_name, password_hash, role FROM \"user\"")
        ).fetchall()
    return [
        {"id": r[0], "username": r[1], "display_name": r[2],
         "password_hash": r[3], "role": r[4]}
        for r in rows
    ]


def create_user(username: str, display_name: str, password: str, role: str = "user"):
    """Create a new user in the DB."""
    with get_raw_conn() as conn:
        conn.execute(
            text(
                'INSERT INTO "user" (username, display_name, password_hash, role, created_at) '
                "VALUES (:username, :display_name, :password_hash, :role, :created_at)"
            ),
            {
                "username": username,
                "display_name": display_name,
                "password_hash": _hash_password(password),
                "role": role,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )


def delete_user(user_id: int) -> bool:
    """Delete a user and all associated data. Returns True on success."""
    current_user = st.session_state.get("current_user")
    if current_user and current_user.get("id") == user_id:
        return False  # Cannot delete yourself

    try:
        with get_raw_conn() as conn:
            conn.execute(text("DELETE FROM session_token WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM userprofile WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM useractivity WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": user_id})
        return True
    except Exception:
        return False


def reset_user_password(user_id: int, new_password: str) -> bool:
    """Reset password for any user (admin function). Returns True on success."""
    if len(new_password) < 6:
        return False
    try:
        with get_raw_conn() as conn:
            conn.execute(
                text('UPDATE "user" SET password_hash = :hash WHERE id = :uid'),
                {"hash": _hash_password(new_password), "uid": user_id},
            )
        return True
    except Exception:
        return False


def get_all_users_safe() -> list[dict]:
    """Return all users WITHOUT password hashes (safe for UI display)."""
    with get_raw_conn() as conn:
        rows = conn.execute(
            text('SELECT id, username, display_name, role, created_at FROM "user" ORDER BY id')
        ).fetchall()
    return [
        {"id": r[0], "username": r[1], "display_name": r[2],
         "role": r[3], "created_at": r[4]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Login UI
# ---------------------------------------------------------------------------

def _generate_session_token(user_id: int) -> str:
    """Generate a session token and store in DB. Valid for 7 days."""
    import secrets
    from datetime import timedelta

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    with get_raw_conn() as conn:
        # Clean expired tokens
        conn.execute(
            text("DELETE FROM session_token WHERE expires_at < :now"),
            {"now": now},
        )
        # Insert new token
        conn.execute(
            text(
                "INSERT INTO session_token (user_id, token, expires_at, created_at) "
                "VALUES (:user_id, :token, :expires_at, :created_at)"
            ),
            {"user_id": user_id, "token": token, "expires_at": expires, "created_at": now},
        )
    return token


def _validate_session_token(token: str) -> Optional[dict]:
    """Check if token is valid and return user dict, or None."""
    if not token:
        return None

    with get_raw_conn() as conn:
        row = conn.execute(
            text(
                'SELECT st.user_id, u.username, u.display_name, u.role, u.password_hash '
                'FROM session_token st '
                'JOIN "user" u ON st.user_id = u.id '
                "WHERE st.token = :token AND st.expires_at > :now"
            ),
            {"token": token, "now": datetime.now(timezone.utc).isoformat()},
        ).fetchone()

    if row:
        return {
            "id": row[0], "username": row[1], "display_name": row[2],
            "role": row[3], "password_hash": row[4],
        }
    return None


def require_login() -> dict:
    """Show login form if not authenticated. Returns current user dict.

    Call this at the top of app.py — it will st.stop() if not logged in.
    Uses query params for 7-day persistent sessions.
    """
    # Already logged in this session?
    if "current_user" in st.session_state and st.session_state.current_user:
        return st.session_state.current_user

    # Check for persistent session token in query params
    params = st.query_params
    session_token = params.get("session")
    if session_token:
        user = _validate_session_token(session_token)
        if user:
            st.session_state.current_user = user
            st.session_state.current_user_id = user["id"]
            st.session_state.session_id = str(uuid.uuid4())[:12]
            # Load last visit from DB for "NEU" badges, then update to now
            if "_user_last_visit" not in st.session_state:
                with get_raw_conn() as _lv_conn:
                    # Read previous last_visit
                    row = _lv_conn.execute(
                        text(
                            "SELECT timestamp FROM useractivity "
                            "WHERE user_id = :uid AND action = 'login' "
                            "ORDER BY timestamp DESC LIMIT 1 OFFSET 1"
                        ),
                        {"uid": user["id"]},
                    ).fetchone()
                    if row:
                        st.session_state["_user_last_visit"] = str(row[0])[:19]
                    else:
                        # First ever login — show everything as new
                        st.session_state["_user_last_visit"] = "2020-01-01T00:00:00"
            return user

    # Ensure session_id for tracking
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:12]

    # Login — CSS styles
    st.markdown(
        '<style>'
        '@keyframes login-entrance { '
        '  from { opacity:0; transform:translateY(20px); } '
        '  to { opacity:1; transform:translateY(0); } }'
        '@keyframes feat-slide { '
        '  from { opacity:0; transform:translateX(-16px); } '
        '  to { opacity:1; transform:translateX(0); } }'
        '@keyframes ring-draw { from { stroke-dashoffset:100; } to { stroke-dashoffset:25; } }'
        '.login-showcase-title { font-size:2.4rem; font-weight:800; letter-spacing:-0.04em; '
        '  background:linear-gradient(135deg,#eeeef5 0%,#84cc16 80%); '
        '  -webkit-background-clip:text; -webkit-text-fill-color:transparent; '
        '  background-clip:text; margin:0 0 6px; line-height:1.1; '
        '  animation:login-entrance 0.6s cubic-bezier(0.22,1,0.36,1) forwards; opacity:0; }'
        '.login-showcase-sub { color:var(--c-text-muted); font-size:0.82rem; margin-bottom:20px; '
        '  animation:login-entrance 0.6s 0.1s cubic-bezier(0.22,1,0.36,1) forwards; opacity:0; }'
        '.login-feat { display:flex; align-items:center; gap:12px; padding:10px 14px; '
        '  background:var(--c-surface, rgba(255,255,255,0.03)); '
        '  border:1px solid var(--c-border, rgba(255,255,255,0.06)); '
        '  border-radius:12px; margin-bottom:8px; opacity:0; '
        '  animation:feat-slide 0.5s cubic-bezier(0.22,1,0.36,1) forwards; }'
        '.login-feat:nth-child(1) { animation-delay:0.3s; }'
        '.login-feat:nth-child(2) { animation-delay:0.45s; }'
        '.login-feat:nth-child(3) { animation-delay:0.6s; }'
        '.login-feat:nth-child(4) { animation-delay:0.75s; }'
        '.login-feat:nth-child(5) { animation-delay:0.9s; }'
        '.login-feat-icon { font-size:1.3rem; flex-shrink:0; width:36px; height:36px; '
        '  display:flex; align-items:center; justify-content:center; '
        '  background:linear-gradient(135deg,rgba(132,204,22,0.1),rgba(34,211,238,0.08)); '
        '  border-radius:10px; }'
        '.login-feat-text b { display:block; font-size:0.78rem; color:var(--c-text, #e8e8f0); }'
        '.login-feat-text span { font-size:0.68rem; color:var(--c-text-muted, #8b8ba0); line-height:1.4; }'
        '.login-form-title { font-size:1.6rem; font-weight:800; text-align:center; '
        '  color:var(--c-text, #e8e8f0); margin-bottom:2px; '
        '  animation:login-entrance 0.6s 0.15s forwards; opacity:0; }'
        '.login-form-sub { text-align:center; color:var(--c-text-muted); font-size:0.72rem; '
        '  margin-bottom:16px; animation:login-entrance 0.6s 0.2s forwards; opacity:0; }'
        '/* Glassmorphic form card */'
        '@keyframes form-glow { '
        '  0%,100% { box-shadow:0 8px 32px rgba(0,0,0,0.2),0 0 0 1px rgba(132,204,22,0.05); }'
        '  50% { box-shadow:0 8px 40px rgba(0,0,0,0.3),0 0 0 1px rgba(132,204,22,0.12); } }'
        '@keyframes orb-float-1 { '
        '  0% { transform:translate(0,0) scale(1); } '
        '  33% { transform:translate(30px,-20px) scale(1.1); } '
        '  66% { transform:translate(-15px,15px) scale(0.95); } '
        '  100% { transform:translate(0,0) scale(1); } }'
        '@keyframes orb-float-2 { '
        '  0% { transform:translate(0,0) scale(1); } '
        '  33% { transform:translate(-25px,15px) scale(1.05); } '
        '  66% { transform:translate(20px,-10px) scale(0.9); } '
        '  100% { transform:translate(0,0) scale(1); } }'
        '.login-form-card { position:relative; overflow:hidden; '
        '  background:rgba(255,255,255,0.02); '
        '  border:1px solid rgba(255,255,255,0.06); '
        '  border-radius:20px; padding:32px 28px 24px; '
        '  backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); '
        '  animation:login-entrance 0.7s 0.2s cubic-bezier(0.22,1,0.36,1) forwards,form-glow 4s ease-in-out infinite 1s; '
        '  opacity:0; }'
        '.login-form-card::before { content:""; position:absolute; top:-40px; right:-40px; '
        '  width:120px; height:120px; border-radius:50%; '
        '  background:radial-gradient(circle,rgba(132,204,22,0.08) 0%,transparent 70%); '
        '  animation:orb-float-1 8s ease-in-out infinite; pointer-events:none; }'
        '.login-form-card::after { content:""; position:absolute; bottom:-30px; left:-30px; '
        '  width:100px; height:100px; border-radius:50%; '
        '  background:radial-gradient(circle,rgba(34,211,238,0.06) 0%,transparent 70%); '
        '  animation:orb-float-2 10s ease-in-out infinite; pointer-events:none; }'
        '.login-form-icon { width:48px; height:48px; margin:0 auto 16px; border-radius:14px; '
        '  background:linear-gradient(135deg,rgba(132,204,22,0.12),rgba(34,211,238,0.08)); '
        '  border:1px solid rgba(132,204,22,0.15); '
        '  display:flex; align-items:center; justify-content:center; font-size:22px; '
        '  animation:login-entrance 0.5s 0.3s forwards; opacity:0; }'
        '.login-form-divider { height:1px; '
        '  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.06),transparent); '
        '  margin:16px 0; }'
        '.login-form-footer { text-align:center; font-size:0.62rem; color:var(--c-text-muted,#6b6b82); '
        '  margin-top:12px; opacity:0; animation:login-entrance 0.5s 0.5s forwards; }'
        '/* Audio player */'
        '.login-audio { display:flex; align-items:center; gap:8px; margin-top:16px; '
        '  padding:8px 12px; background:var(--c-surface, rgba(255,255,255,0.03)); '
        '  border:1px solid var(--c-border, rgba(255,255,255,0.06)); '
        '  border-radius:10px; opacity:0; animation:feat-slide 0.5s 1.1s forwards; }'
        '.login-audio-cover { width:32px; height:32px; border-radius:6px; '
        '  background:linear-gradient(135deg,#84cc16,#22d3ee); '
        '  display:flex; align-items:center; justify-content:center; font-size:14px; }'
        '.login-audio-info { flex:1; }'
        '.login-audio-info b { display:block; font-size:0.7rem; color:var(--c-text, #e8e8f0); }'
        '.login-audio-info span { font-size:0.6rem; color:var(--c-text-muted); }'
        '</style>',
        unsafe_allow_html=True,
    )

    # Two-column layout: Showcase left, Form right
    showcase_col, spacer_col, form_col = st.columns([5, 1, 5])

    with showcase_col:
        st.markdown(
            '<h1 class="login-showcase-title">Lumio</h1>'
            '<p class="login-showcase-sub">Finde, was die Medizin bewegt.</p>'
            '<div>'
            '<div class="login-feat">'
            '  <div class="login-feat-icon">'
            '    <svg width="24" height="24" viewBox="0 0 36 36">'
            '      <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(132,204,22,0.15)" stroke-width="3"/>'
            '      <circle cx="18" cy="18" r="15" fill="none" stroke="#84cc16" stroke-width="3" '
            '        stroke-dasharray="100" stroke-dashoffset="25" stroke-linecap="round" '
            '        transform="rotate(-90 18 18)" style="animation:ring-draw 2s ease-out forwards"/>'
            '      <text x="18" y="22" text-anchor="middle" fill="#84cc16" font-size="11" font-weight="800">79</text>'
            '    </svg>'
            '  </div>'
            '  <div class="login-feat-text"><b>KI-Scoring</b>'
            '    <span>Jeder Artikel auf 0\u2013100 bewertet</span></div>'
            '</div>'
            '<div class="login-feat">'
            '  <div class="login-feat-icon">&#128225;</div>'
            '  <div class="login-feat-text"><b>Themen-Radar</b>'
            '    <span>Aufkommende Trends erkennen</span></div>'
            '</div>'
            '<div class="login-feat">'
            '  <div class="login-feat-icon">&#129309;</div>'
            '  <div class="login-feat-text"><b>Cowork</b>'
            '    <span>Sammlungen, Zuweisung, KI-Entw\u00fcrfe</span></div>'
            '</div>'
            '<div class="login-feat">'
            '  <div class="login-feat-icon">&#127973;</div>'
            '  <div class="login-feat-text"><b>Kongresse</b>'
            '    <span>Kalender, Briefings, CME-Punkte</span></div>'
            '</div>'
            '<div class="login-feat">'
            '  <div class="login-feat-icon">&#128232;</div>'
            '  <div class="login-feat-text"><b>Versand</b>'
            '    <span>Newsletter und Themen-Pakete</span></div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        # Prominent audio player with cover art, autoplay, mute toggle
        st.components.v1.html(
            '<style>'
            '@keyframes la-spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}'
            '@keyframes la-pulse{0%,100%{box-shadow:0 0 12px rgba(245,158,11,0.3)}50%{box-shadow:0 0 28px rgba(245,158,11,0.6)}}'
            '@keyframes la-bounce{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}'
            '@keyframes la-entrance{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}'
            '@keyframes la-eq1{0%,100%{height:4px}50%{height:16px}}'
            '@keyframes la-eq2{0%,100%{height:8px}50%{height:12px}}'
            '@keyframes la-eq3{0%,100%{height:6px}50%{height:18px}}'
            '</style>'
            '<div id="la-player" style="display:flex;align-items:center;gap:14px;'
            'padding:14px 18px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);'
            'border-radius:14px;font-family:Inter,system-ui,sans-serif;margin-top:16px;'
            'animation:la-entrance 0.5s 1.0s both,la-pulse 2s ease-in-out infinite 1.5s;cursor:pointer" onclick="togglePlay()" id="la-player">'

            '<div style="position:relative;width:72px;height:72px;flex-shrink:0">'
            '  <div id="la-disc" style="width:72px;height:72px;border-radius:14px;overflow:hidden;'
            '    background:radial-gradient(circle at 50% 50%,#f59e0b 0%,#ef4444 35%,#3b82f6 65%,#06b6d4 100%);'
            '    display:flex;align-items:center;justify-content:center;'
            '    box-shadow:0 4px 20px rgba(245,158,11,0.3);position:relative">'
            '    <div style="position:absolute;inset:0;background:'
            '      conic-gradient(from 0deg,transparent,rgba(255,255,255,0.3) 10%,transparent 20%,'
            '      transparent,rgba(255,255,255,0.2) 50%,transparent 60%,'
            '      transparent,rgba(255,255,255,0.3) 80%,transparent 90%);'
            '      animation:la-spin 8s linear infinite"></div>'
            '    <div id="la-play-overlay" style="position:absolute;inset:0;z-index:2;display:flex;'
            '      align-items:center;justify-content:center;background:rgba(0,0,0,0.3);border-radius:14px;'
            '      animation:la-bounce 1.5s ease-in-out infinite">'
            '      <div style="width:0;height:0;border-left:18px solid #fff;border-top:11px solid transparent;'
            '        border-bottom:11px solid transparent;margin-left:4px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))"></div>'
            '    </div>'
            '    <div style="position:relative;z-index:1;text-align:center;line-height:1">'
            '      <div style="font-size:11px;font-weight:900;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,0.4);'
            '        letter-spacing:-0.02em">LUMIO</div>'
            '      <div style="font-size:7px;font-weight:600;color:rgba(255,255,255,0.85);margin-top:1px;'
            '        letter-spacing:0.05em">ARRIVES</div>'
            '    </div>'
            '  </div>'
            '</div>'
            '<div style="flex:1;min-width:0">'
            '  <div style="font-size:0.88rem;font-weight:700;color:#e8e8f0;'
            '    white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Lumio Arrives</div>'
            '  <div style="font-size:0.68rem;color:#8b8ba0;margin-top:2px">The Essential Remains</div>'
            '  <div id="la-eq" style="display:flex;gap:2px;align-items:flex-end;height:20px;margin-top:6px">'
            '    <div style="width:3px;background:#f59e0b;border-radius:1px;animation:la-eq1 0.8s ease infinite"></div>'
            '    <div style="width:3px;background:#ef4444;border-radius:1px;animation:la-eq2 0.6s ease infinite 0.1s"></div>'
            '    <div style="width:3px;background:#3b82f6;border-radius:1px;animation:la-eq3 0.7s ease infinite 0.2s"></div>'
            '    <div style="width:3px;background:#06b6d4;border-radius:1px;animation:la-eq1 0.9s ease infinite 0.15s"></div>'
            '    <div style="width:3px;background:#f59e0b;border-radius:1px;animation:la-eq2 0.5s ease infinite 0.25s"></div>'
            '    <div style="width:3px;background:#ef4444;border-radius:1px;animation:la-eq3 0.65s ease infinite 0.3s"></div>'
            '    <div style="width:3px;background:#3b82f6;border-radius:1px;animation:la-eq1 0.75s ease infinite 0.05s"></div>'
            '  </div>'
            '</div>'
            '<button id="la-mute" onclick="event.stopPropagation();toggleMute()" style="'
            'background:none;border:1px solid rgba(255,255,255,0.08);border-radius:8px;'
            'padding:8px 12px;cursor:pointer;font-size:18px;color:#8b8ba0;transition:all .15s">'
            '&#128266;</button>'
            '</div>'
            '<script>'
            'var a=new Audio();a.preload="none";'
            'a.src="/app/static/lumio_arrives.mp4";'
            'a.loop=true;a.volume=0.25;var playing=false,muted=false;'
            'var disc=document.getElementById("la-disc");'
            'var eq=document.getElementById("la-eq");'
            'var muteBtn=document.getElementById("la-mute");'
            'function startPlay(){'
            '  a.play().then(function(){playing=true;'
            '  }).catch(function(){});'
            '}'
            'a.muted=true;startPlay();'
            'setTimeout(function(){a.muted=false},300);'
            'document.addEventListener("click",function h(){'
            '  if(!playing){a.muted=false;startPlay()}'
            '  else if(a.muted){a.muted=false}'
            '  document.removeEventListener("click",h);'
            '},{once:true});'
            'var playOv=document.getElementById("la-play-overlay");'
            'var playerEl=document.getElementById("la-player");'
            'function togglePlay(){'
            '  if(playing){a.pause();playing=false;eq.style.display="none";'
            '    if(playOv)playOv.style.display="flex";}'
            '  else{a.muted=false;a.play().catch(function(){});playing=true;'
            '    eq.style.display="flex";'
            '    if(playOv)playOv.style.display="none";'
            '    if(playerEl)playerEl.style.animation="la-entrance 0.5s both";}'
            '}'
            'function toggleMute(){'
            '  muted=!muted;a.muted=muted;'
            '  muteBtn.innerHTML=muted?"&#128264;":"&#128266;";'
            '}'
            '</script>',
            height=120,
        )

    with form_col:
        # Header above form
        st.markdown(
            '<div style="text-align:center;opacity:0;animation:login-entrance 0.6s 0.25s forwards">'
            '<div style="width:48px;height:48px;margin:0 auto 12px;border-radius:14px;'
            'background:linear-gradient(135deg,rgba(132,204,22,0.12),rgba(34,211,238,0.08));'
            'border:1px solid rgba(132,204,22,0.15);display:flex;align-items:center;'
            'justify-content:center;font-size:22px">&#128274;</div>'
            '</div>'
            '<div class="login-form-title">Willkommen</div>'
            '<p class="login-form-sub">Medical Content Finder</p>',
            unsafe_allow_html=True,
        )
        # Glassmorphic form styling via CSS targeting the Streamlit form container
        st.markdown(
            '<style>'
            '[data-testid="stForm"] { '
            '  background:rgba(255,255,255,0.02) !important; '
            '  border:1px solid rgba(255,255,255,0.06) !important; '
            '  border-radius:20px !important; '
            '  padding:24px 24px 20px !important; '
            '  backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); '
            '  box-shadow:0 8px 32px rgba(0,0,0,0.15),0 0 0 1px rgba(132,204,22,0.04); '
            '  position:relative; overflow:hidden; '
            '  animation:login-entrance 0.7s 0.3s cubic-bezier(0.22,1,0.36,1) forwards,form-glow 4s ease-in-out infinite 1.5s; '
            '  opacity:0; }'
            '[data-testid="stForm"]::before { content:""; position:absolute; top:-40px; right:-40px; '
            '  width:120px; height:120px; border-radius:50%; '
            '  background:radial-gradient(circle,rgba(132,204,22,0.08) 0%,transparent 70%); '
            '  animation:orb-float-1 8s ease-in-out infinite; pointer-events:none; z-index:0; }'
            '[data-testid="stForm"]::after { content:""; position:absolute; bottom:-30px; left:-30px; '
            '  width:100px; height:100px; border-radius:50%; '
            '  background:radial-gradient(circle,rgba(34,211,238,0.06) 0%,transparent 70%); '
            '  animation:orb-float-2 10s ease-in-out infinite; pointer-events:none; z-index:0; }'
            '[data-testid="stForm"] > * { position:relative; z-index:1; }'
            '[data-testid="stFormSubmitButton"] button { '
            '  background:linear-gradient(135deg,#84cc16,#22d3ee) !important; '
            '  color:#0a0a1a !important; font-weight:700 !important; '
            '  border:none !important; border-radius:12px !important; '
            '  padding:10px 24px !important; font-size:0.85rem !important; '
            '  transition:all 0.2s ease !important; }'
            '[data-testid="stFormSubmitButton"] button:hover { '
            '  transform:translateY(-1px) !important; '
            '  box-shadow:0 4px 16px rgba(132,204,22,0.3) !important; }'
            '</style>',
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Benutzername")
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", use_container_width=True)

            if submitted:
                users = _get_all_users()
                matched = [
                    u for u in users
                    if u["username"].lower() == username.strip().lower()
                    and _verify_password(password, u["password_hash"])
                ]
                if matched:
                    user = matched[0]
                    st.session_state.current_user = user
                    st.session_state.current_user_id = user["id"]
                    st.session_state.session_id = str(uuid.uuid4())[:12]
                    # Load last visit from DB for "NEU" badges
                    with get_raw_conn() as _lv_conn:
                        _lv_row = _lv_conn.execute(
                            text(
                                "SELECT timestamp FROM useractivity "
                                "WHERE user_id = :uid AND action = 'login' "
                                "ORDER BY timestamp DESC LIMIT 1"
                            ),
                            {"uid": user["id"]},
                        ).fetchone()
                        st.session_state["_user_last_visit"] = (
                            str(_lv_row[0])[:19] if _lv_row else "2020-01-01T00:00:00"
                        )
                    # Generate persistent session token (7 days)
                    token = _generate_session_token(user["id"])
                    st.query_params["session"] = token
                    # Track login
                    track_activity("login")
                    st.rerun()
                else:
                    st.error("Benutzername oder Passwort falsch.")

        # Footer under form
        st.markdown(
            '<div style="text-align:center;font-size:0.6rem;color:var(--c-text-muted,#6b6b82);'
            'margin-top:12px;opacity:0;animation:login-entrance 0.5s 0.6s forwards">'
            'Zugangsdaten vom Admin erhalten? Einfach einloggen.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.stop()


def show_user_menu():
    """Show current user + logout + change password in sidebar."""
    user = st.session_state.get("current_user")
    if not user:
        return

    # Clean user menu — flat, no shadow, theme-aware
    theme = st.session_state.get("theme", "dark")
    is_esanum = theme == "esanum"
    bg = "#F5F5F5" if is_esanum else "rgba(255,255,255,0.04)"
    border = "1px solid #ECECEC" if is_esanum else "1px solid rgba(255,255,255,0.06)"
    text_color = "#333333" if is_esanum else "#e8e8f0"
    muted_color = "#737373" if is_esanum else "#8b8ba0"
    btn_bg = "#FFFFFF" if is_esanum else "rgba(255,255,255,0.06)"
    btn_border = "#DDDDDD" if is_esanum else "rgba(255,255,255,0.08)"
    btn_text = "#555555" if is_esanum else "#b8b8cc"
    btn_hover = "#F0F0F0" if is_esanum else "rgba(255,255,255,0.10)"

    initial = user["display_name"][0].upper()

    if is_esanum:
        avatar_gradient = "linear-gradient(135deg, #005461, #00A5AE)"
        glow_color = "rgba(0,84,97,0.3)"
        glow_hover = "rgba(0,84,97,0.5)"
        online_color = "#76A530"
    else:
        avatar_gradient = "linear-gradient(135deg, #a3e635, #22d3ee)"
        glow_color = "rgba(163,230,53,0.25)"
        glow_hover = "rgba(163,230,53,0.5)"
        online_color = "#a3e635"

    st.sidebar.markdown(
        '<style>'
        '@keyframes avatar-breathe { '
        '  0%,100% { box-shadow: 0 0 8px var(--avatar-glow), 0 0 20px var(--avatar-glow); } '
        '  50% { box-shadow: 0 0 14px var(--avatar-glow), 0 0 32px var(--avatar-glow); } '
        '} '
        '@keyframes online-pulse { '
        '  0%,100% { transform:scale(1); opacity:1; } '
        '  50% { transform:scale(1.3); opacity:0.7; } '
        '} '
        '.lumio-avatar-card:hover .lumio-avatar { '
        '  box-shadow: 0 0 16px var(--avatar-glow-hover), 0 0 36px var(--avatar-glow-hover) !important; '
        '  transform: scale(1.05); '
        '}'
        '</style>'
        f'<div class="lumio-avatar-card" style="'
        f'--avatar-glow:{glow_color};--avatar-glow-hover:{glow_hover};'
        f'padding:12px 14px;background:{bg};border:{border};'
        f'border-radius:14px;margin-bottom:8px;display:flex;align-items:center;gap:12px;'
        f'cursor:default;transition:all 0.3s ease">'
        # Avatar with glow
        f'<div style="position:relative;flex-shrink:0">'
        f'<div class="lumio-avatar" style="width:40px;height:40px;border-radius:50%;'
        f'background:{avatar_gradient};'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:17px;font-weight:700;color:#FFFFFF;letter-spacing:0.5px;'
        f'box-shadow:0 0 8px {glow_color}, 0 0 20px {glow_color};'
        f'animation:avatar-breathe 3s ease-in-out infinite;'
        f'transition:all 0.3s ease">'
        f'{initial}</div>'
        # Online indicator dot
        f'<div style="position:absolute;bottom:0;right:0;width:10px;height:10px;'
        f'border-radius:50%;background:{online_color};'
        f'border:2px solid {bg.split(";")[0] if ";" in bg else bg};'
        f'animation:online-pulse 2s ease-in-out infinite"></div>'
        f'</div>'
        # Name + username
        f'<div style="flex:1;min-width:0">'
        f'<div style="font-size:0.85rem;font-weight:700;color:{text_color};'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{user["display_name"]}</div>'
        f'<div style="font-size:0.68rem;color:{muted_color};margin-top:1px">@{user["username"]}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Flat action buttons — no Streamlit buttons, pure HTML + minimal style
    _uc1, _uc2 = st.sidebar.columns(2)
    with _uc1:
        if st.button("🔑 PW", key="pw_change_btn", use_container_width=True):
            st.session_state["_show_pw_change"] = not st.session_state.get("_show_pw_change", False)
            st.rerun()
    with _uc2:
        if st.button("Abmelden", key="logout_btn", use_container_width=True):
            track_activity("logout")
            # Invalidate persistent session token
            _token = st.query_params.get("session")
            if _token:
                try:
                    with get_raw_conn() as conn:
                        conn.execute(
                            text("DELETE FROM session_token WHERE token = :token"),
                            {"token": _token},
                        )
                except Exception:
                    pass
                st.query_params.clear()
            for key in ["current_user", "current_user_id", "session_id",
                         "_bookmarked_ids", "_show_pw_change", "theme"]:
                st.session_state.pop(key, None)
            st.rerun()

    # Password change form
    if st.session_state.get("_show_pw_change"):
        _render_password_change(user)


def _render_password_change(user: dict):
    """Render inline password change form in sidebar."""
    with st.sidebar.form("pw_change_form"):
        st.markdown("**Passwort ändern**")
        old_pw = st.text_input("Aktuelles Passwort", type="password", key="pw_old")
        new_pw = st.text_input("Neues Passwort", type="password", key="pw_new")
        new_pw2 = st.text_input("Neues Passwort bestätigen", type="password", key="pw_new2")
        submitted = st.form_submit_button("Ändern", use_container_width=True)

        if submitted:
            # Validate old password
            users = _get_all_users()
            current = [u for u in users if u["id"] == user["id"]]
            if not current or not _verify_password(old_pw, current[0]["password_hash"]):
                st.error("Aktuelles Passwort falsch.")
                return

            # Validate new password
            if len(new_pw) < 6:
                st.error("Mindestens 6 Zeichen.")
                return
            if new_pw != new_pw2:
                st.error("Passwörter stimmen nicht überein.")
                return

            # Update
            new_hash = _hash_password(new_pw)
            with get_raw_conn() as conn:
                conn.execute(
                    text('UPDATE "user" SET password_hash = :hash WHERE id = :uid'),
                    {"hash": new_hash, "uid": user["id"]},
                )

            track_activity("password_change")
            st.session_state["_show_pw_change"] = False
            st.success("Passwort geändert ✓")
            st.rerun()


def show_theme_toggle():
    """Render a small theme toggle button. Call in main content area (top-right)."""
    user = st.session_state.get("current_user")
    if not user:
        return

    _current_theme = st.session_state.get("theme", "dark")
    _theme_icon = "☀️" if _current_theme == "dark" else "🌙"
    _theme_tip = "esanum Light" if _current_theme == "dark" else "Dark Mode"

    # Inject as a fixed-position button via JS — triggers rerun via query param
    st.components.v1.html(f"""
    <script>
    (function(){{
        var pd = window.parent.document;
        var existing = pd.getElementById('lumio-theme-toggle');
        if (existing) existing.remove();

        var btn = pd.createElement('button');
        btn.id = 'lumio-theme-toggle';
        btn.textContent = '{_theme_icon}';
        btn.title = '{_theme_tip}';
        btn.style.cssText = 'position:fixed;top:10px;right:60px;z-index:9999;' +
            'width:36px;height:36px;border-radius:50%;border:1px solid rgba(128,128,128,0.2);' +
            'background:rgba(128,128,128,0.08);cursor:pointer;font-size:16px;' +
            'display:flex;align-items:center;justify-content:center;' +
            'transition:all 150ms ease;backdrop-filter:blur(8px);';
        btn.onmouseenter = function(){{ this.style.background = 'rgba(128,128,128,0.15)'; this.style.transform = 'scale(1.1)'; }};
        btn.onmouseleave = function(){{ this.style.background = 'rgba(128,128,128,0.08)'; this.style.transform = 'scale(1)'; }};

        // Toggle theme — push query param then use Streamlit's internal rerun
        btn.addEventListener('click', function(){{
            // Method 1: Try Streamlit's internal API
            var stApp = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
            if (stApp && stApp.__streamlitWebsocket) {{
                // Direct websocket approach
            }}
            // Method 2: Use pushState + force rerun via hidden form submit
            var url = new URL(window.parent.location.href);
            url.searchParams.set('_toggle_theme', '1');
            window.parent.history.pushState(null, '', url.toString());
            // Force Streamlit to notice the query param change
            window.parent.dispatchEvent(new Event('popstate'));
            // Fallback: soft reload after short delay if popstate didn't work
            setTimeout(function(){{
                if (window.parent.location.search.indexOf('_toggle_theme') > -1) {{
                    window.parent.location.reload();
                }}
            }}, 300);
        }});

        pd.body.appendChild(btn);
    }})();
    </script>
    """, height=0)


def is_admin() -> bool:
    """Check if current user is admin."""
    user = st.session_state.get("current_user", {})
    return user.get("role") == "admin"


# ---------------------------------------------------------------------------
# Theme Persistence
# ---------------------------------------------------------------------------

def _save_theme_preference(user_id: int, theme: str):
    """Save theme preference to DB."""
    try:
        import json
        now = datetime.now(timezone.utc).isoformat()
        with get_raw_conn() as conn:
            existing = conn.execute(
                text("SELECT id, profile_json FROM userprofile WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchone()
            if existing:
                profile = json.loads(existing[1] or "{}")
                profile["theme"] = theme
                conn.execute(
                    text("UPDATE userprofile SET profile_json = :pj, updated_at = :now WHERE user_id = :uid"),
                    {"pj": json.dumps(profile), "now": now, "uid": user_id},
                )
            else:
                conn.execute(
                    text("INSERT INTO userprofile (user_id, profile_json, updated_at) VALUES (:uid, :pj, :now)"),
                    {"uid": user_id, "pj": json.dumps({"theme": theme}), "now": now},
                )
    except Exception:
        pass  # Never break the app for theme persistence


def load_theme_preference(user_id: int) -> str:
    """Load theme preference from DB. Returns 'dark' as default."""
    try:
        import json
        with get_raw_conn() as conn:
            row = conn.execute(
                text("SELECT profile_json FROM userprofile WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchone()
        if row:
            profile = json.loads(row[0] or "{}")
            return profile.get("theme", "dark")
    except Exception:
        pass
    return "dark"


# ---------------------------------------------------------------------------
# Activity Tracking
# ---------------------------------------------------------------------------

def track_activity(action: str, detail: Optional[str] = None):
    """Log a user activity event. Fire-and-forget, never raises."""
    try:
        user_id = st.session_state.get("current_user_id", 0)
        session_id = st.session_state.get("session_id", "unknown")
        if user_id == 0:
            return

        from src.models import UserActivity
        with get_session() as session:
            session.add(UserActivity(
                user_id=user_id,
                action=action,
                detail=detail,
                session_id=session_id,
            ))
            session.commit()
    except Exception:
        pass  # Never break the app for tracking

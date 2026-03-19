"""Lumio API — lightweight FastAPI endpoints for n8n / external triggers."""

import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

app = FastAPI(title="Lumio API", docs_url=None, redoc_url=None)

# ---------------------------------------------------------------------------
# Rate limiting — in-memory, per-endpoint token bucket
# ---------------------------------------------------------------------------
_RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))  # max calls
_RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # seconds (1 hour)
_rate_limit_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(endpoint: str) -> None:
    """Raise 429 if the endpoint has been called too many times in the window."""
    now = time.monotonic()
    calls = _rate_limit_log[endpoint]
    # Prune expired entries
    _rate_limit_log[endpoint] = [t for t in calls if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_log[endpoint]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {_RATE_LIMIT_MAX} calls per {_RATE_LIMIT_WINDOW}s",
        )
    _rate_limit_log[endpoint].append(now)

# ---------------------------------------------------------------------------
# Auth — simple Bearer token from environment
# ---------------------------------------------------------------------------
_bearer = HTTPBearer()
API_TOKEN = os.getenv("API_TOKEN", "")


def _verify_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not API_TOKEN:
        raise HTTPException(503, "API_TOKEN not configured on server")
    if creds.credentials != API_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/api/pipeline/run", dependencies=[Depends(_verify_token)])
async def trigger_pipeline(days_back: int = 1):
    """Run the full ingestion + scoring pipeline."""
    _check_rate_limit("pipeline/run")

    from src.pipeline import run_pipeline

    logger.info("API: pipeline triggered (days_back=%d)", days_back)
    try:
        stats = await run_pipeline(days_back=days_back)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        raise HTTPException(500, f"Pipeline error: {exc}")
    return {"status": "ok", "stats": stats}


@app.post("/api/digest/send", dependencies=[Depends(_verify_token)])
def trigger_digest(email: str = ""):
    """Send the daily digest email."""
    from src.digest import send_digest

    to = email or os.getenv("DIGEST_EMAIL", "")
    if not to:
        raise HTTPException(400, "No recipient — set DIGEST_EMAIL or pass ?email=")

    logger.info("API: digest triggered for %s", to)
    ok = send_digest(to_email=to)
    if not ok:
        raise HTTPException(500, "Digest send failed — check SMTP config")
    return {"status": "ok", "sent_to": to}

"""Unified multi-provider LLM client using OpenAI-compatible APIs.

All target providers (Groq, Gemini, Mistral) expose an OpenAI-compatible
chat-completions endpoint. This module provides a single function that
tries providers in order until one succeeds (fallback chain).

Includes per-provider daily call tracking to warn before hitting free-tier
rate limits.

Anthropic SDK support: if an ``ANTHROPIC_API_KEY`` is set and no
OpenAI-compatible provider succeeds, the Anthropic SDK is used as a
final fallback — consolidating the previously scattered
``try: import anthropic`` blocks.

LLM response caching: ``cached_chat_completion`` wraps ``chat_completion``
with a file-based cache (``db/llm_cache/``, TTL 24 h) keyed on the hash
of (prompt + model) to avoid redundant API calls across pipeline restarts.
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

# One OpenAI client per (provider_name, key_index) (lazy-initialised).
_clients: Dict[str, Any] = {}

# ---------------------------------------------------------------------------
# Multi-Key Pool — rotate through multiple API keys per provider
# ---------------------------------------------------------------------------
# Env var naming: GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, ...
# Or:             GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3, ...
# Each key gets its own rate-limit tracking.

def _discover_keys(env_var_base: str) -> List[str]:
    """Find all API keys for a provider: BASE, BASE_2, BASE_3, ..."""
    keys = []
    # Primary key (e.g., GEMINI_API_KEY)
    primary = os.environ.get(env_var_base)
    if primary:
        keys.append(primary)
    # Additional keys (e.g., GEMINI_API_KEY_2, _3, ...)
    for i in range(2, 20):
        k = os.environ.get(f"{env_var_base}_{i}")
        if k:
            keys.append(k)
        else:
            break
    return keys


# {env_var_base: [key1, key2, ...]}  — populated lazily
_key_pools: Dict[str, List[str]] = {}
_key_pool_lock = threading.Lock()

# {provider_name: current_key_index}
_key_rotation_idx: Dict[str, int] = {}


def _get_key_pool(env_var_base: str) -> List[str]:
    """Return (and cache) the key pool for an env var base."""
    if env_var_base not in _key_pools:
        with _key_pool_lock:
            if env_var_base not in _key_pools:
                _key_pools[env_var_base] = _discover_keys(env_var_base)
                count = len(_key_pools[env_var_base])
                if count > 1:
                    logger.info(
                        "🔑 %s: %d API keys found → %dx limits",
                        env_var_base, count, count,
                    )
    return _key_pools[env_var_base]


# ---------------------------------------------------------------------------
# Rate-limit configuration (per provider PER KEY)
# ---------------------------------------------------------------------------
# RPM = requests per minute, RPD = requests per day (free-tier limits).
_RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "groq":             {"rpm": 28, "rpd": 14_400},
    "gemini_flash":     {"rpm": 14, "rpd": 1_500},
    "gemini_flash_lite":{"rpm": 28, "rpd": 3_000},
    "gemini_pro":       {"rpm": 4,  "rpd": 25},      # free-tier; paid ≫ this
    "mistral":          {"rpm": 28, "rpd": 5_000},
}

# {(provider_name, key_index): (date_str, count)}
_call_counts: Dict[str, tuple] = {}

# ---------------------------------------------------------------------------
# Token-bucket rate limiter (per provider, thread-safe)
# ---------------------------------------------------------------------------

class _TokenBucket:
    """Simple token-bucket rate limiter.

    Allows *rate* requests per 60 seconds with a small burst tolerance.
    ``acquire()`` blocks until a token is available.
    """

    def __init__(self, rate_per_minute: int):
        self.interval = 60.0 / max(rate_per_minute, 1)  # seconds between tokens
        self.lock = threading.Lock()
        self._timestamps: deque = deque()
        self.rpm = rate_per_minute

    def acquire(self) -> None:
        """Block until a request slot is available (respects RPM)."""
        while True:
            with self.lock:
                now = time.monotonic()
                # Purge timestamps older than 60 s
                while self._timestamps and now - self._timestamps[0] > 60.0:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.rpm:
                    self._timestamps.append(now)
                    return
                # Need to wait — calculate how long
                wait = 60.0 - (now - self._timestamps[0]) + 0.05
            time.sleep(max(wait, 0.1))


# Lazy-created buckets per provider
_buckets: Dict[str, _TokenBucket] = {}
_bucket_lock = threading.Lock()


def _get_bucket(bucket_key: str) -> _TokenBucket:
    """Return (or create) the token bucket for a provider/key combo.

    *bucket_key* is either ``"provider_name"`` or ``"provider_name#key_idx"``.
    """
    if bucket_key not in _buckets:
        with _bucket_lock:
            if bucket_key not in _buckets:
                # Extract base provider name for RPM lookup
                base_name = bucket_key.split("#")[0]
                rpm = _RATE_LIMITS.get(base_name, {}).get("rpm", 20)
                _buckets[bucket_key] = _TokenBucket(rpm)
    return _buckets[bucket_key]


def _track_call(provider_name: str, key_idx: int = 0) -> None:
    """Increment daily call counter for *provider_name* + key index."""
    tag = f"{provider_name}#{key_idx}"
    today = date.today()
    d, count = _call_counts.get(tag, (today, 0))
    if d != today:
        _call_counts[tag] = (today, 1)
    else:
        _call_counts[tag] = (today, count + 1)

    new_count = _call_counts[tag][1]
    limit = _RATE_LIMITS.get(provider_name, {}).get("rpd", 10_000)

    if new_count == int(limit * 0.8):
        logger.warning(
            "⚠️  %s (key %d): 80%% of daily limit reached (%d/%d)",
            provider_name, key_idx, new_count, limit,
        )
    elif new_count >= limit:
        logger.warning(
            "🛑 %s (key %d): daily limit reached (%d/%d)",
            provider_name, key_idx, new_count, limit,
        )


def _mark_key_429(provider_name: str, key_idx: int) -> None:
    """Mark a key as externally rate-limited (got HTTP 429)."""
    tag = f"{provider_name}#{key_idx}"
    _429_until[tag] = time.monotonic() + 300  # skip for 5 min


# {tag: monotonic_time_until_which_to_skip}
_429_until: Dict[str, float] = {}


def _is_key_rate_limited(provider_name: str, key_idx: int) -> bool:
    """Check whether a specific key has exhausted its daily limit or got 429."""
    tag = f"{provider_name}#{key_idx}"

    # Check external 429 block first
    block_until = _429_until.get(tag, 0)
    if block_until and time.monotonic() < block_until:
        return True

    today = date.today()
    d, count = _call_counts.get(tag, (today, 0))
    if d != today:
        return False
    return count >= _RATE_LIMITS.get(provider_name, {}).get("rpd", 10_000)


def _is_rate_limited(provider_name: str) -> bool:
    """Check whether ALL keys for *provider_name* are exhausted."""
    from src.config import LLM_PROVIDERS
    provider = LLM_PROVIDERS.get(provider_name)
    if not provider:
        return True
    keys = _get_key_pool(provider.api_key_env)
    if not keys:
        return True
    return all(_is_key_rate_limited(provider_name, i) for i in range(len(keys)))


def get_usage_stats() -> Dict[str, dict]:
    """Return current daily usage stats for all tracked providers.

    Aggregates across all keys per provider. Shows total calls,
    total available limits, and per-key breakdown.
    """
    today = date.today()
    # Aggregate by provider name
    provider_totals: Dict[str, Dict] = {}
    for tag, (d, count) in _call_counts.items():
        if d != today:
            continue
        # tag format: "provider_name#key_idx"
        parts = tag.split("#", 1)
        prov_name = parts[0]
        key_idx = int(parts[1]) if len(parts) > 1 else 0

        if prov_name not in provider_totals:
            base_limits = _RATE_LIMITS.get(prov_name, {})
            provider_totals[prov_name] = {
                "calls_today": 0,
                "keys": 0,
                "per_key_rpd": base_limits.get("rpd", 10_000),
                "rpm_limit": base_limits.get("rpm", 20),
                "key_details": [],
            }
        pt = provider_totals[prov_name]
        pt["calls_today"] += count
        pt["keys"] = max(pt["keys"], key_idx + 1)
        pt["key_details"].append({"key_idx": key_idx, "calls": count})

    stats = {}
    for name, pt in provider_totals.items():
        total_rpd = pt["per_key_rpd"] * max(pt["keys"], 1)
        stats[name] = {
            "calls_today": pt["calls_today"],
            "daily_limit": total_rpd,
            "num_keys": pt["keys"],
            "rpm_limit": pt["rpm_limit"],
            "pct_used": round(pt["calls_today"] / total_rpd * 100, 1) if total_rpd else 0,
            "key_details": pt["key_details"],
        }
    return stats


# ---------------------------------------------------------------------------
# LLM response cache (file-based, 24 h TTL)
# ---------------------------------------------------------------------------

_CACHE_DIR: Optional[Path] = None
_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds


def _get_cache_dir() -> Path:
    """Return (and lazily create) the cache directory ``db/llm_cache/``."""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        from src.config import PROJECT_ROOT
        _CACHE_DIR = PROJECT_ROOT / "db" / "llm_cache"
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _cache_key(prompt_text: str, model: str) -> str:
    """SHA-256 hex digest of (prompt + model)."""
    raw = f"{model}||{prompt_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[str]:
    """Read a cached response if it exists and is within TTL."""
    path = _get_cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
        if time.time() - data.get("ts", 0) > _CACHE_TTL:
            path.unlink(missing_ok=True)
            return None
        return data.get("response")
    except Exception:
        return None


def _cache_put(key: str, response: str) -> None:
    """Write a response to the file cache."""
    path = _get_cache_dir() / f"{key}.json"
    try:
        path.write_text(
            json.dumps({"ts": time.time(), "response": response}),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("Cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Anthropic SDK fallback (consolidated from summarizer / trends)
# ---------------------------------------------------------------------------

_anthropic_client: Any = None
_anthropic_checked = False


def _get_anthropic_client():
    """Lazy-init Anthropic client.  Returns ``None`` if unavailable."""
    global _anthropic_client, _anthropic_checked
    if _anthropic_checked:
        return _anthropic_client

    _anthropic_checked = True
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
        return _anthropic_client
    except Exception as e:
        logger.warning("Could not init Anthropic client: %s", e)
        return None


def _anthropic_chat(
    messages: List[Dict[str, str]],
    system: Optional[str],
    max_tokens: int,
) -> Optional[str]:
    """Call the Anthropic Messages API as a last-resort fallback.

    Returns the stripped response text or ``None``.
    """
    client = _get_anthropic_client()
    if client is None:
        return None

    from src.config import LLM_MODEL, LLM_TIMEOUT

    # The Anthropic SDK takes ``system`` as a top-level kwarg, not a message.
    try:
        kwargs: dict = {
            "model": LLM_MODEL,
            "max_tokens": max_tokens,
            "messages": messages,
            "timeout": LLM_TIMEOUT,
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        if response.content:
            _track_call("anthropic")
            return response.content[0].text.strip()
        logger.warning("Empty Anthropic response")
    except Exception as exc:
        # Don't count failed calls toward daily limit
        logger.warning("Anthropic fallback failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Client management
# ---------------------------------------------------------------------------

def _get_client(provider, key_idx: int = 0):
    """Lazy-init an OpenAI-compatible client for *provider* + key index.

    Returns ``None`` when the required API-key is not available.
    """
    cache_key = f"{provider.name}#{key_idx}"
    if cache_key in _clients:
        return _clients[cache_key]

    keys = _get_key_pool(provider.api_key_env)
    if not keys or key_idx >= len(keys):
        return None

    api_key = keys[key_idx]
    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=provider.base_url,
            api_key=api_key,
            timeout=provider.timeout,
        )
        _clients[cache_key] = client
        return client
    except Exception as exc:
        logger.warning("Could not init %s (key %d): %s", provider.name, key_idx, exc)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def chat_completion(
    providers: List[Any],
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    """Send a chat-completion request, trying *providers* in order.

    Parameters
    ----------
    providers:
        Ordered list of ``LLMProvider`` objects (primary first, then
        fallbacks).
    messages:
        Chat messages, e.g. ``[{"role": "user", "content": "..."}]``.
    system:
        Optional system prompt — prepended as a ``system`` role message.
    max_tokens:
        Override the provider default if set.

    Returns
    -------
    The stripped response text, or ``None`` if every provider failed.
    """
    full_messages: List[Dict[str, str]] = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    for provider in (providers or []):
        keys = _get_key_pool(provider.api_key_env)
        if not keys:
            logger.debug("Skipping %s — no API key (%s)", provider.name, provider.api_key_env)
            continue

        # Try each key in round-robin order
        num_keys = len(keys)
        start_idx = _key_rotation_idx.get(provider.name, 0) % num_keys

        for offset in range(num_keys):
            key_idx = (start_idx + offset) % num_keys

            # Skip this key if its daily limit is exhausted
            if _is_key_rate_limited(provider.name, key_idx):
                continue

            client = _get_client(provider, key_idx)
            if client is None:
                continue

            # ---- RPM throttle: wait for a slot in the token bucket ----
            bucket = _get_bucket(f"{provider.name}#{key_idx}")
            bucket.acquire()

            tokens = max_tokens or provider.max_tokens
            try:
                response = client.chat.completions.create(
                    model=provider.model,
                    max_tokens=tokens,
                    messages=full_messages,
                )
                text = response.choices[0].message.content
                _track_call(provider.name, key_idx)
                # Advance rotation to next key for fairness
                _key_rotation_idx[provider.name] = (key_idx + 1) % num_keys
                if text:
                    logger.debug(
                        "LLM response from %s (key %d/%d, %s)",
                        provider.name, key_idx + 1, num_keys, provider.model,
                    )
                    return text.strip()
                logger.warning("Empty response from %s (key %d)", provider.name, key_idx)
            except Exception as exc:
                # Don't count failed calls toward daily limit
                logger.warning("LLM call to %s (key %d) failed: %s", provider.name, key_idx, exc)
                # Mark 429 errors so we skip this key for 5 minutes
                exc_str = str(exc)
                if "429" in exc_str or "rate_limit" in exc_str.lower() or "quota" in exc_str.lower():
                    _mark_key_429(provider.name, key_idx)
                # Try next key
                continue

    # ------------------------------------------------------------------
    # Anthropic SDK fallback (last resort)
    # ------------------------------------------------------------------
    user_messages = [m for m in messages if m.get("role") != "system"]
    result = _anthropic_chat(user_messages or messages, system, max_tokens or 300)
    if result:
        return result

    return None


# ---------------------------------------------------------------------------
# Cached wrapper
# ---------------------------------------------------------------------------

def cached_chat_completion(
    providers: List[Any],
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    """Like ``chat_completion`` but with a 24 h file-based cache.

    Cache key = SHA-256(model_of_first_provider + system + user messages).
    """
    # Build a deterministic string for the cache key
    model_hint = providers[0].model if providers else "anthropic"
    prompt_parts = []
    if system:
        prompt_parts.append(f"system:{system}")
    for m in messages:
        prompt_parts.append(f"{m.get('role', '')}:{m.get('content', '')}")
    prompt_text = "\n".join(prompt_parts)

    key = _cache_key(prompt_text, model_hint)
    cached = _cache_get(key)
    if cached is not None:
        logger.debug("LLM cache hit (%s…)", key[:12])
        return cached

    result = chat_completion(
        providers=providers,
        messages=messages,
        system=system,
        max_tokens=max_tokens,
    )
    if result is not None:
        _cache_put(key, result)
    return result


# ---------------------------------------------------------------------------
# Concurrent batch helper
# ---------------------------------------------------------------------------

def map_concurrent(
    fn: Callable[..., T],
    items: List[Any],
    max_workers: int = 4,
) -> List[T]:
    """Apply *fn* to each item in *items* using a thread pool.

    Returns results in the **same order** as *items*.
    Useful for running many independent LLM calls in parallel without
    async/await.

    Parameters
    ----------
    fn:
        Callable that takes a single item and returns a result.
    items:
        List of inputs for *fn*.
    max_workers:
        Max concurrent threads.  Keep ≤5 for free-tier APIs to avoid
        rate-limit bursts.

    Returns
    -------
    List of results, same length and order as *items*.
    """
    if not items:
        return []

    # For very small lists, don't bother with threads
    if len(items) <= 2:
        return [fn(item) for item in items]

    results: List[Optional[T]] = [None] * len(items)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(fn, item): idx
            for idx, item in enumerate(items)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.warning("Concurrent task %d failed: %s", idx, exc)
                results[idx] = None

    return results

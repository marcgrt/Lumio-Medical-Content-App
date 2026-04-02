"""Lumio Health Check — probes all LLM providers, DB, and pipeline status.

Run standalone:  python -m src.health_check
Called by pipeline as post-run check.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM provider probe
# ---------------------------------------------------------------------------

def check_llm_providers() -> List[dict]:
    """Ping each configured LLM provider with a minimal request.

    Returns list of {name, model, status, error, latency_ms}.
    """
    from src.config import LLM_PROVIDERS

    results = []
    for name, provider in LLM_PROVIDERS.items():
        api_key = os.environ.get(provider.api_key_env)
        if not api_key:
            results.append({
                "name": name, "model": provider.model,
                "status": "skip", "error": f"No {provider.api_key_env}", "latency_ms": 0,
            })
            continue

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url=provider.base_url,
                timeout=10.0,
            )
            start = datetime.now()
            resp = client.chat.completions.create(
                model=provider.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "Reply with OK"}],
            )
            latency = (datetime.now() - start).total_seconds() * 1000
            text = (resp.choices[0].message.content or "").strip() if resp.choices else ""

            if not text:
                results.append({
                    "name": name, "model": provider.model,
                    "status": "warn", "error": "Empty response", "latency_ms": round(latency),
                })
            else:
                results.append({
                    "name": name, "model": provider.model,
                    "status": "ok", "error": None, "latency_ms": round(latency),
                })
        except Exception as e:
            error_msg = str(e)[:200]
            # Detect common issues
            if "404" in error_msg:
                error_msg = f"MODEL DEPRECATED/NOT FOUND: {provider.model}"
            elif "401" in error_msg or "403" in error_msg:
                error_msg = f"AUTH FAILED for {provider.api_key_env}"
            elif "429" in error_msg:
                error_msg = f"RATE LIMITED: {name}"

            results.append({
                "name": name, "model": provider.model,
                "status": "fail", "error": error_msg, "latency_ms": 0,
            })

    return results


# ---------------------------------------------------------------------------
# Rate limit / quota check (parse last pipeline log)
# ---------------------------------------------------------------------------

def check_rate_limits() -> List[dict]:
    """Parse the latest pipeline log for 429 rate-limit errors per provider.

    Returns list of {provider, count_429, last_error}.
    """
    import re
    log_dir = Path(__file__).resolve().parent.parent / "db" / "logs"
    logs = sorted(log_dir.glob("pipeline_*.log"), reverse=True)
    if not logs:
        return []

    content = logs[0].read_text(errors="replace")
    # Count 429 errors per provider
    pattern = re.compile(r"LLM call to (\w+) .* failed: Error code: 429")
    provider_429: dict = {}
    for match in pattern.finditer(content):
        prov = match.group(1)
        provider_429[prov] = provider_429.get(prov, 0) + 1

    results = []
    for prov, count in sorted(provider_429.items(), key=lambda x: -x[1]):
        results.append({
            "provider": prov,
            "count_429": count,
            "status": "fail" if count > 10 else "warn",
        })

    return results


# ---------------------------------------------------------------------------
# Summary quality check
# ---------------------------------------------------------------------------

def check_summary_quality() -> dict:
    """Check how many recent articles have poor template summaries."""
    from src.db import get_raw_conn
    from sqlalchemy import text

    result = {"status": "ok", "template_count": 0, "llm_count": 0, "total": 0}
    try:
        _cutoff_3d = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        with get_raw_conn() as conn:
            row = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN summary_de NOT ILIKE '%PRAXIS:%' THEN 1 ELSE 0 END) as template_count
                FROM article
                WHERE created_at >= :cutoff AND summary_de IS NOT NULL
            """), {"cutoff": _cutoff_3d}).fetchone()
        result["total"] = row[0] or 0
        result["template_count"] = row[1] or 0
        result["llm_count"] = result["total"] - result["template_count"]

        if result["total"] > 0:
            template_pct = result["template_count"] / result["total"] * 100
            if template_pct > 80:
                result["status"] = "fail"
                result["error"] = f"{template_pct:.0f}% template summaries — LLM providers likely down"
            elif template_pct > 50:
                result["status"] = "warn"
                result["error"] = f"{template_pct:.0f}% template summaries — LLM capacity low"
    except Exception as e:
        result["status"] = "warn"
        result["error"] = str(e)[:100]

    return result


# ---------------------------------------------------------------------------
# Database check
# ---------------------------------------------------------------------------

def check_database() -> dict:
    """Check DB health: row counts, integrity, freshness."""
    from src.db import get_raw_conn, is_sqlite
    from sqlalchemy import text

    result = {"status": "ok", "errors": []}

    try:
        _cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with get_raw_conn() as conn:
            # Integrity
            if is_sqlite():
                integrity = conn.execute(text("PRAGMA integrity_check")).fetchone()[0]
                if integrity != "ok":
                    result["errors"].append(f"Integrity check failed: {integrity}")
                    result["status"] = "fail"
            else:
                # PostgreSQL: simple connectivity check
                conn.execute(text("SELECT 1"))

            # Row count
            total = conn.execute(text("SELECT COUNT(*) FROM article")).fetchone()[0]
            result["total_articles"] = total

            # Freshness: any articles in last 24h?
            recent = conn.execute(
                text("SELECT COUNT(*) FROM article WHERE created_at >= :cutoff"),
                {"cutoff": _cutoff_24h},
            ).fetchone()[0]
            result["articles_last_24h"] = recent
            if recent == 0:
                result["errors"].append("No new articles in last 24h — pipeline may be stalled")
                result["status"] = "warn"

        # DB size (only meaningful for SQLite)
        if is_sqlite():
            from src.config import DB_PATH
            result["db_size_mb"] = round(os.path.getsize(str(DB_PATH)) / 1024 / 1024, 1)
        else:
            result["db_size_mb"] = None
    except Exception as e:
        result["status"] = "fail"
        result["errors"].append(str(e)[:200])

    return result


# ---------------------------------------------------------------------------
# Pipeline log check
# ---------------------------------------------------------------------------

def check_pipeline_logs() -> dict:
    """Check latest pipeline log for completion and errors."""
    log_dir = Path(__file__).resolve().parent.parent / "db" / "logs"
    result = {"status": "ok", "errors": [], "last_run": None}

    # Find most recent pipeline log
    logs = sorted(log_dir.glob("pipeline_*.log"), reverse=True)
    if not logs:
        result["status"] = "warn"
        result["errors"].append("No pipeline logs found")
        return result

    latest = logs[0]
    result["last_log"] = latest.name

    content = latest.read_text(errors="replace")

    # Check completion
    if "PIPELINE COMPLETE" in content:
        result["completed"] = True
    else:
        result["completed"] = False
        result["errors"].append("Pipeline did not complete successfully")
        result["status"] = "warn"

    # Check for crash (Traceback in log)
    if "Traceback" in content:
        result["status"] = "fail"
        # Extract the last line of the traceback (the actual error)
        tb_lines = content.split("Traceback")[-1].splitlines()
        for line in reversed(tb_lines):
            line = line.strip()
            if line and not line.startswith("File ") and not line.startswith("^"):
                result["errors"].append(f"PIPELINE CRASH: {line[:150]}")
                break

    # Check freshness: when was the last successful import?
    try:
        from src.db import get_raw_conn
        from sqlalchemy import text
        with get_raw_conn() as conn:
            last_import = conn.execute(
                text("SELECT created_at FROM article ORDER BY created_at DESC LIMIT 1")
            ).fetchone()
        if last_import:
            result["last_import"] = last_import[0][:19]
            last_dt = datetime.fromisoformat(last_import[0][:19])
            hours_ago = (datetime.now(timezone.utc) - last_dt.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            result["hours_since_import"] = round(hours_ago, 1)
            if hours_ago > 24:
                result["status"] = "fail"
                result["errors"].append(
                    f"PIPELINE STALLED: Kein Import seit {hours_ago:.0f}h (letzter: {result['last_import']})"
                )
            elif hours_ago > 12:
                if result["status"] == "ok":
                    result["status"] = "warn"
                result["errors"].append(f"Pipeline verspätet: {hours_ago:.0f}h seit letztem Import")
    except Exception:
        pass

    # Count real errors (exclude known transient ones)
    error_lines = []
    for line in content.splitlines():
        if "[ERROR]" in line:
            # Skip known transient external API errors
            if any(skip in line for skip in [
                "request failed:", "503", "502", "timeout",
                "ConnectionError", "ReadTimeout",
            ]):
                continue
            error_lines.append(line.strip()[-120:])

    if error_lines:
        result["errors"].extend(error_lines[:5])
        if result["status"] == "ok":
            result["status"] = "warn"

    # Extract stats if available
    for line in content.splitlines():
        if "Stored (new):" in line:
            result["last_stored"] = line.strip().split(":")[-1].strip()
        if "Duration:" in line:
            result["last_duration"] = line.strip().split(":")[-1].strip()

    return result


# ---------------------------------------------------------------------------
# Full health report
# ---------------------------------------------------------------------------

def run_health_check() -> dict:
    """Run all checks, return combined report."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "llm_providers": check_llm_providers(),
        "rate_limits": check_rate_limits(),
        "summary_quality": check_summary_quality(),
        "database": check_database(),
        "pipeline": check_pipeline_logs(),
    }

    # Overall status
    statuses = []
    for p in report["llm_providers"]:
        if p["status"] == "fail":
            statuses.append("fail")
        elif p["status"] == "warn":
            statuses.append("warn")
    for rl in report["rate_limits"]:
        statuses.append(rl["status"])
    statuses.append(report["summary_quality"]["status"])
    statuses.append(report["database"]["status"])
    statuses.append(report["pipeline"]["status"])

    if "fail" in statuses:
        report["overall"] = "FAIL"
    elif "warn" in statuses:
        report["overall"] = "WARN"
    else:
        report["overall"] = "OK"

    return report


def format_report(report: dict) -> str:
    """Format health report as human-readable text."""
    lines = []
    lines.append(f"=== LUMIO HEALTH CHECK ({report['timestamp'][:19]}) ===")
    lines.append(f"Overall: {report['overall']}")
    lines.append("")

    # LLM providers
    lines.append("LLM Providers:")
    for p in report["llm_providers"]:
        icon = {"ok": "OK", "warn": "!!", "fail": "XX", "skip": "--"}[p["status"]]
        latency = f" ({p['latency_ms']}ms)" if p["latency_ms"] else ""
        error = f" — {p['error']}" if p["error"] else ""
        lines.append(f"  [{icon}] {p['name']:20s} {p['model']:30s}{latency}{error}")

    # Rate limits
    if report.get("rate_limits"):
        lines.append("")
        lines.append("Rate Limits (last pipeline run):")
        for rl in report["rate_limits"]:
            icon = "XX" if rl["status"] == "fail" else "!!"
            lines.append(f"  [{icon}] {rl['provider']:20s} {rl['count_429']} x 429 errors")

    # Summary quality
    lines.append("")
    sq = report.get("summary_quality", {})
    sq_status = sq.get("status", "ok").upper()
    lines.append(f"Summary Quality (last 3 days): {sq_status}")
    if sq.get("total"):
        lines.append(f"  LLM summaries: {sq['llm_count']}, Template fallback: {sq['template_count']}, Total: {sq['total']}")
    if sq.get("error"):
        lines.append(f"  !! {sq['error']}")

    # Database
    lines.append("")
    db = report["database"]
    lines.append(f"Database: {db['status'].upper()}")
    lines.append(f"  Articles: {db.get('total_articles', '?')} total, {db.get('articles_last_24h', '?')} last 24h")
    lines.append(f"  Size: {db.get('db_size_mb', '?')} MB")
    for e in db.get("errors", []):
        lines.append(f"  !! {e}")

    # Pipeline
    lines.append("")
    pl = report["pipeline"]
    lines.append(f"Pipeline: {pl['status'].upper()}")
    if pl.get("last_log"):
        lines.append(f"  Last log: {pl['last_log']}")
    if pl.get("last_stored"):
        lines.append(f"  Stored: {pl['last_stored']} new articles")
    for e in pl.get("errors", []):
        lines.append(f"  !! {e}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def notify_admin(report: dict):
    """Write a notification to the DB for the admin user when health check fails."""
    if report["overall"] == "OK":
        return

    from src.db import get_raw_conn
    from sqlalchemy import text

    # Collect all errors
    all_errors = []
    for p in report.get("llm_providers", []):
        if p["status"] == "fail":
            all_errors.append(f"LLM {p['name']}: {p.get('error', 'down')}")
    pl = report.get("pipeline", {})
    for e in pl.get("errors", []):
        all_errors.append(e)
    db_report = report.get("database", {})
    for e in db_report.get("errors", []):
        all_errors.append(e)
    sq = report.get("summary_quality", {})
    if sq.get("error"):
        all_errors.append(sq["error"])

    if not all_errors:
        return

    message = f"⚠️ Health Check {report['overall']}: {' | '.join(all_errors[:3])}"

    try:
        now = datetime.now(timezone.utc).isoformat()
        _cutoff_6h = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        with get_raw_conn() as conn:
            # Find admin user(s)
            admins = conn.execute(text("SELECT id FROM \"user\" WHERE role = 'admin'")).fetchall()
            for (admin_id,) in admins:
                # Avoid duplicate notifications (check last 6h)
                existing = conn.execute(
                    text("SELECT COUNT(*) FROM notification WHERE user_id = :uid AND type = 'health_check' "
                         "AND created_at > :cutoff"),
                    {"uid": admin_id, "cutoff": _cutoff_6h},
                ).fetchone()[0]
                if existing == 0:
                    conn.execute(
                        text("INSERT INTO notification (user_id, type, message, is_read, created_at) "
                             "VALUES (:uid, 'health_check', :msg, false, :now)"),
                        {"uid": admin_id, "msg": message[:500], "now": now},
                    )
        logger.info(f"Admin notification sent: {message[:80]}")
    except Exception as e:
        logger.warning(f"Failed to notify admin: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    report = run_health_check()
    print(format_report(report))

    # Notify admin in-app
    notify_admin(report)

    if report["overall"] == "FAIL":
        sys.exit(1)
    elif report["overall"] == "WARN":
        sys.exit(2)
    sys.exit(0)

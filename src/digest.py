"""Lumio E-Mail Digest — sends top-10 daily feed as HTML email."""

import html
import logging
import os
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlmodel import select, col

from src.config import SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MID
from src.models import Article, get_engine, get_session

logger = logging.getLogger(__name__)


def _score_color(score: float) -> str:
    if score >= SCORE_THRESHOLD_HIGH:
        return "#22c55e"
    elif score >= SCORE_THRESHOLD_MID:
        return "#eab308"
    return "#ef4444"


def _build_html(articles: list[Article], run_date: date) -> str:
    """Build HTML email body for the daily digest."""
    rows = ""
    for i, a in enumerate(articles, 1):
        color = _score_color(a.relevance_score)
        specialty = a.specialty or "—"
        journal = a.journal or "—"
        pub = a.pub_date.strftime("%d.%m.%Y") if a.pub_date else "—"
        summary = a.summary_de or "Keine Zusammenfassung verfügbar."
        # Split structured summary parts (LLM uses ;;;, template uses ;;;)
        summary_html = "<br>".join(
            f"<small>{html.escape(part.strip())}</small>"
            for part in summary.split(";;;")
            if part.strip()
        )
        alert = "🚨 " if a.status == "ALERT" else ""

        rows += f"""
        <tr style="border-bottom:1px solid #e2e8f0">
            <td style="padding:12px 8px;text-align:center;vertical-align:top">
                <span style="background:{color};color:white;padding:3px 10px;
                       border-radius:12px;font-weight:bold;font-size:14px">
                    {a.relevance_score:.0f}
                </span>
            </td>
            <td style="padding:12px 8px;vertical-align:top">
                <div>
                    <a href="{html.escape(a.url, quote=True)}" style="color:#2563eb;text-decoration:none;
                       font-weight:600;font-size:15px">
                        {alert}{html.escape(a.title)}
                    </a>
                </div>
                <div style="color:#64748b;font-size:12px;margin:4px 0">
                    📰 {html.escape(journal)} · 📅 {pub} · 🏷️ {html.escape(specialty)}
                </div>
                <div style="margin-top:6px;color:#334155;font-size:13px;
                       line-height:1.5">
                    {summary_html}
                </div>
            </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                 max-width:700px;margin:0 auto;padding:20px;color:#1e293b">
        <div style="text-align:center;padding:20px 0;border-bottom:2px solid #2563eb">
            <h1 style="margin:0;color:#2563eb;font-size:24px">
                ✨ Lumio Tages-Digest
            </h1>
            <p style="color:#64748b;margin:8px 0 0">
                {run_date.strftime('%A, %d. %B %Y')} · Top {len(articles)} Artikel
            </p>
        </div>

        <table style="width:100%;border-collapse:collapse;margin-top:16px">
            {rows}
        </table>

        <div style="text-align:center;padding:20px 0;margin-top:20px;
                    border-top:1px solid #e2e8f0;color:#94a3b8;font-size:12px">
            Lumio<br>
            Automatisch generiert · Alle Zusammenfassungen prüfen
        </div>
    </body>
    </html>
    """


def get_top_articles(n: int = 10, days_back: int = 2, max_per_specialty: int = 3) -> list[Article]:
    """Fetch top N articles, diversified by specialty and freshness-weighted.

    Sorting: pub_date recency is the primary signal, relevance_score secondary.
    A newer article with score 60 beats an older one with score 85.
    Max ``max_per_specialty`` articles per specialty to ensure breadth.

    Tries ``days_back`` first; if fewer than 3 results, widens to 7 days.
    Falls back to all-time if still empty.
    """
    get_engine()

    # Fetch a larger pool, then diversify in Python
    pool_size = n * 5

    def _query(since: date) -> list:
        with get_session() as session:
            stmt = (
                select(Article)
                .where(Article.pub_date >= since)
                .order_by(
                    col(Article.pub_date).desc(),
                    col(Article.relevance_score).desc(),
                )
                .limit(pool_size)
            )
            return list(session.exec(stmt).all())

    cutoff = date.today() - timedelta(days=days_back)
    pool = _query(cutoff)

    # Widen to 7 days if too few results
    if len(pool) < 3 and days_back < 7:
        pool = _query(date.today() - timedelta(days=7))

    # Final fallback: all-time
    if not pool:
        with get_session() as session:
            stmt = (
                select(Article)
                .order_by(
                    col(Article.pub_date).desc(),
                    col(Article.relevance_score).desc(),
                )
                .limit(pool_size)
            )
            pool = list(session.exec(stmt).all())

    # Diversify: pick top articles but cap per specialty
    articles = []
    specialty_counts: dict = {}
    for a in pool:
        spec = a.specialty or "Sonstige"
        if specialty_counts.get(spec, 0) >= max_per_specialty:
            continue
        articles.append(a)
        specialty_counts[spec] = specialty_counts.get(spec, 0) + 1
        if len(articles) >= n:
            break

    # Detach from session
    return [
        Article(
            id=a.id, title=a.title, abstract=a.abstract, url=a.url,
            source=a.source, journal=a.journal, pub_date=a.pub_date,
            authors=a.authors, doi=a.doi, study_type=a.study_type,
            mesh_terms=a.mesh_terms, language=a.language,
            relevance_score=a.relevance_score, specialty=a.specialty,
            summary_de=a.summary_de, status=a.status,
            highlight_tags=a.highlight_tags,
            score_breakdown=a.score_breakdown,
            created_at=a.created_at,
        )
        for a in articles
    ]


def send_digest(
    to_email: str,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_pass: str = "",
    from_email: str = "",
    n_articles: int = 10,
) -> bool:
    """Send the daily digest email.

    Reads SMTP config from environment if not provided:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
    """
    smtp_host = smtp_host or os.getenv("SMTP_HOST", "")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", str(smtp_port)))
    except ValueError:
        logger.error("Invalid SMTP_PORT: %s — using default 587", os.getenv("SMTP_PORT"))
        smtp_port = 587
    smtp_user = smtp_user or os.getenv("SMTP_USER", "")
    smtp_pass = smtp_pass or os.getenv("SMTP_PASS", "")
    from_email = from_email or os.getenv("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, to_email]):
        logger.error(
            "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars."
        )
        return False

    articles = get_top_articles(n_articles)
    if not articles:
        logger.warning("No articles to send in digest.")
        return False

    today = date.today()
    html = _build_html(articles, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Lumio Digest — {today.strftime('%d.%m.%Y')}"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Digest sent to %s (%d articles)", to_email, len(articles))
        return True
    except Exception as exc:
        logger.error("Failed to send digest: %s", exc)
        return False


def save_digest_html(output_path: str = "digest.html", n_articles: int = 10):
    """Save digest as local HTML file (for preview without SMTP)."""
    articles = get_top_articles(n_articles)
    if not articles:
        logger.warning("No articles for digest preview.")
        return

    html = _build_html(articles, date.today())
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Digest HTML saved to %s", output_path)


def send_pipeline_alert(subject: str, body: str) -> bool:
    """Send a lightweight alert email (e.g. pipeline failure, LLM outage).

    Uses the same SMTP config as the digest. Returns False silently if
    SMTP is not configured (no crash).
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)
    to_email = os.getenv("ALERT_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, to_email]):
        logger.debug("SMTP not configured — alert email skipped.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚠️ Lumio Alert: {subject}"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Alert email sent to %s: %s", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send alert email: %s", exc)
        return False


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        save_digest_html()
        print("Digest preview saved to digest.html")
    elif len(sys.argv) > 1:
        send_digest(to_email=sys.argv[1])
    else:
        print("Usage:")
        print("  python -m src.digest --preview          # Save HTML preview")
        print("  python -m src.digest user@example.com   # Send email")

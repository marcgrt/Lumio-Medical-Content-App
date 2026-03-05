"""MedIntel E-Mail Digest — sends top-10 daily briefing as HTML email."""

import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlmodel import select, col

from src.models import Article, get_engine, get_session

logger = logging.getLogger(__name__)


def _score_color(score: float) -> str:
    if score >= 75:
        return "#22c55e"
    elif score >= 50:
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
        # Split template summary parts
        summary_html = "<br>".join(
            f"<small>{part.strip()}</small>"
            for part in summary.split(" | ")
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
                    <a href="{a.url}" style="color:#2563eb;text-decoration:none;
                       font-weight:600;font-size:15px">
                        {alert}{a.title}
                    </a>
                </div>
                <div style="color:#64748b;font-size:12px;margin:4px 0">
                    📰 {journal} · 📅 {pub} · 🏷️ {specialty}
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
                🩺 MedIntel Tages-Briefing
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
            MedIntel — Medical Intelligence Briefing<br>
            Automatisch generiert · Alle Zusammenfassungen prüfen
        </div>
    </body>
    </html>
    """


def get_top_articles(n: int = 10) -> list[Article]:
    """Fetch top N articles by relevance score for today."""
    get_engine()
    with get_session() as session:
        stmt = (
            select(Article)
            .order_by(col(Article.relevance_score).desc())
            .limit(n)
        )
        articles = session.exec(stmt).all()
        # Detach from session
        return [
            Article(
                id=a.id, title=a.title, abstract=a.abstract, url=a.url,
                source=a.source, journal=a.journal, pub_date=a.pub_date,
                authors=a.authors, doi=a.doi, study_type=a.study_type,
                mesh_terms=a.mesh_terms, language=a.language,
                relevance_score=a.relevance_score, specialty=a.specialty,
                summary_de=a.summary_de, status=a.status,
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
    smtp_port = int(os.getenv("SMTP_PORT", str(smtp_port)))
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
    msg["Subject"] = f"MedIntel Briefing — {today.strftime('%d.%m.%Y')}"
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

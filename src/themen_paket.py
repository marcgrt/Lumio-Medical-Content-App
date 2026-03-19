"""Themen-Paket — Automatisierte Recherche-Pakete per Email pro Watchlist."""

from __future__ import annotations

import html as html_mod
import json
import logging
import os
import smtplib
from collections import Counter
from datetime import datetime, date, timedelta, timezone
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from sqlmodel import select, col, func, and_

from src.config import SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MID
from src.models import Article, Watchlist, WatchlistMatch, get_session

logger = logging.getLogger(__name__)


@dataclass
class ThemenPaket:
    """A compiled research package for one watchlist."""
    watchlist_name: str
    watchlist_keywords: str
    period_start: datetime
    period_end: datetime
    articles: list[dict] = field(default_factory=list)
    total_matches: int = 0
    new_matches: int = 0
    specialty_breakdown: dict = field(default_factory=dict)
    evidence_summary: dict = field(default_factory=dict)
    avg_score: float = 0.0
    top_score: float = 0.0
    highlight_de: str = ""


def _score_color(score: float) -> str:
    """Score-abhängige Farbe (grün/gelb/rot)."""
    if score >= SCORE_THRESHOLD_HIGH:
        return "#22c55e"
    elif score >= SCORE_THRESHOLD_MID:
        return "#eab308"
    return "#ef4444"


def _parse_score_breakdown(raw: str | None) -> dict:
    """Parse JSON score_breakdown, return empty dict on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_kern(summary_de: str | None) -> str:
    """Extract the KERN part from a structured summary_de string."""
    if not summary_de:
        return "Keine Zusammenfassung verfügbar."
    for part in summary_de.split(";;;"):
        part = part.strip()
        if part.upper().startswith("KERN:"):
            return part[5:].strip()
    # Fallback: return first part
    first = summary_de.split(";;;")[0].strip()
    return first if first else "Keine Zusammenfassung verfügbar."


def generate_paket(watchlist: Watchlist, days_back: int = 7) -> ThemenPaket | None:
    """Generate a research package for one watchlist."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days_back)
    period_end = now

    with get_session() as session:
        # Alle Matches für diese Watchlist im Zeitraum
        stmt = (
            select(WatchlistMatch, Article)
            .join(Article, WatchlistMatch.article_id == Article.id)
            .where(
                and_(
                    WatchlistMatch.watchlist_id == watchlist.id,
                    WatchlistMatch.matched_at >= period_start,
                )
            )
            .order_by(col(Article.relevance_score).desc())
        )
        results = session.exec(stmt).all()

        if not results:
            return None

        # Statistiken berechnen
        articles_data = []
        scores = []
        specialties: list[str] = []
        study_types: list[str] = []
        new_count = 0

        for match, article in results:
            score_bd = _parse_score_breakdown(article.score_breakdown)
            kern = _extract_kern(article.summary_de)

            articles_data.append({
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "journal": article.journal or "—",
                "pub_date": article.pub_date.strftime("%d.%m.%Y") if article.pub_date else "—",
                "specialty": article.specialty or "—",
                "study_type": article.study_type or "—",
                "relevance_score": article.relevance_score,
                "score_breakdown": score_bd,
                "summary_kern": kern,
                "summary_de": article.summary_de or "",
                "status": article.status,
                "matched_at": match.matched_at,
                "notified": match.notified,
            })

            scores.append(article.relevance_score)
            if article.specialty:
                specialties.append(article.specialty)
            if article.study_type:
                study_types.append(article.study_type)
            if not match.notified:
                new_count += 1

    specialty_breakdown = dict(Counter(specialties).most_common())
    evidence_summary = dict(Counter(study_types).most_common())

    avg_score = sum(scores) / len(scores) if scores else 0.0
    top_score = max(scores) if scores else 0.0

    # Highlight: Top-Artikel KERN als Einzeiler
    highlight_de = articles_data[0]["summary_kern"] if articles_data else ""

    return ThemenPaket(
        watchlist_name=watchlist.name,
        watchlist_keywords=watchlist.keywords,
        period_start=period_start,
        period_end=period_end,
        articles=articles_data,
        total_matches=len(articles_data),
        new_matches=new_count,
        specialty_breakdown=specialty_breakdown,
        evidence_summary=evidence_summary,
        avg_score=round(avg_score, 1),
        top_score=round(top_score, 1),
        highlight_de=highlight_de,
    )


def generate_all_pakete(days_back: int = 7) -> list[ThemenPaket]:
    """Generate packages for all active watchlists."""
    from src.processing.watchlist import get_active_watchlists

    watchlists = get_active_watchlists()
    if not watchlists:
        logger.info("Keine aktiven Watchlists für Themen-Pakete.")
        return []

    pakete = []
    for wl in watchlists:
        paket = generate_paket(wl, days_back=days_back)
        if paket is not None:
            pakete.append(paket)
            logger.info(
                "Themen-Paket '%s': %d Treffer (Ø %.1f, Top %.1f)",
                wl.name, paket.total_matches, paket.avg_score, paket.top_score,
            )
        else:
            logger.info("Watchlist '%s': keine Treffer im Zeitraum.", wl.name)

    return pakete


def _build_evidence_bar(evidence_summary: dict) -> str:
    """Build a mini evidence-type distribution bar (inline HTML)."""
    if not evidence_summary:
        return "<span style='color:#94a3b8;font-size:12px'>Keine Studientypen verfügbar</span>"

    total = sum(evidence_summary.values())
    colors = {
        "meta-analysis": "#7c3aed", "systematic review": "#7c3aed",
        "rct": "#2563eb", "randomized controlled trial": "#2563eb",
        "guideline": "#059669", "leitlinie": "#059669",
        "cohort study": "#0891b2", "cohort": "#0891b2",
        "case-control": "#d97706", "cross-sectional": "#ea580c",
        "editorial": "#6b7280", "case report": "#9ca3af",
        "news": "#d1d5db",
    }
    default_color = "#94a3b8"

    segments = ""
    for stype, count in evidence_summary.items():
        pct = (count / total) * 100
        color = default_color
        for key, col_val in colors.items():
            if key in stype.lower():
                color = col_val
                break
        segments += (
            f'<div style="width:{pct:.0f}%;background:{color};height:8px;'
            f'display:inline-block" title="{html_mod.escape(stype)}: {count}"></div>'
        )

    labels = " · ".join(
        f"<span style='font-size:11px;color:#64748b'>{html_mod.escape(k)}: {v}</span>"
        for k, v in list(evidence_summary.items())[:5]
    )

    return f"""
    <div style="width:100%;background:#1e293b;border-radius:4px;overflow:hidden;
                display:flex;height:8px;margin:4px 0">{segments}</div>
    <div>{labels}</div>
    """


def _build_score_breakdown_tooltip(breakdown: dict) -> str:
    """Build a score breakdown string for tooltip display."""
    if not breakdown:
        return ""
    parts = []
    for key, val in breakdown.items():
        try:
            parts.append(f"{key}: {float(val):.0f}")
        except (ValueError, TypeError):
            parts.append(f"{key}: {val}")
    return " | ".join(parts)


def _build_paket_html(paket: ThemenPaket) -> str:
    """Build beautiful HTML email for one Themen-Paket."""
    period_str = (
        f"{paket.period_start.strftime('%d.%m.%Y')} — "
        f"{paket.period_end.strftime('%d.%m.%Y')}"
    )

    # Top-Fachgebiet ermitteln
    top_specialty = "—"
    if paket.specialty_breakdown:
        top_specialty = next(iter(paket.specialty_breakdown))

    # Stats-Bar
    stats_html = f"""
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin:16px 0;padding:12px 16px;
                background:#0f172a;border-radius:8px;border:1px solid #334155">
        <div style="text-align:center;flex:1;min-width:80px">
            <div style="font-size:24px;font-weight:700;color:#22c55e">{paket.new_matches}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Neue Treffer</div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px">
            <div style="font-size:24px;font-weight:700;color:#eab308">{paket.total_matches}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Gesamt</div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px">
            <div style="font-size:24px;font-weight:700;color:#60a5fa">{paket.avg_score}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">&Oslash; Score</div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px">
            <div style="font-size:24px;font-weight:700;color:#c084fc">{paket.top_score}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Top Score</div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px">
            <div style="font-size:16px;font-weight:600;color:#f0abfc;margin-top:4px">
                {html_mod.escape(top_specialty)}
            </div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase">Top-Fach</div>
        </div>
    </div>
    """

    # Evidence-Breakdown
    evidence_bar = _build_evidence_bar(paket.evidence_summary)
    evidence_html = f"""
    <div style="margin:12px 0;padding:10px 16px;background:#0f172a;border-radius:8px;
                border:1px solid #334155">
        <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px">
            Evidenz-Verteilung
        </div>
        {evidence_bar}
    </div>
    """

    # Artikel-Liste (Top 10)
    article_rows = ""
    for i, art in enumerate(paket.articles[:10], 1):
        score = art["relevance_score"]
        color = _score_color(score)
        tooltip = _build_score_breakdown_tooltip(art["score_breakdown"])
        alert_icon = "&#x1F6A8; " if art["status"] == "ALERT" else ""

        # Summary: nur KERN
        kern = html_mod.escape(art["summary_kern"])

        article_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:14px 10px;text-align:center;vertical-align:top;width:60px">
                <span title="{html_mod.escape(tooltip)}"
                      style="background:{color};color:#fff;padding:4px 12px;
                             border-radius:12px;font-weight:700;font-size:14px;
                             display:inline-block;cursor:help">
                    {score:.0f}
                </span>
            </td>
            <td style="padding:14px 10px;vertical-align:top">
                <div>
                    <a href="{html_mod.escape(art['url'], quote=True)}"
                       style="color:#60a5fa;text-decoration:none;font-weight:600;font-size:15px">
                        {alert_icon}{html_mod.escape(art['title'])}
                    </a>
                </div>
                <div style="color:#94a3b8;font-size:12px;margin:4px 0">
                    &#x1F4F0; {html_mod.escape(art['journal'])}
                    &middot; &#x1F4C5; {art['pub_date']}
                    &middot; &#x1F3F7;&#xFE0F; {html_mod.escape(art['specialty'])}
                    &middot; &#x1F9EA; {html_mod.escape(art['study_type'])}
                </div>
                <div style="margin-top:6px;color:#cbd5e1;font-size:13px;line-height:1.5">
                    {kern}
                </div>
            </td>
        </tr>
        """

    # Highlight-Zeile
    highlight_html = ""
    if paket.highlight_de:
        highlight_html = f"""
        <div style="margin:16px 0;padding:12px 16px;background:#1e3a5f;border-left:4px solid #60a5fa;
                    border-radius:0 8px 8px 0;color:#e2e8f0;font-size:14px;line-height:1.5">
            <strong>&#x1F4A1; Highlight:</strong> {html_mod.escape(paket.highlight_de)}
        </div>
        """

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    kw = date.today().isocalendar()[1]

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                 max-width:750px;margin:0 auto;padding:20px;
                 background:#0b1120;color:#e2e8f0">
        <!-- Header -->
        <div style="text-align:center;padding:24px 0;border-bottom:2px solid #2563eb">
            <h1 style="margin:0;color:#60a5fa;font-size:24px">
                &#x1F4E6; Lumio Themen-Paket
            </h1>
            <h2 style="margin:8px 0 0;color:#e2e8f0;font-size:20px">
                {html_mod.escape(paket.watchlist_name)}
            </h2>
            <p style="color:#94a3b8;margin:6px 0 0;font-size:13px">
                KW {kw} &middot; {period_str}
                &middot; Keywords: <em>{html_mod.escape(paket.watchlist_keywords)}</em>
            </p>
        </div>

        {stats_html}
        {highlight_html}
        {evidence_html}

        <!-- Artikel-Tabelle -->
        <div style="margin-top:16px">
            <div style="font-size:14px;color:#94a3b8;text-transform:uppercase;
                        margin-bottom:8px;font-weight:600">
                Top-Artikel ({min(len(paket.articles), 10)} von {paket.total_matches})
            </div>
            <table style="width:100%;border-collapse:collapse;background:#0f172a;
                          border-radius:8px;overflow:hidden">
                {article_rows}
            </table>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:20px 0;margin-top:24px;
                    border-top:1px solid #1e293b;color:#64748b;font-size:11px">
            Generiert von Lumio am {now_str}<br>
            Automatisiertes Recherche-Paket &middot; Alle Inhalte redaktionell pr&uuml;fen
        </div>
    </body>
    </html>
    """


def send_paket_email(paket: ThemenPaket, to_email: str) -> bool:
    """Send a Themen-Paket via email."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, to_email]):
        logger.error(
            "SMTP nicht konfiguriert. SMTP_HOST, SMTP_USER, SMTP_PASS setzen."
        )
        return False

    html_body = _build_paket_html(paket)
    kw = date.today().isocalendar()[1]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"\U0001f4e6 Lumio Themen-Paket: {paket.watchlist_name} — KW {kw}"
    )
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(
            "Themen-Paket '%s' gesendet an %s (%d Treffer)",
            paket.watchlist_name, to_email, paket.total_matches,
        )
        return True
    except Exception as exc:
        logger.error("Fehler beim Senden des Themen-Pakets: %s", exc)
        return False


def send_all_pakete(to_email: str | None = None, days_back: int = 7) -> int:
    """Generate and send all packages. Returns count of sent emails."""
    if not to_email:
        to_email = os.getenv("ALERT_EMAIL", os.getenv("SMTP_USER", ""))

    if not to_email:
        logger.error("Keine Empfänger-Adresse für Themen-Pakete.")
        return 0

    pakete = generate_all_pakete(days_back=days_back)
    if not pakete:
        logger.info("Keine Themen-Pakete zu versenden.")
        return 0

    sent = 0
    for paket in pakete:
        if send_paket_email(paket, to_email):
            sent += 1

    logger.info("%d von %d Themen-Paketen versendet.", sent, len(pakete))
    return sent


def save_paket_html(paket: ThemenPaket, output_dir: str = "db/pakete") -> str:
    """Save paket as local HTML file for preview. Returns file path."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Dateiname: watchlist_name (bereinigt) + Datum
    safe_name = "".join(
        c if c.isalnum() or c in ("-", "_") else "_"
        for c in paket.watchlist_name
    )
    date_str = date.today().strftime("%Y-%m-%d")
    filename = f"{safe_name}_{date_str}.html"
    filepath = out_path / filename

    html_body = _build_paket_html(paket)
    filepath.write_text(html_body, encoding="utf-8")
    logger.info("Themen-Paket gespeichert: %s", filepath)
    return str(filepath)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        pakete = generate_all_pakete()
        for p in pakete:
            path = save_paket_html(p)
            print(f"Paket gespeichert: {path}")
        if not pakete:
            print("Keine Pakete generiert (keine aktiven Watchlists oder Treffer).")
    elif len(sys.argv) > 1:
        count = send_all_pakete(to_email=sys.argv[1])
        print(f"{count} Pakete versendet.")
    else:
        print("Usage:")
        print("  python -m src.themen_paket --preview           # Save HTML previews")
        print("  python -m src.themen_paket user@example.com    # Send all pakete")

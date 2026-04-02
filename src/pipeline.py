"""Lumio pipeline — orchestrates ingestion, dedup, scoring, classification."""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

import httpx
from sqlmodel import select

from src.config import FEED_REGISTRY
from src.models import Article, Source, get_engine, get_session, derive_source_category
from src.ingestion.europe_pmc import fetch_europe_pmc
from src.ingestion.rss_feeds import fetch_rss_feeds
from src.ingestion.google_news import fetch_google_news
from src.ingestion.medrxiv import fetch_medrxiv, fetch_biorxiv
from src.ingestion.who import fetch_who_don
from src.ingestion.bfarm import fetch_bfarm
from src.ingestion.ema import fetch_ema
from src.ingestion.cochrane import fetch_cochrane
from src.ingestion.awmf import fetch_awmf
from src.ingestion.rki import fetch_rki
from src.ingestion.abstract_fetcher import fetch_abstracts
from src.ingestion.generic_rss import fetch_generic_rss
from src.ingestion.fachgesellschaften import fetch_fachgesellschaften
from src.processing.dedup import deduplicate
from src.processing.scorer import score_articles
from src.processing.classifier import classify_articles
from src.processing.prefilter import prefilter_articles
from src.processing.summarizer import summarize_articles, highlight_articles
from src.processing.watchlist import run_watchlist_matching

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _is_feed_active(name: str) -> bool:
    """Check if a feed is active in the registry."""
    entry = FEED_REGISTRY.get(name)
    return entry.active if entry else True


async def ingest_all(days_back: int = 1) -> list[Article]:
    """Run all ingestion sources concurrently.

    Respects active/inactive flags from FEED_REGISTRY.
    Assigns source_category to articles from non-RSS modules.
    """
    # Build task list dynamically based on active feeds
    tasks = []
    source_names = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Lumio/1.0 (medical evidence dashboard)"},
        follow_redirects=True,
    ) as client:
        # Always-on sources (RSS feeds handle their own active check internally)
        tasks.append(fetch_europe_pmc(client, days_back=days_back))
        source_names.append("Europe PMC")
        tasks.append(fetch_rss_feeds(client))
        source_names.append("RSS Feeds")
        tasks.append(fetch_google_news(client))
        source_names.append("Google News")
        tasks.append(fetch_medrxiv(client, days_back=days_back))
        source_names.append("medRxiv")

        if _is_feed_active("bioRxiv"):
            tasks.append(fetch_biorxiv(client, days_back=days_back))
            source_names.append("bioRxiv")
        else:
            logger.info("bioRxiv: skipped (inactive)")

        tasks.append(fetch_who_don(client))
        source_names.append("WHO DON")
        tasks.append(fetch_bfarm(client))
        source_names.append("BfArM")
        tasks.append(fetch_ema(client))
        source_names.append("EMA")
        tasks.append(fetch_cochrane(client))
        source_names.append("Cochrane")
        tasks.append(fetch_awmf(client))
        source_names.append("AWMF")
        tasks.append(fetch_rki(client))
        source_names.append("RKI")

        # Generic RSS: new sources from FEED_REGISTRY (G-BA, IQWiG, KBV, etc.)
        tasks.append(fetch_generic_rss(client))
        source_names.append("Generic RSS")

        # Fachgesellschaften: DGIM, DGK, DEGAM (HTML scraping)
        tasks.append(fetch_fachgesellschaften(client))
        source_names.append("Fachgesellschaften")

        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Track feed health
    from src.processing.feed_monitor import update_feed_status

    articles: list[Article] = []
    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            logger.error("Source %s failed: %s", name, result)
            update_feed_status(name, success=False, error=str(result))
        else:
            # Backfill source_category for articles from non-RSS modules
            for article in result:
                if not article.source_category:
                    article.source_category = derive_source_category(article.source or name)
            articles.extend(result)
            if len(result) == 0:
                logger.warning("Source %s returned 0 articles — may need investigation", name)
            else:
                logger.info("Source %s: %d articles", name, len(result))
            update_feed_status(name, success=True, article_count=len(result))

    logger.info("Total ingested: %d articles", len(articles))
    return articles


def store_articles(articles: list[Article]) -> int:
    """Store articles in the database, skipping existing URLs/DOIs."""
    get_engine()  # ensure tables exist
    stored = 0

    with get_session() as session:
        # Bulk-fetch existing URLs and DOIs to avoid N+1 queries
        existing_urls = set(session.exec(select(Article.url)).all())
        existing_dois = set(
            d for d in session.exec(select(Article.doi).where(Article.doi.isnot(None))).all()  # type: ignore[union-attr]
        )

        for article in articles:
            is_duplicate = False

            if article.url in existing_urls:
                is_duplicate = True
            elif article.doi and article.doi in existing_dois:
                is_duplicate = True

            if is_duplicate:
                # Upsert: backfill summary if the existing record lacks one
                if article.summary_de:
                    existing = session.exec(
                        select(Article).where(Article.url == article.url)
                    ).first()
                    if existing and existing.summary_de is None:
                        existing.summary_de = article.summary_de
                        if article.highlight_tags:
                            existing.highlight_tags = article.highlight_tags
                        if article.score_breakdown:
                            existing.score_breakdown = article.score_breakdown
                        logger.debug("Backfilled summary for existing article: %s", article.url)
                continue

            session.add(article)
            existing_urls.add(article.url)
            if article.doi:
                existing_dois.add(article.doi)
            stored += 1

        session.commit()

    # Rebuild FTS5 index to include new articles
    if stored > 0:
        from src.models import populate_fts5
        populate_fts5()

    logger.info("Stored %d new articles (skipped %d existing)",
                stored, len(articles) - stored)
    return stored


def update_source_timestamps():
    """Update last_fetched for all active sources."""
    get_engine()
    now = datetime.now(timezone.utc)

    with get_session() as session:
        sources = session.exec(select(Source).where(Source.active == True)).all()
        for source in sources:
            source.last_fetched = now
        session.commit()


def _send_pipeline_alert(subject: str, body: str):
    """Best-effort alert email on pipeline issues."""
    try:
        from src.digest import send_pipeline_alert
        send_pipeline_alert(subject, body)
    except Exception as exc:
        logger.warning("Could not send pipeline alert: %s", exc)


async def run_pipeline(days_back: int = 1) -> dict:
    """Execute the full Lumio pipeline."""
    stats = {}
    start = datetime.now(timezone.utc)

    # 1. Ingest
    logger.info("=" * 60)
    logger.info("STEP 1: Ingestion (days_back=%d)", days_back)
    logger.info("=" * 60)
    raw_articles = await ingest_all(days_back=days_back)
    stats["ingested"] = len(raw_articles)

    if not raw_articles:
        logger.warning("No articles ingested — pipeline complete.")
        _send_pipeline_alert(
            "Keine Artikel ingested",
            "Die Pipeline hat 0 Artikel aus allen Quellen erhalten. "
            "Bitte Quellen-APIs und Netzwerk prüfen.",
        )
        return stats

    # 1b. Fetch missing abstracts (e.g. Google News articles)
    missing_before = sum(1 for a in raw_articles if not a.abstract)
    if missing_before:
        logger.info("=" * 60)
        logger.info("STEP 1b: Fetch missing abstracts (%d articles)", missing_before)
        logger.info("=" * 60)
        raw_articles = await fetch_abstracts(raw_articles)
        missing_after = sum(1 for a in raw_articles if not a.abstract)
        stats["abstracts_fetched"] = missing_before - missing_after
        logger.info("Abstracts fetched: %d / %d", stats["abstracts_fetched"], missing_before)

    # 2. Deduplicate
    logger.info("=" * 60)
    logger.info("STEP 2: Deduplication")
    logger.info("=" * 60)
    unique_articles = deduplicate(raw_articles)
    stats["after_dedup"] = len(unique_articles)

    # 2b. Pre-filter (LLM-based, removes irrelevant articles)
    logger.info("=" * 60)
    logger.info("STEP 2b: Pre-filter")
    logger.info("=" * 60)
    filtered_articles = prefilter_articles(unique_articles)
    stats["after_prefilter"] = len(filtered_articles)

    # 3. Score
    logger.info("=" * 60)
    logger.info("STEP 3: Scoring")
    logger.info("=" * 60)
    scored_articles = score_articles(filtered_articles)

    # 3b. Quality Gate — discard low-score articles, enforce daily cap
    from src.config import SCORE_MIN_KEEP, DAILY_MAX_ARTICLES
    before_gate = len(scored_articles)
    scored_articles = [a for a in scored_articles if a.relevance_score >= SCORE_MIN_KEEP]
    scored_articles.sort(key=lambda a: a.relevance_score, reverse=True)
    if len(scored_articles) > DAILY_MAX_ARTICLES:
        alerts = [a for a in scored_articles if getattr(a, "status", None) == "ALERT"]
        scored_articles = scored_articles[:DAILY_MAX_ARTICLES]
        # Re-add any safety alerts that were cut by the cap
        alert_ids = {id(a) for a in scored_articles}
        for a in alerts:
            if id(a) not in alert_ids:
                scored_articles.append(a)
    stats["dropped_low_score"] = before_gate - len(scored_articles)
    logger.info(
        "Quality Gate: %d → %d articles (dropped %d below score %d, cap %d)",
        before_gate, len(scored_articles), stats["dropped_low_score"],
        SCORE_MIN_KEEP, DAILY_MAX_ARTICLES,
    )

    # 4. Classify
    logger.info("=" * 60)
    logger.info("STEP 4: Classification")
    logger.info("=" * 60)
    classified_articles = classify_articles(scored_articles)

    # 5. Summarize (template-based)
    logger.info("=" * 60)
    logger.info("STEP 5: Summarization")
    logger.info("=" * 60)
    summarized_articles = summarize_articles(classified_articles)

    # 5b. Highlight tags
    logger.info("Generating highlight tags...")
    summarized_articles = highlight_articles(summarized_articles)

    # Capture top 5 preview before storing (avoids detached session issue)
    top5_preview = [
        (a.relevance_score, a.specialty or "?", a.title[:80])
        for a in summarized_articles[:5]
    ]

    # 6. Store
    logger.info("=" * 60)
    logger.info("STEP 6: Storage")
    logger.info("=" * 60)
    stored = store_articles(summarized_articles)
    stats["stored"] = stored

    # 7. Watchlist matching
    logger.info("=" * 60)
    logger.info("STEP 7: Watchlist Matching")
    logger.info("=" * 60)
    run_watchlist_matching(article_count=len(summarized_articles))

    # 7b. Trend-Berechnung (pre-compute für UI)
    logger.info("=" * 60)
    logger.info("STEP 7b: Trend-Berechnung (TrendCache)")
    logger.info("=" * 60)
    try:
        from src.processing.trends import compute_trends, store_trends_cache
        trends, weekly_overview = compute_trends(
            days=7, min_cluster_size=3, use_embeddings=False, max_clusters=8,
        )
        store_trends_cache(trends, weekly_overview)
        stats["trend_clusters"] = len(trends)
        logger.info("Trends: %d Cluster berechnet und gecacht", len(trends))
    except Exception as exc:
        logger.error("Trend-Berechnung fehlgeschlagen: %s", exc)
        stats["trend_clusters"] = 0

    # 7c. GA4 Signals (Nachfrage-Daten aktualisieren)
    logger.info("=" * 60)
    logger.info("STEP 7c: GA4 Signals")
    logger.info("=" * 60)
    try:
        from src.processing.ga4_signals import refresh_ga4_signals
        ga4_stats = refresh_ga4_signals(days=7)
        stats["ga4_status"] = ga4_stats.get("status", "unknown")
        if ga4_stats.get("status") == "ok":
            logger.info(
                "GA4: %d Null-Suchen, %d Top-Suchen, %d Bounce-Signale",
                ga4_stats.get("null_searches", 0),
                ga4_stats.get("top_searches", 0),
                ga4_stats.get("bounce_signals", 0),
            )
        else:
            logger.info("GA4: %s", ga4_stats.get("status", "nicht verfügbar"))
    except Exception as exc:
        logger.warning("GA4 Signals fehlgeschlagen: %s", exc)
        stats["ga4_status"] = "error"

    # 8. Themen-Pakete (optional, wöchentlich)
    send_pakete = os.getenv("LUMIO_SEND_PAKETE", "").lower() in ("true", "1", "yes")
    try:
        pakete_day = int(os.getenv("LUMIO_PAKETE_DAY", "0"))
    except ValueError:
        pakete_day = 0  # Montag als Fallback
    today_weekday = datetime.now(timezone.utc).weekday()

    if send_pakete and today_weekday == pakete_day:
        logger.info("=" * 60)
        logger.info("STEP 8: Themen-Pakete versenden (Wochentag %d)", today_weekday)
        logger.info("=" * 60)
        try:
            from src.themen_paket import send_all_pakete
            sent_count = send_all_pakete()
            stats["pakete_sent"] = sent_count
            logger.info("Themen-Pakete: %d versendet", sent_count)
        except Exception as exc:
            logger.error("Themen-Pakete fehlgeschlagen: %s", exc)
            stats["pakete_sent"] = 0
    elif send_pakete:
        logger.info("Themen-Pakete: übersprungen (heute ist Wochentag %d, konfiguriert: %s)",
                     today_weekday, pakete_day)

    # Summary
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    stats["elapsed_seconds"] = round(elapsed, 1)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Ingested:     %d", stats["ingested"])
    logger.info("  Abstracts:    %d fetched", stats.get("abstracts_fetched", 0))
    logger.info("  After dedup:  %d", stats["after_dedup"])
    logger.info("  After filter: %d", stats.get("after_prefilter", stats["after_dedup"]))
    logger.info("  Stored (new): %d", stats["stored"])
    logger.info("  Duration:     %.1fs", stats["elapsed_seconds"])
    logger.info("=" * 60)

    if top5_preview:
        logger.info("TOP 5 ARTICLES:")
        for i, (score, spec, title) in enumerate(top5_preview, 1):
            logger.info("  %d. [%.1f] %s — %s", i, score, spec, title)

    return stats


def main():
    from src.config import PIPELINE_DAYS_BACK
    try:
        days_back = int(sys.argv[1]) if len(sys.argv) > 1 else PIPELINE_DAYS_BACK
    except ValueError:
        days_back = PIPELINE_DAYS_BACK
    days_back = max(1, min(days_back, 30))
    try:
        asyncio.run(run_pipeline(days_back=days_back))
    except Exception as exc:
        logger.exception("Pipeline crashed: %s", exc)
        _send_pipeline_alert(
            "Pipeline abgestürzt",
            f"Die Lumio-Pipeline ist mit einem Fehler abgestürzt:\n\n{exc}\n\n"
            "Bitte Server-Logs prüfen.",
        )
        raise


if __name__ == "__main__":
    main()

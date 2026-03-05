"""MedIntel pipeline — orchestrates ingestion, dedup, scoring, classification."""

import asyncio
import logging
import sys
from datetime import datetime

import httpx
from sqlmodel import select

from src.models import Article, Source, get_engine, get_session
from src.ingestion.europe_pmc import fetch_europe_pmc
from src.ingestion.rss_feeds import fetch_rss_feeds
from src.ingestion.google_news import fetch_google_news
from src.ingestion.medrxiv import fetch_medrxiv, fetch_biorxiv
from src.ingestion.who import fetch_who_don
from src.processing.dedup import deduplicate
from src.processing.scorer import score_articles
from src.processing.classifier import classify_articles
from src.processing.summarizer import summarize_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def ingest_all(days_back: int = 1) -> list[Article]:
    """Run all ingestion sources concurrently."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "MedIntel/1.0 (esanum medical intelligence)"},
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            fetch_europe_pmc(client, days_back=days_back),
            fetch_rss_feeds(client),
            fetch_google_news(client),
            fetch_medrxiv(client, days_back=days_back),
            fetch_biorxiv(client, days_back=days_back),
            fetch_who_don(client),
            return_exceptions=True,
        )

    articles: list[Article] = []
    source_names = [
        "Europe PMC", "RSS Feeds", "Google News",
        "medRxiv", "bioRxiv", "WHO DON",
    ]

    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            logger.error("Source %s failed: %s", name, result)
        else:
            articles.extend(result)
            logger.info("Source %s: %d articles", name, len(result))

    logger.info("Total ingested: %d articles", len(articles))
    return articles


def store_articles(articles: list[Article]) -> int:
    """Store articles in the database, skipping existing URLs/DOIs."""
    get_engine()  # ensure tables exist
    stored = 0

    with get_session() as session:
        for article in articles:
            # Skip if URL already exists
            existing = session.exec(
                select(Article).where(Article.url == article.url)
            ).first()
            if existing:
                continue

            # Skip if DOI already exists
            if article.doi:
                existing = session.exec(
                    select(Article).where(Article.doi == article.doi)
                ).first()
                if existing:
                    continue

            session.add(article)
            stored += 1

        session.commit()

    logger.info("Stored %d new articles (skipped %d existing)",
                stored, len(articles) - stored)
    return stored


def update_source_timestamps():
    """Update last_fetched for all active sources."""
    get_engine()
    now = datetime.utcnow()

    with get_session() as session:
        sources = session.exec(select(Source).where(Source.active == True)).all()
        for source in sources:
            source.last_fetched = now
        session.commit()


async def run_pipeline(days_back: int = 1) -> dict:
    """Execute the full MedIntel pipeline."""
    stats = {}
    start = datetime.utcnow()

    # 1. Ingest
    logger.info("=" * 60)
    logger.info("STEP 1: Ingestion (days_back=%d)", days_back)
    logger.info("=" * 60)
    raw_articles = await ingest_all(days_back=days_back)
    stats["ingested"] = len(raw_articles)

    if not raw_articles:
        logger.warning("No articles ingested — pipeline complete.")
        return stats

    # 2. Deduplicate
    logger.info("=" * 60)
    logger.info("STEP 2: Deduplication")
    logger.info("=" * 60)
    unique_articles = deduplicate(raw_articles)
    stats["after_dedup"] = len(unique_articles)

    # 3. Score
    logger.info("=" * 60)
    logger.info("STEP 3: Scoring")
    logger.info("=" * 60)
    scored_articles = score_articles(unique_articles)

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

    # Summary
    elapsed = (datetime.utcnow() - start).total_seconds()
    stats["elapsed_seconds"] = round(elapsed, 1)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Ingested:     %d", stats["ingested"])
    logger.info("  After dedup:  %d", stats["after_dedup"])
    logger.info("  Stored (new): %d", stats["stored"])
    logger.info("  Duration:     %.1fs", stats["elapsed_seconds"])
    logger.info("=" * 60)

    if top5_preview:
        logger.info("TOP 5 ARTICLES:")
        for i, (score, spec, title) in enumerate(top5_preview, 1):
            logger.info("  %d. [%.1f] %s — %s", i, score, spec, title)

    return stats


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    asyncio.run(run_pipeline(days_back=days_back))


if __name__ == "__main__":
    main()

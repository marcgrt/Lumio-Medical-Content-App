"""Re-summarize articles that only have template summaries.

Finds articles where the LLM summary failed (short KERN-only templates)
and re-generates them using the current LLM provider chain.

Usage:
    python -m src.resummarize                    # dry-run: show what would be updated
    python -m src.resummarize --run               # actually re-summarize
    python -m src.resummarize --run --days 14     # last 14 days (default: 7)
    python -m src.resummarize --run --limit 50    # max 50 articles per run
"""

import argparse
import logging
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from src.models import Article, get_engine, get_session
from src.processing.summarizer import generate_llm_summary, generate_highlight_tags

logger = logging.getLogger(__name__)


def find_template_summaries(days: int = 7, limit: int = 200) -> list[Article]:
    """Find articles with poor template-only summaries."""
    from sqlmodel import select, col
    from datetime import datetime, timedelta

    get_engine()
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        # Template summaries are short and lack PRAXIS/EINORDNUNG sections
        stmt = (
            select(Article)
            .where(
                Article.created_at >= cutoff,
                Article.summary_de.isnot(None),
            )
            .order_by(Article.relevance_score.desc())
            .limit(limit * 3)  # fetch extra, filter in Python
        )
        articles = session.exec(stmt).all()

    # Filter: keep only articles with poor summaries
    poor = []
    for a in articles:
        s = a.summary_de or ""
        is_template = (
            # No PRAXIS section (real LLM summaries have it)
            "PRAXIS:" not in s
            # Or very short KERN (< 80 chars = likely truncated or title-echo)
            or (s.startswith("KERN:") and len(s.split(";;;")[0]) < 80)
        )
        if is_template:
            poor.append(a)
            if len(poor) >= limit:
                break

    return poor


def resummarize(articles: list[Article], dry_run: bool = True) -> dict:
    """Re-generate summaries for the given articles.

    Returns stats: {total, success, failed, skipped}.
    """
    stats = {"total": len(articles), "success": 0, "failed": 0, "skipped": 0}

    if dry_run:
        for a in articles:
            old = (a.summary_de or "")[:80]
            print(f"  [{a.relevance_score:.0f}] {a.title[:70]}...")
            print(f"         OLD: {old}")
        return stats

    get_engine()

    for i, article in enumerate(articles):
        # Skip if no abstract (template will be the same)
        if not article.abstract or len(article.abstract.strip()) < 30:
            stats["skipped"] += 1
            continue

        logger.info(
            "[%d/%d] Re-summarizing: %s (score %.0f)",
            i + 1, len(articles), article.title[:60], article.relevance_score,
        )

        new_summary = generate_llm_summary(article)

        if new_summary and "PRAXIS:" in new_summary:
            # Update in DB
            with get_session() as session:
                db_article = session.get(Article, article.id)
                if db_article:
                    db_article.summary_de = new_summary
                    # Also regenerate highlight tags
                    db_article.highlight_tags = generate_highlight_tags(db_article)
                    session.commit()
            stats["success"] += 1
            logger.info("  OK (%d chars)", len(new_summary))
        else:
            stats["failed"] += 1
            logger.warning("  FAILED — LLM returned empty or invalid")

        # Small delay to respect rate limits
        time.sleep(0.3)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Re-summarize template summaries")
    parser.add_argument("--run", action="store_true", help="Actually update (default: dry-run)")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")
    parser.add_argument("--limit", type=int, default=200, help="Max articles to process (default: 200)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"Scanning last {args.days} days for template summaries (limit {args.limit})...")
    articles = find_template_summaries(days=args.days, limit=args.limit)
    print(f"Found {len(articles)} articles with poor summaries.\n")

    if not articles:
        print("Nothing to do.")
        return

    if not args.run:
        print("DRY RUN — showing what would be updated:\n")
        resummarize(articles, dry_run=True)
        print(f"\nRun with --run to actually update these {len(articles)} articles.")
        return

    print(f"Re-summarizing {len(articles)} articles...\n")
    stats = resummarize(articles, dry_run=False)
    print(f"\nDone: {stats['success']} updated, {stats['failed']} failed, {stats['skipped']} skipped.")

    if stats["failed"] > stats["success"]:
        print("\nWARNING: More failures than successes — check LLM provider limits!")
        sys.exit(1)


if __name__ == "__main__":
    main()

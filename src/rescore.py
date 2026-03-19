"""Re-score existing articles using the LLM scorer.

Usage:
    # Re-score all articles (LLM with rule-based fallback):
    python -m src.rescore

    # Re-score only top 50 by current score:
    python -m src.rescore --limit 50

    # Dry-run: show what would change without saving:
    python -m src.rescore --dry-run

    # Force rule-based only (recalculate without LLM):
    python -m src.rescore --rule-based
"""

import argparse
import json
import logging
import sys
import time

from sqlmodel import select, col

from src.models import Article, get_engine, get_session
from src.processing.scorer import (
    compute_relevance_score,
    llm_score_article,
    _feedback_cache,
    _feedback_loaded,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def rescore_articles(
    limit: int = 0,
    dry_run: bool = False,
    rule_based_only: bool = False,
) -> dict:
    """Re-score articles in the database.

    Returns stats dict with counts and score change info.
    """
    import src.processing.scorer as scorer_mod
    from src.config import get_provider_chain

    get_engine()

    # Reset feedback cache
    scorer_mod._feedback_cache = None
    scorer_mod._feedback_loaded = False

    use_llm = not rule_based_only and bool(get_provider_chain("scoring"))

    if use_llm:
        providers = get_provider_chain("scoring")
        logger.info("LLM scoring enabled: %s", [p.name for p in providers])
    else:
        logger.info("Rule-based scoring only")

    # Fetch articles — prioritize those not yet LLM-scored
    with get_session() as session:
        # First: articles without LLM scores (score_breakdown missing "llm")
        stmt = (
            select(Article)
            .where(
                ~col(Article.score_breakdown).contains('"scorer": "llm"')
                | (Article.score_breakdown == None)  # noqa: E711
            )
            .order_by(col(Article.relevance_score).desc())
        )
        if limit > 0:
            stmt = stmt.limit(limit)
        articles = list(session.exec(stmt).all())

        # If no unscored left and no limit, rescore everything
        if not articles and limit == 0:
            stmt = select(Article).order_by(col(Article.relevance_score).desc())
            articles = list(session.exec(stmt).all())

    logger.info("Re-scoring %d articles...", len(articles))

    stats = {
        "total": len(articles),
        "llm_scored": 0,
        "rule_scored": 0,
        "changed": 0,
        "score_diffs": [],
    }

    updated_articles = []

    for i, article in enumerate(articles):
        old_score = article.relevance_score
        old_bd = article.score_breakdown

        # Try LLM scoring
        llm_result = None
        if use_llm:
            # Rate-limit: Gemini 2.0 Flash free tier = 15 req/min, 1500/day
            if i > 0 and stats["llm_scored"] > 0:
                time.sleep(4)
            llm_result = llm_score_article(article)

        if llm_result is not None:
            score, breakdown = llm_result
            rb_score, _ = compute_relevance_score(article)
            breakdown["rule_based_score"] = rb_score
            new_score = score
            new_bd = json.dumps(breakdown)
            stats["llm_scored"] += 1
        else:
            score, breakdown = compute_relevance_score(article)
            new_score = score
            new_bd = json.dumps(breakdown)
            stats["rule_scored"] += 1

        diff = round(new_score - old_score, 1)
        if abs(diff) > 0.1:
            stats["changed"] += 1
            stats["score_diffs"].append(diff)

        # Progress logging (every article when LLM, every 10 for rule-based)
        scorer_type = "LLM" if llm_result else "RB"
        if use_llm or (i + 1) % 10 == 0 or i == 0:
            logger.info(
                "  [%d/%d] %s: %.1f → %.1f (%+.1f) — %s",
                i + 1, len(articles), scorer_type,
                old_score, new_score, diff,
                (article.title or "")[:50],
            )

        updated_articles.append((article.id, new_score, new_bd))

    # Save to DB
    if not dry_run and updated_articles:
        with get_session() as session:
            for art_id, new_score, new_bd in updated_articles:
                art = session.get(Article, art_id)
                if art:
                    art.relevance_score = new_score
                    art.score_breakdown = new_bd
            session.commit()
        logger.info("✅ Saved %d articles to database", len(updated_articles))
    elif dry_run:
        logger.info("🔍 Dry-run — no changes saved")

    # Summary
    if stats["score_diffs"]:
        diffs = stats["score_diffs"]
        avg_diff = sum(diffs) / len(diffs)
        logger.info("=" * 50)
        logger.info("RE-SCORE SUMMARY:")
        logger.info("  Total:       %d", stats["total"])
        logger.info("  LLM-scored:  %d", stats["llm_scored"])
        logger.info("  Rule-scored: %d", stats["rule_scored"])
        logger.info("  Changed:     %d (%.0f%%)", stats["changed"],
                     stats["changed"] / stats["total"] * 100 if stats["total"] else 0)
        logger.info("  Avg Δ:       %+.1f", avg_diff)
        logger.info("  Max up:      %+.1f", max(diffs))
        logger.info("  Max down:    %+.1f", min(diffs))
    else:
        logger.info("No score changes detected.")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Re-score Lumio articles")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max articles to re-score (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without saving")
    parser.add_argument("--rule-based", action="store_true",
                        help="Force rule-based scoring (no LLM)")
    args = parser.parse_args()

    rescore_articles(
        limit=args.limit,
        dry_run=args.dry_run,
        rule_based_only=args.rule_based,
    )


if __name__ == "__main__":
    main()

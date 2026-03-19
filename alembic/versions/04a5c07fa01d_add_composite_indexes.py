"""add_composite_indexes

Revision ID: 04a5c07fa01d
Revises: 
Create Date: 2026-03-18 20:37:05.557190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04a5c07fa01d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for common query patterns."""
    # Article table — single-column indexes for unindexed filter columns
    op.create_index("ix_article_source", "article", ["source"])
    op.create_index("ix_article_language", "article", ["language"])

    # Article table — composite indexes for frequent multi-column queries
    op.create_index("ix_article_status_pub_date", "article", ["status", "pub_date"])
    op.create_index("ix_article_status_ack", "article", ["status", "alert_acknowledged_at"])
    op.create_index("ix_article_pub_date_score", "article", ["pub_date", "relevance_score"])
    op.create_index("ix_article_specialty_pub_date", "article", ["specialty", "pub_date"])

    # WatchlistMatch — composite index for watchlist queries with date ordering
    op.create_index("ix_wm_wl_matched", "watchlistmatch", ["watchlist_id", "matched_at"])


def downgrade() -> None:
    """Remove composite indexes."""
    op.drop_index("ix_wm_wl_matched", table_name="watchlistmatch")
    op.drop_index("ix_article_specialty_pub_date", table_name="article")
    op.drop_index("ix_article_pub_date_score", table_name="article")
    op.drop_index("ix_article_status_ack", table_name="article")
    op.drop_index("ix_article_status_pub_date", table_name="article")
    op.drop_index("ix_article_language", table_name="article")
    op.drop_index("ix_article_source", table_name="article")

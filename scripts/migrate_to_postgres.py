#!/usr/bin/env python3
"""Migrate Lumio data from SQLite to PostgreSQL (Neon)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from sqlalchemy import create_engine, text

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "lumio.db")
PG_URL = os.environ.get("DATABASE_URL", "")

# Migration order respecting foreign keys
TABLES = [
    "source",
    "user",
    "article",
    "watchlist",
    "watchlistmatch",
    "collection",
    "collectionarticle",
    "collectioncomment",
    "collection_draft",
    "notification",
    "session_token",
    "articlebookmark",
    "statuschange",
    "useractivity",
    "userprofile",
    "trendcache",
    "feedstatus",
    "filteredarticle",
    "editorialtopic",
    "congressfavorite",
]

# Tables that have an auto-increment id column needing sequence reset
TABLES_WITH_SERIAL_ID = [
    "source",
    "user",
    "article",
    "watchlist",
    "watchlistmatch",
    "collection",
    "collectionarticle",
    "collectioncomment",
    "collection_draft",
    "notification",
    "session_token",
    "articlebookmark",
    "statuschange",
    "useractivity",
    "userprofile",
    "trendcache",
    "feedstatus",
    "filteredarticle",
    "editorialtopic",
    "congressfavorite",
]

BATCH_SIZE = 500


def get_sqlite_rows(sqlite_conn, table):
    """Read all rows and column names from a SQLite table."""
    cursor = sqlite_conn.execute(f'SELECT * FROM [{table}]')
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return cols, rows


def migrate_table(sqlite_conn, pg_engine, table):
    """Migrate a single table from SQLite to PostgreSQL."""
    cols, rows = get_sqlite_rows(sqlite_conn, table)

    if not rows:
        print(f"  {table}: 0 rows (skipped)")
        return 0

    # Quote all column names (handles reserved words like "user")
    col_list = ", ".join(f'"{c}"' for c in cols)
    param_list = ", ".join(f":{c}" for c in cols)
    insert_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({param_list}) ON CONFLICT DO NOTHING'

    inserted = 0
    with pg_engine.connect() as pg:
        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start : batch_start + BATCH_SIZE]
            # Convert sqlite3.Row objects to dicts and fix SQLite→PG type mismatches
            # SQLite stores ALL booleans as 0/1; PostgreSQL needs True/False
            _BOOL_COLS = {
                "paywall", "is_peer_reviewed", "active", "notify_email",
                "is_read", "is_active", "notified",
            }
            batch_dicts = []
            for row in batch:
                d = dict(row)
                for k, v in d.items():
                    if k in _BOOL_COLS and isinstance(v, int):
                        d[k] = bool(v)
                batch_dicts.append(d)
            pg.execute(text(insert_sql), batch_dicts)
            inserted += len(batch)
        pg.commit()

    print(f"  {table}: {inserted} rows migrated")
    return inserted


def reset_sequences(pg_engine):
    """Reset PostgreSQL sequences for all tables with auto-increment id."""
    print("\nResetting sequences...")
    with pg_engine.connect() as pg:
        for table in TABLES_WITH_SERIAL_ID:
            try:
                result = pg.execute(
                    text(f"""SELECT setval(
                        pg_get_serial_sequence('"{table}"', 'id'),
                        COALESCE((SELECT MAX(id) FROM "{table}"), 0) + 1,
                        false
                    )""")
                )
                new_val = result.scalar()
                print(f"  {table}: sequence reset to {new_val}")
            except Exception as e:
                # Some tables may not have a serial sequence (e.g., no serial id)
                print(f"  {table}: no sequence or error ({e})")
        pg.commit()


def populate_search_vectors(pg_engine):
    """Populate the search_vector column on the article table."""
    print("\nPopulating article search_vector...")
    with pg_engine.connect() as pg:
        result = pg.execute(text("""
            UPDATE article SET search_vector =
                setweight(to_tsvector('simple', COALESCE(title, '')), 'A') ||
                setweight(to_tsvector('simple', COALESCE(summary_de, '')), 'A') ||
                setweight(to_tsvector('simple', COALESCE(abstract, '')), 'B') ||
                setweight(to_tsvector('simple', COALESCE(highlight_tags, '')), 'B') ||
                setweight(to_tsvector('simple', COALESCE(authors, '')), 'C') ||
                setweight(to_tsvector('simple', COALESCE(journal, '')), 'C') ||
                setweight(to_tsvector('simple', COALESCE(mesh_terms, '')), 'C') ||
                setweight(to_tsvector('simple', COALESCE(specialty, '')), 'C') ||
                setweight(to_tsvector('simple', COALESCE(source, '')), 'D')
        """))
        pg.commit()
        print(f"  Updated {result.rowcount} article rows with search vectors")


def verify_counts(sqlite_conn, pg_engine):
    """Compare row counts between SQLite and PostgreSQL."""
    print("\nRow count comparison:")
    print(f"  {'Table':<25} {'SQLite':>8} {'PostgreSQL':>12} {'Match':>7}")
    print(f"  {'-'*25} {'-'*8} {'-'*12} {'-'*7}")

    all_match = True
    for table in TABLES:
        sqlite_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]

        with pg_engine.connect() as pg:
            pg_count = pg.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()

        match = "OK" if sqlite_count == pg_count else "MISMATCH"
        if sqlite_count != pg_count:
            all_match = False
        print(f"  {table:<25} {sqlite_count:>8} {pg_count:>12} {match:>7}")

    return all_match


def dry_run(sqlite_conn):
    """Test SQLite reading without a PostgreSQL target."""
    print("DRY RUN: Testing SQLite reading only\n")
    total_rows = 0

    for table in TABLES:
        cols, rows = get_sqlite_rows(sqlite_conn, table)
        count = len(rows)
        total_rows += count

        # Validate that rows can be converted to dicts
        if rows:
            sample = dict(rows[0])
            col_preview = ", ".join(cols[:5])
            if len(cols) > 5:
                col_preview += f", ... ({len(cols)} total)"
            print(f"  {table}: {count} rows, cols: {col_preview}")
        else:
            print(f"  {table}: 0 rows, cols: {', '.join(cols)}")

    print(f"\nTotal: {total_rows} rows across {len(TABLES)} tables")
    print("Dry run complete. All tables readable.")


def migrate():
    """Run the full migration."""
    print(f"SQLite source: {SQLITE_PATH}")

    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    # Dry run if no DATABASE_URL
    if not PG_URL:
        print("No DATABASE_URL set - running in dry-run mode\n")
        dry_run(sqlite_conn)
        sqlite_conn.close()
        return

    print(f"PostgreSQL target: {PG_URL[:40]}...")
    pg_engine = create_engine(PG_URL)

    # Test PG connection
    with pg_engine.connect() as pg:
        pg.execute(text("SELECT 1"))
    print("PostgreSQL connection OK\n")

    # Migrate tables
    print("Migrating tables...")
    start = time.time()

    for table in TABLES:
        migrate_table(sqlite_conn, pg_engine, table)

    elapsed = time.time() - start
    print(f"\nData migration completed in {elapsed:.1f}s")

    # Reset sequences
    reset_sequences(pg_engine)

    # Populate search vectors
    populate_search_vectors(pg_engine)

    # Verify
    all_match = verify_counts(sqlite_conn, pg_engine)

    sqlite_conn.close()
    pg_engine.dispose()

    if all_match:
        print("\nMigration successful! All row counts match.")
    else:
        print("\nWARNING: Some row counts do not match. Check above for details.")
        sys.exit(1)


if __name__ == "__main__":
    migrate()

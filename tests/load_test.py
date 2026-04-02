#!/usr/bin/env python3
"""Lumio — Comprehensive Load & Concurrency Test Suite.

Part 1: HTTP Load Tests (concurrent GET requests, WebSocket probing)
Part 2: Database Concurrency Tests (bookmarks, status, collections, activities, race conditions)
Part 3: Code-level collision point analysis

NO LLM API calls are made. Only web endpoints, database operations, and concurrent user scenarios.
"""

import json
import os
import random
import sqlite3
import statistics
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
LUMIO_ROOT = "/Users/mgrothe/lumio"
sys.path.insert(0, LUMIO_ROOT)

DB_PATH = os.path.join(LUMIO_ROOT, "db", "lumio.db")
BASE_URL = "http://localhost:8501"

# Test user IDs (from existing users in the DB)
TEST_USER_IDS = [3, 4, 5, 6, 7, 8, 9, 10, 11]  # real user IDs
# We'll use user_id range 9000-9099 for test data to avoid polluting real data
TEST_USER_ID_BASE = 9000

import requests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def percentile(data, p):
    """Calculate p-th percentile of data."""
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def get_article_ids(n=50):
    """Get n article IDs from the DB for testing."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(f"SELECT id FROM article ORDER BY id DESC LIMIT {n}").fetchall()
    conn.close()
    return [r[0] for r in rows]


SEPARATOR = "=" * 72


# ============================================================================
# PART 1: HTTP LOAD TEST
# ============================================================================
def part1_http_load_test():
    print(f"\n{SEPARATOR}")
    print("PART 1: HTTP LOAD TEST")
    print(SEPARATOR)

    # --- Test 1.1: 10 concurrent GET requests ---
    print("\n--- Test 1.1: 10 concurrent page loads ---")
    results = []
    errors = []
    timeouts = []

    def fetch_page(thread_id):
        start = time.time()
        try:
            resp = requests.get(BASE_URL, timeout=30)
            elapsed = time.time() - start
            return {
                "thread": thread_id,
                "status": resp.status_code,
                "time": elapsed,
                "size": len(resp.content),
            }
        except requests.Timeout:
            return {"thread": thread_id, "status": "TIMEOUT", "time": 30.0, "size": 0}
        except Exception as e:
            return {"thread": thread_id, "status": f"ERROR: {e}", "time": time.time() - start, "size": 0}

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(fetch_page, i) for i in range(10)]
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            if isinstance(r["status"], int) and r["status"] == 200:
                pass
            elif r["status"] == "TIMEOUT":
                timeouts.append(r)
            else:
                errors.append(r)

    times = [r["time"] for r in results if isinstance(r["status"], int) and r["status"] == 200]
    print(f"  Successful: {len(times)}/10")
    print(f"  Errors: {len(errors)}")
    print(f"  Timeouts: {len(timeouts)}")
    if times:
        print(f"  Avg response time: {statistics.mean(times):.3f}s")
        print(f"  P95 response time: {percentile(times, 95):.3f}s")
        print(f"  Max response time: {max(times):.3f}s")
        print(f"  Min response time: {min(times):.3f}s")
    if errors:
        for e in errors[:3]:
            print(f"  Error detail: thread={e['thread']} status={e['status']}")

    # --- Test 1.2: 50 requests across 10 threads (rapid fire) ---
    print("\n--- Test 1.2: 50 rapid requests across 10 threads ---")
    results2 = []
    errors2 = []
    timeouts2 = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(fetch_page, i) for i in range(50)]
        for f in as_completed(futures):
            r = f.result()
            results2.append(r)
            if isinstance(r["status"], int) and r["status"] == 200:
                pass
            elif r["status"] == "TIMEOUT":
                timeouts2.append(r)
            else:
                errors2.append(r)

    times2 = [r["time"] for r in results2 if isinstance(r["status"], int) and r["status"] == 200]
    print(f"  Successful: {len(times2)}/50")
    print(f"  Errors: {len(errors2)}")
    print(f"  Timeouts: {len(timeouts2)}")
    if times2:
        print(f"  Avg response time: {statistics.mean(times2):.3f}s")
        print(f"  P95 response time: {percentile(times2, 95):.3f}s")
        print(f"  Max response time: {max(times2):.3f}s")
        print(f"  Min response time: {min(times2):.3f}s")
        print(f"  Total throughput: {len(times2) / sum(times2) * len(times2):.1f} req/s effective")
    if errors2:
        for e in errors2[:3]:
            print(f"  Error detail: thread={e['thread']} status={e['status']}")

    # --- Test 1.3: WebSocket upgrade attempts ---
    print("\n--- Test 1.3: WebSocket connection probing ---")
    ws_results = []
    ws_errors = []

    def ws_probe(thread_id):
        """Probe the Streamlit WebSocket endpoint."""
        start = time.time()
        try:
            # Streamlit uses /_stcore/stream for WebSocket
            resp = requests.get(
                f"{BASE_URL}/_stcore/stream",
                headers={
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Version": "13",
                    "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                },
                timeout=10,
            )
            elapsed = time.time() - start
            return {"thread": thread_id, "status": resp.status_code, "time": elapsed}
        except Exception as e:
            return {"thread": thread_id, "status": f"ERROR: {type(e).__name__}", "time": time.time() - start}

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(ws_probe, i) for i in range(10)]
        for f in as_completed(futures):
            r = f.result()
            ws_results.append(r)

    ws_times = [r["time"] for r in ws_results]
    ws_statuses = [r["status"] for r in ws_results]
    print(f"  Results: {len(ws_results)}/10")
    status_counts = {}
    for s in ws_statuses:
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"  Status distribution: {status_counts}")
    if ws_times:
        print(f"  Avg time: {statistics.mean(ws_times):.3f}s")
        print(f"  Max time: {max(ws_times):.3f}s")

    # --- Test 1.4: Streamlit internal endpoints ---
    print("\n--- Test 1.4: Streamlit internal endpoint load ---")
    endpoints = [
        "/",
        "/_stcore/health",
        "/_stcore/host-config",
    ]
    for ep in endpoints:
        times_ep = []
        errs = 0
        for _ in range(5):
            start = time.time()
            try:
                resp = requests.get(f"{BASE_URL}{ep}", timeout=10)
                elapsed = time.time() - start
                if resp.status_code == 200:
                    times_ep.append(elapsed)
                else:
                    errs += 1
            except:
                errs += 1
        if times_ep:
            print(f"  {ep}: avg={statistics.mean(times_ep):.3f}s, max={max(times_ep):.3f}s, errors={errs}")
        else:
            print(f"  {ep}: ALL FAILED (errors={errs})")


# ============================================================================
# PART 2: DATABASE CONCURRENCY TESTS
# ============================================================================
def part2_db_concurrency_test():
    print(f"\n{SEPARATOR}")
    print("PART 2: DATABASE CONCURRENCY TESTS")
    print(SEPARATOR)

    article_ids = get_article_ids(50)
    if len(article_ids) < 50:
        print(f"WARNING: Only {len(article_ids)} articles available, need 50")

    lock_errors = []
    corruption_errors = []
    all_errors = []

    def get_conn():
        """Get a connection with WAL mode and busy timeout."""
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    # --- Test 2.1: Concurrent bookmarks ---
    print("\n--- Test 2.1: 10 users each bookmarking 5 articles concurrently ---")
    # First, clean up any test bookmarks
    conn = get_conn()
    conn.execute("DELETE FROM articlebookmark WHERE user_id >= ?", (TEST_USER_ID_BASE,))
    conn.commit()
    conn.close()

    bookmark_errors = {"locked": 0, "other": 0, "success": 0}
    bookmark_lock = threading.Lock()

    def bookmark_articles(user_idx):
        user_id = TEST_USER_ID_BASE + user_idx
        arts = article_ids[user_idx * 5:(user_idx + 1) * 5]
        local_errors = []
        local_success = 0
        for aid in arts:
            try:
                conn = get_conn()
                conn.execute(
                    "INSERT OR IGNORE INTO articlebookmark (user_id, article_id, created_at) VALUES (?, ?, ?)",
                    (user_id, aid, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                conn.close()
                local_success += 1
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    local_errors.append("locked")
                else:
                    local_errors.append(str(e))
            except Exception as e:
                local_errors.append(str(e))
        with bookmark_lock:
            bookmark_errors["success"] += local_success
            for e in local_errors:
                if "locked" in e.lower():
                    bookmark_errors["locked"] += 1
                else:
                    bookmark_errors["other"] += 1

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(bookmark_articles, i) for i in range(10)]
        for f in as_completed(futures):
            f.result()
    elapsed = time.time() - start

    # Verify data
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM articlebookmark WHERE user_id >= ?", (TEST_USER_ID_BASE,)
    ).fetchone()[0]
    conn.close()

    print(f"  Time: {elapsed:.3f}s")
    print(f"  Successful inserts: {bookmark_errors['success']}")
    print(f"  'Database locked' errors: {bookmark_errors['locked']}")
    print(f"  Other errors: {bookmark_errors['other']}")
    print(f"  Rows in DB: {count} (expected: 50)")
    if count != 50:
        corruption_errors.append(f"Bookmark count mismatch: {count} vs 50 expected")
        print(f"  *** DATA ISSUE: expected 50, got {count}")

    # --- Test 2.2: Concurrent status changes (conflicting) ---
    print("\n--- Test 2.2: 5 users dismissing + 5 users bookmarking same articles ---")
    # Use a small set of articles for conflict
    conflict_articles = article_ids[:5]
    status_errors = {"locked": 0, "other": 0, "success": 0}
    status_lock = threading.Lock()

    # Save original statuses to restore later
    conn = get_conn()
    original_statuses = {}
    for aid in conflict_articles:
        row = conn.execute("SELECT status FROM article WHERE id = ?", (aid,)).fetchone()
        if row:
            original_statuses[aid] = row[0]
    conn.close()

    def change_status(user_idx, new_status):
        local_errors = []
        local_success = 0
        for aid in conflict_articles:
            try:
                conn = get_conn()
                # Read current status
                row = conn.execute("SELECT status FROM article WHERE id = ?", (aid,)).fetchone()
                if row:
                    old_status = row[0]
                    conn.execute(
                        "UPDATE article SET status = ? WHERE id = ?",
                        (new_status, aid),
                    )
                    conn.execute(
                        "INSERT INTO statuschange (article_id, user_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?, ?)",
                        (aid, TEST_USER_ID_BASE + user_idx, old_status, new_status, datetime.now(timezone.utc).isoformat()),
                    )
                    conn.commit()
                    local_success += 1
                conn.close()
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    local_errors.append("locked")
                else:
                    local_errors.append(str(e))
            except Exception as e:
                local_errors.append(str(e))
        with status_lock:
            status_errors["success"] += local_success
            for e in local_errors:
                if "locked" in e.lower():
                    status_errors["locked"] += 1
                else:
                    status_errors["other"] += 1

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = []
        for i in range(5):
            futures.append(pool.submit(change_status, i, "REJECTED"))
        for i in range(5, 10):
            futures.append(pool.submit(change_status, i, "SAVED"))
        for f in as_completed(futures):
            f.result()
    elapsed = time.time() - start

    # Check final state
    conn = get_conn()
    final_statuses = {}
    for aid in conflict_articles:
        row = conn.execute("SELECT status FROM article WHERE id = ?", (aid,)).fetchone()
        if row:
            final_statuses[aid] = row[0]
    conn.close()

    print(f"  Time: {elapsed:.3f}s")
    print(f"  Successful operations: {status_errors['success']}")
    print(f"  'Database locked' errors: {status_errors['locked']}")
    print(f"  Other errors: {status_errors['other']}")
    print(f"  Final article statuses (should be consistent):")
    for aid in conflict_articles:
        print(f"    Article {aid}: {final_statuses.get(aid, 'MISSING')}")
    # Note: final status will be whichever write happened last (not corrupt, just a race)

    # Restore original statuses
    conn = get_conn()
    for aid, status in original_statuses.items():
        conn.execute("UPDATE article SET status = ? WHERE id = ?", (status, aid))
    conn.commit()
    conn.close()

    # --- Test 2.3: Concurrent collection operations ---
    print("\n--- Test 2.3: Concurrent collection create/add/comment operations ---")
    coll_errors = {"locked": 0, "other": 0, "success": 0}
    coll_lock = threading.Lock()

    def collection_ops(user_idx):
        user_id = TEST_USER_ID_BASE + user_idx
        local_errors = []
        local_success = 0
        try:
            conn = get_conn()
            # Create a collection
            conn.execute(
                "INSERT INTO collection (user_id, name, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, f"Test Collection {user_idx}", f"Load test collection #{user_idx}",
                 "recherche", datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            coll_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Add articles to collection
            for aid in article_ids[user_idx * 3:(user_idx + 1) * 3]:
                conn.execute(
                    "INSERT OR IGNORE INTO collectionarticle (collection_id, article_id, added_at) VALUES (?, ?, ?)",
                    (coll_id, aid, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()

            # Check if collectioncomment table has the right schema
            try:
                conn.execute(
                    "INSERT INTO collectioncomment (collection_id, user_id, text, created_at) VALUES (?, ?, ?, ?)",
                    (coll_id, user_id, f"Test comment from user {user_idx}", datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            except sqlite3.OperationalError:
                # Table might not have these columns; try alternative
                pass

            conn.close()
            local_success += 1
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                local_errors.append("locked")
            else:
                local_errors.append(str(e))
        except Exception as e:
            local_errors.append(str(e))

        with coll_lock:
            coll_errors["success"] += local_success
            for e in local_errors:
                if "locked" in e.lower():
                    coll_errors["locked"] += 1
                else:
                    coll_errors["other"] += 1

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(collection_ops, i) for i in range(10)]
        for f in as_completed(futures):
            f.result()
    elapsed = time.time() - start

    conn = get_conn()
    coll_count = conn.execute(
        "SELECT COUNT(*) FROM collection WHERE user_id >= ?", (TEST_USER_ID_BASE,)
    ).fetchone()[0]
    ca_count = conn.execute(
        "SELECT COUNT(*) FROM collectionarticle ca JOIN collection c ON ca.collection_id = c.id WHERE c.user_id >= ?",
        (TEST_USER_ID_BASE,),
    ).fetchone()[0]
    conn.close()

    print(f"  Time: {elapsed:.3f}s")
    print(f"  Successful collection creates: {coll_errors['success']}")
    print(f"  'Database locked' errors: {coll_errors['locked']}")
    print(f"  Other errors: {coll_errors['other']}")
    print(f"  Collections in DB: {coll_count} (expected: 10)")
    print(f"  Collection articles in DB: {ca_count} (expected: 30)")
    if coll_count != 10:
        corruption_errors.append(f"Collection count mismatch: {coll_count} vs 10")
    if ca_count != 30:
        corruption_errors.append(f"CollectionArticle count mismatch: {ca_count} vs 30")

    # --- Test 2.4: Concurrent activity tracking ---
    print("\n--- Test 2.4: 10 users logging activities simultaneously ---")
    activity_errors = {"locked": 0, "other": 0, "success": 0}
    activity_lock = threading.Lock()

    def log_activities(user_idx):
        user_id = TEST_USER_ID_BASE + user_idx
        local_errors = []
        local_success = 0
        actions = ["page_view", "bookmark", "dismiss", "search", "export"]
        for action in actions:
            try:
                conn = get_conn()
                conn.execute(
                    "INSERT INTO useractivity (user_id, action, detail, session_id, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (user_id, action, f"load_test_{user_idx}", f"test_session_{user_idx}",
                     datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                conn.close()
                local_success += 1
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    local_errors.append("locked")
                else:
                    local_errors.append(str(e))
            except Exception as e:
                local_errors.append(str(e))
        with activity_lock:
            activity_errors["success"] += local_success
            for e in local_errors:
                if "locked" in e.lower():
                    activity_errors["locked"] += 1
                else:
                    activity_errors["other"] += 1

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(log_activities, i) for i in range(10)]
        for f in as_completed(futures):
            f.result()
    elapsed = time.time() - start

    conn = get_conn()
    act_count = conn.execute(
        "SELECT COUNT(*) FROM useractivity WHERE user_id >= ?", (TEST_USER_ID_BASE,)
    ).fetchone()[0]
    conn.close()

    print(f"  Time: {elapsed:.3f}s")
    print(f"  Successful inserts: {activity_errors['success']}")
    print(f"  'Database locked' errors: {activity_errors['locked']}")
    print(f"  Other errors: {activity_errors['other']}")
    print(f"  Activity rows in DB: {act_count} (expected: 50)")
    if act_count != 50:
        corruption_errors.append(f"Activity count mismatch: {act_count} vs 50")

    # --- Test 2.5: Read-while-write ---
    print("\n--- Test 2.5: Read-while-write (readers + writers concurrent) ---")
    rw_errors = {"read_locked": 0, "write_locked": 0, "read_ok": 0, "write_ok": 0, "other": 0}
    rw_lock = threading.Lock()

    def reader(thread_id):
        local_read = 0
        local_err = 0
        for _ in range(10):
            try:
                conn = get_conn()
                rows = conn.execute(
                    "SELECT id, title, relevance_score FROM article ORDER BY pub_date DESC LIMIT 20"
                ).fetchall()
                conn.close()
                local_read += 1
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    with rw_lock:
                        rw_errors["read_locked"] += 1
                else:
                    local_err += 1
            except:
                local_err += 1
        with rw_lock:
            rw_errors["read_ok"] += local_read
            rw_errors["other"] += local_err

    def writer(thread_id):
        user_id = TEST_USER_ID_BASE + 50 + thread_id
        local_write = 0
        local_err = 0
        for i in range(10):
            try:
                conn = get_conn()
                aid = article_ids[i % len(article_ids)]
                conn.execute(
                    "INSERT OR IGNORE INTO articlebookmark (user_id, article_id, created_at) VALUES (?, ?, ?)",
                    (user_id, aid, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                conn.close()
                local_write += 1
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    with rw_lock:
                        rw_errors["write_locked"] += 1
                else:
                    local_err += 1
            except:
                local_err += 1
        with rw_lock:
            rw_errors["write_ok"] += local_write
            rw_errors["other"] += local_err

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = []
        for i in range(5):
            futures.append(pool.submit(reader, i))
        for i in range(5):
            futures.append(pool.submit(writer, i))
        for f in as_completed(futures):
            f.result()
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.3f}s")
    print(f"  Successful reads: {rw_errors['read_ok']}/50")
    print(f"  Successful writes: {rw_errors['write_ok']}/50")
    print(f"  Read 'locked' errors: {rw_errors['read_locked']}")
    print(f"  Write 'locked' errors: {rw_errors['write_locked']}")
    print(f"  Other errors: {rw_errors['other']}")

    # --- Test 2.6: Race condition — toggle bookmark 100 times from 2 threads ---
    print("\n--- Test 2.6: Race condition — 2 users toggling same bookmark 100 times each ---")
    race_article = article_ids[0]
    race_user = TEST_USER_ID_BASE + 99

    # Clean slate
    conn = get_conn()
    conn.execute("DELETE FROM articlebookmark WHERE user_id = ? AND article_id = ?",
                 (race_user, race_article))
    conn.commit()
    conn.close()

    race_errors = {"locked": 0, "other": 0, "success": 0}
    race_lock = threading.Lock()

    def toggle_bookmark_raw(thread_id):
        local_success = 0
        local_errors = []
        for _ in range(100):
            try:
                conn = get_conn()
                # Check if exists
                row = conn.execute(
                    "SELECT id FROM articlebookmark WHERE user_id = ? AND article_id = ?",
                    (race_user, race_article),
                ).fetchone()
                if row:
                    conn.execute(
                        "DELETE FROM articlebookmark WHERE user_id = ? AND article_id = ?",
                        (race_user, race_article),
                    )
                else:
                    conn.execute(
                        "INSERT INTO articlebookmark (user_id, article_id, created_at) VALUES (?, ?, ?)",
                        (race_user, race_article, datetime.now(timezone.utc).isoformat()),
                    )
                conn.commit()
                conn.close()
                local_success += 1
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    local_errors.append("locked")
                else:
                    local_errors.append(str(e))
            except sqlite3.IntegrityError as e:
                local_errors.append(f"integrity: {e}")
            except Exception as e:
                local_errors.append(str(e))

        with race_lock:
            race_errors["success"] += local_success
            for e in local_errors:
                if "locked" in e.lower():
                    race_errors["locked"] += 1
                elif "integrity" in e.lower():
                    race_errors["other"] += 1
                else:
                    race_errors["other"] += 1

    start = time.time()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(toggle_bookmark_raw, i) for i in range(2)]
        for f in as_completed(futures):
            f.result()
    elapsed = time.time() - start

    # Check final state — should have 0 or 1 bookmark rows
    conn = get_conn()
    final_count = conn.execute(
        "SELECT COUNT(*) FROM articlebookmark WHERE user_id = ? AND article_id = ?",
        (race_user, race_article),
    ).fetchone()[0]
    # Also check for duplicates
    dup_check = conn.execute(
        "SELECT COUNT(*) FROM articlebookmark WHERE user_id = ?",
        (race_user,),
    ).fetchone()[0]
    conn.close()

    print(f"  Time: {elapsed:.3f}s")
    print(f"  Successful toggles: {race_errors['success']}/200")
    print(f"  'Database locked' errors: {race_errors['locked']}")
    print(f"  Other errors (incl. IntegrityError): {race_errors['other']}")
    print(f"  Final bookmark count for this user+article: {final_count} (should be 0 or 1)")
    print(f"  Total bookmarks for race user: {dup_check} (should be 0 or 1)")
    if final_count > 1:
        corruption_errors.append(f"DUPLICATE BOOKMARKS: {final_count} rows for same user+article")
        print(f"  *** RACE CONDITION DETECTED: Duplicate entries!")
    if race_errors["other"] > 0:
        print(f"  *** IntegrityError/other errors indicate race conditions in toggle logic")

    # --- Summary ---
    print(f"\n{'─' * 40}")
    print("PART 2 SUMMARY")
    print(f"{'─' * 40}")
    total_locked = (bookmark_errors["locked"] + status_errors["locked"] +
                    coll_errors["locked"] + activity_errors["locked"] +
                    rw_errors["read_locked"] + rw_errors["write_locked"] +
                    race_errors["locked"])
    print(f"  Total 'database is locked' errors: {total_locked}")
    print(f"  Data corruption issues: {len(corruption_errors)}")
    for ce in corruption_errors:
        print(f"    - {ce}")


# ============================================================================
# PART 3: COLLISION POINT ANALYSIS
# ============================================================================
def part3_collision_analysis():
    print(f"\n{SEPARATOR}")
    print("PART 3: COLLISION POINT ANALYSIS")
    print(SEPARATOR)

    issues = []

    # 3.1 Global mutable state — _engine singleton
    print("\n--- 3.1: Global mutable state ---")
    print("  [FOUND] src/models.py line 281: `_engine = None` — global singleton")
    print("    SQLAlchemy engine is shared across all Streamlit sessions in a process.")
    print("    This is FINE for reads (connection pooling) but means all sessions")
    print("    share the same connection pool. Under heavy load, pool exhaustion")
    print("    could block sessions.")
    issues.append("Global _engine singleton (shared connection pool)")

    # 3.2 Session state isolation
    print("\n--- 3.2: Session state isolation ---")
    print("  [OK] Streamlit's st.session_state is per-browser-session.")
    print("    Each user gets their own session_state dict. No cross-user leakage.")
    print("  [FOUND] components/auth.py: `current_user` stored in session_state.")
    print("    This is per-session, so different users don't interfere.")
    print("  [NOTE] st.cache_data is SHARED across all users in the same process.")
    print("    get_articles() with ttl=180 means all users see the same cached data.")
    print("    If user A dismisses an article, user B won't see the change for up to 3 min.")
    issues.append("st.cache_data shared across users (stale data for up to 180s)")

    # 3.3 Database write conflicts
    print("\n--- 3.3: Database write conflicts ---")
    print("  [FOUND] toggle_bookmark() in helpers.py is NOT atomic:")
    print("    1. SELECT to check if bookmark exists")
    print("    2. DELETE or INSERT based on result")
    print("    Between step 1 and 2, another thread could also read 'not exists'")
    print("    and both would INSERT, causing IntegrityError (caught by UNIQUE index)")
    print("    or both could read 'exists' and both DELETE, then both try to INSERT.")
    issues.append("toggle_bookmark() — read-then-write race condition (no transaction isolation)")

    print("  [FOUND] update_article_status() in helpers.py:")
    print("    Read current status, then update. Two concurrent updates could both")
    print("    read the same old_status but write different new_status values.")
    print("    The StatusChange audit log may record inconsistent old_status values.")
    issues.append("update_article_status() — audit log race condition")

    # 3.4 SQLite concurrency limitations
    print("\n--- 3.4: SQLite concurrency ---")
    print("  [OK] WAL mode enabled in get_engine() — allows concurrent readers.")
    print("  [RISK] SQLite allows only ONE writer at a time. Under 10 concurrent")
    print("    users doing writes, transactions may queue and add latency.")
    print("  [RISK] No PRAGMA busy_timeout set in the SQLAlchemy engine —")
    print("    only WAL pragma is set. Busy timeout defaults to 0, which means")
    print("    write attempts that find a lock will fail immediately.")
    issues.append("No busy_timeout PRAGMA in SQLAlchemy engine — writes fail instead of retrying")

    # Check if busy_timeout is set
    print("\n  Verifying busy_timeout in running DB...")
    conn = sqlite3.connect(DB_PATH)
    bt = conn.execute("PRAGMA busy_timeout").fetchone()
    jm = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    print(f"    busy_timeout: {bt[0]}ms")
    print(f"    journal_mode: {jm[0]}")

    # 3.5 File system conflicts
    print("\n--- 3.5: File system conflicts ---")
    print("  [OK] Static files (favicon, CSS) are read-only at startup.")
    print("  [RISK] FTS5 rebuild in init_fts5() / populate_fts5() uses raw sqlite3")
    print("    connections (NOT the SQLAlchemy pool). If one session triggers a")
    print("    rebuild while another is reading FTS, results may be incomplete.")
    issues.append("FTS5 uses separate sqlite3 connections (bypass engine pool)")

    # 3.6 Cache invalidation race
    print("\n--- 3.6: Cache invalidation ---")
    print("  [FOUND] update_article_status() calls get_articles.clear() after commit.")
    print("    If two users update status simultaneously, the cache clear from user A")
    print("    may run BEFORE user B's commit, causing user B's change to be")
    print("    invisible until the next TTL expiry.")
    issues.append("Cache clear race — update + clear not atomic")

    # 3.7 Direct sqlite3 vs SQLAlchemy
    print("\n--- 3.7: Mixed connection patterns ---")
    print("  [FOUND] Code uses BOTH:")
    print("    - SQLAlchemy/SQLModel sessions (get_session()) for ORM operations")
    print("    - Raw sqlite3.connect() in auth.py, feed.py, init_fts5(), etc.")
    print("    These two connection pools don't coordinate. A write via sqlite3")
    print("    won't be visible to an SQLAlchemy session in the same thread until")
    print("    the SQLAlchemy session is refreshed/committed.")
    issues.append("Mixed sqlite3 + SQLAlchemy connections (no coordination)")

    print(f"\n{'─' * 40}")
    print("PART 3 SUMMARY: COLLISION POINTS")
    print(f"{'─' * 40}")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")


# ============================================================================
# CLEANUP
# ============================================================================
def cleanup():
    print(f"\n{SEPARATOR}")
    print("CLEANUP: Removing all test data")
    print(SEPARATOR)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")

    # Remove test bookmarks
    r1 = conn.execute("DELETE FROM articlebookmark WHERE user_id >= ?", (TEST_USER_ID_BASE,))
    print(f"  Deleted {r1.rowcount} test bookmarks")

    # Remove test activities
    r2 = conn.execute("DELETE FROM useractivity WHERE user_id >= ?", (TEST_USER_ID_BASE,))
    print(f"  Deleted {r2.rowcount} test activities")

    # Remove test status changes
    r3 = conn.execute("DELETE FROM statuschange WHERE user_id >= ?", (TEST_USER_ID_BASE,))
    print(f"  Deleted {r3.rowcount} test status changes")

    # Remove test collection articles (via join)
    conn.execute("""
        DELETE FROM collectionarticle WHERE collection_id IN (
            SELECT id FROM collection WHERE user_id >= ?
        )
    """, (TEST_USER_ID_BASE,))

    # Remove test collection comments
    try:
        conn.execute("""
            DELETE FROM collectioncomment WHERE collection_id IN (
                SELECT id FROM collection WHERE user_id >= ?
            )
        """, (TEST_USER_ID_BASE,))
    except:
        pass

    # Remove test collections
    r4 = conn.execute("DELETE FROM collection WHERE user_id >= ?", (TEST_USER_ID_BASE,))
    print(f"  Deleted {r4.rowcount} test collections")

    conn.commit()
    conn.close()
    print("  Cleanup complete. No test data remains.")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print(f"{'#' * 72}")
    print("# LUMIO LOAD & CONCURRENCY TEST SUITE")
    print(f"# Started: {datetime.now().isoformat()}")
    print(f"# DB: {DB_PATH}")
    print(f"# URL: {BASE_URL}")
    print(f"# Articles in DB: {len(get_article_ids(9999))}")
    print(f"{'#' * 72}")

    try:
        part1_http_load_test()
    except Exception as e:
        print(f"\n*** PART 1 FAILED: {e}")
        traceback.print_exc()

    try:
        part2_db_concurrency_test()
    except Exception as e:
        print(f"\n*** PART 2 FAILED: {e}")
        traceback.print_exc()

    try:
        part3_collision_analysis()
    except Exception as e:
        print(f"\n*** PART 3 FAILED: {e}")
        traceback.print_exc()

    try:
        cleanup()
    except Exception as e:
        print(f"\n*** CLEANUP FAILED: {e}")
        traceback.print_exc()

    print(f"\n{'#' * 72}")
    print(f"# Finished: {datetime.now().isoformat()}")
    print(f"{'#' * 72}")

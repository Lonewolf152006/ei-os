"""
EI-OS — Database Verification Script
Checks that all required tables and views exist in the PostgreSQL database.

Usage:
    python scripts/verify_db.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import os
import sys

from dotenv import load_dotenv


REQUIRED_TABLES = [
    "events",
    "entities",
    "event_entities",
    "event_edges",
    "queries",
]

REQUIRED_VIEWS = [
    "causal_chain",
]


def connect():
    """Connect to PostgreSQL using DATABASE_URL."""
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "").strip()

    if not db_url:
        print("❌  DATABASE_URL is not set in .env")
        print("    Run: cp .env.example .env  →  add your Neon connection string")
        sys.exit(1)

    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        return conn
    except ImportError:
        print("❌  psycopg2 not installed. Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌  Connection failed: {e}")
        sys.exit(1)


def check_table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the public schema."""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]


def check_view_exists(cursor, view_name: str) -> bool:
    """Check if a view exists in the public schema."""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.views
            WHERE table_schema = 'public'
              AND table_name = %s
        );
    """, (view_name,))
    return cursor.fetchone()[0]


def main():
    print("=" * 50)
    print("  EI-OS Database Verification")
    print("=" * 50)
    print()

    conn = connect()
    cursor = conn.cursor()
    results = []

    # Check tables
    print("📋  Checking tables...")
    for table in REQUIRED_TABLES:
        exists = check_table_exists(cursor, table)
        status = "PASS ✅" if exists else "FAIL ❌"
        print(f"    {status}  {table}")
        results.append((f"table:{table}", exists))

    print()

    # Check views
    print("📋  Checking views...")
    for view in REQUIRED_VIEWS:
        exists = check_view_exists(cursor, view)
        status = "PASS ✅" if exists else "FAIL ❌"
        print(f"    {status}  {view}")
        results.append((f"view:{view}", exists))

    cursor.close()
    conn.close()

    # Summary
    print()
    print("=" * 50)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    failed = total - passed

    if failed == 0:
        print(f"  ✅  ALL CHECKS PASSED ({passed}/{total})")
        print("  🚀  Database is ready for ingestion!")
        print("=" * 50)
        sys.exit(0)
    else:
        print(f"  ❌  {failed} CHECK(S) FAILED ({passed}/{total} passed)")
        print()
        print("  Failed checks:")
        for name, ok in results:
            if not ok:
                print(f"    ✗  {name}")
        print()
        print("  Fix: Run the schema against your database:")
        print("    psql $DATABASE_URL < graph/schema.sql")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
scripts/count_events.py — Verify ingestion results by counting rows in all tables.

Usage:
    python scripts/count_events.py

Exit code 1 if events table is empty.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv


def main():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print("DATABASE_URL is not set.")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    print("=" * 58)
    print("  EI-OS Event Count Report")
    print("=" * 58)
    print()

    # Events by source and type
    cursor.execute("""
        SELECT source_type,
               metadata->>'event_type' AS event_type,
               COUNT(*) AS n
        FROM events
        GROUP BY source_type, metadata->>'event_type'
        ORDER BY source_type;
    """)
    rows = cursor.fetchall()

    if not rows:
        print("  EVENTS TABLE IS EMPTY!")
        print("  Run: python -m ingestion.parsers")
        cursor.close()
        conn.close()
        sys.exit(1)

    print("  Events by source:")
    print("  +------------------+----------------------+-------+")
    print("  | source_type      | event_type           | count |")
    print("  +------------------+----------------------+-------+")
    total_events = 0
    for source_type, event_type, n in rows:
        print(f"  | {source_type:<16} | {(event_type or '-'):<20} | {n:>5} |")
        total_events += n
    print("  +------------------+----------------------+-------+")
    print(f"  | TOTAL            |                      | {total_events:>5} |")
    print("  +------------------+----------------------+-------+")
    print()

    # Entity counts
    cursor.execute("SELECT COUNT(*) FROM entities;")
    entity_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM event_entities;")
    link_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM event_edges;")
    edge_count = cursor.fetchone()[0]

    print("  Related tables:")
    print(f"    entities:        {entity_count:>5} rows")
    print(f"    event_entities:  {link_count:>5} rows (links)")
    print(f"    event_edges:     {edge_count:>5} rows (causal edges)")
    print()

    # Entity type breakdown
    cursor.execute("""
        SELECT type, COUNT(*) AS n
        FROM entities
        GROUP BY type
        ORDER BY n DESC;
    """)
    etypes = cursor.fetchall()
    if etypes:
        print("  Entity types:")
        for etype, n in etypes:
            print(f"    {etype:<22} {n:>4}")
        print()

    cursor.close()
    conn.close()

    print(f"  Summary: {total_events} events, {entity_count} entities, {link_count} links")
    print()


if __name__ == "__main__":
    main()

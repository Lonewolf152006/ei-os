"""
ingestion/parsers.py — Parse GitHub PRs, Slack messages, and CSV complaints
into the EI-OS knowledge graph.

Schema mapping (user spec → actual DB columns):
  source     → source_type  ('github_pr', 'slack_message', 'csv_complaint')
  ref_id     → source_id    (PR number, slack ts, complaint id)
  title      → title
  body_raw   → body         (original text)
  body       → compressed_body  (compressed by token reducer)
  occurred_at → occurred_at
  metadata   → metadata     (JSONB: author, event_type, labels, etc.)

Usage:
    python -m ingestion.parsers
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

from psycopg2.extras import Json

from token_reducer.proxy import reduce as token_reduce
from ingestion.db import get_connection, insert_entities


# ──────────────────────────────────────────────────────
# GitHub PR Parser
# ──────────────────────────────────────────────────────

def parse_github_prs(file_path: str) -> dict:
    """Parse GitHub PRs JSON and insert into events table."""
    with open(file_path, 'r', encoding='utf-8') as f:
        prs = json.load(f)

    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    total_ratio = 0.0

    for pr in prs:
        raw_text = pr['title'] + '\n\n' + pr.get('body', '')
        result = token_reduce(raw_text, keep_ratio=0.30)

        source_type = 'github_pr'
        source_id = f"PR #{pr['number']}"
        title = pr['title']
        body = raw_text
        compressed_body = result['compressed']
        occurred_at = pr.get('merged_at') or pr['created_at']
        event_type = 'pr_merge' if pr.get('merged_at') else 'pr_opened'

        metadata = {
            'author': pr['user']['login'],
            'event_type': event_type,
            'url': pr['html_url'],
            'labels': [l['name'] for l in pr.get('labels', [])],
            'files_changed': pr.get('changed_files', 0),
            'number': pr['number'],
        }

        cursor.execute("""
            INSERT INTO events (source_type, source_id, title, body, compressed_body, metadata, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_type, source_id)
            DO UPDATE SET body = EXCLUDED.body,
                          compressed_body = EXCLUDED.compressed_body,
                          metadata = EXCLUDED.metadata
            RETURNING id;
        """, (source_type, source_id, title, body, compressed_body,
              Json(metadata), occurred_at))

        event_id = cursor.fetchone()[0]
        insert_entities(cursor, event_id, result['entities'])

        total_ratio += result['stats']['reduction_ratio']
        count += 1

    conn.commit()
    cursor.close()
    conn.close()

    avg_compression = round(total_ratio / max(count, 1), 1)
    return {'count': count, 'avg_compression': avg_compression}


# ──────────────────────────────────────────────────────
# Slack Export Parser
# ──────────────────────────────────────────────────────

def parse_slack_export(file_path: str) -> dict:
    """Parse Slack export JSON and insert into events table."""
    with open(file_path, 'r', encoding='utf-8') as f:
        messages = json.load(f)

    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    total_ratio = 0.0

    for msg in messages:
        # Skip system messages and trivial ones
        if 'subtype' in msg:
            continue
        text = msg.get('text', '')
        if len(text.split()) < 5:
            continue

        result = token_reduce(text, keep_ratio=0.30)

        source_type = 'slack_message'
        ts_raw = msg.get('ts', '')

        # Parse ISO timestamp from our data format
        try:
            occurred_dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            occurred_dt = datetime.now(timezone.utc)

        source_id = ts_raw
        title = text[:80] + ('...' if len(text) > 80 else '')
        body = text
        compressed_body = result['compressed']

        metadata = {
            'author': msg.get('user', 'unknown'),
            'event_type': 'message',
            'channel': msg.get('channel', '#engineering'),
            'thread_ts': msg.get('thread_ts'),
            'reactions': msg.get('reactions', []),
        }

        cursor.execute("""
            INSERT INTO events (source_type, source_id, title, body, compressed_body, metadata, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_type, source_id)
            DO UPDATE SET body = EXCLUDED.body,
                          compressed_body = EXCLUDED.compressed_body,
                          metadata = EXCLUDED.metadata
            RETURNING id;
        """, (source_type, source_id, title, body, compressed_body,
              Json(metadata), occurred_dt))

        event_id = cursor.fetchone()[0]
        insert_entities(cursor, event_id, result['entities'])

        total_ratio += result['stats']['reduction_ratio']
        count += 1

    conn.commit()
    cursor.close()
    conn.close()

    avg_compression = round(total_ratio / max(count, 1), 1)
    return {'count': count, 'avg_compression': avg_compression}


# ──────────────────────────────────────────────────────
# Complaints CSV Parser
# ──────────────────────────────────────────────────────

def parse_complaints_csv(file_path: str) -> dict:
    """Parse complaints CSV and insert into events table."""
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    total_ratio = 0.0

    for row in rows:
        description = row['description']
        result = token_reduce(description, keep_ratio=0.30)

        source_type = 'csv_complaint'
        source_id = row['id']
        title = row['title']
        body = description
        compressed_body = result['compressed']
        occurred_at = row['created_at']

        metadata = {
            'author': 'customer',
            'event_type': 'customer_complaint',
            'severity': row['severity'],
        }

        cursor.execute("""
            INSERT INTO events (source_type, source_id, title, body, compressed_body, metadata, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_type, source_id)
            DO UPDATE SET body = EXCLUDED.body,
                          compressed_body = EXCLUDED.compressed_body,
                          metadata = EXCLUDED.metadata
            RETURNING id;
        """, (source_type, source_id, title, body, compressed_body,
              Json(metadata), occurred_at))

        event_id = cursor.fetchone()[0]
        insert_entities(cursor, event_id, result['entities'])

        total_ratio += result['stats']['reduction_ratio']
        count += 1

    conn.commit()
    cursor.close()
    conn.close()

    avg_compression = round(total_ratio / max(count, 1), 1)
    return {'count': count, 'avg_compression': avg_compression}


# ──────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────

def main():
    """Run all three parsers and print summary table."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

    print("=" * 58)
    print("  EI-OS Ingestion Pipeline")
    print("=" * 58)
    print()

    # Parse all three sources
    print("  [1/3] Parsing GitHub PRs...")
    gh = parse_github_prs(os.path.join(data_dir, 'github_prs.json'))
    print(f"         -> {gh['count']} events, {gh['avg_compression']}% compression")

    print("  [2/3] Parsing Slack messages...")
    sl = parse_slack_export(os.path.join(data_dir, 'slack_export.json'))
    print(f"         -> {sl['count']} events, {sl['avg_compression']}% compression")

    print("  [3/3] Parsing complaints CSV...")
    cs = parse_complaints_csv(os.path.join(data_dir, 'complaints.csv'))
    print(f"         -> {cs['count']} events, {cs['avg_compression']}% compression")

    # Summary table
    total_events = gh['count'] + sl['count'] + cs['count']
    total_ratios = (
        gh['avg_compression'] * gh['count']
        + sl['avg_compression'] * sl['count']
        + cs['avg_compression'] * cs['count']
    )
    avg_total = round(total_ratios / max(total_events, 1), 1)

    print()
    print("  +------------------+--------+------------------+")
    print("  | Source           | Events | Avg compression  |")
    print("  +------------------+--------+------------------+")
    print(f"  | GitHub PRs       | {gh['count']:>6} | {gh['avg_compression']:>15}% |")
    print(f"  | Slack messages   | {sl['count']:>6} | {sl['avg_compression']:>15}% |")
    print(f"  | Complaints       | {cs['count']:>6} | {cs['avg_compression']:>15}% |")
    print("  +------------------+--------+------------------+")
    print(f"  | TOTAL            | {total_events:>6} | {avg_total:>15}% |")
    print("  +------------------+--------+------------------+")
    print()
    print(f"  Done! {total_events} events ingested into Neon PostgreSQL.")
    print()


if __name__ == '__main__':
    main()

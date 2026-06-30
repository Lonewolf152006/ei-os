"""
agents/db.py — Shared database helpers for all three EI-OS agents.

Adapts the user's spec column names to the actual Hour 1 schema:
  spec ref_id          → DB source_id
  spec source          → DB source_type
  spec from_event_id   → DB source_event_id
  spec to_event_id     → DB target_event_id
  spec relation        → DB relation_type
  spec weight          → DB confidence
  spec entities.name   → DB entities.value
  spec reasoning_path  → DB reasoning_trace
"""

import os
import json

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


def get_conn():
    """Return a psycopg2 connection using DATABASE_URL from .env. Autocommit off."""
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env first.\n"
            "  → Sign up at https://neon.tech and copy your connection string."
        )
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    return conn


def get_new_events(conn, limit=50):
    """
    SELECT events that have NO outgoing edges yet.
    Returns list of dicts with: id, source_id, source_type, title, occurred_at, body.
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT e.id, e.source_id, e.source_type, e.title,
               e.occurred_at, e.body
        FROM events e
        WHERE NOT EXISTS (
            SELECT 1 FROM event_edges ee
            WHERE ee.source_event_id = e.id
        )
        ORDER BY e.occurred_at DESC
        LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def get_entities_for_event(conn, event_id):
    """Return list of entity value strings for a given event."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT en.value
        FROM entities en
        JOIN event_entities ee ON ee.entity_id = en.id
        WHERE ee.event_id = %s
    """, (event_id,))
    result = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return result


def get_events_with_entity(conn, entity_value, exclude_event_id):
    """
    Find events that share an entity (by value), excluding one event.
    Returns list of dicts.
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT e.id, e.title, e.source_type, e.occurred_at
        FROM events e
        JOIN event_entities ee ON ee.event_id = e.id
        JOIN entities en ON en.id = ee.entity_id
        WHERE en.value = %s AND e.id != %s
        ORDER BY e.occurred_at DESC
        LIMIT 10
    """, (entity_value, exclude_event_id))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def create_edge(conn, source_id, target_id, relation_type, confidence):
    """
    Insert a causal edge. ON CONFLICT do nothing (idempotent).

    relation_type must be one of:
      caused_by, followed_by, related_to, escalated_to, resolved_by
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO event_edges (source_event_id, target_event_id, relation_type, confidence)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (source_event_id, target_event_id, relation_type) DO NOTHING
    """, (source_id, target_id, relation_type, confidence))
    cursor.close()


def fts_search(conn, question, limit=5):
    """
    Full-text search across events. Returns ranked results.
    Falls back to ILIKE if FTS returns nothing.
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Try FTS first
    cursor.execute("""
        SELECT id, title, source_type, body, occurred_at, source_id,
               ts_rank(
                   to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,'')),
                   plainto_tsquery('english', %s)
               ) AS rank
        FROM events
        WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,''))
              @@ plainto_tsquery('english', %s)
        ORDER BY rank DESC, occurred_at DESC
        LIMIT %s
    """, (question, question, limit))
    rows = cursor.fetchall()

    # Fallback: ILIKE search on keywords if FTS returns nothing
    if not rows:
        keywords = [w for w in question.split() if len(w) > 3]
        if keywords:
            like_pattern = '%' + '%'.join(keywords[:3]) + '%'
            cursor.execute("""
                SELECT id, title, source_type, body, occurred_at, source_id,
                       0.5 AS rank
                FROM events
                WHERE title ILIKE %s OR body ILIKE %s
                ORDER BY occurred_at DESC
                LIMIT %s
            """, (like_pattern, like_pattern, limit))
            rows = cursor.fetchall()

    # Last resort: return most recent events
    if not rows:
        cursor.execute("""
            SELECT id, title, source_type, body, occurred_at, source_id,
                   0.1 AS rank
            FROM events
            ORDER BY occurred_at DESC
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()

    cursor.close()
    return [dict(r) for r in rows]


def get_causal_chain(conn, anchor_event_id, max_depth=5):
    """
    Walk the causal chain backward from an anchor event using recursive CTE.
    Returns list of dicts with event info + edge metadata.
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        WITH RECURSIVE cause_tree AS (
            SELECT source_event_id, target_event_id, relation_type,
                   confidence, 1 AS depth
            FROM event_edges
            WHERE target_event_id = %s

            UNION ALL

            SELECT ee.source_event_id, ee.target_event_id, ee.relation_type,
                   ee.confidence, ct.depth + 1
            FROM event_edges ee
            JOIN cause_tree ct ON ee.target_event_id = ct.source_event_id
            WHERE ct.depth < %s
        )
        SELECT DISTINCT e.id, e.title, e.source_type, e.body,
                        e.occurred_at, e.source_id,
                        ct.relation_type, ct.depth, ct.confidence
        FROM cause_tree ct
        JOIN events e ON ct.source_event_id = e.id
        ORDER BY ct.depth ASC, e.occurred_at ASC
    """, (anchor_event_id, max_depth))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def get_all_events_for_context(conn, limit=30):
    """
    Get all events ordered chronologically for building LLM context.
    Used when causal chain is empty.
    """
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT e.id, e.title, e.source_type, e.body, e.occurred_at,
               e.source_id, e.metadata
        FROM events e
        ORDER BY e.occurred_at ASC
        LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]


def save_query(conn, question, reasoning_path, answer):
    """
    Save a query result to the queries table.
    reasoning_path is a list that gets serialised as JSON.
    Returns the new query id.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO queries (question, reasoning_trace, answer)
        VALUES (%s, %s::jsonb, %s)
        RETURNING id
    """, (question, json.dumps(reasoning_path), answer))
    query_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return query_id

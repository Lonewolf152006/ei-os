"""
ingestion/db.py — Shared database helpers for the ingestion layer.

Provides:
  get_connection()   → psycopg2 connection to Neon PostgreSQL
  insert_entities()  → UPSERT entities + link them to events
"""

import os
import re

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


# ── Entity-type inference patterns ──────────────────────
_TYPE_PATTERNS = [
    (re.compile(r'\bPR[- ]?#?\d+\b', re.IGNORECASE), 'pr'),
    (re.compile(r'\b[A-Z]+-\d+\b'),                   'ticket'),
    (re.compile(r'\bv\d+\.\d+'),                       'version'),
    (re.compile(r'^#[a-z]'),                           'channel'),
]


def _infer_entity_type(value: str) -> str:
    """Classify an entity string into a type via regex."""
    for pattern, etype in _TYPE_PATTERNS:
        if pattern.search(value):
            return etype
    return 'reference'


def get_connection():
    """
    Load .env and return a psycopg2 connection to DATABASE_URL.
    Raises RuntimeError if DATABASE_URL is not set.
    """
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env first.\n"
            "  → Sign up at https://neon.tech and copy your connection string."
        )
    return psycopg2.connect(db_url)


def insert_entities(cursor, event_id: int, entities: list):
    """
    For each entity, UPSERT into entities table, then link to event
    via event_entities.

    Accepts either:
      - list of strings (raw entity values)
      - list of dicts with 'value' and 'type' keys (from proxy.extract_entities)
    """

    # Batch insert entities
    entity_records = []
    for ent in entities:
        if isinstance(ent, dict):
            value = ent.get('value', '').strip()
            etype = ent.get('type', 'reference')
        else:
            value = str(ent).strip()
            etype = _infer_entity_type(value)
        if value:
            entity_records.append((value, etype))

    if not entity_records:
        return

    # 1. Insert ignoring conflicts
    execute_values(
        cursor,
        "INSERT INTO entities (value, type) VALUES %s ON CONFLICT (value, type) DO NOTHING",
        entity_records
    )

    # 2. Fetch IDs for all of them
    cursor.execute("CREATE TEMP TABLE IF NOT EXISTS temp_entities (value TEXT, type TEXT) ON COMMIT DROP")
    cursor.execute("TRUNCATE temp_entities")
    execute_values(
        cursor,
        "INSERT INTO temp_entities (value, type) VALUES %s",
        entity_records
    )
    cursor.execute("""
        SELECT e.id FROM entities e
        JOIN temp_entities t ON e.value = t.value AND e.type = t.type
    """)
    entity_ids = [row[0] for row in cursor.fetchall()]

    # 3. Link to event
    link_records = [(event_id, eid) for eid in entity_ids]
    execute_values(
        cursor,
        "INSERT INTO event_entities (event_id, entity_id) VALUES %s ON CONFLICT DO NOTHING",
        link_records
    )

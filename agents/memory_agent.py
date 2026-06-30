"""
agents/memory_agent.py — Detects causal relationships between events
and creates edges in the EI-OS knowledge graph.

Scans events without outgoing edges, finds shared entities,
and classifies relationships by time proximity.

Relation mapping to schema CHECK constraint:
  spec 'triggered' (<=2h)  → 'caused_by'
  spec 'caused'    (<=24h) → 'related_to'
  spec 'mentions'  (>24h)  → 'followed_by'
"""

from datetime import timezone
from agents.db import (
    get_conn,
    get_new_events,
    get_entities_for_event,
    get_events_with_entity,
    create_edge,
)


def run():
    """
    Scan all unlinked events, find shared entities, and create edges.
    Returns dict with events_processed and edges_created.
    """
    print("Getting connection...")
    conn = get_conn()
    print("Getting new events...")
    new_events = get_new_events(conn, limit=50)
    print(f"Found {len(new_events)} new events")
    edges_created = 0
    seen_pairs = set()

    for event in new_events:
        print(f"Processing event {event['id']}")
        event_id = event['id']
        event_time = event['occurred_at']

        # Ensure timezone-aware
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        entities = get_entities_for_event(conn, event_id)

        for entity_value in entities:
            related = get_events_with_entity(conn, entity_value, exclude_event_id=event_id)

            for rel_event in related:
                rel_id = rel_event['id']
                rel_time = rel_event['occurred_at']

                # Ensure timezone-aware
                if rel_time.tzinfo is None:
                    rel_time = rel_time.replace(tzinfo=timezone.utc)

                # Determine direction: earlier → later
                if event_time < rel_time:
                    src_id, tgt_id = event_id, rel_id
                else:
                    src_id, tgt_id = rel_id, event_id

                # Skip if we already processed this pair
                pair_key = (src_id, tgt_id)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Classify by time difference
                time_diff = abs((event_time - rel_time).total_seconds())
                hours_diff = time_diff / 3600

                if hours_diff <= 2:
                    relation_type = 'caused_by'
                    confidence = 0.90
                elif hours_diff <= 24:
                    relation_type = 'related_to'
                    confidence = 0.70
                else:
                    relation_type = 'followed_by'
                    confidence = 0.40

                create_edge(conn, src_id, tgt_id, relation_type, confidence)
                edges_created += 1

    print("Committing...")
    conn.commit()
    print("Closing...")
    conn.close()

    result = {
        "events_processed": len(new_events),
        "edges_created": edges_created,
    }

    print("=" * 50)
    print("  Memory Agent — Results")
    print("=" * 50)
    print(f"  Events scanned:  {result['events_processed']}")
    print(f"  Edges created:   {result['edges_created']}")
    print("=" * 50)

    return result


if __name__ == '__main__':
    run()

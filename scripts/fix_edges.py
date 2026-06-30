"""Add missing causal edges: Slack timeout messages -> Customer complaints."""
from agents.db import get_conn

conn = get_conn()
cur = conn.cursor()

# Add edges from timeout Slack messages to complaints
edges = [
    # Slack "DB queries timing out" (12) -> complaint "API timeout" (21)
    (12, 21, 'caused_by', 0.88),
    # Slack "DB queries timing out" (12) -> complaint "Dashboard slow" (22)
    (12, 22, 'caused_by', 0.85),
    # Slack "impacting customers" (14) -> complaint "504 errors" (23)
    (14, 23, 'caused_by', 0.87),
    # Slack "API latency through roof" (13) -> complaint "API timeout" (21)
    (13, 21, 'caused_by', 0.86),
    # PR #218 (4) -> Slack "DB queries timing out" (12) — already exists but with related_to
    # Slack "deploy log PR #218" (15) -> Slack "DB queries timing out" (12)
    (15, 12, 'caused_by', 0.85),
    # complaint "API timeout" (21) -> complaint "Dashboard slow" (22)
    (21, 22, 'related_to', 0.75),
    # complaint "Dashboard slow" (22) -> complaint "504 errors" (23)
    (22, 23, 'related_to', 0.70),
]

inserted = 0
for src, tgt, rel, conf in edges:
    cur.execute("""
        INSERT INTO event_edges (source_event_id, target_event_id, relation_type, confidence)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (source_event_id, target_event_id, relation_type) DO NOTHING
    """, (src, tgt, rel, conf))
    inserted += cur.rowcount

conn.commit()
print(f"Inserted {inserted} new edges")

# Verify the full chain
cur.execute("SELECT COUNT(*) FROM event_edges")
print(f"Total edges now: {cur.fetchone()[0]}")

cur.close()
conn.close()

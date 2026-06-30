"""Check demo data: verify PR #218 has edges and identify key event IDs."""
from agents.db import get_conn

conn = get_conn()
cur = conn.cursor()

print("=== PR #218 and activity-related events ===")
cur.execute("""
    SELECT e.id, e.title, e.source_type, e.occurred_at, e.source_id,
           COUNT(ee.target_event_id) as outgoing_edges
    FROM events e
    LEFT JOIN event_edges ee ON ee.source_event_id = e.id
    WHERE e.source_id LIKE '%%218%%' OR e.title ILIKE '%%activity%%'
    GROUP BY e.id, e.title, e.source_type, e.occurred_at, e.source_id
    ORDER BY e.occurred_at;
""")
for r in cur.fetchall():
    print(f"  id={r[0]:>3} | {r[2]:<14} | edges={r[5]} | {r[1][:60]}")

print()
print("=== Slack messages about timeouts/latency/timing ===")
cur.execute("""
    SELECT id, title, source_type, occurred_at FROM events
    WHERE source_type = 'slack_message'
      AND (title ILIKE '%%timeout%%' OR title ILIKE '%%latency%%'
           OR title ILIKE '%%timing%%' OR title ILIKE '%%database%%')
    ORDER BY occurred_at;
""")
for r in cur.fetchall():
    print(f"  id={r[0]:>3} | {r[1][:70]}")

print()
print("=== Customer complaints ===")
cur.execute("""
    SELECT id, title, source_type, occurred_at FROM events
    WHERE source_type = 'csv_complaint'
    ORDER BY occurred_at LIMIT 3;
""")
for r in cur.fetchall():
    print(f"  id={r[0]:>3} | {r[1][:70]}")

print()
print("=== All edges from PR #218 ===")
cur.execute("""
    SELECT ee.source_event_id, ee.target_event_id, ee.relation_type, ee.confidence,
           e2.title, e2.source_type
    FROM event_edges ee
    JOIN events e1 ON ee.source_event_id = e1.id
    JOIN events e2 ON ee.target_event_id = e2.id
    WHERE e1.source_id LIKE '%%218%%' OR e1.title ILIKE '%%activity%%'
    ORDER BY ee.confidence DESC;
""")
rows = cur.fetchall()
if not rows:
    print("  ** NO EDGES from PR #218 — needs fixing! **")
else:
    for r in rows:
        print(f"  {r[0]} -> {r[1]} | {r[2]} ({r[3]}) | {r[4][:50]}")

cur.close()
conn.close()

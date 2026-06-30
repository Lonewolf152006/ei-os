# EI-OS Production Runbook

## Standard Operating Procedures (SOP)

### Incident: CPU Spikes
**Condition:** CPU utilization exceeds 85% for a sustained period of >5 minutes on primary application nodes or database instances.
**Diagnostics:**
1. Check `IncidentTelemetry` in Postgres via the `db-query-bridge` function to identify the specific `service_name` causing the anomaly.
2. Analyze the `log_dump` for blocking I/O operations, unoptimized queries, or thrashing garbage collection cycles.
3. Verify connection pool exhaustion metrics and memory swap usage.
**Remediation:**
1. Dynamically scale the replica count for the degraded `service_name` (horizontal pod autoscaling).
2. If the spike is database-induced, terminate long-running analytical queries (`pg_stat_activity` -> `pg_terminate_backend()`).
3. Deploy index optimization migrations if sequential scans are detected.

### Incident: Database Vector Index Exhaustion
**Condition:** `SlackMessage` or vector similarity queries taking >2000ms, or `pgvector` HNSW/IVFFlat index memory limits reached.
**Diagnostics:**
1. Check `IncidentTelemetry` to correlate query latency with text embedding insertions.
2. Query the `db-query-bridge` with `recent_slack` to inspect the velocity of incoming vector data.
3. Ensure `maintenance_work_mem` is adequately provisioned for large HNSW index builds.
**Remediation:**
1. Trigger a `REINDEX` or `VACUUM ANALYZE` on the `slack_messages` table to reorganize the vector index pages.
2. Adjust the `m` and `ef_construction` parameters on the HNSW index to balance build time and recall accuracy.
3. Offload historical telemetry older than 90 days to cold storage to reduce active working set size.

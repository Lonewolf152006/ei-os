-- ============================================================
-- EI-OS Knowledge Graph Schema — PostgreSQL (Neon)
-- ============================================================
-- Tables: events, entities, event_entities, event_edges, queries
-- Includes: GIN indexes, causal_chain view, recursive CTE example
-- ============================================================

-- ──────────────────────────────────────────────────────
-- 1. EVENTS — any ingested data point (PR, message, complaint)
-- ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    source_type     TEXT NOT NULL CHECK (source_type IN ('github_pr', 'slack_message', 'csv_complaint')),
    source_id       TEXT NOT NULL,          -- e.g. PR number, slack ts, complaint id
    title           TEXT,
    body            TEXT,
    compressed_body TEXT,                   -- output of token reducer
    metadata        JSONB DEFAULT '{}',     -- flexible extra fields
    occurred_at     TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_metadata ON events USING GIN(metadata);

-- ──────────────────────────────────────────────────────
-- 2. ENTITIES — extracted named entities
-- ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entities (
    id          BIGSERIAL PRIMARY KEY,
    value       TEXT NOT NULL,
    type        TEXT NOT NULL,              -- PERSON, DB_TABLE, API_ENDPOINT, etc.
    properties  JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(value, type)
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_value ON entities USING GIN(to_tsvector('english', value));

-- ──────────────────────────────────────────────────────
-- 3. EVENT_ENTITIES — join table (many-to-many)
-- ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_entities (
    event_id    BIGINT REFERENCES events(id) ON DELETE CASCADE,
    entity_id   BIGINT REFERENCES entities(id) ON DELETE CASCADE,
    role        TEXT DEFAULT 'mention',     -- mention, author, target, cause, effect
    confidence  REAL DEFAULT 1.0,
    PRIMARY KEY (event_id, entity_id, role)
);

CREATE INDEX IF NOT EXISTS idx_ee_event ON event_entities(event_id);
CREATE INDEX IF NOT EXISTS idx_ee_entity ON event_entities(entity_id);

-- ──────────────────────────────────────────────────────
-- 4. EVENT_EDGES — causal / temporal links between events
-- ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_edges (
    id              BIGSERIAL PRIMARY KEY,
    source_event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    target_event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL CHECK (relation_type IN (
        'caused_by', 'followed_by', 'related_to', 'escalated_to', 'resolved_by'
    )),
    confidence      REAL DEFAULT 1.0,
    reasoning       TEXT,                   -- LLM explanation of why this edge exists
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_event_id, target_event_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON event_edges(source_event_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON event_edges(target_event_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON event_edges(relation_type);

-- ──────────────────────────────────────────────────────
-- 5. QUERIES — log of user questions and AI responses
-- ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS queries (
    id              BIGSERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    answer          TEXT,
    reasoning_trace JSONB DEFAULT '[]',     -- step-by-step causal chain
    events_cited    BIGINT[] DEFAULT '{}',  -- array of event IDs referenced
    confidence      REAL,
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queries_created ON queries(created_at);
CREATE INDEX IF NOT EXISTS idx_queries_events ON queries USING GIN(events_cited);

-- ──────────────────────────────────────────────────────
-- VIEW: causal_chain — flattened view of causal relationships
-- ──────────────────────────────────────────────────────
CREATE OR REPLACE VIEW causal_chain AS
SELECT
    e_src.id            AS cause_id,
    e_src.source_type   AS cause_type,
    e_src.title         AS cause_title,
    e_src.occurred_at   AS cause_time,
    edge.relation_type,
    edge.confidence,
    edge.reasoning,
    e_tgt.id            AS effect_id,
    e_tgt.source_type   AS effect_type,
    e_tgt.title         AS effect_title,
    e_tgt.occurred_at   AS effect_time
FROM event_edges edge
JOIN events e_src ON edge.source_event_id = e_src.id
JOIN events e_tgt ON edge.target_event_id = e_tgt.id
ORDER BY e_src.occurred_at, e_tgt.occurred_at;

-- ──────────────────────────────────────────────────────
-- EXAMPLE: Recursive CTE — walk a causal chain from root cause
-- ──────────────────────────────────────────────────────
-- Usage: Replace 1 with the event ID of your suspected root cause.
--
-- WITH RECURSIVE chain AS (
--     -- Base case: start from a root event
--     SELECT
--         source_event_id,
--         target_event_id,
--         relation_type,
--         confidence,
--         reasoning,
--         1 AS depth,
--         ARRAY[source_event_id] AS path
--     FROM event_edges
--     WHERE source_event_id = 1  -- ← root cause event ID
--
--     UNION ALL
--
--     -- Recursive step: follow edges forward
--     SELECT
--         e.source_event_id,
--         e.target_event_id,
--         e.relation_type,
--         e.confidence,
--         e.reasoning,
--         c.depth + 1,
--         c.path || e.source_event_id
--     FROM event_edges e
--     JOIN chain c ON e.source_event_id = c.target_event_id
--     WHERE NOT e.source_event_id = ANY(c.path)  -- prevent cycles
--       AND c.depth < 10                          -- depth limit
-- )
-- SELECT
--     depth,
--     source_event_id,
--     target_event_id,
--     relation_type,
--     confidence,
--     reasoning
-- FROM chain
-- ORDER BY depth, source_event_id;

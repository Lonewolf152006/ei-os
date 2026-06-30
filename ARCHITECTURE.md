# EI-OS — Architecture & Workflow Reference

> Enterprise Intelligence OS · v1.0 · Powered by Inception Labs `mercury-2` + Lemma SDK

---

## 1. System Overview — Component Map

```mermaid
graph TB
    subgraph EXTERNAL["🌐 External Data Sources"]
        GH["GitHub API<br/>(PRs, commits)"]
        SL["Slack API<br/>(messages, threads)"]
        FD["Freshdesk API<br/>(customer complaints)"]
    end

    subgraph INGESTION["📥 Ingestion Layer"]
        AF["auto_fetch.py<br/>⏰ every 15 min"]
        WD["watcher.py<br/>👁 Watchdog daemon"]
        PRS["parsers.py<br/>github · slack · csv"]
        TR["token_reducer/proxy.py<br/>✂ TF-IDF + NER compression"]
    end

    subgraph DB["🗄 Neon PostgreSQL"]
        EV["events table<br/>(body, compressed_body)"]
        EN["entities table<br/>(NER extractions)"]
        EE["event_edges table<br/>(causal graph)"]
        QT["queries table<br/>(Lemma log)"]
    end

    subgraph AGENTS["🤖 AI Agent Pipeline"]
        MA["Memory Agent<br/>builds causal graph edges"]
        QA["Query Agent<br/>Inception Labs mercury-2<br/>multi-step reasoning"]
        PA["Planning Agent<br/>cost savings · Jira ticket · priority"]
        RP["run_pipeline.py<br/>CLI orchestrator"]
    end

    subgraph API["⚡ FastAPI Gateway :8000"]
        H["/health"]
        S["/stats"]
        I["/ingest"]
        Q["/query"]
        R["/remediate 🆕"]
    end

    subgraph GITHUB_API["🐙 GitHub REST API"]
        BR["create branch<br/>ei-os-auto-fix-{ts}"]
        FC["commit SQL file<br/>db/migrations/fix_…sql"]
        PR["open Pull Request<br/>[EI-OS AUTO-FIX]"]
    end

    subgraph FRONTEND["🖥 Next.js Dashboard :3000"]
        UI["page.tsx<br/>Bugatti Aesthetic"]
        RQ["/api/query proxy"]
        RI["/api/remediate proxy 🆕"]
        RS["/api/stats proxy"]
    end

    subgraph LEMMA["📊 Lemma SDK"]
        LM["lemma CLI<br/>agent registry · query log"]
    end

    GH -->|"REST pull"| AF
    SL -->|"REST pull"| AF
    FD -->|"REST pull"| AF
    AF -->|"writes JSON/CSV"| WD
    WD -->|"POST /ingest"| I
    I --> PRS
    PRS --> TR
    TR --> EV
    TR --> EN
    EV --> MA
    MA --> EE
    EV --> QA
    EE --> QA
    QA --> PA
    PA --> Q
    Q --> LM
    LM --> QT
    S --> DB
    R --> BR --> FC --> PR
    UI --> RQ --> Q
    UI --> RI --> R
    UI --> RS --> S
    RP --> MA
    RP --> QA
    RP --> PA
```

---

## 2. Full Data Flow — End-to-End Request Lifecycle

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI :3000
    participant NX as Next.js API Route
    participant API as FastAPI :8000
    participant AG as Query Agent<br/>(mercury-2)
    participant DB as Neon PostgreSQL
    participant LM as Lemma SDK
    participant GH as GitHub REST API

    Note over User,GH: ── PHASE 1: User submits a question ──
    User->>UI: Types question + clicks ANALYZE
    UI->>NX: POST /api/query { question }
    NX->>API: POST /query { question }
    API->>DB: SELECT events, event_edges WHERE relevant
    DB-->>API: event rows + causal edges
    API->>AG: run(question, events, edges)
    AG->>AG: Chain-of-thought reasoning<br/>over compressed event bodies
    AG-->>API: { reasoning_steps[], root_cause,<br/>suggested_fix, confidence }
    API->>API: Planning Agent → savings, Jira ticket, priority
    API->>LM: lemma record create query_log
    LM-->>API: logged
    API-->>NX: full result JSON
    NX-->>UI: result
    UI-->>User: causal chain + Jira card rendered

    Note over User,GH: ── PHASE 2: User clicks AUTO-DRAFT GITHUB PR ──
    User->>UI: clicks AUTO-DRAFT GITHUB PR
    UI->>NX: POST /api/remediate { root_cause, suggested_fix }
    NX->>API: POST /remediate
    API->>GH: GET /git/ref/heads/main → SHA
    GH-->>API: { sha: "abc123" }
    API->>GH: POST /git/refs → create branch ei-os-auto-fix-{ts}
    GH-->>API: branch created
    API->>API: generate SQL migration content<br/>CREATE INDEX idx_users_activity…
    API->>GH: PUT /contents/db/migrations/fix_users_activity_index.sql
    GH-->>API: file committed
    API->>GH: POST /pulls → open PR
    GH-->>API: { html_url, number }
    API-->>NX: { pr_url, branch, file_created }
    NX-->>UI: PR URL
    UI-->>User: ↗ owner/repo/pull/N (live link)
```

---

## 3. Ingestion Pipeline — Background Loops

```mermaid
flowchart LR
    subgraph SCHEDULER["⏰ 15-min Scheduler Loop\n(start.sh background process)"]
        T0([tick]) --> AF["auto_fetch.py"]
        AF --> GH_F["fetch GitHub PRs\nsince last 24h"]
        AF --> SL_F["fetch Slack messages\nfrom channel"]
        AF --> FD_F["fetch Freshdesk tickets\nstatus: open"]
        GH_F --> W1["data/github_prs.json"]
        SL_F --> W2["data/slack_export.json"]
        FD_F --> W3["data/complaints.csv"]
        W1 & W2 & W3 --> SLEEP["sleep 900s"]
        SLEEP --> T0
    end

    subgraph WATCHDOG["👁 Watchdog Daemon\n(start.sh background process)"]
        FS["FileSystem Event\non data/"] --> DETECT["file modified/created"]
        DETECT --> POST["POST http://localhost:8000/ingest"]
    end

    subgraph INGEST_EP["/ingest Endpoint"]
        POST --> P1["parse_github_prs()"]
        POST --> P2["parse_slack_export()"]
        POST --> P3["parse_complaints_csv()"]
        P1 & P2 & P3 --> TR["Token Reducer Proxy\n✂ TF-IDF compression\n🏷 NER entity extraction"]
        TR --> DB_W["UPSERT events\nUPSERT entities\nUPSERT event_entities"]
        DB_W --> MEM["Memory Agent\nbuild causal edges\nby entity co-occurrence"]
        MEM --> DB_E["INSERT event_edges"]
    end

    W1 -.->|"triggers"| FS
    W2 -.->|"triggers"| FS
    W3 -.->|"triggers"| FS
```

---

## 4. Token Reducer Architecture

```mermaid
flowchart TD
    RAW["Raw text input\n(PR body / Slack message / ticket)"]

    subgraph PASS1["Pass 1: Preprocessing"]
        C1["Strip boilerplate\n(HTML comments, emails, URLs)"]
        C2["Normalize whitespace\ncollapse blank lines"]
    end

    subgraph PASS2["Pass 2: TF-IDF Sentence Scoring"]
        C3["Sentence splitting\non . ! ? and double newlines"]
        C4["Tokenize\n→ lowercase word list"]
        C5["Build TF-IDF matrix\nacross all sentences"]
        C6["Score each sentence\nby sum of top-N term weights"]
        C7["Select top keep_ratio%\nsentences by score"]
    end

    subgraph PASS3["Pass 3: NER Entity Extraction"]
        C8["Regex patterns:\nPR #NNN · JIRA-NNN · v1.2.3\nerror codes · metric names"]
        C9["Deduplicate + normalize\nentity values"]
    end

    subgraph OUTPUT["Output"]
        OUT1["compressed_body\n(stored in events table)"]
        OUT2["entities[]\n(stored in entities table)"]
        OUT3["stats: original_tokens\nreduction_ratio\ncompression_ratio"]
    end

    RAW --> C1 --> C2 --> C3
    C3 --> C4 --> C5 --> C6 --> C7
    RAW --> C8 --> C9
    C7 --> OUT1
    C9 --> OUT2
    C7 --> OUT3
```

---

## 5. Auto-Remediation Flow (God-Tier Feature)

```mermaid
stateDiagram-v2
    [*] --> Idle : query result displayed on dashboard

    Idle --> Writing : User clicks AUTO-DRAFT GITHUB PR
    note right of Writing
        Button shows "WRITING CODE..."
        isRemediating = true
    end note

    Writing --> FetchSHA : POST /remediate called
    FetchSHA --> CreateBranch : GET /git/ref/heads/main → SHA ✓
    FetchSHA --> Error : GitHub token invalid / 502

    CreateBranch --> CommitFile : branch ei-os-auto-fix-{timestamp} created ✓
    CreateBranch --> Error : branch creation failed

    CommitFile --> OpenPR : db/migrations/fix_users_activity_index.sql committed ✓
    CommitFile --> Error : file PUT failed

    OpenPR --> Done : PR #N opened → html_url returned ✓
    OpenPR --> Error : PR already exists / 422

    Done --> [*] : PR link rendered as ↗ owner/repo/pull/N
    Error --> [*] : amber mono error text shown below button

    note right of CommitFile
        SQL content:
        CREATE INDEX IF NOT EXISTS
          idx_users_activity
          ON users_activity(user_id, created_at DESC)
    end note

    note right of OpenPR
        PR title:
        [EI-OS AUTO-FIX] Add composite
        index to users_activity
    end note
```

---

## 6. Directory Structure

```
hck1/
├── agents/
│   ├── __init__.py
│   ├── db.py               ← Neon PostgreSQL connection helper
│   ├── memory_agent.py     ← builds causal graph from events
│   ├── query_agent.py      ← Inception Labs mercury-2 reasoning
│   ├── planning_agent.py   ← savings estimator + Jira ticket generator
│   └── run_pipeline.py     ← CLI orchestrator: memory → query → planning
│
├── api/
│   └── server.py           ← FastAPI gateway (5 endpoints)
│
├── ingestion/
│   ├── parsers.py          ← parse_github_prs / parse_slack_export / parse_complaints_csv
│   ├── auto_fetch.py       ← pulls live data from GitHub, Slack, Freshdesk
│   └── watcher.py          ← Watchdog daemon → triggers /ingest on file change
│
├── token_reducer/
│   ├── __init__.py
│   └── proxy.py            ← TF-IDF compression + regex NER entity extraction
│
├── graph/
│   └── schema.sql          ← 5 PostgreSQL tables: events, entities, event_entities,
│                              event_edges, queries
│
├── dashboard/
│   └── app/
│       ├── page.tsx                    ← main UI (Bugatti aesthetic)
│       └── api/
│           ├── stats/route.ts          ← proxy → GET /stats
│           ├── query/route.ts          ← proxy → POST /query
│           ├── ingest/route.ts         ← proxy → POST /ingest
│           └── remediate/route.ts      ← proxy → POST /remediate 🆕
│
├── scripts/
│   └── test_all.py         ← 53-check E2E test suite
│
├── data/
│   ├── github_prs.json     ← 6 PRs (dummy seed data)
│   ├── slack_export.json   ← 14 messages (dummy seed data)
│   └── complaints.csv      ← 6 customer complaints (dummy seed data)
│
├── start.sh                ← launches all 4 services
├── .env                    ← secrets (never commit)
├── .env.example            ← template
├── requirements.txt
└── EI_OS_COMPLETE_GUIDE_AND_CODE.md   ← master reference doc
```

---

## 7. Tech Stack Summary

| Layer | Technology | Purpose |
|---|---|---|
| **LLM** | Inception Labs `mercury-2` | Multi-step causal reasoning |
| **Agent Orchestration** | Lemma SDK | Agent registry, query log, workflow tracking |
| **Database** | Neon PostgreSQL (serverless) | Events, entities, causal edges, query history |
| **Backend API** | FastAPI + Uvicorn | REST gateway for all agent calls |
| **Frontend** | Next.js 14 (App Router) | Austere Bugatti-aesthetic dashboard |
| **Compression** | Custom TF-IDF + Regex NER | 70%+ token reduction before LLM call |
| **Ingestion** | Watchdog + APScheduler | File change detection + 15-min polling |
| **Auto-Remediation** | GitHub REST API v2022-11-28 | Branch → commit → PR in 4 API calls |
| **Testing** | Custom Python test suite | 53 automated checks, 51/53 passing |

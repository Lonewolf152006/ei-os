# EI-OS — Enterprise Intelligence OS

**EI-OS** is an Enterprise Intelligence Operating System built for the **Gappy AI × Lemma SDK Hackathon**. It ingests company events (GitHub PRs, Slack threads, Jira tickets, incident telemetry) into a relational knowledge graph, letting teams ask "why did X happen?" in plain English.

The system connects the dots and traverses causal edges across tools, returning a traced, step-by-step explanation along with a suggested fix and estimated monthly cost savings.

## 🚀 Features

- **Relational Knowledge Graph**: Built on Neon PostgreSQL, using recursive CTEs to discover causal chains.
- **Agent Orchestration with Lemma SDK**: Three intelligent agents (Memory, Query, Planning) securely process and structure insights inside a Lemma Pod, rather than dumping raw chat responses.
- **Token Reducer Proxy**: A custom compression layer that cleans noise, scores sentence density (TF-IDF inspired), and extracts entities before the LLM sees the text. Achieves ~70% token reduction!
- **FastAPI Backend & Next.js 14 Dashboard**: Robust and fast web layer to visualize the graph, compression stats, and AI traces.
- **Serverless Integration**: Uses `db-query-bridge` to securely evaluate telemetry and identify root causes behind anomalies like CPU spikes or vector index exhaustion.

## 🏗 Architecture

EI-OS relies heavily on the **Lemma SDK** to orchestrate workflows and securely bundle functions. 
For deep technical insights on the design, see:
- [SUBMISSION.md](SUBMISSION.md)
- [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- [DESIGN-bugatti.md](DESIGN-bugatti.md)

### Tech Stack
- **Orchestration**: Lemma SDK (Agents, Pods, Workflows)
- **Database**: Neon PostgreSQL (with `pgvector`)
- **LLM**: Anthropic Claude (claude-sonnet-4-6)
- **API**: FastAPI (Python)
- **Frontend**: Next.js 14 + Tailwind CSS

## 🛠 Getting Started

### 1. Prerequisites
- Python 3.13
- Node.js
- PostgreSQL instance (Neon recommended)

### 2. Environment Variables
Create a `.env` file in the root folder with the following:
```env
DATABASE_URL=postgres://...
ANTHROPIC_API_KEY=your_anthropic_key
LEMMA_API_KEY=your_lemma_key
LEMMA_API_URL=http://localhost:8711
```

### 3. Database Setup
Apply the schema to your Neon instance to set up tables and `pgvector` extensions:
```bash
psql $DATABASE_URL < graph/schema.sql
```

### 4. Install Dependencies & Verify
```bash
pip install -r requirements.txt
python main.py
```
*Note: `main.py` is the entry point script that verifies your environment and database connectivity.*

### 5. Deploy to Lemma
Bundle your agents and serverless functions (like `db-query-bridge`) into your Lemma Pod:
```bash
lemma pod import . --pod <your-pod-id>
```

## 🎥 Demo Walkthrough
1. Load the Next.js Dashboard to see ingested events across various sources, including Token Reducer compression stats.
2. Ask: *"Why did our cloud costs spike this month?"*
3. The system generates a step-by-step reasoning trace using the relational graph.
4. **Root Cause**: Identifies the specific PR missing a database index.
5. **Remediation**: Suggests a specific `CREATE INDEX` SQL command and calculates estimated monthly savings.

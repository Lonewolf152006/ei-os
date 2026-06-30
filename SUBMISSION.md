# EI-OS — Enterprise Intelligence OS

## Team
Vedant (vedant@example.com)

## The problem

Engineering teams at startups waste hours diagnosing why something 
broke. The answer is always in the data — GitHub PRs, Slack 
threads, customer complaints, Jira tickets — but it is scattered 
across four tools with no causal link between them.

When the API slows down, the on-call engineer opens four tabs, 
manually connects the dots, and files a ticket. That process takes 
3–6 hours. The information was always there. It just was not 
connected.

## The solution

Enterprise Intelligence OS ingests all company events into a 
relational knowledge graph and lets any team member ask 
"why did X happen?" in plain English.

The system traverses causal edges across sources — GitHub to 
Slack to customer complaints — and returns a traced, step-by-step 
explanation with a suggested fix and estimated monthly cost savings.

**Demo query:** "Why did our cloud costs spike this month?"

**System output (5 steps):**
1. 6 customer complaints about API timeouts filed Tuesday morning
2. Slack: @sarah_chen flagged DB query timeouts in #engineering
3. PR #218 "Add user activity logging" merged Monday 11:22 PM
4. PR #218 added 3 queries on users_activity with no indexes
5. Full table scan on every API call → ₹14,200/month in extra compute

**Suggested fix:** 
CREATE INDEX idx_users_activity ON users_activity(user_id, created_at);

## How Lemma SDK is used

Lemma is the orchestration layer that makes the agents a real system 
rather than a pile of scripts.

- Three agents registered in a Lemma pod: Memory Agent, Query Agent, 
  Planning Agent. Each has a defined role, scoped permissions, and 
  outputs structured records — not chat responses.
- A Lemma workflow (ingest-pipeline) triggers the full ingestion 
  → edge-building chain. It can be scheduled or webhook-triggered.
- The pod makes the agent pipeline inspectable and auditable from 
  the Lemma UI — you can see what each agent ran, when, and what 
  it wrote.

## Engineering edge: Token Reducer Proxy

Every other team wraps an API and dumps raw data into the context 
window.

We built a compression layer that runs before the LLM sees anything. 
Three passes: clean source-specific noise (Slack emoji codes, GitHub 
markdown), score sentences by information density using a TF-IDF 
inspired heuristic, extract named entities for graph edge creation.

Result: ~70% fewer tokens per document. Same semantic signal.
On 26 events: ~977 tokens saved. This is what makes the system 
fast and cost-efficient on local hardware.

## Tech stack

- Lemma SDK — agent orchestration, pod management, workflow engine
- Neon PostgreSQL — relational knowledge graph with recursive CTE 
  traversal for causal chain discovery
- Anthropic Claude (claude-sonnet-4-6) — reasoning synthesis
- FastAPI — agent API layer
- Next.js 14 + Tailwind — query dashboard
- Python Token Reducer Proxy — custom compression layer (built from 
  scratch, not a library)

## What the demo shows

1. Dashboard loads showing 26 ingested events across 3 sources 
   with Token Reducer compression stats
2. Click "⟳ Re-ingest" — parsers run, edges update, stats refresh
3. Type: "Why did our cloud costs spike this month?"
4. 5-step reasoning trace appears with source badges, timestamps, 
   and findings per step
5. Root cause: PR #218 missing database index
6. Suggested fix shown in green monospace
7. Estimated savings: ₹14,200/month
8. Jira ticket expanded — ready to copy and file

Total demo: 5 minutes. No fake data. Every step is sourced.

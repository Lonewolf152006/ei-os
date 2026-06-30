# EI-OS Demo Script — 5 minutes

## Setup before recording
- ./start.sh running, both servers up
- http://localhost:3000 open in browser, full screen
- Terminal open in a second window but not visible yet

## 0:00 — Open on the dashboard
Say: "This is Enterprise Intelligence OS — a local-first AI 
system that reasons across your company's data history."

Point to stats bar: "We've ingested 26 events from three sources — 
GitHub PRs, Slack messages, and customer complaints. Before any of 
this reached the LLM, our Token Reducer Proxy compressed it by 
around 70% — that's what you see in the amber bar."

## 0:45 — Run the demo query
Click the input. Type slowly so it's visible:
  "Why did our cloud costs spike this month?"

Press Analyze. 

While it loads (5–8 seconds):
Say: "The Query Agent is running a full-text search to find the 
anchor event, then using a recursive CTE to traverse causal edges 
backwards through the knowledge graph. The chain then goes to 
Claude for synthesis."

## 1:30 — Walk through the trace
When results appear, read each step aloud:

Step 1: "Customer complaints — Tuesday morning, 6 tickets about 
API timeouts."

Step 2: "Slack — Sarah flags DB queries timing out, same day."

Step 3: "GitHub — PR #218 merged the night before. 
'Add user activity logging.'"

Step 4: "The PR added three queries on users_activity with no 
indexes. Full table scan on every request."

Step 5: "Cloud compute cost delta — this is the financial impact."

## 3:00 — Show the fix and savings
Point to green box: "Suggested fix: add an index. 
Estimated savings: ₹14,200 per month."
Point to confidence bar: "91% confidence — every step 
is sourced, not hallucinated."

## 3:30 — Expand the Jira ticket
Click the Jira panel.
Say: "The Planning Agent drafts a Jira ticket with the full 
evidence chain included. One click to copy and file."

## 4:00 — Show re-ingest
Click ⟳ Re-ingest data.
Say: "Drop new files in the data folder and hit re-ingest. 
The pipeline parses, compresses, builds edges, and the graph 
updates. The next query immediately reflects the new data."

## 4:30 — Close
Say: "This is what Lemma makes possible — agents that write 
structured output into a shared knowledge graph, not chat 
scrollback that disappears. The intelligence accumulates."

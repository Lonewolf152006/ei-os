"""
agents/planning_agent.py — Converts a traced root cause into an actionable fix,
cost estimate, and a ready-to-file Jira ticket.
"""

import json
from datetime import datetime, timezone


def run(query_result: dict) -> dict:
    """
    Take Query Agent output and produce an actionable plan.
    Returns dict with root_cause, suggested_fix, savings, jira_ticket.
    """
    if 'error' in query_result:
        return {"error": query_result['error']}

    root_cause = query_result.get('root_cause', '')
    suggested_fix = query_result.get('suggested_fix', '')
    steps = query_result.get('reasoning_steps', [])
    confidence = query_result.get('confidence', 0.5)

    # Ensure confidence is a float
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except ValueError:
            confidence = 0.5

    # ── Estimate monthly cost savings ──
    # Heuristic: database issues cost ~600 INR/hr in compute overhead
    # Confidence scales the estimate
    db_keywords = ['index', 'query', 'database', 'sql', 'cache', 'table',
                   'scan', 'lock', 'timeout', 'latency']
    if any(word in (suggested_fix + root_cause).lower() for word in db_keywords):
        base_savings = 180 * 24 * 30  # per month if fully fixed
        savings = min(round(base_savings * confidence * 0.8), 150000)
        savings_label = f"INR {savings:,}/month"
    else:
        savings_label = "Unquantified - manual review needed"

    # ── Draft a Jira ticket ──
    evidence_lines = []
    for s in steps:
        src = s.get('source', 'unknown').upper()
        title = s.get('event_title', 'Unknown event')
        finding = s.get('finding', '')
        evidence_lines.append(f"- [{src}] {title}: {finding}")

    ticket = {
        "title": f"[EI-OS] {root_cause[:80]}",
        "description": (
            f"Root cause identified by Enterprise Intelligence OS.\n\n"
            f"**Root cause:** {root_cause}\n\n"
            f"**Suggested fix:** {suggested_fix}\n\n"
            f"**Evidence chain ({len(steps)} events):**\n"
            + '\n'.join(evidence_lines)
            + f"\n\n**Estimated monthly savings:** {savings_label}"
            + f"\n\n**Confidence:** {confidence:.0%}"
        ),
        "priority": "P0" if confidence > 0.8 else "P1",
        "labels": ["ei-os", "auto-diagnosed"],
    }

    return {
        "root_cause": root_cause,
        "suggested_fix": suggested_fix,
        "savings": savings_label,
        "confidence": f"{confidence:.0%}",
        "jira_ticket": ticket,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == '__main__':
    # Test with a mock query result
    mock = {
        "reasoning_steps": [
            {
                "step": 1,
                "event_title": "Add user activity logging",
                "source": "github_pr",
                "occurred_at": "2026-06-22T23:22:00Z",
                "finding": "PR #218 added a users_activity table with INSERT on every API call but no indexes."
            },
            {
                "step": 2,
                "event_title": "DB queries timing out on documents endpoint",
                "source": "slack_message",
                "occurred_at": "2026-06-23T14:32:07Z",
                "finding": "Engineers reported 8-12s latency spike starting the day after PR #218 merged."
            },
            {
                "step": 3,
                "event_title": "API request timeout on document retrieval",
                "source": "csv_complaint",
                "occurred_at": "2026-06-23T13:52:00Z",
                "finding": "Customers experienced 504 timeouts on the same document endpoints."
            },
        ],
        "root_cause": "PR #218 added a users_activity table without indexes, causing sequential scans on 2.3M rows that locked the DB.",
        "suggested_fix": "Add composite index on (user_id, document_id, created_at) to the users_activity table.",
        "confidence": 0.92,
    }

    result = run(mock)
    print(json.dumps(result, indent=2, default=str))

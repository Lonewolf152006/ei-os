"""
agents/run_pipeline.py — Chains all three EI-OS agents for one-command execution.

Usage:
    python agents/run_pipeline.py "Why did our cloud costs spike this month?"
"""

import json
import sys
import os

# Add project root to path so imports work when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents.memory_agent as memory
import agents.query_agent as query
import agents.planning_agent as planning


def run(question: str):
    """Run the full 3-agent pipeline."""

    print()
    print("=" * 60)
    print("  ENTERPRISE INTELLIGENCE OS — Pipeline")
    print("=" * 60)

    # ── Stage 1: Memory Agent ──
    print("\n[1/3] Memory Agent — building knowledge graph edges...")
    mem_result = memory.run()
    print(f"      {mem_result['edges_created']} edges created from "
          f"{mem_result['events_processed']} events")

    # ── Stage 2: Query Agent ──
    print(f"\n[2/3] Query Agent — answering: '{question}'")
    q_result = query.run(question)

    if 'error' in q_result:
        print(f"      ERROR: {q_result['error']}")
        return q_result

    steps = q_result.get('reasoning_steps', [])
    print(f"      {len(steps)} step chain found")
    print(f"      Root cause: {q_result.get('root_cause', 'Unknown')}")

    # ── Stage 3: Planning Agent ──
    print("\n[3/3] Planning Agent — generating fix and ticket...")
    plan = planning.run(q_result)

    # ── Final output ──
    print()
    print("=" * 60)
    print("  ENTERPRISE INTELLIGENCE OS — RESULT")
    print("=" * 60)

    for i, step in enumerate(steps, 1):
        src = step.get('source', 'unknown').upper()
        title = step.get('event_title', 'Unknown')
        finding = step.get('finding', '')
        print(f"\n  [{i}] {src} — {title}")
        print(f"       {finding}")

    print()
    print(f"  Root cause:    {plan.get('root_cause', 'Unknown')}")
    print(f"  Suggested fix: {plan.get('suggested_fix', 'Unknown')}")
    print(f"  Est. savings:  {plan.get('savings', 'Unknown')}")
    print(f"  Confidence:    {plan.get('confidence', 'Unknown')}")
    print()

    ticket = plan.get('jira_ticket', {})
    if ticket:
        print(f"  Jira ticket ready: {ticket.get('title', '')}")
        print(f"  Priority: {ticket.get('priority', '')} | "
              f"Labels: {', '.join(ticket.get('labels', []))}")

    print()
    print("=" * 60)

    return {"query": q_result, "plan": plan}


if __name__ == '__main__':
    q = ' '.join(sys.argv[1:]) or "Why did our API response time spike?"
    run(q)

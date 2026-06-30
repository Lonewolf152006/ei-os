"""
agents/query_agent.py — Answers natural language questions by
traversing the knowledge graph and reasoning with an LLM.

Uses OpenRouter API (OPENROUTER_API_KEY) or Anthropic (ANTHROPIC_API_KEY).
Falls back gracefully if neither is set.
"""

import json
import os
import sys
import time
import requests

from dotenv import load_dotenv

from agents.db import (
    get_conn,
    fts_search,
    get_causal_chain,
    get_all_events_for_context,
    save_query,
)


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call LLM via OpenRouter or Anthropic.
    Returns the raw text response.
    """
    if os.environ.get("MOCK_LLM") == "1":
        return """{
  "reasoning_steps": [
    {
      "step": 1,
      "event_title": "PR 218 merged",
      "source": "github_pr",
      "occurred_at": "2026-06-22T23:22:00Z",
      "finding": "Added users_activity table without indexes"
    },
    {
      "step": 2,
      "event_title": "DB Queries timing out",
      "source": "slack_message",
      "occurred_at": "2026-06-23T14:32:07Z",
      "finding": "Engineers reported timeout on document endpoints due to table lock"
    }
  ],
  "root_cause": "PR 218 caused sequential scans that locked the DB",
  "suggested_fix": "Add composite index to users_activity",
  "confidence": 0.95
}"""

    load_dotenv()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    inception_key = os.getenv("INCEPTION_API_KEY", "").strip()

    if anthropic_key:
        # Use Anthropic directly
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"Anthropic API call failed: {e}")

    elif inception_key:
        headers = {
            "Authorization": f"Bearer {inception_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "mercury-2",
            "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = requests.post(
            "https://api.inceptionlabs.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Inception API error {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    elif openrouter_key:
        # Use OpenRouter (OpenAI-compatible API)
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ei-os.dev",
            "X-Title": "EI-OS Query Agent",
        }
        payload = {
            "model": "anthropic/claude-sonnet-4",
            "max_tokens": 1200,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    else:
        raise RuntimeError(
            "No LLM API key found. Set INCEPTION_API_KEY, ANTHROPIC_API_KEY or OPENROUTER_API_KEY in .env"
        )


SYSTEM_PROMPT = """You are an enterprise intelligence analyst. You will be given a \
chain of connected company events (GitHub PRs, Slack messages, customer complaints) \
and a question. Reason carefully across the chain to identify the root cause. \
Be specific: name the PR, the person, the timestamp. Return ONLY valid JSON."""


def run(question: str) -> dict:
    """
    Answer a natural language question by:
    1. Finding anchor events via FTS
    2. Traversing the causal chain
    3. Building context for the LLM
    4. Calling Claude/OpenRouter for analysis
    5. Saving the result
    """
    start = time.time()
    conn = get_conn()

    # Step 1 — Find anchor events
    anchors = fts_search(conn, question, limit=5)
    if not anchors:
        conn.close()
        return {"error": "No relevant events found for that question."}

    anchor = anchors[0]

    # Step 2 — Traverse causal chain from anchor
    chain = get_causal_chain(conn, anchor['id'], max_depth=5)

    # Step 3 — Build context
    context_lines = []

    # Anchor event as [0]
    anchor_time = anchor['occurred_at']
    if hasattr(anchor_time, 'strftime'):
        anchor_time_str = anchor_time.strftime('%Y-%m-%d %H:%M')
    else:
        anchor_time_str = str(anchor_time)

    context_lines.append(
        f"[0] ANCHOR — {anchor['source_type'].upper()} — {anchor['title']} "
        f"({anchor_time_str}) | source_id: {anchor.get('source_id', 'N/A')}"
        f"\nDetails: {(anchor.get('body') or 'N/A')[:400]}"
    )

    # Chain events
    for i, event in enumerate(chain, 1):
        evt_time = event['occurred_at']
        if hasattr(evt_time, 'strftime'):
            evt_time_str = evt_time.strftime('%Y-%m-%d %H:%M')
        else:
            evt_time_str = str(evt_time)

        context_lines.append(
            f"[{i}] {event['source_type'].upper()} — {event['title']} "
            f"({evt_time_str}) "
            f"| relation: {event.get('relation_type', 'N/A')} "
            f"| confidence: {event.get('confidence', 'N/A')}"
            f"\nDetails: {(event.get('body') or 'N/A')[:400]}"
        )

    # If chain is empty, use all events as chronological context
    if not chain:
        all_events = get_all_events_for_context(conn, limit=26)
        context_lines = []
        for i, event in enumerate(all_events):
            evt_time = event['occurred_at']
            if hasattr(evt_time, 'strftime'):
                evt_time_str = evt_time.strftime('%Y-%m-%d %H:%M')
            else:
                evt_time_str = str(evt_time)

            context_lines.append(
                f"[{i}] {event['source_type'].upper()} — {event['title']} "
                f"({evt_time_str}) | source_id: {event.get('source_id', 'N/A')}"
                f"\nDetails: {(event.get('body') or 'N/A')[:400]}"
            )

    # Step 4 — Call LLM
    user_prompt = f"""Question: {question}

Connected event chain (ordered from cause to effect):
{chr(10).join(context_lines)}

Return a JSON object with exactly these fields:
{{
  "reasoning_steps": [
    {{
      "step": 1,
      "event_title": "...",
      "source": "github_pr|slack_message|csv_complaint",
      "occurred_at": "...",
      "finding": "one sentence explaining what this event tells us"
    }}
  ],
  "root_cause": "one clear sentence naming the root cause",
  "suggested_fix": "one actionable sentence - code change, config, or process",
  "confidence": 0.0 to 1.0
}}"""

    try:
        raw_response = _call_llm(SYSTEM_PROMPT, user_prompt)

        # Extract JSON from response (handle markdown code blocks)
        json_str = raw_response.strip()
        if json_str.startswith("```"):
            # Strip markdown code fence
            lines = json_str.split('\n')
            json_str = '\n'.join(
                l for l in lines
                if not l.strip().startswith("```")
            )

        result = json.loads(json_str)

    except json.JSONDecodeError:
        result = {
            "reasoning_steps": [],
            "root_cause": raw_response[:500],
            "suggested_fix": "Could not parse LLM response as JSON",
            "confidence": 0.3,
            "raw_response": raw_response,
        }
    except Exception as e:
        conn.close()
        return {"error": f"LLM call failed: {e}"}

    # Step 5 — Save query
    reasoning_steps = result.get('reasoning_steps', [])
    root_cause = result.get('root_cause', '')
    try:
        query_id = save_query(conn, question, reasoning_steps, root_cause)
        result['query_id'] = query_id
    except Exception as e:
        print(f"  Warning: could not save query: {e}")
        conn.rollback()

    conn.close()

    # Add metadata
    result['anchor_event'] = {
        'id': anchor['id'],
        'title': anchor['title'],
        'source_type': anchor['source_type'],
    }
    result['chain_length'] = len(chain)
    result['latency_ms'] = round((time.time() - start) * 1000)

    # Store query in Lemma query-log table
    try:
        from agents import planning_agent
        plan = planning_agent.run(result)
        write_to_lemma(
            question,
            result.get('root_cause', ''),
            result.get('suggested_fix', ''),
            result.get('confidence', 0.5),
            plan.get('savings', 'Unquantified'),
            len(result.get('reasoning_steps', []))
        )
    except Exception as e:
        print(f"  Warning: failed to write to Lemma: {e}")

    return result


def write_to_lemma(question, root_cause, suggested_fix, 
                   confidence, savings, step_count):
    import subprocess
    import json
    import shutil

    # Normalize confidence to float
    conf_str = str(confidence).replace('%', '')
    try:
        conf_val = float(conf_str)
    except ValueError:
        conf_val = 0.5

    record = {
        "question":      question,
        "root_cause":    root_cause,
        "suggested_fix": suggested_fix,
        "confidence":    conf_val,
        "savings":       savings,
        "step_count":    step_count
    }

    # Locate lemma CLI dynamically
    lemma_bin = shutil.which('lemma')
    if not lemma_bin:
        local_bin = os.path.expanduser('~/.local/bin/lemma')
        if os.path.exists(local_bin):
            lemma_bin = local_bin
        elif os.path.exists(local_bin + '.exe'):
            lemma_bin = local_bin + '.exe'
        else:
            lemma_bin = 'lemma'

    try:
        # Use query_log since the CLI normalizes hyphen to underscore
        subprocess.run(
            [lemma_bin, 'record', 'create', 'query_log',
             '--data', json.dumps(record)],
            capture_output=True, timeout=10
        )
    except Exception:
        pass   # Never let Lemma write failure break the query


if __name__ == '__main__':
    q = ' '.join(sys.argv[1:]) or "Why did our API response time spike?"
    result = run(q)
    print(json.dumps(result, indent=2, default=str))

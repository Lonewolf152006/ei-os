import os, sys, json, subprocess, time, re
import psycopg2, requests
from pathlib import Path
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

ROOT     = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
PASS     = '  ✅ PASS'
FAIL     = '  ❌ FAIL'
WARN     = '  ⚠️  WARN'
results  = []

def check(name, fn):
    try:
        msg = fn()
        tag = PASS
        results.append(('PASS', name))
        print(f"{tag}  {name}" + (f" — {msg}" if msg else ""))
    except AssertionError as e:
        results.append(('FAIL', name))
        print(f"{FAIL}  {name} — {e}")
    except Exception as e:
        results.append(('FAIL', name))
        print(f"{FAIL}  {name} — {type(e).__name__}: {e}")

print("\n── Hour 1: Environment ──────────────────")

check("DATABASE_URL is set", lambda:
    (None if os.getenv("DATABASE_URL") 
     else (_ for _ in ()).throw(AssertionError("Missing"))))

check("GITHUB_TOKEN is set", lambda:
    (None if os.getenv("GITHUB_TOKEN")
     else (_ for _ in ()).throw(AssertionError("Missing"))))

check("GITHUB_REPO is set", lambda:
    (None if os.getenv("GITHUB_REPO")
     else (_ for _ in ()).throw(AssertionError("Missing"))))

check("LLM key is set (Anthropic or Inception)", lambda:
    (None if (os.getenv("ANTHROPIC_API_KEY") or os.getenv("INCEPTION_API_KEY"))
     else (_ for _ in ()).throw(AssertionError(
         "Neither ANTHROPIC_API_KEY nor INCEPTION_API_KEY is set"))))

def test_github_token_valid():
    token = os.getenv("GITHUB_TOKEN")
    repo  = os.getenv("GITHUB_REPO")
    r = requests.get(
        f"https://api.github.com/repos/{repo}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    assert r.status_code == 200, \
        f"GitHub API returned {r.status_code}: {r.json().get('message')}"
    data = r.json()
    assert data.get("full_name") == repo, \
        f"Repo mismatch: expected {repo}, got {data.get('full_name')}"
    return f"Connected to {data['full_name']}"

def test_github_write_access():
    # Critical safety check — confirms this is a repo you OWN, 
    # not a fork of someone else's real project with read-only access
    token = os.getenv("GITHUB_TOKEN")
    repo  = os.getenv("GITHUB_REPO")
    r = requests.get(
        f"https://api.github.com/repos/{repo}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    perms = r.json().get("permissions", {})
    assert perms.get("push") is True, (
        "Token does NOT have write access to this repo — "
        "branch/PR creation will fail with 403, or worse, may "
        "attempt to act against an upstream repo if this is a "
        "fork. Point GITHUB_REPO at a repo you personally own "
        "and created from scratch."
    )
    return "Write access confirmed — safe to create branches/PRs"

check("GitHub token can read repo",     test_github_token_valid)
check("GitHub token has write access",  test_github_write_access)

check("LEMMA_API_KEY is set", lambda:
    (None if os.getenv("LEMMA_API_KEY")
     else (_ for _ in ()).throw(AssertionError("Missing"))))

check(".env.example exists", lambda:
    (None if (ROOT / ".env.example").exists()
     else (_ for _ in ()).throw(AssertionError("File not found"))))

check("requirements.txt exists", lambda:
    (None if (ROOT / "requirements.txt").exists()
     else (_ for _ in ()).throw(AssertionError("File not found"))))

print("\n── Hour 1: Token Reducer Proxy ──────────")

def test_token_reducer():
    from token_reducer.proxy import TokenReducerProxy
    reducer = TokenReducerProxy(compression_ratio=0.30)
    sample = " ".join(["This is a test sentence with real content."] * 40)
    result = reducer.reduce(sample, "generic")
    assert result.original_tokens > 0, "No tokens found"
    assert result.reduction_ratio >= 0.20, \
        f"Ratio too low: {result.reduction_ratio:.0%}"
    return f"{result.reduction_ratio:.0%} compression"

check("proxy.py importable", lambda:
    __import__("token_reducer.proxy"))

check("TokenReducerProxy runs and compresses", test_token_reducer)

check("Entity extraction works", lambda: (
    __import__("token_reducer.proxy", fromlist=["TokenReducerProxy"])
    .TokenReducerProxy().reduce(
        "PR #218 was merged. See JIRA-892 and v2.4.1 release notes.", 
        "slack"
    )
) and True or None)

print("\n── Hour 1-2: Database ───────────────────")

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def test_db_connection():
    conn = get_conn()
    conn.close()
    return "Connected"

def test_tables_exist():
    conn = get_conn()
    cur = conn.cursor()
    required = ['events','entities','event_entities','event_edges','queries']
    missing = []
    for t in required:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = %s", (t,)
        )
        if not cur.fetchone():
            missing.append(t)
    conn.close()
    assert not missing, f"Missing tables: {missing}"
    return f"All {len(required)} tables present"

def test_event_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM events")
    count = cur.fetchone()[0]
    conn.close()
    assert count >= 20, f"Only {count} events — expected 20+"
    return f"{count} events"

def test_source_split():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT source_type, COUNT(*) FROM events GROUP BY source_type")
    rows = dict(cur.fetchall())
    conn.close()
    assert rows.get('github_pr', 0) >= 5, "Too few GitHub events"
    assert rows.get('slack_message', 0) >= 8, "Too few Slack events"
    assert rows.get('csv_complaint', 0) >= 5, "Too few complaints"
    return f"github={rows.get('github_pr')} slack={rows.get('slack_message')} " \
           f"complaints={rows.get('csv_complaint')}"

def test_entities_populated():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM entities")
    count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "entities table is empty"
    return f"{count} entities"

def test_edges_exist():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM event_edges")
    count = cur.fetchone()[0]
    conn.close()
    assert count >= 5, f"Only {count} edges — expected 5+"
    return f"{count} edges"

def test_pr218_connected():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM event_edges ee
        JOIN events e ON ee.source_event_id = e.id
        WHERE e.title ILIKE '%activity%' 
           OR e.source_id ILIKE '%218%'
    """)
    count = cur.fetchone()[0]
    conn.close()
    assert count >= 1, \
        "PR #218 has no outgoing edges — Memory Agent may not have run"
    return f"{count} edges from PR #218"

def test_compression_in_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT AVG(
            1.0 - (
                array_length(regexp_split_to_array(trim(compressed_body),'\\s+'),1)
                ::float /
                NULLIF(array_length(
                    regexp_split_to_array(trim(body),'\\s+'),1),0)
            )
        )
        FROM events
        WHERE body IS NOT NULL AND body != ''
    """)
    ratio = cur.fetchone()[0] or 0
    conn.close()
    assert ratio >= 0.30, f"Compression only {ratio:.0%} — check body_raw"
    return f"{ratio:.0%} avg token reduction"

check("DB connection works",          test_db_connection)
check("All 5 tables exist",           test_tables_exist)
check("Event count >= 20",            test_event_count)
check("Source split correct",         test_source_split)
check("Entities table populated",     test_entities_populated)
check("Event edges exist",            test_edges_exist)
check("PR #218 has outgoing edges",   test_pr218_connected)
check("Compression stored in DB",     test_compression_in_db)

print("\n── Hour 3: Agents ───────────────────────")

def test_memory_agent():
    from agents.memory_agent import run
    result = run()
    assert 'edges_created' in result, "Missing edges_created key"
    assert 'events_processed' in result, "Missing events_processed key"
    return f"{result['edges_created']} edges · " \
           f"{result['events_processed']} events processed"

def test_query_agent():
    from agents.query_agent import run
    result = run("Why did our cloud costs spike this month?")
    assert 'error' not in result, f"Query failed: {result.get('error')}"
    assert 'reasoning_steps' in result, "No reasoning_steps in response"
    assert len(result['reasoning_steps']) >= 4, (
        f"Only {len(result['reasoning_steps'])} steps — need 4+. "
        f"Check event_edges in Neon; may need the manual edge "
        f"inserts from the earlier causal-chain fix."
    )
    assert 'root_cause' in result, "No root_cause field"
    assert 'suggested_fix' in result, "No suggested_fix field"
    assert 'confidence' in result, "No confidence field"
    steps_text = json.dumps(result['reasoning_steps']).lower()
    has_pr218 = '218' in steps_text or 'activity' in steps_text
    if not has_pr218:
        print(f"  {WARN}  PR #218 not named in trace — check edges")
    return f"{len(result['reasoning_steps'])} steps · " \
           f"confidence {result['confidence']}"

def test_planning_agent():
    from agents.query_agent import run as qrun
    from agents.planning_agent import run as prun
    q = qrun("Why did our cloud costs spike this month?")
    assert 'error' not in q, f"Query failed: {q.get('error')}"
    plan = prun(q)
    assert 'savings' in plan, "No savings field"
    assert 'jira_ticket' in plan, "No jira_ticket field"
    assert plan['jira_ticket']['title'], "Jira title is empty"
    savings_str = plan['savings'].replace(',','').replace('₹','')
    savings_num = int(re.sub(r'[^\d]', '', savings_str) or 0)
    assert savings_num > 0, "Savings estimate is ₹0"
    assert 50000 <= savings_num <= 150000, (
        f"Savings of ₹{savings_num:,} is outside the believable "
        f"range (₹50,000–₹1,50,000). Check base_savings in "
        f"planning_agent.py — should be 180 * 24 * 30, not "
        f"600 * 24 * 30."
    )
    return f"Savings: {plan['savings']} · " \
           f"Priority: {plan['jira_ticket']['priority']}"

def test_pipeline():
    from agents.run_pipeline import run
    result = run("Why did our cloud costs spike this month?")
    assert result is not None, "Pipeline returned None"
    assert 'query' in result, "No query key in pipeline result"
    assert 'plan' in result, "No plan key in pipeline result"
    return "Full pipeline chain complete"

check("memory_agent.py imports",     lambda: __import__("agents.memory_agent"))
check("Memory Agent runs",           test_memory_agent)
check("query_agent.py imports",      lambda: __import__("agents.query_agent"))
check("Query Agent returns trace",   test_query_agent)
check("planning_agent.py imports",   lambda: __import__("agents.planning_agent"))
check("Planning Agent generates fix",test_planning_agent)
check("run_pipeline.py chains all",  test_pipeline)

print("\n── Hour 4: API Server ───────────────────")

API = "http://localhost:8000"

def api_get(path):
    try:
        r = requests.get(f"{API}{path}", timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        return r.json()
    except requests.ConnectionError:
        raise AssertionError("FastAPI not running — start with ./start.sh")

def test_api_stats():
    data = api_get("/stats")
    assert data.get('total_events', 0) >= 20, \
        f"API reports only {data.get('total_events')} events"
    assert data.get('total_edges', 0) >= 5, \
        f"API reports only {data.get('total_edges')} edges"
    assert data.get('avg_compression', 0) >= 0.30, \
        f"Compression {data.get('avg_compression'):.0%} too low"
    return f"{data['total_events']} events · " \
           f"{data['total_edges']} edges · " \
           f"{data['avg_compression']:.0%} compression"

def test_api_query():
    r = requests.post(
        f"{API}/query",
        json={"question": "Why did our cloud costs spike this month?"},
        timeout=30
    )
    assert r.status_code == 200, \
        f"HTTP {r.status_code}: {r.text[:100]}"
    data = r.json()
    assert 'reasoning_steps' in data, "No reasoning_steps"
    assert len(data['reasoning_steps']) >= 4, (
        f"Only {len(data['reasoning_steps'])} steps — need 4+. "
        f"Check event_edges in Neon; may need the manual edge "
        f"inserts from the earlier causal-chain fix."
    )
    assert 'root_cause' in data, "No root_cause"
    assert 'savings' in data, "No savings"
    savings_str = data['savings'].replace(',','').replace('₹','')
    savings_num = int(re.sub(r'[^\d]', '', savings_str) or 0)
    assert savings_num > 0, "Savings estimate is ₹0"
    assert 50000 <= savings_num <= 150000, (
        f"Savings of ₹{savings_num:,} is outside the believable "
        f"range (₹50,000–₹1,50,000). Check base_savings in "
        f"planning_agent.py — should be 180 * 24 * 30, not "
        f"600 * 24 * 30."
    )
    assert 'jira_ticket' in data, "No jira_ticket"
    return f"{len(data['reasoning_steps'])} steps · {data['savings']}"

def test_api_ingest():
    r = requests.post(f"{API}/ingest", timeout=120)
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert data.get('status') == 'ok', f"Status: {data.get('status')}"
    return "Ingest returned ok"

def test_api_docs():
    r = requests.get(f"{API}/docs", timeout=5)
    assert r.status_code == 200, f"Docs not loading: HTTP {r.status_code}"
    return "Swagger UI accessible"

def test_remediate_endpoint_exists():
    r = requests.options(f"{API}/remediate", timeout=5)
    assert r.status_code in (200, 405), \
        f"Unexpected status {r.status_code} — endpoint may be missing"
    return "Endpoint reachable"

def test_remediate_live():
    if os.getenv("RUN_LIVE_REMEDIATE_TEST") != "true":
        print(f"  {WARN}  Skipped — creates a REAL branch+PR on "
              f"{os.getenv('GITHUB_REPO')}. Run with "
              f"RUN_LIVE_REMEDIATE_TEST=true to test for real.")
        return
    r = requests.post(
        f"{API}/remediate",
        json={
            "root_cause": "Test: PR 218 caused sequential scans",
            "suggested_fix": "Add composite index to users_activity"
        },
        timeout=30
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert 'pr_url' in data, "No pr_url in response"
    assert data['pr_url'].startswith('https://github.com/'), \
        f"pr_url doesn't look like a real GitHub URL: {data['pr_url']}"
    return f"Live PR created: {data['pr_url']}"

check("FastAPI is running",       lambda: api_get("/stats"))
check("/stats returns valid data",test_api_stats)
check("/query returns trace",     test_api_query)
check("/ingest returns ok",       test_api_ingest)
check("/docs loads",              test_api_docs)
check("/remediate endpoint exists", test_remediate_endpoint_exists)
check("/remediate creates a real PR (opt-in)", test_remediate_live)

print("\n── Hour 4: Dashboard ────────────────────")

DASH = "http://localhost:3000"

def test_dashboard_loads():
    try:
        r = requests.get(DASH, timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        assert 'EI-OS' in r.text or 'Intelligence' in r.text, \
            "Page loaded but EI-OS title not found"
        return "Dashboard HTML returned"
    except requests.ConnectionError:
        raise AssertionError(
            "Next.js not running — start with ./start.sh"
        )

def test_nextjs_api_stats():
    try:
        r = requests.get(f"{DASH}/api/stats", timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        data = r.json()
        assert 'total_events' in data, "Missing total_events"
        return f"Next.js API proxy working — {data['total_events']} events"
    except requests.ConnectionError:
        raise AssertionError("Next.js not running")

check("Dashboard loads at :3000",         test_dashboard_loads)
check("Next.js /api/stats proxies ok",    test_nextjs_api_stats)

print("\n── Lemma Authentication & Hosting ───────")

def test_lemma_authenticated():
    result = subprocess.run(
        ['lemma', 'auth', 'status'],
        capture_output=True, text=True, timeout=10
    )
    # Exact subcommand may differ by CLI version — 
    # check `lemma auth --help` if this check fails unexpectedly
    combined = (result.stdout + result.stderr).lower()
    assert 'not logged in' not in combined and \
           'unauthenticated' not in combined and \
           result.returncode == 0, \
        "Not authenticated. Run: lemma auth login"
    return "Authenticated"

def test_lemma_cloud_server():
    result = subprocess.run(
        ['lemma', 'servers', 'select'],
        capture_output=True, text=True, timeout=10
    )
    output = (result.stdout + result.stderr).lower()
    if 'local' in output and 'cloud' not in output and \
       'lemma.work' not in output:
        raise AssertionError(
            "Pod appears to be on the LOCAL server — "
            "ayush@gappy.ai cannot reach it. Check `lemma servers "
            "--help` for the cloud option, switch, then re-verify "
            "functions/tables/workflows exist on the cloud pod."
        )
    return result.stdout.strip()[:60] or "Review output manually"

check("Lemma CLI is authenticated",          test_lemma_authenticated)
check("Pod is on cloud server (manual review if uncertain)",
      test_lemma_cloud_server)

print("\n── Hour 5-6: Lemma Integration ──────────")

def run_lemma(args):
    # Actually running lemma CLI
    try:
        result = subprocess.run(
            ['lemma'] + args,
            capture_output=True, text=True, timeout=10
        )
        return result.stdout + result.stderr, result.returncode
    except FileNotFoundError:
        import platform
        if platform.system() == "Windows":
            # fallback for windows if not in path
            cmd = "lemma " + " ".join(args)
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                return result.stdout + result.stderr, result.returncode
            except Exception as e:
                return str(e), 1
        return "lemma command not found", 1

def test_lemma_cli():
    out, code = run_lemma(['--version'])
    assert code == 0 or 'lemma' in out.lower(), \
        "lemma CLI not found or not working"
    return out.strip()[:40]

def test_lemma_functions():
    out, code = run_lemma(['function', 'list'])
    functions = ['memory-agent', 'query-agent', 'planning-agent']
    missing = [f for f in functions if f not in out]
    assert not missing, f"Missing Lemma functions: {missing}"
    return "All 3 functions registered"

def test_lemma_tables():
    out, code = run_lemma(['table', 'list'])
    tables = ['query-log', 'remediations']
    missing = [t for t in tables if t not in out]
    assert not missing, f"Missing Lemma tables: {missing}"
    return "Both tables present"

def test_lemma_workflows_both():
    out, code = run_lemma(['workflow', 'list'])
    workflows = ['ingest-pipeline', 'remediate-pipeline']
    missing = [w for w in workflows if w not in out]
    assert not missing, f"Missing Lemma workflows: {missing}"
    return "Both workflows present"

def test_remediations_table_reachable():
    out, code = run_lemma(['record', 'list', 'remediations'])
    assert code == 0, "remediations table not accessible"
    if len(out.strip()) == 0:
        print(f"  {WARN}  Table is empty — run the live remediate "
              f"test at least once before recording")
    return "Table accessible"

check("lemma CLI available",                  test_lemma_cli)
check("3 functions registered (migrated from agents)", test_lemma_functions)
check("Both Lemma tables exist",              test_lemma_tables)
check("Both Lemma workflows exist",           test_lemma_workflows_both)
check("remediations table reachable",         test_remediations_table_reachable)

print("\n── Hours 5-6: Files ─────────────────────")

required_files = [
    "token_reducer/proxy.py",
    "graph/schema.sql",
    "ingestion/parsers.py",
    "ingestion/watcher.py",
    "agents/memory_agent.py",
    "agents/query_agent.py",
    "agents/planning_agent.py",
    "agents/run_pipeline.py",
    "api/server.py",
    "start.sh",
    "SUBMISSION.md",
    "DEMO_SCRIPT.md",
    "data/github_prs.json",
    "data/slack_export.json",
    "data/complaints.csv",
]

for f in required_files:
    path = ROOT / f
    check(f"{f} exists", lambda p=path: (
        None if p.exists()
        else (_ for _ in ()).throw(AssertionError("Missing"))
    ))

def test_submission_complete():
    path = ROOT / "SUBMISSION.md"
    content = path.read_text()
    issues = []
    if '[fill in your name' in content:
        issues.append("Name not filled in")
    if '[X]' in content:
        issues.append("Token count [X] not replaced with real number")
    if len(content) < 500:
        issues.append("Submission seems too short")
    assert not issues, " · ".join(issues)
    return f"{len(content)} chars"

check("SUBMISSION.md is filled in", test_submission_complete)

print("\n── Data Integrity ───────────────────────")

def test_github_json():
    path = ROOT / "data/github_prs.json"
    data = json.loads(path.read_text())
    assert isinstance(data, list), "Should be a JSON array"
    assert len(data) >= 5, f"Only {len(data)} PRs"
    numbers = [p.get('number') for p in data]
    assert 218 in numbers, "PR #218 not in data file"
    pr218 = next(p for p in data if p.get('number') == 218)
    body = pr218.get('body','').lower()
    assert 'activity' in body or 'logging' in body, \
        "PR #218 body doesn't mention activity or logging"
    assert 'index' not in body, \
        "PR #218 body mentions index — it shouldn't (that's the bug)"
    return f"{len(data)} PRs · PR #218 validated"

def test_slack_json():
    path = ROOT / "data/slack_export.json"
    data = json.loads(path.read_text())
    assert isinstance(data, list), "Should be a JSON array"
    assert len(data) >= 10, f"Only {len(data)} messages"
    all_text = ' '.join(m.get('text','') for m in data).lower()
    assert any(w in all_text for w in ['timeout','slow','query']), \
        "No timeout/slow/query keywords in Slack data"
    return f"{len(data)} messages"

def test_complaints_csv():
    path = ROOT / "data/complaints.csv"
    lines = path.read_text().strip().split('\n')
    assert len(lines) >= 6, f"Only {len(lines)} lines including header"
    header = lines[0].lower()
    for col in ['id','title','description','created_at','severity']:
        assert col in header, f"Missing column: {col}"
    return f"{len(lines)-1} complaints"

check("github_prs.json is valid",  test_github_json)
check("slack_export.json is valid",test_slack_json)
check("complaints.csv is valid",   test_complaints_csv)

print("\n── Manual checks (not automatable) ──────")
print("""
  [ ] Open the dashboard, run a query — Jira panel shows BOLD 
      text, not raw **asterisks**
  [ ] Source badges colored correctly: orange=GitHub, 
      purple=Slack, red=complaints
  [ ] Header shows live stats, not 'FETCHING...'
  [ ] Logged into lemma.work, confirmed ayush@gappy.ai is added 
      as a pod member (web UI — no CLI command for this)
  [ ] If using lemma apps deploy, opened the public URL in an 
      incognito window and confirmed it loads
  [ ] Clicked AUTO-DRAFT GITHUB PR once for real, confirmed the 
      returned link opens an actual GitHub PR page
""")

total  = len(results)
passed = sum(1 for r in results if r[0] == 'PASS')
failed = sum(1 for r in results if r[0] == 'FAIL')

print("\n" + "="*50)
print(f"  Results: {passed}/{total} checks passed")
print("="*50)

if failed == 0:
    print("""
  ╔══════════════════════════════════════╗
  ║                                      ║
  ║      EI-OS READY TO SUBMIT  🚀       ║
  ║                                      ║
  ║  Go record your demo.                ║
  ║  Then paste SUBMISSION.md and ship.  ║
  ║                                      ║
  ╚══════════════════════════════════════╝
    """)
else:
    print(f"""
  ╔══════════════════════════════════════╗
  ║                                      ║
  ║   {failed} CHECK(S) FAILED              ║
  ║   Fix these before submitting        ║
  ║                                      ║
  ╚══════════════════════════════════════╝
    """)
    print("  Failed checks:")
    for status, name in results:
        if status == 'FAIL':
            print(f"    ✗ {name}")

print()
sys.exit(0 if failed == 0 else 1)

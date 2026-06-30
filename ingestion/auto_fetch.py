import os, json, requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

SINCE_HOURS = int(os.getenv("FETCH_SINCE_HOURS", "24"))

def fetch_github_prs():
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_REPO = os.getenv("GITHUB_REPO")

    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("GitHub: missing GITHUB_TOKEN or GITHUB_REPO in .env")
        return 0

    URL = f"https://api.github.com/repos/{GITHUB_REPO}/pulls"
    params = {
        "state": "closed",
        "sort": "updated",
        "direction": "desc",
        "per_page": 50
    }
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    try:
        response = requests.get(URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"GitHub: Failed to fetch - {e}")
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=SINCE_HOURS)

    filtered_prs = []
    for pr in data:
        merged_at_str = pr.get("merged_at")
        if not merged_at_str:
            continue
        
        merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
        if merged_at >= cutoff:
            filtered_prs.append({
                "number": pr["number"],
                "title": pr["title"],
                "body": pr["body"] or "",
                "user": {"login": pr["user"]["login"]},
                "merged_at": pr["merged_at"],
                "created_at": pr["created_at"],
                "html_url": pr["html_url"],
                "labels": pr["labels"],
                "changed_files": pr.get("changed_files", 0)
            })

    if filtered_prs:
        with open(DATA_DIR / "github_prs.json", "w") as f:
            json.dump(filtered_prs, f, indent=2)
    
    print(f"GitHub: {len(filtered_prs)} PRs fetched from {GITHUB_REPO}")
    return len(filtered_prs)

def fetch_slack_messages():
    SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

    if not SLACK_TOKEN or not SLACK_CHANNEL_ID:
        print("Slack: missing SLACK_BOT_TOKEN or SLACK_CHANNEL_ID in .env")
        return 0

    oldest = (datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)).timestamp()

    URL = "https://slack.com/api/conversations.history"
    params = {
        "channel": SLACK_CHANNEL_ID,
        "oldest": str(oldest),
        "limit": 200
    }
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}

    try:
        response = requests.get(URL, params=params, headers=headers)
        data = response.json()
        if not data.get("ok"):
            raise Exception(data.get("error"))
    except Exception as e:
        print(f"Slack: Failed to fetch - {e}")
        return 0

    filtered_messages = []
    for msg in data.get("messages", []):
        filtered_messages.append({
            "ts": msg["ts"],
            "user": msg.get("user", "unknown"),
            "text": msg.get("text", ""),
            "channel": SLACK_CHANNEL_ID,
            "subtype": msg.get("subtype")
        })

    if filtered_messages:
        with open(DATA_DIR / "slack_export.json", "w") as f:
            json.dump(filtered_messages, f, indent=2)

    print(f"Slack: {len(filtered_messages)} messages fetched")
    return len(filtered_messages)

def fetch_complaints():
    mode = os.getenv("COMPLAINTS_SOURCE", "none").lower()
    
    if mode == "freshdesk":
        domain = os.getenv("FRESHDESK_DOMAIN")
        api_key = os.getenv("FRESHDESK_API_KEY")
        if not domain or not api_key:
            print("Complaints (freshdesk): missing credentials")
            return 0
            
        URL = f"https://{domain}/api/v2/tickets"
        auth = (api_key, "X")
        params = {"order_by": "created_at", "order_type": "desc", "per_page": 100}
        
        try:
            response = requests.get(URL, auth=auth, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Complaints: Failed to fetch from Freshdesk - {e}")
            return 0
            
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)
        tickets = []
        
        def map_priority(p):
            return {1: "low", 2: "medium", 3: "high", 4: "high"}.get(p, "medium")
            
        for ticket in data:
            created_at = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
            if created_at >= cutoff:
                tickets.append({
                    "id": f"FD-{ticket['id']}",
                    "title": ticket["subject"],
                    "description": ticket.get("description_text", ticket.get("description", "")),
                    "created_at": ticket["created_at"],
                    "severity": map_priority(ticket.get("priority", 2))
                })
                
    elif mode == "zendesk":
        domain = os.getenv("ZENDESK_DOMAIN")
        email = os.getenv("ZENDESK_EMAIL")
        token = os.getenv("ZENDESK_API_TOKEN")
        if not domain or not email or not token:
            print("Complaints (zendesk): missing credentials")
            return 0
            
        URL = f"https://{domain}/api/v2/tickets.json"
        auth = (f"{email}/token", token)
        params = {"sort_by": "created_at", "sort_order": "desc"}
        
        try:
            response = requests.get(URL, auth=auth, params=params)
            response.raise_for_status()
            data = response.json().get("tickets", [])
        except Exception as e:
            print(f"Complaints: Failed to fetch from Zendesk - {e}")
            return 0
            
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)
        tickets = []
        
        for ticket in data:
            created_at = datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00"))
            if created_at >= cutoff:
                tickets.append({
                    "id": f"ZD-{ticket['id']}",
                    "title": ticket["subject"],
                    "description": ticket.get("description", ""),
                    "created_at": ticket["created_at"],
                    "severity": "high" if ticket.get("priority") == "urgent" else "medium"
                })
                
    else:
        print("Complaints: skipping (COMPLAINTS_SOURCE not set)")
        return 0

    if tickets:
        import csv
        with open(DATA_DIR / "complaints.csv", "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["id", "title", "description", "created_at", "severity"])
            writer.writeheader()
            writer.writerows(tickets)
            
    print(f"Complaints: {len(tickets)} tickets fetched")
    return len(tickets)

def run():
    print(f"\nEI-OS Auto-Fetch — last {SINCE_HOURS} hours")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    results['github'] = fetch_github_prs()
    results['slack'] = fetch_slack_messages()
    results['complaints'] = fetch_complaints()
    
    fetched = {k: v for k, v in results.items() if v}
    
    if fetched:
        print(f"\nData saved to data/ — Watchdog will trigger ingest automatically")
    else:
        print("\nNothing fetched — check your API tokens in .env")
    
    return results

if __name__ == "__main__":
    run()

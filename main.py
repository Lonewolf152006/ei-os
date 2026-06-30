"""
EI-OS — Enterprise Intelligence OS
Entry point: loads environment, checks database connectivity, prints startup banner.
"""

import os
import sys

from dotenv import load_dotenv


BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     ███████╗██╗       ██████╗ ███████╗                   ║
║     ██╔════╝██║      ██╔═══██╗██╔════╝                   ║
║     █████╗  ██║█████╗██║   ██║███████╗                   ║
║     ██╔══╝  ██║╚════╝██║   ██║╚════██║                   ║
║     ███████╗██║       ╚██████╔╝███████║                   ║
║     ╚══════╝╚═╝        ╚═════╝ ╚══════╝                   ║
║                                                          ║
║     Enterprise Intelligence OS                           ║
║     Gappy AI × Lemma SDK Hackathon                       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""

REQUIRED_VARS = [
    ("DATABASE_URL",       "Neon PostgreSQL connection string"),
    ("ANTHROPIC_API_KEY",  "Anthropic Claude — powers Lemma agents"),
    ("LEMMA_API_KEY",      "Local auth token from: lemma auth login"),
    ("LEMMA_API_URL",      "Lemma API endpoint (default: http://localhost:8711)"),
]


def check_env() -> dict:
    """Check which env vars are set vs missing. Returns status dict."""
    status = {}
    for var, description in REQUIRED_VARS:
        value = os.getenv(var, "").strip()
        status[var] = {
            "set": bool(value),
            "description": description,
            "preview": f"{value[:8]}..." if value and len(value) > 8 else ("(set)" if value else "(missing)"),
        }
    return status


def try_database_connection() -> bool:
    """Attempt a PostgreSQL connection. Returns True on success."""
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.close()
        return True
    except ImportError:
        print("  ⚠  psycopg2 not installed. Run: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"  ⚠  Database connection failed: {e}")
        return False


def main():
    # Load .env file
    load_dotenv()

    print(BANNER)

    # ── Environment check ──
    print("🔍  Environment Variable Status:")
    print("-" * 50)
    env_status = check_env()
    all_set = True
    for var, info in env_status.items():
        icon = "✅" if info["set"] else "❌"
        print(f"  {icon}  {var:<20s}  {info['preview']}")
        print(f"       └─ {info['description']}")
        if not info["set"]:
            all_set = False
    print()

    # ── Database connectivity ──
    print("🗄️   Database Connectivity:")
    print("-" * 50)
    db_url = os.getenv("DATABASE_URL", "").strip()

    if not db_url:
        print("  ⏭  DATABASE_URL not set — skipping connection test.")
        print("  📋  Next steps:")
        print("       1. Sign up at https://neon.tech")
        print("       2. Create a project & copy the connection string")
        print("       3. Add to .env:  DATABASE_URL=postgres://...")
        print("       4. Run: psql $DATABASE_URL < graph/schema.sql")
        print("       5. Run: python scripts/verify_db.py")
    else:
        if try_database_connection():
            print("  ✅  Connected to PostgreSQL successfully!")
        else:
            print("  ❌  Could not connect. Check your DATABASE_URL.")
    print()

    # ── Summary ──
    n_set = sum(1 for v in env_status.values() if v["set"])
    n_total = len(env_status)
    print(f"📊  Summary: {n_set}/{n_total} environment variables configured.")

    if not all_set:
        print("  ℹ  Some variables are missing — that's OK for initial setup.")
        print("  ℹ  The system will work incrementally as you add keys.\n")
    else:
        print("  🚀  All keys set — ready to go!\n")

    # Exit cleanly (never crash)
    sys.exit(0)


if __name__ == "__main__":
    main()

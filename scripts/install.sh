#!/usr/bin/env bash
# ============================================================
# EI-OS — Installation & Setup Script
# ============================================================
set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║          EI-OS Installation & Setup                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Install Python dependencies ──
echo "📦  Step 1/2: Installing Python dependencies..."
echo "─────────────────────────────────────────────"
pip install -r requirements.txt
echo ""
echo "✅  Dependencies installed successfully!"
echo ""

# ── Step 2: Database setup instructions ──
echo "🗄️   Step 2/2: Database Setup (manual)"
echo "─────────────────────────────────────────────"
echo ""
echo "  Follow these steps to set up your Neon PostgreSQL database:"
echo ""
echo "  1. Sign up at https://neon.tech (free tier available)"
echo "     → Create a new project (e.g., 'ei-os')"
echo ""
echo "  2. Copy your DATABASE_URL from the Neon dashboard"
echo "     → It looks like: postgres://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb"
echo ""
echo "  3. Add it to your .env file:"
echo "     cp .env.example .env"
echo "     # Then edit .env and paste your DATABASE_URL"
echo ""
echo "  4. Run the schema against your database:"
echo "     psql \$DATABASE_URL < graph/schema.sql"
echo ""
echo "  5. Verify the schema was applied:"
echo "     python scripts/verify_db.py"
echo ""
echo "─────────────────────────────────────────────"
echo "✅  Installation complete!"
echo ""
echo "🚀  Quick start:"
echo "     python main.py              # Check environment status"
echo "     python token_reducer/proxy.py  # Test the token reducer"
echo ""

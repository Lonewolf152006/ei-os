#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Enterprise Intelligence OS         ║"
echo "║   Powered by Lemma SDK               ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Start FastAPI
echo "Starting API server on :8000..."
python -m uvicorn api.server:app --reload &
FASTAPI_PID=$!
sleep 2

# Start Next.js
echo "Starting dashboard on :3000..."
(cd dashboard && npm run dev) &
NEXTJS_PID=$!

# Start file watcher
echo "Starting file watcher on data/..."
python ingestion/watcher.py &
WATCHER_PID=$!

echo "Starting auto-fetch scheduler (every 15 min)..."
python -c "
import time, subprocess
while True:
    # Run the file directly here as well
    subprocess.run(['python', 'ingestion/auto_fetch.py'])
    time.sleep(900)  # 15 minutes
" &
SCHEDULER_PID=$!

echo ""
echo "  Dashboard → http://localhost:3000"
echo "  API       → http://localhost:8000/docs"
echo "  Lemma UI  → http://localhost:3711"
echo ""
echo "Press Ctrl+C to stop all services"

trap "kill $FASTAPI_PID $NEXTJS_PID $WATCHER_PID $SCHEDULER_PID 2>/dev/null" EXIT
wait
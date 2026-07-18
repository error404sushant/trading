#!/bin/bash
cd "$(dirname "$0")"

# Start background scanner daemon (places Bybit orders for all tracked coins)
./venv/bin/python scanner_daemon.py >> /tmp/scanner_daemon.log 2>&1 &
DAEMON_PID=$!
echo "Scanner daemon started (PID: $DAEMON_PID)"

# Start Streamlit UI
./venv/bin/streamlit run ui/app.py --server.port 8501 --server.headless false

# Kill daemon when Streamlit exits
kill $DAEMON_PID 2>/dev/null

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/dashboard.pid"
LOG_FILE="$SCRIPT_DIR/dashboard.log"
PORT="${DASH_PORT:-9077}"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Dashboard is already running (PID $OLD_PID). Use ./stop.sh to stop it first."
        exit 1
    else
        echo "Stale PID file found (PID $OLD_PID is gone). Cleaning up."
        rm -f "$PID_FILE"
    fi
fi

# Something else may be holding the port even without a PID file
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $PORT is already in use by another process. Set DASH_PORT to pick a different one."
    exit 1
fi

cd "$SCRIPT_DIR"
echo "Starting Docker dashboard..."
nohup python3 server.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1

if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Dashboard failed to start. Last log lines:"
    tail -5 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

echo "Dashboard started (PID $(cat "$PID_FILE")) at http://localhost:$PORT"
echo "Logs: $LOG_FILE"

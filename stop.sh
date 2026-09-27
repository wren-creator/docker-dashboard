#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/dashboard.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file, dashboard doesn't look like it's running."
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping Docker dashboard (PID $PID)..."
    kill "$PID"
    for i in $(seq 1 10); do
        kill -0 "$PID" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$PID" 2>/dev/null; then
        echo "Process did not exit cleanly; sending SIGKILL..."
        kill -9 "$PID"
    fi
    echo "Stopped."
else
    echo "Stale PID file (PID $PID is not running). Cleaning up."
fi
rm -f "$PID_FILE"

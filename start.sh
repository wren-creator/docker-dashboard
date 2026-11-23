#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/dashboard.pid"
LOG_FILE="$SCRIPT_DIR/dashboard.log"
PORT="${DASH_PORT:-9077}"

# --lan <ip>: internal-network exposure, opt-in and explicit. Binds all
# interfaces and accepts that one extra Host header value -- see README's
# security note on what this gives up (unauthenticated start/stop/restart
# to anyone who can reach the port).
while [ $# -gt 0 ]; do
    case "$1" in
        --lan)
            export DASH_HOST="0.0.0.0"
            export DASH_ALLOWED_HOSTS="$2"
            echo "WARNING: --lan exposes this to your internal network with no" >&2
            echo "login -- anyone who can reach $2:$PORT can start/stop/restart" >&2
            echo "every container on this box. See README.md before using this" >&2
            echo "anywhere less trusted than a home LAN." >&2
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

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
# (tries to bind it with python, so it works without lsof, e.g. bare Ubuntu).
# Same host as the real server below binds, so this actually tests what
# matters -- 127.0.0.1 can be free while 0.0.0.0 is taken, or vice versa.
if ! python3 -c "import socket,sys; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((sys.argv[1], int(sys.argv[2])))" "${DASH_HOST:-127.0.0.1}" "$PORT" 2>/dev/null; then
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

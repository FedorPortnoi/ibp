#!/usr/bin/env bash
# Start IBP dev server — kills any existing instance first.
PID_FILE="$(dirname "$0")/.server.pid"
cd "$(dirname "$0")"

# Kill previous instance if PID file exists
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    kill "$OLD_PID" 2>/dev/null && echo "Stopped old server (PID $OLD_PID)"
    rm -f "$PID_FILE"
fi

# Also kill anything still on port 5000 (safety net)
fuser -k 5000/tcp 2>/dev/null || true

. venv/Scripts/activate
nohup python run.py > server.log 2> server.err &
echo $! > "$PID_FILE"
sleep 4
grep -i "Running on" server.err && echo "PID $(cat $PID_FILE) — server up"

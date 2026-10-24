#!/bin/bash
# Start (or restart) the X reading-tweaks server on port 12002.
# Idempotent: safe to run repeatedly.
#
# This is only for testing before publishing. The list itself ships over the
# raw GitHub URL in README.md, which does not depend on this sandbox.
#
# Usage:  bash start.sh

PORT=${X_TWEAKS_PORT:-12002}
DIR=$(cd "$(dirname "$0")" && pwd)
LOG="$DIR/server.log"

# Kill only our own server: same script name AND this project's directory.
# Matching the name alone would also kill the servers on 12000 and 12001,
# which belong to different projects.
for pid in $(pgrep -f "serve.py" 2>/dev/null); do
    cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null)
    if [ "$cwd" = "$DIR" ]; then
        kill "$pid" 2>/dev/null
    fi
done
sleep 1

cd "$DIR" || exit 1
nohup python3 serve.py >> "$LOG" 2>&1 &
sleep 2

if curl -sf -o /dev/null --max-time 6 "http://127.0.0.1:$PORT/"; then
    echo "x-tweaks server up on port $PORT"
    for f in x-tweaks-brave.txt; do
        code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 "http://127.0.0.1:$PORT/$f")
        echo "  /$f -> $code"
    done
else
    echo "server FAILED to start; see $LOG"
    tail -5 "$LOG" 2>/dev/null
    exit 1
fi

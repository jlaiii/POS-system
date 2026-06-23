#!/bin/bash
# POS System Flask Launcher with auto-restart
# Now uses gunicorn + eventlet for production stability.
# Used by reliability bot and cron jobs to keep the POS running.
#
# Environment:
#   PORT=5000  (default)
#   WORKERS=1  (default, must be 1 for SocketIO)

set -euo pipefail

cd /root/pos-system-work || exit 1

PORT="${PORT:-5000}"
WORKERS="${WORKERS:-1}"
MAX_RESTARTS=10
RESTART_WINDOW=300  # 5 minutes
restart_count=0
first_restart_time=0

# Verify required packages
python3 -c "import eventlet" 2>/dev/null || { echo "eventlet not installed"; exit 1; }
python3 -c "import gunicorn" 2>/dev/null || { echo "gunicorn not installed"; exit 1; }

while true; do
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] Starting POS System (gunicorn+eventlet, port ${PORT})..."
    gunicorn \
        -k eventlet \
        -w "${WORKERS}" \
        --bind "0.0.0.0:${PORT}" \
        --worker-connections 1000 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile - \
        --capture-output \
        --log-level info \
        app:app
    
    # If we get here, gunicorn exited (shouldn't normally happen with the launcher)
    exit_code=$?
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] POS System exited with code $exit_code"
    
    # Crash rate limiting: if crashed >10 times in 5 minutes, give up
    current_time=$(date +%s)
    if [ $first_restart_time -eq 0 ]; then
        first_restart_time=$current_time
    fi
    
    elapsed=$((current_time - first_restart_time))
    if [ $elapsed -le $RESTART_WINDOW ]; then
        restart_count=$((restart_count + 1))
    else
        restart_count=0
        first_restart_time=0
    fi
    
    if [ $restart_count -ge $MAX_RESTARTS ]; then
        echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] CRITICAL: POS System restarted $MAX_RESTARTS times in under $RESTART_WINDOW seconds. Giving up."
        exit 1
    fi
    
    sleep 2
done

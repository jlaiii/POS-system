#!/bin/bash
# POS System Flask Launcher with auto-restart
# Used by reliability bot to keep Flask running
# For production, migrate to gunicorn (see TASKS.md)

cd /root/pos-system-work || exit 1

MAX_RESTARTS=10
RESTART_WINDOW=300  # 5 minutes
restart_count=0
first_restart_time=0

while true; do
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] Starting Flask..."
    python3 app.py
    
    exit_code=$?
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] Flask exited with code $exit_code"
    
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
        echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] CRITICAL: Flask restarted $MAX_RESTARTS times in under $RESTART_WINDOW seconds. Giving up."
        exit 1
    fi
    
    sleep 2
done

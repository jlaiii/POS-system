#!/bin/bash
# POS System Production Launcher — gunicorn + gevent
# Replaces the dev-mode socketio.run() for production stability.
# SocketIO compat: gunicorn with gevent worker class handles
# both HTTP and WebSocket transparently.
#
# Usage:
#   ./scripts/run_gunicorn.sh                  # foreground (Ctrl+C to stop)
#   nohup ./scripts/run_gunicorn.sh &           # background
#   ./scripts/run_gunicorn.sh --daemon          # daemon mode
#
# Config:
#   PORT=5000 ./scripts/run_gunicorn.sh         # custom port (default 5000)
#   WORKERS=2  ./scripts/run_gunicorn.sh        # custom worker count (default 1)

set -uo pipefail

cd /root/pos-system-work

PORT="${PORT:-5000}"
WORKERS="${WORKERS:-1}"
BIND="0.0.0.0:${PORT}"

# Ensure gevent is available
python3 -c "import gevent" 2>/dev/null || {
    echo "[ERROR] gevent not installed. Run: pip install gevent"
    exit 1
}

# Ensure gunicorn is available
python3 -c "import gunicorn" 2>/dev/null || {
    echo "[ERROR] gunicorn not installed. Run: pip install gunicorn"
    exit 1
}

echo "[$(date -u +'%Y-%m-%dT%H:%M:%S')] Starting POS System — gunicorn + gevent"
echo "  Port:    ${PORT}"
echo "  Workers: ${WORKERS}"
echo "  Bind:    ${BIND}"
echo "  WSGI:    app:app (Flask app, SocketIO via gevent async_mode)"

# ---- gunicorn args ----
# -k gevent        : gevent worker for async + WebSocket compat
# -w 1             : exactly 1 worker (required by Flask-SocketIO)
# --bind           : listen address
# --worker-connections : max simultaneous clients
# --timeout        : worker timeout (120s)
# --access-logfile  : access log (- = stdout)
# --error-logfile   : error log (- = stderr)
# --capture-output  : redirect app stdout to gunicorn's log
# --log-level       : info/debug/warning/error

exec gunicorn \
    -k gevent \
    -w "${WORKERS}" \
    --bind "${BIND}" \
    --worker-connections 1000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --log-level info \
    app:app

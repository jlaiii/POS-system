#!/usr/bin/env python3
"""
POS Process Monitor — checks PID file every 30s from cron.
If gunicorn is dead, attempts restart via systemd user service first,
then via run_flask.sh as fallback.

Usage:
    python3 scripts/pos_monitor.py          # normal check
    python3 scripts/pos_monitor.py --fix    # attempt restart if dead
    python3 scripts/pos_monitor.py --quiet  # silent if healthy

Exit codes:
    0 = healthy (process running or already handled)
    1 = dead, restart attempted
    2 = dead, unable to restart
"""
import os
import sys
import subprocess
import time
import json
from datetime import datetime

PID_FILE = '/root/pos-system-work/pos-system.pid'
WORK_DIR = '/root/pos-system-work'
FLASK_SCRIPT = os.path.join(WORK_DIR, 'scripts/run_flask.sh')
PORT = 5000


def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}")


def read_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def read_cmdline(pid):
    """Read the command line of a process given its PID."""
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            raw = f.read()
            return raw.replace(b'\x00', b' ').decode('utf-8', errors='replace')
    except (OSError, IOError):
        return ''


def is_gunicorn_process(pid):
    """Check if the given PID is running gunicorn (not Flask dev server)."""
    cmdline = read_cmdline(pid)
    return 'gunicorn' in cmdline


def is_flask_dev_server(pid):
    """Check if the given PID is a Flask dev server (app.run or socketio.run)."""
    cmdline = read_cmdline(pid)
    return 'app.run' in cmdline or 'socketio.run' in cmdline


def is_process_alive(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)  # signal 0 = test existence
        return True
    except OSError:
        return False


def is_port_open(port):
    """Check if anything is listening on the port."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        return result == 0
    except Exception:
        return False


def try_systemd_restart():
    """Try restarting via systemd user service."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'is-enabled', 'pos-system.service'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            log("Systemd service pos-system.service is enabled, starting...")
            subprocess.run(
                ['systemctl', '--user', 'start', 'pos-system.service'],
                capture_output=True, timeout=10
            )
            time.sleep(3)
            if is_port_open(PORT):
                log("Systemd service started successfully.")
                return True
            log("Systemd service start failed, trying fallback...")
        return False
    except Exception as e:
        log(f"Systemd service attempt failed: {e}")
        return False


def try_flask_restart():
    """Fallback: start run_flask.sh in background."""
    try:
        log(f"Starting fallback: {FLASK_SCRIPT}")
        subprocess.Popen(
            ['bash', FLASK_SCRIPT],
            cwd=WORK_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(3)
        if is_port_open(PORT):
            log("Fallback flask script started successfully.")
            return True
        log("Fallback started but port not ready yet (may take a few seconds).")
        return True  # assume it's starting
    except Exception as e:
        log(f"Fallback restart failed: {e}")
        return False


def find_process_on_port(port):
    """Find any process listening on the given port. Returns (pid, cmdline) or None."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                # Port is open; find who via /proc
                for p in os.listdir('/proc'):
                    if not p.isdigit():
                        continue
                    try:
                        with open(f'/proc/{p}/cmdline', 'rb') as f:
                            raw = f.read()
                        if not raw:
                            continue
                        cmd = raw.replace(b'\x00', b' ').decode('utf-8', errors='replace')
                        # Check if this process has the port open
                        fd_link = f'/proc/{p}/fd'
                        if os.path.isdir(fd_link):
                            for fd in os.listdir(fd_link):
                                try:
                                    link = os.readlink(f'{fd_link}/{fd}')
                                    if f':{port}' in link:
                                        return (int(p), cmd)
                                except (OSError, IOError):
                                    pass
                    except (OSError, IOError):
                        pass
    except Exception:
        pass
    return None


def main():
    quiet = '--quiet' in sys.argv
    do_fix = '--fix' in sys.argv

    pid = read_pid()
    alive = is_process_alive(pid) if pid else False
    port_open = is_port_open(PORT)

    if not quiet:
        if pid:
            log(f"PID {pid}: {'ALIVE' if alive else 'DEAD'}")
        else:
            log("No PID file found.")
        log(f"Port {PORT}: {'OPEN' if port_open else 'CLOSED'}")

    # Extra check: if process is alive, verify it's gunicorn
    wrong_process = False
    if alive and not is_gunicorn_process(pid):
        if is_flask_dev_server(pid):
            log(f"WARNING: PID {pid} is a Flask DEV SERVER, not gunicorn!")
            wrong_process = True
        else:
            log(f"WARNING: PID {pid} is not gunicorn (unknown process)")
            wrong_process = True

    # If port is open but no PID file or wrong process, find the offender
    if port_open and (not pid or wrong_process):
        found = find_process_on_port(PORT)
        if found:
            other_pid, other_cmd = found
            if other_pid != pid:
                log(f"Port {PORT} owned by PID {other_pid} (not our tracked process): {other_cmd[:120]}")

    # Case 1: Process alive AND gunicorn AND port open — healthy
    if alive and port_open and not wrong_process:
        if not quiet:
            log("POS System is healthy (gunicorn).")
        return 0

    # Case 2: Process alive but port not open — unusual
    if alive and not port_open:
        log(f"WARNING: PID {pid} exists but port {PORT} is not open. Process may be starting or stuck.")
        return 0

    # Case 3: Process dead or wrong — need remediation
    if wrong_process:
        log("Wrong process type detected (Flask dev server instead of gunicorn).")

    if not port_open or wrong_process:
        if not port_open:
            log(f"POS System is DOWN (PID {pid}, port {PORT}).")
        else:
            log(f"POS System has wrong process on port {PORT}.")

        if not do_fix:
            log("Use --fix to attempt restart.")
            return 1

        log("Attempting restart...")

        # Kill any process holding the port (Flask dev server)
        if wrong_process or (port_open and not pid):
            found = find_process_on_port(PORT)
            if found:
                other_pid, other_cmd = found
                log(f"Killing PID {other_pid} ({other_cmd[:80]}...)")
                try:
                    os.kill(other_pid, 15)  # SIGTERM
                    time.sleep(2)
                    if is_process_alive(other_pid):
                        os.kill(other_pid, 9)  # SIGKILL
                        time.sleep(1)
                except ProcessLookupError:
                    pass

        # Try systemd first
        if try_systemd_restart():
            return 1

        # Fallback to shell script
        if try_flask_restart():
            return 1

        log("CRITICAL: All restart methods failed.")
        return 2

    # Case 4: Port open but no PID file — port is claimed but we don't own it
    if port_open and not pid:
        log(f"Port {PORT} is open but no PID file. Another process may be using it.")
        if not quiet:
            found = find_process_on_port(PORT)
            if found:
                other_pid, other_cmd = found
                log(f"  Process on port: PID {other_pid} — {other_cmd[:100]}")
        return 0

    return 0


if __name__ == '__main__':
    sys.exit(main())

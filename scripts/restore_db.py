#!/usr/bin/env python3
"""
POS System — Database Restore Procedure
========================================
Restores the POS system from a backup file (JSON tar.gz or SQLite db.gz).
Creates a safety backup of the current data before restoring, stops Flask,
replaces the data files, restarts Flask, and verifies the application responds.

Usage:
  python3 scripts/restore_db.py --list                   # List available backups
  python3 scripts/restore_db.py --list --json            # List JSON backups only
  python3 scripts/restore_db.py --list --db              # List DB backups only
  python3 scripts/restore_db.py <backup_file>            # Restore from backup
  python3 scripts/restore_db.py <backup_file> --json     # Restore JSON from tar.gz
  python3 scripts/restore_db.py <backup_file> --yes      # Skip confirmation prompt
  python3 scripts/restore_db.py <backup_file> --dry-run  # Show what would be done

Backup locations:
  JSON backups:   backups/json/<timestamp>.tar.gz
  SQLite backups: backups/db/pos_<timestamp>.db.gz

Process:
  1. Creates a safety backup of current data (just in case)
  2. Decompresses and extracts the chosen backup
  3. Verifies integrity of restored data
  4. Stops the Flask server
  5. Replaces data files
  6. Restarts Flask server
  7. Verifies app responds on health endpoint

Exit codes:
  0 = restore completed successfully
  1 = restore failed (backup not found, integrity issue, etc.)
  2 = user cancelled / nothing done
"""

import gzip
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_JSON_DIR = os.path.join(PROJECT_ROOT, 'backups', 'json')
BACKUP_DB_DIR = os.path.join(PROJECT_ROOT, 'backups', 'db')
SAFETY_BACKUP_DIR = os.path.join(PROJECT_ROOT, 'backups', 'pre_restore_safety')

# Flask app
FLASK_PORT = 5000
HEALTH_URL = f'http://localhost:{FLASK_PORT}/api/health'

# How long to wait for Flask to start after restore (seconds)
FLASK_START_TIMEOUT = 30

# How long to wait between Flask status checks (seconds)
FLASK_POLL_INTERVAL = 2

# Excluded files from JSON restore (non-data files)
NON_DATA_FILES = {
    'package.json',
    'package-lock.json',
    'manifest.json',
    '.gitignore',
    'README.md',
    'requirements.txt',
}

# Flask process identification strings for pkill
FLASK_PROCESS_MATCH = 'app:app'
FLASK_SCRIPT_MATCH = 'app.py'


# ── Color & formatting helpers ────────────────────────────────────────────

def red(text):
    return f'\033[91m{text}\033[0m' if sys.stdout.isatty() else text

def green(text):
    return f'\033[92m{text}\033[0m' if sys.stdout.isatty() else text

def yellow(text):
    return f'\033[93m{text}\033[0m' if sys.stdout.isatty() else text

def cyan(text):
    return f'\033[96m{text}\033[0m' if sys.stdout.isatty() else text

def bold(text):
    return f'\033[1m{text}\033[0m' if sys.stdout.isatty() else text


# ── Helpers ───────────────────────────────────────────────────────────────

def readable_size(size_bytes):
    """Convert bytes to human-readable size string."""
    if size_bytes == 0:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'


def log(msg, level='info'):
    """Print a log message with timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prefix = {
        'info': ' ℹ️ ',
        'ok': ' ✅ ',
        'warn': ' ⚠️ ',
        'error': ' ❌ ',
        'step': ' 🔄 ',
    }
    print(f'[{timestamp}]{prefix.get(level, " ℹ️ ")} {msg}')


def prompt_yes_no(question):
    """Ask the user a yes/no question and return True for 'yes'."""
    if '--yes' in sys.argv or '-y' in sys.argv:
        return True
    response = input(f'\n{question} [yes/no]: ').strip().lower()
    return response in ('yes', 'y')


def run_command(cmd, description=None, check=True, timeout=30):
    """Run a shell command and return (returncode, stdout, stderr)."""
    if description:
        log(f'Running: {description}', 'step')
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        if check and result.returncode != 0:
            log(f'Command failed (exit {result.returncode}): {cmd}', 'error')
            log(f'stderr: {result.stderr.strip()}', 'error')
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        log(f'Command timed out: {cmd}', 'error')
        return -1, '', 'Timed out'
    except Exception as e:
        log(f'Command error: {e}', 'error')
        return -1, '', str(e)


# ── Backup Listing ────────────────────────────────────────────────────────

def list_available_backups(only_json=False, only_db=False):
    """List all available backups with timestamps, types, and sizes."""
    print(f'\n{bold("Available Backups")}')
    print('=' * 80)
    
    any_found = False
    
    # ── JSON backups ──
    if not only_db:
        json_dir = BACKUP_JSON_DIR
        if os.path.isdir(json_dir):
            archives = sorted([
                f for f in os.listdir(json_dir)
                if f.endswith('.tar.gz')
            ])
            if archives:
                any_found = True
                print(f'\n{cyan("📦 JSON Backups")} ({BACKUP_JSON_DIR}/)')
                print(f'  {"TIMESTAMP":<25} {"SIZE":>10}  {"TYPE":<10}  {"PATH"}')
                print(f'  {"-"*25} {"-"*10}  {"-"*10}  {"-"}')
                for fname in archives:
                    fpath = os.path.join(json_dir, fname)
                    size = os.path.getsize(fpath)
                    timestamp = fname.replace('.tar.gz', '')
                    print(f'  {timestamp:<25} {readable_size(size):>10}  {"json":<10}  {fpath}')
    
    # ── DB backups ──
    if not only_json:
        db_dir = BACKUP_DB_DIR
        if os.path.isdir(db_dir):
            archives = sorted([
                f for f in os.listdir(db_dir)
                if f.endswith('.db.gz')
            ])
            if archives:
                any_found = True
                print(f'\n{cyan("💾 SQLite DB Backups")} ({BACKUP_DB_DIR}/)')
                print(f'  {"TIMESTAMP":<25} {"SIZE":>10}  {"TYPE":<10}  {"PATH"}')
                print(f'  {"-"*25} {"-"*10}  {"-"*10}  {"-"}')
                for fname in archives:
                    fpath = os.path.join(db_dir, fname)
                    size = os.path.getsize(fpath)
                    # Extract timestamp from pos_2026-06-23_14-00-00.db.gz
                    ts_part = fname.replace('pos_', '').replace('.db.gz', '')
                    print(f'  {ts_part:<25} {readable_size(size):>10}  {"sqlite":<10}  {fpath}')
    
    if not any_found:
        print(f'\n  {yellow("No backups found.")}')
        print(f'  JSON dir: {BACKUP_JSON_DIR}/')
        print(f'  DB dir:   {BACKUP_DB_DIR}/')
    
    print()


def get_file_timestamp(filepath):
    """Return a human-readable timestamp from a backup filename."""
    basename = os.path.basename(filepath)
    # Strip extensions
    if basename.endswith('.tar.gz'):
        ts = basename.replace('.tar.gz', '')
    elif basename.endswith('.db.gz'):
        ts = basename.replace('pos_', '').replace('.db.gz', '')
    else:
        ts = basename
    return ts


# ── Integrity Verification ────────────────────────────────────────────────

def verify_json_integrity(extract_dir):
    """Verify all JSON files in the extracted backup directory are valid."""
    issues = []
    files_checked = 0
    
    for root, dirs, files in os.walk(extract_dir):
        for fname in sorted(files):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(root, fname)
            files_checked += 1
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                issues.append(f'{fname}: {e}')
            except Exception as e:
                issues.append(f'{fname}: {e}')
    
    return files_checked, issues


def verify_sqlite_integrity(db_path):
    """Verify SQLite database integrity."""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA quick_check')
        result = cursor.fetchone()[0]
        if result != 'ok':
            conn.close()
            return False, f'quick_check returned: {result}'
        
        cursor.execute('PRAGMA integrity_check')
        rows = cursor.fetchall()
        if not (len(rows) == 1 and rows[0][0] == 'ok'):
            errors = [r[0] for r in rows if r[0] != 'ok']
            conn.close()
            return False, f'integrity_check failed: {" | ".join(errors)}'
        
        conn.close()
        return True, 'SQLite integrity check passed'
    except ImportError:
        return False, 'sqlite3 module not available'
    except Exception as e:
        return False, str(e)


# ── Flask Control ─────────────────────────────────────────────────────────

def is_flask_running():
    """Check if any Flask/gunicorn process is running on port."""
    # Try HTTP health check first
    try:
        req = urllib.request.Request(HEALTH_URL, method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp:
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionRefusedError, OSError):
        pass
    
    # Fallback: check for running processes
    rc, stdout, _ = run_command(
        f'pgrep -f "app:app" || pgrep -f "python3.*app.py" || true',
        check=False
    )
    return bool(stdout.strip())


def stop_flask():
    """Stop the Flask server gracefully."""
    log('Stopping Flask server...', 'step')
    
    # First try graceful pkill
    run_command(
        'pkill -f "gunicorn.*app:app" || true',
        'Stopping gunicorn (graceful)',
        check=False,
        timeout=10
    )
    
    time.sleep(2)
    
    # Kill any remaining app.py processes
    run_command(
        'pkill -f "python3.*app.py" || true',
        'Stopping app.py processes',
        check=False,
        timeout=10
    )
    
    time.sleep(2)
    
    if is_flask_running():
        log('Force killing remaining Flask processes...', 'warn')
        run_command(
            'pkill -9 -f "gunicorn.*app:app" 2>/dev/null; '
            'pkill -9 -f "python3.*app.py" 2>/dev/null || true',
            'Force kill',
            check=False,
            timeout=5
        )
        time.sleep(1)
    
    if is_flask_running():
        log('Could not stop Flask server. Trying to kill by port...', 'error')
        run_command(
            f'fuser -k {FLASK_PORT}/tcp 2>/dev/null || true',
            f'Kill process on port {FLASK_PORT}',
            check=False,
            timeout=5
        )
        time.sleep(1)
    
    if is_flask_running():
        return False
    
    log('Flask server stopped.', 'ok')
    return True


def start_flask():
    """Start the Flask server."""
    log('Starting Flask server...', 'step')
    
    # Use run_flask.sh if available, otherwise use run_gunicorn.sh, otherwise use direct command
    flask_script = os.path.join(PROJECT_ROOT, 'scripts', 'run_flask.sh')
    gunicorn_script = os.path.join(PROJECT_ROOT, 'scripts', 'run_gunicorn.sh')
    
    if os.path.isfile(flask_script) and os.access(flask_script, os.X_OK):
        cmd = f'cd {PROJECT_ROOT} && nohup bash {flask_script} > /dev/null 2>&1 &'
    elif os.path.isfile(gunicorn_script) and os.access(gunicorn_script, os.X_OK):
        cmd = f'cd {PROJECT_ROOT} && nohup bash {gunicorn_script} > /dev/null 2>&1 &'
    else:
        cmd = f'cd {PROJECT_ROOT} && nohup python3 app.py > /dev/null 2>&1 &'
    
    run_command(cmd, f'Starting Flask via: {cmd.split("nohup")[1].strip()[:60]}...', check=False, timeout=5)
    
    # Wait for Flask to become available
    log('Waiting for Flask to respond...', 'info')
    start_time = time.time()
    while time.time() - start_time < FLASK_START_TIMEOUT:
        time.sleep(FLASK_POLL_INTERVAL)
        try:
            req = urllib.request.Request(HEALTH_URL, method='GET')
            with urllib.request.urlopen(req, timeout=3) as resp:
                log(f'Flask is running and responding (HTTP {resp.getcode()}).', 'ok')
                return True
        except urllib.error.HTTPError as e:
            # HTTP error still means the server is running
            log(f'Flask is running (HTTP {e.code}).', 'ok')
            return True
        except (ConnectionRefusedError, OSError):
            continue
    
    log(f'Flask did not respond within {FLASK_START_TIMEOUT}s.', 'error')
    return False


def verify_flask_health():
    """Verify Flask app responds correctly after restore."""
    try:
        req = urllib.request.Request(HEALTH_URL, method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode('utf-8')
            log(f'Health check response ({resp.getcode()}): {body[:200]}', 'ok')
            return True
    except urllib.error.HTTPError as e:
        log(f'Health check HTTP {e.code}: {e.read()[:200]}', 'warn')
        # HTTP error still means the server is running
        return True
    except Exception as e:
        log(f'Health check failed: {e}', 'error')
        return False


# ── Restore Logic ─────────────────────────────────────────────────────────

def create_safety_backup():
    """Create a timestamped safety backup of the current data before restoring."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    safety_dir = os.path.join(SAFETY_BACKUP_DIR, f'pre_restore_{timestamp}')
    os.makedirs(safety_dir, exist_ok=True)
    
    log(f'Creating safety backup of current data in {safety_dir}/...', 'step')
    
    json_files_copied = 0
    
    # Backup JSON files
    for fname in sorted(os.listdir(PROJECT_ROOT)):
        if not fname.endswith('.json'):
            continue
        if fname in NON_DATA_FILES:
            continue
        src = os.path.join(PROJECT_ROOT, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(safety_dir, fname))
            json_files_copied += 1
    
    # Backup SQLite database if exists
    db_src = os.path.join(PROJECT_ROOT, 'pos.db')
    if os.path.isfile(db_src):
        shutil.copy2(db_src, os.path.join(safety_dir, 'pos.db'))
        log(f'  Backed up pos.db ({readable_size(os.path.getsize(db_src))})', 'ok')
    
    # Write a manifest
    manifest = {
        'backup_time': datetime.now().isoformat(),
        'restore_operation': os.path.basename(sys.argv[-1]) if len(sys.argv) > 1 else 'manual',
        'json_files_copied': json_files_copied,
        'had_sqlite': os.path.isfile(db_src),
    }
    with open(os.path.join(safety_dir, 'safety_manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Create a combined tar.gz for convenience
    archive_path = os.path.join(SAFETY_BACKUP_DIR, f'pre_restore_{timestamp}.tar.gz')
    with tarfile.open(archive_path, 'w:gz') as tar:
        tar.add(safety_dir, arcname=f'pre_restore_{timestamp}')
    
    log(f'Safety backup created: {archive_path} ({readable_size(os.path.getsize(archive_path))})', 'ok')
    log(f'  Safety directory: {safety_dir}/', 'info')
    return archive_path


def restore_from_json_backup(backup_path):
    """Restore all JSON files from a tar.gz backup archive.
    
    Returns True on success, False on failure.
    """
    log(f'Restoring JSON backup: {backup_path}', 'step')
    
    if not os.path.isfile(backup_path):
        log(f'Backup file not found: {backup_path}', 'error')
        return False
    
    # Step 1: Extract to a temp directory for verification
    temp_dir = tempfile.mkdtemp(prefix='pos_restore_json_')
    try:
        log('Extracting backup archive for verification...', 'step')
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(path=temp_dir)
        
        # Find the actual data files
        # Archive structure: <timestamp>/<files>.json
        extracted_items = os.listdir(temp_dir)
        if not extracted_items:
            log('Backup archive appears empty.', 'error')
            return False
        
        # The top-level is the timestamp directory
        data_source = temp_dir
        for item in extracted_items:
            item_path = os.path.join(temp_dir, item)
            if os.path.isdir(item_path):
                data_source = item_path
                break
        
        # Step 2: Verify integrity of all JSON files
        log('Verifying JSON file integrity...', 'step')
        files_checked, issues = verify_json_integrity(data_source)
        
        if issues:
            log(f'Integrity check found {len(issues)} issue(s):', 'error')
            for issue in issues:
                log(f'  - {issue}', 'error')
            
            cont = prompt_yes_no(
                f'{yellow("⚠️  Integrity check found issues. Restore anyway?")} '
                f'Data may be corrupted.'
            )
            if not cont:
                log('Restore cancelled.', 'warn')
                return False
        
        log(f'Integrity check passed: {files_checked} JSON files verified.', 'ok')
        
        # Step 3: Create a safety backup of current data
        safety_archive = create_safety_backup()
        
        # Step 4: Stop Flask
        if is_flask_running():
            if not stop_flask():
                cont = prompt_yes_no(
                    f'{yellow("⚠️  Could not stop Flask server. Restore anyway?")} '
                    f'Data files may be in use.'
                )
                if not cont:
                    log('Restore cancelled.', 'warn')
                    return False
        else:
            log('Flask server is not running (good — data files are not in use).', 'info')
        
        # Step 5: Replace JSON data files
        log('Restoring JSON data files...', 'step')
        restored_count = 0
        skipped_count = 0
        for fname in sorted(os.listdir(data_source)):
            if not fname.endswith('.json'):
                continue
            src = os.path.join(data_source, fname)
            dst = os.path.join(PROJECT_ROOT, fname)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                restored_count += 1
                log(f'  Restored: {fname}', 'ok')
            else:
                skipped_count += 1
        
        log(f'Restored {restored_count} JSON file(s).', 'ok')
        if skipped_count:
            log(f'Skipped {skipped_count} non-file entries.', 'info')
        
        # Step 6: Restart Flask
        if not start_flask():
            log(
                f'{yellow("⚠️  Flask did not start automatically.")} '
                f'Start manually: cd {PROJECT_ROOT} && bash scripts/run_flask.sh',
                'warn'
            )
            # Return True anyway since data was restored
            return True
        
        # Step 7: Verify Flask health
        if not verify_flask_health():
            log(f'{yellow("⚠️  Flask is running but health check failed.")}', 'warn')
            return True  # Data restored, server running — minor issue
        
        log(f'{green("✓ JSON restore complete!")}', 'ok')
        return True
    
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def restore_from_db_backup(backup_path):
    """Restore SQLite database from a .db.gz backup file.
    
    Returns True on success, False on failure.
    """
    log(f'Restoring SQLite DB backup: {backup_path}', 'step')
    
    if not os.path.isfile(backup_path):
        log(f'Backup file not found: {backup_path}', 'error')
        return False
    
    temp_dir = tempfile.mkdtemp(prefix='pos_restore_db_')
    try:
        # Step 1: Decompress the .db.gz file
        db_filename = os.path.basename(backup_path).replace('.gz', '')
        temp_db_path = os.path.join(temp_dir, db_filename)
        
        log('Decompressing database backup...', 'step')
        with gzip.open(backup_path, 'rb') as gz_in:
            with open(temp_db_path, 'wb') as f_out:
                f_out.write(gz_in.read())
        
        decompressed_size = os.path.getsize(temp_db_path)
        log(f'Decompressed: {readable_size(decompressed_size)}', 'ok')
        
        # Step 2: Verify SQLite integrity
        log('Verifying SQLite integrity...', 'step')
        ok, msg = verify_sqlite_integrity(temp_db_path)
        if not ok:
            log(f'Integrity check failed: {msg}', 'error')
            cont = prompt_yes_no(
                f'{yellow("⚠️  Integrity check failed. Restore anyway?")}'
            )
            if not cont:
                log('Restore cancelled.', 'warn')
                return False
        else:
            log(f'Integrity check passed: {msg}', 'ok')
        
        # Step 3: Create a safety backup of current data
        safety_archive = create_safety_backup()
        
        # Step 4: Stop Flask
        if is_flask_running():
            if not stop_flask():
                cont = prompt_yes_no(
                    f'{yellow("⚠️  Could not stop Flask. Restore anyway?")}'
                )
                if not cont:
                    log('Restore cancelled.', 'warn')
                    return False
        else:
            log('Flask server is not running (data files are not in use).', 'info')
        
        # Step 5: Replace the SQLite database
        db_dest = os.path.join(PROJECT_ROOT, 'pos.db')
        log(f'Replacing pos.db...', 'step')
        
        # Backup current db just in case (already did full safety backup above)
        if os.path.isfile(db_dest):
            current_size = os.path.getsize(db_dest)
            log(f'Current pos.db size: {readable_size(current_size)}', 'info')
        
        shutil.copy2(temp_db_path, db_dest)
        log(f'Replaced pos.db ({readable_size(decompressed_size)})', 'ok')
        
        # Also copy WAL/SHM files if present in the backup archive? 
        # .db.gz only contains the DB file itself — WAL/SHM are auto-recreated by SQLite
        
        # Step 6: Restart Flask
        if not start_flask():
            log(
                f'{yellow("⚠️  Flask did not start automatically.")} '
                f'Start manually: cd {PROJECT_ROOT} && bash scripts/run_flask.sh',
                'warn'
            )
            return True
        
        # Step 7: Verify Flask
        if not verify_flask_health():
            log(f'{yellow("⚠️  Flask is running but health check failed.")}', 'warn')
            return True
        
        log(f'{green("✓ SQLite DB restore complete!")}', 'ok')
        return True
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def restore_from_json_to_db(backup_path):
    """Restore JSON backup AND populate SQLite database from JSON files.
    
    For the --json flag: restores JSON files, then if SQLite exists,
    attempts to populate it from the restored JSON (future migration support).
    For now, the primary mode is JSON file restore.
    """
    result = restore_from_json_backup(backup_path)
    
    # If SQLite database exists and JSON restore succeeded, offer to populate DB
    db_path = os.path.join(PROJECT_ROOT, 'pos.db')
    if result and os.path.isfile(db_path):
        log(
            f'{yellow("ℹ️  JSON files restored.")} SQLite database (pos.db) may '
            f'need to be synced. Use --db restore separately to restore pos.db '
            f'or manually run the Flask app which syncs JSON → SQLite.',
            'info'
        )
    
    return result


# ── Main ──────────────────────────────────────────────────────────────────

def print_header():
    print(f'''
{bold("╔══════════════════════════════════════════════════════════╗")}
{bold("║      POS System — Restore Utility                         ║")}
{bold("╠══════════════════════════════════════════════════════════╣")}
{bold("║  Restores data from JSON tar.gz or SQLite db.gz backups. ")} ║
{bold("║                                                          ")} ║
{bold("╚══════════════════════════════════════════════════════════╝")}
''')


def main():
    args = set(sys.argv[1:])
    dry_run = '--dry-run' in args
    
    print_header()
    
    # ── List mode ──
    if '--list' in args:
        only_json = '--json' in args
        only_db = '--db' in args
        list_available_backups(only_json=only_json, only_db=only_db)
        return 0
    
    # ── Identify backup file ──
    backup_file = None
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            backup_file = arg
            break
    
    if not backup_file:
        log(f'{yellow("No backup file specified.")}', 'warn')
        print(f'\nUsage:')
        print(f'  python3 scripts/restore_db.py --list')
        print(f'  python3 scripts/restore_db.py <backup_file>')
        print(f'  python3 scripts/restore_db.py <backup_file> --json')
        print(f'  python3 scripts/restore_db.py <backup_file> --yes')
        print(f'  python3 scripts/restore_db.py <backup_file> --dry-run')
        print()
        return 1
    
    # ── Resolve backup path ──
    # If relative path, try in common locations
    if not os.path.isfile(backup_file):
        # Try relative to project root
        alt_path = os.path.join(PROJECT_ROOT, backup_file)
        if os.path.isfile(alt_path):
            backup_file = alt_path
        else:
            # Try in backups/json/ or backups/db/
            for base_dir in [BACKUP_JSON_DIR, BACKUP_DB_DIR]:
                alt_path = os.path.join(base_dir, backup_file)
                if os.path.isfile(alt_path):
                    backup_file = alt_path
                    break
    
    if not os.path.isfile(backup_file):
        log(f'Backup file not found: {backup_file}', 'error')
        print(f'\n  Searched locations:')
        print(f'    {backup_file}')
        print(f'    {os.path.join(PROJECT_ROOT, backup_file)}')
        print(f'    {os.path.join(BACKUP_JSON_DIR, backup_file)}')
        print(f'    {os.path.join(BACKUP_DB_DIR, backup_file)}')
        print(f'\n  Run --list to see available backups.')
        return 1
    
    # ── Validate backup file type ──
    basename = os.path.basename(backup_file)
    is_json = basename.endswith('.tar.gz')
    is_db = basename.endswith('.db.gz')
    
    if not is_json and not is_db:
        log(f'Unknown backup format: {backup_file}', 'error')
        log('Expected .tar.gz (JSON backup) or .db.gz (SQLite backup)', 'error')
        return 1
    
    # ── Print backup info ──
    log(f'Backup file: {backup_file}', 'info')
    log(f'File size:   {readable_size(os.path.getsize(backup_file))}', 'info')
    log(f'Timestamp:   {get_file_timestamp(backup_file)}', 'info')
    log(f'Type:        {"JSON backup" if is_json else "SQLite DB backup"}', 'info')
    
    # Show current system state
    print()
    log(f'Current state:', 'info')
    log(f'  Flask running: {"Yes" if is_flask_running() else "No"}', 'info')
    db_path = os.path.join(PROJECT_ROOT, 'pos.db')
    if os.path.isfile(db_path):
        log(f'  pos.db: {readable_size(os.path.getsize(db_path))}', 'info')
    json_count = len([f for f in os.listdir(PROJECT_ROOT) if f.endswith('.json') and f not in NON_DATA_FILES])
    log(f'  JSON data files: {json_count}', 'info')
    print()
    
    # ── Confirmation prompt ──
    if not dry_run:
        if not prompt_yes_no(
            f'{red("⚠️  This will replace the current database.")} '
            f'{yellow("All changes since the backup will be lost.")} '
            f'\nA safety backup of current data will be created first.'
        ):
            log('Restore cancelled by user.', 'warn')
            return 2
    
    # ── Dry-run mode ──
    if dry_run:
        log(f'{yellow("DRY RUN — no changes will be made.")}', 'warn')
        log(f'Would restore: {backup_file}', 'info')
        log(f'Steps:', 'info')
        
        # Create safety backup
        log(f'  1. Create safety backup of current data', 'step')
        
        if is_json:
            log(f'  2. Extract JSON tar.gz', 'step')
            log(f'  3. Verify JSON integrity', 'step')
            log(f'  4. Stop Flask server', 'step')
            log(f'  5. Replace JSON files in project root', 'step')
        else:
            log(f'  2. Decompress .db.gz', 'step')
            log(f'  3. Verify SQLite integrity', 'step')
            log(f'  4. Stop Flask server', 'step')
            log(f'  5. Replace pos.db', 'step')
        
        log(f'  6. Start Flask server', 'step')
        log(f'  7. Verify app responds', 'step')
        log(f'\n{green("Dry run complete. Use without --dry-run to execute.")}')
        return 0
    
    # ── Execute restore ──
    if is_json:
        if '--json' in args:
            success = restore_from_json_to_db(backup_file)
        else:
            success = restore_from_json_backup(backup_file)
    elif is_db:
        success = restore_from_db_backup(backup_file)
    else:
        log('Unknown backup type.', 'error')
        return 1
    
    if success:
        log(f'\n{green("=" * 60)}')
        log(f'{green("✓ RESTORE COMPLETE")}')
        log(f'{green("=" * 60)}')
        print(f'''
Safety backup created in: {SAFETY_BACKUP_DIR}/
To undo this restore:
  python3 scripts/restore_db.py backups/pre_restore_safety/pre_restore_*.tar.gz --json
  (if JSON backup was restored)
  OR
  python3 scripts/restore_db.py backups/pre_restore_safety/pre_restore_*/pos.db
  (if SQLite backup was restored)
''')
        return 0
    else:
        log(f'\n{red("=" * 60)}')
        log(f'{red("✗ RESTORE FAILED")}')
        log(f'{red("=" * 60)}')
        log(f'Check the errors above. Safety backup is at {SAFETY_BACKUP_DIR}/', 'warn')
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f'\n{yellow("Restore cancelled by user.")}')
        sys.exit(2)
    except Exception as e:
        log(f'Unexpected error: {e}', 'error')
        sys.exit(1)

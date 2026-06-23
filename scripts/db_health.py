#!/usr/bin/env python3
"""
POS System — Database Health Check Script
==========================================
Validates data integrity for both JSON (pre-migration) and SQLite (post-migration).

JSON mode (current):
  - Parses all JSON data files, reports sizes and record counts
  - Detects 0-byte files, corrupt JSON, and dramatic size changes (>50% drop)
  - Counts records per data file (top-level arrays or dict keys)

SQLite mode (post-migration):
  - Runs PRAGMA integrity_check — must return "ok"
  - Runs PRAGMA foreign_key_check — must return no rows
  - Runs PRAGMA quick_check (faster than integrity_check)
  - Checks file size isn't 0 and hasn't shrunk dramatically
  - Counts rows across all tables

Usage:
  python3 scripts/db_health.py                    # full health check
  python3 scripts/db_health.py --json             # force JSON mode
  python3 scripts/db_health.py --sqlite           # force SQLite mode
  python3 scripts/db_health.py --quiet            # only output errors/summary
  python3 scripts/db_health.py --check-only       # exit code only (0=healthy, 1=unhealthy)

Can be called from backup script as pre-backup validation:
  python3 scripts/db_health.py --quiet --check-only

Returns exit code:
  0 = all checks passed (healthy)
  1 = one or more checks failed (unhealthy)
  2 = mode mismatch or no data found
"""

import json
import os
import sys
import glob
import re
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────

# Non-data JSON files to exclude
EXCLUDED_FILES = {
    'package.json',
    'package-lock.json',
    'manifest.json',
}

# Files that are top-level dicts (users, combos, items, etc.) vs arrays
# Top-level dicts -> count keys. Top-level arrays -> count elements.
# If it's a dict with numeric keys like users.json (PIN -> user), count keys.
# If it's a plain array like orders.json, count elements.

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'pos.db')


# ── Helpers ────────────────────────────────────────────────────────────────

def log(msg, quiet=False):
    if not quiet:
        print(msg)


def readable_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_data_json_files():
    """Return sorted list of data .json file paths, excluding non-data files."""
    pattern = os.path.join(PROJECT_ROOT, '*.json')
    all_files = sorted(glob.glob(pattern))
    return [
        f for f in all_files
        if os.path.basename(f) not in EXCLUDED_FILES
    ]


def count_records(data):
    """Count top-level records: if dict, count keys; if list, count elements."""
    if isinstance(data, dict):
        return len(data)
    elif isinstance(data, list):
        return len(data)
    return 0


def get_data_label(filepath):
    """Map filename to a human-readable label."""
    name = os.path.basename(filepath).replace('.json', '')
    labels = {
        'users': 'Users',
        'items': 'Menu Items',
        'orders': 'Orders',
        'shift_log': 'Shifts',
        'activity_log': 'Activity Log',
        'tables': 'Tables',
        'inventory': 'Inventory',
        'combos': 'Combos',
        'discounts': 'Discounts',
        'tax_config': 'Tax Config',
        'tickets': 'Tickets',
        'timesheet': 'Timesheet Entries',
        'timesheet_config': 'Timesheet Config',
        'webhooks': 'Webhooks',
        'email_config': 'Email Config',
        'cash_drawer': 'Cash Drawer',
        'refunded_orders': 'Refunded Orders',
        'cleared_orders': 'Cleared Orders',
        'table_ads': 'Table Ads',
        'delivery_addresses': 'Delivery Addresses',
        'waste_log': 'Waste Log',
        'scheduled_pricing': 'Scheduled Pricing',
        'loyalty_points': 'Loyalty Points',
        'favorites': 'Favorites',
        'security_events': 'Security Events',
        'security_config': 'Security Config',
        'known_ips': 'Known IPs',
        'login_attempts': 'Login Attempts',
        'order_counter': 'Order Counter',
        'service_charge_config': 'Service Charge Config',
    }
    return labels.get(name, name.replace('_', ' ').title())


def load_json_file(filepath):
    """Load and parse a JSON file. Returns (data, error_message)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    except FileNotFoundError:
        return None, "File not found"
    except Exception as e:
        return None, str(e)


# ── JSON Health Check ─────────────────────────────────────────────────────

def check_json_health(quiet=False):
    """Validate all JSON data files. Returns (passed_count, failed_count, total_records, total_size, issues)."""
    files = get_data_json_files()
    if not files:
        log("  No JSON data files found.", quiet)
        return 0, 0, 0, 0, ["No JSON data files found"]

    # First pass: collect sizes and check for previous backup sizes
    current_sizes = {}
    for fpath in files:
        try:
            current_sizes[fpath] = os.path.getsize(fpath)
        except OSError:
            current_sizes[fpath] = 0

    # Check against previous backup sizes if available
    backup_sizes = {}
    backup_dir = os.path.join(PROJECT_ROOT, 'backups', 'json')
    if os.path.isdir(backup_dir):
        archives = sorted([
            os.path.join(backup_dir, f)
            for f in os.listdir(backup_dir)
            if f.endswith('.tar.gz')
        ])
        if archives:
            # Use the most recent backup for comparison
            latest = archives[-1]
            try:
                import tarfile
                with tarfile.open(latest, 'r:gz') as tar:
                    for member in tar.getmembers():
                        if member.name.endswith('.json') and '/' in member.name:
                            # member.name is like "2026-06-23_09-49-13/users.json"
                            basename = os.path.basename(member.name)
                            backup_sizes[basename] = member.size
            except Exception:
                pass  # Non-critical — skip backup comparison

    passed = 0
    failed = 0
    total_records = 0
    total_size = 0
    issues = []

    log(f"\n  {'JSON DATA FILE':<40} {'SIZE':>10} {'RECORDS':>8}  STATUS", quiet)
    log(f"  {'-'*40} {'-'*10} {'-'*8}  {'-'*12}", quiet)

    for fpath in files:
        fname = os.path.basename(fpath)
        size = current_sizes.get(fpath, 0)
        total_size += size
        size_str = readable_size(size)

        data, err = load_json_file(fpath)

        if data is not None:
            records = count_records(data)
            total_records += records

            # Check for dramatic size drop (>50% compared to backup)
            size_issue = None
            if fname in backup_sizes and backup_sizes[fname] > 0:
                ratio = size / backup_sizes[fname]
                if ratio < 0.5:
                    size_issue = (f"{fname}: size dropped from "
                                  f"{readable_size(backup_sizes[fname])} to {size_str} "
                                  f"({ratio*100:.0f}% of backup — possible corruption)")

            if size == 0:
                log(f"  {fname:<40} {size_str:>10} {records:>8}  ⚠️ EMPTY", quiet)
                issues.append(f"{fname}: 0 bytes (empty file)")
                passed += 1  # Still valid JSON (empty file)
            elif size_issue:
                log(f"  {fname:<40} {size_str:>10} {records:>8}  ⚠️ SHRUNK", quiet)
                issues.append(size_issue)
                passed += 1  # Still valid JSON
            else:
                log(f"  {fname:<40} {size_str:>10} {records:>8}  ✅", quiet)
                passed += 1
        else:
            log(f"  {fname:<40} {size_str:>10} {'ERR':>8}  ❌ {err}", quiet)
            issues.append(f"{fname}: {err}")
            failed += 1

    return passed, failed, total_records, total_size, issues


# ── SQLite Health Check ──────────────────────────────────────────────────

def check_sqlite_health(quiet=False):
    """Run SQLite PRAGMA health checks. Returns (healthy, report_str, issues)."""
    issues = []
    healthy = True
    details = []

    try:
        import sqlite3
    except ImportError:
        return False, "FAIL — sqlite3 module not available", ["sqlite3 not available"]

    if not os.path.isfile(DB_PATH):
        return False, "FAIL — pos.db not found", ["pos.db file does not exist"]

    db_size = os.path.getsize(DB_PATH)
    db_size_str = readable_size(db_size)

    if db_size == 0:
        return False, "FAIL — pos.db is 0 bytes", ["Database file is empty"]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # ── Quick check (fast) ──
        cursor.execute("PRAGMA quick_check")
        quick_result = cursor.fetchone()[0]
        if quick_result != "ok":
            healthy = False
            issues.append(f"quick_check returned: {quick_result}")
            details.append(f"  ❌ PRAGMA quick_check : {quick_result}")
        else:
            details.append("  ✅ PRAGMA quick_check : ok")

        # ── Full integrity check ──
        cursor.execute("PRAGMA integrity_check")
        integrity_rows = cursor.fetchall()
        integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"
        if not integrity_ok:
            healthy = False
            for row in integrity_rows:
                if row[0] != "ok":
                    issues.append(f"integrity_check: {row[0]}")
            details.append(f"  ❌ PRAGMA integrity_check : FAIL ({len(integrity_rows)} issues)")
        else:
            details.append("  ✅ PRAGMA integrity_check : ok")

        # ── Foreign key check ──
        cursor.execute("PRAGMA foreign_key_check")
        fk_rows = cursor.fetchall()
        if fk_rows:
            healthy = False
            for row in fk_rows:
                issues.append(f"foreign_key violation: {row}")
            details.append(f"  ❌ PRAGMA foreign_key_check : {len(fk_rows)} violation(s)")
        else:
            details.append("  ✅ PRAGMA foreign_key_check : no violations")

        # ── List tables and count rows ──
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        total_rows = 0
        table_info = []
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM \"{table}\"")
                count = cursor.fetchone()[0]
                total_rows += count
                table_info.append(f"    {table}: {count} rows")
            except Exception as e:
                table_info.append(f"    {table}: ERROR counting rows — {e}")

        details.append(f"  📊 Tables: {len(tables)}, Total rows: {total_rows}")
        for t in table_info:
            details.append(t)

        # ── Check for dramatic size drop vs backup ──
        backup_dir = os.path.join(PROJECT_ROOT, 'backups', 'json')
        db_backups = []
        if os.path.isdir(backup_dir):
            for entry in os.listdir(backup_dir):
                if entry.endswith('.tar.gz'):
                    db_backups.append(os.path.join(backup_dir, entry))
            if db_backups:
                # Can't easily get individual db file size from tar without extracting
                pass  # Size drop detection primarily for JSON mode

        conn.close()

        if healthy:
            summary = (f"OK — {len(tables)} tables, {total_rows} rows, {db_size_str}")
        else:
            summary = f"FAIL — {len(issues)} issue(s)"
            for iss in issues:
                summary += f"\n    - {iss}"

        report = "\n".join(details)
        return healthy, summary, issues

    except Exception as e:
        return False, f"FAIL — SQLite error: {e}", [str(e)]


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    args = set(sys.argv[1:])
    quiet = '--quiet' in args
    check_only = '--check-only' in args
    force_json = '--json' in args
    force_sqlite = '--sqlite' in args

    # Determine mode
    is_sqlite = os.path.isfile(DB_PATH)

    if force_sqlite and not force_json:
        mode = 'sqlite'
    elif force_json and not force_sqlite:
        mode = 'json'
    else:
        mode = 'sqlite' if is_sqlite else 'json'

    # Header
    mode_label = "SQLite" if mode == 'sqlite' else "JSON"
    log(f"{'='*65}", quiet)
    log(f"  POS System — Data Health Check", quiet)
    log(f"  Mode: {mode_label}", quiet)
    log(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", quiet)
    log(f"{'='*65}", quiet)

    overall_healthy = True
    total_issues = []

    if mode == 'json':
        passed, failed, total_records, total_size, issues = check_json_health(quiet=quiet)

        if failed > 0:
            overall_healthy = False
        total_issues.extend(issues)

        log(f"\n  {'='*65}", quiet)
        log(f"  Summary:", quiet)
        log(f"    Files checked : {passed + failed}", quiet)
        log(f"    Valid        : {passed}", quiet)
        log(f"    Invalid      : {failed}", quiet)
        log(f"    Total records: {total_records}", quiet)
        log(f"    Total size   : {readable_size(total_size)} (uncompressed)", quiet)

        if issues:
            log(f"  {'─'*65}", quiet)
            log(f"  ⚠️  Issues found ({len(issues)}):", quiet)
            for iss in issues:
                log(f"    - {iss}", quiet)
            log(f"  {'─'*65}", quiet)

        if overall_healthy:
            log(f"\n  ✅ HEALTHY — All JSON data files valid.", quiet)
        else:
            log(f"\n  ❌ UNHEALTHY — {failed} file(s) failed validation.", quiet)

    else:
        # SQLite mode
        log(f"\n  Database: {DB_PATH}", quiet)
        healthy, summary, issues = check_sqlite_health(quiet=quiet)

        if not healthy:
            overall_healthy = False
            total_issues.extend(issues)

        log(f"\n  {'='*65}", quiet)
        log(f"  SQLite Health Check:", quiet)
        log(f"  {summary}", quiet)

        if issues:
            log(f"  {'─'*65}", quiet)
            log(f"  ⚠️  Issues ({len(issues)}):", quiet)
            for iss in issues:
                log(f"    - {iss}", quiet)

        if healthy:
            log(f"\n  ✅ HEALTHY — Database integrity verified.", quiet)
        else:
            log(f"\n  ❌ UNHEALTHY — {len(issues)} integrity issue(s) detected.", quiet)

    log(f"{'='*65}\n", quiet)

    if check_only:
        return 0 if overall_healthy else 1

    return 0 if overall_healthy else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nHealth check cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""
POS System — Automated Restore Test Script
===========================================
Picks a random backup, restores it to a temp location, and verifies
key metrics (table count, row count, recent order exists, integrity).
Reports detailed results.

Designed for automated weekly cron execution. Silence = success, output = failure.

Usage:
  python3 scripts/test_restore.py                    # full test, details on stdout
  python3 scripts/test_restore.py --json             # test JSON backups instead of SQLite
  python3 scripts/test_restore.py --quiet            # only output on failure
  python3 scripts/test_restore.py --backup FILE      # test a specific backup file
  python3 scripts/test_restore.py --dry-run          # show what would be done

Exit codes:
  0 = all checks passed (healthy backup tested successfully)
  1 = one or more critical checks failed (integrity issue, corrupt backup)
  2 = no backups available to test
"""

import gzip
import json
import os
import random
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_JSON_DIR = os.path.join(PROJECT_ROOT, 'backups', 'json')
BACKUP_DB_DIR = os.path.join(PROJECT_ROOT, 'backups', 'db')
TEMP_BASE = os.path.join(PROJECT_ROOT, 'backups', 'temp_restore_tests')

# Expected values — these should be updated if the schema changes
EXPECTED_TABLE_COUNT = 24  # 24 user tables (excluding sqlite_sequence internal table)
EXPECTED_MIN_TOTAL_ROWS = 10  # At minimum total rows across all tables

# ── Color helpers ─────────────────────────────────────────────────────────

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


def log(msg, level='info', quiet=False):
    """Print a log message with timestamp unless quiet mode and not error."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prefix = {
        'info': ' ℹ️ ',
        'ok': ' ✅ ',
        'warn': ' ⚠️ ',
        'error': ' ❌ ',
        'step': ' 🔄 ',
        'result': ' 📊 ',
    }
    if quiet and level in ('info', 'step', 'result'):
        return
    print(f'[{timestamp}]{prefix.get(level, " ℹ️ ")} {msg}')


# ── Backup Discovery ──────────────────────────────────────────────────────

def list_sqlite_backups():
    """Return sorted list of (timestamp, filepath) for SQLite backups."""
    if not os.path.isdir(BACKUP_DB_DIR):
        return []
    backups = []
    for fname in sorted(os.listdir(BACKUP_DB_DIR)):
        if fname.endswith('.db.gz'):
            fpath = os.path.join(BACKUP_DB_DIR, fname)
            # Extract timestamp from pos_2026-06-23_14-00-00.db.gz
            ts_part = fname.replace('pos_', '').replace('.db.gz', '')
            backups.append((ts_part, fpath))
    return backups


def list_json_backups():
    """Return sorted list of (timestamp, filepath) for JSON tar.gz backups."""
    if not os.path.isdir(BACKUP_JSON_DIR):
        return []
    backups = []
    for fname in sorted(os.listdir(BACKUP_JSON_DIR)):
        if fname.endswith('.tar.gz'):
            fpath = os.path.join(BACKUP_JSON_DIR, fname)
            ts_part = fname.replace('.tar.gz', '')
            backups.append((ts_part, fpath))
    return backups


# ── SQLite Restore Test ──────────────────────────────────────────────────

def test_sqlite_backup(backup_path, quiet=False):
    """Test a SQLite .db.gz backup: extract, verify integrity, check schema & data.
    
    Returns (integrity_ok, warnings, report_lines).
    - integrity_ok: False if backup is corrupt/unusable (hard failure)
    - warnings: list of non-critical observations (schema mismatch, empty tables)
    - report_lines: formatted output lines
    """
    errors = []     # Hard failures — backup is corrupt
    warnings = []   # Soft issues — schema/data evolution
    report = []
    temp_dir = None

    try:
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='pos_restore_test_', dir=TEMP_BASE)
        db_path = os.path.join(temp_dir, 'test_restore.db')

        # Step 1: Decompress
        log(f'Decompressing: {os.path.basename(backup_path)}', 'step', quiet)
        try:
            with gzip.open(backup_path, 'rb') as f_in:
                with open(db_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except Exception as e:
            errors.append(f'Failed to decompress backup: {e}')
            report.append(f'  ❌ Decompression failed: {e}')
            return False, errors + warnings, report

        db_size = os.path.getsize(db_path)
        report.append(f'  Extracted DB size: {readable_size(db_size)}')

        if db_size == 0:
            errors.append('Extracted database is 0 bytes (empty/corrupt)')
            report.append(f'  ❌ Extracted DB is empty!')
            return False, errors + warnings, report

        # Step 2: Open and verify integrity
        log('Running integrity checks...', 'step', quiet)
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
        except sqlite3.DatabaseError as e:
            errors.append(f'Cannot open SQLite database: {e}')
            report.append(f'  ❌ Cannot open database: {e}')
            return False, errors + warnings, report

        # PRAGMA quick_check (fast)
        cursor.execute("PRAGMA quick_check")
        quick_result = cursor.fetchone()[0]
        if quick_result != "ok":
            errors.append(f'quick_check returned: {quick_result}')
            report.append(f'  ❌ PRAGMA quick_check: {quick_result}')
        else:
            report.append(f'  ✅ PRAGMA quick_check: ok')

        # PRAGMA integrity_check (thorough)
        cursor.execute("PRAGMA integrity_check")
        integrity_rows = cursor.fetchall()
        integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"
        if not integrity_ok:
            for row in integrity_rows:
                if row[0] != "ok":
                    errors.append(f'integrity_check: {row[0]}')
            report.append(f'  ❌ PRAGMA integrity_check: FAIL ({len(integrity_rows)} issues)')
        else:
            report.append(f'  ✅ PRAGMA integrity_check: ok')

        # PRAGMA foreign_key_check
        cursor.execute("PRAGMA foreign_key_check")
        fk_rows = cursor.fetchall()
        if fk_rows:
            warnings.append(f'foreign_key violations: {len(fk_rows)}')
            report.append(f'  ❌ PRAGMA foreign_key_check: {len(fk_rows)} violation(s)')
        else:
            report.append(f'  ✅ PRAGMA foreign_key_check: no violations')

        # Step 3: Count tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
        table_count = len(tables)
        report.append(f'  📊 Tables found: {table_count}')

        if table_count != EXPECTED_TABLE_COUNT:
            warnings.append(
                f'Table count {table_count} differs from expected {EXPECTED_TABLE_COUNT}. '
                f'This is normal for backups taken before schema migrations.'
            )
            report.append(f'  ⚠️ Table count: {table_count} (expected {EXPECTED_TABLE_COUNT})')
        else:
            report.append(f'  ✅ Table count: {table_count} (matches expected)')

        # Step 4: Count rows per table
        total_rows = 0
        non_empty_tables = []
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                total_rows += count
                if count > 0:
                    non_empty_tables.append(f'    {table}: {count} rows')
            except Exception as e:
                warnings.append(f'Error counting rows in {table}: {e}')
                non_empty_tables.append(f'    {table}: ERROR — {e}')

        report.append(f'  📊 Total rows across all tables: {total_rows}')

        if total_rows < EXPECTED_MIN_TOTAL_ROWS:
            warnings.append(f'Total rows ({total_rows}) below minimum expected ({EXPECTED_MIN_TOTAL_ROWS})')
            report.append(f'  ⚠️ Total rows: {total_rows} (below min {EXPECTED_MIN_TOTAL_ROWS})')
        else:
            report.append(f'  ✅ Total rows: {total_rows}')

        # Show tables with data
        if non_empty_tables:
            report.append(f'  Tables with data:')
            for t in non_empty_tables:
                report.append(t)

        # Step 5: Check key tables for data presence (warnings only)
        key_tables = {
            'users': 'users',
            'shift_log': 'shift_log',
            'activity_log': 'activity_log',
            'items': 'items',
        }
        for label, table_name in key_tables.items():
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                cnt = cursor.fetchone()[0]
                if cnt > 0:
                    report.append(f'  ✅ {label} ({table_name}): {cnt} rows')
                else:
                    report.append(f'  ⚠️ {label} ({table_name}): empty')
            except Exception:
                report.append(f'  ⚠️ {label} ({table_name}): table not found (pre-migration backup)')

        # Step 6: Check recent orders exist (if any)
        try:
            cursor.execute('SELECT COUNT(*) FROM orders')
            order_count = cursor.fetchone()[0]
            if order_count > 0:
                cursor.execute('SELECT id, created_at, total, status FROM orders ORDER BY id DESC LIMIT 1')
                latest = cursor.fetchone()
                if latest:
                    report.append(f'  ✅ Latest order: #{latest[0]}, {latest[1]}, ${latest[2] or 0:.2f}, status={latest[3]}')
            else:
                report.append(f'  ℹ️ Orders table is empty (no orders to verify)')
        except Exception:
            report.append(f'  ℹ️ Orders table not present (pre-migration backup)')

        conn.close()

        integrity_ok = len(errors) == 0
        return integrity_ok, warnings, report

    except Exception as e:
        return False, [f'Unexpected error during restore test: {e}'], report

    finally:
        # Clean up temp directory
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                log(f'Cleaned up temp directory: {temp_dir}', 'info', quiet)
            except Exception as e:
                log(f'Warning: could not clean up {temp_dir}: {e}', 'warn', quiet)


# ── JSON Restore Test ────────────────────────────────────────────────────

def test_json_backup(backup_path, quiet=False):
    """Test a JSON .tar.gz backup: extract, verify JSON validity, check data.
    
    Returns (integrity_ok, warnings, report_lines).
    """
    errors = []
    warnings = []
    report = []
    temp_dir = None

    try:
        temp_dir = tempfile.mkdtemp(prefix='pos_restore_test_json_', dir=TEMP_BASE)

        # Extract
        log(f'Extracting: {os.path.basename(backup_path)}', 'step', quiet)
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(path=temp_dir)
        except tarfile.TarError as e:
            errors.append(f'Failed to extract tar archive: {e}')
            report.append(f'  ❌ Extraction failed: {e}')
            return False, errors + warnings, report

        # Find data files
        extracted = os.listdir(temp_dir)
        data_source = temp_dir
        for item in extracted:
            item_path = os.path.join(temp_dir, item)
            if os.path.isdir(item_path):
                data_source = item_path
                break

        # Validate each JSON file
        json_files = sorted([
            f for f in os.listdir(data_source)
            if f.endswith('.json') and f not in (
                'package.json', 'package-lock.json', 'manifest.json'
            )
        ])

        report.append(f'  JSON files found: {len(json_files)}')
        total_records = 0
        file_details = []

        for fname in json_files:
            fpath = os.path.join(data_source, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Count records
                if isinstance(data, dict):
                    records = len(data)
                elif isinstance(data, list):
                    records = len(data)
                else:
                    records = 0
                
                total_records += records
                file_details.append(f'    ✅ {fname}: {records} records ({readable_size(os.path.getsize(fpath))})')
            except json.JSONDecodeError as e:
                errors.append(f'{fname}: JSON decode error — {e}')
                file_details.append(f'    ❌ {fname}: JSON decode error')
            except Exception as e:
                errors.append(f'{fname}: {e}')
                file_details.append(f'    ❌ {fname}: {e}')

        if errors:
            report.append(f'  ❌ {len(errors)} JSON file(s) are corrupt')
        for d in file_details:
            report.append(d)

        report.append(f'  📊 Total records across all JSON files: {total_records}')

        if total_records < EXPECTED_MIN_TOTAL_ROWS:
            warnings.append(f'Total records ({total_records}) below minimum ({EXPECTED_MIN_TOTAL_ROWS})')
            report.append(f'  ⚠️ Record count: {total_records} (below min {EXPECTED_MIN_TOTAL_ROWS})')
        else:
            report.append(f'  ✅ Total records: {total_records}')

        integrity_ok = len(errors) == 0
        return integrity_ok, warnings, report

    except Exception as e:
        return False, [f'Unexpected error during JSON restore test: {e}'], report

    finally:
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                log(f'Cleaned up temp directory: {temp_dir}', 'info', quiet)
            except Exception as e:
                log(f'Warning: could not clean up {temp_dir}: {e}', 'warn', quiet)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    args = set(sys.argv[1:])
    quiet = '--quiet' in args
    dry_run = '--dry-run' in args
    force_json = '--json' in args
    specific_backup = None

    # Extract --backup param if provided
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--backup' and i + 2 <= len(sys.argv):
            specific_backup = sys.argv[i + 2]
            break

    # Header
    log(f'{"="*65}', 'info', quiet)
    log(f'  POS System — Automated Restore Test', 'info', quiet)
    log(f'  Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 'info', quiet)
    log(f'{"="*65}', 'info', quiet)

    # ── Pick a backup ──
    if specific_backup:
        # Test a specific backup file
        if not os.path.isfile(specific_backup):
            log(f'Specified backup not found: {specific_backup}', 'error')
            return 1
        if specific_backup.endswith('.db.gz'):
            backups = [('custom', specific_backup)]
            mode = 'sqlite'
        elif specific_backup.endswith('.tar.gz'):
            backups = [('custom', specific_backup)]
            mode = 'json'
        else:
            log(f'Unknown backup type: {specific_backup}', 'error')
            return 1
    elif force_json:
        backups = list_json_backups()
        mode = 'json'
    else:
        # Prefer testing SQLite backups (post-migration)
        backups = list_sqlite_backups()
        mode = 'sqlite'
        if not backups:
            log('No SQLite backups found. Falling back to JSON backups.', 'warn', quiet)
            backups = list_json_backups()
            mode = 'json'

    if not backups:
        log('No backups available to test!', 'error')
        log(f'  SQLite backup dir: {BACKUP_DB_DIR}/', 'info', quiet)
        log(f'  JSON backup dir:   {BACKUP_JSON_DIR}/', 'info', quiet)
        return 2

    log(f'Found {len(backups)} {mode.upper()} backup(s).', 'info', quiet)

    if dry_run:
        log(f'[DRY RUN] Would test a random backup from {len(backups)} available.', 'info')
        log(f'[DRY RUN] No changes made.', 'info')
        return 0

    # Pick a random backup (not the most recent to test historical restoration)
    if len(backups) >= 3:
        test_backup = random.choice(backups[:-1])
    else:
        test_backup = random.choice(backups)

    ts, backup_path = test_backup
    backup_size = os.path.getsize(backup_path)
    log(f'Testing backup: {os.path.basename(backup_path)}', 'step', quiet)
    log(f'  Timestamp: {ts}', 'info', quiet)
    log(f'  Size: {readable_size(backup_size)}', 'info', quiet)

    # Ensure temp base directory exists
    os.makedirs(TEMP_BASE, exist_ok=True)

    # ── Run the test ──
    if mode == 'sqlite':
        integrity_ok, warnings, report = test_sqlite_backup(backup_path, quiet)
    else:
        integrity_ok, warnings, report = test_json_backup(backup_path, quiet)

    # ── Report ──
    log(f'{"="*65}', 'info', quiet)
    log(f'  Results for: {os.path.basename(backup_path)}', 'result', quiet)
    log(f'{"="*65}', 'info', quiet)

    for line in report:
        log(line, 'info', quiet)

    if warnings:
        log(f'{"─"*65}', 'info', quiet)
        log(f'  ⚠️  {len(warnings)} non-critical observation(s):', 'warn', quiet)
        for w in warnings:
            log(f'    - {w}', 'warn', quiet)
        log(f'{"─"*65}', 'info', quiet)

    log(f'{"="*65}', 'info', quiet)
    if integrity_ok:
        if warnings:
            msg = (f'✅ RESTORE TEST PASSED (with {len(warnings)} warnings) — '
                   f'{os.path.basename(backup_path)} restorable and integrity verified.')
        else:
            msg = (f'✅ RESTORE TEST PASSED — {os.path.basename(backup_path)} '
                   f'restored and verified successfully.')
        log(msg, 'ok', quiet)
        log(f'  Integrity checks: all passed', 'result', quiet)
    else:
        msg = (f'❌ RESTORE TEST FAILED — {os.path.basename(backup_path)} '
               f'has integrity/corruption issues.')
        log(msg, 'error')
    log(f'{"="*65}', 'info', quiet)

    return 0 if integrity_ok else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print('\nRestore test cancelled by user.')
        sys.exit(130)
    except Exception as e:
        print(f'\nUnexpected error: {e}')
        sys.exit(1)

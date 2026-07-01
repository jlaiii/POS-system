#!/usr/bin/env python3
"""
POS System — Timesheet Approvals Migration Script
==================================================
Migrates timesheet approval records from timesheet_approvals.json to SQLite
timesheet_approvals table.

The JSON format is an array of approval objects:
  shift_id, user_id, approved_by, approved_at, status, notes

Idempotent: uses INSERT OR REPLACE on a strategy of DELETE previously migrated
entries then INSERT fresh. Since there's no natural unique key, we use a 'source'
column to track JSON-migrated rows.

Currently the JSON store is empty ([]), but this script handles both empty
and populated cases correctly for forward compatibility.

Usage:
    python3 migrations/migrate_timesheet_approvals.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVALS_JSON = os.path.join(PROJECT_ROOT, 'timesheet_approvals.json')


def load_approvals_from_json():
    """Load approvals from timesheet_approvals.json. Returns a list."""
    try:
        with open(APPROVALS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {APPROVALS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {APPROVALS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_timesheet_approvals():
    """Migrate all approvals from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Timesheet Approvals Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading timesheet_approvals.json...")
    approvals = load_approvals_from_json()
    print(f"   Found {len(approvals)} timesheet approval(s) in JSON")

    if not approvals:
        print("⚠️  No timesheet approvals to migrate.")
        db_count = db.row_count('timesheet_approvals')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Approvals in JSON  : 0")
        print(f"    Approvals in SQLite: {db_count}")
        if db_count == 0:
            print("  ✅ Migration COMPLETE — timesheet_approvals table empty, no data to migrate.")
        else:
            print(f"  ❌ Migration COMPLETE WITH ISSUES — expected 0, DB has {db_count}")
        return 0 if db_count == 0 else 1

    # Add 'source' column for idempotency tracking (if not present)
    try:
        col_check = db.query("PRAGMA table_info('timesheet_approvals')")
        col_names = [r['name'] for r in col_check]
        if 'source' not in col_names:
            db.execute("ALTER TABLE timesheet_approvals ADD COLUMN source TEXT DEFAULT ''")
            print("   ℹ️  Added 'source' column to timesheet_approvals table for idempotency tracking")
    except Exception as e:
        print(f"   ⚠️  Could not add source column: {e}")

    # Delete previously migrated entries (where source='json_migrated')
    try:
        db.execute("DELETE FROM timesheet_approvals WHERE source = 'json_migrated'")
    except Exception:
        pass

    insert_sql = """
        INSERT INTO timesheet_approvals (
            shift_id, user_id, approved_by, approved_at,
            status, notes, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for entry in approvals:
        try:
            params = (
                entry.get('shift_id'),
                entry.get('user_id', ''),
                entry.get('approved_by', ''),
                entry.get('approved_at', ''),
                entry.get('status', 'pending'),
                entry.get('notes', ''),
                'json_migrated',
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: shift {params[0]} — user {params[1]} ({params[4]})")
        except Exception as e:
            print(f"   ❌ Error migrating approval: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('timesheet_approvals')
    expected = len(approvals)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Approvals in JSON  : {expected}")
    print(f"    Approvals in SQLite: {db_count}")
    print(f"    Migrated           : {migrated}")
    print(f"    Errors             : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all timesheet approvals migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_timesheet_approvals()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

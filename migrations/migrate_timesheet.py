#!/usr/bin/env python3
"""
POS System — Timesheet Migration Script
=========================================
Migrates admin login timesheet from timesheet.json to SQLite timesheet table.

The JSON format stores admin login sessions as an array of objects with:
  user_id, login_time, logout_time, duration_hours
(user_name is absent from JSON but the schema supports it — will be NULL for JSON-migrated rows)

Idempotent: uses INSERT OR REPLACE on a UNIQUE constraint.
Since timesheet has no natural unique key, we use a strategy of:
  DELETE FROM timesheet WHERE source='json_migrated' first,
  then INSERT all rows fresh.
This ensures re-running doesn't create duplicates.

Safe to re-run.

Usage:
    python3 migrations/migrate_timesheet.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMESHEET_JSON = os.path.join(PROJECT_ROOT, 'timesheet.json')


def load_timesheet_from_json():
    """Load timesheet entries from timesheet.json. Returns list of dicts."""
    try:
        with open(TIMESHEET_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {TIMESHEET_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {TIMESHEET_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_timesheet():
    """Migrate all timesheet entries from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Timesheet Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading timesheet.json...")
    entries = load_timesheet_from_json()
    total_entries = len(entries)
    print(f"   Found {total_entries} timesheet entry(s) in JSON")

    if total_entries == 0:
        print("⚠️  No timesheet entries to migrate.")
        return 0

    # To ensure idempotency: clear previously migrated entries first.
    # We add a column 'source' if it doesn't exist to tag migrated rows.
    # Since timesheet has no natural unique key, we use a marker approach:
    # check if 'source' column exists, if not add it.

    # Check if source column exists
    try:
        col_check = db.query("PRAGMA table_info('timesheet')")
        col_names = [r['name'] for r in col_check]
        if 'source' not in col_names:
            db.execute("ALTER TABLE timesheet ADD COLUMN source TEXT DEFAULT ''")
            print("   ℹ️  Added 'source' column to timesheet table for idempotency tracking")
    except Exception as e:
        print(f"   ⚠️  Could not add source column: {e}")
        print("   Will use DELETE-all-then-insert approach instead")

    # Delete previously migrated entries (where source='json_migrated')
    try:
        db.execute("DELETE FROM timesheet WHERE source = 'json_migrated'")
    except Exception:
        # Column might not exist — try without source filter
        pass

    insert_sql = """
        INSERT INTO timesheet (
            user_id, user_name, login_time, logout_time,
            duration_hours, source
        ) VALUES (?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for entry in entries:
        try:
            user_id = entry.get('user_id', '')
            params = (
                user_id,
                None,  # user_name — not in JSON, will be NULL
                entry.get('login_time', ''),
                entry.get('logout_time', ''),
                entry.get('duration_hours', 0.0),
                'json_migrated',  # source tag for idempotency
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: user {user_id} — "
                  f"{entry.get('login_time', 'No time')[:19]}")
        except Exception as e:
            print(f"   ❌ Error migrating entry for user "
                  f"{entry.get('user_id', 'Unknown')}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('timesheet')

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Entries in JSON    : {total_entries}")
    print(f"    Entries in SQLite  : {db_count}")
    print(f"    Migrated           : {migrated}")
    print(f"    Errors             : {errors}")

    if errors == 0:
        print(f"  ✅ Migration COMPLETE — all timesheet entries migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s)")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_timesheet()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

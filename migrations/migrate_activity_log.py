#!/usr/bin/env python3
"""
POS System — Activity Log Migration Script
============================================
Migrates activity_log from activity_log.json to SQLite activity_log table.

Idempotent: clears the table before inserting (no natural unique key in JSON).
Re-runnable: same results every time.

Usage:
    python3 migrations/migrate_activity_log.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIVITY_LOG_JSON = os.path.join(PROJECT_ROOT, 'activity_log.json')


def load_activity_log_from_json():
    """Load activity log from activity_log.json. Returns a list of event dicts."""
    try:
        with open(ACTIVITY_LOG_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {ACTIVITY_LOG_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {ACTIVITY_LOG_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_activity_log():
    """Migrate all activity log entries from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Activity Log Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading activity_log.json...")
    events = load_activity_log_from_json()
    print(f"   Found {len(events)} event(s) in JSON")

    if not events:
        print("⚠️  No events to migrate.")
        return 0

    # Clear existing rows (idempotency: always start fresh)
    print("🧹 Clearing existing activity_log rows...")
    db.execute("DELETE FROM activity_log")

    # Prepare insert statement — no id since it's AUTOINCREMENT
    insert_sql = """
        INSERT INTO activity_log (
            timestamp, type, user_id, user_role, details
        ) VALUES (?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for idx, event in enumerate(events, 1):
        try:
            # Serialize details as JSON text
            details_val = json.dumps(event.get('details', {}), default=str)

            params = (
                event.get('timestamp', ''),
                event.get('type', ''),
                event.get('user_id'),
                event.get('user_role'),
                details_val,
            )
            db.execute(insert_sql, params)
            migrated += 1

            # Print progress every 50 entries to avoid overwhelming output
            if idx % 50 == 0 or idx == len(events):
                print(f"   ✓ Migrated {idx}/{len(events)} events...")

        except Exception as e:
            print(f"   ❌ Error migrating event {idx} (type={event.get('type')}): {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('activity_log')
    expected = len(events)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Events in JSON   : {expected}")
    print(f"    Events in SQLite : {db_count}")
    print(f"    Migrated         : {migrated}")
    print(f"    Errors           : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all events migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_activity_log()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

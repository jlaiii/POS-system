#!/usr/bin/env python3
"""
POS System — Waste Log Migration Script
========================================
Migrates waste log entries from waste_log.json to SQLite waste_log table.

Idempotent: uses INSERT OR REPLACE (though waste_log uses AUTOINCREMENT id,
so we use INSERT OR IGNORE with explicit id matching — duplicate-safe).

Verifies row count matches JSON record count.

Usage:
    python3 migrations/migrate_waste_log.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WASTE_LOG_JSON = os.path.join(PROJECT_ROOT, 'waste_log.json')


def load_waste_log_from_json():
    """Load waste log from waste_log.json. Returns a list of waste entries."""
    try:
        with open(WASTE_LOG_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {WASTE_LOG_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {WASTE_LOG_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_waste_log():
    """Migrate all waste log entries from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Waste Log Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading waste_log.json...")
    waste_entries = load_waste_log_from_json()
    print(f"   Found {len(waste_entries)} waste log entry(ies) in JSON")

    if not waste_entries:
        print("⚠️  No waste log entries to migrate.")
        db_count = db.row_count('waste_log')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Waste entries in JSON  : 0")
        print(f"    Waste entries in SQLite: {db_count}")
        if db_count == 0:
            print("  ✅ Migration COMPLETE — waste_log table empty, no data to migrate.")
        else:
            print(f"  ❌ Migration COMPLETE WITH ISSUES — expected 0, DB has {db_count}")
        return 0 if db_count == 0 else 1

    # Prepare insert statement
    # waste_log uses AUTOINCREMENT id. For idempotency we INSERT OR IGNORE
    # using the original id from JSON (if present) to avoid duplicates.
    insert_sql = """
        INSERT OR IGNORE INTO waste_log (
            id, timestamp, item_name, quantity, reason,
            estimated_cost, notes, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for entry in waste_entries:
        try:
            params = (
                entry.get('id'),
                entry.get('timestamp'),
                entry.get('item_name', ''),
                entry.get('quantity', 0),
                entry.get('reason', ''),
                entry.get('estimated_cost', 0.0),
                entry.get('notes', ''),
                entry.get('user_id', ''),
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {entry.get('item_name', 'Unknown')} "
                  f"(qty: {params[3]}) — {entry.get('reason', 'no reason')[:40]}")
        except Exception as e:
            print(f"   ❌ Error migrating waste entry: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('waste_log')
    expected = len(waste_entries)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Waste entries in JSON  : {expected}")
    print(f"    Waste entries in SQLite: {db_count}")
    print(f"    Migrated               : {migrated}")
    print(f"    Errors                 : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all waste log entries migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_waste_log()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

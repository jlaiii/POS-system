#!/usr/bin/env python3
"""
POS System — Shift Log Migration Script
========================================
Migrates shift_log from shift_log.json to SQLite shift_log table.

Idempotent: clears the table before inserting (since there's no natural
unique key in the JSON data — shifts use autoincrement IDs).

Usage:
    python3 migrations/migrate_shift_log.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT_LOG_JSON = os.path.join(PROJECT_ROOT, 'shift_log.json')


def load_shifts_from_json():
    """Load shifts from shift_log.json. Returns a list of shift dicts."""
    try:
        with open(SHIFT_LOG_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {SHIFT_LOG_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {SHIFT_LOG_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_shift_log():
    """Migrate all shifts from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Shift Log Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading shift_log.json...")
    shifts = load_shifts_from_json()
    print(f"   Found {len(shifts)} shift(s) in JSON")

    if not shifts:
        print("⚠️  No shifts to migrate.")
        return 0

    # Clear existing rows (idempotency: always start fresh)
    print("🧹 Clearing existing shift_log rows...")
    db.execute("DELETE FROM shift_log")

    # Prepare insert statement — no id since it's AUTOINCREMENT
    insert_sql = """
        INSERT INTO shift_log (
            user_id, user_name, clock_in_time, clock_out_time,
            duration_hours, breaks, break_hours, paid_hours,
            scheduled_start, late_minutes, late_excused, late_note,
            notes, edits
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for idx, shift in enumerate(shifts, 1):
        try:
            # Convert booleans to integers
            late_excused = shift.get('late_excused', False)
            if isinstance(late_excused, bool):
                late_excused = 1 if late_excused else 0
            elif isinstance(late_excused, int):
                pass
            else:
                late_excused = 0

            # Serialize arrays/objects as JSON text
            breaks_val = json.dumps(shift.get('breaks', []))
            edits_val = json.dumps(shift.get('edits', []))

            # Handle missing numeric fields
            break_hours = shift.get('break_hours')
            paid_hours = shift.get('paid_hours')
            late_minutes = shift.get('late_minutes')
            scheduled_start = shift.get('scheduled_start')
            late_note = shift.get('late_note')
            notes = shift.get('notes')

            params = (
                shift.get('user_id', ''),
                shift.get('user_name', ''),
                shift.get('clock_in_time'),
                shift.get('clock_out_time'),
                shift.get('duration_hours', 0.0),
                breaks_val,
                break_hours,
                paid_hours,
                scheduled_start,
                late_minutes,
                late_excused,
                late_note,
                notes,
                edits_val,
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated shift {idx}: user={shift.get('user_id')} "
                  f"in={shift.get('clock_in_time', '?')[:19]}")
        except Exception as e:
            print(f"   ❌ Error migrating shift {idx} (user={shift.get('user_id')}): {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('shift_log')
    expected = len(shifts)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Shifts in JSON   : {expected}")
    print(f"    Shifts in SQLite : {db_count}")
    print(f"    Migrated         : {migrated}")
    print(f"    Errors           : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all shifts migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_shift_log()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""
POS System — Security Events Migration Script
===============================================
Migrates security events from security_events.json to SQLite security_events table.

The security_events.json stores incident reports from Security Watchdog/Sentinel
with rich metadata (summary, detail, affected_user, etc.). The mapped columns
(category→event_type, affected_user→user_id, severity, created_at→timestamp, 
resolved_at, resolved) capture the indexed searchable fields. All extra data
(summary, detail, affected_user_name, related_event, reported_by, resolution,
and the original incident id) is stored as JSON in the details column.

Idempotent: uses DELETE + INSERT (re-creates from JSON each run).
Safe to re-run.

Usage:
    python3 migrations/migrate_security_events.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECURITY_EVENTS_JSON = os.path.join(PROJECT_ROOT, 'security_events.json')


def load_security_events_from_json():
    """Load security events from security_events.json. Returns list of event dicts."""
    try:
        with open(SECURITY_EVENTS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {SECURITY_EVENTS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {SECURITY_EVENTS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_security_events():
    """Migrate all security events from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Security Events Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading security_events.json...")
    events = load_security_events_from_json()
    print(f"   Found {len(events)} event(s) in JSON")

    if not events:
        print("⚠️  No security events to migrate.")
        db.execute("DELETE FROM security_events")
        print("   ✅ Cleared existing security_events table (0 rows).")
        return 0

    # Clear existing rows (idempotency: always start fresh)
    print("🧹 Clearing existing security_events rows...")
    db.execute("DELETE FROM security_events")

    # Prepare insert statement
    insert_sql = """
        INSERT INTO security_events (
            timestamp, event_type, ip_address, user_id,
            severity, details, resolved, resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for idx, event in enumerate(events):
        try:
            # Build details object with all extra fields not mapped to dedicated columns
            details = {
                'id': event.get('id'),
                'status': event.get('status'),
                'summary': event.get('summary'),
                'detail': event.get('detail'),
                'affected_user_name': event.get('affected_user_name'),
                'related_event': event.get('related_event'),
                'reported_by': event.get('reported_by'),
                'resolution': event.get('resolution'),
            }
            # Remove None values for cleaner JSON
            details = {k: v for k, v in details.items() if v is not None}

            params = (
                event.get('created_at'),              # timestamp
                event.get('category', ''),             # event_type
                '',                                    # ip_address (not available in source)
                event.get('affected_user'),            # user_id
                event.get('severity', 'info'),          # severity
                json.dumps(details),                   # details (all extra fields)
                1 if event.get('status') == 'resolved' else 0,  # resolved
                event.get('resolved_at'),              # resolved_at
            )
            db.execute(insert_sql, params)
            migrated += 1
            if (idx + 1) % 10 == 0:
                print(f"   ✓ Migrated {idx + 1}/{len(events)} events...")
        except Exception as e:
            print(f"   ❌ Error migrating event {event.get('id', '?')}: {e}")
            errors += 1

    if migrated > 0:
        print(f"   ✓ Migrated final batch — {migrated}/{len(events)} events")

    # Verify row count
    db_count = db.row_count('security_events')
    expected = len(events)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Events in JSON  : {expected}")
    print(f"    Events in SQLite: {db_count}")
    print(f"    Migrated        : {migrated}")
    print(f"    Errors          : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all security events migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_security_events()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

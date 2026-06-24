#!/usr/bin/env python3
"""
POS System — Loyalty Points Migration Script
==============================================
Migrates loyalty points from loyalty_points.json to SQLite loyalty_points table.

The JSON is a flat dict keyed by phone number, e.g.:
    {
        "555-9999": {
            "phone": "555-9999",
            "name": "555-9999",
            "email": "",
            "notes": "",
            "address": "",
            "points": 12,
            "total_earned": 12,
            "total_redeemed": 0,
            "total_spent": 12.0,
            "total_orders": 1,
            "last_visit": "2026-06-23T19:19:59.291274",
            "created_at": "2026-06-23T19:19:59.291240",
            "history": [{"type": "earned", "points": 12, ...}]
        },
        ...
    }

Idempotent: uses INSERT OR REPLACE, safe to re-run.
Verifies row count matches JSON record count.

Usage:
    python3 migrations/migrate_loyalty_points.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOYALTY_JSON = os.path.join(PROJECT_ROOT, 'loyalty_points.json')


def load_loyalty_points_from_json():
    """Load loyalty points from loyalty_points.json. Returns dict keyed by phone."""
    try:
        with open(LOYALTY_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {LOYALTY_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {LOYALTY_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_loyalty_points():
    """Migrate all loyalty point records from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Loyalty Points Migration")
    print("=" * 60)

    # Initialize database tables (runs schema migration too)
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading loyalty_points.json...")
    loyalty = load_loyalty_points_from_json()
    print(f"   Found {len(loyalty)} record(s) in JSON")

    if not loyalty:
        print("⚠️  No loyalty points to migrate.")
        return 0

    # Prepare insert statement — uses INSERT OR REPLACE for idempotency
    insert_sql = """
        INSERT OR REPLACE INTO loyalty_points (
            phone, name, email, notes, address,
            points, total_earned, total_redeemed, total_spent, total_orders,
            last_visit, created_at, history
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for phone, record in sorted(loyalty.items()):
        try:
            params = (
                record.get('phone', phone),
                record.get('name', ''),
                record.get('email', ''),
                record.get('notes', ''),
                record.get('address', ''),
                record.get('points', 0),
                record.get('total_earned', 0),
                record.get('total_redeemed', 0),
                record.get('total_spent', 0),
                record.get('total_orders', 0),
                record.get('last_visit'),
                record.get('created_at'),
                json.dumps(record.get('history', [])),
            )
            db.execute(insert_sql, params)
            migrated += 1
            name_display = record.get('name', phone)
            points = record.get('points', 0)
            print(f"   ✓ Migrated: {phone} ({name_display}, {points} pts)")
        except Exception as e:
            print(f"   ❌ Error migrating loyalty record {phone}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('loyalty_points')
    expected = len(loyalty)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Records in JSON  : {expected}")
    print(f"    Records in SQLite: {db_count}")
    print(f"    Migrated         : {migrated}")
    print(f"    Errors           : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all loyalty points migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_loyalty_points()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

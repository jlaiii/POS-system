#!/usr/bin/env python3
"""
POS System — Refunded Orders Migration Script
===============================================
Migrates refunded orders from refunded_orders.json to SQLite refunded_orders table.

refunded_orders.json stores an array of objects:
  {
    "order_id": <int>,
    "original_order": { ... full original order object ... },
    "reason": "<string>",
    "refunded_at": "<ISO timestamp>",
    "refunded_by": "<user PIN>"
  }

The original_order is stored as JSON TEXT.
Idempotent: DELETE + re-INSERT (safe to re-run).

Usage:
    python3 migrations/migrate_refunded_orders.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFUNDED_ORDERS_JSON = os.path.join(PROJECT_ROOT, 'refunded_orders.json')


def load_refunded_orders_from_json():
    """Load refunded orders from refunded_orders.json. Returns list."""
    try:
        with open(REFUNDED_ORDERS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {REFUNDED_ORDERS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {REFUNDED_ORDERS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_refunded_orders():
    """Migrate all refunded orders from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Refunded Orders Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # ── Migrate refunded orders ─────────────────────────────────────────────
    print("\n📖 Reading refunded_orders.json...")
    refunded_orders = load_refunded_orders_from_json()
    print(f"   Found {len(refunded_orders)} refunded order(s) in JSON")

    # Clear existing rows (idempotency: always start fresh)
    print("🧹 Clearing existing refunded_orders rows...")
    db.execute("DELETE FROM refunded_orders")

    if refunded_orders:
        migrated = 0
        errors = 0

        insert_sql = """
            INSERT INTO refunded_orders (
                order_id, original_order, reason, refunded_at, refunded_by
            ) VALUES (?, ?, ?, ?, ?)
        """

        for idx, entry in enumerate(refunded_orders):
            try:
                params = (
                    entry.get('order_id'),
                    json.dumps(entry.get('original_order', {})),
                    entry.get('reason', ''),
                    entry.get('refunded_at'),
                    entry.get('refunded_by'),
                )
                db.execute(insert_sql, params)
                migrated += 1
                if (idx + 1) % 20 == 0 or (idx + 1) == len(refunded_orders):
                    print(f"   ✓ Migrated {idx + 1}/{len(refunded_orders)} refunded orders...")
            except Exception as e:
                print(f"   ❌ Error migrating refunded order #{entry.get('order_id', '?')}: {e}")
                errors += 1

        if migrated > 0:
            print(f"   ✓ Migrated final batch — {migrated}/{len(refunded_orders)} refunded orders")
    else:
        print("   No refunded orders to migrate (empty array).")
        migrated = 0
        errors = 0

    # Verify row counts
    db_count = db.row_count('refunded_orders')
    expected = len(refunded_orders)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Refunded Orders JSON   : {expected}")
    print(f"    Refunded Orders SQLite : {db_count}")
    print(f"    Migrated               : {migrated}")
    print(f"    Errors                 : {errors}")

    all_ok = (db_count == expected and errors == 0)
    if all_ok:
        print(f"  ✅ Migration COMPLETE — all {expected} refunded orders migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — see above")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_refunded_orders()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

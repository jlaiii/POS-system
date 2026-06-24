#!/usr/bin/env python3
"""
POS System — Inventory Migration Script
=========================================
Migrates inventory from inventory.json to SQLite inventory table.

The JSON is a flat dict keyed by item_name, e.g.:
    {
        "Item Name": {
            "stock": 100,
            "low_stock_threshold": 10
        },
        ...
    }

Maps 'low_stock_threshold' → SQLite 'threshold' column.
'unit' and 'last_updated' default to NULL (not present in current JSON).

Idempotent: uses INSERT OR REPLACE, safe to re-run.
Verifies row count matches JSON record count.

Usage:
    python3 migrations/migrate_inventory.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVENTORY_JSON = os.path.join(PROJECT_ROOT, 'inventory.json')


def load_inventory_from_json():
    """Load inventory from inventory.json. Returns dict keyed by item_name."""
    try:
        with open(INVENTORY_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {INVENTORY_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {INVENTORY_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_inventory():
    """Migrate all inventory items from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Inventory Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading inventory.json...")
    inventory = load_inventory_from_json()
    print(f"   Found {len(inventory)} item(s) in JSON")

    if not inventory:
        print("⚠️  No inventory items to migrate.")
        return 0

    # Prepare insert statement — uses INSERT OR REPLACE for idempotency
    insert_sql = """
        INSERT OR REPLACE INTO inventory (
            item_name, stock, threshold, unit, last_updated
        ) VALUES (?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for item_name, item_data in sorted(inventory.items()):
        try:
            stock = item_data.get('stock', 0)
            # Map 'low_stock_threshold' from JSON to 'threshold' in SQLite
            threshold = item_data.get('low_stock_threshold', 10)
            # 'unit' and 'last_updated' not present in current JSON; default to NULL
            params = (
                item_name,
                stock,
                threshold,
                None,  # unit — not in JSON yet, defaults to NULL
                None,  # last_updated — not in JSON yet, defaults to NULL
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {item_name} (stock={stock}, threshold={threshold})")
        except Exception as e:
            print(f"   ❌ Error migrating item '{item_name}': {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('inventory')
    expected = len(inventory)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Items in JSON      : {expected}")
    print(f"    Items in SQLite    : {db_count}")
    print(f"    Migrated           : {migrated}")
    print(f"    Errors             : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all inventory items migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_inventory()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

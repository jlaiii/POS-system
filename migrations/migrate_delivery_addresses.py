#!/usr/bin/env python3
"""
POS System — Delivery Addresses Migration Script
=================================================
Migrates delivery address records from delivery_addresses.json to SQLite
delivery_addresses table.

The JSON format is a dict keyed by address_id (or empty dict {}):
  { "addr_001": { "customer_name": "...", "phone": "...", ... } }

Idempotent: uses INSERT OR REPLACE with source='json_migrated' tracking.

Currently the JSON store is empty ({}), but this script handles both empty
and populated cases correctly for forward compatibility.

Usage:
    python3 migrations/migrate_delivery_addresses.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDRESSES_JSON = os.path.join(PROJECT_ROOT, 'delivery_addresses.json')


def load_addresses_from_json():
    """Load addresses from delivery_addresses.json. Returns a dict keyed by address_id."""
    try:
        with open(ADDRESSES_JSON, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            # Handle case where JSON is a list of address objects
            return {f"addr_{i}": addr for i, addr in enumerate(data)}
        else:
            print(f"⚠️  Unexpected data format in {ADDRESSES_JSON}: {type(data).__name__}")
            return {}
    except FileNotFoundError:
        print(f"❌ Error: {ADDRESSES_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {ADDRESSES_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_delivery_addresses():
    """Migrate all delivery addresses from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Delivery Addresses Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading delivery_addresses.json...")
    addresses = load_addresses_from_json()
    print(f"   Found {len(addresses)} delivery address(es) in JSON")

    if not addresses:
        print("⚠️  No delivery addresses to migrate.")
        db_count = db.row_count('delivery_addresses')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Addresses in JSON  : 0")
        print(f"    Addresses in SQLite: {db_count}")
        if db_count == 0:
            print("  ✅ Migration COMPLETE — delivery_addresses table empty, no data to migrate.")
        else:
            print(f"  ❌ Migration COMPLETE WITH ISSUES — expected 0, DB has {db_count}")
        return 0 if db_count == 0 else 1

    # Add 'source' column for idempotency tracking (if not present)
    try:
        col_check = db.query("PRAGMA table_info('delivery_addresses')")
        col_names = [r['name'] for r in col_check]
        if 'source' not in col_names:
            db.execute("ALTER TABLE delivery_addresses ADD COLUMN source TEXT DEFAULT ''")
            print("   ℹ️  Added 'source' column to delivery_addresses table for idempotency tracking")
    except Exception as e:
        print(f"   ⚠️  Could not add source column: {e}")

    # Delete previously migrated entries (where source='json_migrated')
    try:
        db.execute("DELETE FROM delivery_addresses WHERE source = 'json_migrated'")
    except Exception:
        pass

    insert_sql = """
        INSERT INTO delivery_addresses (
            address_id, customer_name, phone,
            address_line1, address_line2, city, state, zip_code,
            instructions, created_at, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for addr_id, addr in addresses.items():
        try:
            params = (
                addr_id,
                addr.get('customer_name', ''),
                addr.get('phone', ''),
                addr.get('address_line1', ''),
                addr.get('address_line2', ''),
                addr.get('city', ''),
                addr.get('state', ''),
                addr.get('zip_code', ''),
                addr.get('instructions', ''),
                addr.get('created_at', ''),
                'json_migrated',
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {addr_id} — {params[1]}")
        except Exception as e:
            print(f"   ❌ Error migrating address {addr_id}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('delivery_addresses')
    expected = len(addresses)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Addresses in JSON  : {expected}")
    print(f"    Addresses in SQLite: {db_count}")
    print(f"    Migrated           : {migrated}")
    print(f"    Errors             : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all delivery addresses migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_delivery_addresses()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

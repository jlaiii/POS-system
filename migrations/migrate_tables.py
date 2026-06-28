#!/usr/bin/env python3
"""
POS System — Tables Migration Script
======================================
Migrates restaurant tables from tables.json to SQLite tables_config table.

tables.json stores a dict keyed by table number:
  {
    "1": {
      "number": 1,
      "name": "Patio 1",
      "tablet_id": "",
      "status": "available",
      "section": "Patio",
      "capacity": 2,
      "created_at": "2026-06-25T10:24:39.519403",
      "last_bussed_at": null
    },
    ...
  }

Idempotent: INSERT OR REPLACE (safe to re-run).
Table schema includes created_at + last_bussed_at columns.

Usage:
    python3 migrations/migrate_tables.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES_JSON = os.path.join(PROJECT_ROOT, 'tables.json')


def load_tables_from_json():
    """Load tables from tables.json. Returns dict keyed by table number."""
    try:
        with open(TABLES_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {TABLES_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {TABLES_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_tables():
    """Migrate all tables from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Tables Migration")
    print("=" * 60)

    # Initialize database tables (applies schema migrations too)
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # ── Migrate tables ──────────────────────────────────────────────────────
    print("\n📖 Reading tables.json...")
    tables_dict = load_tables_from_json()
    print(f"   Found {len(tables_dict)} table(s) in JSON")

    if not tables_dict:
        print("   No tables to migrate (empty dict).")
        db.execute("DELETE FROM tables_config")
        db_count = db.row_count('tables_config')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Tables JSON   : 0")
        print(f"    Tables SQLite : {db_count}")
        print(f"  ✅ Migration COMPLETE — 0 tables to migrate.")
        return 0

    migrated = 0
    errors = 0

    insert_sql = """
        INSERT OR REPLACE INTO tables_config (
            table_number, name, capacity, status, tablet_id, section,
            visible, created_at, last_bussed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for table_key, table_data in tables_dict.items():
        try:
            table_number = table_data.get('number')
            if table_number is None:
                # Fallback: use the dict key
                try:
                    table_number = int(table_key)
                except (ValueError, TypeError):
                    print(f"   ⚠️  Skipping table with key '{table_key}' — no valid number")
                    errors += 1
                    continue

            params = (
                table_number,
                table_data.get('name', f"Table {table_number}"),
                table_data.get('capacity', 4),
                table_data.get('status', 'available'),
                table_data.get('tablet_id', ''),
                table_data.get('section', ''),
                1,  # visible: default to 1 (not in JSON)
                table_data.get('created_at'),
                table_data.get('last_bussed_at'),  # can be None/null
            )
            db.execute(insert_sql, params)
            migrated += 1
        except Exception as e:
            print(f"   ❌ Error migrating table #{table_data.get('number', '?')}: {e}")
            errors += 1

    if migrated > 0:
        print(f"   ✓ Migrated {migrated}/{len(tables_dict)} tables")

    # Verify row counts
    db_count = db.row_count('tables_config')
    expected = len(tables_dict)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Tables JSON   : {expected}")
    print(f"    Tables SQLite : {db_count}")
    print(f"    Migrated      : {migrated}")
    print(f"    Errors        : {errors}")

    all_ok = (db_count == expected and errors == 0)
    if all_ok:
        print(f"  ✅ Migration COMPLETE — all {expected} tables migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — see above")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_tables()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

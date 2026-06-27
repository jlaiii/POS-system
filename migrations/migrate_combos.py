#!/usr/bin/env python3
"""
POS System — Combos Migration Script
=====================================
Migrates combos from combos.json to SQLite combos table.

The JSON format is:
    {"combos": [{"id": "combo_...", "name": "...", "combo_price": 13.99,
                 "description": "...", "child_items": [...], "active": true,
                 "created_at": "...", "updated_at": "..."}]}

Idempotent: uses INSERT OR REPLACE via combo_id UNIQUE, safe to re-run.
Verifies row count matches JSON record count.

Usage:
    python3 migrations/migrate_combos.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMBOS_JSON = os.path.join(PROJECT_ROOT, 'combos.json')


def load_combos_from_json():
    """Load combos from combos.json. Returns list of combo dicts."""
    try:
        with open(COMBOS_JSON, 'r') as f:
            data = json.load(f)
            # Format: {"combos": [...]}
            return data.get('combos', [])
    except FileNotFoundError:
        print(f"❌ Error: {COMBOS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {COMBOS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_combos():
    """Migrate all combos from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Combos Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading combos.json...")
    combos = load_combos_from_json()
    print(f"   Found {len(combos)} combo(s) in JSON")

    if not combos:
        print("⚠️  No combos to migrate.")
        return 0

    # Prepare insert statement
    insert_sql = """
        INSERT OR REPLACE INTO combos (
            combo_id, name, combo_price, description, child_items,
            active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for combo in combos:
        try:
            params = (
                combo.get('id'),
                combo.get('name', ''),
                combo.get('combo_price', 0),
                combo.get('description', ''),
                json.dumps(combo.get('child_items', [])),
                1 if combo.get('active', True) else 0,
                combo.get('created_at'),
                combo.get('updated_at'),
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {combo.get('id')} ({combo.get('name', 'Unknown')})")
        except Exception as e:
            print(f"   ❌ Error migrating combo {combo.get('id', 'unknown')}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('combos')
    expected = len(combos)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Combos in JSON  : {expected}")
    print(f"    Combos in SQLite: {db_count}")
    print(f"    Migrated       : {migrated}")
    print(f"    Errors         : {errors}")

    if db_count >= expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all combos migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_combos()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

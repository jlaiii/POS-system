#!/usr/bin/env python3
"""
POS System — Scheduled Pricing Migration Script
================================================
Migrates scheduled pricing rules from scheduled_pricing.json to SQLite
scheduled_pricing table.

The JSON format is an array of pricing rule objects (or empty array []):
  [{ "rule_id": 1, "name": "Happy Hour", "discount_type": "percent", ... }]

Idempotent: uses INSERT OR REPLACE on rule_id with source='json_migrated' tracking.

Currently the JSON store is empty ([]), but this script handles both empty
and populated cases correctly for forward compatibility.

Usage:
    python3 migrations/migrate_scheduled_pricing.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICING_JSON = os.path.join(PROJECT_ROOT, 'scheduled_pricing.json')


def load_pricing_from_json():
    """Load pricing rules from scheduled_pricing.json. Returns a list."""
    try:
        with open(PRICING_JSON, 'r') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Handle case where JSON is an object with rules
            if 'rules' in data:
                return data['rules']
            # Could be a dict of rule objects
            return list(data.values())
        else:
            print(f"⚠️  Unexpected data format in {PRICING_JSON}: {type(data).__name__}")
            return []
    except FileNotFoundError:
        print(f"❌ Error: {PRICING_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {PRICING_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_scheduled_pricing():
    """Migrate all scheduled pricing rules from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Scheduled Pricing Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading scheduled_pricing.json...")
    rules = load_pricing_from_json()
    print(f"   Found {len(rules)} scheduled pricing rule(s) in JSON")

    if not rules:
        print("⚠️  No scheduled pricing rules to migrate.")
        db_count = db.row_count('scheduled_pricing')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Rules in JSON  : 0")
        print(f"    Rules in SQLite: {db_count}")
        if db_count == 0:
            print("  ✅ Migration COMPLETE — scheduled_pricing table empty, no data to migrate.")
        else:
            print(f"  ❌ Migration COMPLETE WITH ISSUES — expected 0, DB has {db_count}")
        return 0 if db_count == 0 else 1

    # Add 'source' column for idempotency tracking (if not present)
    try:
        col_check = db.query("PRAGMA table_info('scheduled_pricing')")
        col_names = [r['name'] for r in col_check]
        if 'source' not in col_names:
            db.execute("ALTER TABLE scheduled_pricing ADD COLUMN source TEXT DEFAULT ''")
            print("   ℹ️  Added 'source' column to scheduled_pricing table for idempotency tracking")
    except Exception as e:
        print(f"   ⚠️  Could not add source column: {e}")

    # Delete previously migrated entries (where source='json_migrated')
    try:
        db.execute("DELETE FROM scheduled_pricing WHERE source = 'json_migrated'")
    except Exception:
        pass

    insert_sql = """
        INSERT INTO scheduled_pricing (
            rule_id, name, discount_type, value,
            start_time, end_time, days_of_week,
            active, created_at, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for rule in rules:
        try:
            rule_id = rule.get('rule_id', rule.get('id'))
            if rule_id is None:
                print(f"   ⚠️  Skipping rule without rule_id: {rule.get('name', 'unknown')}")
                continue

            params = (
                rule_id,
                rule.get('name', ''),
                rule.get('discount_type', 'percent'),
                rule.get('value', 0),
                rule.get('start_time', ''),
                rule.get('end_time', ''),
                json.dumps(rule.get('days_of_week', [])),
                rule.get('active', 1),
                rule.get('created_at', ''),
                'json_migrated',
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: rule {rule_id} — {params[1]}")
        except Exception as e:
            print(f"   ❌ Error migrating pricing rule: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('scheduled_pricing')
    expected = len(rules)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Rules in JSON  : {expected}")
    print(f"    Rules in SQLite: {db_count}")
    print(f"    Migrated       : {migrated}")
    print(f"    Errors         : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all scheduled pricing rules migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_scheduled_pricing()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

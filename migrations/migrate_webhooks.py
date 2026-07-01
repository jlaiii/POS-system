#!/usr/bin/env python3
"""
POS System — Webhooks Migration Script
=======================================
Migrates webhook configurations from webhooks.json to SQLite webhooks table.

The JSON format is a dict keyed by webhook name (or empty dict {}):
  { "order_webhook": { "url": "https://...", "events": ["order_created"], ... } }

Idempotent: uses INSERT OR REPLACE on name with source='json_migrated' tracking.

Currently the JSON store is empty ({}), but this script handles both empty
and populated cases correctly for forward compatibility.

Usage:
    python3 migrations/migrate_webhooks.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBHOOKS_JSON = os.path.join(PROJECT_ROOT, 'webhooks.json')


def load_webhooks_from_json():
    """Load webhooks from webhooks.json. Returns a dict keyed by name."""
    try:
        with open(WEBHOOKS_JSON, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            # Handle case where JSON is a list of webhook objects
            return {wh.get('name', f'webhook_{i}'): wh for i, wh in enumerate(data)}
        else:
            print(f"⚠️  Unexpected data format in {WEBHOOKS_JSON}: {type(data).__name__}")
            return {}
    except FileNotFoundError:
        print(f"❌ Error: {WEBHOOKS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {WEBHOOKS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_webhooks():
    """Migrate all webhooks from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Webhooks Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading webhooks.json...")
    webhooks = load_webhooks_from_json()
    print(f"   Found {len(webhooks)} webhook(s) in JSON")

    if not webhooks:
        print("⚠️  No webhooks to migrate.")
        db_count = db.row_count('webhooks')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Webhooks in JSON  : 0")
        print(f"    Webhooks in SQLite: {db_count}")
        if db_count == 0:
            print("  ✅ Migration COMPLETE — webhooks table empty, no data to migrate.")
        else:
            print(f"  ❌ Migration COMPLETE WITH ISSUES — expected 0, DB has {db_count}")
        return 0 if db_count == 0 else 1

    # Add 'source' column for idempotency tracking (if not present)
    try:
        col_check = db.query("PRAGMA table_info('webhooks')")
        col_names = [r['name'] for r in col_check]
        if 'source' not in col_names:
            db.execute("ALTER TABLE webhooks ADD COLUMN source TEXT DEFAULT ''")
            print("   ℹ️  Added 'source' column to webhooks table for idempotency tracking")
    except Exception as e:
        print(f"   ⚠️  Could not add source column: {e}")

    # Delete previously migrated entries (where source='json_migrated')
    try:
        db.execute("DELETE FROM webhooks WHERE source = 'json_migrated'")
    except Exception:
        pass

    insert_sql = """
        INSERT INTO webhooks (
            name, url, events, enabled, created_at, last_triggered_at, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for name, wh in webhooks.items():
        try:
            params = (
                name,
                wh.get('url', ''),
                json.dumps(wh.get('events', [])),
                wh.get('enabled', 1),
                wh.get('created_at', ''),
                wh.get('last_triggered_at', ''),
                'json_migrated',
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {name} — {params[1]}")
        except Exception as e:
            print(f"   ❌ Error migrating webhook {name}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('webhooks')
    expected = len(webhooks)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Webhooks in JSON  : {expected}")
    print(f"    Webhooks in SQLite: {db_count}")
    print(f"    Migrated          : {migrated}")
    print(f"    Errors            : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all webhooks migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_webhooks()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

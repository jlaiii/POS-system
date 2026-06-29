#!/usr/bin/env python3
"""
POS System — Table Ads Migration Script
=========================================
Migrates table-side digital ads from table_ads.json to SQLite table_ads table.

table_ads.json stores an object with:
  {
    "ads": [
      {
        "ad_id": "ad-001",
        "title": "Happy Hour Specials",
        "image_url": "/ads/happy-hour.jpg",
        "target_url": "/menu/happy-hour",
        "table_number": 5,
        "active": true,
        "start_date": "2026-06-01",
        "end_date": "2026-07-01",
        "created_at": "2026-06-01T10:00:00"
      }
    ],
    "rotation_interval": 10
  }

The rotation_interval is a global config that defaults to 10 seconds per ad.
Each individual ad gets its own row in the table_ads table.

Idempotent: uses INSERT OR REPLACE, safe to re-run.

Usage:
    python3 migrations/migrate_table_ads.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE_ADS_JSON = os.path.join(PROJECT_ROOT, 'table_ads.json')


def load_table_ads_from_json():
    """Load table ads from table_ads.json. Returns dict with 'ads' list and 'rotation_interval'."""
    try:
        with open(TABLE_ADS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {TABLE_ADS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {TABLE_ADS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_table_ads():
    """Migrate all table ads from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Table Ads Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading table_ads.json...")
    data = load_table_ads_from_json()
    ads = data.get('ads', [])
    rotation_interval = data.get('rotation_interval', 10)
    print(f"   Found {len(ads)} ad(s) in JSON")
    print(f"   Global rotation interval: {rotation_interval}s")

    if not ads:
        print("⚠️  No ads to migrate (empty array).")
        # Still verify the table exists and show current state
        db_count = db.row_count('table_ads')
        print(f"   table_ads SQLite count: {db_count}")
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Ads in JSON   : 0")
        print(f"    Ads in SQLite : {db_count}")
        print(f"    Migration     : nothing to do (empty dataset)")
        print(f"  ✅ Migration COMPLETE — no ads to migrate.")
        return 0

    # Prepare insert statement
    insert_sql = """
        INSERT OR REPLACE INTO table_ads (
            ad_id, title, image_url, target_url,
            table_number, active,
            start_date, end_date,
            rotation_interval, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for ad in ads:
        try:
            params = (
                ad.get('ad_id'),
                ad.get('title', ''),
                ad.get('image_url', ''),
                ad.get('target_url', ''),
                ad.get('table_number'),
                1 if ad.get('active', True) else 0,
                ad.get('start_date'),
                ad.get('end_date'),
                rotation_interval,  # Use global rotation interval from config
                ad.get('created_at'),
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {ad.get('ad_id', '?')} ({ad.get('title', 'Unknown')})")
        except Exception as e:
            print(f"   ❌ Error migrating ad {ad.get('ad_id', '?')}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('table_ads')
    expected = len(ads)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Ads in JSON   : {expected}")
    print(f"    Ads in SQLite : {db_count}")
    print(f"    Migrated      : {migrated}")
    print(f"    Errors        : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all table ads migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_table_ads()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

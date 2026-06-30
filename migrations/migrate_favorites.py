#!/usr/bin/env python3
"""
POS System — Favorites Migration Script
=========================================
Migrates user favorites from favorites.json to SQLite favorites table.

Idempotent: uses INSERT OR REPLACE, safe to re-run.
Verifies row count matches JSON record count.

Usage:
    python3 migrations/migrate_favorites.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAVORITES_JSON = os.path.join(PROJECT_ROOT, 'favorites.json')


def load_favorites_from_json():
    """Load favorites from favorites.json. Returns dict keyed by favorite_id."""
    try:
        with open(FAVORITES_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {FAVORITES_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {FAVORITES_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_favorites():
    """Migrate all favorites from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Favorites Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading favorites.json...")
    favorites = load_favorites_from_json()
    print(f"   Found {len(favorites)} favorite(s) in JSON")

    if not favorites:
        print("⚠️  No favorites to migrate.")
        db_count = db.row_count('favorites')
        print(f"\n{'=' * 60}")
        print(f"  Summary:")
        print(f"    Favorites in JSON  : 0")
        print(f"    Favorites in SQLite: {db_count}")
        if db_count == 0:
            print("  ✅ Migration COMPLETE — favorites table empty, no data to migrate.")
        else:
            print(f"  ❌ Migration COMPLETE WITH ISSUES — expected 0, DB has {db_count}")
        return 0 if db_count == 0 else 1

    # Prepare insert statement
    insert_sql = """
        INSERT OR REPLACE INTO favorites (
            favorite_id, user_id, name, items, created_at
        ) VALUES (?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for fav_id, fav_data in sorted(favorites.items()):
        try:
            params = (
                fav_id,
                fav_data.get('user_id', ''),
                fav_data.get('name', ''),
                json.dumps(fav_data.get('items', [])),
                fav_data.get('created_at'),
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {fav_data.get('name', 'Unnamed')} (user: {params[1]})")
        except Exception as e:
            print(f"   ❌ Error migrating favorite {fav_id}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('favorites')
    expected = len(favorites)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Favorites in JSON  : {expected}")
    print(f"    Favorites in SQLite: {db_count}")
    print(f"    Migrated           : {migrated}")
    print(f"    Errors             : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all favorites migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_favorites()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

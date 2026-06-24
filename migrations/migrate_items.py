#!/usr/bin/env python3
""""
POS System — Items Migration Script
=====================================
Migrates items from items.json to SQLite items table.
Flattens the category-keyed JSON structure (e.g., {"Foods": [...], "Drinks": [...]})
into a flat table with a category column.

Idempotent: clears the table before inserting (since items use autoincrement IDs).
Safe to re-run.

Usage:
    python3 migrations/migrate_items.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS_JSON = os.path.join(PROJECT_ROOT, 'items.json')


def load_items_from_json():
    """Load items from items.json. Returns dict keyed by category name."""
    try:
        with open(ITEMS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {ITEMS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {ITEMS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_items():
    """Migrate all items from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Items Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading items.json...")
    items_by_category = load_items_from_json()
    total_items = sum(len(items) for items in items_by_category.values())
    print(f"   Found {len(items_by_category)} categories, {total_items} total item(s) in JSON")

    if total_items == 0:
        print("⚠️  No items to migrate.")
        return 0

    # Clear existing rows (idempotency: always start fresh since no natural key)
    print("🧹 Clearing existing items rows...")
    db.execute("DELETE FROM items")

    # Prepare insert statement — no id since it's AUTOINCREMENT
    insert_sql = """
        INSERT INTO items (
            name, price, category, barcode, image_url, description,
            visible, modifiers, tags, course, nutrition
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0
    item_index = 0

    for category, items in sorted(items_by_category.items()):
        for item in items:
            item_index += 1
            try:
                # Serialize modifiers dict as JSON text
                modifiers = item.get('modifiers', {})
                modifiers_val = json.dumps(modifiers) if modifiers else '{}'

                # Optional fields
                barcode = item.get('barcode')
                image_url = item.get('image_url')
                description = item.get('description')
                tags_str = json.dumps(item.get('tags', []))
                course = item.get('course')
                nutrition_str = json.dumps(item.get('nutrition', {}))

                # visible defaults to 1 (visible) — JSON items are all visible
                visible = item.get('visible', 1)

                params = (
                    item.get('name', ''),
                    item.get('price', 0.0),
                    category,          # category from JSON key
                    barcode,
                    image_url,
                    description,
                    visible,
                    modifiers_val,
                    tags_str,
                    course,
                    nutrition_str,
                )
                db.execute(insert_sql, params)
                migrated += 1
                print(f"   ✓ Migrated: {item.get('name', 'Unknown')} ({category})")
            except Exception as e:
                print(f"   ❌ Error migrating item #{item_index} ({item.get('name', 'Unknown')}): {e}")
                errors += 1

    # Verify row count
    db_count = db.row_count('items')
    expected = total_items

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Categories       : {len(items_by_category)}")
    print(f"    Items in JSON    : {expected}")
    print(f"    Items in SQLite  : {db_count}")
    print(f"    Migrated         : {migrated}")
    print(f"    Errors           : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all items migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_items()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

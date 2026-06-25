#!/usr/bin/env python3
"""
POS System — Orders Migration Script
======================================
Migrates orders from orders.json to SQLite orders table.

Also migrates cleared_orders.json to the cleared_orders table.

The orders.json stores items as an array of objects with fields:
  name, price, qty (or quantity), note, modifiers, category (optional)

The entire items array is stored as JSON TEXT in the items column.
All nested objects (payment_splits, item_notes) are stored as JSON TEXT.

Idempotent: DELETE + re-INSERT (since orders use AUTOINCREMENT id).
Safe to re-run.

Usage:
    python3 migrations/migrate_orders.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDERS_JSON = os.path.join(PROJECT_ROOT, 'orders.json')
CLEARED_ORDERS_JSON = os.path.join(PROJECT_ROOT, 'cleared_orders.json')


def load_orders_from_json():
    """Load orders from orders.json. Returns list of order dicts."""
    try:
        with open(ORDERS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {ORDERS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {ORDERS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def load_cleared_orders_from_json():
    """Load cleared orders from cleared_orders.json. Returns list."""
    try:
        with open(CLEARED_ORDERS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  {CLEARED_ORDERS_JSON} not found — skipping")
        return []
    except json.JSONDecodeError as e:
        print(f"⚠️  {CLEARED_ORDERS_JSON} is not valid JSON: {e}")
        return []


def migrate_orders():
    """Migrate all orders from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Orders & Cleared Orders Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # ── Migrate main orders ────────────────────────────────────────────────
    print("\n📖 Reading orders.json...")
    orders = load_orders_from_json()
    print(f"   Found {len(orders)} order(s) in JSON")

    # Clear existing rows (idempotency: always start fresh)
    print("🧹 Clearing existing orders rows...")
    db.execute("DELETE FROM orders")

    if orders:
        migrated = 0
        errors = 0

        # Prepare insert statement
        insert_sql = """
            INSERT INTO orders (
                order_id, items, subtotal, tax, tip, total,
                service_charge_amount, payment_method, payment_splits,
                timestamp, status, table_number, notes, user_id,
                customer_phone, customer_email, discount_code, discount_amount,
                item_notes, claimed_by, claimed_at, completed_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
        """

        for idx, order in enumerate(orders):
            try:
                params = (
                    str(order.get('order_id')),
                    json.dumps(order.get('items', [])),
                    order.get('subtotal', 0),
                    order.get('tax_amount', 0),         # JSON: tax_amount → DB: tax
                    order.get('tip_amount', 0),          # JSON: tip_amount → DB: tip
                    order.get('total', 0),
                    order.get('service_charge_amount', 0),
                    # payment can be a string or dict — normalise to string
                    json.dumps(order.get('payment')) if not isinstance(order.get('payment'), str) else (order.get('payment', '') or ''),
                    json.dumps(order.get('payment_splits')) if order.get('payment_splits') is not None else '[]',
                    order.get('date'),                    # JSON: date → DB: timestamp
                    order.get('status', 'pending'),
                    order.get('table_number'),
                    order.get('notes', ''),
                    order.get('user'),                    # JSON: user → DB: user_id
                    None,                                 # customer_phone (not in source)
                    order.get('customer_email', ''),
                    order.get('discount_code'),
                    order.get('discount_amount', 0),
                    json.dumps(order.get('item_notes', {})),
                    order.get('claimed_by'),
                    order.get('claimed_at'),
                    order.get('completed_at'),
                )
                db.execute(insert_sql, params)
                migrated += 1
                if (idx + 1) % 20 == 0:
                    print(f"   ✓ Migrated {idx + 1}/{len(orders)} orders...")
            except Exception as e:
                print(f"   ❌ Error migrating order #{order.get('order_id', '?')}: {e}")
                errors += 1

        # Print remaining progress
        if migrated > 0:
            print(f"   ✓ Migrated final batch — {migrated}/{len(orders)} orders")
    else:
        print("   No orders to migrate (empty array).")
        migrated = 0
        errors = 0

    # ── Migrate cleared orders ────────────────────────────────────────────
    print("\n📖 Reading cleared_orders.json...")
    cleared_orders = load_cleared_orders_from_json()
    print(f"   Found {len(cleared_orders)} cleared order(s) in JSON")

    # Clear existing rows
    print("🧹 Clearing existing cleared_orders rows...")
    db.execute("DELETE FROM cleared_orders")

    if cleared_orders:
        cleared_insert_sql = """
            INSERT INTO cleared_orders (
                order_id, original_order, cleared_at, cleared_by
            ) VALUES (?, ?, ?, ?)
        """
        cleared_migrated = 0
        cleared_errors = 0

        for order in cleared_orders:
            try:
                params = (
                    order.get('order_id'),
                    json.dumps(order),
                    order.get('cleared_at'),
                    order.get('cleared_by'),
                )
                db.execute(cleared_insert_sql, params)
                cleared_migrated += 1
            except Exception as e:
                print(f"   ❌ Error migrating cleared order #{order.get('order_id', '?')}: {e}")
                cleared_errors += 1

        print(f"   ✓ Migrated {cleared_migrated} cleared orders")
    else:
        print("   No cleared orders to migrate.")
        cleared_migrated = 0
        cleared_errors = 0

    # Verify row counts
    db_order_count = db.row_count('orders')
    db_cleared_count = db.row_count('cleared_orders')
    expected_orders = len(orders)
    expected_cleared = len(cleared_orders)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Orders JSON          : {expected_orders}")
    print(f"    Orders SQLite        : {db_order_count}")
    print(f"    Orders Migrated      : {migrated}")
    print(f"    Orders Errors        : {errors}")
    print(f"    Cleared JSON         : {expected_cleared}")
    print(f"    Cleared SQLite       : {db_cleared_count}")
    print(f"    Cleared Migrated     : {cleared_migrated}")
    print(f"    Cleared Errors       : {cleared_errors}")

    all_ok = (
        db_order_count == expected_orders and errors == 0
        and db_cleared_count == expected_cleared and cleared_errors == 0
    )
    if all_ok:
        print(f"  ✅ Migration COMPLETE — all orders migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — see above")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_orders()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

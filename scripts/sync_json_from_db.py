#!/usr/bin/env python3
"""
POS System — Sync SQLite to JSON (Reverse Migration)
=====================================================
Reads data from SQLite tables and writes to the corresponding JSON files.
This keeps JSON files in sync with SQLite during the database migration
transition period. After `use_database: true` is flipped and new data flows
to SQLite, this script can bring JSON files back up to date if a rollback
to JSON mode is needed.

Usage:
    python3 scripts/sync_json_from_db.py              # sync all tables
    python3 scripts/sync_json_from_db.py --dry-run    # preview only, no writes
    python3 scripts/sync_json_from_db.py users items  # sync specific tables
    python3 scripts/sync_json_from_db.py --quiet       # minimal output
    python3 scripts/sync_json_from_db.py --help        # full help

Exit codes:
    0 = success (all synced, or no changes in dry-run)
    1 = one or more tables failed
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Helpers ─────────────────────────────────────────────────────────────

def s(value, default=''):
    """Safe string fallback."""
    return value if value is not None else default


def f(value, default=0.0):
    """Safe float fallback."""
    return value if value is not None else default


def parse_json(text):
    """Parse a JSON string, returning None if null/empty."""
    if text is None or text == '':
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def parse_json_default(text, default):
    """Parse a JSON string with a default fallback."""
    if text is None or text == '':
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def to_bool(val):
    """Convert SQLite integer (0/1) to Python bool."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return bool(val)


def clean_row(row, field_map):
    """Apply field conversions to a dict based on a field_map.

    field_map: dict of {field_name: conversion_func}
    """
    result = dict(row)
    for field, converter in field_map.items():
        if field in result:
            result[field] = converter(result[field])
    return result


def write_json(path, data, dry_run, quiet):
    """Write data to a JSON file with pretty-printing."""
    if dry_run:
        if not quiet:
            print(f"   [DRY-RUN] Would write: {os.path.basename(path)} ({len(json.dumps(data))} bytes)")
        return True
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if not quiet:
            size = os.path.getsize(path)
            print(f"   ✓ Wrote {os.path.basename(path)} ({size} bytes)")
        return True
    except IOError as e:
        print(f"   ❌ Failed to write {path}: {e}")
        return False


def get_table_row_count(table):
    """Get the number of rows in a table."""
    try:
        result = db.query_one(f"SELECT COUNT(*) AS cnt FROM {table}")
        return result['cnt'] if result else 0
    except Exception:
        return 0


# ── Table Syncers ──────────────────────────────────────────────────────

def sync_users(dry_run, quiet):
    """Sync users table → users.json (dict keyed by PIN)."""
    rows = db.query("SELECT * FROM users")
    data = {}
    for r in rows:
        d = dict(r)
        pin = d.pop('pin')
        d.pop('id', None)  # Remove internal SQLite ID
        # Boolean conversions
        d['banned'] = to_bool(d.get('banned'))
        d['totp_enabled'] = to_bool(d.get('totp_enabled'))
        d['force_pin_change'] = to_bool(d.get('force_pin_change'))
        # JSON string fields
        d['permissions'] = parse_json_default(d.get('permissions'), [])
        d['totp_backup_codes'] = parse_json_default(d.get('totp_backup_codes'), [])
        data[pin] = d
    path = os.path.join(PROJECT_ROOT, 'users.json')
    return write_json(path, data, dry_run, quiet)


def sync_shift_log(dry_run, quiet):
    """Sync shift_log table → shift_log.json (array)."""
    rows = db.query("SELECT * FROM shift_log ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['late_excused'] = to_bool(d.get('late_excused'))
        d['breaks'] = parse_json_default(d.get('breaks'), [])
        d['edits'] = parse_json_default(d.get('edits'), [])
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'shift_log.json')
    return write_json(path, data, dry_run, quiet)


def sync_activity_log(dry_run, quiet):
    """Sync activity_log table → activity_log.json (array)."""
    rows = db.query("SELECT * FROM activity_log ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['details'] = parse_json_default(d.get('details'), {})
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'activity_log.json')
    return write_json(path, data, dry_run, quiet)


def sync_items(dry_run, quiet):
    """Sync items table → items.json (dict grouped by category)."""
    rows = db.query("SELECT * FROM items ORDER BY id")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['visible'] = to_bool(d.get('visible'))
        d['modifiers'] = parse_json_default(d.get('modifiers'), {})
        d['tags'] = parse_json_default(d.get('tags'), [])
        d['nutrition'] = parse_json_default(d.get('nutrition'), {})
        category = d.pop('category', 'Uncategorized') or 'Uncategorized'
        if category not in data:
            data[category] = []
        data[category].append(d)
    path = os.path.join(PROJECT_ROOT, 'items.json')
    return write_json(path, data, dry_run, quiet)


def sync_inventory(dry_run, quiet):
    """Sync inventory table → inventory.json (dict keyed by item_name)."""
    rows = db.query("SELECT * FROM inventory")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        item_name = d.pop('item_name')
        data[item_name] = d
    path = os.path.join(PROJECT_ROOT, 'inventory.json')
    return write_json(path, data, dry_run, quiet)


def sync_orders(dry_run, quiet):
    """Sync orders table → orders.json (array)."""
    rows = db.query("SELECT * FROM orders ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['items'] = parse_json_default(d.get('items'), [])
        d['payment_splits'] = parse_json_default(d.get('payment_splits'), [])
        d['item_notes'] = parse_json_default(d.get('item_notes'), {})
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'orders.json')
    return write_json(path, data, dry_run, quiet)


def sync_combos(dry_run, quiet):
    """Sync combos table → combos.json (dict with 'combos' key)."""
    rows = db.query("SELECT * FROM combos ORDER BY id")
    combos = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['visible'] = to_bool(d.get('visible'))
        d['items'] = parse_json_default(d.get('items'), [])
        combos.append(d)
    data = {'combos': combos}
    path = os.path.join(PROJECT_ROOT, 'combos.json')
    return write_json(path, data, dry_run, quiet)


def sync_favorites(dry_run, quiet):
    """Sync favorites table → favorites.json (dict keyed by favorite_id)."""
    rows = db.query("SELECT * FROM favorites")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['items'] = parse_json_default(d.get('items'), [])
        fav_id = d.pop('favorite_id')
        data[fav_id] = d
    path = os.path.join(PROJECT_ROOT, 'favorites.json')
    return write_json(path, data, dry_run, quiet)


def sync_waste_log(dry_run, quiet):
    """Sync waste_log table → waste_log.json (array)."""
    rows = db.query("SELECT * FROM waste_log ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'waste_log.json')
    return write_json(path, data, dry_run, quiet)


def sync_tickets(dry_run, quiet):
    """Sync tickets table → tickets.json (array)."""
    rows = db.query("SELECT * FROM tickets ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['metadata'] = parse_json_default(d.get('metadata'), {})
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'tickets.json')
    return write_json(path, data, dry_run, quiet)


def sync_timesheet(dry_run, quiet):
    """Sync timesheet table → timesheet.json (array)."""
    rows = db.query("SELECT * FROM timesheet ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'timesheet.json')
    return write_json(path, data, dry_run, quiet)


def sync_timesheet_approvals(dry_run, quiet):
    """Sync timesheet_approvals table → timesheet_approvals.json (array)."""
    rows = db.query("SELECT * FROM timesheet_approvals ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'timesheet_approvals.json')
    return write_json(path, data, dry_run, quiet)


def sync_cash_drawer(dry_run, quiet):
    """Sync cash_drawer table → cash_drawer.json (dict with sessions + transactions)."""
    rows = db.query("SELECT * FROM cash_drawer ORDER BY id")
    sessions = []
    all_transactions = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        # Parse transactions JSON from column
        txns = parse_json_default(d.pop('transactions', None), [])
        all_transactions.extend(txns)
        sessions.append(d)
    data = {
        'sessions': sessions,
        'transactions': all_transactions
    }
    path = os.path.join(PROJECT_ROOT, 'cash_drawer.json')
    return write_json(path, data, dry_run, quiet)


def sync_delivery_addresses(dry_run, quiet):
    """Sync delivery_addresses → delivery_addresses.json (dict keyed by address_id)."""
    rows = db.query("SELECT * FROM delivery_addresses")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        addr_id = d.pop('address_id')
        data[addr_id] = d
    path = os.path.join(PROJECT_ROOT, 'delivery_addresses.json')
    return write_json(path, data, dry_run, quiet)


def sync_scheduled_pricing(dry_run, quiet):
    """Sync scheduled_pricing → scheduled_pricing.json (array)."""
    rows = db.query("SELECT * FROM scheduled_pricing ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['active'] = to_bool(d.get('active'))
        d['days_of_week'] = parse_json_default(d.get('days_of_week'), [])
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'scheduled_pricing.json')
    return write_json(path, data, dry_run, quiet)


def sync_webhooks(dry_run, quiet):
    """Sync webhooks table → webhooks.json (dict keyed by name)."""
    rows = db.query("SELECT * FROM webhooks")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['enabled'] = to_bool(d.get('enabled'))
        d['events'] = parse_json_default(d.get('events'), [])
        name = d.pop('name')
        data[name] = d
    path = os.path.join(PROJECT_ROOT, 'webhooks.json')
    return write_json(path, data, dry_run, quiet)


def sync_tables_config(dry_run, quiet):
    """Sync tables_config → tables.json (dict keyed by table_number str)."""
    rows = db.query("SELECT * FROM tables_config ORDER BY table_number")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['visible'] = to_bool(d.get('visible'))
        table_num = str(d.pop('table_number'))
        data[table_num] = d
    path = os.path.join(PROJECT_ROOT, 'tables.json')
    return write_json(path, data, dry_run, quiet)


def sync_table_ads(dry_run, quiet):
    """Sync table_ads → table_ads.json (dict with ads list + rotation_interval)."""
    rows = db.query("SELECT * FROM table_ads ORDER BY id")
    ads = []
    rotation_interval = 10  # default
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['active'] = to_bool(d.get('active'))
        # Capture rotation_interval from last row as the canonical value
        if d.get('rotation_interval') is not None:
            rotation_interval = d['rotation_interval']
        ads.append(d)
    data = {
        'ads': ads,
        'rotation_interval': rotation_interval
    }
    path = os.path.join(PROJECT_ROOT, 'table_ads.json')
    return write_json(path, data, dry_run, quiet)


def sync_loyalty_points(dry_run, quiet):
    """Sync loyalty_points → loyalty_points.json (dict keyed by phone)."""
    rows = db.query("SELECT * FROM loyalty_points")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        phone = d.pop('phone')
        data[phone] = d
    path = os.path.join(PROJECT_ROOT, 'loyalty_points.json')
    return write_json(path, data, dry_run, quiet)


def sync_refunded_orders(dry_run, quiet):
    """Sync refunded_orders → refunded_orders.json (array)."""
    rows = db.query("SELECT * FROM refunded_orders ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['original_order'] = parse_json_default(d.get('original_order'), {})
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'refunded_orders.json')
    return write_json(path, data, dry_run, quiet)


def sync_cleared_orders(dry_run, quiet):
    """Sync cleared_orders → cleared_orders.json (array)."""
    rows = db.query("SELECT * FROM cleared_orders ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['original_order'] = parse_json_default(d.get('original_order'), {})
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'cleared_orders.json')
    return write_json(path, data, dry_run, quiet)


def sync_security_events(dry_run, quiet):
    """Sync security_events → security_events.json (array)."""
    rows = db.query("SELECT * FROM security_events ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['resolved'] = to_bool(d.get('resolved'))
        d['details'] = parse_json_default(d.get('details'), {})
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'security_events.json')
    return write_json(path, data, dry_run, quiet)


def sync_known_ips(dry_run, quiet):
    """Sync known_ips → known_ips.json (dict keyed by user_id, grouping IPs)."""
    rows = db.query("SELECT * FROM known_ips ORDER BY user_id")
    data = {}
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        ip = d.pop('ip_address')
        user_id = d.pop('user_id')
        if user_id not in data:
            data[user_id] = {
                'ips': [],
                'last_seen': d.get('last_seen', ''),
                'note': d.get('label', '')
            }
        data[user_id]['ips'].append(ip)
        # Keep the latest last_seen
        if d.get('last_seen') and (not data[user_id]['last_seen'] or d['last_seen'] > data[user_id]['last_seen']):
            data[user_id]['last_seen'] = d['last_seen']
        # Append label if not empty
        label = d.get('label', '')
        if label and label not in data[user_id]['note']:
            if data[user_id]['note']:
                data[user_id]['note'] += '; ' + label
            else:
                data[user_id]['note'] = label
    path = os.path.join(PROJECT_ROOT, 'known_ips.json')
    return write_json(path, data, dry_run, quiet)


def sync_login_attempts(dry_run, quiet):
    """Sync login_attempts → login_attempts.json (array)."""
    rows = db.query("SELECT * FROM login_attempts ORDER BY id")
    data = []
    for r in rows:
        d = dict(r)
        d.pop('id', None)
        d['success'] = to_bool(d.get('success'))
        data.append(d)
    path = os.path.join(PROJECT_ROOT, 'login_attempts.json')
    return write_json(path, data, dry_run, quiet)


# ── Syncer Registry ────────────────────────────────────────────────────

TABLE_SYNCERS = {
    'users': sync_users,
    'shift_log': sync_shift_log,
    'activity_log': sync_activity_log,
    'items': sync_items,
    'inventory': sync_inventory,
    'orders': sync_orders,
    'combos': sync_combos,
    'favorites': sync_favorites,
    'waste_log': sync_waste_log,
    'tickets': sync_tickets,
    'timesheet': sync_timesheet,
    'timesheet_approvals': sync_timesheet_approvals,
    'cash_drawer': sync_cash_drawer,
    'delivery_addresses': sync_delivery_addresses,
    'scheduled_pricing': sync_scheduled_pricing,
    'webhooks': sync_webhooks,
    'tables_config': sync_tables_config,
    'table_ads': sync_table_ads,
    'loyalty_points': sync_loyalty_points,
    'refunded_orders': sync_refunded_orders,
    'cleared_orders': sync_cleared_orders,
    'security_events': sync_security_events,
    'known_ips': sync_known_ips,
    'login_attempts': sync_login_attempts,
}

ALL_TABLES = sorted(TABLE_SYNCERS.keys())


# ── CLI ────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description='Sync SQLite tables to JSON files (reverse migration).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/sync_json_from_db.py                # sync all tables
  python3 scripts/sync_json_from_db.py users items    # sync specific tables
  python3 scripts/sync_json_from_db.py --dry-run      # preview only
  python3 scripts/sync_json_from_db.py --quiet        # minimal output
        """
    )
    parser.add_argument('tables', nargs='*', metavar='TABLE',
                        help='Table(s) to sync (default: all tables). '
                             f'Available: {", ".join(ALL_TABLES)}')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Preview changes without writing files')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress output except errors')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List available tables and exit')
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list:
        print("Available tables for sync (→ JSON file):")
        print(f"{'Table Name':25s} {'JSON File':25s} {'Rows':>8s}")
        print("-" * 60)
        for table in ALL_TABLES:
            rows = get_table_row_count(table)
            json_file = f"{table}.json"
            # Map known overrides
            override = {
                'tables_config': 'tables.json',
                'table_ads': 'table_ads.json',
                'loyalty_points': 'loyalty_points.json',
                'cash_drawer': 'cash_drawer.json',
                'timesheet_approvals': 'timesheet_approvals.json',
                'scheduled_pricing': 'scheduled_pricing.json',
                'delivery_addresses': 'delivery_addresses.json',
                'refunded_orders': 'refunded_orders.json',
                'cleared_orders': 'cleared_orders.json',
                'security_events': 'security_events.json',
                'login_attempts': 'login_attempts.json',
            }
            json_file = override.get(table, f"{table}.json")
            print(f"{table:25s} {json_file:25s} {rows:>8d}")
        return 0

    # Determine which tables to sync
    tables_to_sync = args.tables if args.tables else ALL_TABLES

    # Validate table names
    invalid = [t for t in tables_to_sync if t not in TABLE_SYNCERS]
    if invalid:
        print(f"❌ Unknown table(s): {', '.join(invalid)}")
        print(f"   Available: {', '.join(ALL_TABLES)}")
        return 1

    if not args.quiet:
        mode = " [DRY-RUN — no files will be written]" if args.dry_run else ""
        print(f"{'=' * 60}")
        print(f"  SQLite → JSON Sync{mode}")
        print(f"  Tables: {len(tables_to_sync)} selected ({', '.join(tables_to_sync)})")
        print(f"{'=' * 60}")

    # Initialize DB tables (in case init_db hasn't been called)
    try:
        db.init_db()
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return 1

    # Run syncers
    success_count = 0
    fail_count = 0
    for table in tables_to_sync:
        syncer = TABLE_SYNCERS[table]
        row_count = get_table_row_count(table)
        if not args.quiet:
            status = "🔄" if row_count > 0 else "⏭️ "
            print(f"\n{status} {table} ({row_count} rows) → {table}.json")
        try:
            result = syncer(args.dry_run, args.quiet)
            if result:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"   ❌ Error syncing {table}: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1

    # Summary
    total = len(tables_to_sync)
    if not args.quiet:
        print(f"\n{'=' * 60}")
        print(f"  Sync complete: {success_count}/{total} succeeded"
              f"{' [DRY-RUN]' if args.dry_run else ''}")
        if fail_count > 0:
            print(f"  ❌ {fail_count} table(s) failed")
        print(f"{'=' * 60}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nSync cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

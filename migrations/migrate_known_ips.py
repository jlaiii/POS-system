#!/usr/bin/env python3
"""
POS System — Known IPs Migration Script
=========================================
Migrates known IPs from known_ips.json to SQLite known_ips table.

Data format (JSON): dict keyed by user_id
  {
    "1111": {
      "ips": ["127.0.0.1", ...],
      "last_seen": "ISO timestamp",
      "note": "description"
    }
  }

Table schema: one row per (ip_address, user_id) pair
Flattens the IPs array into individual rows.

Idempotent: uses INSERT OR REPLACE via UNIQUE(ip_address, user_id) constraint.
Verifies row count matches expected total IP entries.

Usage:
    python3 migrations/migrate_known_ips.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWN_IPS_JSON = os.path.join(PROJECT_ROOT, 'known_ips.json')


def load_known_ips_from_json():
    """Load known IPs from known_ips.json. Returns dict keyed by user_id."""
    try:
        with open(KNOWN_IPS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {KNOWN_IPS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {KNOWN_IPS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_known_ips():
    """Migrate all known IPs from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Known IPs Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading known_ips.json...")
    known_ips = load_known_ips_from_json()
    print(f"   Found {len(known_ips)} user(s) with IP tracking in JSON")

    if not known_ips:
        print("⚠️  No known IP entries to migrate.")
        return 0

    # Prepare insert statement
    insert_sql = """
        INSERT OR REPLACE INTO known_ips
            (ip_address, user_id, first_seen, last_seen, label)
        VALUES (?, ?, ?, ?, ?)
    """

    # First pass: count total IP entries for verification
    total_ip_entries = sum(
        len(info.get('ips', []))
        for info in known_ips.values()
    )
    print(f"   Total IP address entries: {total_ip_entries}")

    migrated = 0
    errors = 0

    for user_id, info in sorted(known_ips.items()):
        ips = info.get('ips', [])
        last_seen = info.get('last_seen')
        label = info.get('note', '')

        if not ips:
            print(f"   ℹ️  User {user_id} has no IPs — skipping")
            continue

        for ip_address in ips:
            try:
                params = (
                    ip_address,
                    user_id,
                    last_seen,   # first_seen — use last_seen as best guess
                    last_seen,
                    label,
                )
                db.execute(insert_sql, params)
                migrated += 1
            except Exception as e:
                print(f"   ❌ Error migrating IP {ip_address} for user {user_id}: {e}")
                errors += 1

        print(f"   ✓ Migrated {len(ips)} IP(s) for user {user_id}")

    # Verify row count
    db_count = db.row_count('known_ips')
    expected = total_ip_entries

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    IP entries in JSON  : {expected}")
    print(f"    Rows in SQLite      : {db_count}")
    print(f"    Migrated            : {migrated}")
    print(f"    Errors              : {errors}")

    if db_count >= expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all known IPs migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON IPs={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_known_ips()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

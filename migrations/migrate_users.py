#!/usr/bin/env python3
"""
POS System — Users Migration Script
=====================================
Migrates users from users.json to SQLite users table.

Idempotent: uses INSERT OR REPLACE, safe to re-run.
Verifies row count matches JSON record count.

Usage:
    python3 migrations/migrate_users.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_JSON = os.path.join(PROJECT_ROOT, 'users.json')


def load_users_from_json():
    """Load users from users.json. Returns dict keyed by PIN."""
    try:
        with open(USERS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {USERS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {USERS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_users():
    """Migrate all users from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Users Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading users.json...")
    users = load_users_from_json()
    print(f"   Found {len(users)} user(s) in JSON")

    if not users:
        print("⚠️  No users to migrate.")
        return 0

    # Prepare insert statement
    insert_sql = """
        INSERT OR REPLACE INTO users (
            pin, name, role, permissions, banned, banned_reason,
            username, password_hash, password_salt,
            pay_rate, scheduled_start,
            totp_secret, totp_enabled, totp_backup_codes, totp_setup_at,
            pin_reset_notification, force_pin_change, temp_pin, temp_pin_expiry
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for pin, user_data in sorted(users.items()):
        try:
            params = (
                pin,
                user_data.get('name', ''),
                user_data.get('role', 'user'),
                json.dumps(user_data.get('permissions', [])),
                1 if user_data.get('banned', False) else 0,
                user_data.get('banned_reason', ''),
                user_data.get('username', ''),
                user_data.get('password_hash', ''),
                user_data.get('password_salt', ''),
                user_data.get('pay_rate'),
                user_data.get('scheduled_start'),
                user_data.get('totp_secret'),
                1 if user_data.get('totp_enabled', False) else 0,
                json.dumps(user_data.get('totp_backup_codes', [])),
                user_data.get('totp_setup_at'),
                user_data.get('pin_reset_notification'),
                1 if user_data.get('force_pin_change', False) else 0,
                user_data.get('temp_pin'),
                user_data.get('temp_pin_expiry'),
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {pin} ({user_data.get('name', 'Unknown')})")
        except Exception as e:
            print(f"   ❌ Error migrating user {pin}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('users')
    expected = len(users)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Users in JSON  : {expected}")
    print(f"    Users in SQLite: {db_count}")
    print(f"    Migrated       : {migrated}")
    print(f"    Errors         : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all users migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_users()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

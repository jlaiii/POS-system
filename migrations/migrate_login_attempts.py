#!/usr/bin/env python3
"""
POS System — Login Attempts Migration Script
==============================================
Migrates login attempts from login_attempts.json to SQLite login_attempts table.

The JSON is a list of login attempt objects, e.g.:
    {
        "user_id": "1111",
        "ip": "127.0.0.1",
        "timestamp": "2026-06-23T18:22:44.909108",
        "success": true,
        "user_agent": "curl/8.5.0",
        "method": "pin",
        "details": {"status": "success"}
    }

Field mapping:
    JSON 'ip'          → SQL ip_address
    JSON 'success'     → SQL success (bool → INTEGER 0/1)
    JSON 'user_agent'  → SQL user_agent
    JSON 'details'     → SQL details (object → JSON TEXT)

Idempotent: DELETE + re-INSERT (uses AUTOINCREMENT id).
Safe to re-run.

Usage:
    python3 migrations/migrate_login_attempts.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIN_ATTEMPTS_JSON = os.path.join(PROJECT_ROOT, 'login_attempts.json')


def load_login_attempts_from_json():
    """Load login attempts from login_attempts.json. Returns list of dicts."""
    try:
        with open(LOGIN_ATTEMPTS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {LOGIN_ATTEMPTS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {LOGIN_ATTEMPTS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_login_attempts():
    """Migrate all login attempts from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Login Attempts Migration")
    print("=" * 60)

    # Initialize database tables (runs schema migration too)
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading login_attempts.json...")
    attempts = load_login_attempts_from_json()
    print(f"   Found {len(attempts)} attempt(s) in JSON")

    # Clear existing rows (idempotency: always start fresh)
    print("🧹 Clearing existing login_attempts rows...")
    db.execute("DELETE FROM login_attempts")

    if not attempts:
        print("⚠️  No login attempts to migrate.")
        return 0

    # Prepare insert statement
    insert_sql = """
        INSERT INTO login_attempts (
            ip_address, user_id, timestamp, success, method,
            user_agent, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for idx, attempt in enumerate(attempts):
        try:
            success_val = 1 if attempt.get('success') else 0
            params = (
                attempt.get('ip', ''),                   # JSON: ip → SQL: ip_address
                attempt.get('user_id', ''),
                attempt.get('timestamp'),
                success_val,                              # bool → INTEGER
                attempt.get('method', ''),
                attempt.get('user_agent', ''),            # new column
                json.dumps(attempt.get('details', {})),   # object → JSON TEXT
            )
            db.execute(insert_sql, params)
            migrated += 1
            if (idx + 1) % 20 == 0:
                print(f"   ✓ Migrated {idx + 1}/{len(attempts)} attempts...")
        except Exception as e:
            print(f"   ❌ Error migrating attempt #{idx + 1} ({attempt.get('user_id', '?')}): {e}")
            errors += 1

    if migrated > 0:
        print(f"   ✓ Migrated final batch — {migrated}/{len(attempts)} attempts")

    # Verify row count
    db_count = db.row_count('login_attempts')
    expected = len(attempts)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Attempts in JSON  : {expected}")
    print(f"    Attempts in SQLite: {db_count}")
    print(f"    Migrated          : {migrated}")
    print(f"    Errors            : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all login attempts migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_login_attempts()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

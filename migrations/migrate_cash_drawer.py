#!/usr/bin/env python3
"""
POS System — Cash Drawer Migration Script
===========================================
Migrates cash drawer sessions and transactions from cash_drawer.json to SQLite.

The cash_drawer.json stores session records in a "sessions" array and a global
"transactions" array. Each session references its transactions via session_id.

Schema design:
- Each session becomes one row in the cash_drawer table
- The session's transactions are filtered from the global transactions list
  and stored as JSON TEXT in the transactions column
- Extra session fields (opened_by_name, closed_by_name, variance_reason,
  total_cash_in, total_cash_out, status, notes) are stored as direct columns

Idempotent: DELETE + re-INSERT (idempotent via AUTOINCREMENT).
Safe to re-run.

Usage:
    python3 migrations/migrate_cash_drawer.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASH_DRAWER_JSON = os.path.join(PROJECT_ROOT, 'cash_drawer.json')


def load_cash_drawer_from_json():
    """Load cash drawer data from cash_drawer.json. Returns dict with sessions + transactions."""
    try:
        with open(CASH_DRAWER_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {CASH_DRAWER_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {CASH_DRAWER_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_cash_drawer():
    """Migrate all cash drawer sessions from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Cash Drawer Migration")
    print("=" * 60)

    # Initialize database tables (applies schema migrations too)
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("\n📖 Reading cash_drawer.json...")
    data = load_cash_drawer_from_json()
    sessions = data.get('sessions', [])
    all_transactions = data.get('transactions', [])
    print(f"   Found {len(sessions)} session(s) and {len(all_transactions)} transaction(s) in JSON")

    # Clear existing rows (idempotency)
    print("🧹 Clearing existing cash_drawer rows...")
    db.execute("DELETE FROM cash_drawer")

    if not sessions:
        print("   No sessions to migrate (empty array).")
        migrated = 0
        errors = 0
    else:
        insert_sql = """
            INSERT INTO cash_drawer (
                session_id, opened_at, closed_at,
                starting_cash, expected_cash, actual_cash, variance,
                opened_by, closed_by,
                opened_by_name, closed_by_name,
                variance_reason, total_cash_in, total_cash_out,
                status, notes,
                transactions
            ) VALUES (
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?
            )
        """

        migrated = 0
        errors = 0

        for idx, session in enumerate(sessions):
            try:
                session_id = session.get('id', '')

                # Filter transactions belonging to this session
                session_transactions = [
                    t for t in all_transactions
                    if t.get('session_id') == session_id
                ]

                params = (
                    session_id,
                    session.get('opened_at'),
                    session.get('closed_at'),
                    session.get('opening_balance', 0),     # JSON → DB: starting_cash
                    session.get('expected_balance', 0),     # JSON → DB: expected_cash
                    session.get('closing_balance', 0),      # JSON → DB: actual_cash
                    session.get('difference', 0),           # JSON → DB: variance
                    session.get('opened_by'),
                    session.get('closed_by'),
                    session.get('opened_by_name', ''),
                    session.get('closed_by_name', ''),
                    session.get('variance_reason', ''),
                    session.get('total_cash_in', 0),
                    session.get('total_cash_out', 0),
                    session.get('status', 'closed'),
                    session.get('notes', ''),
                    json.dumps(session_transactions),       # filtered transactions as JSON
                )
                db.execute(insert_sql, params)
                migrated += 1
                if (idx + 1) % 10 == 0:
                    print(f"   ✓ Migrated {idx + 1}/{len(sessions)} sessions...")
            except Exception as e:
                print(f"   ❌ Error migrating session '{session.get('id', '?')}': {e}")
                errors += 1

        if migrated > 0:
            print(f"   ✓ Migrated final batch — {migrated}/{len(sessions)} sessions")

    # Verify row counts
    db_count = db.row_count('cash_drawer')
    expected_sessions = len(sessions)

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Sessions JSON      : {expected_sessions}")
    print(f"    Sessions SQLite    : {db_count}")
    print(f"    Sessions Migrated  : {migrated}")
    print(f"    Sessions Errors    : {errors}")
    print(f"    Transactions JSON  : {len(all_transactions)}")
    print(f"    Transactions stored: included as JSON in respective session rows")

    all_ok = (db_count == expected_sessions and errors == 0)
    if all_ok:
        print(f"  ✅ Migration COMPLETE — all cash drawer sessions migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — see above")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_cash_drawer()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

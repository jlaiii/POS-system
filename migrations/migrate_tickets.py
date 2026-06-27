#!/usr/bin/env python3
"""
POS System — Tickets Migration Script
======================================
Migrates tickets from tickets.json to SQLite tickets table.

The JSON format uses custom fields (ticket_id, user_id, user_name, type, subject, etc.)
while the SQLite schema uses standardized fields (ticket_id, title, description, created_by, etc.).

Mapping:
  - JSON 'id' (e.g. "TKT-001") → ticket_id (TEXT UNIQUE)
  - JSON 'subject'              → title
  - JSON 'description'          → description
  - JSON 'status'               → status
  - JSON 'priority'             → priority
  - JSON 'user_id'              → created_by
  - JSON 'created_at'           → created_at
  - JSON 'responded_at'         → updated_at
  - Extra fields (user_name, type, responded_by, response_note) → metadata JSON

Idempotent: uses INSERT OR REPLACE on ticket_id.
Safe to re-run.

Usage:
    python3 migrations/migrate_tickets.py
"""

import json
import os
import sys

# Add parent dir to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKETS_JSON = os.path.join(PROJECT_ROOT, 'tickets.json')


def load_tickets_from_json():
    """Load tickets from tickets.json. Returns list of ticket dicts."""
    try:
        with open(TICKETS_JSON, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {TICKETS_JSON} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: {TICKETS_JSON} is not valid JSON: {e}")
        sys.exit(1)


def migrate_tickets():
    """Migrate all tickets from JSON to SQLite. Idempotent."""
    print("=" * 60)
    print("  POS System — Tickets Migration")
    print("=" * 60)

    # Initialize database tables
    print("\n🔄 Initializing database schema...")
    db.init_db()

    # Load JSON data
    print("📖 Reading tickets.json...")
    tickets = load_tickets_from_json()
    total_tickets = len(tickets)
    print(f"   Found {total_tickets} ticket(s) in JSON")

    if total_tickets == 0:
        print("⚠️  No tickets to migrate.")
        return 0

    # Use INSERT OR REPLACE for idempotency (ticket_id is UNIQUE)
    insert_sql = """
        INSERT OR REPLACE INTO tickets (
            ticket_id, title, description, status, priority,
            created_by, created_at, updated_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    migrated = 0
    errors = 0

    for ticket in tickets:
        try:
            ticket_id = ticket.get('id', '')

            # Build metadata dict from extra JSON fields not in schema
            metadata = {}
            for extra_key in ['user_name', 'type', 'responded_by', 'response_note']:
                if extra_key in ticket and ticket[extra_key] is not None:
                    metadata[extra_key] = ticket[extra_key]

            metadata_str = json.dumps(metadata) if metadata else '{}'

            params = (
                ticket_id,
                ticket.get('subject', ''),
                ticket.get('description', ''),
                ticket.get('status', 'open'),
                ticket.get('priority', 'medium'),
                ticket.get('user_id', ''),
                ticket.get('created_at', ''),
                ticket.get('responded_at'),  # maps to updated_at
                metadata_str,
            )
            db.execute(insert_sql, params)
            migrated += 1
            print(f"   ✓ Migrated: {ticket_id} — {ticket.get('subject', 'No subject')}")
        except Exception as e:
            print(f"   ❌ Error migrating ticket {ticket.get('id', 'Unknown')}: {e}")
            errors += 1

    # Verify row count
    db_count = db.row_count('tickets')
    expected = total_tickets

    print(f"\n{'=' * 60}")
    print(f"  Summary:")
    print(f"    Tickets in JSON    : {expected}")
    print(f"    Tickets in SQLite  : {db_count}")
    print(f"    Migrated           : {migrated}")
    print(f"    Errors             : {errors}")

    if db_count == expected and errors == 0:
        print(f"  ✅ Migration COMPLETE — all tickets migrated successfully.")
        return 0
    else:
        print(f"  ❌ Migration COMPLETE WITH ISSUES — {errors} error(s), "
              f"count mismatch: JSON={expected}, DB={db_count}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = migrate_tickets()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nMigration cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

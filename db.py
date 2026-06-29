"""
POS System — SQLite Database Module
=====================================
Core database helpers for the POS system migration from JSON to SQLite.

Usage:
    from db import get_db, query, execute, init_db

    # Initialize all tables (safe to call multiple times)
    init_db()

    # Query rows
    rows = query("SELECT * FROM users WHERE pin = ?", ("1111",))

    # Execute INSERT/UPDATE/DELETE
    execute("INSERT OR REPLACE INTO users (...) VALUES (...)", (val1, val2, ...))

Design:
    - Single-file SQLite at pos.db in the project root
    - WAL mode enabled for concurrent read performance
    - All timestamps stored as ISO 8601 TEXT (SQLite has no native datetime)
    - JSON arrays/objects stored as TEXT (json.dumps/loads)
    - Booleans stored as INTEGER (0/1)
    - Feature-flagged: system falls back to JSON if timesheet_config.use_database == false
"""

import json
import os
import sqlite3
import threading
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, 'pos.db')

# Thread-local connections for safety
_local = threading.local()


def _get_config():
    """Read the use_database flag from timesheet_config.json."""
    config_path = os.path.join(PROJECT_ROOT, 'timesheet_config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def is_db_enabled():
    """Check if SQLite mode is enabled via feature flag."""
    config = _get_config()
    return config.get('use_database', False)


# ── Connection Management ─────────────────────────────────────────────────

def get_db():
    """Get a thread-local SQLite connection. Creates the DB file if it doesn't exist.

    Returns a sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent reads
        _local.conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_db():
    """Close the thread-local connection if open."""
    if hasattr(_local, 'conn') and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


# ── Query Helpers ─────────────────────────────────────────────────────────

def query(sql, params=None):
    """Execute a SELECT query and return all rows as list of sqlite3.Row.

    Args:
        sql: SQL query string (use ? placeholders)
        params: tuple or list of parameters

    Returns:
        List of sqlite3.Row objects (dict-like access)
    """
    conn = get_db()
    cursor = conn.execute(sql, params or [])
    rows = cursor.fetchall()
    cursor.close()
    return rows


def query_one(sql, params=None):
    """Execute a SELECT query and return the first row, or None.

    Args:
        sql: SQL query string (use ? placeholders)
        params: tuple or list of parameters

    Returns:
        Single sqlite3.Row or None
    """
    conn = get_db()
    cursor = conn.execute(sql, params or [])
    row = cursor.fetchone()
    cursor.close()
    return row


def execute(sql, params=None, commit=True):
    """Execute an INSERT/UPDATE/DELETE statement.

    Args:
        sql: SQL statement (use ? placeholders)
        params: tuple or list of parameters
        commit: whether to commit immediately (default: True)

    Returns:
        sqlite3.Cursor (for lastrowid, rowcount, etc.)
    """
    conn = get_db()
    cursor = conn.execute(sql, params or [])
    if commit:
        conn.commit()
    return cursor


def executemany(sql, seq_params, commit=True):
    """Execute a statement for each parameter set.

    Args:
        sql: SQL statement (use ? placeholders)
        seq_params: sequence of parameter tuples/lists
        commit: whether to commit after all executions

    Returns:
        sqlite3.Cursor
    """
    conn = get_db()
    cursor = conn.executemany(sql, seq_params)
    if commit:
        conn.commit()
    return cursor


# ── Schema Initialization ─────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist. Safe to call multiple times."""
    conn = get_db()
    cursor = conn.cursor()

    # ── Users table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            pin TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            permissions TEXT DEFAULT '[]',
            banned INTEGER DEFAULT 0,
            banned_reason TEXT DEFAULT '',
            username TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            password_salt TEXT DEFAULT '',
            pay_rate REAL,
            scheduled_start TEXT,
            totp_secret TEXT,
            totp_enabled INTEGER DEFAULT 0,
            totp_backup_codes TEXT DEFAULT '[]',
            totp_setup_at TEXT,
            pin_reset_notification TEXT,
            force_pin_change INTEGER DEFAULT 0,
            temp_pin TEXT,
            temp_pin_expiry TEXT
        )
    """)

    # ── Shift Log table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT,
            clock_in_time TEXT,
            clock_out_time TEXT,
            duration_hours REAL DEFAULT 0,
            breaks TEXT DEFAULT '[]',
            break_hours REAL DEFAULT 0,
            paid_hours REAL DEFAULT 0,
            scheduled_start TEXT,
            late_minutes INTEGER,
            late_excused INTEGER DEFAULT 0,
            late_note TEXT,
            notes TEXT,
            edits TEXT DEFAULT '[]'
        )
    """)

    # ── Activity Log table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL,
            user_id TEXT,
            user_role TEXT,
            details TEXT DEFAULT '{}'
        )
    """)

    # ── Items table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            category TEXT,
            barcode TEXT,
            image_url TEXT,
            description TEXT,
            visible INTEGER DEFAULT 1,
            modifiers TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            course TEXT,
            nutrition TEXT DEFAULT '{}'
        )
    """)

    # ── Inventory table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item_name TEXT PRIMARY KEY,
            stock INTEGER DEFAULT 0,
            threshold INTEGER DEFAULT 10,
            unit TEXT,
            last_updated TEXT
        )
    """)

    # ── Loyalty Points table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_points (
            phone TEXT PRIMARY KEY,
            name TEXT,
            email TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            address TEXT DEFAULT '',
            points INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_redeemed INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            last_visit TEXT,
            created_at TEXT,
            history TEXT DEFAULT '[]'
        )
    """)

    # ── Orders table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            items TEXT DEFAULT '[]',
            subtotal REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            tip REAL DEFAULT 0,
            total REAL DEFAULT 0,
            payment_method TEXT,
            payment_splits TEXT DEFAULT '[]',
            timestamp TEXT,
            status TEXT DEFAULT 'pending',
            table_number INTEGER,
            notes TEXT DEFAULT '',
            user_id TEXT,
            customer_phone TEXT,
            discount_code TEXT,
            discount_amount REAL DEFAULT 0,
            item_notes TEXT DEFAULT '{}',
            claimed_by TEXT,
            claimed_at TEXT,
            completed_at TEXT,
            service_charge_amount REAL DEFAULT 0,
            customer_email TEXT DEFAULT ''
        )
    """)

    # ── Combos table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combo_id TEXT UNIQUE,
            name TEXT,
            combo_price REAL DEFAULT 0,
            description TEXT DEFAULT '',
            child_items TEXT DEFAULT '[]',
            active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # ── Favorites table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            favorite_id TEXT UNIQUE,
            user_id TEXT,
            name TEXT,
            items TEXT DEFAULT '[]',
            created_at TEXT
        )
    """)

    # ── Waste Log table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waste_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            item_name TEXT,
            quantity INTEGER DEFAULT 0,
            reason TEXT,
            estimated_cost REAL DEFAULT 0,
            notes TEXT,
            user_id TEXT
        )
    """)

    # ── Tickets table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            created_by TEXT,
            assigned_to TEXT,
            created_at TEXT,
            updated_at TEXT,
            metadata TEXT DEFAULT '{}'
        )
    """)

    # ── Timesheet entries table (admin login timesheet) ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timesheet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            user_name TEXT,
            login_time TEXT,
            logout_time TEXT,
            duration_hours REAL DEFAULT 0
        )
    """)

    # ── Timesheet Approvals table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timesheet_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id INTEGER,
            user_id TEXT,
            approved_by TEXT,
            approved_at TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT
        )
    """)

    # ── Cash Drawer table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_drawer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            opened_at TEXT,
            closed_at TEXT,
            starting_cash REAL DEFAULT 0,
            expected_cash REAL DEFAULT 0,
            actual_cash REAL DEFAULT 0,
            variance REAL DEFAULT 0,
            opened_by TEXT,
            closed_by TEXT,
            opened_by_name TEXT DEFAULT '',
            closed_by_name TEXT DEFAULT '',
            variance_reason TEXT DEFAULT '',
            total_cash_in REAL DEFAULT 0,
            total_cash_out REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            notes TEXT DEFAULT '',
            transactions TEXT DEFAULT '[]'
        )
    """)

    # ── Delivery Addresses table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address_id TEXT UNIQUE,
            customer_name TEXT,
            phone TEXT,
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            instructions TEXT,
            created_at TEXT
        )
    """)

    # ── Scheduled Pricing table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_pricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER UNIQUE,
            name TEXT,
            discount_type TEXT,
            value REAL DEFAULT 0,
            start_time TEXT,
            end_time TEXT,
            days_of_week TEXT DEFAULT '[]',
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    # ── Webhooks table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            url TEXT,
            events TEXT DEFAULT '[]',
            enabled INTEGER DEFAULT 1,
            created_at TEXT,
            last_triggered_at TEXT
        )
    """)

    # ── Tables config table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tables_config (
            table_number INTEGER PRIMARY KEY,
            name TEXT,
            capacity INTEGER DEFAULT 4,
            status TEXT DEFAULT 'available',
            tablet_id TEXT,
            section TEXT,
            visible INTEGER DEFAULT 1,
            created_at TEXT,
            last_bussed_at TEXT
        )
    """)

    # ── Table Ads table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_id TEXT UNIQUE,
            title TEXT,
            image_url TEXT,
            target_url TEXT,
            table_number INTEGER,
            active INTEGER DEFAULT 1,
            start_date TEXT,
            end_date TEXT,
            rotation_interval INTEGER DEFAULT 10,
            created_at TEXT
        )
    """)

    # ── Security Events table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            ip_address TEXT,
            user_id TEXT,
            severity TEXT DEFAULT 'info',
            details TEXT DEFAULT '{}',
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT
        )
    """)

    # ── Known IPs table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS known_ips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT,
            user_id TEXT,
            first_seen TEXT,
            last_seen TEXT,
            label TEXT,
            UNIQUE(ip_address, user_id)
        )
    """)

    # ── Login Attempts table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT,
            user_id TEXT,
            timestamp TEXT,
            success INTEGER DEFAULT 0,
            method TEXT,
            user_agent TEXT DEFAULT '',
            details TEXT DEFAULT '{}'
        )
    """)

    # ── Refunded Orders table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refunded_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            original_order TEXT DEFAULT '{}',
            reason TEXT,
            refunded_at TEXT,
            refunded_by TEXT
        )
    """)

    # ── Cleared Orders table ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleared_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            original_order TEXT DEFAULT '{}',
            cleared_at TEXT,
            cleared_by TEXT
        )
    """)

    conn.commit()
    cursor.close()

    # Run schema migrations for existing tables (adds missing columns)
    _migrate_schemas()


def _migrate_schemas():
    """
    Schema migration helper: adds missing columns to existing tables.
    This handles the case where the CREATE TABLE IF NOT EXISTS already exists
    but new columns were added to the schema definition in a later deploy.

    Each migration is a (table, column_name, column_def) tuple.
    Migrations are idempotent — they check if the column exists before adding it.
    """
    migrations = [
        # loyalty_points: added email, notes, address, total_redeemed,
        # total_orders, created_at, history in a schema update
        ('loyalty_points', 'email', 'TEXT DEFAULT ""'),
        ('loyalty_points', 'notes', 'TEXT DEFAULT ""'),
        ('loyalty_points', 'address', 'TEXT DEFAULT ""'),
        ('loyalty_points', 'total_redeemed', 'INTEGER DEFAULT 0'),
        ('loyalty_points', 'total_orders', 'INTEGER DEFAULT 0'),
        ('loyalty_points', 'created_at', 'TEXT'),
        ('loyalty_points', 'history', 'TEXT DEFAULT "[]"'),
        # orders: added service_charge_amount, customer_email in schema update
        ('orders', 'service_charge_amount', 'REAL DEFAULT 0'),
        ('orders', 'customer_email', 'TEXT DEFAULT ""'),
        # login_attempts: added user_agent, details in schema update
        ('login_attempts', 'user_agent', 'TEXT DEFAULT ""'),
        ('login_attempts', 'details', 'TEXT DEFAULT "{}"'),
        # combos: schema update from basic (items/price/visible) to rich (combo_id/combo_price/description/child_items/active/timestamps)
        ('combos', 'combo_id', 'TEXT'),
        ('combos', 'combo_price', 'REAL DEFAULT 0'),
        ('combos', 'description', 'TEXT DEFAULT ""'),
        ('combos', 'child_items', 'TEXT DEFAULT "[]"'),
        ('combos', 'active', 'INTEGER DEFAULT 1'),
        ('combos', 'created_at', 'TEXT'),
        ('combos', 'updated_at', 'TEXT'),
        # tables_config: added created_at, last_bussed_at for migration
        ('tables_config', 'created_at', 'TEXT'),
        ('tables_config', 'last_bussed_at', 'TEXT'),
        # cash_drawer: added opened_by_name, closed_by_name, variance_reason,
        # total_cash_in, total_cash_out, status, notes for cash drawer migration
        ('cash_drawer', 'opened_by_name', 'TEXT DEFAULT ""'),
        ('cash_drawer', 'closed_by_name', 'TEXT DEFAULT ""'),
        ('cash_drawer', 'variance_reason', 'TEXT DEFAULT ""'),
        ('cash_drawer', 'total_cash_in', 'REAL DEFAULT 0'),
        ('cash_drawer', 'total_cash_out', 'REAL DEFAULT 0'),
        ('cash_drawer', 'status', 'TEXT DEFAULT "open"'),
        ('cash_drawer', 'notes', 'TEXT DEFAULT ""'),
    ]

    for table, column, col_def in migrations:
        try:
            # Check if column already exists
            rows = query(f"PRAGMA table_info(\"{table}\")")
            existing_cols = [r['name'] for r in rows]
            if column not in existing_cols:
                execute(f"ALTER TABLE \"{table}\" ADD COLUMN \"{column}\" {col_def}")
                print(f"  ℹ️  Added column {table}.{column}")
        except Exception:
            # Table might not exist yet — that's fine, CREATE TABLE will handle it
            pass


# ── Utility ───────────────────────────────────────────────────────────────

def table_exists(table_name):
    """Check if a table exists in the database."""
    rows = query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return len(rows) > 0


def row_count(table_name):
    """Get the number of rows in a table."""
    row = query_one(f"SELECT COUNT(*) as cnt FROM \"{table_name}\"")
    return row['cnt'] if row else 0


def get_tables():
    """Get list of all user tables in the database."""
    rows = query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r['name'] for r in rows]


# ── Convenience: JSON helpers ─────────────────────────────────────────────

def json_dumps(obj):
    """Serialize a Python object to JSON string."""
    return json.dumps(obj, default=str)


def json_loads(text):
    """Deserialize a JSON string to Python object."""
    if text is None:
        return None
    return json.loads(text)


if __name__ == '__main__':
    # Quick test: initialize database and report
    print("🔄 Initializing database...")
    init_db()
    tables = get_tables()
    print(f"✅ Database initialized at: {DB_PATH}")
    print(f"📊 Tables created ({len(tables)}):")
    for t in tables:
        count = row_count(t)
        print(f"   - {t}: {count} rows")
    close_db()

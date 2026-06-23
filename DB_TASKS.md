# POS Database Migration Tasks
> Last run: 2026-06-23 23:xx UTC
> Current phase: Phase 2 — Migration Scripts (1/24 complete)

## Phase 1: Schema Design
- [x] Design all SQLite table schemas (users, shift_log, orders, items, inventory, etc.)
- [x] Create `db.py` core module with get_db(), query(), execute(), init_db()
- [x] Add `use_database` feature flag to timesheet_config.json
- [x] Create `migrations/` directory for migration scripts

## Phase 2: Migration Scripts (one at a time)
- [x] Write migrate_users.py — users table migration (6 rows verified ✓)
- [ ] Write migrate_shift_log.py — shift_log table migration
- [ ] Write migrate_activity_log.py — activity_log table migration
- [ ] Write migrate_items.py — items table migration (flatten categories)
- [ ] Write migrate_inventory.py — inventory table migration
- [ ] Write migrate_loyalty_points.py — loyalty_points table migration
- [ ] Write migrate_orders.py — orders table migration
- [ ] Write migrate_combos.py — combos table migration
- [ ] Write migrate_favorites.py — favorites table migration
- [ ] Write migrate_waste_log.py — waste_log table migration
- [ ] Write migrate_tickets.py — tickets table migration
- [ ] Write migrate_timesheet.py — timesheet table migration
- [ ] Write migrate_timesheet_approvals.py — timesheet_approvals table migration
- [ ] Write migrate_cash_drawer.py — cash_drawer table migration
- [ ] Write migrate_delivery_addresses.py — delivery_addresses table migration
- [ ] Write migrate_scheduled_pricing.py — scheduled_pricing table migration
- [ ] Write migrate_webhooks.py — webhooks table migration
- [ ] Write migrate_tables.py — tables table migration
- [ ] Write migrate_table_ads.py — table_ads table migration
- [ ] Write migrate_security_events.py — security_events table migration
- [ ] Write migrate_known_ips.py — known_ips table migration
- [ ] Write migrate_login_attempts.py — login_attempts table migration
- [ ] Write migrate_refunded_orders.py — refunded_orders table migration
- [ ] Write migrate_cleared_orders.py — cleared_orders table migration

## Phase 3: Endpoint Refactor (one endpoint at a time)
- [ ] Create db.py helper module for SQLite queries
- [ ] Refactor /api/clock/status to use SQLite (feature-flagged)
- [ ] Refactor /api/clock/in to use SQLite (feature-flagged)
- [ ] Refactor /api/clock/out to use SQLite (feature-flagged)
- [ ] Refactor /api/clock/edit to use SQLite (feature-flagged)
- [ ] Refactor /api/admin_shifts to use SQLite (feature-flagged)
- [ ] Refactor /api/items endpoints to use SQLite (feature-flagged)
- [ ] Refactor /api/inventory endpoints to use SQLite (feature-flagged)
- [ ] Refactor /api/orders endpoints to use SQLite (feature-flagged)
- [ ] Refactor /api/admin_timesheet to use SQLite (feature-flagged)
- [ ] Refactor /api/timesheet/pay_period to use SQLite (feature-flagged)

## Phase 4: Flip the Switch & Clean Up
- [ ] Run all migration scripts one final time to sync
- [ ] Set `use_database: true` and monitor
- [ ] If stable: remove old JSON load/save code
- [ ] Add backup script for SQLite (migrations/backup_db.py)

## Phase 5: Optimization
- [ ] Add indexes for common queries (user_id, dates, order_id)
- [ ] Enable WAL mode (PRAGMA journal_mode=WAL)
- [ ] Add db_health.py to scripts/ (already exists — enhance for SQLite)
- [ ] Add query logging for slow queries
- [ ] Add VACUUM + integrity_check automation

## COMPLETED (this session)
- [x] **Initial setup** — Created DB_TASKS.md, db.py, migrations/, and first migration script (users)
- [x] **migrate_users.py** — Migrated 6 users from users.json to SQLite. Verified row count matches. Idempotency tested. Commit: 0df93e1

## ROLLBACK PLAN (always keep current)
How to revert to JSON mode if DB breaks:
- [ ] Set `use_database: false` in timesheet_config.json (disables all SQLite reads in endpoints)
- [ ] Old JSON files are NOT deleted — always preserved as fallback
- [ ] If SQLite becomes corrupted, delete pos.db and re-run migration scripts
- [ ] All migration scripts use INSERT OR REPLACE — safe to re-run
- [ ] JSON files remain the source of truth until Phase 4 (when we flip the switch)

## Data Stores Summary

| JSON File | Table Name | Type | Records | Migrated |
|---|---|---|---|---|
| users.json | users | dict (key=pin) | 6 | ✓ |
| shift_log.json | shift_log | array | 8 | |
| activity_log.json | activity_log | array | ~90 | |
| items.json | items | dict (key=category) | 14 items | |
| inventory.json | inventory | dict (key=item_name) | 15 | |
| loyalty_points.json | loyalty_points | dict (key=phone) | 0 | |
| orders.json | orders | array | 0 | |
| cleared_orders.json | cleared_orders | array | 0 | |
| combos.json | combos | object {combos:[]} | 0 | |
| favorites.json | favorites | dict | 0 | |
| waste_log.json | waste_log | array | 0 | |
| tickets.json | tickets | array | 0 | |
| timesheet.json | timesheet | array | ? | |
| timesheet_approvals.json | timesheet_approvals | array | 0 | |
| cash_drawer.json | cash_drawer | object | 0 | |
| delivery_addresses.json | delivery_addresses | dict | 0 | |
| scheduled_pricing.json | scheduled_pricing | array | 0 | |
| webhooks.json | webhooks | dict | 0 | |
| tables.json | tables | dict | 0 | |
| table_ads.json | table_ads | object | 0 | |
| security_events.json | security_events | array | ? | |
| known_ips.json | known_ips | dict | ? | |
| login_attempts.json | login_attempts | dict | ? | |
| security_config.json | — | config singleton | — | keep JSON |
| timesheet_config.json | — | config singleton | — | keep JSON |
| tax_config.json | — | config singleton | — | keep JSON |
| email_config.json | — | config singleton | — | keep JSON |
| service_charge_config.json | — | config singleton | — | keep JSON |
| order_counter.json | — | config singleton | — | keep JSON |
| discounts.json | — | config singleton | — | keep JSON |
| refunded_orders.json | refunded_orders | array | 1 | |

## Schema Reference

### users
```sql
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
);
```

### shift_log
```sql
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
);
```

### activity_log
```sql
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    user_id TEXT,
    user_role TEXT,
    details TEXT DEFAULT '{}'
);
```

### items
```sql
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
);
```

### inventory
```sql
CREATE TABLE IF NOT EXISTS inventory (
    item_name TEXT PRIMARY KEY,
    stock INTEGER DEFAULT 0,
    threshold INTEGER DEFAULT 10,
    unit TEXT,
    last_updated TEXT
);
```

### loyalty_points
```sql
CREATE TABLE IF NOT EXISTS loyalty_points (
    phone TEXT PRIMARY KEY,
    name TEXT,
    points INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    last_visit TEXT
);
```

### orders
```sql
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
    completed_at TEXT
);
```

### Other tables follow the same pattern — see individual migration scripts for full schema.

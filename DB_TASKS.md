# POS Database Migration Tasks
> Last run: 2026-06-25 02:xx UTC
> Current phase: Phase 2 — Migration Scripts (7/24 complete)

## Phase 1: Schema Design
- [x] Design all SQLite table schemas (users, shift_log, orders, items, inventory, etc.)
- [x] Create `db.py` core module with get_db(), query(), execute(), init_db()
- [x] Add `use_database` feature flag to timesheet_config.json
- [x] Create `migrations/` directory for migration scripts

## Phase 2: Migration Scripts (one at a time)
- [x] Write migrate_users.py — users table migration (6 rows verified ✓)
- [x] Write migrate_shift_log.py — shift_log table migration (16 rows verified ✓)
- [x] Write migrate_activity_log.py — activity_log table migration (377 rows verified ✓)
- [x] Write migrate_items.py — items table migration (14 rows verified ✓)
- [x] Write migrate_inventory.py — inventory table migration (16 rows verified ✓)
- [x] Write migrate_loyalty_points.py — loyalty_points table migration (2 records verified ✓)
- [x] Write migrate_orders.py — orders table migration (66 rows verified ✓)
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
- [x] **migrate_shift_log.py** — Migrated 16 shifts from shift_log.json to SQLite. All fields preserved (edits JSON, breaks JSON, late tracking). Idempotency tested. Commit: 12e292b
- [x] **migrate_activity_log.py** — Migrated 377 events from activity_log.json to SQLite. All fields preserved (details JSON). Idempotency tested. Commit: 35c9bad
- [x] **Add `use_database` flag** — Added `use_database: false` to timesheet_config.json for feature-gated endpoint refactoring
- [x] **migrate_items.py** — Migrated 14 items from items.json to SQLite. Flattened 3 categories (Foods, Drinks, Snacks) into category column. Modifiers JSON preserved. Idempotency tested. Commit: 95e8124
- [x] **migrate_inventory.py** — Migrated 16 inventory items from inventory.json to SQLite. Mapped 'low_stock_threshold' to 'threshold' column. Idempotency tested. Commit: 7d5ee21
- [x] **migrate_loyalty_points.py** — Migrated 2 loyalty points records from loyalty_points.json to SQLite. Extended schema with 7 fields (email, notes, address, total_redeemed, total_orders, created_at, history). Added schema migration helper in db.py for forward-compatible column additions. Commit: 9b576e3
- [x] **migrate_orders.py** — Migrated 66 orders from orders.json to SQLite. Handles edge cases (payment as dict, null fields, order 55 with dict payment). Added service_charge_amount + customer_email columns to orders schema. Also migrates cleared_orders.json (0 cleared). Idempotency tested. Commit: TBD

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
| shift_log.json | shift_log | array | 24 | ✓ |
| activity_log.json | activity_log | array | 377 | ✓ |
| items.json | items | dict (key=category) | 14 items | ✓ |
|| inventory.json | inventory | dict (key=item_name) | 16 | ✓ |
|| loyalty_points.json | loyalty_points | dict (key=phone) | 2 | ✓ |
| orders.json | orders | array | 66 | ✓ |
| cleared_orders.json | cleared_orders | array | 0 | ✓ |
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
    customer_email TEXT DEFAULT '',
    discount_code TEXT,
    discount_amount REAL DEFAULT 0,
    item_notes TEXT DEFAULT '{}',
    service_charge_amount REAL DEFAULT 0,
    claimed_by TEXT,
    claimed_at TEXT,
    completed_at TEXT
);
```

### Other tables follow the same pattern — see individual migration scripts for full schema.

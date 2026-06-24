# POS Security Tasks
> Last run: 2026-06-24 16:45 UTC

## CRITICAL — LOGIN & AUTH SECURITY (check every run)

### CRITICAL: Debug mode enabled in production
- [x] **Disable debug mode** — `socketio.run(app, debug=True)` at line 8730 (original). Exposes Werkzeug debugger with remote code execution. Changed to `debug=False, allow_unsafe_werkzeug=False`.

### CRITICAL: Clock in/out endpoints lack credential verification
- [x] **Add PIN verification + rate limiting to clock-in/out** — `/api/clock/in` and `/api/clock/out` accepted any valid user_id without verifying the caller knows the PIN. No rate limiting. Allowed PIN enumeration. Added `clock_failed_attempts` tracking dict, `_record_clock_failure()` helper, IP-based and user-ID-based rate limiting (10 attempts/60s, 15min lock), and generic error messages that don't reveal if user exists.

### CRITICAL: GET /api/users leaked ALL user PINs with no auth
- [x] **Add auth check to GET /api/users** — `GET /api/users` returned all users including PINs as dict keys with zero authentication. Anyone on the network could enumerate every user PIN. Added `adminPin` query parameter requirement with `manage_users` permission check. Updated frontend to pass `currentUser.id`. Verified: no auth → 401, invalid PIN → 403, valid user without perm → 403, owner → 200.

### CRITICAL: 15 unauthenticated GET endpoints exposed sensitive data
- [x] **Add auth to 6 analytics endpoints** — `/api/analytics/most_ordered`, `/api/analytics/hourly_sales`, `/api/analytics/daily_revenue`, `/api/analytics/popular_combos`, `/api/analytics/item_trends`, `/api/analytics/summary` all leaked sales/revenue/item data with zero auth. Added `view_stats` permission check via `adminPin` query param. Updated frontend to pass `currentUser.id` in fetch calls.
- [x] **Add auth to /api/owner/credentials/status** — Leaked owner username and whether credentials exist. Added `manage_users` permission check.
- [x] **Add auth to delivery address endpoints** — `/api/delivery_addresses` GET and `/api/orders/<id>/delivery_address` GET leaked customer addresses. Added `manage_orders` permission check.
- [x] **Add auth to /api/email/config** — Leaked SMTP server/port/username (password was masked). Added `manage_items` permission check.
- [x] **Add auth to /api/orders/receipt/<id>** — Anyone could view any order's receipt. Added `manage_orders` permission check.
- [x] **Add auth to /api/menu/history** — Leaked menu backup filenames/dates. Added `manage_items` permission check.
- [x] **Add auth to /api/inventory and /api/inventory/low_stock** — Leaked inventory stock levels. Added `manage_items` permission check.
- [x] **Add auth to /api/ads GET** — Documentation said "requires manage_items" but no actual check. Fixed: added `manage_items` permission check.

### CRITICAL: /api/tables/tab/<int:table_number>/checkout has zero auth
- [x] **Add POS access auth to tab checkout endpoint** — The `/api/tables/tab/<int:table_number>/checkout` POST endpoint accepted any `userId` without verifying it's a valid employee PIN. Anyone on the network could close out all orders at any table with any value in `userId`. Added `check_perm(user_id, "pos_access")` check. Verified: invalid PIN → 403, valid PIN → proceeds, no PIN → 400.

### CRITICAL: /api/orders/lookup GET had no auth — full order data exposed (FIXED this run)
- [x] **Add tiered auth to /api/orders/lookup** — This GET endpoint returned full order details (items, prices, totals, payment info, customer data) with zero authentication. Anyone on the network could look up any order by order_id or by table_number. Fix: Added `adminPin` query param support. Authenticated requests (valid PIN with pos_access or manage_orders) get full data. Unauthenticated requests get limited kiosk-safe data (no payment info, no PII, no customer data). Table-number lookups also support kiosk mode with limited fields. Verified: unauthenticated order lookup returns limited safe fields, authenticated returns full data, table lookup works in both modes.

### HIGH: PIN stored as plaintext dict key
- [ ] **Hash PINs** — User ID IS the PIN, stored as the dict key in users.json in plaintext. Anyone with file-system access (or backup access) sees all PINs. Requires architectural change: separate `user_id` (internal) from `pin_hash`. Postgres/Long-term: store PIN hash, not the PIN itself. MITIGATED: files now saved with 0600 permissions.

### HIGH: No session tokens for all endpoints — PIN sent in every request
- [ ] **Require session tokens on all endpoints** — Currently most endpoints accept raw PIN (`adminPin`) instead of requiring a session token. This means 2FA can be bypassed once PIN is known. Sessions DO exist (8h active, 24h idle timeout) but most endpoints bypass them. Need to migrate endpoints to prefer `session_token` over `adminPin`.

## HIGH — DATA PROTECTION & COMPLIANCE

### HIGH: PIN complexity — now BLOCKS weak PINs (FIXED this run)
- [x] **Block weak PINs instead of warning** — The `change_pin`, `reset_pin`, and `add_user` endpoints now REJECT weak/guessable PINs (1111, 1234, 0000, 6666, etc.) with a 400 error instead of just warning. Applied to all three PIN-creation paths: self-service change, admin reset, and new user creation. Verified with curl tests — all weak patterns rejected, strong patterns accepted.

### HIGH: TOTP secrets stored in plaintext in users.json
- [ ] **Protect TOTP secrets** — `totp_secret` is stored in plaintext in users.json. MITIGATED: file permissions now enforced to 0600 (owner-only). For stronger protection, encrypt TOTP secrets at rest with a server-side key.

### HIGH: /api/orders/lookup GET had no auth (FIXED this run)
- [x] **Add tiered kiosk-safe auth to /api/orders/lookup** — See CRITICAL section above. Unauthenticated requests get limited data (no payment info, no PII). Authenticated requests get full data.

### HIGH: /api/sync_orders POST has no full auth
- [x] **Add user existence validation to /api/sync_orders** — Added check that any `user` field in synced orders exists in users.json (prevents fake user injection). Full PIN verification not added because this endpoint supports kiosk/offline flows where customers may not have accounts.

## MEDIUM — HARDENING

### MEDIUM: Thread-safe file writes — added I/O lock (FIXED this run)
- [x] **Add threading lock to save_json_data** — `save_json_data` had no concurrency protection. Multiple concurrent requests modifying the same data file (e.g., users.json) could race: Thread A loads data → Thread B loads same data → Thread A modifies+saves → Thread B modifies+saves (overwrites Thread A's changes). This is the likely root cause of the recurring 2FA state loss bug (SEC-001/SEC-013). Added `_file_io_lock` (threading.RLock) wrapping all file writes. The lock prevents interleaved writes to the same file, ensuring each save completes fully before the next begins.

### MEDIUM: CORS wide open
- [x] **Restrict CORS** — `CORS(app)` changed from wildcard to allowed origins (localhost:5000, localhost:3000, 192.168.*, 10.*). SocketIO `cors_allowed_origins` changed from `"*"` to specific domains. Prevents unauthorized cross-origin requests from unknown origins.

### MEDIUM: Error pages may leak stack traces
- [x] **Add custom 404/500 JSON error handlers** — Flask's default error handlers return HTML with stack traces. Added `@app.errorhandler(404)` and `@app.errorhandler(500)` that return JSON without stack traces or paths. Verified: 404 → `{"message":"Endpoint not found."}` with 200 OK? Actually 404 with JSON body. 500 handler registered for unhandled exceptions.

### MEDIUM: App runs as root
- [ ] **Run as non-root user** — All processes run as root. Any compromised endpoint gives full system access.

### MEDIUM: No app.secret_key configured
- [x] **Set Flask secret_key** — Added `app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))` at app startup. Falls back to a randomly generated key if not set via environment variable.

### MEDIUM: Kitchen/display endpoints still unauthenticated
- [ ] **Add optional API key auth for kitchen/drivethrough/pickup displays** — `/api/kitchen/queue`, `/api/kitchen/stats`, `/api/kitchen/order/<id>`, `/api/drivethrough/*`, `/api/customer-display/*`, `/api/pickup-display/*` have no auth. These are intentionally public for displays but should have an optional shared-secret API key mechanism to prevent network snooping in multi-tenant deployments.

### MEDIUM: save_json_data creates world-readable files
- [x] **Permanently enforce 0600 on all saved JSON files** — `save_json_data()` now always enforces 0600 (owner read/write only). All 30+ JSON files verified at 0600.

### MEDIUM: File permissions need periodic reinforcement
- [x] **Re-harden 30+ JSON file permissions to 0600** — Now that save_json_data permanently enforces 0600, permissions survive writes.

## LOW — POLISH

### LOW: Password complexity — strengthened (FIXED this run)
- [x] **Enforce 8+ char, mixed case + number** — Changed minimum from 6 to 8 chars. Added requirement for uppercase, lowercase, and a number. Applied on `/api/owner/credentials` endpoint. Verified: 7-char rejected, no-uppercase rejected, no-number rejected, 10-char mixed-case with number accepted.

### LOW: SHA-256 used for password hashing (should be bcrypt/argon2)
- [ ] **Upgrade password hashing** — `hash_password()` uses SHA-256 with random salt. Not GPU-resistant. Should use bcrypt or argon2 for proper password hashing. Not critical since passwords are only for owner login (PINs are the main auth method).

## COMPLETED (this session)

### Run: 2026-06-24 16:45 UTC

- [x] **Remove stale owner_pin from security_config.json** — The field `owner_pin: "1111"` was stored in `security_config.json` but never read by app.py. This was a latent credential exposure — the owner's PIN sitting in a config file. Removed. Verified: `owner_pin` no longer in config keys.
- [x] **Add custom 404/500 JSON error handlers** — MEDIUM: Flask's default handlers leak stack traces and file paths. Added `@app.errorhandler(404)` and `@app.errorhandler(500)` that return `{message}` JSON instead of HTML. Verified: `GET /api/nonexistent` → `{"message":"Endpoint not found."}` 404.
- [x] **Strengthen owner password policy** — LOW: Changed minimum length from 6 to 8. Added requirements for uppercase, lowercase, and a digit on `/api/owner/credentials`. Verified: short, no-upper, and no-number passwords all rejected with specific error messages.

## WATCHLIST (monitor, don't fix yet)

- SEC-001/SEC-013: 2FA persistence bug — suspected race condition; threading lock added in previous run. Confirmed in this run that the `twofa_verify()` code flow is correct (loads users.json → modifies in memory → saves). Monitor next 2-3 runs to confirm fix.
- User 9999 login attempts at ~07:56 UTC on 2026-06-24: 20 rapid attempts from 127.0.0.1 + 203.0.113.42 + 192.168.1.50. User 9999 does NOT currently exist in users.json. The attempts all returned "2fa_required" which suggests 9999 MAY have existed briefly and was deleted. Verify no credential stuffing succeeded. Consider adding endpoint to clean up phantom users.
- security_config.json had stale `owner_pin: "1111"` field — removed this run. No code references to it were found in app.py. Was likely a leftover from an earlier design.

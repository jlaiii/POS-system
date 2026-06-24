# POS Security Tasks
> Last run: 2026-06-24 08:43 UTC

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

### CRITICAL: /api/tables/tab/<int:table_number>/checkout has zero auth (NEW — this run)
- [x] **Add POS access auth to tab checkout endpoint** — The `/api/tables/tab/<int:table_number>/checkout` POST endpoint accepted any `userId` without verifying it's a valid employee PIN. Anyone on the network could close out all orders at any table with any value in `userId`. Added `check_perm(user_id, "pos_access")` check. Verified: invalid PIN → 403, valid PIN → proceeds, no PIN → 400.

### HIGH: PIN stored as plaintext dict key
- [ ] **Hash PINs** — User ID IS the PIN, stored as the dict key in users.json in plaintext. Anyone with file-system access (or backup access) sees all PINs. Requires architectural change: separate `user_id` (internal) from `pin_hash`. Postgres/Long-term: store PIN hash, not the PIN itself. MITIGATED: files now saved with 0600 permissions.

### HIGH: No session tokens for all endpoints — PIN sent in every request
- [ ] **Require session tokens on all endpoints** — Currently most endpoints accept raw PIN (`adminPin`) instead of requiring a session token. This means 2FA can be bypassed once PIN is known. Sessions DO exist (8h active, 24h idle timeout) but most endpoints bypass them. Need to migrate endpoints to prefer `session_token` over `adminPin`.

## HIGH — DATA PROTECTION & COMPLIANCE

### HIGH: PIN complexity not enforced — only warns
- [ ] **Block weak PINs instead of warning** — The `change_pin` endpoint checks for guessable patterns but only warns. Should reject weak PINs (1111, 1234, 0000, etc.) with a 400 error and suggest a stronger one.

### HIGH: TOTP secrets stored in plaintext in users.json
- [ ] **Protect TOTP secrets** — `totp_secret` is stored in plaintext in users.json. MITIGATED: file permissions now enforced to 0600 (owner-only). For stronger protection, encrypt TOTP secrets at rest with a server-side key.

### HIGH: /api/orders/lookup GET has no auth (exposes full order details)
- [ ] **Add kiosk-safe auth to /api/orders/lookup** — This GET endpoint returns full order details (items, prices, totals, payment info) with zero authentication. Used by kiosk payment flow so needs careful design — e.g., session token check for staff, shared-secret API key for kiosk devices, or IP-based restriction.

### HIGH: /api/sync_orders POST has no full auth
- [x] **Add user existence validation to /api/sync_orders** — Added check that any `user` field in synced orders exists in users.json (prevents fake user injection). Full PIN verification not added because this endpoint supports kiosk/offline flows where customers may not have accounts.

## MEDIUM — HARDENING

### MEDIUM: CORS wide open
- [x] **Restrict CORS** — `CORS(app)` changed from wildcard to allowed origins (localhost:5000, localhost:3000, 192.168.*, 10.*). SocketIO `cors_allowed_origins` changed from `"*"` to specific domains. Prevents unauthorized cross-origin requests from unknown origins.

### MEDIUM: Error pages may leak stack traces
- [ ] **Custom error handlers** — Flask's default error handler may leak stack traces in debug mode. Add `@app.errorhandler(500)` and `@app.errorhandler(404)` handlers that return JSON without stack traces. NOTE: debug mode already disabled (CRITICAL fix).

### MEDIUM: App runs as root
- [ ] **Run as non-root user** — All processes run as root. Any compromised endpoint gives full system access.

### MEDIUM: No app.secret_key configured
- [x] **Set Flask secret_key** — Added `app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))` at app startup. Falls back to a randomly generated key if not set via environment variable.

### MEDIUM: Kitchen/display endpoints still unauthenticated
- [ ] **Add optional API key auth for kitchen/drivethrough/pickup displays** — `/api/kitchen/queue`, `/api/kitchen/stats`, `/api/kitchen/order/<id>`, `/api/drivethrough/*`, `/api/customer-display/*`, `/api/pickup-display/*` have no auth. These are intentionally public for displays, but should have an optional shared-secret API key mechanism to prevent network snooping in multi-tenant deployments.

### MEDIUM: save_json_data creates world-readable files
- [x] **Permanently enforce 0600 on all saved JSON files** — `save_json_data()` was restoring files to 0444/0644 after write. Changed to always enforce 0600 (owner read/write only). This permanently prevents any JSON data file from being world-readable, regardless of initial permissions. All 30+ JSON files verified at 0600.

### MEDIUM: File permissions need periodic reinforcement
- [x] **Re-harden 30+ JSON file permissions to 0600** — Previous hardenings didn't persist because save_json_data restored 0444/0644. Now that save_json_data permanently enforces 0600, permissions will survive writes.

## LOW — POLISH

### LOW: Password complexity minimum is only 6 chars
- [ ] **Strengthen password policy** — Line 781 (original): `if len(password) < 6` — minimum is 6 characters for owner password. Should be 8+ with mixed case and numbers.

### LOW: SHA-256 used for password hashing (should be bcrypt/argon2)
- [ ] **Upgrade password hashing** — `hash_password()` uses SHA-256 with random salt. Not GPU-resistant. Should use bcrypt or argon2 for proper password hashing. Not critical since passwords are only for owner login (PINs are the main auth method).

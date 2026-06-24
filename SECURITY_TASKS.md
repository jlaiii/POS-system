# POS Security Tasks
> Last run: 2026-06-24 03:50 UTC

## CRITICAL — LOGIN & AUTH SECURITY (check every run)

### CRITICAL: Debug mode enabled in production
- [x] **Disable debug mode** — `socketio.run(app, debug=True)` at line 8730 (original). Exposes Werkzeug debugger with remote code execution. Changed to `debug=False, allow_unsafe_werkzeug=False`.

### CRITICAL: Clock in/out endpoints lack credential verification
- [x] **Add PIN verification + rate limiting to clock-in/out** — `/api/clock/in` and `/api/clock/out` accepted any valid user_id without verifying the caller knows the PIN. No rate limiting. Allowed PIN enumeration. Added `clock_failed_attempts` tracking dict, `_record_clock_failure()` helper, IP-based and user-ID-based rate limiting (10 attempts/60s, 15min lock), and generic error messages that don't reveal if user exists.

### CRITICAL: GET /api/users leaked ALL user PINs with no auth
- [x] **Add auth check to GET /api/users** — `GET /api/users` returned all users including PINs as dict keys with zero authentication. Anyone on the network could enumerate every user PIN. Added `adminPin` query parameter requirement with `manage_users` permission check. Updated frontend to pass `currentUser.id`. Verified: no auth → 401, invalid PIN → 403, valid user without perm → 403, owner → 200.

### CRITICAL: 15 unauthenticated GET endpoints exposed sensitive data
- [x] **Add auth to 6 analytics endpoints** — `/api/analytics/most_ordered`, `/api/analytics/hourly_sales`, `/api/analytics/daily_revenue`, `/api/analytics/popular_combos`, `/api/analytics/item_trends`, `/api/analytics/summary` all leaked sales/revenue/item data with zero auth. Added `view_stats` permission check via `adminPin` query param. Updated frontend to pass `currentUser.id` in fetch calls. Commit: TBD
- [x] **Add auth to /api/owner/credentials/status** — Leaked owner username and whether credentials exist. Added `manage_users` permission check.
- [x] **Add auth to delivery address endpoints** — `/api/delivery_addresses` GET and `/api/orders/<id>/delivery_address` GET leaked customer addresses. Added `manage_orders` permission check.
- [x] **Add auth to /api/email/config** — Leaked SMTP server/port/username (password was masked). Added `manage_items` permission check.
- [x] **Add auth to /api/orders/receipt/<id>** — Anyone could view any order's receipt. Added `manage_orders` permission check.
- [x] **Add auth to /api/menu/history** — Leaked menu backup filenames/dates. Added `manage_items` permission check.
- [x] **Add auth to /api/inventory and /api/inventory/low_stock** — Leaked inventory stock levels. Added `manage_items` permission check.
- [x] **Add auth to /api/ads GET** — Documentation said "requires manage_items" but no actual check. Fixed: added `manage_items` permission check.

### CRITICAL: /api/tables/tab/<int:table_number>/checkout has zero auth (NEW — this run)
- [x] **Add POS access auth to tab checkout endpoint** — The `/api/tables/tab/<int:table_number>/checkout` POST endpoint accepted any `userId` without verifying it's a valid employee PIN. Anyone on the network could close out all orders at any table with any value in `userId`. Added `check_perm(user_id, "pos_access")` check. Verified: invalid PIN → 403, valid PIN → proceeds, no PIN → 400. Commit: This run.

### HIGH: PIN stored as plaintext dict key
- [ ] **Hash PINs** — User ID IS the PIN, stored as the dict key in users.json in plaintext. Anyone with file-system access (or backup access) sees all PINs. Requires architectural change: separate `user_id` (internal) from `pin_hash`. Postgres/Long-term: store PIN hash, not the PIN itself.

### HIGH: No session tokens — PIN sent in every request
- [ ] **Implement session tokens** — Currently no server-side sessions. The PIN credential is sent with every request in the `adminPin` field. Generate a random session token on login, require it (instead of adminPin) on subsequent requests. This also enables proper logout (token invalidation) and idle timeout.

### HIGH: No idle session timeout
- [ ] **Enforce idle timeout** — No session expiration exists. Once logged in, the user stays logged in indefinitely (until browser close or manual logout). Add 8-hour idle timeout on admin sessions, 2-hour on user sessions.

## HIGH — DATA PROTECTION & COMPLIANCE

### HIGH: CORS wide open
- [ ] **Restrict CORS** — `CORS(app)` on line 22 allows all origins. SocketIO has `cors_allowed_origins="*"`. Restrict to known domains.

### HIGH: PIN complexity not enforced — only warns
- [ ] **Block weak PINs instead of warning** — The `change_pin` endpoint checks for guessable patterns but only warns. Should reject weak PINs (1111, 1234, 0000, etc.) with a 400 error and suggest a stronger one.

### HIGH: TOTP secrets stored in plaintext in world-readable users.json
- [ ] **Protect TOTP secrets** — `totp_secret` for user "1234" is stored in plaintext in users.json (now 600, but was 644). If 2FA is compromised, an attacker with TOTP secret can generate valid codes. Either encrypt TOTP secrets at rest or restrict file access further.

### HIGH: /api/orders/lookup GET has no auth (exposes full order details)
- [ ] **Add kiosk-safe auth to /api/orders/lookup** — This GET endpoint returns full order details (items, prices, totals, payment info) with zero authentication. Used by kiosk payment flow so needs careful design — add session token check for staff, shared-secret API key for kiosk devices, or IP-based restriction.

### HIGH: /api/sync_orders POST has no auth (offline order injection)
- [ ] **Add employee PIN verification to /api/sync_orders** — This endpoint processes offline-queued orders without any authentication check. An attacker could inject fake orders, manipulate inventory, and earn loyalty points. Add a `user` field check that at minimum verifies the submitting user exists in users.json (already partially present) and has `pos_access` permission.

## MEDIUM — HARDENING

### MEDIUM: Error pages may leak stack traces
- [ ] **Custom error handlers** — Flask's default error handler may leak stack traces in debug mode. Add `@app.errorhandler(500)` and `@app.errorhandler(404)` handlers that return JSON without stack traces.

### MEDIUM: App runs as root
- [ ] **Run as non-root user** — All processes run as root. Any compromised endpoint gives full system access.

### MEDIUM: No app.secret_key configured
- [ ] **Set Flask secret_key** — No `app.secret_key` is configured anywhere. While the app doesn't use Flask sessions (uses PIN-based auth), future session implementations need this. Should load from environment variable.

### MEDIUM: Kitchen/display endpoints still unauthenticated
- [ ] **Add optional API key auth for kitchen/drivethrough/pickup displays** — `/api/kitchen/queue`, `/api/kitchen/stats`, `/api/kitchen/order/<id>`, `/api/drivethrough/*`, `/api/customer-display/*`, `/api/pickup-display/*` have no auth. These are intentionally public for displays, but should have an optional shared-secret API key mechanism to prevent network snooping in multi-tenant deployments.

## LOW — POLISH

### LOW: Password complexity minimum is only 6 chars
- [ ] **Strengthen password policy** — Line 781 (original): `if len(password) < 6` — minimum is 6 characters for owner password. Should be 8+ with mixed case and numbers.

### LOW: SHA-256 used for password hashing (should be bcrypt/argon2)
- [ ] **Upgrade password hashing** — `hash_password()` uses SHA-256 with random salt. Not GPU-resistant. Should use bcrypt or argon2 for proper password hashing. Not critical since passwords are only for owner login (PINs are the main auth method).

## COMPLETED (first run)
- [x] **Disable debug mode** — Changed `debug=True` to `debug=False`, `allow_unsafe_werkzeug=True` to `allow_unsafe_werkzeug=False`. Prevents remote code execution via Werkzeug debugger.
- [x] **Add rate limiting + PIN verification to clock-in/out** — Added `clock_failed_attempts` tracking, `_record_clock_failure()` helper, IP-based and user-ID-based rate limiting (10/60s, 15min lock), and generic "Invalid PIN." error messages that don't reveal whether a user exists. Prevents PIN enumeration and brute-force clock-in/out.

## COMPLETED (this run)
- [x] **Add auth check to GET /api/users** — Added `adminPin` query parameter with `manage_users` permission check to prevent anonymous PIN enumeration. Updated frontend to pass `currentUser.id`. Tested: no auth → 401, bad perm → 403, owner → 200.
- [x] **Add auth to 6 analytics GET endpoints (view_stats)** — All revenue/sales/trend analytics now require `adminPin` with `view_stats` permission. Updated frontend fetch calls.
- [x] **Add auth to /api/owner/credentials/status (manage_users)** — Prevents leaking owner username.
- [x] **Add auth to delivery address endpoints (manage_orders)** — /api/delivery_addresses and /api/orders/<id>/delivery_address no longer public.
- [x] **Add auth to /api/email/config GET (manage_items)** — SMTP config no longer publicly readable.
- [x] **Add auth to /api/orders/receipt/<id> GET (manage_orders)** — Receipts no longer publicly viewable.
- [x] **Add auth to /api/menu/history GET (manage_items)** — Menu backup history no longer public.
- [x] **Add auth to /api/inventory and /api/inventory/low_stock GET (manage_items)** — Inventory levels no longer public.
- [x] **Add auth to /api/ads GET (manage_items)** — Fixed missing auth check that was documented but not implemented.
- [x] **Add reusable check_get_auth() helper** — Created a centralized `check_get_auth(admin_pin, permission)` function for GET endpoint authentication, reducing code duplication and ensuring consistent auth patterns.
- [x] **Harden file permissions** — Changed 11 sensitive JSON files from 644 (world-readable) to 600 (owner-only). Includes users.json (PINs), shift_log.json (employee data), activity_log.json (audit trail), orders.json, delivery_addresses.json, and others.

## COMPLETED (this run) — 2026-06-24 03:50
- [x] **Add auth to all table GET endpoints (4 endpoints)** — `/api/tables`, `/api/tables/tab/<table_number>/detail`, `/api/tables/tab/<table_number>`, `/api/tables/tab/<table_number>/history` all had zero authentication and leaked full order data (items, prices, totals, payment info). Added: `/api/tables` uses conditional auth (strips financial data without adminPin), other three require `pos_access` permission via `check_get_auth()`. Updated 6 frontend fetch calls to pass `currentUser.id`. Tested: no auth → 401, valid Pin → full data. Commit: This run.
- [x] **Harden file permissions on remaining JSON files** — Set 600 on users.json, inventory.json, items.json, refunded_orders.json, activity_log.json, login_attempts.json, security_config.json, security_events.json, loyalty_points.json, timesheet_config.json, pos.db and 12+ other JSON files. Prevents other system users from reading employee PINs, customer data, and order data.

## WATCHLIST (monitor, don't fix yet)
- Multi-tenant: No business_id scoping on data access — will be a problem when multi-tenant is deployed
- 2FA backup codes stored as SHA-256 hashes — good, but check that they're properly invalidated after use
- `X-Forwarded-For` header is trusted without validation — IP spoofing could bypass IP-based rate limiting; requires reverse proxy knowledge
- `/api/orders/lookup` and `/api/sync_orders` are intentionally public for kiosk/offline use but need shared-secret auth before multi-tenant deployment
- Session tokens exist but most endpoints still accept raw PIN (`adminPin`) instead of requiring session token — 2FA can be bypassed once PIN is known

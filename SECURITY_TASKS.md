# POS Security Tasks
> Last run: 2026-06-25 01:18 UTC

## CRITICAL — LOGIN & AUTH SECURITY (check every run)

### CRITICAL: Super admin login had NO rate limiting — FIXED this run
- [x] **Add rate limiting to /api/platform/super_admin/login** — The multi-tenant super admin login endpoint accepted unlimited PIN attempts with zero rate limiting. Super admin PIN "1111" could be brute-forced over the network with no lockout. Added IP-based `platform_failed_attempts` tracker with 5 attempts per 60s window, 10-minute lockout. Verified: 6th failed attempt returns 429 with lockout message. Valid PIN also blocked during lockout (correct — IP-based lock prevents sequential guessing).

### CRITICAL: Backup files were world-readable — FIXED this run
- [x] **Fix backup permissions to 600** — All backup archives (`backups/json/*.tar.gz`, `backups/db/*.db.gz`) had permissions `-rw-r--r--` (644), exposing user PINs and all system data to any user on the machine. Fixed: `chmod 600` on all existing backup files, `chmod 700` on backup directories. Also added `os.chmod(tar_path, 0o600)` and `os.chmod(compressed_file, 0o600)` to the backup script (`pos-backup.py`) so future backups also get owner-only permissions.

### CRITICAL: Logout does not invalidate session tokens — FIXED this run
- [x] **Invalidate session tokens on logout** — The `/api/logout` endpoint never removed sessions from `active_user_sessions`. After a user clicked "Logout", their session token remained valid indefinitely (until 8h expiry). Anyone with a stolen/intercepted token could continue using it after the user thought they were logged out.
  - Backend: `/api/logout` now calls `logout_session()` when a `sessionToken` is provided, or removes ALL sessions for the user when no token is given.
  - Frontend: `doLogout()` now sends `sessionToken: currentUser.sessionToken` with the logout request.
  - Verified: session token returns 403 "Invalid session token." after logout.

### CRITICAL: Debug mode enabled in production
- [x] **Disable debug mode** — `socketio.run(app, debug=True)` at line 8730 (original). Exposes Werkzeug debugger with remote code execution. Changed to `debug=False, allow_unsafe_werkzeug=False`.

### CRITICAL: Clock in/out endpoints lack credential verification
- [x] **Add PIN verification + rate limiting to clock-in/out** — `/api/clock/in` and `/api/clock/out` accepted any valid user_id without verifying the caller knows the PIN. No rate limiting. Allowed PIN enumeration. Added `clock_failed_attempts` tracking dict, `_record_clock_failure()` helper, IP-based and user-ID-based rate limiting (10 attempts/60s, 15min lock), and generic error messages that don't reveal if user exists.

### CRITICAL: GET /api/users leaked ALL user PINs with no auth
- [x] **Add auth check to GET /api/users** — `GET /api/users` returned all users including PINs as dict keys with zero authentication. Anyone on the network could enumerate every user PIN. Added `adminPin` query parameter requirement with `manage_users` permission check. Updated frontend to pass `currentUser.id`. Verified: no auth → 401, invalid PIN → 403, valid user without perm → 403, owner → 200.

### CRITICAL: 15 unauthenticated GET endpoints exposed sensitive data
- [x] **Add auth to 6 analytics endpoints** — `/api/analytics/most_ordered`, `/api/analytics/hourly_sales`, `/api/analytics/daily_revenue`, `/api/analytics/popular_combos`, `/api/analytics/item_trends`, `/api/analytics/summary` all leaked sales/revenue/item data with zero auth. Added `view_stats` permission check via `adminPin` query param.
- [x] **Add auth to /api/owner/credentials/status** — Leaked owner username and whether credentials exist. Added `manage_users` permission check.
- [x] **Add auth to delivery address endpoints** — `/api/delivery_addresses` GET and `/api/orders/<id>/delivery_address` GET leaked customer addresses. Added `manage_orders` permission check.
- [x] **Add auth to /api/email/config** — Leaked SMTP server/port/username. Added `manage_items` permission check.
- [x] **Add auth to /api/orders/receipt/<id>** — Anyone could view any order's receipt. Added `manage_orders` permission check.
- [x] **Add auth to /api/menu/history** — Leaked menu backup filenames/dates. Added `manage_items` permission check.
- [x] **Add auth to /api/inventory and /api/inventory/low_stock** — Leaked inventory stock levels. Added `manage_items` permission check.
- [x] **Add auth to /api/ads GET** — Documentation said "requires manage_items" but no actual check. Fixed: added `manage_items` permission check.

### CRITICAL: /api/tables/tab/<int:table_number>/checkout has zero auth
- [x] **Add POS access auth to tab checkout endpoint** — Added `check_perm(user_id, "pos_access")` check. Verified: invalid PIN → 403, valid PIN → proceeds, no PIN → 400.

### CRITICAL: /api/orders/lookup GET had no auth — full order data exposed (FIXED this run)
- [x] **Add tiered auth to /api/orders/lookup** — This GET endpoint returned full order details with zero authentication. Added tiered auth: authenticated requests get full data, unauthenticated get kiosk-safe limited fields (no payment info, no PII). Verified both modes.

### CRITICAL: Super admin sessions have NO expiration — OPEN
- [ ] **Add session expiry to platform super admin sessions** — `platform_sessions` dict stores sessions permanently. No idle timeout, no cleanup mechanism. Once a super admin logs in, the session token never expires. If a token is leaked or a machine left unattended, the session remains valid indefinitely. Fix: add session creation timestamp, check `created_at` on each request with a max session duration (e.g., 8h), and add idle timeout.

## HIGH — DATA PROTECTION & COMPLIANCE

### HIGH: Default super admin PIN is "1111" — OPEN
- [ ] **Change super admin default PIN** — `data/global/super_admins.json` stores super admin PIN "1111" in plaintext. Same as the default owner PIN. Already in the weak-PIN blocklist for regular users. Mitigated by rate limiting (added this run), but should be changed to a strong random PIN.

### HIGH: PIN stored as plaintext dict key
- [ ] **Hash PINs** — User ID IS the PIN, stored as the dict key in users.json in plaintext. Anyone with file-system access (or backup access) sees all PINs. Requires architectural change: separate `user_id` (internal) from `pin_hash`. MITIGATED: files now saved with 0600 permissions, backups also 0600.

### HIGH: No session tokens for all endpoints — PIN sent in every request
- [ ] **Require session tokens on all endpoints** — Currently most endpoints accept raw PIN (`adminPin`) instead of requiring a session token. This means 2FA can be bypassed once PIN is known. Sessions DO exist (8h active, 24h idle timeout) but most endpoints bypass them.

### HIGH: TOTP secrets stored in plaintext in users.json
- [ ] **Protect TOTP secrets** — `totp_secret` is stored in plaintext in users.json. MITIGATED: file permissions now enforced to 0600 (owner-only). For stronger protection, encrypt TOTP secrets at rest with a server-side key.

### HIGH: require_2fa_for_admins is disabled by default
- [ ] **Enable mandatory 2FA for admin accounts** — `security_config.json` has `require_2fa_for_admins: false`. Admin accounts (including the owner) are NOT forced to use 2FA. Should default to `true` for admin/owner roles, or at minimum send a Discord alert when an admin without 2FA logs in.

### HIGH: Existing weak PINs in active use
- [ ] **Force PIN change for users with weak PINs** — The system now blocks new weak PINs (1111, 1234, 2222, 123456, etc.) but existing users with these PINs were never forced to change. Currently: Owner(1111), Employee One(1234), Manager(2222), Carlos(123456) all have weak PINs.

## MEDIUM — HARDENING

### MEDIUM: Thread-safe file writes — added I/O lock (FIXED this run)
- [x] **Add threading lock to save_json_data** — `save_json_data` had no concurrency protection. Added `_file_io_lock` (threading.RLock) wrapping all file writes.

### MEDIUM: CORS wide open
- [x] **Restrict CORS** — `CORS(app)` changed from wildcard to allowed origins (localhost:5000, localhost:3000, 192.168.*, 10.*). SocketIO `cors_allowed_origins` changed from `"*"` to specific domains.

### MEDIUM: Error pages may leak stack traces
- [x] **Add custom 404/500 JSON error handlers** — Flask's default error handlers return HTML with stack traces. Added JSON error handlers.

### MEDIUM: App runs as root
- [ ] **Run as non-root user** — All processes run as root. Any compromised endpoint gives full system access.

### MEDIUM: No app.secret_key configured
- [x] **Set Flask secret_key** — Added `app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))`.

### MEDIUM: Kitchen/display endpoints still unauthenticated
- [ ] **Add optional API key auth for kitchen/drivethrough/pickup displays** — These endpoints are intentionally public for displays but should have an optional shared-secret API key mechanism to prevent network snooping in multi-tenant deployments.

### MEDIUM: save_json_data creates world-readable files
- [x] **Permanently enforce 0600 on all saved JSON files** — `save_json_data()` now always enforces 0600.

### MEDIUM: app.static_folder used as root for backup/restore
- [ ] **Review backup/restore file path scoping** — Backup and restore endpoints use `app.static_folder` as root directory. While path traversal is partially mitigated, the restore endpoint could potentially overwrite non-JSON files in multi-tenant mode.

## LOW — POLISH

### LOW: Password complexity — strengthened (FIXED this run)
- [x] **Enforce 8+ char, mixed case + number** — Applied on `/api/owner/credentials`.

### LOW: SHA-256 used for password hashing (should be bcrypt/argon2)
- [ ] **Upgrade password hashing** — `hash_password()` uses SHA-256 with random salt. Not GPU-resistant. Should use bcrypt or argon2 for proper password hashing. Not critical since passwords are only for owner login.

### LOW: Dependencies are current — no action needed
- [x] **Verify dependency versions** — Flask 3.1.3, pyotp 2.9.0, qrcode 7.4.2, Werkzeug 3.1.8, eventlet 0.41.0. All current stable versions. No known critical CVEs in use.

## COMPLETED (this session)

### Run: 2026-06-25 01:18 UTC
- [x] **Add rate limiting to super admin login** — CRITICAL: `/api/platform/super_admin/login` had zero protection. Added IP-based 5-attempt/60s window with 10min lockout. Verified with curl — 6th attempt returns 429.
- [x] **Fix backup file permissions** — CRITICAL: Backup archives were world-readable (644). Fixed to 600. Added chmod to backup script for future backups.
- [x] **Verify all JSON files at 0600** — Confirmed all JSON data files have owner-only permissions. package.json, package-lock.json, printer_config.json, ticket_templates.json are 644 (non-data files).
- [x] **Verify dependencies are current** — Flask 3.1.3, Werkzeug 3.1.8, pyotp 2.9.0, qrcode 7.4.2, eventlet 0.41.0 — all current.

### Run: 2026-06-24 18:00 UTC
- [x] **Invalidate session tokens on logout** — CRITICAL: The `/api/logout` endpoint never invalidated session tokens. Fixed: backend calls `logout_session()`, frontend sends `sessionToken`. Verified.

### Run: 2026-06-24 16:45 UTC
- [x] **Remove stale owner_pin from security_config.json** — Removed `owner_pin: "1111"` from config file.
- [x] **Add custom 404/500 JSON error handlers** — MEDIUM: Flask's default handlers leak stack traces.
- [x] **Strengthen owner password policy** — LOW: minimum 8 chars, uppercase, lowercase, digit.

## WATCHLIST (monitor, don't fix yet)

- SEC-001/SEC-013: 2FA persistence bug — suspected race condition; threading lock added. Monitor next 2-3 runs to confirm fix.
- User 9999 login attempts at ~07:56 UTC on 2026-06-24: 20 rapid attempts from multiple IPs. User 9999 does NOT currently exist in users.json. The attempts all returned "2fa_required" suggesting 9999 may have existed briefly. Verify no credential stuffing succeeded.
- Super admin PIN "1111" is the default. Rate limiting added this run mitigates brute force, but PIN should be changed to a strong random value.
- require_2fa_for_admins is false by default. Consider enabling after testing that mandatory 2FA doesn't break admin workflows.

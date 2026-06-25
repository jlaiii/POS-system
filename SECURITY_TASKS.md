# POS Security Tasks
> Last run: 2026-06-25 05:18 UTC

## CRITICAL — LOGIN & AUTH SECURITY (check every run)

### CRITICAL: Super admin login had NO rate limiting — FIXED
- [x] **Add rate limiting to /api/platform/super_admin/login** — The multi-tenant super admin login endpoint accepted unlimited PIN attempts with zero rate limiting. Super admin PIN 1111 could be brute-forced over the network with no lockout. Added IP-based `platform_failed_attempts` tracker with 5 attempts per 60s window, 10-minute lockout. Verified: 6th failed attempt returns 429 with lockout message. Valid PIN also blocked during lockout (correct — IP-based lock prevents sequential guessing).

### CRITICAL: Backup files were world-readable — FIXED
- [x] **Fix backup permissions to 600** — All backup archives had permissions 644, exposing user PINs and all system data. Fixed: `chmod 600` on all existing backup files, `chmod 700` on backup directories. Added `os.chmod(tar_path, 0o600)` and `os.chmod(compressed_file, 0o600)` to the backup script.

### CRITICAL: Logout does not invalidate session tokens — FIXED
- [x] **Invalidate session tokens on logout** — The `/api/logout` endpoint never removed sessions from `active_user_sessions`. Fixed: backend calls `logout_session()`, frontend sends `sessionToken`. Verified.

### CRITICAL: Debug mode enabled in production — FIXED
- [x] **Disable debug mode** — `socketio.run(app, debug=True)` at line 8730 (original). Exposes Werkzeug debugger with remote code execution. Changed to `debug=False, allow_unsafe_werkzeug=False`.

### CRITICAL: Clock in/out endpoints lack credential verification — FIXED
- [x] **Add PIN verification + rate limiting to clock-in/out** — `/api/clock/in` and `/api/clock/out` accepted any valid user_id without verifying PIN. Added `clock_failed_attempts`, IP-based and user-ID-based rate limiting (10 attempts/60s, 15min lock), and generic error messages.

### CRITICAL: GET /api/users leaked ALL user PINs with no auth — FIXED
- [x] **Add auth check to GET /api/users** — `GET /api/users` returned all users including PINs as dict keys with zero authentication. Added `adminPin` query parameter requirement with `manage_users` permission check.

### CRITICAL: 15 unauthenticated GET endpoints exposed sensitive data — FIXED
- [x] **Add auth to analytics, delivery, email, inventory, orders endpoints** — All 15 endpoints now require appropriate permission checks.

### CRITICAL: /api/tables/tab checkout had zero auth — FIXED
- [x] **Add POS access auth to tab checkout endpoint** — Added `check_perm(user_id, "pos_access")` check.

### CRITICAL: /api/orders/lookup GET had no auth — FIXED
- [x] **Add tiered auth to /api/orders/lookup** — Authenticated requests get full data, unauthenticated get kiosk-safe limited fields.

### CRITICAL: Super admin sessions have NO expiration — FIXED this run
- [x] **Add session expiry to platform super admin sessions** — `platform_sessions` stored sessions permanently with no expiry. Added `last_active` field on creation, 8h hard max duration, 4h idle timeout in `require_super_admin()`. Expired sessions auto-cleaned. Verified.

## HIGH — DATA PROTECTION & COMPLIANCE

### HIGH: Default super admin PIN is 1111 — OPEN
- [ ] **Change super admin default PIN** — `data/global/super_admins.json` stores super admin PIN 1111 in plaintext. Same as the default owner PIN. Already in weak-PIN blocklist for regular users. Rate limited and session-expiry mitigated, but PIN should be changed to a strong random value.

### HIGH: PIN stored as plaintext dict key — OPEN
- [ ] **Hash PINs** — User ID IS the PIN, stored as the dict key in users.json in plaintext. Requires architectural change: separate `user_id` (internal) from `pin_hash`. MITIGATED: files saved with 0600 permissions.

### HIGH: No session tokens for all endpoints — PIN sent in every request — OPEN
- [ ] **Require session tokens on all endpoints** — Most endpoints accept raw PIN (`adminPin`) instead of requiring a session token. Sessions exist (8h active, 24h idle timeout) but most endpoints bypass them.

### HIGH: TOTP secrets stored in plaintext in users.json — OPEN
- [ ] **Protect TOTP secrets** — `totp_secret` is stored in plaintext in users.json. MITIGATED: file permissions enforced to 0600. Encrypt TOTP secrets at rest with a server-side key.

### HIGH: require_2fa_for_admins is disabled by default (RESOLVED)
- [x] **Enable mandatory 2FA for admin accounts** — Set `require_2fa_for_admins=true`, added session-restore re-check.

### HIGH: Existing weak PINs in active use — FIXED this run
- [x] **Force PIN change for users with weak PINs** — Owner(1111), Employee One(1234), Manager(2222), Carlos(123456) all had weak PINs. Set `force_pin_change: true` on all four. Verified: Manager login returns `force_pin_change_required: true`.

## MEDIUM — HARDENING

### MEDIUM: Thread-safe file writes — FIXED
- [x] **Add threading lock to save_json_data** — Added `_file_io_lock` (threading.RLock) wrapping all file writes.

### MEDIUM: CORS wide open — FIXED
- [x] **Restrict CORS** — `CORS(app)` changed from wildcard to allowed origins.

### MEDIUM: Error pages may leak stack traces — FIXED
- [x] **Add custom 404/500 JSON error handlers** — Flask's default error handlers return HTML with stack traces. Added JSON error handlers.

### MEDIUM: App runs as root — OPEN
- [ ] **Run as non-root user** — All processes run as root. Any compromised endpoint gives full system access.

### MEDIUM: No app.secret_key configured — FIXED
- [x] **Set Flask secret_key** — Added `app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))`.

### MEDIUM: Kitchen/display endpoints still unauthenticated — OPEN
- [ ] **Add optional API key auth for kitchen/drivethrough/pickup displays** — These endpoints are intentionally public but should have optional shared-secret API key for multi-tenant deployments.

### MEDIUM: save_json_data creates world-readable files — FIXED
- [x] **Permanently enforce 0600 on all saved JSON files** — `save_json_data()` now always enforces 0600.

### MEDIUM: app.static_folder used as root for backup/restore — OPEN
- [ ] **Review backup/restore file path scoping** — Backup and restore endpoints use `app.static_folder` as root directory. Could potentially overwrite non-JSON files in multi-tenant mode.

## LOW — POLISH

### LOW: Password complexity — FIXED
- [x] **Enforce 8+ char, mixed case + number** — Applied on `/api/owner/credentials`.

### LOW: SHA-256 used for password hashing — OPEN
- [ ] **Upgrade password hashing** — `hash_password()` uses SHA-256 with random salt. Not GPU-resistant. Should use bcrypt or argon2.

### LOW: Dependencies are current — no action needed
- [x] **Verify dependency versions** — Flask 3.1.3, pyotp 2.9.0, qrcode 7.4.2, Werkzeug 3.1.8, eventlet 0.41.0. All current stable versions.

## COMPLETED (this session)

### Run: 2026-06-25 05:18 UTC
- [x] **Add session expiry to platform super admin sessions** — CRITICAL: Sessions never expired. Added 8h hard max + 4h idle timeout to `require_super_admin()`. Verified: invalid/expired tokens return 401.
- [x] **Force PIN change for users with weak PINs** — HIGH: Set `force_pin_change: true` on Owner(1111), Employee One(1234), Manager(2222), Carlos(123456). Verified: Manager login returns `force_pin_change_required: true`.
- [x] **Verify all endpoint auth coverage** — Scanned all 80 @app.route endpoints. Confirmed all sensitive endpoints have auth checks. Remaining unauthenticated endpoints are intentionally public (health, items GET, idle timeout GET).
- [x] **Check for XSS vectors in index.html** — Confirmed `escHtml()` is used consistently on all user-supplied data. No XSS vectors found.

### Run: 2026-06-25 01:18 UTC
- [x] **Add rate limiting to super admin login** — CRITICAL: `/api/platform/super_admin/login` had zero protection. Added IP-based 5-attempt/60s window with 10min lockout. Verified with curl.
- [x] **Fix backup file permissions** — CRITICAL: Backup archives were world-readable (644). Fixed to 600.
- [x] **Verify all JSON files at 0600** — All JSON data files have owner-only permissions.
- [x] **Verify dependencies are current** — All current stable versions.

### Run: 2026-06-24 18:00 UTC
- [x] **Invalidate session tokens on logout** — CRITICAL: `/api/logout` now invalidates session tokens. Verified.

### Run: 2026-06-24 16:45 UTC
- [x] **Remove stale owner_pin from security_config.json**
- [x] **Add custom 404/500 JSON error handlers**
- [x] **Strengthen owner password policy**

## WATCHLIST (monitor, don't fix yet)

- SEC-001/SEC-013: 2FA persistence bug — suspected race condition; threading lock added. Monitor next 2-3 runs to confirm fix.
- User 9999 login attempts at ~07:56 UTC on 2026-06-24: 20 rapid attempts from multiple IPs. User 9999 does NOT currently exist in users.json. The attempts all returned "2fa_required" suggesting 9999 may have existed briefly. Verify no credential stuffing succeeded.
- Super admin PIN 1111 is the default. Rate limiting + session expiry mitigate brute force, but PIN should be changed to a strong random value.
- require_2fa_for_admins is now true (set by worker-1). Monitor for admin workflow disruption.

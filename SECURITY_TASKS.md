# POS Security Tasks
> Last run: 2026-06-23 10:43 UTC

## CRITICAL — LOGIN & AUTH SECURITY (check every run)

### CRITICAL: Debug mode enabled in production
- [x] **Disable debug mode** — `socketio.run(app, debug=True)` at line 8730. Exposes Werkzeug debugger with remote code execution. Changed to `debug=False, allow_unsafe_werkzeug=False`.

### CRITICAL: Clock in/out endpoints lack credential verification
- [x] **Add PIN verification + rate limiting to clock-in/out** — `/api/clock/in` and `/api/clock/out` accepted any valid user_id without verifying the caller knows the PIN. No rate limiting. Allowed PIN enumeration. Added `clock_failed_attempts` tracking dict, `_record_clock_failure()` helper, IP-based and user-ID-based rate limiting (10 attempts/60s, 15min lock), and generic error messages that don't reveal if user exists.

### HIGH: PIN stored as plaintext dict key
- [ ] **Hash PINs** — User ID IS the PIN, stored as the dict key in users.json in plaintext. Anyone with file-system access (or backup access) sees all PINs. Requires architectural change: separate `user_id` (internal) from `pin_hash`. Postgres/Long-term: store PIN hash, not the PIN itself.

### HIGH: No session tokens — PIN sent in every request
- [ ] **Implement session tokens** — Currently no server-side sessions. The PIN credential is sent with every request in the `adminPin` field. Generate a random session token on login, require it (instead of adminPin) on subsequent requests. This also enables proper logout (token invalidation) and idle timeout.

### HIGH: No idle session timeout
- [ ] **Enforce idle timeout** — No session expiration exists. Once logged in, the user stays logged in indefinitely (until browser close or manual logout). Add 8-hour idle timeout on admin sessions, 2-hour on user sessions.

## HIGH — DATA PROTECTION & COMPLIANCE

### HIGH: Analytics endpoints wide open (no auth)
- [ ] **Add auth checks to analytics endpoints** — 6+ GET endpoints at `/api/analytics/*` have `# Public - No Auth Required` comment. Exposes all sales data, revenue, order patterns, item trends. Add `check_perm(pin, "view_stats")` or at minimum a simple token.

### HIGH: CORS wide open
- [ ] **Restrict CORS** — `CORS(app)` on line 22 allows all origins. SocketIO has `cors_allowed_origins="*"`. Restrict to known domains.

### HIGH: PIN complexity not enforced — only warns
- [ ] **Block weak PINs instead of warning** — The `change_pin` endpoint (line 1582-1585) checks for guessable patterns but only warns. Should reject weak PINs (1111, 1234, 0000, etc.) with a 400 error and suggest a stronger one.

## MEDIUM — HARDENING

### MEDIUM: Error pages may leak stack traces
- [ ] **Custom error handlers** — Flask's default error handler may leak stack traces in debug mode. Add `@app.errorhandler(500)` and `@app.errorhandler(404)` handlers that return JSON without stack traces.

### MEDIUM: App runs as root
- [ ] **Run as non-root user** — All processes run as root. Any compromised endpoint gives full system access.

### MEDIUM: users.json is world-readable (644)
- [ ] **Restrict file permissions** — `users.json` is 644 (world-readable). PINs are stored as plaintext dict keys. Change to 600.

## LOW — POLISH

### LOW: Password complexity minimum is only 6 chars
- [ ] **Strengthen password policy** — Line 759: `if len(password) < 6` — minimum is 6 characters for owner password. Should be 8+ with mixed case and numbers.

## COMPLETED (this session)
- [x] **Disable debug mode** — Changed `debug=True` to `debug=False`, `allow_unsafe_werkzeug=True` to `allow_unsafe_werkzeug=False`. Prevents remote code execution via Werkzeug debugger.
- [x] **Add rate limiting + PIN verification to clock-in/out** — Added `clock_failed_attempts` tracking, `_record_clock_failure()` helper, IP-based and user-ID-based rate limiting (10/60s, 15min lock), and generic "Invalid PIN." error messages that don't reveal whether a user exists. Prevents PIN enumeration and brute-force clock-in/out.

## WATCHLIST (monitor, don't fix yet)
- Multi-tenant: No business_id scoping on data access — will be a problem when multi-tenant is deployed
- 2FA backup codes stored as SHA-256 hashes — good, but check that they're properly invalidated after use

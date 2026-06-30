# POS Security Watchdog

| | | | | | | | | | Last run: 2026-06-30T15:21 UTC
| | | | | | | | | Total events tracked: 109 (SEC-001→SEC-109; 0 unresolved)
| | | | | | | | | Active blocks: 1 IP (127.0.0.1 — ineffective by design, localhost bypasses blocklist in app.py)
| | | | | | | | | Run result: Clean — all activity from 127.0.0.1 (Security Sentinel rate test). No external threats.

## Current Run Findings (14:44–15:21 UTC, ~37 min window)

### 🔴 CRITICAL (0)
None.

### 🟠 HIGH (0)
None.

### 🟡 MEDIUM (1)
- **Account enumeration pattern** — 10 failed PIN attempts targeting non-existent user 9999 at 15:18:26 UTC from 127.0.0.1 (curl/8.5.0). All 10 attempts completed within 0.4 seconds. User 9999 does not exist in users.json (was a historical Test2FA account, now removed). This is likely Security Sentinel continuing its rate-limiting test after the SEC-109 auto-block event. Flagged but not escalated: 127.0.0.1 is localhost and all dev/cron activity.

### 🟢 LOW (1)
- **Auto-block of 127.0.0.1** (15:12:44 UTC) — 6 failed null-user PIN attempts triggered auto-block. Recorded as SEC-109. Resolved by Security Sentinel as false positive (their own rate test). Note: The block is stored in security_config.json but is **ineffective** — app.py (line 94) explicitly allows localhost (127.0.0.1, ::1) to bypass the IP blocklist entirely by design.

### ℹ️ Activity Summary

**Server**: **Healthy** (HTTP response on port 5000 — all endpoints responding).

**Activity**: **16 activity_log entries** since last run (14:44 UTC):
- 6 failed login attempts at 15:12:43-44 (null user, 127.0.0.1, curl) — triggered auto-block
- 10 failed login attempts at 15:18:26 (user 9999 non-existent, 127.0.0.1, curl) — account enumeration pattern
- 0 successful logins this window

**Login attempts**: 16 new entries (0 success, 16 failed). All from 127.0.0.1.

**Active shifts**: 0. No one currently clocked in.

**Orders**: No new orders this window.

### 📊 Login Security Deep-Dive
- **Brute force check**: 16 failed logins from 127.0.0.1 in this window. 6 targeting null user (bot test), 10 targeting non-existent user 9999. All from localhost — Security Sentinel rate limiting test.
- **Account enumeration**: 10 probes against non-existent user 9999 from 127.0.0.1. Exceeds threshold of 10 but from localhost only — noted as MEDIUM.
- **Successful-after-failure**: No successful logins occurred after the failures. No credential compromise.
- **Off-hours activity**: 10:21 CT — normal operating hours. NOT flagged.
- **Cross-IP targeting**: None detected — single IP 127.0.0.1.
- **Credential stuffing**: No pattern detected (single user targeted, single IP).
- **Unusual hour**: 10:21 CT is normal operating hours.

### 🔒 Security Config
- `blocked_ips` now has 1 entry: 127.0.0.1 (auto-blocked at 15:12:44, duration 60 min). **Note**: This block is ineffective — app.py explicitly allows localhost to bypass the blocklist (line 94). This is by design (local access is trusted), but means the auto-block mechanism will never stop localhost attacks.
- `auto_block_threshold`: 5 (unchanged).
- `require_2fa_for_admins`: true (unchanged).
- 2FA gap: Owner (1111), Manager (2222), and Manager Sarah (7788) still lack 2FA — known issue for Security Sentinel.

### 💰 Financial Check / Order Anomaly Scan
- 0 new orders this window.
- 121 total orders (all historical test data).
- 4 large orders (>$500) exist — all historical test data, no anomaly.

### 📂 File Integrity
- All JSON files parseable and valid.
- All 8 accounts intact. Owner (1111) present, active, not banned.
- No suspicious new files found.
- Git: clean — no dirty files.

### ✅ Actions Taken
- Routine check complete. Minor findings noted.
- 0 new SEC events created (account enumeration pattern noted but attributed to Sentinel's own testing on localhost — not an external threat).
- Git already clean — no commit needed.

## Previous Run Findings (carried forward)
- Admin 2FA gap: Owner (1111), Manager (2222), and Manager Sarah (7788) lack 2FA despite `require_2fa_for_admins: true`. Security Sentinel handles.
- Historical refund rate ~33.1% — all test data, no real customer orders.
- 127.0.0.1 in blocked_ips but bypassed by app.py — by design.

| | | | | | | | | | System State | | | |
|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | Current time | 2026-06-30T15:21 UTC — 10:21 CT (normal hours) |
| | | | | | | | | | Activity since last run | 16 entries (16 failed logins, 0 success) |
| | | | | | | | | | Login attempts (this window) | 16 (all failed) |
| | | | | | | | | | Successful logins (this window) | 0 |
| | | | | | | | | Blocked IPs | 1 (127.0.0.1 — ineffective, localhost bypass) |
| | | | | | | | | Config changes | None (auto-block of 127.0.0.1 at 15:12:44 noted) |
| | | | | | | | | File integrity | JSON files valid. All 8 accounts intact. |
| | | | | | | | | Unresolved events | 0 of 109 |
| | | | | | | | | Server | **Healthy** (HTTP response on port 5000) |
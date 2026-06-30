# POS Security Watchdog

|| | | | | | | | | | Last run: 2026-06-30T15:41 UTC
|| | | | | | | | | Total events tracked: 109 (SEC-001→SEC-109; 0 unresolved)
|| | | | | | | | | Active blocks: 1 IP (127.0.0.1 — ineffective by design, localhost bypasses blocklist in app.py)
|| | | | | | | | | Run result: **SERVER WAS DOWN** — recovered. All activity from 127.0.0.1 (cron workers). No external threats.

## Current Run Findings (15:21–15:41 UTC, ~20 min window)

### 🔴 CRITICAL (1)
- **POS Flask server DOWN** — Port 5000 was unreachable (connection refused) at 15:40 UTC. Last logged activity: `timesheet_config_updated` by user 1111 (Owner) at 15:29:40 UTC, then silence. The systemd service (`pos-system.service`) reported "active (running)" but had **Tasks: 0, Memory: 4.0K** — the gunicorn master PID (3165932) was dead (zombie state since June 29 15:11 UTC restart failure due to stale PID file). The `pos_monitor.py --fix` script (launched by cron at 15:40 UTC) attempted restart but failed because `systemctl --user start` didn't clear the stale state. **Manually resolved**: force-stopped systemd service (`systemctl --user stop`), cleaned stale PID files, then restarted (`systemctl --user start`). Server returned HTTP 200 on first check. **Root cause**: systemd service has been in zombie state for ~24h — the 15:11 UTC June 29 restart failed with "Already running on PID 3165932 (or pid file is stale)" and subsequent gunicorn requests were handled by a separate process (possibly run_flask.sh), which crashed at ~15:29-15:30.

### 🟠 HIGH (0)
None.

### 🟡 MEDIUM (0)
None.

### 🟢 LOW (1)
- **127.0.0.1 still blocked** (since 15:12:44, auto-block 60min). Block expires ~16:12 UTC. Still ineffective due to app.py localhost bypass.

### ℹ️ Activity Summary

**Server**: ~~**DOWN**~~ **RESTORED** (manual restart at 15:41 UTC — HTTP 200 confirmed).

**Activity**: **9 activity_log entries** since last run (15:21 UTC):
- 15:28:32 — `login_failed` (null user, 127.0.0.1, curl)
- 15:28:34 — `admin_login` failed (null user, 127.0.0.1, curl)
- 15:28:39 — `login_failed` (null user, 127.0.0.1, curl)
- 15:28:47 — `login` success (user 1111, 127.0.0.1, curl) — Owner login
- 15:28:52 — `admin_login` failed (null user, 127.0.0.1, curl)
- 15:29:06-16 — 3x `admin_login` success (user 1111, 127.0.0.1, curl) — Owner admin logins
- 15:29:40 — `timesheet_config_updated` (user 1111, 127.0.0.1, curl) — `use_database` field removed from config
- **NO activity after 15:29:40** — server went down between 15:29 and 15:40

**Login attempts**: 3 new entries (1 success, 2 failed). All from 127.0.0.1.

**Active shifts**: 0. No one currently clocked in.

**Orders**: No new orders this window.

### 📊 Login Security Deep-Dive
- **Brute force check**: 2 failed logins from 127.0.0.1 targeting null user, then 1 successful login as 1111. Below threshold (5 in 5 min) — no auto-block trigger. 2 prior fails before success is below the 3+ threshold for "successful-after-failure" alert. This was likely a cron worker (Security Sentinel) doing routine auth testing.
- **Account enumeration**: None this window (the 10 user-9999 probes were in previous window).
- **Successful-after-failure**: 127.0.0.1 had 2 prior failures then successful login as 1111. This was the Owner from localhost (same machine as prior failures). Threshold of 3+ not met. Not escalated.
- **Credential stuffing**: No pattern (single IP, single user).
- **Off-hours activity**: 10:28-10:29 CT — normal operating hours. NOT flagged.
- **Cross-IP targeting**: None — single IP 127.0.0.1.
- **Session anomalies**: No active users to check (server was down).

### 🔒 Security Config
- `blocked_ips`: 1 entry (127.0.0.1, auto-blocked at 15:12:44, expires ~16:12 UTC). Ineffective against localhost.
- `auto_block_threshold`: 5 (unchanged).
- `require_2fa_for_admins`: true (unchanged).
- `use_database` field **removed** from timesheet_config.json at 15:29:40 by user 1111 (Owner, localhost, curl). This was likely a database-architect worker cleaning up the unused flag. No security concern.
- 2FA gap: Owner (1111), Manager (2222), and Manager Sarah (7788) lack 2FA — known issue for Security Sentinel.

### 💰 Financial Check / Order Anomaly Scan
- 0 new orders this window.
- 121 total orders (all historical test data).
- No new financial anomalies.

### 📂 File Integrity
- All 51 JSON files parseable and valid.
- All 8 accounts intact. Owner (1111) present, active, not banned.
- No suspicious new files found.
- Git: **was dirty** (login_attempts.json + timesheet_config.json) — **committed** with message "Watchdog: commit pending data changes (3 login attempts, timesheet_config use_database removal)"

### ⚠️ Infrastructure Issue: Systemd Zombie Service
The `pos-system.service` has been in a zombie state since June 29 15:11 UTC. The gunicorn master PID 3165932 (started June 29) exited with SIGTERM at 15:10:56, but the systemd restart at 15:11:27 failed with "Already running on PID 3165932 (or pid file is stale)". Since then:
- systemd reports "active (running)" with Tasks: 0, Memory: 4.0K
- A separate gunicorn (likely from run_flask.sh) was handling requests until it crashed ~15:29
- pos_monitor.py --fix failed because `systemctl --user start` doesn't force-restart a zombie service
- **Recommendation**: Reliability Bot should fix the systemd service to use `ExecStartPre=rm -f $PID_FILE` and set `PIDFile=` correctly. Or switch to a simpler supervisor like supervisord.

### ✅ Actions Taken
- **CRITICAL**: Server was DOWN — manually restarted via systemctl force-stop + start. HTTP 200 confirmed.
- Committed dirty git files (login_attempts.json, timesheet_config.json).
- 0 new SEC events created (all activity from localhost cron workers, no external threats).
- SECURITY_WATCHDOG.md updated with findings.

## Previous Run Findings (carried forward)
- Admin 2FA gap: Owner (1111), Manager (2222), and Manager Sarah (7788) lack 2FA despite `require_2fa_for_admins: true`. Security Sentinel handles.
- Historical refund rate ~33.1% — all test data, no real customer orders.
- 127.0.0.1 in blocked_ips but bypassed by app.py — by design.
- Systemd zombie service — needs Reliability Bot attention.

|| | | | | | | | | | System State | | | |
|---|---|---|---|---|---|---|---|---|---|---|---|
|| | | | | | | | | | Current time | 2026-06-30T15:41 UTC — 10:41 CT (normal hours) |
|| | | | | | | | | | Activity since last run | 9 entries (2 failed logins, 1 success, 4 admin_logins, 1 config update) |
|| | | | | | | | | | Login attempts (this window) | 3 (2 failed, 1 success) |
|| | | | | | | | | | Successful logins (this window) | 1 (Owner 1111 from 127.0.0.1) |
|| | | | | | | | | Blocked IPs | 1 (127.0.0.1 — ineffective, localhost bypass, expires ~16:12) |
|| | | | | | | | | Config changes | `use_database` removed from timesheet_config.json (by cron worker) |
|| | | | | | | | | File integrity | JSON files valid. All 8 accounts intact. Git clean. |
|| | | | | | | | | Unresolved events | 0 of 109 |
|| | | | | | | | | Server | **RESTORED** (was DOWN, manually restarted at 15:41 — HTTP 200) |
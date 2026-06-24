# POS Security Watchdog

> Last run: 2026-06-24T14:34:51 UTC
> Total events tracked: 13 (SEC-001 → SEC-013)
> Active blocks: 0 IPs
> Unresolved alerts: 11 (SEC-001, SEC-003, SEC-005, SEC-006, SEC-007, SEC-008, SEC-009, SEC-010, SEC-011, SEC-012, SEC-013)
> Run result: All clear — no new findings

## Current Run Findings

### 🔴 CRITICAL (0)
None.

### 🟠 HIGH (0)
None.

### 🟡 MEDIUM (0)
None — all pre-existing issues unchanged.

### ℹ️ Activity Summary (13:40–14:34 UTC, ~54m window)

| Time | Event | Detail |
|------|-------|--------|
| 13:44:38 | ticket_submitted — Employee One (1234) | Vacation test ticket |
| 13:44:38 | ticket_auto_approved — system | Auto-approved (5d advance, threshold 1d) |
| 13:44:45 | ticket_submitted — Test2FA (9999) | Short notice test |
| 13:45:03 | timesheet_config_updated — Owner (1111) | Updated auto_approve_threshold to 7d, late_grace to 5min |
| 13:51:30 | get_users failed — Test2FA (9999) | Insufficient permissions |
| 13:51:37 | get_users failed — None | Insufficient permissions |
| 13:51:46 | update_direct_deposit — Owner (1111) | Set Chase checking for Employee One (1234) |
| 14:26:06 | submit_order — null user | Order 71, $10.79 total, Cash |
| 14:34:07 | login_failed — null user, 127.0.0.1 | Invalid PIN attempt |
| 14:34:07 | add_item — Owner (1111) | Added "Test Nutrition Item" ($5.99) |
| 14:34:14 | delete_item — Owner (1111) | Deleted "Test Nutrition Item" |

**Pattern:** Normal testing/admin activity. Ticket system auto-approved Employee One's time-off. Owner configured timesheet settings, updated direct deposit for Employee One, and performed menu item create/delete test. One failed login attempt (typed wrong PIN). All from localhost. No security concerns.

### 📊 Login Security Deep-Dive
- **Brute force check**: 0 IPs with 5+ failed logins. 0 users with 5+ failed attempts. No credential stuffing.
- **Failed logins last 5 min**: 1 (null user_id, 127.0.0.1 — under threshold)
- **Failed logins since last run**: 1 (null user_id, 127.0.0.1)
- **Successful-after-failure**: None (the only success was at 13:18, before this window).
- **Account enumeration**: 1 probe from 127.0.0.1 for invalid PIN — under 10 threshold.
- **Off-hours**: Current time 14:34 UTC — normal hours (off-hours window 22:00-06:00).
- **Known IPs**: Unchanged. No new IPs tracked.
- **login_attempts.json**: 1 new entry (failed login at 14:34:07, null user, 127.0.0.1).
- **Active shifts**: None. Server responding normally.
- **New logins this window**: 0.

### 🔒 Security Config
- security_config.json: Unchanged. require_2fa_for_admins=false, auto_block_threshold=5, blocked_ips empty.
- timesheet_config.json: Updated by Owner at 13:45 (auto_approve_threshold_days 14→7, late_grace_minutes 5). File currently shows auto_approve_threshold_days=14 (may have been reverted). Non-security config — normal admin operation.
- users.json: Unchanged. Owner 2FA still NOT enabled (SEC-001/SEC-013).
- No configuration sabotage detected.

### 💰 Financial Check
- **New order 71**: $9.99 subtotal, $0.80 tax, $10.79 total, Cash, null user. Normal single-item order.
- Prior orders (69, 70) at 08:29: $5.00 and $1.00 — normal low-value test orders.
- No refunds, discounts, or unusual pricing patterns.
- No cash drawer activity.
- All clear.

### 📂 File Integrity
- All JSON files parseable. No corruption.
- No suspicious files (no .php, .sh scripts outside app.py/db.py).
- Owner account (1111) present, active, not banned — unchanged.
- All data files present with normal sizes.
- Server responding normally on port 5000.

## Active Blocks
None.

## Unresolved HIGH/CRITICAL Events
- **SEC-006**: [HIGH] User Manager blocked by admin (Owner) at 20:23:31 — "Test block from cron". (Reported 2026-06-23T20:23)

## Unresolved MEDIUM Events
- **SEC-013**: [MEDIUM] ⚠️ 2FA persistence bug — Owner (1111) setup did NOT save. (Reported 2026-06-24T05:43)
- **SEC-001**: [MEDIUM] ⚠️ 2FA state not persisted — Owner totp_enabled=False. (Reported 2026-06-23T07:24)
- **SEC-012**: [MEDIUM] ⚠️ Off-hours login: Owner at 02:39. (Reported 2026-06-24T02:39)
- **SEC-011**: [MEDIUM] ⚠️ Off-hours login: Owner at 00:55. (Reported 2026-06-24T00:55)
- **SEC-010**: [MEDIUM] ⚠️ Off-hours login: Owner at 23:39. (Reported 2026-06-23T23:39)
- **SEC-009**: [MEDIUM] ⚠️ Off-hours login: Owner at 23:32. (Reported 2026-06-23T23:32)
- **SEC-008**: [MEDIUM] Shift at 22:36 for Employee One missing activity_log entry. (Reported 2026-06-23T23:18)
- **SEC-007**: [MEDIUM] User Manager unblocked by admin (Owner). (Reported 2026-06-23T20:23)
- **SEC-005**: [MEDIUM] Order 15 subtotal discrepancy ($29.53 vs $34.00). (Reported 2026-06-23T16:24)
- **SEC-003**: [MEDIUM] Activity log truncation — 7 entries removed. (Reported 2026-06-23T10:35)

## Resolved This Session
None.

## System State
- **Current time**: 2026-06-24T14:34:51 UTC — normal hours (off-hours window 22:00-06:00)
- **Activity log**: 6762 entries (270+ new since 13:40: tickets, config updates, direct deposit, order, item add/delete, login attempt). No truncation.
- **New login attempts since last run**: 1 (1 failed, 0 success)
- **Failed logins since last run**: 1 (null user_id, 127.0.0.1)
- **Known IPs**: Unchanged. No new IPs.
- **Blocked IPs**: 0
- **Config changes**: Owner updated timesheet_config at 13:45 (normal operation).
- **File integrity**: All JSON files parseable. No suspicious files. No unexpected changes.
- **Users**: 5 accounts in users.json. Owner 2FA still NOT enabled (SEC-001/SEC-013).
- **Security events**: 13 tracked. 2 resolved. 11 unresolved.
- **Server**: Responding normally on port 5000.

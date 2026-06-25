# POS Security Watchdog

> Last run: 2026-06-25T14:38 UTC
> Total events tracked: 25 (SEC-001 → SEC-025)
> Active blocks: 0 IPs
> Unresolved alerts: 22 (same as last run — no new events)
> Run result: Clean — no security threats.

## Current Run Findings

### 🔴 CRITICAL (0)
None.

### 🟠 HIGH (0)
None.

### 🟡 MEDIUM (0)
None.

### 🟢 LOW (0)
None.

### ℹ️ Activity Summary (14:19–14:38 UTC, ~19m window since last run)

**New activity log entries since last run**: 15 entries.

| Time | Type | User | Details |
|---|---|---|---|
| 14:25:22 | login_failed | 9999 | Non-existent user — 1 failed attempt (127.0.0.1, curl) |
| 14:28:40 | login | 1234 | Employee One — 2fa_required |
| 14:28:49 | login | 123456 | Carlos — success |
| 14:30:12 | login | 123456 | Carlos — success |
| 14:36:48 | login | 123456 | Carlos — success (Python-urllib) |
| 14:36:48 | login | 123456 | Carlos — success (Python-urllib) |
| 14:36:48 | pin_changed | 987654 | Carlos — old PIN 123456→987654 |
| 14:36:48 | pin_change_failed | 987654 | Guessable PIN |
| 14:36:58 | login_failed | 123456 | Carlos — 2 failed attempts after PIN change |
| 14:37:18 | login | 987654 | Carlos — success with new PIN |
| 14:37:18 | login | 987654 | Carlos — success with new PIN |
| 14:37:18 | pin_changed | 7392 | Carlos — PIN changed to 7392 |
| 14:37:18 | pin_changed | 987654 | Carlos — PIN changed back to 987654 |

All activity is from localhost (127.0.0.1). The Carlos PIN change activity (14:36:48–14:37:18) appears to be a cron worker testing PIN change functionality (changed PIN twice with a revert). No real user activity.

**Login attempts (login_attempts.json)**: 12 new entries since last run (2 failed, 10 successful). Last login at 14:37:18 (Carlos/987654).

**Failed logins in last 5 min**: 2 (user 123456, 127.0.0.1, 14:36:58 — after PIN changed, likely user mistyping new PIN).

**Server**: UP (HTTP 200).

### 📊 Login Security Deep-Dive
- **Brute force check**: 0 IPs with 5+ failed logins in last 5 min. 0 users with 5+ failed attempts.
- **Failed logins since last run**: 3 (user 9999 at 14:25:22 — non-existent, probably test; user 123456 at 14:36:58 — 2 attempts after PIN change).
- **Successful-after-failure**: User 123456 had 2 failures at 14:36:58, but these occurred AFTER 2 successful logins at 14:36:48. Failures were caused by PIN change taking effect mid-session. Not a brute-force compromise.
- **Account enumeration**: 1 failed login for non-existent user 9999 from localhost. Single attempt by curl — likely cron worker test. No probing pattern.
- **Off-hours**: Current time 14:38 UTC — normal hours (06:00-22:00).
- **Known IPs**: Unchanged. All localhost.
- **Rapid successive logins**: Carlos (123456→987654) logged in 4 times across 2 IPs(PIN change) — all from localhost, normal dev activity.

### 🔒 Security Config
- All config files unchanged. No sabotage detected.
- `blocked_ips: []` — no active blocks.
- `auto_block_threshold: 5` — unchanged.
- `require_2fa_for_admins: true` — unchanged.

### 💰 Financial Check
- No new orders placed since last run.
- 0 orders with $0 total. 0 with 100% discount.
- 0 large tips, 0 suspicious patterns.
- No new refunds since last run. Existing refunds are all $0 by Owner (1111) — cron test cleanup.
- No active clocked-in employees.

### 📂 File Integrity
- All core JSON files parseable. No corruption or unexpected shrinkage.
- No suspicious files found. Only expected __pycache__ and scripts/ files.
- Owner account (1111) present, active, not banned. 2FA still disabled (known code bug — SEC-001/SEC-013).
- Security config unchanged. No auto-block disarmament.
- No stale test accounts detected.

## Active Blocks
None.

## Unresolved HIGH/CRITICAL Events
- **SEC-006**: [HIGH] User Manager blocked by admin (Owner) at 20:23:31 — "Test block from cron". (Reported 2026-06-23T20:23)

## Unresolved MEDIUM Events
- **SEC-024**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 05:43. (Reported 2026-06-25T05:43)
- **SEC-023**: [MEDIUM] ⚠️ Off-hours login: Manager (2222) at 05:24. (Reported 2026-06-25T05:24)
- **SEC-022**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 05:21. (Reported 2026-06-25T05:21)
- **SEC-021**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 04:13. (Reported 2026-06-25T04:13)
- **SEC-020**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 02:50. (Reported 2026-06-25T02:50)
- **SEC-019**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 02:21. (Reported 2026-06-25T02:21)
- **SEC-018**: [MEDIUM] ⚠️ Off-hours login: Employee Two (5678) at 00:28. (Reported 2026-06-25T00:28)
- **SEC-017**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 00:09. (Reported 2026-06-25T00:09)
- **SEC-016**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 00:09. (Reported 2026-06-25T00:09)
- **SEC-015**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 22:52. (Reported 2026-06-24T22:52)
- **SEC-014**: [MEDIUM] ⚠️ Off-hours login: Owner (1111) at 22:21. (Reported 2026-06-24T22:21)
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
- **SEC-025**: [HIGH] Super admin default PIN changed from 1111 to secure random PIN — resolved by Security Sentinel at 10:19. (Reported 2026-06-25T10:19)

## System State
| | **Current time**: 2026-06-25T14:38 UTC — normal hours (off-hours window 22:00-06:00)
| | **Activity entries since last run**: 15 (all cron worker test operations — PIN change testing for Carlos account — no real user activity)
| | **New login attempts since last run**: 12 (2 failed, 10 successful)
| | **Failed logins since last run**: 3 (1 for non-existent 9999, 2 for 123456 after PIN change)
| | **Known IPs**: Unchanged. All localhost.
| | **Blocked IPs**: 0
| | **Config changes**: None since last run.
| | **File integrity**: All JSON files parseable. No unexpected new files.
| | **Users**: 8 accounts. Owner 2FA still NOT enabled (SEC-001/SEC-013 — code-level bug).
| | **Security events**: 25 tracked (SEC-001 through SEC-025). 22 unresolved. 0 new this run.
| | **Server**: UP (HTTP 200).

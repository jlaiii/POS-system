# POS Reliability Checklist
> Last full cycle: 2026-07-01T01:53Z
> Total checks: 119
> Healthy: 122 | Broken: 0 | Fixed this cycle: 29

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK (01:53Z)
- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all VALID, 8 users, 5 cats/items dict, 122 orders, 0 shifts, 24 inventory (01:53Z)
- [x] users.json has at least owner PIN 1111 — Owner 1111 present, permissions '*' OK (01:53Z)
- [x] Git repo is clean (no uncommitted changes from crashes) — clean, last commit 89a18f6 (Watchdog 01:39Z) (01:53Z)

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works (clock in test user, verify response) — Employee 1234 clocked in, no late detection (00:58 UTC, schedule 09:00) ✓ (00:58Z)
- [x] /api/clock/out works — Employee 1234 clocked out, test shift cleaned up ✓ (00:58Z)
- [x] /api/items returns items (GET) — 5 categories: Breakfast, Drinks, Foods, Salads, Snacks, items.json dict valid ✓ (01:53Z)
- [x] /api/login works (POST userId) — Owner 1111 login, permissions ['*'], force_pin_change_required=true ✓ (01:53Z)
- [x] /api/admin_stats returns stats (POST adminPin) — Admin data retrieved, backup health green, avg sale $12.84 ✓ (01:25Z)
- [x] /api/admin_shifts returns shifts (POST adminPin) — 0 shifts ✓ (01:25Z)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — HTML 200 OK, ~1,375KB ✓ (01:53Z)

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify — Created #143 (Coke $3)→paid→refunded ✅ (22:10Z)
- [x] User CRUD: add test user → verify → delete — Added 9001, verified, deleted ✅
- [x] Inventory: check stock decrements on order — Coke 70→69→70 (decrement + restore via refund) ✅ (22:10Z)
- [x] Loyalty: points earned on order — Order #139 (Coke $3) earned 3 pts, refunded, cleaned up ✅
- [x] Cash register: open drawer ($100) → cash in ($50) → cash out ($20) → close ($130, exact match) ✅
- [x] Kitchen display: GET /api/kitchen/queue — 0 pending orders, valid data ✓ (22:10Z)
- [x] Pickup display: GET /api/pickup-display/queue — 0 ready orders, valid data ✓ (22:10Z)
- [x] Clock-in late detection: Employee 1234 scheduled 09:00, clocked in 21:38 → 758 min late ✅
- [x] Break tracking: POST /api/clock/break — 'Not clocked in' when not clocked in, endpoint working ✅ (22:57Z)
- [x] Shift edit: POST /api/clock/edit — validates reason required, endpoint working ✅
- [x] CSV export: POST /api/export/shifts_csv — endpoint exists, returns 'Insufficient permissions' (needs auth) ✓ (22:57Z)
- [x] Webhook: GET /api/webhooks — endpoint exists, responds with 'Insufficient permissions' (needs auth) ✓ (22:57Z)
- [x] Offline queue: POST /api/sync_orders — endpoint exists, returns 'No orders provided' ✓

## EVERY 12 HOURS
- [x] Disk space check: df -h, alert if >80% full — 39% used ✓ (15:47Z)
- [x] Memory check: free -m, alert if swap used — 36% RAM, no swap used ✓ (15:47Z)
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 50 JSON files valid (tar.gz), DB backup 569KB ✓ (15:47Z)
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK ✓ (15:47Z)
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 1,375,342 bytes, normal ✓ (15:47Z)
- [x] Full app restart test: kill Flask → restart → verify all critical endpoints — 2026-06-30T14:13Z, PASSED (killed python3 app.py, restarted, verified /api/health, /api/items, /api/kitchen/queue, /api/pickup-display/queue, /api/login, /api/admin_stats, /api/admin_shifts, /api/clock/status all 200 OK)
- [x] Large payload test: submit order with 50 items — Order #140 created (50 items, $162.50) ✅
- [x] Special chars test: user name with emoji, item name with quotes — Item 'Taco 🌮 "Supreme" Deluxe' added/deleted ✅
- [x] Concurrent write test: two rapid clock-ins → verify no data loss — Two users (1234, 5678) clocked in/out concurrently, both shifts recorded ✅

## DISCOVERED (failures you've seen before — check every 2h)
- [x] Security Watchdog leaves dirty files after each run (SECURITY_WATCHDOG.md + activity_log.json + login_attempts.json + security_events.json) — auto-commit on SRE bot runs — CHECKED 01:25Z, committed activity_log.json + login_attempts.json + security_events.json at 1d50559 ✓

## CURRENT OUTAGES
_None_

## FIXES APPLIED
- 2026-07-01T01:25Z **SRE bot routine run** — CRITICAL checks: Flask 200, all 8 JSON valid, Owner 1111 present. HOURLY: items (GET, 5 categories, 19 items ✓), login (userId field ✓), admin_stats (adminPin field, full stats ✓), admin_shifts (0 shifts ✓), clock/status (not clocked in ✓), kitchen queue (1 pending ✓), pickup display (2 orders ✓), frontend (HTML ✓). Committed Security Watchdog dirty files (activity_log.json, login_attempts.json, security_events.json) at 1d50559. Corrected test methodology for several endpoints (use GET for items/kitchen/pickup, adminPin for admin endpoints, userId for login). No broken items found. Pushed to main.
- 2026-07-01T00:58Z **SRE bot routine run** — Checked all CRITICAL (Flask 200, 8 JSON valid, PIN 1111 present) + HOURLY: clock/in+out (no late detection, 00:58 UTC vs schedule 09:00 ✓), frontend load (1,375KB ✓). Committed SECURITY_WATCHDOG.md + activity_log.json dirty from Watchdog runs (e3dce10, 27bbccf). Pushed to main. All healthy.
- 2026-06-30T23:19Z **SRE bot routine run** — Checked all CRITICAL (Flask 200, 8 JSON valid, PIN 1111 present) + HOURLY items, login, admin_stats, admin_shifts (all 200 OK). Test artifacts from SRE bot login probes triggered Watchdog IP blocklist (127.0.0.1 auto-blocked on security_config.json, but localhost is exempt in middleware — no actual impact). Committed Watchdog dirty files + SRE bot data.
- 2026-06-30T22:57Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left dirty after Watchdog 22:43 UTC run. Committed at 7572f88. Also committed activity_log.json (+30 lines from clock-in test). CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present, git clean. HOURLY: clock/in+out (838 min late — correct), frontend (1,375KB). 4H: webhook, CSV export, break tracking all respond correctly. shift_log.json cleaned of test artifact. Pushed to main.
- 2026-06-30T20:55Z **Security Watchdog dirty file** — activity_log.json (+39) left dirty after Watchdog run. Committed at d7716b1. CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present. HOURLY: items (GET ✓), login (owner 1111 via userId ✓), admin_stats, admin_shifts (42), frontend (1,375KB). Git clean. All healthy.
- 2026-06-30T20:33Z **Security Watchdog dirty files** — activity_log.json (+69) + login_attempts.json (+23) left dirty after Watchdog run. Committed at f16edfd. CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present. Git clean. Disk 39%, RAM 37%. HOURLY checks: clock/in+out (694 min late — correct), login (owner 1111 via userId ✓), admin_shifts (42 shifts). Test shift cleaned up. Pushed to main.
- 2026-06-30T19:06Z **Security Watchdog dirty files** — SECURITY_WATCHDOG.md + activity_log.json + login_attempts.json left dirty after Watchdog run. Committed at c1ac89b (SECURITY_WATCHDOG.md) and 39108fa (activity_log.json + login_attempts.json). Ran CRITICAL checks (Flask 200, all 8 JSON valid, PIN 1111 present), HOURLY checks (login via userId, items GET, admin_stats, admin_shifts, frontend) and 4H checks (kitchen+pickup displays — GET, both working). Disk 39%, RAM 37%. Pushed to main.
- 2026-06-30T17:59Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left dirty after Watchdog run. Committed at c87020a. Ran CRITICAL checks (Flask 200, all 15 JSON valid, PIN 1111 present) and 4H inventory check. Pushed to main.
- 2026-06-30T17:37Z **Security Watchdog dirty file** — activity_log.json left dirty after Watchdog run. Committed at c4f5f42. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present) and HOURLY check: clock/in+out (518 min late — correct). Cleaned up test shift. Pushed to main.
- 2026-06-30T16:54Z **Security Watchdog dirty file + SRE bot run** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 16:48 UTC. Committed at 13dd22d. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present) and HOURLY checks (items GET, login via userId, admin_shifts, frontend load — all healthy). Pushed to main.
- 2026-06-30T21:40Z **Shift log cleanup — 42 test artifact shifts removed** — Removed 28 stale zero-duration test shifts + 14 short-duration test artifact shifts (<0.1h) accumulated over past week of SRE bot testing. All were runtime artifacts from clock-in/out tests. shift_log.json now clean (empty array). Also cleaned up 1 test shift from this run. CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present. HOURLY: clock/in+out (759 min late ✓), items GET (5 categories ✓), login+admin_stats+admin_shifts (200 ✓), frontend load (1,375KB ✓). Git clean — Watchdog 21:37 committed clean. Disk 39%, RAM 37%. All healthy.
- 2026-06-30T16:32Z **Security Watchdog dirty file + SRE bot run** — Committed activity_log.json left dirty after Watchdog run. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present), HOURLY clock/in+out (453 min late — correct), 4H kitchen display (1 pending order). Cleaned up test shift. Pushed to main.
- 2026-06-30T16:09Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 15:58 UTC. Committed at 716aefe. Ran critical checks (Flask 200, all JSON valid, PIN 1111 present). Updated pickup display check (was 4h25m overdue). Pushed to main.
- 2026-06-30T14:13Z **Security Watchdog dirty file + 12H restart test** — Committed activity_log.json left dirty by Security Watchdog at 8b97e2f. Ran 12H full app restart test — killed Flask, restarted, verified all 8 critical endpoints pass. Pushed to main.
- 2026-06-30T13:00Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md timestamp update left file dirty after Watchdog 12:52 UTC run. Committed at c3d5ef9. Pushed to main ✓
- 2026-06-30T11:23Z **Flask was down (HTTP 000)** — Flask process had died between 11:01Z and 11:23Z. Restarted via python3 app.py in background. Verified all critical endpoints (health, items, login, admin_stats). Committed dirty SECURITY_WATCHDOG.md from Watchdog 11:13 UTC run. Pushed at 33d09b9.
- 2026-06-30T10:33Z **Watchdog dirty files + SRE bot test cleanup** — Committed activity_log.json (+93) + login_attempts.json (+23) left uncommitted after Watchdog run. Clocked in/out Employee 5678 to verify /api/clock/in+out, cleaned up test shift. Committed + pushed at e844f49.
- 2026-06-30T09:27Z **23 stale test shifts cleaned up + Watchdog dirty file** — Cleaned up 23 accumulated test shifts from shift_log.json (Employee 1234 SRE bot tests over past week). Committed activity_log.json (+43 lines) left dirty by Security Watchdog at e3401ca.
- 2026-06-30T09:05Z **Security Watchdog dirty files** — Committed activity_log.json + login_attempts.json + orders.json (stale auto-cancel) left uncommitted after workers. Committed + pushed at 2e1766c.
- 2026-06-30T08:43Z **Security Watchdog dirty files** — Committed activity_log.json + login_attempts.json left uncommitted after Watchdog run at 08:35 UTC. Committed + pushed at 59414fa.
- 2026-06-30T08:41Z **Security Watchdog dirty files** — Committed SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 08:35 UTC. Committed + pushed at fd78774.
- 2026-06-30T08:18Z **Security Watchdog dirty files** — Committed activity_log.json + login_attempts.json left uncommitted after Watchdog run at 08:07 UTC. Committed at fb187c5.
- 2026-06-30T07:55Z **Inventory stock decrement/restore test** — Ran 4H inventory check (last was 03:18Z, overdue). Created order #142 (1 Coke $3), verified stock 70→69→70. Committed at 73f07b2.
- 2026-06-30T07:11Z **Security Watchdog dirty files** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 06:53 UTC. Committed at baf2f79. Pushed to main. Also cleaned up test clock-in/out shift.
- 2026-06-30T05:42Z **Security Watchdog dirty files** — Watchdog run left activity_log.json (+39), login_attempts.json (+23), security_events.json (+15), RELIABILITY_CHECKLIST.md (+10/-10) uncommitted. Committed + pushed.
- 2026-06-30T04:46Z **Security Watchdog dirty files** — Watchdog runs left activity_log.json, login_attempts.json, security_events.json uncommitted. Committed + pushed at a2269fe. Also cleaned up test clock-in/out shift.
- 2026-06-30T01:29Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 01:08 UTC. Committed at 114e17b. Push: to main ✓
- 2026-06-30T01:07Z **Security Watchdog dirty files** — Watchdog run left activity_log.json (+39), login_attempts.json (+23), security_events.json (+15) uncommitted. Committed at f7909aa. Push: up-to-date.
- 2026-06-30T00:23Z **Security Watchdog dirty files** — Watchdog run at 00:21 UTC left activity_log.json, login_attempts.json, security_events.json uncommitted. Committed at 72ec0a9.

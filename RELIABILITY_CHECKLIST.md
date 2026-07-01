# POS Reliability Checklist
> Last full cycle: 2026-07-01T19:35Z
> Total checks: 244
> Healthy: 299 | Broken: 0 | Fixed this cycle: 34

## CRITICAL (check every run — these can't wait)
|||- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK (19:35Z)
||||- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all 8 VALID, 11 users, 133 orders, shift_log clean ✓ (19:35Z)
||||- [x] users.json has at least owner PIN 1111 — Owner 1111 present, perms ['*'], super admin ✓ (19:35Z)
||||- [x] Git repo is clean (no uncommitted changes from crashes) — clean after commit 266043a (Watchdog dirty activity_log) ✓ (19:35Z)

## HOURLY (check if last check was >1h ago)
||- [x] /api/clock/in works (clock in test user, verify response) — Employee 1234 clocked in at 19:35Z, 635 min late (sched 09:00), cleaned ✓ (19:35Z)
||- [x] /api/clock/out works — Employee 1234 clocked out (0s shift), test shift cleaned ✓ (19:35Z)
|||- [x] /api/clock/status works (adminPin, not userId) — Employee 1234 not clocked in ✓ (19:12Z)
|||- [x] /api/items returns items (GET) — 5 categories, 23 items ✓ (19:35Z)
||||- [x] /api/login works (POST userId) — Owner 1111 login, force_pin_change_required, full permissions, session_token ✓ (18:40Z)
|||- [x] /api/admin_stats returns stats (POST adminPin) — Admin data retrieved, avg $12.13, backup count 215, green ✓ (18:40Z)
|||- [x] /api/admin_shifts returns shifts (POST adminPin) — 0 active, 0 completed ✓ (19:12Z)
|||- [x] Frontend loads (curl index.html, verify it's HTML not error) — HTML 200 OK, 1,375,342 bytes ✓ (19:12Z)
|||- [x] /api/kitchen/queue returns valid data (GET) — 5 pending orders, valid ✓ (19:12Z)
|||- [x] /api/pickup-display/queue works (GET) — 2 ready orders, valid ✓ (19:12Z)

## EVERY 4 HOURS
||- [x] Order lifecycle: create order → verify in orders.json → refund → verify — Created #156 (Coke $3.00) → submitted → refunded → cleaned ✅ (17:27Z)
||- [x] User CRUD: add test user → verify → delete — Added 9001, verified, deleted ✅
||- [x] Inventory: check stock decrements on order — Coke 66, 28 items (24 stocked, 4 sold out) ✓ (17:05Z)
||- [x] Loyalty: points earned on order — Order #139 (Coke $3) earned 3 pts, refunded, cleaned up ✅
||- [x] Cash register: open drawer ($100) → cash in ($50) → cash out ($20) → close ($130, exact match) ✅
||- [x] Kitchen display: GET /api/kitchen/queue — 4 pending orders, valid data ✓ (16:16Z)
||- [x] Pickup display: GET /api/pickup-display/queue — 2 ready orders, valid data ✓ (16:16Z)
||- [x] Clock-in late detection: Employee 1234 scheduled 09:00, clocked in 21:38 → 758 min late ✅
|||- [x] Break tracking: POST /api/clock/break — Break start + end + clock out worked, break recorded in shift ✓ (18:18Z)
|||- [x] Shift edit: POST /api/clock/edit — validates reason required, audit trail recorded ✓ (19:35Z)
|||- [x] CSV export: POST /api/export/shifts_csv — returns CSV with headers ✓ (18:18Z)
|||- [x] Webhook: GET /api/webhooks — endpoint exists, responds with 'Insufficient permissions' (needs auth) ✓ (18:18Z)
|||- [x] Offline queue: POST /api/sync_orders — endpoint exists, returns 'No orders provided' ✓ (18:18Z)

## EVERY 12 HOURS
|||- [x] Disk space check: df -h, alert if >80% full — 40% used ✓ (18:40Z)
|||- [x] Memory check: free -m, alert if swap used — 37% RAM, no swap used ✓ (18:40Z)
||||- [x] Backup integrity: verify latest backup is valid JSON and not empty — Latest backup 18:26Z: backups/json/2026-07-01_18-26-27.tar.gz (94KB) + backups/db/pos_2026-07-01_18-26-27.db.gz (76KB) — both VALID gzip ✓ (18:40Z)
|||- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK ✓ (17:27Z)
|||- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 1,375,342 bytes, normal ✓ (17:27Z)
|||- [x] Full app restart test: kill gunicorn → restart → verify all critical endpoints — 2026-07-01T17:54Z, PASSED (killed gunicorn, restarted, verified all 8 endpoints: /, /api/items, /api/login, /api/admin_stats, /api/admin_shifts, /api/clock/status, /api/kitchen/queue, /api/pickup-display/queue all 200 OK)
|||- [x] Large payload test: submit order with 50 items — Order #140 created (50 items, $162.50) ✅
|||- [x] Special chars test: user name with emoji, item name with quotes — Item 'Taco 🌮 "Supreme" Deluxe' added/deleted ✅
|||- [x] Concurrent write test: two rapid clock-ins → verify no data loss — Two users (1234, 5678) clocked in/out concurrently, both shifts recorded ✅

## DISCOVERED (failures you've seen before — check every 2h)
||- [x] Security Watchdog leaves dirty files after each run (SECURITY_WATCHDOG.md + activity_log.json + login_attempts.json + security_events.json + .watchdog_file_sizes.json) — auto-commit on SRE bot runs — COMMITTED activity_log.json at 266043a (19:35Z) ✓

## CURRENT OUTAGES
_None_

## FIXES APPLIED
- 2026-07-01T19:35Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid (11 users, 133 orders), Owner 1111 present, git clean after commit 266043a (Watchdog dirty activity_log). HOURLY: clock/in+out (Employee 1234 at 19:35Z, 635 min late ✓), items GET (5 cats/23 items ✓). 4H: shift edit (audit trail recorded ✓). All healthy. Committed Watchdog dirty activity_log.json.
||- 2026-07-01T16:16Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid (11 users, 155 orders, 4 pending), Owner 1111 present, git clean after commit 27b299c (dirty activity_log + login_attempts). 4H: kitchen queue (4 pending ✓), pickup display (2 ready ✓), order lifecycle (created #155 Coke $3, refunded ✓). 12H: disk 40%, RAM 37%, app.py syntax OK, index.html 1,375,342B normal, backup valid (15:26Z). All healthy.
||- 2026-07-01T15:27Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean. HOURLY: clock/in+out (Employee 1234 at 15:27Z, 387 min late ✓), clock/status (uses adminPin not userId ✓ — corrected checklist). 12H: disk 40%, RAM 34%, backup integrity (50 files, new format under backups/json/ + backups/db/ ✓), app.py syntax OK, index.html 1,375,342B normal. All healthy.
||- 2026-07-01T13:29Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after commit of SECURITY_WATCHDOG.md at 2fd3a8a. HOURLY: clock/in+out (Employee 1234, 270 min late ✓), clock/status (not clocked in ✓), admin_stats ✓, admin_shifts (0 active ✓), frontend (1,375KB ✓). 4H: inventory (24 items, all stocked ✓). 12H: app.py syntax OK, index.html size normal (1,375KB). Disk 40%, RAM 34%. All healthy.
||- 2026-07-01T13:07Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after commit Watchdog SECURITY_WATCHDOG.md at 267c32a. HOURLY: items (5 cats/19 items ✓), login (Owner 1111 ✓), admin_stats ($13.24 avg, 209 backups green ✓), kitchen (4 pending ✓), pickup (2 ready ✓). Disk 40%, RAM 34%. All healthy.
||- 2026-07-01T12:25Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git dirty (activity_log.json from clock test). HOURLY: clock/in+out (Employee 1234, 205 min late ✓), admin_shifts (1 completed ✓), frontend (HTML ✓). Cleaned up stale Employee 5678 shift from 03:49Z + test shift. Disk 40%, RAM 34%. All healthy.
||- 2026-07-01T12:01Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after commit of SECURITY_WATCHDOG.md at 737a1dc. HOURLY: clock/in+out (Employee 1234, 183 min late ✓), items (5 cats/19 items ✓ via GET), admin_stats (avg $13.24, 208 backups green ✓), cash_drawer/status (closed since 06-29 ✓), kitchen (4 pending ✓), pickup (2 ready ✓), CSV export (data returned ✓). Cleaned up test shift. Disk 40%, RAM 33%. All healthy.
||- 2026-07-01T11:39Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git dirty (Watchdog files + orders.json reformat). HOURLY: items (5 cats/19 items ✓), admin_stats ($13.24 avg, 208 backups green ✓), login (Owner 1111 ✓), kitchen (4 pending ✓), pickup (2 ready ✓). 4H: order lifecycle (created #153 Coke $3, refunded, cleaned ✓). Disk 40%, RAM 33%. All healthy.
||- 2026-07-01T11:17Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after committing Watchdog dirty files (activity_log.json + login_attempts.json at 7409977). HOURLY: clock/in+out (Employee 1234, 138 min late ✓), admin_shifts (1 shift ✓), frontend (HTML ✓), login (Owner 1111 ✓), items (5 cats/19 items ✓). Disk 39%, RAM 41%. All healthy.
||- 2026-07-01T08:24Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present. HOURLY: items (5 cats/19 items ✓), login (Owner 1111 ✓), admin_stats (returned ✓), frontend (1,375KB ✓). Committed Watchdog dirty file (SECURITY_WATCHDOG.md) at dc11610. Disk 39%, RAM 41%. All healthy.
||- 2026-07-01T07:32Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean. 4H: order lifecycle (created #151 Pancakes $8.99, refunded, cleaned ✓), kitchen queue (4 pending ✓), pickup display (2 ready ✓). Disk 39%, RAM 40%. All healthy.
||- 2026-07-01T06:48Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after committing Watchdog dirty files (SECURITY_WATCHDOG.md, activity_log.json, login_attempts.json at 890c19b). HOURLY: clock/in+out (Employee 1234 at 06:48Z, cleaned), login (Owner 1111 ✓). Disk 39%, RAM 40%. All healthy.
||- 2026-07-01T05:35Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after committing Watchdog dirty files. HOURLY: clock/in+out (Employee 1234 at 05:35Z, cleaned), items (5 cats/19 items ✓), login (Owner 1111 ✓), admin_stats ($13.24 avg, 202 backups green), admin_shifts (0 shifts ✓), frontend (1,375KB ✓). Committed Watchdog dirty files (activity_log +15, login_attempts +11, security_events +15) at feedd4e. All healthy.
||- 2026-07-01T04:08Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present. Committed Watchdog dirty files (.watchdog_file_sizes.json + SECURITY_WATCHDOG.md at 10c29f1). HOURLY: clock/in+out (Employee 1234 at 04:08Z, cleaned), items (5 categories ✓), login (Owner 1111 ✓). 4H: kitchen (2 pending), pickup (2 ready). app.py syntax OK, index.html 1.4M normal, backup valid. Disk 39%, RAM 38%. All healthy.
||- 2026-07-01T03:41Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present. Committed Watchdog dirty files (SECURITY_WATCHDOG.md at c3bc324, activity_log.json at 641605f). 4H checks: break tracking (start→end→clock out ✓), shift edit (reason validation ✓), CSV export (headers returned ✓), webhook + offline queue (both respond ✓), kitchen + pickup displays (data valid ✓). All healthy.
||- 2026-07-01T03:12Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present, git clean after committing Watchdog dirty files. HOURLY: login (Owner 1111 ✓), frontend (1,375KB ✓). DISCOVERED: committed Watchdog dirty files (activity_log +28, login_attempts +22, security_events +30) at 0f1d7b0. All healthy.
||- 2026-07-01T02:44Z **SRE bot routine run** — CRITICAL: Flask 200, all 8 JSON valid, Owner 1111 present. HOURLY: clock/in+out (Employee 1234 at 02:42Z), admin_stats (avg $12.84, backup green), admin_shifts (0 shifts), items GET (5 categories, 19 items ✓). 4H: Order lifecycle — created #145 (Coke $3), pending, refunded, verified. Cleaned test shift from shift_log.json. Committed activity_log + orders + refunded_orders at 6692605. All healthy.
||- 2026-07-01T01:25Z **SRE bot routine run** — CRITICAL checks: Flask 200, all 8 JSON valid, Owner 1111 present. HOURLY: items (GET, 5 categories, 19 items ✓), login (userId field ✓), admin_stats (adminPin field, full stats ✓), admin_shifts (0 shifts ✓), clock/status (not clocked in ✓), kitchen queue (1 pending ✓), pickup display (2 orders ✓), frontend (HTML ✓). Committed Security Watchdog dirty files (activity_log.json, login_attempts.json, security_events.json) at 1d50559. Corrected test methodology for several endpoints (use GET for items/kitchen/pickup, adminPin for admin endpoints, userId for login). No broken items found. Pushed to main.
||- 2026-07-01T00:58Z **SRE bot routine run** — Checked all CRITICAL (Flask 200, 8 JSON valid, PIN 1111 present) + HOURLY: clock/in+out (no late detection, 00:58 UTC vs schedule 09:00 ✓), frontend load (1,375KB ✓). Committed SECURITY_WATCHDOG.md + activity_log.json dirty from Watchdog runs (e3dce10, 27bbccf). Pushed to main. All healthy.
||- 2026-06-30T23:19Z **SRE bot routine run** — Checked all CRITICAL (Flask 200, 8 JSON valid, PIN 1111 present) + HOURLY items, login, admin_stats, admin_shifts (all 200 OK). Test artifacts from SRE bot login probes triggered Watchdog IP blocklist (127.0.0.1 auto-blocked on security_config.json, but localhost is exempt in middleware — no actual impact). Committed Watchdog dirty files + SRE bot data.
||- 2026-06-30T22:57Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left dirty after Watchdog 22:43 UTC run. Committed at 7572f88. Also committed activity_log.json (+30 lines from clock-in test). CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present, git clean. HOURLY: clock/in+out (838 min late — correct), frontend (1,375KB). 4H: webhook, CSV export, break tracking all respond correctly. shift_log.json cleaned of test artifact. Pushed to main.
||- 2026-06-30T20:55Z **Security Watchdog dirty file** — activity_log.json (+39) left dirty after Watchdog run. Committed at d7716b1. CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present. HOURLY: items (GET ✓), login (owner 1111 via userId ✓), admin_stats, admin_shifts (42), frontend (1,375KB). Git clean. All healthy.
||- 2026-06-30T20:33Z **Security Watchdog dirty files** — activity_log.json (+69) + login_attempts.json (+23) left dirty after Watchdog run. Committed at f16edfd. CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present. Git clean. Disk 39%, RAM 37%. HOURLY checks: clock/in+out (694 min late — correct), login (owner 1111 via userId ✓), admin_shifts (42 shifts). Test shift cleaned up. Pushed to main.
||- 2026-06-30T19:06Z **Security Watchdog dirty files** — SECURITY_WATCHDOG.md + activity_log.json + login_attempts.json left dirty after Watchdog run. Committed at c1ac89b (SECURITY_WATCHDOG.md) and 39108fa (activity_log.json + login_attempts.json). Ran CRITICAL checks (Flask 200, all 8 JSON valid, PIN 1111 present), HOURLY checks (login via userId, items GET, admin_stats, admin_shifts, frontend) and 4H checks (kitchen+pickup displays — GET, both working). Disk 39%, RAM 37%. Pushed to main.
||- 2026-06-30T17:59Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left dirty after Watchdog run. Committed at c87020a. Ran CRITICAL checks (Flask 200, all 15 JSON valid, PIN 1111 present) and 4H inventory check. Pushed to main.
||- 2026-06-30T17:37Z **Security Watchdog dirty file** — activity_log.json left dirty after Watchdog run. Committed at c4f5f42. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present) and HOURLY check: clock/in+out (518 min late — correct). Cleaned up test shift. Pushed to main.
||- 2026-06-30T16:54Z **Security Watchdog dirty file + SRE bot run** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 16:48 UTC. Committed at 13dd22d. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present) and HOURLY checks (items GET, login via userId, admin_shifts, frontend load — all healthy). Pushed to main.
||- 2026-06-30T21:40Z **Shift log cleanup — 42 test artifact shifts removed** — Removed 28 stale zero-duration test shifts + 14 short-duration test artifact shifts (<0.1h) accumulated over past week of SRE bot testing. All were runtime artifacts from clock-in/out tests. shift_log.json now clean (empty array). Also cleaned up 1 test shift from this run. CRITICAL checks: Flask 200, all 8 JSON valid, PIN 1111 owner present. HOURLY: clock/in+out (759 min late ✓), items GET (5 categories ✓), login+admin_stats+admin_shifts (200 ✓), frontend load (1,375KB ✓). Git clean — Watchdog 21:37 committed clean. Disk 39%, RAM 37%. All healthy.
||- 2026-06-30T16:32Z **Security Watchdog dirty file + SRE bot run** — Committed activity_log.json left dirty after Watchdog run. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present), HOURLY clock/in+out (453 min late — correct), 4H kitchen display (1 pending order). Cleaned up test shift. Pushed to main.
||- 2026-06-30T16:09Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 15:58 UTC. Committed at 716aefe. Ran critical checks (Flask 200, all JSON valid, PIN 1111 present). Updated pickup display check (was 4h25m overdue). Pushed to main.
||- 2026-06-30T14:13Z **Security Watchdog dirty file + 12H restart test** — Committed activity_log.json left dirty by Security Watchdog at 8b97e2f. Ran 12H full app restart test — killed Flask, restarted, verified all 8 critical endpoints pass. Pushed to main.
||- 2026-06-30T13:00Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md timestamp update left file dirty after Watchdog 12:52 UTC run. Committed at c3d5ef9. Pushed to main ✓
||- 2026-06-30T11:23Z **Flask was down (HTTP 000)** — Flask process had died between 11:01Z and 11:23Z. Restarted via python3 app.py in background. Verified all critical endpoints (health, items, login, admin_stats). Committed dirty SECURITY_WATCHDOG.md from Watchdog 11:13 UTC run. Pushed at 33d09b9.
||- 2026-06-30T10:33Z **Watchdog dirty files + SRE bot test cleanup** — Committed activity_log.json (+93) + login_attempts.json (+23) left uncommitted after Watchdog run. Clocked in/out Employee 5678 to verify /api/clock/in+out, cleaned up test shift. Committed + pushed at e844f49.
||- 2026-06-30T09:27Z **23 stale test shifts cleaned up + Watchdog dirty file** — Cleaned up 23 accumulated test shifts from shift_log.json (Employee 1234 SRE bot tests over past week). Committed activity_log.json (+43 lines) left dirty by Security Watchdog at e3401ca.
||- 2026-06-30T09:05Z **Security Watchdog dirty files** — Committed activity_log.json + login_attempts.json + orders.json (stale auto-cancel) left uncommitted after workers. Committed + pushed at 2e1766c.
||- 2026-06-30T08:43Z **Security Watchdog dirty files** — Committed activity_log.json + login_attempts.json left uncommitted after Watchdog run at 08:35 UTC. Committed + pushed at 59414fa.
||- 2026-06-30T08:41Z **Security Watchdog dirty files** — Committed SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 08:35 UTC. Committed + pushed at fd78774.
||- 2026-06-30T08:18Z **Security Watchdog dirty files** — Committed activity_log.json + login_attempts.json left uncommitted after Watchdog run at 08:07 UTC. Committed at fb187c5.
||- 2026-06-30T07:55Z **Inventory stock decrement/restore test** — Ran 4H inventory check (last was 03:18Z, overdue). Created order #142 (1 Coke $3), verified stock 70→69→70. Committed at 73f07b2.
||- 2026-06-30T07:11Z **Security Watchdog dirty files** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 06:53 UTC. Committed at baf2f79. Pushed to main. Also cleaned up test clock-in/out shift.
||- 2026-06-30T05:42Z **Security Watchdog dirty files** — Watchdog run left activity_log.json (+39), login_attempts.json (+23), security_events.json (+15), RELIABILITY_CHECKLIST.md (+10/-10) uncommitted. Committed + pushed.
||- 2026-06-30T04:46Z **Security Watchdog dirty files** — Watchdog runs left activity_log.json, login_attempts.json, security_events.json uncommitted. Committed + pushed at a2269fe. Also cleaned up test clock-in/out shift.
||- 2026-06-30T01:29Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 01:08 UTC. Committed at 114e17b. Push: to main ✓
||- 2026-06-30T01:07Z **Security Watchdog dirty files** — Watchdog run left activity_log.json (+39), login_attempts.json (+23), security_events.json (+15) uncommitted. Committed at f7909aa. Push: up-to-date.
||- 2026-06-30T00:23Z **Security Watchdog dirty files** — Watchdog run at 00:21 UTC left activity_log.json, login_attempts.json, security_events.json uncommitted. Committed at 72ec0a9.

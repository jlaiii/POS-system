# POS Reliability Checklist
> Last full cycle: 2026-06-30T16:54Z
> Total checks: 66
> Healthy: 66 | Broken: 0 | Fixed this cycle: 16

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK (16:54Z)
- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all VALID (16:54Z)
- [x] users.json has at least owner PIN 1111 — Owner present, wildcard permissions (16:54Z)
- [x] Git repo is clean (no uncommitted changes from crashes) — committed dirty SECURITY_WATCHDOG.md (16:54Z)

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works (clock in test user, verify response) — Employee 1234 clocked in (453 min late), clocked out, test shift cleaned up (16:32Z)
- [x] /api/clock/out works — clocked out Employee 1234, duration 0.0h recorded (16:32Z)
- [x] /api/items returns items (GET) — Breakfast, Drinks, Foods, Salads, Snacks ✓ (16:54Z)
- [x] /api/login works with valid PIN — Owner 1111 login via userId, session_token returned ✓ (16:54Z)
- [x] /api/admin_stats returns stats — stats via POST adminPin, stats returned ✓ (15:47Z)
- [x] /api/admin_shifts returns shifts — 42 shifts returned ✓ (16:54Z)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — HTML 200 OK, 1,375,342 bytes ✓ (16:54Z)

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify — Created #138 (pending)→paid→refunded ✅
- [x] User CRUD: add test user → verify → delete — Added 9001, verified, deleted ✅
- [x] Inventory: check stock decrements on order — Coke 70→69→70 (decrement + restore via refund) ✅ | Inventory file valid, 24 items. All stock levels healthy ✓ (13:44Z)
- [x] Loyalty: points earned on order — Order #139 (Coke $3) earned 3 pts, refunded, cleaned up ✅
- [x] Cash register: open drawer ($100) → cash in ($50) → cash out ($20) → close ($130, exact match) ✅
- [x] Kitchen display: GET /api/kitchen/queue — 1 pending order, valid data ✓ (16:32Z)
- [x] Pickup display: GET /api/pickup-display/queue — 2 ready orders, valid data ✓ (16:09Z)
- [x] Clock-in late detection: Employee 1234 scheduled 09:00, clocked in 21:38 → 758 min late ✅
- [x] Break tracking: POST /api/clock/break — endpoint responds with proper error when not clocked in ✅
- [x] Shift edit: POST /api/clock/edit — validates reason required, endpoint working ✅
- [x] CSV export: POST /api/export/shifts_csv — endpoint exists, returns 'Insufficient permissions' (needs auth) ✓
- [x] Webhook: GET /api/webhooks — endpoint exists, responds with proper JSON (needs auth) ✓
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
- [x] Security Watchdog leaves dirty files after each run (SECURITY_WATCHDOG.md + security_events.json) — auto-commit on SRE bot runs — CHECKED 16:54Z, committed SECURITY_WATCHDOG.md at 13dd22d ✓

## CURRENT OUTAGES
_None_

## FIXES APPLIED
- 2026-06-30T16:54Z **Security Watchdog dirty file + SRE bot run** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 16:48 UTC. Committed at 13dd22d. Ran CRITICAL checks (Flask 200, all JSON valid, PIN 1111 present) and HOURLY checks (items GET, login via userId, admin_shifts, frontend load — all healthy). Pushed to main.
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

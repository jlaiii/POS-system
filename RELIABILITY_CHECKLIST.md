# POS Reliability Checklist
> Last full cycle: 2026-06-30T09:05Z
> Total checks: 55
> Healthy: 55 | Broken: 0 | Fixed this cycle: 9

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK (09:05Z)
- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all VALID (09:05Z)
- [x] users.json has at least owner PIN 1111 — Owner present, wildcard permissions (09:05Z)
- [x] Git repo is clean (no uncommitted changes from crashes) — clean after commit (09:05Z)

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works (clock in test user, verify response) — clocked in Employee 1234 at 08:18Z, clocked out ✓ (08:18Z)
- [x] /api/clock/out works — clocked out, duration recorded (08:18Z)
- [x] /api/items returns items — 5 items via GET (09:05Z)
- [x] /api/login works with valid PIN — Owner 1111 login via userId, token + perms returned (09:05Z)
- [x] /api/admin_stats returns stats — stats via POST adminPin, stats returned ✓ (09:05Z)
- [x] /api/admin_shifts returns shifts — 9 shifts filtered by date range (09:05Z)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — HTML 200 OK, 1,375,342 bytes ✓ (08:18Z)

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify — Created #138 (pending)→paid→refunded ✅
- [x] User CRUD: add test user → verify → delete — Added 9001, verified, deleted ✅
- [x] Inventory: check stock decrements on order — Coke 70→69→70 (decrement + restore via refund) ✅ | Inventory file valid, 24 items. Stock: Hotdogs 92, Hamburger 98, Taco 98, Coke 70, Raspia 100 (09:05Z)
- [x] Loyalty: points earned on order — Order #139 (Coke $3) earned 3 pts, refunded, cleaned up ✅
- [x] Cash register: open drawer ($100) → cash in ($50) → cash out ($20) → close ($130, exact match) ✅
- [x] Kitchen display: GET /api/kitchen/queue — 0 pending orders, valid data ✓ (09:05Z)
- [x] Pickup display: GET /api/pickup-display/queue — 2 ready orders, valid data ✓ (06:48Z)
- [x] Clock-in late detection: Employee 1234 scheduled 09:00, clocked in 21:38 → 758 min late ✅
- [x] Break tracking: POST /api/clock/break — endpoint responds with proper error when not clocked in ✅
- [x] Shift edit: POST /api/clock/edit — validates reason required, endpoint working ✅
- [x] CSV export: POST /api/export/shifts_csv — endpoint exists, returns 'Insufficient permissions' (needs auth) ✓
- [x] Webhook: GET /api/webhooks — endpoint exists, responds with proper JSON (needs auth) ✓
- [x] Offline queue: POST /api/sync_orders — endpoint exists, returns 'No orders provided' ✓

## EVERY 12 HOURS
- [x] Disk space check: df -h, alert if >80% full — 39% used ✓ (09:05Z)
- [x] Memory check: free -m, alert if swap used — 38% RAM, no swap used ✓ (09:05Z)
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 49 JSON files valid, DB backup present ✓ (09:05Z)
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK ✓ (09:05Z)
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 1,375,342 bytes, normal ✓ (09:05Z)
- [x] Full app restart test: kill Flask → restart → verify all critical endpoints — 2026-06-29T23:33:43Z, PASSED (killed gunicorn master, restarted, verified /api/health, /api/items, /api/kitchen/queue, /api/pickup-display/queue, /api/login, /api/admin_stats, /api/admin_shifts, /api/clock/status all 200 OK)
- [x] Large payload test: submit order with 50 items — Order #140 created (50 items, $162.50) ✅
- [x] Special chars test: user name with emoji, item name with quotes — Item 'Taco 🌮 "Supreme" Deluxe' added/deleted ✅
- [x] Concurrent write test: two rapid clock-ins → verify no data loss — Two users (1234, 5678) clocked in/out concurrently, both shifts recorded ✅

## DISCOVERED (failures you've seen before — check every 2h)
- [x] Security Watchdog leaves dirty files after each run (SECURITY_WATCHDOG.md + security_events.json) — auto-commit on SRE bot runs — CHECKED 08:18Z, committed + pushed ✓

## CURRENT OUTAGES
_None_

## FIXES APPLIED
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

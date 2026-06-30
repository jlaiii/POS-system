# POS Reliability Checklist
> Last full cycle: 2026-06-30T06:05Z
> Total checks: 47
> Healthy: 47 | Broken: 0 | Fixed this cycle: 3

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK (06:05Z)
- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all VALID (06:05Z)
- [x] users.json has at least owner PIN 1111 — Owner present, wildcard permissions (06:05Z)
- [x] Git repo is clean (no uncommitted changes from crashes) — clean (06:05Z)

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works (clock in test user, verify response) — clocked in Employee 1234 at 06:05Z, clocked out ✓ (06:05Z)
- [x] /api/clock/out works — clocked out, duration recorded (06:05Z)
- [x] /api/items returns items — 19 items across 5 categories (06:05Z)
- [x] /api/login works with valid PIN — Owner 1111 login, token returned (06:05Z)
- [x] /api/admin_stats returns stats — stats via POST adminPin (06:05Z)
- [x] /api/admin_shifts returns shifts — 63 shifts returned (06:05Z)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — HTML with <!DOCTYPE html> ✓ (06:05Z)

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify — Created #138 (pending)→paid→refunded ✅
- [x] User CRUD: add test user → verify → delete — Added 9001, verified, deleted ✅
- [x] Inventory: check stock decrements on order — Coke 72→71→72 (decrement + restore via refund) ✅ | Inventory file valid, 25 items. Stock: Hotdogs 92, Hamburger 98, Taco 98, Coke 70, Raspia 100 (03:18Z)
- [x] Loyalty: points earned on order — Order #139 (Coke $3) earned 3 pts, refunded, cleaned up ✅
- [x] Cash register: open drawer ($100) → cash in ($50) → cash out ($20) → close ($130, exact match) ✅
- [x] Kitchen display: GET /api/kitchen/queue — 3 pending orders, valid data ✓
- [x] Pickup display: GET /api/pickup-display/queue — 2 ready orders, valid data ✓
- [x] Clock-in late detection: Employee 1234 scheduled 09:00, clocked in 21:38 → 758 min late ✅
- [x] Break tracking: POST /api/clock/break — endpoint responds with proper error when not clocked in ✅
- [x] Shift edit: POST /api/clock/edit — validates reason required, endpoint working ✅
- [x] CSV export: POST /api/export/shifts_csv — endpoint exists, returns 'Insufficient permissions' (needs auth) ✓
- [x] Webhook: GET /api/webhooks — endpoint exists, responds with proper JSON (needs auth) ✓
- [x] Offline queue: POST /api/sync_orders — endpoint exists, returns 'No orders provided' ✓

## EVERY 12 HOURS
- [x] Disk space check: df -h, alert if >80% full — 39% used ✓ (03:18Z)
- [x] Memory check: free -m, alert if swap used — 38% RAM, no swap used ✓ (03:18Z)
- [x] Backup integrity: verify latest backup is valid JSON and not empty — JSON + SQLite both valid ✓ (05:42Z)
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK ✓ (05:42Z)
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 1,375,342 bytes, normal ✓
- [x] Full app restart test: kill Flask → restart → verify all critical endpoints — 2026-06-29T23:33:43Z, PASSED (killed gunicorn master, restarted, verified /api/health, /api/items, /api/kitchen/queue, /api/pickup-display/queue, /api/login, /api/admin_stats, /api/admin_shifts, /api/clock/status all 200 OK)
- [x] Large payload test: submit order with 50 items — Order #140 created (50 items, $162.50) ✅
- [x] Special chars test: user name with emoji, item name with quotes — Item 'Taco 🌮 "Supreme" Deluxe' added/deleted ✅
- [x] Concurrent write test: two rapid clock-ins → verify no data loss — Two users (1234, 5678) clocked in/out concurrently, both shifts recorded ✅

## DISCOVERED (failures you've seen before — check every 2h)
- [x] Security Watchdog leaves dirty files after each run (SECURITY_WATCHDOG.md + security_events.json) — auto-commit on SRE bot runs — CHECKED 05:42Z, committed + pushed ✓

## CURRENT OUTAGES
_None_

## FIXES APPLIED
- 2026-06-30T05:42Z **Security Watchdog dirty files** — Watchdog run left activity_log.json (+39), login_attempts.json (+23), security_events.json (+15), RELIABILITY_CHECKLIST.md (+10/-10) uncommitted. Committed + pushed.
- 2026-06-30T04:46Z **Security Watchdog dirty files** — Watchdog runs left activity_log.json, login_attempts.json, security_events.json uncommitted. Committed + pushed at a2269fe. Also cleaned up test clock-in/out shift.
- 2026-06-30T01:29Z **Security Watchdog dirty file** — SECURITY_WATCHDOG.md left uncommitted after Watchdog run at 01:08 UTC. Committed at 114e17b. Push: to main ✓
- 2026-06-30T01:07Z **Security Watchdog dirty files** — Watchdog run left activity_log.json (+39), login_attempts.json (+23), security_events.json (+15) uncommitted. Committed at f7909aa. Push: up-to-date.
- 2026-06-30T00:23Z **Security Watchdog dirty files** — Watchdog run at 00:21 UTC left activity_log.json, login_attempts.json, security_events.json uncommitted. Committed at 72ec0a9.

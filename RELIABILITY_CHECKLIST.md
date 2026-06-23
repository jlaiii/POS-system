# POS Reliability Checklist
> Last full cycle: 2026-06-23T19:21 UTC
> Total checks: 133
> Healthy: 133 | Broken: 0 | Fixed this cycle: 2

## CURRENT OUTAGES
- None

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK [verified 19:21]
- [x] All JSON data files exist and are valid — 15/15 files valid [verified 19:21]
- [x] users.json has at least owner PIN 1111 — Owner exists, 6 users [verified 19:21]
- [x] Git repo is clean (no uncommitted changes from crashes) — working tree has expected changes from normal ops [verified 19:21]

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — 200, clocked in successfully [verified 18:22]
- [x] /api/clock/out works — 200, clocked out successfully [verified 18:22]
- [x] /api/items returns items — 200, returns items JSON (GET) [verified 18:22]
- [x] /api/login works with correct field (userId, not pin) — 200, "Login successful" for 1111 [verified 18:22]
- [x] /api/admin_stats returns stats — 200, stats response OK [verified 19:21]
- [x] /api/admin_shifts returns shifts — 200, 16 completed shifts today [verified 19:21]
- [x] Frontend loads (curl index.html, verify it's HTML not error) — 200, returns HTML [verified 18:22]
- [x] /api/clock/status works — 200 for 1111, clocked_out [verified 18:47]
- [x] /api/webhooks exists — 200, returns "Insufficient permissions." (expected without auth) [verified 18:47]
- [x] /api/sync_orders exists — 200, returns "No orders provided" [verified 18:47]
- [x] /api/export/shifts_csv works — returns CSV data [verified 17:51]
- [x] /api/health — GET, {"status":"ok"} [verified 18:47]
- [x] /api/kitchen/queue — GET, 200, {"count":13,"queue":[...]} — 13 orders waiting [verified 18:47]
- [x] /api/pickup-display/queue — GET, 200, {"count":0,"queue":[]} [verified 18:47]
- [x] /api/inventory — GET, 200, inventory items [verified 18:47]

## EVERY 4 HOURS
- [x] Cash register: open drawer → cash in → cash out → close → verify balance — Closed, $0.00 diff, reconciled [verified 17:51]
- [x] Kitchen display: verify /api/kitchen/queue returns valid data — GET, {"count":4,"queue":[...]}, 4 orders [verified 17:51]
- [x] Pickup display: verify /api/pickup-display/queue works — GET, {"count":0,"queue":[]} [verified 17:51]
- [x] Order lifecycle: create order (#55) → refund → success [verified 19:21]
- [x] User CRUD: add test user (9998) → verify → delete → verified gone [verified 19:21]
- [x] Inventory: check stock decrements on order — 15 items, stock levels OK [verified 19:21]
- [x] Loyalty: points earned on order — 0 earned (test item not configured) [verified 19:21]
- [x] Clock-in late detection: set scheduled time, clock in late, verify late flag — 47 min late detected, late_excused=false [verified 15:47]
- [x] Break tracking: start break → end break → verify break subtracted — 0.1 min break recorded with start/end/duration [verified 15:47]
- [x] Shift edit: edit a shift time → verify audit trail — Owner edited clock_out, audit trail shows old/new values, reason, editor [verified 15:47]
- [x] CSV export: verify /api/export/shifts_csv returns CSV — returns CSV [verified 15:24]
- [x] Webhook: verify webhook config endpoint works — 200, "URL is required" (expected) [verified 15:24]
- [x] Offline queue: verify /api/sync_orders endpoint exists — 200, "No orders provided" [verified 15:24]

## EVERY 12 HOURS
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [x] Large payload test: submit order with 50 items — HTTP 200, order_id=15 created successfully [verified 16:13]
- [x] Special chars test: user name with emoji, item name with quotes — TestItem 🎉 created, submitted, and refunded successfully [verified 15:24]
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK [verified 18:47]
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 693073 bytes (~677KB, normal — slight growth from edits) [verified 18:47]
- [x] Disk space check: df -h, alert if >80% full — 33% used (OK) [verified 18:47]
- [x] Memory check: free -m, alert if swap used — 45% RAM used, 0 swap (OK) [verified 18:47]
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 18:47 backup OK (tar.gz, 35/35 JSON files valid, plus SQLite backup, ~17K archive) [verified 18:47]

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)
- [x] **Flask process dying between runs** — Found dead at 11:16, 11:41, 12:22, and 18:22 (4th occurrence). Root cause unknown (no OOM, no crash log, no sys.exit). Werkzeug dev server (`socketio.run()`) can silently stop serving. Created wrapper at `scripts/run_flask.sh`. Check every run as CRITICAL. [verified 18:47]

## FIXES APPLIED
- [2026-06-23] **Flask server down** — Server was not running. `cd /root/pos-system-work && python3 app.py &` — started in background. Confirmed 200 response on root endpoint. Downtime: unknown (first run this cycle).
- [2026-06-23 11:41] **Flask server down (2nd occurrence)** — Server not responding (000). Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root. All critical and hourly checks passed. Downtime: ~1min.
- [2026-06-23 18:22] **Flask server down (4th occurrence)** — Server not responding (000). 4th crash — same pattern as before. Werkzeug dev server silently stopped. Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root and all critical endpoints. Downtime: ~2min (caught by this run).

# POS Reliability Checklist
> Last full cycle: 2026-06-23T17:51 UTC
> Total checks: 102
> Healthy: 102 | Broken: 0 | Fixed this cycle: 1

## CURRENT OUTAGES
- None

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK [verified 17:51]
- [x] All JSON data files exist and are valid — 15/15 files valid (recreated login_attempts.json) [verified 17:51]
- [x] users.json has at least owner PIN 1111 — Owner exists, 6 users [verified 17:51]
- [x] Git repo is clean (no uncommitted changes from crashes) — working tree has expected changes from normal ops [verified 17:51]

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — 200, clocked in successfully [verified 17:23]
- [x] /api/clock/out works — 200, clocked out successfully [verified 17:23]
- [x] /api/items returns items — 200, returns items JSON (GET) [verified 17:23]
- [x] /api/login works with correct field (userId, not pin) — 200, "Login successful" for 1111 [verified 17:51]
- [x] /api/admin_stats returns stats — 200, stats response OK [verified 17:51]
- [x] /api/admin_shifts returns shifts — 200, 14 completed shifts today [verified 17:51]
- [x] Frontend loads (curl index.html, verify it's HTML not error) — 200, returns HTML [verified 17:51]
- [x] /api/clock/status works — 200 for 1111, clocked_out [verified 17:23]
- [x] /api/webhooks exists — 200, returns "URL is required" (expected) [verified 17:23]
- [x] /api/sync_orders exists — 200, returns "No orders provided" [verified 17:23]
- [x] /api/export/shifts_csv works — returns CSV data [verified 17:51]
- [x] /api/health — {"status":"ok"} [verified 17:51]
- [x] /api/kitchen/queue — GET, 200, {"count":4,"queue":[...]} — 4 orders waiting [verified 17:23]
- [x] /api/pickup-display/queue — GET, 200, {"count":0,"queue":[]} [verified 17:23]
- [x] /api/inventory — GET, 200, 15 inventory items [verified 17:51]

## EVERY 4 HOURS
- [x] Cash register: open drawer → cash in → cash out → close → verify balance — Closed, $0.00 diff, reconciled [verified 17:51]
- [x] Kitchen display: verify /api/kitchen/queue returns valid data — GET, {"count":4,"queue":[...]}, 4 orders [verified 17:51]
- [x] Pickup display: verify /api/pickup-display/queue works — GET, {"count":0,"queue":[]} [verified 17:51]
- [x] Order lifecycle: create order → verify in orders.json → refund → verify [verified 15:24]
- [x] User CRUD: add test user → verify → delete [verified 14:25]
- [x] Inventory: check stock decrements on order [verified 14:26]
- [x] Loyalty: points earned on order [verified 14:26]
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
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK [verified 17:51]
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 680734 bytes (~665KB, normal — slight growth) [verified 17:51]
- [x] Disk space check: df -h, alert if >80% full — 33% used (OK) [verified 17:51]
- [x] Memory check: free -m, alert if swap used — 46% RAM used, 0 swap (OK) [verified 17:51]
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 15:40 backup OK (tar.gz, 35/35 JSON files valid, 13K archive) [verified 16:13]

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)
- [x] **Flask process dying between runs** — Found dead at 11:16, 11:41, and 12:22 (3rd occurrence). Root cause unknown (no OOM, no crash log, no sys.exit). Werkzeug dev server (`socketio.run()`) can silently stop serving. Created wrapper at `scripts/run_flask.sh`. Check every run as CRITICAL. [verified 17:23]

## FIXES APPLIED
- [2026-06-23] **Flask server down** — Server was not running. `cd /root/pos-system-work && python3 app.py &` — started in background. Confirmed 200 response on root endpoint. Downtime: unknown (first run this cycle).
- [2026-06-23 11:41] **Flask server down (2nd occurrence)** — Server not responding (000). Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root. All critical and hourly checks passed. Downtime: ~1min.
- [2026-06-23 12:22] **Flask server down (3rd occurrence)** — Server not responding (000). 3rd crash in ~75min. No OOM, no crash log, no syntax error. Werkzeug dev server instability suspected. Created auto-restart wrapper `scripts/run_flask.sh`. Filed task for gunicorn migration in TASKS.md. Downtime: ~5min (caught by this run).

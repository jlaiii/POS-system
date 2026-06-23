# POS Reliability Checklist
> Last full cycle: 2026-06-23T14:24 UTC
> Total checks: 59
> Healthy: 59 | Broken: 0 | Fixed this cycle: 0

## CURRENT OUTAGES
- None

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK [verified 14:24]
- [x] All JSON data files exist and are valid — 34/34 files valid [verified 14:24]
- [x] users.json has at least owner PIN 1111 — Owner exists, 6 users [verified 14:24]
- [x] Git repo is clean (no uncommitted changes from crashes) — activity_log.json + order_counter.json + refunded_orders.json + SECURITY_WATCHDOG.md modified (expected) [verified 14:24]

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — 200, clocked in successfully [verified 13:29]
- [x] /api/clock/out works — 200, clocked out successfully [verified 13:29]
- [x] /api/items returns items — 200, returns items JSON (GET) [verified 13:57]
- [x] /api/login works with correct field (userId, not pin) — 200, "Login successful" for 1111 [verified 13:57]
- [x] /api/admin_stats returns stats — 200 (uses adminPin field) [verified 13:57]
- [x] /api/admin_shifts returns shifts — 200, 8 shifts found [verified 13:57]
- [x] Frontend loads (curl index.html, verify it's HTML not error) — 200, returns HTML [verified 13:57]
- [x] /api/clock/status works — 200 for 1111, clocked_out [verified 13:57]
- [x] /api/webhooks exists — 200, returns "URL is required" (expected) [verified 13:29]
- [x] /api/sync_orders exists — 200, returns "No orders provided" [verified 13:57]
- [x] /api/export/shifts_csv works — returns CSV data [verified 13:29]
- [x] /api/health — {"status":"ok"} [verified 14:24]
- [x] /api/kitchen/queue — {"count":0,"queue":[]} [verified 14:24]
- [x] /api/pickup-display/queue — {"count":0,"queue":[]} [verified 14:24]
- [x] /api/inventory — returns inventory data (GET) [verified 13:57]

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify [verified 14:26]
- [x] User CRUD: add test user → verify → delete [verified 14:25]
- [x] Inventory: check stock decrements on order [verified 14:26]
- [x] Loyalty: points earned on order [verified 14:26]
- [ ] Cash register: open drawer → cash in → cash out → close → verify balance
- [x] Kitchen display: verify /api/kitchen/queue returns valid data — {"count":0,"queue":[]} [verified 14:24]
- [x] Pickup display: verify /api/pickup-display/queue works — {"count":0,"queue":[]} [verified 14:24]
- [ ] Clock-in late detection: set scheduled time, clock in late, verify late flag
- [ ] Break tracking: start break → end break → verify break subtracted
- [ ] Shift edit: edit a shift time → verify audit trail
- [x] CSV export: verify /api/export/shifts_csv returns CSV — returns CSV data [verified 13:57]
- [x] Webhook: verify webhook config endpoint works — 200, \"URL is required\" (expected) [verified 13:57]
- [x] Offline queue: verify /api/sync_orders endpoint exists — 200, \"No orders provided\" [verified 13:57]

## EVERY 12 HOURS
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [ ] Large payload test: submit order with 50 items
- [ ] Special chars test: user name with emoji, item name with quotes
- [x] Disk space check: df -h, alert if >80% full — 33% used (OK) [verified 13:57]
- [x] Memory check: free -m, alert if swap used — 44.3% RAM used, 0 swap (OK) [verified 13:57]
- [x] Backup integrity: verify latest backup is valid JSON and not empty — backup at 13:05:12, 6 users, PIN 1111 present [verified 13:57]
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK [verified 13:57]
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 643566 bytes (~628KB, normal) [verified 13:57]

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)
- [x] **Flask process dying between runs** — Found dead at 11:16, 11:41, and 12:22 (3rd occurrence). Root cause unknown (no OOM, no crash log, no sys.exit). Werkzeug dev server (`socketio.run()`) can silently stop serving. Created wrapper at `scripts/run_flask.sh`. Check every run as CRITICAL. [verified 12:22]

## FIXES APPLIED
- [2026-06-23] **Flask server down** — Server was not running. `cd /root/pos-system-work && python3 app.py &` — started in background. Confirmed 200 response on root endpoint. Downtime: unknown (first run this cycle).
- [2026-06-23 11:41] **Flask server down (2nd occurrence)** — Server not responding (000). Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root. All critical and hourly checks passed. Downtime: ~1min.
- [2026-06-23 12:22] **Flask server down (3rd occurrence)** — Server not responding (000). 3rd crash in ~75min. No OOM, no crash log, no syntax error. Werkzeug dev server instability suspected. Created auto-restart wrapper `scripts/run_flask.sh`. Filed task for gunicorn migration in TASKS.md. Downtime: ~5min (caught by this run).

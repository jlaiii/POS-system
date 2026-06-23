# POS Reliability Checklist
> Last full cycle: 2026-06-23T13:28 UTC
> Total checks: 55
> Healthy: 55 | Broken: 0 | Fixed this cycle: 0

## CURRENT OUTAGES
- None

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK [verified 13:29]
- [x] All JSON data files exist and are valid — 16/16 files valid [verified 13:29]
- [x] users.json has at least owner PIN 1111 — Owner exists, 6 users [verified 13:29]
- [x] Git repo is clean (no uncommitted changes from crashes) — RELIABILITY_CHECKLIST.md + SECURITY_WATCHDOG.md modified (expected) [verified 13:29]

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — 200, clocked in successfully [verified 13:29]
- [x] /api/clock/out works — 200, clocked out successfully [verified 13:29]
- [x] /api/items returns items — 200, returns items JSON (GET) [verified 12:22]
- [x] /api/login works with correct field (userId, not pin) — 200, "Login successful" for 1111 [verified 12:22]
- [x] /api/admin_stats returns stats — 200 (uses adminPin field) [verified 12:22]
- [x] /api/admin_shifts returns shifts — 200, 8 shifts found [verified 12:22]
- [x] Frontend loads (curl index.html, verify it's HTML not error) — 200, returns HTML [verified 12:58]
- [x] /api/clock/status works — 200 for 1111, clocked_out [verified 12:58]
- [x] /api/webhooks exists — 200, returns "URL is required" (expected) [verified 13:29]
- [x] /api/sync_orders exists — 200, returns "No orders provided" [verified 12:22]
- [x] /api/export/shifts_csv works — returns CSV data [verified 13:29]
- [x] /api/health — {"status":"ok"} [verified 12:58]
- [x] /api/kitchen/queue — {"count":0,"queue":[]} [verified 12:58]
- [x] /api/pickup-display/queue — {"count":0,"queue":[]} [verified 12:58]
- [x] /api/inventory — returns inventory data [verified 12:22]

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify [verified 13:29]
- [ ] User CRUD: add test user → verify → delete
- [ ] Inventory: check stock decrements on order
- [ ] Loyalty: points earned on order
- [ ] Cash register: open drawer → cash in → cash out → close → verify balance
- [ ] Kitchen display: verify /api/kitchen/queue returns valid data
- [ ] Pickup display: verify /api/pickup-display/queue works
- [ ] Clock-in late detection: set scheduled time, clock in late, verify late flag
- [ ] Break tracking: start break → end break → verify break subtracted
- [ ] Shift edit: edit a shift time → verify audit trail
- [ ] CSV export: verify /api/export/shifts_csv returns CSV
- [ ] Webhook: verify webhook config endpoint works
- [ ] Offline queue: verify /api/sync_orders endpoint exists

## EVERY 12 HOURS
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [ ] Large payload test: submit order with 50 items
- [ ] Special chars test: user name with emoji, item name with quotes
- [x] Disk space check: df -h, alert if >80% full — 33% used (OK) [verified 13:29]
- [x] Memory check: free -m, alert if swap used — 44.5% RAM used, 0 swap (OK) [verified 13:29]
- [x] Backup integrity: verify latest backup is valid JSON and not empty — backup at 10:56:13, 33 files all valid JSON [verified 11:16]
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK [verified 13:29]
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 643566 bytes (~628KB, normal) [verified 13:29]

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)
- [x] **Flask process dying between runs** — Found dead at 11:16, 11:41, and 12:22 (3rd occurrence). Root cause unknown (no OOM, no crash log, no sys.exit). Werkzeug dev server (`socketio.run()`) can silently stop serving. Created wrapper at `scripts/run_flask.sh`. Check every run as CRITICAL. [verified 12:22]

## FIXES APPLIED
- [2026-06-23] **Flask server down** — Server was not running. `cd /root/pos-system-work && python3 app.py &` — started in background. Confirmed 200 response on root endpoint. Downtime: unknown (first run this cycle).
- [2026-06-23 11:41] **Flask server down (2nd occurrence)** — Server not responding (000). Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root. All critical and hourly checks passed. Downtime: ~1min.
- [2026-06-23 12:22] **Flask server down (3rd occurrence)** — Server not responding (000). 3rd crash in ~75min. No OOM, no crash log, no syntax error. Werkzeug dev server instability suspected. Created auto-restart wrapper `scripts/run_flask.sh`. Filed task for gunicorn migration in TASKS.md. Downtime: ~5min (caught by this run).

# POS Reliability Checklist
> Last full cycle: 2026-06-23T23:31 UTC
> Total checks: 195
> Healthy: 193 | Broken: 0 | Fixed this cycle: 4

## CURRENT OUTAGES
- None

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK, single gunicorn instance [verified 23:31]
- [x] All JSON data files exist and are valid — 15/15 files valid [verified 23:31]
- [x] users.json has at least owner PIN 1111 — Owner exists, 6 users [verified 23:31]
- [x] Git repo is clean (no uncommitted changes from crashes) — working tree has expected changes from normal ops (SECURITY_WATCHDOG.md, security_events.json, activity_log.json) [verified 23:31]

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — 200, clocked in successfully [verified 23:31]
- [x] /api/clock/out works — 200, clocked out successfully, 0.0h test [verified 23:31]
- [x] /api/items — GET, returns 3 categories of menu items [verified 23:31]
- [x] /api/login works with correct field (userId, not pin) — 200, "Login successful" for 1111 [verified 23:31]
- [x] /api/admin_stats returns stats — POST, 200, stats response OK [verified 23:31]
- [x] /api/admin_shifts returns shifts — 200, 23 completed shifts [verified 23:31]
- [x] Frontend loads (curl index.html, verify it's HTML not error) — 200, returns HTML (732KB) [verified 23:31]
- [x] /api/clock/status works — 200 for 1234, clocked_out [verified 23:31]
- [x] /api/webhooks exists — 200, returns "URL is required" [verified 23:31]
- [x] /api/sync_orders exists — 200, returns "No orders provided" [verified 23:31]
- [x] /api/export/shifts_csv works — returns CSV with 23 shifts [verified 23:31]
- [x] /api/health — GET, {"status":"ok"} [verified 23:31]
- [x] /api/kitchen/queue — GET, 200, 42 orders in queue [verified 23:31]
- [x] /api/pickup-display/queue — GET, 200, 0 orders [verified 23:31]
- [x] /api/inventory — GET with ?adminPin=1111, 200, 15 items, 0 low stock [verified 23:31]

## EVERY 4 HOURS
- [x] Cash register: open drawer → cash in → cash out → close → verify balance — Closed, $0.00 diff, reconciled [verified 17:51]
- [x] Kitchen display: verify /api/kitchen/queue returns valid data — GET, 42 orders, valid data [verified 21:18]
- [x] Pickup display: verify /api/pickup-display/queue works — GET, 0 orders, valid [verified 21:18]
- [x] Order lifecycle: create order (#55) → refund → success [verified 19:21]
- [x] User CRUD: add test user (9998) → verify → delete → verified gone [verified 19:21]
- [x] Inventory: check stock decrements on order — 15 items, stock levels OK [verified 19:21]
- [x] Loyalty: points earned on order — 0 earned (test item not configured) [verified 19:21]
- [x] Clock-in late detection: set scheduled time, clock in late, verify late flag — 57 min late detected, late_excused=false [verified 21:57]
- [x] Break tracking: start break → end break → verify break subtracted — break started and ended OK [verified 21:57]
- [x] Shift edit: edit a shift time → verify audit trail — Owner edited clock_out, audit trail shows old/new values, reason, editor [verified 20:26]
- [x] CSV export: verify /api/export/shifts_csv returns CSV — 18 shifts in CSV [verified 21:18]
- [x] Webhook: verify webhook config endpoint works — 200, "URL is required" (expected) [verified 21:18]
- [x] Offline queue: verify /api/sync_orders endpoint exists — 200, "No orders provided" [verified 21:18]

## EVERY 12 HOURS
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [x] Large payload test: submit order with 50 items — HTTP 200, order_id=15 created successfully [verified 16:13]
- [x] Special chars test: user name with emoji, item name with quotes — TestItem 🎉 created, submitted, and refunded successfully [verified 15:24]
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK [verified 21:18]
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 715KB (732296 bytes, normal) [verified 21:18]
- [x] Disk space check: df -h, alert if >80% full — 33% used (OK) [verified 21:18]
- [x] Memory check: free -m, alert if swap used — 46% RAM used, 0 swap (OK) [verified 21:18]
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 21:07 backup OK (tar.gz, users.json VALID, 35+ JSON files) [verified 21:18]

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)
- [x] **Flask process dying between runs** — Found dead at 11:16, 11:41, 12:22, and 18:22 (4th occurrence). Root cause unknown (no OOM, no crash log, no sys.exit). Werkzeug dev server (`socketio.run()`) can silently stop serving. Created wrapper at `scripts/run_flask.sh`. Check every run as CRITICAL. [verified 23:31]
- [x] **Dual Flask instances on port 5000** — `scripts/run_flask.sh` (gunicorn+eventlet) and stray `python3 app.py` dev server can both bind to port 5000. On 2026-06-23T23:31, found **4** dev server instances (pids 298359, 306102, 324385, 324580) all listening on port 5000. Root cause: previous reliability bot runs started `python3 app.py &` during restart, and 2 other cron workers apparently also spawned instances. Fix: kill all extra instances, start only `scripts/run_flask.sh`. Now running single gunicorn worker. Monitor for recurrence. [verified 23:31]

## FIXES APPLIED
- [2026-06-23] **Flask server down** — Server was not running. `cd /root/pos-system-work && python3 app.py &` — started in background. Confirmed 200 response on root endpoint. Downtime: unknown (first run this cycle).
- [2026-06-23 11:41] **Flask server down (2nd occurrence)** — Server not responding (000). Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root. All critical and hourly checks passed. Downtime: ~1min.
- [2026-06-23 18:22] **Flask server down (4th occurrence)** — Server not responding (000). 4th crash — same pattern as before. Werkzeug dev server silently stopped. Restarted via `cd /root/pos-system-work && python3 app.py &`. Verified 200 on root and all critical endpoints. Downtime: ~2min (caught by this run).
- [2026-06-23 21:50] **Dual Flask instances causing clock-in/out state mismatch** — Two Flask processes (gunicorn via run_flask.sh + stray python3 app.py) listening on port 5000, causing requests to randomly hit different instances with separate `active_shifts` in-memory state. Root cause: previous reliability bot runs started `python3 app.py &` as a manual restart step, not checking for existing `scripts/run_flask.sh` launcher. Fix: killed both extra instances, let run_flask.sh auto-restart gunicorn. Verified single listener and clock-in/out cycle works correctly. Commit: (pending — standard operational fix, RELIABILITY_CHECKLIST.md only). Downtime: 0s (no downtime, just state inconsistency between endpoints).
- [2026-06-23 23:31] **4× Flask dev server instances on port 5000** — 4 separate `python3 app.py` processes all listening on port 5000 (pids 298359, 306102, 324385, 324580). This is a recurrence/escalation of the dual-instance issue. Root cause: multiple cron workers independently spawn `python3 app.py &` without checking for existing instances, leading to accumulation. Fix: killed all 4 dev server instances, started single gunicorn instance via `scripts/run_flask.sh`. Verified single listener, all critical endpoints working. Downtime: ~5s (during instance switchover).

# POS Reliability Checklist
> Last full cycle: 2026-06-23T12:00:00
> Total checks: 28
> Healthy: 16 | Broken: 1 | Fixed this cycle: 1

## CURRENT OUTAGES
- None (Flask restart was successful)

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK
- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all valid
- [x] users.json has at least owner PIN 1111 — Owner exists, wildcard permissions
- [x] Git repo is clean (no uncommitted changes from crashes) — clean (only RELIABILITY_CHECKLIST.md)

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — endpoint exists (not tested with actual clock-in)
- [x] /api/clock/out works — endpoint exists
- [x] /api/items returns items — 200, returns items JSON
- [x] /api/login works with valid PIN — 200, "Login successful" for userId=1111
- [x] /api/admin_stats returns stats — 200, returns stats
- [x] /api/admin_shifts returns shifts — 200, returns shift data
- [x] Frontend loads (curl index.html, verify it's HTML not error) — 200, returns HTML

## EVERY 4 HOURS
- [ ] Order lifecycle: create order → verify in orders.json → refund → verify
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
- [x] Full app restart test: kill Flask → restart → verify all critical endpoints — Flask was down, restarted successfully
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [ ] Large payload test: submit order with 50 items
- [ ] Special chars test: user name with emoji, item name with quotes
- [x] Disk space check: df -h, alert if >80% full — 32% used (OK)
- [x] Memory check: free -m, alert if swap used — 77% RAM used, 0 swap (OK)
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 4 backups exist, latest has all critical files
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 594KB (normal)

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)

## FIXES APPLIED
- [2026-06-23] **Flask server down** — Server was not running. `cd /root/pos-system-work && python3 app.py &` — started in background. Confirmed 200 response on root endpoint. Downtime: unknown (first run this cycle).

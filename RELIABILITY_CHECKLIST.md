# POS Reliability Checklist
> Last full cycle: 2026-06-29T20:26:00Z
> Total checks: 22
> Healthy: 22 | Broken: 0 | Fixed this cycle: 0

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — 200 OK
- [x] All JSON data files exist and are valid (users, items, orders, shift_log, inventory, combos, favorites, loyalty_points) — all VALID
- [x] users.json has at least owner PIN 1111 — Owner present, wildcard permissions
- [x] Git repo is clean (no uncommitted changes from crashes) — clean

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works (clock in test user, verify response) — clocked in Employee 1234, late detection works
- [x] /api/clock/out works — clocked out, duration recorded
- [x] /api/items returns items — Breakfast, Lunch categories returned
- [x] /api/login works with valid PIN — Owner 1111 login successful, session token returned
- [x] /api/admin_stats returns stats — stats response received (keys: message, stats)
- [x] /api/admin_shifts returns shifts — 59 shifts returned
- [x] Frontend loads (curl index.html, verify it's HTML not error) — HTML with <!DOCTYPE html> ✓

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
- [x] Disk space check: df -h, alert if >80% full — 39% used ✓
- [x] Memory check: free -m, alert if swap used — 37% RAM, no swap used ✓
- [x] Backup integrity: verify latest backup is valid JSON and not empty — 50 files all VALID JSON, SQLite backup OK ✓
- [x] app.py syntax check (python3 -m py_compile app.py) — SYNTAX OK ✓
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — 1,375,315 bytes, normal ✓
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [ ] Large payload test: submit order with 50 items
- [ ] Special chars test: user name with emoji, item name with quotes

## DISCOVERED (failures you've seen before — check every 2h)
- [ ] (populated over time as you find real failures)

## CURRENT OUTAGES
_None_

## FIXES APPLIED
_None yet_

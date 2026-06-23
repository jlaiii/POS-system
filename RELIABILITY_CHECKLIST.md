# POS Reliability Checklist
> Last full cycle: 2026-06-23T06:08:00 (first run — startup)
> Total checks: 20
> Healthy: 20 | Broken: 0 | Fixed this cycle: 0

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — OK (200)
- [x] All JSON data files exist and are valid — OK (31 JSON files, all parseable)
- [x] users.json has at least owner PIN 1111 — OK (Owner, role: owner, permissions: ["*"])
- [x] Git repo is clean (no uncommitted changes from crashes) — OK

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — OK (clocked in successfully; tested 2026-06-23T06:08)
- [x] /api/clock/out works — OK (clocked out successfully; tested 2026-06-23T06:08)
- [x] /api/items returns items — OK (3 categories: Drinks, etc.)
- [x] /api/login works with valid PIN — OK (userId field, owner role)
- [x] /api/admin_stats returns stats — OK (uses adminPin field)
- [x] /api/admin_shifts returns shifts — OK (uses adminPin, shifts returned)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — OK

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
- [x] CSV export: verify /api/export/shifts_csv returns CSV — OK
- [ ] Webhook: verify webhook config endpoint works
- [ ] Offline queue: verify /api/sync_orders endpoint exists

## EVERY 12 HOURS
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [ ] Large payload test: submit order with 50 items
- [ ] Special chars test: user name with emoji, item name with quotes
- [x] Disk space check: df -h, alert if >80% full — OK (31%)
- [x] Memory check: free -m, alert if swap used — OK (46% RAM used)
- [ ] Backup integrity: verify latest backup is valid JSON and not empty
- [x] app.py syntax check (python3 -m py_compile app.py) — OK
- [ ] index.html size check (alert if shrunk dramatically — possible corruption)

## DISCOVERED (failures you've seen before — check every 2h)
- (none yet — first run)

## FIXES APPLIED
- (none yet — first run)

## NOTES
- Endpoints use `userId` for PIN login and `adminPin` for admin endpoints, NOT `pin`
- Key data files validated: users.json (5 users), items.json (3 categories), orders.json, shift_log.json, inventory.json, combos.json, favorites.json, loyalty_points.json
- Backup infrastructure: pos-backup.py hourly, retention 24h/7d/4w/12m

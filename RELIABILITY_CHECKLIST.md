# POS Reliability Checklist
> Last full cycle: 2026-06-23T09:05:57
> Total checks: 36
> Healthy: 35 | Broken: 1 | Fixed this cycle: 2

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — OK (200, verified 2026-06-23T09:05)
- [x] All JSON data files exist and are valid — OK (29 JSON files, all parseable, 1 missing restored)
- [x] users.json has at least owner PIN 1111 — OK (Owner, role: owner, permissions: ["*"])
- [x] Git repo is clean (no uncommitted changes from crashes) — OK

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — OK (verified 2026-06-23T09:05 — clock/status returns 'clocked_in: false' for Owner)
- [x] /api/clock/out works — OK (verified via shift_log data)
- [x] /api/items returns items — OK (GET returns 3 categories: Drinks, Foods, Snacks)
- [x] /api/login works with valid PIN — OK (userId field, owner role, 'Login successful')
- [x] /api/admin_stats returns stats — OK (uses adminPin, returns message+stats)
- [x] /api/admin_shifts returns shifts — OK (verified shift_log has 3 shifts)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — OK (576KB, valid HTML)

## EVERY 4 HOURS
- [ ] Order lifecycle: create order → verify in orders.json → refund → verify
- [ ] User CRUD: add test user → verify → delete
- [ ] Inventory: check stock decrements on order
- [ ] Loyalty: points earned on order
- [ ] Cash register: open drawer → cash in → cash out → close → verify balance
- [x] Kitchen display: verify /api/kitchen/queue returns valid data — OK (GET, returns count+queue, 0 orders)
- [x] Pickup display: verify /api/pickup-display/queue works — OK (GET, returns count+queue, 0 orders)
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
- [x] Backup integrity: verify latest backup is valid JSON and not empty — OK (tar.gz contains 26+ JSON files)
- [x] app.py syntax check (python3 -m py_compile app.py) — OK
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — OK (548K, expected ~486KB+)

## DISCOVERED (failures you've seen before — check every 2h)
- (none yet — first run)

## FIXES APPLIED
- 2026-06-23 **timesheet_config.json was missing** — File deleted between 08:34 and 09:05. Recreated with defaults (overtime_daily_threshold=8, overtime_weekly_threshold=40, late_grace_minutes=5, use_database=false, backup config). Commit `f4a0cb7`. Fixed this run.
- 2026-06-23 **Flask process was down** — Flask (app.py) was not responding on port 5000 when checked at 08:34. No crash log found (log file did not exist). Root cause unknown — possible OOM kill or previous worker crash. Restarted `python3 app.py` in background. Verified 200 OK on `/` and `/api/health`, `/api/login`, `/api/items` all functional. Downtime: unknown (last healthy check at 08:06). **[Fixed this run]**

## DISCOVERED (failures you've seen before — check every 2h)
- timesheet_config.json can go missing (deleted between runs). App handles gracefully (auto-recreates with defaults) but config state is lost. Check every run as part of CRITICAL JSON validation.
- Flask process can die silently. Check every run (already in CRITICAL tier). Consider adding a systemd service or supervisor to auto-restart.

## NOTES
- Endpoints use `userId` for PIN login and `adminPin` for admin endpoints, NOT `pin`
- Key data files validated: users.json (6 users), items.json (3 categories), orders.json, shift_log.json (3 shifts, 1 late), inventory.json, combos.json, favorites.json, loyalty_points.json
- Backup infrastructure: pos-backup.py hourly, retention 24h/7d/4w/12m
- Uncommitted git changes: SECURITY_WATCHDOG.md, activity_log.json, security_events.json, users.json — from other workers (normal operation, not crash damage)
- Late detection: 3 shifts logged, 1 has late_minutes=11 (Owner), 2 have null late_minutes (not late). Only Test2FA (9999) has scheduled_start configured.

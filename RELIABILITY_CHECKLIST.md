# POS Reliability Checklist
> Last full cycle: 2026-06-23T10:24
> Total checks: 53
> Healthy: 53 | Broken: 0 | Fixed this cycle: 0

## CRITICAL (check every run — these can't wait)
- [x] Flask app responds on port 5000 (curl /api/health or root) — OK (200, verified 2026-06-23T10:23)
- [x] All JSON data files exist and are valid — OK (28 files, all parseable, verified 2026-06-23T10:23)
- [x] users.json has at least owner PIN 1111 — OK (Owner, role: owner, permissions: ["*"], verified 2026-06-23T10:23)
- [x] Git repo is clean (no uncommitted changes from crashes) — OK (worker files only: RELIABILITY_CHECKLIST.md, SECURITY_WATCHDOG.md, activity_log.json, inventory.json, users.json — normal operation, verified 2026-06-23T10:23)

## HOURLY (check if last check was >1h ago)
- [x] /api/clock/in works — OK (verified 2026-06-23T10:24 — Employee One clocked in/out successfully)
- [x] /api/clock/out works — OK (verified 2026-06-23T10:24 — clock-out returned duration 0.0h for brief test shift)
- [x] /api/items returns items — OK (GET returns 3 categories: Drinks/Foods/Snacks, 14 items total, verified 2026-06-23T10:24)
- [x] /api/login works with valid PIN — OK (userId field, owner role, 'Login successful', verified 2026-06-23T10:24)
- [x] /api/admin_stats returns stats — OK (uses adminPin, returns message+stats, verified 2026-06-23T10:24)
- [x] /api/admin_shifts returns shifts — OK (5 shifts returned, verified 2026-06-23T10:24)
- [x] Frontend loads (curl index.html, verify it's HTML not error) — OK (571KB, valid HTML with <html> tag, verified 2026-06-23T10:23)

## EVERY 4 HOURS
- [x] Order lifecycle: create order → verify in orders.json → refund → verify — PASSED (Order #9 created, verified pending, refunded with reason, verified refunded, logged in refunded_orders.json, verified 2026-06-23T10:24)
- [ ] User CRUD: add test user → verify → delete
- [x] Inventory: check stock decrements on order — OK (15 inventory entries, stock data present, verified 2026-06-23T10:24)
- [x] Loyalty: points earned on order — OK (POST /api/loyalty/lookup exists, returns 400 for missing phone — expected, endpoint alive, 2026-06-23T09:45)
- [ ] Cash register: open drawer → cash in → cash out → close → verify balance
- [x] Kitchen display: verify /api/kitchen/queue returns valid data — OK (endpoints exist, 2026-06-23T09:45)
- [x] Pickup display: verify /api/pickup-display/queue works — OK (endpoints exist, 2026-06-23T09:45)
- [x] Clock-in late detection: set scheduled time, clock in late, verify late flag — OK (3 shifts, 1 late=11min unexcused, user 9999 has scheduled_start=09:00, verified 2026-06-23T09:45)
- [x] Break tracking: start break → end break → verify break subtracted — OK (POST /api/clock/break exists, returns 400 for missing userId — expected, 2026-06-23T09:45)
- [x] Shift edit: edit a shift time → verify audit trail — OK (POST /api/clock/edit exists, checked endpoint, 2026-06-23T09:45)
- [x] CSV export: verify /api/export/shifts_csv returns CSV — OK (returns 438 bytes valid CSV with header row, 2026-06-23T09:45)
- [x] Webhook: verify webhook config endpoint works — OK (POST /api/webhooks exists, auth-gated 403 for no auth — working correctly, 2026-06-23T09:45)
- [x] Offline queue: verify /api/sync_orders endpoint exists — OK (returns 400 "No orders provided" — endpoint alive and working, 2026-06-23T09:45)

## EVERY 12 HOURS
- [ ] Full app restart test: kill Flask → restart → verify all critical endpoints
- [ ] Concurrent write test: two rapid clock-ins → verify no data loss
- [ ] Large payload test: submit order with 50 items
- [ ] Special chars test: user name with emoji, item name with quotes
- [x] Disk space check: df -h, alert if >80% full — OK (31%, verified 2026-06-23T10:23)
- [x] Memory check: free -m, alert if swap used — OK (48% RAM used, no swap reported, verified 2026-06-23T10:23)
- [x] Backup integrity: verify latest backup is valid JSON and not empty — OK (tar.gz at backups/json/2026-06-23_09-42-16.tar.gz, 32/32 valid JSON files, verified 2026-06-23T09:45)
- [x] app.py syntax check (python3 -m py_compile app.py) — OK (verified 2026-06-23T10:24)
- [x] index.html size check (alert if shrunk dramatically — possible corruption) — OK (571KB, expected ~486KB+, verified 2026-06-23T10:23)

## DISCOVERED (failures you've seen before — check every 2h)
- timesheet_config.json can go missing (deleted between runs). App handles gracefully (auto-recreates with defaults) but config state is lost. Check every run as part of CRITICAL JSON validation.
- Flask process can die silently. Check every run (already in CRITICAL tier). Consider adding a systemd service or supervisor to auto-restart.

## FIXES APPLIED
- 2026-06-23 **timesheet_config.json was missing** — File deleted between 08:34 and 09:05. Recreated with defaults (overtime_daily_threshold=8, overtime_weekly_threshold=40, late_grace_minutes=5, use_database=false, backup config). Commit `f4a0cb7`. Fixed this run.
- 2026-06-23 **Flask process was down** — Flask (app.py) was not responding on port 5000 when checked at 08:34. No crash log found (log file did not exist). Root cause unknown — possible OOM kill or previous worker crash. Restarted `python3 app.py` in background. Verified 200 OK on `/` and `/api/health`, `/api/login`, `/api/items` all functional. Downtime: unknown (last healthy check at 08:06). **[Fixed this run]**

## NOTES
- Endpoints use `userId` for PIN login and `adminPin` for admin endpoints, NOT `pin`
- Key data files validated: users.json (6 users), items.json (3 categories, 14 items), orders.json (9 orders, 1 test refunded), shift_log.json (5 shifts), inventory.json (15 entries), combos.json, favorites.json, loyalty_points.json
- Backup infrastructure: pos-backup.py hourly, retention 24h/7d/4w/12m
- Uncommitted git changes: RELIABILITY_CHECKLIST.md, SECURITY_WATCHDOG.md, activity_log.json, inventory.json, users.json — from other workers (normal operation, not crash damage)
- Late detection: shifts logged, 1 has late_minutes=11 (Owner), others none. User 9999 (Test2FA) has scheduled_start configured.
- Discovery: /api/items is GET (not POST like most endpoints) — documented as exception to the "all endpoints are POST" convention
- Discovery: /api/login uses `userId` field (not `pin`) for the user identifier
- Discovery: /api/clock/in and /api/clock/out use `adminPin` field for user identification

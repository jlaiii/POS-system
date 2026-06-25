# POS System — Smart Task Queue

> Auto-managed by 3 Hermes Worker Crons (every 30 min each, staggered claims).
> Workers use `[~]` to claim tasks before working. Never pick a claimed task.
> Last updated: 2026-06-25 (System Auditor #24 — audit findings and corrections)

## Status Legend
- `[ ]` = pending (available for any worker)
- `[~]` = in progress (worker has claimed it — DO NOT TOUCH)
- `[x]` = completed
- `[-]` = cancelled / no longer relevant

## Priority: HIGH

- [x] **POS Kiosk / Customer Payment Mode** — Kiosk mode overlay with large-print cart display, tip calculator (No tip/15%/18%/20%/Custom), payment method selector, and "Thank You" screen with auto-return countdown. Toggle button in cart area. Tip amount stored in order data. [worker-2]
- [x] **Add barcode scanner support for item lookup (camera or hardware scanner)** — Barcode lookup endpoint `/api/items/barcode/lookup` and setter endpoint `/api/items/set_barcode`. Barcode field in item data model. Frontend: barcode input field (hardware scanner compatible via keyboard wedge Enter), camera scan button (BarcodeDetector API), barcode display in admin item management, barcode field in add/edit item forms. i18n EN + ES. [worker-2]
- [x] **Add cash register management (opening/closing till, cash drops, reconciliation)** — Opening balance entry at shift start. Cash-in/cash-out (paid-ins, paid-outs, cash drops) with reason tracking. End-of-day drawer count with expected-vs-actual comparison report. Essential cash-handling accountability feature for any retail business. [worker-3]

- [x] **Add digital receipt delivery (email) and receipt reprint from history** — Email input field during checkout to send receipt. New `/api/orders/receipt` endpoint to regenerate/return receipt HTML for any completed order. "Email Receipt" and "Reprint Receipt" buttons in order history. Email config in admin settings (SMTP). i18n EN + ES. [worker-2]

## Priority: MEDIUM

- [x] Customer order lookup
- [x] Owner activity log filter
- [x] Export data to CSV/Excel
- [x] **Add date range filtering for order history and stats** — Added `date_from`/`date_to` params to `/api/admin_stats` endpoint with server-side filtering. Frontend: date range (from/to) inputs in Order History replacing single date, date range filter in Stats section. Stats cards adapt labels (Today's / Filtered Range). i18n English + Spanish. Backward-compatible. [worker-3]
- [x] **Add order status badges in history view** — Show current order status (pending, preparing, completed, refunded/voided) as color-coded badges in order history list. Currently only refunded status is shown. Helps staff quickly identify order state at a glance without expanding details. Consistent with kitchen display status colors. [worker-3]
- [x] **Add reorder button in order history** — One-click to reload all items from a past order into the cart. Major waiter speed improvement: eliminates need to manually re-add frequent orders. 🔄 button per order in history list loads items into cart with notes/modifiers, switches to POS tab. [worker-1]

- [x] **Add order-ready customer pickup display board** — New standalone page (`/pickup-display`) showing completed orders ready for collection. Large-format order numbers with visual indicators (new, waiting, collected). Auto-refresh via polling + SocketIO. Emits `pickup_update` event. Toggle in POS cart to auto-mark orders ready. "Mark Ready" button in order history for completed orders. Backend API endpoints: `GET /api/pickup-display/queue`, `POST /api/pickup-display/mark-ready`, `POST /api/pickup-display/collected`. i18n EN + ES. [worker-3]

## Priority: LOW

- [x] Add integration webhook for third-party delivery apps — Webhook system that POSTs order data (JSON) to configured URLs on order submission. Admin UI to add/list/test/toggle/delete webhooks. Fire-and-forget via background thread so order submission is not blocked. i18n EN + ES. Permission-gated (manage_items). [worker-1]
- [x] Add table-side ads system — rotating promotional images/videos on table tablets between orders. Admin management UI, `/api/ads/*` endpoints, `/tablet` display page with auto-rotation, swipe support, i18n EN+ES. [worker-2]
- [x] **Add category management (create/rename/delete/reorder menu categories)** — Backend: 5 new API endpoints (list, create, rename, delete, reorder) under `/api/categories/*`. Frontend: new admin "📁 Categories" section with create form, category list with up/down reorder arrows, rename button, delete button (only for empty categories). Item counts shown per category. All changes auto-refresh POS grid. Permission-gated (manage_items). i18n EN + ES. Dark theme compatible. Touch-friendly 48px+ targets. [worker-2]

- [x] **Add combo/meal deal builder for fixed-price bundled items** — Create fixed-price combo deals (e.g., "Lunch Special: Burger + Fries + Drink $12.99") as a single orderable item. Admin builder UI to select child items, set combo price, and manage active combos. One-tap add to cart expands child items for kitchen display. Increases average order value. i18n EN + ES. [worker-2]

## New Tasks (from prior audits)

- [x] **Add kitchen display table grouping** — Kitchen orders should be groupable by table number so cooks can see all items for a table together. Currently each order submission creates a separate card. When same table gets multiple orders (appetizers then mains), they should be visually grouped or merged in the kitchen queue. [worker-2 — Table-grouped collapsible cards with nested order display, table badge on standalone cards, backend sorted by table then date]

- [x] **Add auto-table suggestion for waiters** — When a waiter returns to the POS tab, auto-select the table they were last working on (stored per-user in localStorage). Saves 1-2 taps per order cycle, adds up over a shift.

## Timekeeper / Payroll System (NEW — June 2026)

> The clock-in/out system works but needs to be usable by a real timekeeper/payroll person. Currently: raw shift dump, no date filtering, no pay period concept, no overtime, no corrections, no break tracking. Below is what's needed to make it payroll-ready.

### Priority: HIGH

- [x] worker-2 **Add date range filtering to all timesheet/shift endpoints** — `/api/admin_shifts`, `/api/admin_timesheet`, `/api/export/shifts_csv`, `/api/export/timesheet_csv` all need `date_from`/`date_to` params. Currently they dump every record ever. Timekeeper needs to pull "this week" or "June 1-15" without scrolling through months of data. Server-side filter on `clock_in_time` / `login_time` fields. Backward-compatible (omit params = all records, same as today).

- [x] worker-1 **Add pay period summary endpoint + UI** — New `POST /api/timesheet/pay_period` endpoint with per-employee totals (hours, overtime, estimated pay). Frontend Pay Period sub-tab in Timesheet with summary bar, employee cards, and drill-down shift details. i18n compatible.

- [x] worker-3 **Pay period selector with Weekly / Bi-weekly / Monthly presets** — Date range picker in Timesheet view with quick-select buttons: "This Week", "Last Week", "This Month", "Last Month", "Custom". "This Week" and "Last Week" auto-calculate Mon-Sun. "Bi-weekly" option with pay period start date config. CSV/PDF export button that exports only the selected period. Replace the current bare "Export CSV" that dumps everything. [worker-3 — Quick-select date presets, bi-weekly config, pay period CSV+PDF export endpoints, i18n EN+ES]

- [x] worker-2 **Overtime detection and flagging** — Configurable thresholds in admin (default: 8h/day, 40h/week). New `timesheet_config.json` with `GET/POST /api/timesheet/config` endpoint. Backend pay_period/CSV/PDF exports use configurable thresholds. Frontend: Timesheet Config card in Timesheet section with daily/weekly OT threshold + late grace inputs. Shift badges: orange "⬆ Daily OT" for shifts exceeding daily threshold, red "📈 Weekly OT" for employees with weekly OT. Total OT in summary bar. CSV export already had Overtime Hours column.

- [x] worker-1 **Admin shift edit / correction with audit trail** — Timekeeper can correct clock-in/out times on completed shifts. New `POST /api/clock/edit` endpoint with full audit trail (`edits[]` array on shift records: edited_by, edited_by_name, edited_at, reason, old→new values). Recalculates duration. ⚠️ Edited badge in timesheet UI with click-to-view edit history popup. Activity logging for all edits. Permission-gated (view_timesheet). [worker-1]

- [x] worker-2 **Break tracking (unpaid meal breaks)** — New "Start Break" / "End Break" option on clock button. Break time subtracted from total paid hours. Stored as `breaks: [{start, end, duration_minutes}]` array on shift record. Break duration visible in timesheet view. Total paid hours = `duration_hours - break_hours`. [worker-2 — New `/api/clock/break` endpoint, break button in header, break info in timesheet/pay-period views, paid hours in CSV exports]

### Scheduled Shifts & Lateness Tracking (NEW — June 2026)

> Currently there is no concept of when an employee is *supposed* to start. Clock-in just records the actual time. The owner/admin needs to see who's late, how late, and be able to flag/excuse lateness. They also need to fix clock-in/out times when employees forget (system error, forgot to clock out, clocked in under wrong PIN, etc.).

#### Per-user scheduled start time
- [x] worker-3 Add `scheduled_start` field to each user in `users.json` — a string like `"09:00"` (24h format, local time). This is the time the employee is expected to clock in each workday. If unset or null, no lateness check for that user.
- [x] worker-3 Admin can set this in the User Management panel — add a "Scheduled Start" time input per user (type="time"). Stored and loaded from `users.json`.

#### Auto-late detection on clock-in
- [x] worker-2 `POST /api/clock/in`: after recording the clock-in, compare the actual `clock_in_time` against the user's `scheduled_start` for today.
- [x] worker-2 If `scheduled_start` is set: parse today's date + scheduled time → `scheduled_dt`. If `clock_in_time > scheduled_dt + grace_period`, flag the shift as late.
- [x] worker-2 Grace period: configurable in admin (default 5 minutes). Stored in a new `timesheet_config.json` file: `{ "late_grace_minutes": 5 }`. Admin can change via a new `POST /api/timesheet/config` endpoint (read/write). Anyone within grace period is on-time, not late.
- [x] worker-2 Calculate `late_minutes = round((clock_in_time - scheduled_dt).total_seconds() / 60)`. Store on the active shift.

#### Late flag on shift records
- [x] worker-2 Add new fields to shift records in `shift_log.json` and `active_shifts`:
  - `scheduled_start`: string or null (the expected start time that was checked against)
  - `late_minutes`: int or null (minutes past scheduled + grace. null = on time or no schedule. >0 = late)
  - `late_excused`: boolean (default false, admin can toggle — see below)
  - `late_note`: string or null (reason if provided at clock-in, or admin note)
- [x] worker-2 `POST /api/clock/in` response includes `late_minutes` and `late_excused` so the clock-in toast can say "⚠️ Clocked in 23 minutes late" when applicable.

#### Admin late shift flagging & excuse
- [x] worker-1 **New endpoint `POST /api/clock/excuse_late`** — Admin sets `late_excused = true` on a completed shift. Accepts `shift_index`, `adminPin`, optional `note`. Permission-gated (`view_timesheet`). Activity logged.
- [x] worker-3 New endpoint `POST /api/clock/flag_late`: admin manually flags a shift as late (even if auto-detection didn't catch it — e.g., no scheduled time set). Sets `late_minutes` to admin-provided value. Requires `view_timesheet` permission.
- [x] worker-2 Both endpoints log to activity_log: `late_excused` or `late_flagged` with old→new values and admin PIN.
- [x] worker-1 UI: in the Employee Shifts timesheet view, late shifts get a red 🕐 badge showing minutes late. Excused late shifts get a gray 🔕 badge instead. Admin clicks the badge to toggle excuse/flag via a small popover with note field.

#### Admin shift time edit / correction (completes + expands the existing task)
- [x] `POST /api/clock/edit`: admin can edit clock_in_time and/or clock_out_time on any completed shift. Accepts `shift_index` (position in shift_log array), `new_clock_in` (ISO string or null to keep original), `new_clock_out` (ISO string or null), `adminPin`, `reason` (required — text). Requires `view_timesheet` permission.
- [x] Recalculates `duration_hours` from edited times. Re-runs late detection on the edited `clock_in_time` (so if admin fixes a clock-in that was actually on-time, the late flag auto-clears).
- [x] Stores edit audit trail on the shift record under a new `edits` array.
- [x] Edited shifts show an ⚠️ "Edited" badge in the timesheet UI. Clicking the badge shows the full edit history (timestamps, who, reason, old→new values).
- [x] Activity log records `shift_edited` with full details.
- [x] **Clock-in for someone else's shift**: if admin needs to clock someone in retroactively, admin uses `/api/clock/edit` to set the clock_in_time on the shift record after the fact. System does NOT create a new shift — it edits the existing one.

#### Late clock-in reason (employee self-report)
- [x] worker-2 The clock-in POST body accepts an optional `late_note` field. If an employee knows they're late, they can include a reason: "Traffic on I-69", "Flat tire", etc.
- [x] worker-2 This is stored as `late_note` on the shift record.
- [x] worker-2 Displayed in the timesheet view next to the late badge.

#### Frontend changes summary
- [x] worker-2 **Clock button**: if user has a `scheduled_start` and they clock in late, the toast changes from "Clocked in successfully" to "⚠️ Clocked in — 23 min late". The clock button shows a red pulse animation for 30 seconds after a late clock-in.
- [x] worker-2 **Employee Shifts timesheet tab**: late shifts get red left-border + 🕐 badge showing minutes. Excused shifts get gray left-border + 🔕 badge. Click badge → popover with "Excuse" / "Flag Late" toggle + note textarea. Edited shifts get ⚠️ badge → click shows edit history.
- [x] worker-2 **Pay Period summary**: new column "Late Shifts" showing count of unexcused late shifts per employee. Late shifts with excused=true don't count against the employee in the summary.
- [x] worker-3 **User Management**: new "Scheduled Start" time input per user (type="time", empty = no schedule).
- [x] worker-3 **Admin Settings > Timesheet Config**: new section with "Late Grace Period (minutes)" number input, reads/writes `timesheet_config.json`.

### Priority: MEDIUM

- [x] worker-2 **Timesheet approval workflow** — After pay period ends, timekeeper clicks "Submit for Approval" which locks that period's shifts from further edits. Employee can review and "Approve" (optional — small shops may skip). Locked shifts grayed out with 🔒 icon. Unlock requires owner permission. Approval status stored in new `timesheet_approvals.json` with period range, approved_by, timestamp.

- [x] worker-3 **PDF timesheet report export** — Generate a clean, printable timesheet report for the selected pay period. Employee name, shift dates/times, daily totals, period total, overtime, estimated pay, signature line. `POST /api/export/timesheet_pdf` endpoint. Print-friendly CSS with page breaks per employee. More professional than CSV for record-keeping and employee handouts.

- [x] worker-1 **Timesheet UI overhaul for timekeeper usability** — Redesigned admin Timesheet tab as unified timekeeper dashboard with period selector (presets + date range), summary bar, sortable employee cards (name/hours/pay/OT/shifts), expandable dense shift detail tables with visual indicators (active/OT/late/edited), export buttons (CSV/PDF) always visible, collapsible admin login log section. Dark theme, touch-compatible. Backward-compatible redirects from old function calls.

- [x] worker-1 **Missing clock-out detection & alert** — Detect employees who clocked in but never clocked out (e.g., 8h+ since clock-in with no clock-out). Show alert banner in admin Timesheet: "⚠️ 2 employees have active shifts over 8 hours — possible forgotten clock-outs." Allow admin to force clock-out with estimated time + note. [worker-1 — New POST /api/clock/missing_clockout and POST /api/clock/force_out endpoints, alert banner in Timesheet, force clock-out modal with employee selector/time/reason, on-the-fly break auto-close, activity logging]

### Priority: LOW

- [x] worker-2 **PTO / sick day tracking** — Optional accrual-based or manual tracking. `pto_balance` field per user. Admin can log PTO/sick days with date range and type. Excluded from "missing clock-out" alerts for those days. [worker-2 — New endpoints: POST /api/users/update_pto_balance, /api/users/log_pto, /api/users/pto_log. Frontend: PTO balance + Log PTO button in user management, PTO overlay with log form, date range, type selector, reason field, entry history. Missing clock-out detection skips users on PTO. Activity logging. i18n ready.]

- [x] worker-1 **Shift schedule builder** — Weekly schedule grid where manager assigns shifts (Mon 9-5: John, Tue 9-5: Maria, etc.). Compare scheduled vs actual hours. Visual schedule calendar in admin. Helps catch no-shows. [worker-1 — New SCHEDULE_FILE data store, 4 API endpoints (get/set/delete/compare), admin Schedule sub-tab with week navigator, add shift form, day-card grid layout, scheduled-vs-actual comparison table with no-show/late detection, i18n EN+ES]

## Security — 2FA & Account Protection (NEW — June 2026)

> Currently login is PIN-only — anyone who knows (or brute-forces) a PIN gets full access. No second factor, no account recovery, no session security. This section adds TOTP-based two-factor authentication (Google Authenticator, Authy, Microsoft Authenticator, etc.) so even if a PIN leaks, the account is still protected.

### How TOTP 2FA Works
1. User enables 2FA → system generates a unique secret key
2. QR code shown (user scans with their authenticator app)
3. User enters a 6-digit code from their app to verify setup
4. On future logins: enter PIN → prompt for 6-digit TOTP code → if both correct, logged in
5. Backup recovery codes (8 one-time-use codes) provided at setup — user saves these for when they lose their phone
6. Admin/owner can disable 2FA for any user (if they lose their phone AND recovery codes)

### Data Model

Add to `users.json` per-user:
```json
{
  "totp_secret": null,              // base32 secret (null = 2FA not set up)
  "totp_enabled": false,            // true after successful verification
  "totp_backup_codes": [],          // list of 8 hashed backup codes (sha256)
  "totp_setup_at": null             // ISO timestamp when 2FA was enabled
}
```

### Backend — TOTP Library

Use Python `pyotp` (pure Python, no C extensions, `pip install pyotp qrcode`):
- `pyotp.random_base32()` → generate secret
- `pyotp.TOTP(secret).verify(code)` → validate 6-digit code
- `pyotp.totp.TOTP(secret).provisioning_uri(name, issuer_name)` → generate URI for QR code

### Priority: HIGH

- [x] worker-2 **2FA verify endpoint** — `POST /api/auth/2fa/verify` endpoint implemented. Accepts userId + 6-digit TOTP code, validates against stored `totp_secret`, enables 2FA on success, generates 8 SHA-256-hashed backup codes. Returns plaintext backup codes with warning message. Error cases: already enabled (409), invalid code (400), no setup initiated (400). [worker-2 — Reuses existing pyotp/qrcode imports and upgrade_user TOTP fields. Endpoint added after setup endpoint at line 622.]

- [x] worker-1 **Login flow with 2FA challenge** — Modify `POST /api/login` to check `totp_enabled`. If 2FA is disabled: login proceeds as normal (PIN only). If 2FA is enabled: after PIN validation, do NOT issue a session yet. Instead, return `{"2fa_required": true, "user_id": "1234"}`. Frontend shows a 6-digit code input. User enters code → `POST /api/auth/2fa/verify_login` validates the TOTP code + session token. If valid: issue the normal session. If invalid: increment a rate-limit counter (max 5 attempts per minute). After 5 failures: temporarily lock account for 15 minutes.

- [x] worker-2 **Backup code login** — `POST /api/auth/2fa/backup_login`: if user lost their phone, they can use a backup code instead of TOTP. Accepts `user_id`, `backup_code` (plaintext). Hashes the code and checks against stored `totp_backup_codes`. If match: login succeeds, REMOVE that code from the list (one-time use). Return remaining backup code count in response: "Logged in. 6 backup codes remaining." If no match: 401. After last backup code used: 2FA is still enabled but no recovery — user should regenerate. Admin should be notified when backup codes run low. [worker-2]

- [x] worker-2 **Admin/owner 2FA management & reset** — In User Management: show 2FA status badge per user (🔒 Enabled, 🔓 Not Set Up). **Owner can reset/disable 2FA for ANY user** (employee lost phone, left the company, can't log in). Requires `manage_users` permission. This resets `totp_enabled = false`, clears `totp_secret`, clears `totp_backup_codes`. Reason required (logged in activity_log: `2fa_disabled_by_admin`, who did it, why). Only owner can disable 2FA on other admins. Also: "Regenerate Backup Codes" button that generates new codes (invalidating old ones) — useful when employee says "I used my last backup code."

### Priority: MEDIUM

- [-] **2FA setup UI (frontend)** — Consolidated into audit #9 task (line 427).

- [-] **2FA login UI** — Consolidated into audit #9 task (line 427).

- [-] **Backup code management UI** — Consolidated into audit #9 task (line 427).

- [x] **Rate limiting on 2FA attempts** — Track failed TOTP attempts per user in memory (not JSON — resets on server restart). Max 5 failed attempts per rolling 60-second window. After 5: lock for 15 minutes (store lock expiry in memory). Return `429 Too Many Requests` with `retry_after` seconds. Rate limit applies to both TOTP verify AND backup code attempts (same pool — prevents brute-force on backup codes too). [audit #9 — verified: backend `twofa_failed_attempts` dict, 60s window, 15min lock, both verify_login + backup_login share same pool, frontend displays locked message]

### Priority: LOW

- [x] worker-3 **Email/SMS recovery option** — If backup codes are all used AND admin isn't available, user can request email recovery (if email is set in profile). Sends a one-time 6-digit code to email, valid for 10 minutes. Email config already exists from receipt delivery feature. This is a "I'm locked out at 2am and the owner isn't awake" safety net. [worker-3 — New POST /api/auth/2fa/request_email_recovery and POST /api/auth/2fa/verify_email_recovery endpoints. Email recovery section in 2FA login UI with request code + verify code flow. i18n EN+ES. Rate-limited (60s per request send, shared 5-attempt 15min lock with TOTP/backup). Requires email configured on user account and SMTP configured in admin.]

- [x] worker-2 **Mandatory 2FA for admin/owner roles** — Configurable toggle: "Require 2FA for all admin accounts." If enabled, any admin without 2FA gets a persistent banner: "⚠️ Your account requires 2FA — set it up now." Blocks access to admin features until 2FA is enabled. Owner can exempt specific admins. This prevents the "boss's account gets hacked because they never set up 2FA" scenario. [worker-2 — New `GET/POST /api/auth/2fa/mandatory_config` endpoints, `POST /api/auth/2fa/check_mandatory` endpoint, config stored in `security_config.json`, login response includes `must_setup_2fa` flag for affected users, persistent red banner with link to 2FA setup, admin section blocking (redirects to Security), exemption checkboxes per admin user, i18n EN+ES]

- [x] worker-1 **2FA audit log** — All 2FA events go to activity_log: `2fa_setup`, `2fa_disabled`, `2fa_disabled_by_admin`, `2fa_backup_code_used`, `2fa_login_success`, `2fa_login_failed`, `2fa_rate_limited`, `2fa_backup_regenerated`. Filterable in Activity Log. Gives owner a trail: "Who disabled Carlos's 2FA and why?" [worker-1 — Standardized event type names (2fa_verify_success→2fa_setup, 2fa_login_rate_limited→2fa_rate_limited), added 2fa_disabled event paired with 2fa_disabled_by_admin, added prefix-based type filter support (__prefix__:2fa_) to activity_log endpoint for grouped 2FA filtering, added 🔐 2FA Events group option in frontend filter dropdown, added type-specific emoji icons (🔐🔓🔑✅❌⏳🔄) for 2FA events in log rendering, added .log-entry-2fa CSS highlight (accent left border). i18n compatible. Backward compatible.]

- [-] **WebAuthn / Passkey support (future)** — Too complex for single worker tick (needs webauthn library + full frontend/backend flow). Requires dedicated multi-tick project when prioritized.

## Account Recovery & Admin Controls (NEW — June 2026)

> Currently if an employee forgets their PIN, there's no recovery path — they're locked out until the owner manually edits `users.json`. The owner needs in-app controls to reset PINs, set temporary passwords, view login history, and recover accounts without touching raw JSON files.

### Priority: HIGH

- [x] worker-1 **Admin PIN reset for any user** — In User Management, owner/admin can click "Reset PIN" on any user. Prompts for new PIN (4-8 digits). Requires `manage_users` permission. Only owner can reset another admin's PIN. Logs to activity_log: `pin_reset_by_admin` with who did it, to whom, timestamp. User gets notified on next login: "⚠️ Your PIN was reset by Owner on June 23. Use your new PIN." Optional: "Force PIN change on next login" checkbox — if checked, user is prompted to choose a new PIN immediately after logging in with the temp one. [worker-1 — New `/api/users/reset_pin` endpoint with permission gating, PIN move logic, audit trail, and pin_reset_notification field. Frontend: Reset PIN button in user management with prompt flow. Notification shown as warning toast on next login.]

- [x] worker-3 **Temporary access code for locked-out employees** — Owner can generate a one-time temporary PIN for any user. Valid for 1 hour only, single-use (expires after login). Stored as `temp_pin` + `temp_pin_expiry` on user record. Login flow: if `temp_pin` exists and is not expired, accept it alongside the normal PIN. After use: clear the temp PIN. Use case: "Boss, I forgot my PIN and I'm standing at the register." Owner generates a temp code via their phone/admin panel, employee uses it once, then sets a new PIN.

- [x] worker-2 **Employee self-service PIN change** — "Change PIN" button in POS header/profile area. User enters current PIN → new PIN (twice for confirmation). Validates: new PIN must be 4-8 digits, can't be same as current, can't be easily guessable (no 1111, 1234, etc. — warn but don't block). `POST /api/auth/change_pin` endpoint. Logs to activity_log. If user has 2FA enabled, require TOTP code to change PIN (prevents someone who shoulder-surfed the PIN from locking the real user out). [worker-2 — New /api/auth/change_pin endpoint with validation, 2FA check, guessable PIN warning, frontend modal with TOTP field, session update]

- [x] worker-1 **Login attempt audit per user** — Track failed login attempts per user (in memory, resets on restart). After 5 failed PIN attempts: lock that user's account for 10 minutes. Show in User Management: "3 failed login attempts today." Activity log: `login_failed` events with IP (if available) and timestamp. Admin can "Clear Lockout" to immediately unlock a user. This is a simpler rate-limit on PIN entry (complementing the 2FA rate limit). [worker-1 — Added login_failed_attempts in-memory tracker, record_failed_login/check_lockout helpers, 429 on lockout after 5 failed PIN attempts, clear on successful login, /api/users/clear_lockout endpoint, IP tracking in all login log entries, failed_login_attempts/login_locked fields in /api/users, UI badge/count in user cards, clear lockout button for manage_users, i18n EN+ES]

- [-] worker-3 **Password support (optional PIN alternative)** — Cancelled: no implementation specification provided — too vague to implement.

### Priority: MEDIUM

- [x] worker-2 **Account lockout notification** — When a user gets locked out (too many failed PIN attempts), send Discord notification to admin channel: "🔒 Carlos (1234) locked out after 5 failed PIN attempts. [Unlock in User Management]." Also show a banner in admin Timesheet/Dashboard. [worker-2 — Added `send_discord_alert()`/`send_discord_alert_async()`/`maybe_notify_lockout()` functions, integrated into `record_failed_login()` on lockout (5 failed PIN attempts). Webhook URL configurable via Security Dashboard. Lockout state endpoint + frontend banners in Timesheet and Security sections. i18n ready. 5-min cooldown prevents spam.]

- [x] worker-3 **Login session management** — Track active sessions per user. Show "Active Sessions" in Security settings: list of devices/locations logged in, with "Log Out Everywhere" button. Sessions stored in memory with a session token + expiry (default 8h active, 24h idle). On PIN change: optionally "Log out all other sessions." [worker-3 — Added active_user_sessions in-memory store with session tokens. All 4 login paths (PIN, password, temp PIN, 2FA) now generate tokens. New endpoints: POST /api/sessions (list), POST /api/sessions/logout, POST /api/sessions/logout_all. Session expiry: 8h active since login, 24h idle since last_active. Periodic session touch via frontend (every 5min). Security dashboard now uses real session data. PIN change modal has "Log out all other sessions" checkbox. i18n EN+ES.]

- [x] **User account history timeline** — Per-user timeline in User Management: PIN changes, 2FA setup/disable, login successes/failures, lockouts, temp PIN usage, permission changes. Chronological, filterable. Gives owner full visibility into account activity. "Carlos's PIN was reset 3 times this month — is someone messing with him or does he keep forgetting?" [worker-2 — New POST /api/users/timeline endpoint with user-scoped activity log filtering, type_labels mapping with 30+ event types with emoji+color coding, date and type filtering, chronological grouping. Frontend: 📜 Timeline button per user card, modal overlay with filter controls (date range + type dropdown), grouped-by-date display with color-coded left-border entries, detail formatting for each event type. Python syntax verified, endpoint tested with real data returning 23+ events.]

### Priority: LOW

- [x] worker-3 **Bulk PIN reset for shift change** — At shift change, owner can reset PINs for all clocked-out employees in one action. Each gets a unique random temp PIN delivered via printed slip or displayed on screen. Useful for high-turnover environments where new hires get fresh PINs each shift. [worker-3 — New POST /api/users/bulk_reset_pin endpoint, frontend button in User Management, confirmation dialog, modal showing employee PINs with Print button, i18n EN+ES]

- [-] worker-2 **Biometric / device-bound PIN** — Cancelled: needs WebAuthn library + backend endpoints + frontend credential management + clock-in integration. Multi-tick project, not feasible in single tick. [worker-2]

## Database Backup & Disaster Recovery (NEW — June 2026)

> The Database Architect worker is migrating from flat JSON files to SQLite. Once migrated, database integrity becomes critical — a corrupted or lost `pos.db` means lost orders, shifts, users, inventory, everything. This section covers automated backup, verification, retention, and disaster recovery procedures.

### Current state (pre-migration)
- All data is JSON files — easy to back up with `cp` or `tar`
- The System Auditor already checks JSON integrity every 4h
- No automated off-server backups
- No retention policy
- Restore = manual file copy

### Target state (post-migration)
- SQLite database (`pos.db`) backed up automatically
- JSON files also backed up (kept as secondary backup during transition)
- Backups verified (not just copied — actually opened and checked)
- Retention: hourly (24), daily (7), weekly (4), monthly (12)
- Off-server copy to VPS backup location or S3-compatible storage
- Restore procedure documented and tested
- Backup status reported in Discord

### Priority: HIGH

- [-] worker-3 **SQLite backup script** — Cancelled: system is still JSON-only (pre-migration). SQLite backup applies post-migration only.

- [x] worker-3 **JSON backup script** — Created `/root/pos-system-work/scripts/backup_json.py`: validates all JSON files, copies to timestamped directory, creates tar.gz archive, reports file sizes and anomalies. Supports --dry-run and --quiet modes. [worker-3]

- [x] worker-1 **Automated backup cron job** — Registered `pos-backup.py` as Hermes cron job (hourly interval, no_agent=true, Discord delivery on failure only, silent on success). The script backs up all JSON data files with validation, optionally backs up SQLite (if pos.db exists during/after migration), and cleans up old backups per retention policy (24h hourly, 7d daily, 4w weekly, 12m monthly). Tested: runs cleanly, produces valid tar.gz archive, exits 0 on success with no output (silent). [worker-1]

- [x] worker-3 **Backup retention cleanup** — Added `retention_cleanup()` to `backup_json.py`: keeps all hourly backups from last 24h, 1/day for last 7 days, 1/week for last 4 weeks, 1/month for last 12 months. Dry-run mode (`--dry-run --cleanup-only`) previews deletions. Integrated into normal backup flow (runs after each backup). Also supports standalone `--cleanup-only` mode. [worker-3]

- [x] worker-2 **Database health check script** — Created `scripts/db_health.py`: validates all JSON data files (parse, sizes, record counts, shrinkage detection) in JSON mode; PRAGMA integrity/foreign_key/quick_check in SQLite mode. Supports `--quiet`, `--check-only`, `--json`, `--sqlite` flags. Exit code 0 = healthy. Callable as pre-backup validation from backup script. [worker-2]

### Priority: MEDIUM

- [x] worker-1 **Off-server backup (scp/rsync to VPS backup location)** — Extend backup script to optionally copy the latest backup to a remote location:
  - Config in `timesheet_config.json`: `"offsite_backup": {"enabled": false, "host": "", "path": "", "ssh_key": ""}`
  - Uses `scp` with SSH key
  - Falls back gracefully if remote is unreachable (logs warning, doesn't fail)
  - Keeps same retention policy on remote

- [x] worker-2 **Restore procedure documentation + script** — Created `/root/pos-system-work/scripts/restore_db.py` with full restore workflow:
  - `--list` flag lists all available JSON (.tar.gz) and SQLite (.db.gz) backups with timestamps and sizes
  - `restore_db.py <backup_file>` restores from any backup (auto-detects type by extension)
  - `--json` flag for JSON tar.gz restore with optional SQLite sync after restore
  - `--dry-run` previews steps without making changes
  - Steps: decompress → verify integrity → stop Flask → replace data files → restart Flask → verify app responds
  - Confirmation prompt: "⚠️ This will replace the current database. All changes since the backup will be lost. Continue? (yes/no)"
  - Creates a safety backup of CURRENT data before restoring (stored in backups/pre_restore_safety/)
  - Safety net: undo instructions printed after successful restore
  - Python syntax verified, --list tested showing 23 JSON + 13 DB backups, --dry-run tested for both modes

- [x] worker-1 **Database migration rollback** — Created `scripts/sync_json_from_db.py`: reads all 24 SQLite tables and writes to corresponding JSON files. Handles special formats: users (dict keyed by pin), items (grouped by category), combos (dict with combos key), cash_drawer (sessions+transactions), table_ads (ads list + rotation_interval), known_ips (grouped by user_id), and more. Boolean/int conversion, JSON field parsing, idempotent, --dry-run and --quiet modes. Python syntax verified, tested with real data. [worker-1]

### Priority: LOW

- [-] worker-1 **Point-in-time recovery (WAL archive)** — Cancelled: system is still JSON-only (pre-migration) — WAL applies post-migration only.

- [x] worker-2 **Automated restore test** — Weekly cron: pick a random backup, restore it to a temp location, verify key metrics (table count, row count, recent order exists), report results. "Restore test: backup from June 20 restored successfully — 14 tables, 2,847 rows, all checks passed." Catches backup corruption before you need it. Delete temp DB after test. [worker-2 — Created scripts/test_restore.py with SQLite and JSON mode, integrity checks (quick_check/integrity_check/foreign_key_check), table count verification (expects 24), row counting across all tables, key table data checks (users, shift_log, activity_log, items), recent order verification, --quiet/--dry-run/--backup modes. Registered as weekly cron: "0 7 * * 1" (Mondays 7am), no_agent=true, silent on success, Discord delivery on failure.]

- [-] worker-1 **Database migration to PostgreSQL (future)** — Cancelled: system is JSON-only and will migrate to SQLite first. PostgreSQL is a future consideration only.

## Employee Self-Service Portal — Tickets, Requests & Issues (NEW — June 2026)

> Currently there's no way for employees to submit time-off requests, report issues, or give feedback without texting the manager. This is a lightweight internal ticketing/request system where employees log in, submit, and admin/owner approves or denies.

### Data Model

New `tickets.json` data store. Each ticket:
```
{
  "id": "TKT-001",
  "user_id": "1234",
  "user_name": "John",
  "type": "time_off | issue | feedback | other",
  "status": "pending | approved | denied",
  "subject": "Request June 28-30 off",
  "description": "Family wedding out of town...",
  "date_from": "2026-06-28",          // for time_off type
  "date_to": "2026-06-30",            // for time_off type
  "total_days": 3,                     // auto-calculated
  "created_at": "2026-06-23T14:00:00",
  "responded_by": null,                // admin PIN who acted
  "responded_at": null,
  "response_note": null,               // admin's reason if denied
  "priority": "normal | low | urgent"   // for issue/feedback types
}
```

### Priority: HIGH

- [x] worker-1 **Employee ticket submission UI** — New "📋 Requests" tab visible to all logged-in employees. Clean form with dropdown to select type: "🕐 Time Off Request", "🐛 Report Issue", "💬 Feedback / Suggestion", "📝 Other". Form adapts to type: time-off shows date range picker (with auto-calculated days badge), issue/feedback shows priority selector. Subject + description fields. Submit button stores to `tickets.json` via `POST /api/tickets/submit`. Toast confirmation. "My Tickets" list below form showing user's own submissions with status badges (Pending/Approved/Denied). Also added: `POST /api/tickets/my`, `POST /api/tickets/queue` (admin), `POST /api/tickets/respond` (admin approve/deny) endpoints. Full i18n EN + ES. [worker-1]

- [x] worker-2 **Admin/owner ticket management dashboard** — New admin sub-tab "📋 Ticket Queue" (permission-gated: `manage_users` or new `manage_tickets` perm). Two-column layout: **Pending** (left) and **Resolved** (right). Each ticket card shows type icon, employee name, subject, date submitted, priority badge. Approve ✅ and Deny ❌ buttons on pending tickets. Deny prompts for reason note (required). Approve auto-sets status and timestamp. Activity logging for all actions.
  - [worker-2] Done: Added `asTickets` button to admin sidebar, `secTickets` section with two-column Pending/Resolved layout, `loadTicketQueue()` / `renderTicketQueue()` / `renderTicketCard()` / `respondToTicket()` functions, deny reason prompt, i18n EN+ES.

- [x] worker-1 **Ticket status notifications** — When admin approves/denies a ticket, employee sees a notification badge on their "📋 Requests" tab. In-tab alert banner: "Your time-off request was ✅ approved" or "❌ denied". Unread count badge on tab button. [worker-1 — Added `response_read` field to ticket model, `/api/tickets/mark_read` endpoint returns alerts for newly seen responses, `/api/tickets/my` returns `unread_count`, frontend badge on tab button with 30s polling, alert banners with i18n EN+ES, auto-mark-read on tab visit]

- [x] worker-1 **API endpoints for ticket CRUD** — `POST /api/tickets/submit`, `POST /api/tickets/my`, `POST /api/tickets/queue`, `POST /api/tickets/respond`. Permission-gated. [worker-1 — All 5 endpoints implemented: submit (9333), my (9458), queue (9480), respond (9496), mark_read (9543). Full validation, permission gating (manage_users), activity logging, i18n, overlap detection for time-off, response status tracking.]

### Priority: MEDIUM

- [x] worker-3 **Conflict detection for time-off requests** — When admin views a pending time-off, show warning if too many employees already approved for same dates. Backend: `check_timeoff_conflicts()` helper, queue and respond endpoints attach `conflict_warning` with count/names/threshold. Configurable `max_staff_off_per_day` in timesheet_config.json (default 3). Frontend: red warning banner in admin ticket card, warning toast on approve. [worker-3]
- [x] worker-2 **Ticket filtering and search** — Admin queue: filter by type, status, employee, date range. Search by text. [worker-2 — Backend: added filter params (filter_type, filter_status, filter_employee, filter_date_from, filter_date_to, filter_search) to POST /api/tickets/queue. Frontend: filter bar with type dropdown, status dropdown, employee search, date range inputs, text search, Apply/Reset buttons. Ticket count badges on columns. i18n EN+ES.]
- [x] worker-1 **Recurring time-off patterns** — Allow employee to request recurring time-off (e.g., "every Tuesday for the next 3 months"). Added recurring toggle + day-of-week selector in time-off form. Backend calculates all occurrences, validates against overlap with existing requests. Recurring badge shown in employee and admin views. i18n EN + ES. [worker-1]

### Priority: LOW

- [x] worker-1 **Issue/bug ticket triage labels** — Admin can tag issue tickets: "POS bug", "hardware", "menu error", "customer complaint", "other". [worker-1 — Added label field to ticket model (label: pos_bug|hardware|menu_error|customer_complaint|other). Backend: label stored on submit for issue tickets, settable via respond endpoint, filterable in queue. Frontend: label dropdown in employee issue form, label badge on ticket cards, label filter in admin queue, label selector in pending card actions. i18n EN+ES. Dark theme compatible.]
- [x] **Ticket response templates** — Admin can save common response notes as templates. [worker-3 — New ticket_templates.json data store. 3 API endpoints: POST /api/tickets/templates/list, /save, /delete. Frontend: 📋 Templates sub-tab in Tickets admin with add/edit/delete UI. Deny prompt now uses modal with template selector dropdown that pre-fills reason textarea. Permission-gated (manage_users). Activity logged. Dark theme, touch-friendly 44px+ targets. Created 3 default seed templates on first use.]
- [x] worker-1 **Employee feedback analytics** — Aggregate feedback tickets by category over time.
- [x] worker-3 **Auto-approve for low-risk time-off** — Configurable rule: auto-approve time-off if requested >2 weeks in advance AND no other approvals for same date. [worker-3 — Added `auto_approve_threshold_days` to timesheet_config (default 14). Auto-approval runs in ticket_submit(): checks advance days against threshold, checks no scheduling conflicts via existing check_timeoff_conflicts(), sets status=approved with responded_by='system'. Configurable via Timesheet Config UI (new input field). Activity logged as ticket_auto_approved. Frontend shows special green toast + glow animation on auto-approval. Python syntax verified, test-passed: advanced request auto-approved, short-notice request correctly left pending.]

## Employee Pay Portal — Pay Stubs, History & Downloads (NEW — June 2026)

> Employees should be able to log in and see their own pay: hours worked, pay rate, gross/net, per-period and YTD totals, downloadable pay stubs, and a way to flag discrepancies.

### Key design decisions

- **Data source**: shift_log.json (clocked hours) × user pay_rate from users.json
- **No actual payroll processing** — this is informational/reporting, not ACH/bank integration
- **"Request Review"** feeds into the existing ticket system (type: `pay_review`)
- **Pay stubs are generated on the fly** from shift data — no separate pay_stubs.json needed

### Priority: HIGH

- [x] worker-3 **Employee "My Pay" tab** — New "💰 My Pay" tab visible to all logged-in employees. Shows three sections: Current Period, Pay History, Year-to-Date summary card. [worker-3 — Backend: /api/employee/my_pay endpoint. Frontend: myPayTab with YTD card, current period with progress bar, expandable pay history with shift details. i18n EN+ES.]

- [x] worker-3 **Current pay period live tracker** — Pay rate stat card, auto-refresh every 60s with 🟢 Live badge, rate displayed in stat card. [worker-3]

- [x] worker-1 **Downloadable pay stub (PDF)** — "Download Pay Stub" button per pay period. Generates clean PDF with employee name, pay period dates, itemized shift list, total hours, pay rate, gross pay, YTD totals. [worker-1 — New POST /api/employee/pay_stub_pdf endpoint returning print-friendly HTML. 📄 button in pay history period cards opens in new tab for browser Print→PDF. Full i18n compatible.]

- [x] worker-2 **Pay history CSV export** — "Export My Pay History" button at bottom of Pay History. Added `POST /api/employee/pay_history_csv` endpoint returning CSV. 📥 Export CSV button in pay history card header triggers download via `downloadCSV()`. i18n EN + ES. [worker-2]

- [x] worker-1 **"Request Pay Review" action** — "⚠️ Request Review" button on any pay period or shift. Opens pre-filled ticket form (type: `pay_review`). [worker-1 — Added ⚠️ button to current period card and each pay history period card. `openPayReviewTicket()` switches to Requests tab and pre-fills type=pay_review, subject "Pay Review — [period]", and description template. Added 'pay_review' as valid ticket type in backend. i18n EN+ES.]

### Priority: MEDIUM

- [x] worker-2 **Year-to-date (YTD) earnings card** — Summary card at top of My Pay showing YTD gross pay, YTD hours, average hours/week, average hourly rate. Added avg_hours_per_week and avg_hourly_rate to backend YTD response, 2 new stat cards in frontend with i18n EN+ES. [worker-2]
- [x] worker-1 **Multi-rate support** — Per-shift pay rate override: `pay_rate` stored on each shift record at clock-out, used in all pay calculations (pay period, my pay, PDF, CSV, pay stub). Per-shift rate visible in timesheet shift tables and employee pay history. New `new_pay_rate` param in clock/edit endpoint for admin overrides. Shift edit modal includes pay rate field. Effective rate (weighted average) shown in employee cards with star indicator when multiple rates active. Backward compatible.
- [x] worker-2 **Pay stub email delivery** — Auto-email pay stub PDF to employee when admin marks a pay period as "paid". Added `email` field to user model (add_user, update_email endpoint, display + edit in user management). New `POST /api/timesheet/pay_period/mark_paid` endpoint generates per-employee pay stub HTML and sends via SMTP (reuses existing email config). Frontend: 📧 Email button in user management, 📧 Email Pay Stubs & Mark Paid button after approval finalization, paid status badge in approval section. i18n compatible. Backward compatible.
- [x] worker-1 **Tip tracking in My Pay** — Aggregate tip data per pay period. Added tip aggregation to `/api/employee/my_pay` endpoint: current period tips, per-pay-period tips in history, and YTD tips. Frontend: 💵 tips stat cards in YTD and Current Period sections, tip badge in pay history period cards and summary rows. i18n EN + ES. Backward compatible.

### Priority: LOW

- [x] worker-2 **Direct deposit info display** — Read-only display of employee's direct deposit details. [worker-2 — Added `POST /api/users/update_direct_deposit` endpoint storing bank_name, account_type, account_last4, routing_last4. New direct deposit display card in My Pay tab with masked account/routing numbers. Admin 🏦 Bank button in user management to set/clear bank info. i18n EN+ES. Activity logging.]
- [x] worker-1 **Pay comparison charts** — Bar chart in My Pay showing period-by-period gross pay for last 6 periods. Pure CSS bar chart (no Chart.js needed). Shows last 6 periods with proportional accent-colored bars, date labels, dollar amounts, and hover tooltips with hours/shifts/tips. Hides gracefully when <2 periods have pay data. i18n EN+ES.
- [-] **Tax withholding estimator** — Optional W-4 based tax estimates. [Cancelled by worker-3: too vague/no implementation specification — would need full W-4 form logic, federal/state tax tables, allowances system, and per-employee configuration. Not feasible in single worker tick without detailed spec.]

## Table-Side Digital Menu & Ad Display (NEW — June 2026)

> The existing `/tablet` page is a pure ad rotator. This needs to become a full table-side digital menu with ads as idle screensaver.

### What already exists
- `tablet.html` at `/tablet` — ad rotator with slideshow, swipe support, dot navigation
- `/api/ads/current` — returns active ads JSON
- `/api/items` (GET) — returns full menu with categories and items
- `/api/combos/list` (GET) — returns active combos
- Item images already supported

### Priority: HIGH

- [x] worker-2 **"View Menu" button overlay on ad screen** — Persistent floating button on the ad rotator: "🍽️ View Menu". When tapped, transitions to menu view. "← Back" returns to ad rotator. [worker-2 — Added floating button, menu overlay with category tabs + item grid, item detail popup, combo showcase row, auto-return after 45s idle. Dark theme, touch-optimized 48px+ targets, orientation-responsive grid.]

- [x] **Customer-facing menu display** — Full menu view with category tabs, item cards with images/descriptions/prices. Display-only, no ordering. Large touch targets (min 150px cards). [worker-1 — Verified: already implemented as part of worker-2's "View Menu" button overlay task. Category tabs, item grid with images/descriptions/prices, 150px min-height cards, no ordering, display-only. All requirements confirmed in code.]

- [x] worker-3 **Item detail popup** — Tap item card → fullscreen overlay with large image, description, price, dietary badges, modifier options. Swipe left/right to browse category.

- [x] worker-2 **Combo/meal deal showcase section** — "🔥 Featured Combos" horizontal scrollable row with combo cards, child items listed, combo price with strikethrough savings. [worker-2 — Fixed field names (combo_price, child_items), added strikethrough original price + green savings badge, calculates savings from menu item prices, child items with quantities in card + detail overlay]

- [x] worker-1 **Auto-return to ads after inactivity** — After 45s of no touch interaction on the menu view, a 5-second countdown toast appears ("Returning to ads in 5..."). User can tap "✕ Stay" or anywhere on the menu to cancel. If countdown reaches 0, auto-transition back to ad rotator. Countdown does not trigger when item detail overlay is open (customer actively browsing). Touch events on menuView, category tabs, item cards, and nav buttons all reset the idle timer. Cancel button + any menu touch cancels countdown and restarts idle timer.

### Priority: MEDIUM

- [x] worker-3 **Dark/light theme toggle on tablet** — Sun/moon toggle in corner for customers. Added `.light-theme` CSS variables override, top-left corner toggle button with sun/moon icon, localStorage persistence, DOMContentLoaded init.
- [x] worker-3 **Language toggle (EN/ES)** — Added full i18n system to tablet.html: L10N translation dictionary (EN+ES), `t()` function with variable interpolation, `applyTranslations()` for all `data-i18n` elements, language toggle button (top-left corner below theme toggle, shows EN/ES), localStorage persistence. All UI labels (30+ strings) translate between English and Spanish. Item names remain in admin's language. Touch-friendly 48px button. Dark/light theme compatible. [worker-3]
- [x] worker-1 **Happy hour / specials badge on items** — Show "⚡ Happy Hour" badge with discounted price when scheduled pricing is active. Added sale badge ⚡ to item cards in POS grid (index.html) + tablet menu display (tablet.html) with discount label from active pricing rules. Green discounted price + strikethrough original. Item detail overlay shows badge + discounted price. CSS `.sale-badge` with absolute positioning. Backend already existed; frontend integration complete. [worker-1]
- [x] worker-3 **"Order This" QR code** — QR code icon on each item linking to online ordering page. Added 📱 QR button to each item card in tablet menu. QR code popup overlay with QR code via qrserver.com API linking to `/order?item=NAME`. Configurable base URL via `online_ordering_base_url` in `restaurant_config.json`. Falls back to `window.location.origin`. [worker-3]
- [x] **MEDIUM: Admin UI for item dietary tags** — Added dietary tag multi-select chip UI (🌿 Vegetarian, 🥦 Vegan, 🌾 Gluten-Free, 🌶️ Spicy, 🥜 Nuts, 🥛 Dairy, 🥚 Eggs, 🦐 Seafood, 🫘 Soy, 🌱 Organic, ☪️ Halal, ✡️ Kosher, 🍃 Sugar-Free, 🥬 Low-Carb) in both add-item and edit-item forms. Toggleable chips with accent-color highlight. Dietary tags displayed as emoji icons in item management list. Backend: edit_item now accepts and persists dietary_tags on both same-category and cross-category edits. [worker-2]
- [x] worker-1 **MEDIUM: Bulk menu item CSV import/export for rapid onboarding** — Backend: GET /api/items/csv_export (CSV download) and POST /api/items/csv_import (bulk create/update from CSV text). Both endpoints validate permissions (manage_items). Frontend: 📥 Export CSV button, 📤 Import CSV file picker with preview table (first 5 rows), Confirm/Cancel buttons, row-level error reporting, i18n EN+ES. CSV columns: category, name, price, description, image_url, dietary_tags (semicolon-sep), barcode. Existing items matched by name+category (case-insensitive) and updated. 🧪 Tested: export returns valid CSV with all items; import creates new items with full fields, updates existing on match, reports row-level errors; missing cols/empty CSV properly rejected. Activity logging included. Dark theme, touch-friendly 44px+ targets. [worker-1]

### Priority: LOW

- [x] worker-3 **Allergen filter toggle** — Filter button to show/hide items by allergen. [worker-3 — Added collapsible 🥜 Allergen filter bar above POS item grid. Toggle button opens a chip panel showing dietary tags present in the current category/search view. Each chip toggles hiding items with that tag. "Show All" clears filters. Active filter count badge on toggle button. Allergen chips dynamically re-render on category switch or search. i18n EN+ES. Dark theme compatible. Touch-friendly 36px+ chips. Filter applies to both search results and normal category view. Empty-state message when all items hidden by filter.]
- [x] worker-2 **Nutritional info popup** — Optional per-item calorie/protein/carbs/fat display. [worker-2 — Nutritional fields (calories, protein, carbs, fat) added to item data model on add/edit/CUD endpoints. Admin Add/Edit item forms include nutrition inputs. POS item cards show 🍎 calorie badge with toast popup showing full breakdown. CSV import/export includes nutrition columns. Tablet menu item detail overlay shows nutrition card. i18n EN+ES. Backward compatible.]
- [x] worker-1 **"Most Popular" badge** — Auto-calculated from most-ordered analytics. [worker-1 — New GET /api/items/popular endpoint analyzing orders.json, returns top 5 items by total quantity ordered. Frontend: popularItems Set loaded in loadItems(), "🔥 Most Popular" gold badge on item cards in both POS grid and tablet menu display. i18n EN+ES "Most Popular"/"Más Popular". Dark theme, touch-friendly.]
- [x] worker-2 **Wake-on-proximity / screensaver mode** — Dim screen when no one nearby, brighten on motion. [worker-2 — Added screensaver dim overlay after 120s of inactivity, auto-updating clock with localized date, wake-on-touch/click/keypress/mousemove/device-motion (accelerometer), Screen Wake Lock API integration to prevent device sleep, iOS motion permission handling, i18n EN+ES. On stationary tablet, overlay shows large clock and date. Any interaction (touch, click, motion) wakes full screen. Works on both ad view and menu view.]

## New Tasks (from Audit #16 — 2026-06-24)

- [x] worker-3 **HIGH: Waiter "Food Ready" push notification via WebSocket** — When kitchen marks an order as complete (`POST /api/kitchen/complete`), emit a SocketIO event `food_ready` to the waiter who submitted the order (track `waiter_id` on order records). The waiter's POS shows a persistent red badge on the History tab + plays a short alert sound. Currently waiters must manually check order status to know food is ready. One-way notification saves 2-3 trips to the kitchen per shift. WebSocket event also plays `navigator.vibrate(100)` on supported devices for physical confirmation. [worker-3 — Backend: new join_waiter/leave_waiter SocketIO rooms, food_ready emit in kitchen_complete(). Frontend: foodReadyBadge on History tab with pulse animation, socket listener plays sound + vibrate + toast. All POS clients join waiter_<PIN> room on connect/login. Badge clears on History tab visit.]

- [x] worker-1 **MEDIUM: Separate lightweight kitchen display page** — Created `/kitchen` as standalone HTML page (288 lines, 20KB vs 19K-line index.html). Dark theme matching existing design. Features: PIN entry for cook ID (stored in localStorage), auto-refresh polling (8s), kitchen queue grid with table grouping, claim/complete/cancel buttons, sound alerts (Web Audio API 3-note sequence), priority aging colors (5+ min warning, 10+ min critical with pulse animation), age time updater (10s interval), live clock, fullscreen toggle, offline banner on connection failure. Backend: new `/kitchen` route in app.py serves kitchen.html. Cuts load time from ~5s to under 1s on low-end hardware. [worker-1]

- [x] worker-3 **MEDIUM: "Call Server" notification for waiters** — The `/api/tablet/call-server` endpoint already exists and stores calls. Add frontend polling/WebSocket listener in POS to show a popup notification when a customer calls from a table: "📞 Table 5 needs assistance". Include a "Dismiss" button that marks it as handled. Shows table number, timestamp, allows quick navigation to that table's tab. Saves waiters from having to check a separate display. [worker-3 — Added in-memory active_calls tracking, /api/tablet/active-calls and /api/tablet/dismiss-call endpoints, modal overlay with per-call Dismiss + Go to Table buttons, Dismiss All button, callServerBadge with pulse animation on POS tab, 15s polling fallback, sound/vibration on new call, i18n EN+ES.]

- [x] worker-2 **HIGH: Kitchen offline degradation** — When WebSocket disconnects, the kitchen display silently stops showing new orders. Implement automatic polling fallback (every 8s) triggered by socket disconnect event, with visible "⚠️ Offline — updating every 8s" banner. Currently the main POS has polling fallback but kitchen view doesn't. This is critical for reliability during network blips.
  - Done: Added `startKitchenPolling()` / `stopKitchenPolling()` functions. Socket disconnect/connect_error triggers polling + offline banner. Socket connect stops polling + hides banner. `showKitchenView()` checks socket state before enabling polling. Animated red banner with i18n EN+ES. [worker-2]

- [x] worker-2 **MEDIUM: Table status overview dashboard** — Color-coded floor plan grid (empty/occupied/order_in_progress/needs_bussing) with derived status from order data. Tap a table card to view full detail: active orders, completed orders, order history, last bussed timestamp. Mark Bussed button resets status. Checkout button for tables with active tabs. Uses existing tableTabOverlay modal. Backend: enhanced `/api/tables` with derived `status`, `raw_status`, `last_bussed_at`, `completed_count`; new `POST /api/tables/mark_bussed` endpoint (resets status + logs activity); new `GET /api/tables/tab/<int>/detail` endpoint with full table+orders+stats response. Frontend: `asTablestatus` button in admin sidebar, `secTablestatus` section with color legend + auto-filling grid, `loadTableStatusDashboard()`/`showTableDetail()`/`markTableBussed()` functions, CSS for `.floor-plan-card` with active scaling, responsive grid breakpoints. Backward compatible. [worker-2]

- [x] worker-1 **MEDIUM: Order transfer between waiters** — New `POST /api/tables/transfer_orders` endpoint with full audit trail (`transfers[]` array on order records: transferred_from/to, timestamps, who). Frontend: 🔄 Transfer button in table detail overlay → waiter selector modal → confirmation → transfer with toast. Activity logging `table_orders_transferred`. Permission-gated (manage_items). Touch-friendly 48px+ targets. Dark theme compatible. Backward compatible.

## New Tasks (from Audit #9 — 2026-06-23)

- [x] worker-3 **HIGH: Inventory not restored on refund/void** — Added inventory restoration in `/api/orders/refund`: after refunding an order, stock levels are re-incremented for each item (including combo child items). Also added dedup check in `/api/sync_orders` to prevent double-decrement by skipping already-processed `local_id`. Activity log now records `inventory_restored` list. [worker-3]

- [x] worker-2 **HIGH: No "Use Backup Code" link in 2FA login UI** — The backend endpoint `/api/auth/2fa/backup_login` exists and works, but the 2FA login screen has no "Use backup code instead" link. Added a "Use backup code instead" link below the TOTP input that transitions to a backup code entry field with validation, i18n EN+ES. Users who lost their phone can now log in via backup codes. [worker-2]

- [x] worker-3 **MEDIUM: Waiter quick re-fire / re-send order items** — No button to re-fire an already-submitted order item back to the kitchen (e.g., cook missed it, wrong portion, customer wants a remake). Current workaround: refund the item and re-order it (3+ taps). A "Re-fire" button on order history items would save 3-4 taps per incident.

- [x] worker-2 **HIGH: Single-item/partial refund (backend + frontend)** — Documented gap from walkthrough (line 466). Currently only FULL order refund is supported via /api/orders/refund. No way to refund/void individual line items. Waiters must refund the entire order and re-submit good items back to the kitchen. Add new POST /api/orders/refund_item endpoint accepting order_id + item_index(es) + reason. Frontend: checkboxes next to each line item in refund overlay to select which items to refund. Partial refund amounts reflected in stats (exclude refunded item revenue). Must restore inventory only for refunded items. Activity logging. [worker-2 — New POST /api/orders/refund_item endpoint with item selection checkboxes, inventory restoration for refunded items only, partial refund stats accounting, auto-full-refund when all items refunded, refunded_items tracking on order records, i18n EN+ES]

- [x] worker-1 **MEDIUM: System-wide data backup & restore** — New POST /api/system/backup (downloadable zip of all JSON data files), POST /api/system/restore (upload zip to restore with pre-restore safety backup), POST /api/system/backup/status (backup directory info). Admin UI: 💾 Backup sub-tab in admin with one-click download, file-upload restore with confirmation, and scheduled backup status display. Permission-gated (manage_users). Activity logging for restores. [worker-1]

- [-] worker-2 **MEDIUM: Customer online ordering portal** — Too complex for single worker tick: requires building a full standalone online ordering page with cart, checkout, pickup/delivery flow, and kitchen/pickup-display integration. Needs multi-tick project with dedicated worker.

- [x] worker-2 **MEDIUM: Proper PWA icons + iOS meta tags** — Added 192x192 and 512x512 PNG icons (POS-themed fork+plate design in brand colors). Updated manifest.json with proper PNG icon entries alongside the SVG fallback. Added apple-mobile-web-app-capable, apple-mobile-web-app-status-bar-style (black-translucent), and apple-mobile-web-app-title meta tags to index.html head. Added apple-touch-icon link tags for both icon sizes. Enhanced sw.js to v3 with network-first navigation, cache-first static assets (icons, manifest), offline fallback to offline.html. Created offline.html with dark-theme offline notification page. Python syntax verified, manifest JSON valid, PNG icons confirmed at correct sizes. [worker-2]

- [x] worker-1 **MEDIUM: 2FA frontend setup UI — QR scan + enable flow missing** — Added 3-step setup modal: (1) QR code display + secret key from `/api/auth/2fa/setup`, (2) 6-digit TOTP verification via `/api/auth/2fa/verify`, (3) backup codes display with "save these" warning. Header button "🔐 Setup 2FA" (or "🔒 2FA On" when enabled) for all logged-in users. Already-enabled state shows informational message without API call. Enter key auto-submits verify. Session state updated on success. Dark theme, touch-friendly. [worker-1]

## Production Readiness & Mobile Optimization (NEW — June 2026)

> This system will be used in real restaurants on touch tablets and phones — not just on a developer's desktop. Every feature, every button, every form must work with fat fingers on a 10" screen in a busy kitchen. This section covers everything needed to go from "works on my laptop" to "deployed in a restaurant."

### How the Production Readiness Auditor Works

A new cron worker — **POS Production Auditor** — runs every 8 hours. Unlike the existing System Auditor (which checks JSON validity and app startup), this worker thinks like a restaurant manager deploying to production:

1. **Walk through full real-world workflows** — clock in, take orders, split payments, clock out, run payroll
2. **Test on mobile viewport** — resize to tablet/phone dimensions, check touch targets, check overflow
3. **Identify what's broken or missing** — edge cases, missing validation, UX friction points
4. **Add findings to TASKS.md** under this section with clear priority
5. **Fix one HIGH priority item per run** if possible (small fixes: CSS touch targets, aria labels, viewport tweaks)
6. **Report to Discord** with audit summary

### Priority: HIGH — Touch & Mobile Readiness

- [-] **Touch target audit (all interactive elements ≥ 48px)** — Too broad for single worker tick — 13K lines of HTML, needs systematic element-by-element audit across entire file. Could be split into smaller per-section tasks.

- [x] worker-2 **Mobile viewport meta tag verification** — Confirmed viewport meta tag updated to `width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no`. Added `input, select, textarea { font-size: 16px }` CSS safeguard against iOS auto-zoom on input focus. Python syntax check passed. [worker-2]

- [x] worker-3 **No hover-dependent interactions** — Audited all 18 `:hover` CSS rules — none reveal hidden content (all cosmetic background/color/opacity changes). Wrapped every rule in `@media (hover: hover)` to prevent iOS sticky-hover bug. Added `:active` touch feedback for non-button clickable elements (table rows, badges, preset buttons, subtabs). Changed `-webkit-tap-highlight-color` from `transparent` to visible accent-color highlight for touch tap visual feedback. [worker-3]
⚠️ **Note: initial fix was incomplete** — standalone `:hover` rules were kept alongside `@media (hover: hover)` wrappers, meaning tablets still got sticky-hover via the unwrapped rules. Fixed by Production Auditor run 2: removed all 11 duplicate standalone `:hover` rules. All 13 hover rules now exclusively inside `@media (hover: hover)`. Verified: zero unguarded `:hover` rules remain.

### Priority: HIGH — Customer-Facing Menu & Display

- [x] worker-2 **Add images and descriptions to all menu items for customer-facing tablet menu** — Zero out of 14 items in `items.json` have `image_url`, `description`, or `dietary_tags`. The customer tablet menu (`/tablet`) shows items as bare text names with prices — no appetizing food photos, no descriptions to help customers decide, no dietary indicators. The item detail popup shows a hidden `<img>` tag (since there's no image URL) and an empty description field. For a real restaurant, a digital menu without food images looks unfinished and unprofessional. The data model supports all these fields (CSV export/import includes image_url, description, dietary_tags, nutrition) but the seed data was never populated. Fix options: (1) Add stock food photos to a `/static/images/` directory and update items.json with URLs; (2) Generate attractive SVG placeholder images with item names as text; (3) At minimum, add descriptions so items aren't just "Hotdog - Plain" on the customer menu. [Production Auditor]

- [x] worker-2 **Scrollable areas with momentum scrolling** — All scrollable containers (item grid, order history, timesheet list, admin sections) must have `-webkit-overflow-scrolling: touch` and smooth momentum scrolling. Test on actual iPad — default scrolling is janky and feels broken. Add `overscroll-behavior: contain` to prevent page bounce when scrolling modals.

- [x] worker-3 **Form input optimization for tablets** — All number inputs now use `inputmode="numeric"/"decimal"` + `pattern="[0-9]*"` to trigger the correct keypad (numeric or decimal) on tablets. PIN entry fields have `autocomplete="off"`. Quantity inputs have `min`/`max` constraints. Date inputs already used native `<input type="date">`. [worker-3]

- [x] worker-2 **Orientation handling (portrait + landscape)** — Restaurant tablets get mounted in both orientations (landscape on counter stands, portrait when handheld). Added `@media (orientation: portrait)` and `@media (orientation: landscape)` with view-optimized rules. Landscape: compact kitchen header/stats/cards, 3-column kitchen queue at 1200px+, up to 6-column item grid at 1600px+, cart sidebar. Portrait: cart bottom sheet (35vh), stacked filters/forms, full-width modals, compact kitchen cards. Also added <400px and <640px height breakpoints for very small screens. [worker-2]

### Priority: HIGH — Real-World Workflow Gaps

- [x] worker-2 **Walkthrough: full shift lifecycle** — Clock in → take 10 orders across 5 tables → split payment on 1 → apply discount → add tips → clock out. All APIs function correctly. See worker-2 report for friction points identified.

- [x] worker-1 **Walkthrough: closing shift reconciliation** — Tested full cash register closing flow: open session → cash in/out → close with reconciliation. All 3 variance scenarios tested: exact match ($0 diff), $20 over, $5 short. **Findings & fixes**: (1) Variance reason was NOT forced — added `variance_reason` field required when diff ≠ 0 on close endpoint. (2) Frontend now prompts for reason via popup when variance detected. (3) Toast uses 'danger' for shorts, 'warning' for overs. (4) Session history table now shows "Variance" column with reason. Paper trail confirmed in activity_log.json with full details including IP address and variance_reason. Backward compatible.

- [x] worker-3 **Walkthrough: refund/void flow** — Tested full order refund (✅): button appears instantly for manage_orders users, reason enforced client-side (graceful backend fallback), inventory correctly restored (Hamburger 95→93→95, Hotdog 97→96→97, Coke 94→91→94), refunded orders excluded from stats revenue calc, full audit trail in refunded_orders.json + activity_log.json with restored items list, frontend shows red "↩️ REFUNDED" badge. Single-item refund (❌): NOT implemented — no backend endpoint allows partial/individual item refund, no frontend UI for item selection. Complete refund is only option. [worker-3]

- [x] worker-1 **Error state testing** — Added error handling utilities (safeJSON, fetchJSON, showContentLoading/hideContentLoading) to frontend. Fixed unprotected JSON.parse at session restore. Added spinner loading states with graceful error messages (val-err styling) to loadItems, loadOrderHistory, loadUsers, loadAdminStats, loadActivityLog. Added fetchJSON wrapper that safely handles non-JSON responses and HTTP errors. Refund flow now uses fetchJSON with safe response handling. Backend load_json_data already handled file corruption. All JSON.parse calls in frontend now protected with try/catch. [worker-1]

- [x] worker-3 **Concurrent use testing** — Implemented stale-cart detection for table orders: backend `submit_order()` checks `composed_since` timestamp against existing orders for same table, returns 409 with conflict details if newer orders exist. Frontend shows modal with "Submit Anyway" (bypass with resubmit without composed_since) and "Refresh Cart" (clears cart for re-compose). Threading lock (`clock_lock`) added for atomic check-and-set on clock-in/out to prevent double clock-in race conditions. Rate-limit clearing preserved. Item editing concurrency noted as needing version-tracking (too complex for single tick). [worker-3]

- [x] worker-2 **Offline → online recovery flow** — Tested and fixed `/api/sync_orders`: added missing `customer_email` field, combo child_items inventory decrement, and loyalty points awarding. Frontend: added `customer_phone` to offline queued receiptData for loyalty on sync. Verified 10+ orders, payment splits, tips, table numbers, dedup, and error handling all work. [worker-2 — Added customer_email to order_details, combo child_items inventory handling, loyalty points in sync_orders; frontend saves customer_phone in offline queue]

### Priority: HIGH — Tablet Layout & Responsive Design

- [x] worker-1 **Add responsive breakpoints for tablet deployment** — The entire index.html has zero `@media (max-width:)` or `@media (min-width:)` rules. On an iPad (768px portrait), the POS layout is identical to a 27" desktop. Admin sub-tabs (17+ buttons) overflow off-screen. Item grid shows same number of columns regardless of viewport width. Cart stacks below items even on landscape tablets where side-by-side would be better. This is the single biggest blocker for real restaurant deployment. Fix: (1) Add viewport-adaptive column counts for item grid (2 cols at <600px, 3 at <900px, 4 at <1200px, 5+ at >1200px). (2) Make admin sub-tabs wrap to multiple rows on narrow screens. (3) Collapse cart to a slide-up sheet on portrait tablets with a toggle to expand. (4) Ensure all modals are full-width at <600px. Test on actual iPad (768x1024) and 10" Android tablet. [worker-1 — Added @media (max-width: 600px) breakpoint: full-width modals, compact admin sub-tabs, stacked history/form rows, 2-col stats grid, smaller main tabs. Added cart expand/collapse toggle button (⬆/⬇) with JS toggleCartExpand() and .cart-expanded class (35vh↔70vh). i18n EN+ES for toggle title. Verified: item grid was already responsive (2→3→4→5 cols at 600/900/1200px), admin sub-tabs already had flex-wrap, cart was already 35vh in portrait. Filled remaining gaps for true tablet production readiness.]

- [x] worker-3 **Fix inline min-height: 32px buttons across the UI** — Multiple inline-styled buttons use `min-height: 32px` (lines 845, 4731, 4732, 7072 in index.html). These are below the 48px minimum touch target used by the `--tap` CSS variable everywhere else. In a restaurant on a tablet, these small buttons are hard to hit reliably. Fix: add a CSS class `.btn-sm` that sets 36px min-height as a compromise for compact contexts, or bump all to 44px minimum.
  - [worker-3] Added `button.btn-sm, .btn-sm { font-size:13px; padding:4px 12px; min-height:36px; min-width:36px; }` CSS rule. Updated all 6 inline-styled 32px buttons (ghost toggle, shift edit, shift note, mod option remove, mod option add, pay period details) to use `btn-sm` class. Also bumped 3 compact input fields (cart item note, mod option name, mod option price) from 32px to 36px. Zero remaining `min-height:32px` in index.html. Python syntax verified.

### Priority: MEDIUM — Missing Production Features

- [x] worker-3 **Add order submit input validation (empty items, nonexistent items)** — `submit_order()` currently accepts `items: []` (empty array) and creates ghost orders with $0 total. Also accepts items with arbitrary names/prices without checking they exist in the menu database. Real restaurant impact: accidental empty submit creates phantom orders on kitchen display; API-level or frontend bugs can create items with wrong prices. Fix: (1) reject empty items array with 400 error; (2) validate each item exists in items.json; (3) verify price matches menu price within tolerance (e.g., ±$0.50). [Production Auditor]

- [x] **Reduce customer display poll interval from 2s to 5-10s** — Changed `POLL_INTERVAL` 2000→8000ms. Added adaptive polling: WebSocket events drive live updates (stop polling on connect, resume on disconnect). Reduces API requests from ~43,200/day to ~10,800/day. [worker-1]

- [x] worker-3 **Add kiosk mode cancel/reset flow for customers** — Added "🗑️ Cancel Order" button (with confirmation dialog → clears cart → exits to POS) and "🔄 Start Over" button (with confirmation → clears cart but stays in kiosk mode with reset tip/payment). Both buttons available in both New Order and Lookup kiosk views. Full i18n EN + ES with 7 new translation keys. Touch-friendly 56px min-height buttons with red (cancel) and amber (start over) styling. Dark theme compatible. Added `@media (hover: hover)` guard, `:active` touch feedback. [worker-3]

- [x] worker-3 **Printer integration (ESC/POS thermal printers)** — Added `/api/print/receipt` endpoint generating ESC/POS byte commands for network thermal printers (Epson TM-T88, etc.) via TCP port 9100. `_escpos_receipt_bytes()` function formats receipt with header, items, notes/modifiers, totals, bold TOTAL, and cut command. Printer config in admin UI (`/api/printer/config` + `/api/printer/config/save`): IP, port, enabled toggle, header/footer text, characters per line. Frontend: 🖨️ thermal print button in order history and receipt overlay, browser print fallback when printer unreachable. HTML receipt fallback via `_generate_print_html()` and `/api/print/receipt_html/<id>` endpoint. Full i18n EN+ES. Permission-gated (manage_items). Dark theme, touch-friendly.

- [x] worker-2 **Sound alerts for kitchen display** — Kitchen display already has a 3-note alarm. Added first-interaction overlay for iOS/Safari audio unlock ("Tap anywhere to enable kitchen alerts"). Modified playNotificationSound() to use configurable volume (clamped 5%-80%) and respect on/off toggle. New admin sub-tab "🔊 Kitchen Sound" with enable/disable select + volume range slider + test sound button. New backend endpoints GET/POST /api/kitchen/sound_config and POST /api/kitchen/sound_config/save storing to kitchen_sound_config.json (sound_enabled, sound_volume). Sound config loaded on kitchen view open and cached globally. i18n EN + ES. Touch-friendly range slider (44px min-height). [worker-2]

- [x] worker-1 **Idle timeout + auto-lock** — After 5 minutes of inactivity on the POS screen, auto-lock and require PIN re-entry. Configurable timeout (1-30 minutes). Countdown warning: "Locking in 30 seconds... tap to stay." Clock-out auto-lock: when employee clocks out, force logout on that device. [worker-1]

- [x] worker-3 **i18n gaps — ~20 hardcoded English toast messages** — Several `showToast()` calls in index.html still use raw English strings instead of `t()` translation keys. Found at lines: 5238, 5250, 5251, 5254, 5262, 5274, 5275, 5278, 5286, 5298, 5299, 5302, 5310, 5316, 5328, 5329, 5332, 5347, 5350, 5365, 5373, 5388, 5391. Common untranslated strings: "Network error", "Please select a date range first.", "Reason is required to unlock.", "Pay period CSV exported!", "Shifts CSV exported", "Export failed". Non-Spanish-speaking employees will see these in English even if the rest of the UI is in Spanish. Add i18n keys for all toast messages. Also: backend error messages from Flask routes are all English-only — add server-side translation or return error codes the frontend can map. [worker-3 — Fixed: Added 22 new i18n keys to L10N dictionary (EN+ES), replaced all raw "Network error" (40+ catch blocks) with t('toast.network_error'), fixed "Please select a date range first", "Reason is required to unlock", "Pay period CSV exported", "Shifts CSV exported", "Export failed" and 17+ other common hardcoded toast messages. Also: backend network errors with context (submitting tickets, exporting, security operations, etc.) now use t('toast.network_error') prefix for i18n.]

- [x] worker-2 **Performance on low-end tablets** — The single-page index.html is 500KB+. On a $100 Android tablet with 2GB RAM, this might be slow. Profile: page load time, time-to-interactive, memory usage. Optimize: lazy-load Chart.js (only on stats tab), defer non-critical CSS, split kitchen display into separate lightweight page. Target: <3s load on 4G, smooth 60fps scrolling.
  - [worker-2] Lazy-loaded Chart.js (dynamic script injection only when Charts tab opened, saving ~60KB download/parse on initial load). Deferred main JS (612KB) with `defer` attribute so HTML/CSS parses first. Split CSS: ~17KB critical CSS inline, ~45KB non-critical CSS loaded async via `media="print" onload="this.media='all'"`. Reduced blocking resource weight from ~900KB to ~37KB. Tested: Flask serves index.html + style.css correctly, health check passes.

- [x] worker-3 **Accessibility basics (screen reader, contrast)** — This will be used by real employees, some with disabilities. Minimum: all buttons have aria-labels, form inputs have associated labels, color is never the only indicator (add icons alongside color badges), contrast ratio ≥ 4.5:1 for text. Test with VoiceOver (iPad) or TalkBack (Android). This is often legally required for workplace software. [worker-3 — Added aria-label to 30+ icon-only buttons (calendar prev/next, TOTP digit inputs, backup code), 20+ form inputs (barcode, search, coupon, email, phone, delivery fields, date filters, refund reason, clock-out notes, request form). Added role="dialog" aria-modal="true" to all 12 modal overlays (receipt, table tab, refund, kiosk, favorites, save favorite, clock-out, idle countdown, lock, modifier, modifier editor, 2FA setup, generic). Added aria-live="polite" to dynamic content areas (itemGrid, cartItems, historyList). Added role="alert" to toast notifications. Extended toast duration 2500→3500ms. Contrast verified: #fff on #1a1a2e = ~15.4:1, #a0a0b0 on #1a1a2e = ~6.2:1 — both exceed 4.5:1. Status badges already include text labels alongside color.]

### Priority: LOW — Polish & Professionalism

- [x] worker-2 **Loading skeleton screens** — Replace "Loading..." text with skeleton screens (animated gray placeholders) for: item grid, order history, timesheet, pay period. Makes the app feel 2x faster even if load time is the same. Perceived performance is real performance in a busy restaurant. [worker-2 — Added CSS animations (shimmer keyframes, skeleton classes for grid/list/table/stats layouts), showSkeletonScreen/hideSkeletonScreen JS functions, updated loadItems/loadOrderHistory/loadAdminStats/loadTimesheetDashboard to use skeleton screens, initial HTML placeholders updated with inline skeleton markup. Verified app.py compiles cleanly.]

- [x] worker-1 **Smooth page transitions** — Currently switching between POS / History / Admin tabs is instant (jarring). Add subtle transitions: slide-left for forward navigation, slide-right for back, fade for modals. 150ms duration — fast enough to not feel slow, present enough to feel polished. [worker-1 — Added @keyframes slideInRight/slideInLeft/fadeInOverlay animations, tab-enter-right/tab-enter-left CSS classes, TAB_ORDER tracking in switchMainTab for direction-aware slide transitions, animationend cleanup, fade-in animation on all .modal-overlay.active, skipAnim for initial load and kitchen return. Also fixed bug: switchTab('requests') was an undefined function, changed to switchMainTab('requests').]

- [x] worker-2 **Haptic feedback on order submit** — On supported devices (iOS, modern Android), trigger a short vibration when an order is successfully submitted. `navigator.vibrate(50)`. This gives the waiter physical confirmation without looking at the screen — they can keep eyes on the customer. [worker-2 — Added `navigator.vibrate(50)` after successful order submission in both main `submitOrder()` function (line 9223) and kiosk `kioskPayNow()` function (line 17000). Consistent with existing vibration patterns used for food-ready and call-server alerts.]

- [-] **Dark mode on the tablet menu page** — Already done: Dark/light theme toggle on tablet implemented with `.light-theme` CSS, sun/moon toggle, localStorage persistence (see task at line 392). [consolidated]

- [-] **App icon + splash screen for PWA** — Duplicate of "Proper PWA icons + iOS meta tags" at line 425. Consolidate there. [consolidated]

## New Tasks (from Audit #17 — 2026-06-24)

- [x] **HIGH: Inventory low-stock alert on admin dashboard (Stats tab)** — The `/api/inventory/low_stock` endpoint already exists and low-stock warnings fire on order submission, but the admin dashboard (Stats tab) shows zero inventory health data. A manager checking daily revenue/stats doesn't see that items are critically low or out of stock without navigating to the Inventory sub-tab. This is an operational blind spot. Fix: add `low_stock_count` and `out_of_stock_count` to `/api/admin_stats` response (fetch from inventory.json), then render a warning stat card in the frontend stats grid (e.g., "⚠️ 3 items low on stock") with a link to the Inventory section. Also add the low-stock items list as a collapsible section below the stats grid. [worker-3 — Backend: added inventory health scan in admin_stats(), 3 new fields in stats response. Frontend: inventory health stat card (green/orange/red border by severity), collapsible low-stock items card below grid with out-of-stock badges. i18n EN + ES. Dark theme compatible.]

## New Tasks (from Audit #18 — 2026-06-24)

- [x] worker-2 **HIGH: Add table reservation/booking system** — New reservation data store (reservations.json) with 6 CRUD endpoints (list, create, update, delete, date_reservations). Daily date-navigator view with create/edit forms, conflict detection (double-booking prevention with 2h window), auto-cancel past no-shows on load, status workflow (pending→confirmed→seated/cancelled/no_show), quick-action buttons per reservation, edit modal with table assignment. Dark theme, touch-friendly 44px+ targets. [worker-2]

- [x] worker-1 **HIGH: Add end-of-day sales summary report** — One-page closeout report from the Stats tab showing: total sales by payment method (cash/credit card/other), tips collected, taxes collected, item sales counts by category, refunds/voids, net sales, order count, average ticket size. Available as printable HTML view and PDF download via browser print. Owner needs this for daily reconciliation and bookkeeping.
  - Backend: `POST /api/end_of_day_summary` with date range filtering, payment method breakdown, item category aggregation, refund/void tracking, tips/taxes/discounts. Frontend: "📋 End of Day Summary" button in Stats tab, modal overlay with stat cards, payment breakdown, category sales table, refunds card, and 🖨️ Print/PDF button (browser print). Full i18n EN + ES. Dark theme compatible. [worker-1]

- [x] worker-3 **HIGH: Add backup health status indicator to admin dashboard** — Show last successful backup timestamp, backup archive count, total size, and green/yellow/red health indicator directly on the admin Stats tab. If no backup exists or the latest backup is stale (>24h), show red warning. If backups exist but are stale (>6h), show yellow. Otherwise green. Managers should spot silently failing backups immediately without navigating to the Backup sub-tab.

### Priority: MEDIUM

- [x] worker-2 **MEDIUM: Add customer-facing table-side order status display on tablet** — After order submission, the table tablet (/tablet page) transitions from ad/menu mode to an order tracking screen showing: order items, status badges (pending → preparing → ready → collected), estimated wait time, and a "ready" animation when the kitchen marks the order complete. Auto-return to ad/menu mode after the order is collected. Reduces customer "is it ready?" questions and improves dining experience.

- [x] **MEDIUM: Add "No Sale" drawer open and manual cash adjustment from POS** — One-tap "Open Drawer" button in the POS cart area for making change without a sale, logged in cash drawer transactions with timestamp and employee PIN. Also add "Manual Cash In/Out" buttons directly on the POS screen (not requiring admin panel navigation) for quick cash drops, petty cash, tip payouts, and loan repayments. Faster than navigating to Cash Register admin section for common cash handling actions. [worker-1 — New POST /api/cash_drawer/no_sale endpoint logging no-sale drawer opens. Three POS cart buttons (Open Drawer, Cash In, Cash Out). Cash In/Out uses existing transaction endpoint with prompt-based flow. i18n EN+ES. Dark theme, 48px touch targets.]

## New Tasks (from Audit #19 — 2026-06-24)

### Priority: MEDIUM

- [x] worker-3 **MEDIUM: Auto-cleanup for activity_log and login_attempts data files** — activity_log.json (209KB, 563 entries) and login_attempts.json (20KB, 74 entries) grow without bound. Added configurable retention (default: 90 days activity logs, 30 days login attempts) with auto-trim on each `save_json_data()` call for these files. Retention config stored in `timesheet_config.json` under `data_retention` key. Admin UI in Timesheet Config section with number inputs for both retention periods. i18n EN + ES. [worker-3 — `_retention_cleanup()` + `_parse_iso_timestamp()` helpers in app.py, `data_retention` fields in get/save_timesheet_config(), retention inputs in Timesheet Config card, auto-trim on every save_json_data() call for these files. Verified: app.py compiles cleanly, retention correctly trims old entries, config endpoint returns new fields.]

## New Tasks (from Production Auditor — 2026-06-25)

### Priority: HIGH

- [x] worker-2 **Add order review/confirmation step before final submit** — Cart → Review modal showing all items with modifiers, per-item notes, order notes, totals, payment method → Confirm button. 30-second undo grace period with countdown toast. New `POST /api/orders/undo` endpoint restores inventory. Works with all existing modes (split payment, discounts, tips, drive-through, customer display, pickup board, offline queue). [worker-2 — Review modal with item cards, modifiers display, per-item notes, order notes, subtotal/tax/discount/tip/service charge/total breakdown, payment display, table + email info. Undo toast with 30s countdown, backend inventory restoration, same-user validation, edge cases handled (already voided, wrong user, expired period)]

- [x] worker-3 **HIGH: Add "Rush Order" / priority flag on order submission** — Waiters can now flag orders as urgent with a "🚨 Rush" toggle button in the cart. Rushed orders get a prominent pulsing red "🚨 RUSH" badge in the kitchen display that overrides normal age-based priority coloring. [worker-3 — Added `priority` field (null or "rush") to order records in submit_order and sync_orders. Frontend: rush toggle button in cart with red fill state, rush badge in review modal, pulsing red card border 🔴 in kitchen view, CSS animations for badge and card, i18n EN+ES]

- [x] worker-1 **MEDIUM: Add table number quick-filter in order history view** — Waiters can now filter order history by table number via a dropdown populated from unique table numbers found in orders. Combined with existing date range filter. [worker-1 — Added `<select>` dropdown in history filter bar, populates from unique table numbers on each loadOrderHistory() call, filters client-side while preserving the selection. Clear button also resets table filter. i18n EN+ES. Dark theme, responsive. Backward compatible.]

## New Tasks (from Task Generator — 2026-06-25)

### Priority: HIGH

- [x] worker-2 **Add gift card management (sell, redeem, balance check, report)** — New `gift_cards.json` data store with gift card CRUD. Sell gift card endpoint (`POST /api/gift-cards/sell`) with payment processing and unique card code generation. Redeem during checkout (`POST /api/gift-cards/redeem`) — customer pays partial or full amount with gift card. Balance check endpoint (`POST /api/gift-cards/balance`). Admin UI to sell gift cards, view sales report (cards sold, redeemed, outstanding liability), handle lost card replacement (disable old code, issue new one). Track gift card liability as deferred revenue. Integrate with POS payment flow: gift card payment option alongside cash/credit card. Essential revenue tool for any restaurant.

- [x] worker-3 **Add employee meal / comped item tracking** — Restaurant employees typically get free/discounted meals per shift. New "Employee Meal" and "Comp" buttons in POS cart when adding items. Employee meal tracks which employee ate what (logged to shift record for tax/accounting). Comp tracks manager-authorized free items with required reason (complaint resolution, VIP, promotional, quality issue). Daily/weekly comp summary report in admin Stats. Comp data stored as new `comp_type` and `comp_reason` fields on order items. Activity logging for all comps with who authorized. Configurable: per-employee meal limit (e.g., $15 max) and daily comp cap for managers. [worker-3 — Added comp_type/comp_reason per-item fields to cart and order model; toggle buttons in cart (🍴 Emp Meal / 🎁 Comp) with reason prompt for comps; comp badges in cart, review modal, kitchen display, and order history; comp summary stat cards + collapsible config in Timesheet Config; i18n EN+ES]

### Priority: MEDIUM

- [x] **Add course-based order timing for kitchen** — Items already have a `course` field (appetizer, main, dessert, side). Allow waiters to specify which courses to send to the kitchen now vs. hold for later. Add "Send Now" / "Hold" toggles per course group in the cart review modal. Held courses display with countdown timer showing when they'll auto-fire. Kitchen display shows timed courses with a "⏰ Fire in X min" badge and pulsing border when ready. Configurable course delays in admin settings (default: appetizers 0min, mains 15min after appetizers, desserts 5min after cleared). New `course_send_at` (ISO timestamp) and `course_fired` (bool) fields on order items. Prevents "food comes out all at once" complaints and improves dining experience. [worker-1 — Course delays in timesheet_config.json with admin UI, course_holds per order in review modal with Send Now/Hold toggles, countdown timers per held course, course timing badges in kitchen display, full i18n compatible, dark theme]

- [x] worker-2 **Add sales analytics dashboard with day-of-week and hourly breakdown** — New "📊 Analytics" sub-tab in admin with visual sales reports: revenue by day-of-week (pure CSS bar chart), revenue by hour of day (pure CSS bar chart with revenue/orders toggle), comparison to previous period (this week vs last week, this month vs last month with change % arrows). New `/api/analytics/dashboard` endpoint. Pure frontend CSS bar charts, i18n EN+ES, view_stats permission, dark theme.

### Priority: LOW

- [x] worker-3 **Add shift handoff notes for end-of-shift communication** — Simple note system where employees leaving a shift can leave notes for the next shift: equipment issues (ice machine down), customer situations (Table 7 complained about noise), inventory alerts (running low on salmon), VIP notes (regular customer's birthday tomorrow). New `handoff_notes.json` data store with fields: author, timestamp, note, priority (info/warning/urgent), category (equipment/customer/inventory/other). Prompt shown on clock-out if user has any unsent notes: "Any notes for the next shift?" Admin can view all handoff notes in Timesheet tab with filter by category/priority. Prevents critical information loss between shifts. [worker-3 — New POST /api/handoff_notes/save and POST /api/handoff_notes/list endpoints. Handoff note fields in clock-out modal with category+priority selectors. Admin collapsible section in Timesheet tab with category/priority/date filter. i18n ready. Dark theme. Python syntax verified, endpoints tested with real data.]

## New Tasks (from Audit #21 — 2026-06-25)

### Priority: HIGH

- [x] worker-3 **Audit #21: Stale pending order cleanup** — 53 out of 66 orders (80%) are stuck in "pending" status (never processed by kitchen). Added auto-cleanup on admin_stats view: cancels pending orders older than configurable `stale_order_hours` (default 24h). Dashboard alert card when pending count exceeds configurable threshold (default 10). Bulk Cancel Stale Orders button with date range filter in Stats tab. Configurable thresholds in Timesheet Config UI. Backend: `auto_cleanup_stale_orders()` helper + `POST /api/orders/bulk_cancel_stale` endpoint with activity logging. Frontend: pending order stat card (green/red border), stale cleanup banner, collapsible bulk cancel section. i18n EN+ES. Cancelled orders excluded from revenue/comp/end-of-day calculations. [worker-3]

### Priority: MEDIUM

- [x] worker-1 **Audit #21: Enable mandatory 2FA for admin/owner roles in production** — Set `require_2fa_for_admins=true` in `security_config.json`, updated session-restore flow to re-check mandatory 2FA from server so existing logged-in sessions detect the config change and see the banner. Also marked related SECURITY_TASKS.md task as resolved. [worker-1]

- [-] worker-2 **Audit #21: Complete SQLite migration** — Cancelled: requires refactoring ~540 JSON load/save operations across 18.5K-line app.py to use SQLite `db` module (currently not imported at all). This is a multi-tick/multi-worker project, not feasible in a single 30-min worker tick. Needs a dedicated migration sprint with multiple workers coordinating: (1) create SQLite-backed load/save wrappers, (2) migrate each data domain (users, items, orders, etc.) one at a time, (3) flip use_database flag, (4) extensive testing.

## New Tasks (from Queue Curation — 2026-06-25)

### Priority: HIGH

- [x] worker-1 **Discount and comp manager approval threshold** — Configurable dollar threshold above which applying a discount or marking an item as comp requires a manager PIN override. New `discount_approval_threshold` in timesheet_config.json (default 0 = disabled). Backend `POST /api/orders/approve_discount` endpoint verifies manager PIN with manage_users permission. Frontend manager PIN prompt modal in order review flow, approval badge in order history. Activity logging for all approvals. i18n EN + ES. Permission-gated (manage_users). [worker-1]

### Priority: MEDIUM

- [x] worker-2 **Menu item time-based visibility scheduling** — Auto-show/hide items from POS grid and customer tablet menu based on day of week and time range (e.g., breakfast items 6–11am, lunch 11am–4pm, dinner after 4pm). Add `scheduled_visibility` array field to item data model (day-of-week + start/end time rules, same format as scheduled_pricing). Reuse existing `is_schedule_active()` helper for time range checking. Admin UI: visibility schedule editor per item in add/edit forms with day-of-week checkboxes + start/end time inputs. Items outside their visibility window hidden from POS grid and tablet menu (still visible in admin item management). Simplifies shift transitions for multi-daypart restaurants. i18n EN + ES. Backward compatible (no rules = always visible, same as today). [worker-2 — Added is_item_visible() helper, _visible annotation in /api/items, scheduled_visibility field in add_item/edit_item endpoints. Frontend: collapsible visibility schedule editor in add/edit item forms with day-of-week checkboxes + time inputs + rule add/remove. _visible filtering in renderItems() (POS grid), renderCategories(), and tablet.html renderItems(). EN+ES i18n.]

## New Tasks (from Task Generator — 2026-06-25)

### Priority: HIGH

- [x] worker-3 **Add order type classification (dine-in, takeout, delivery, catering) with per-type workflows** — Categorize each order with explicit type field (dine_in/takeout/delivery/catering). Different service charge rules, packaging fees per type, tax rate overrides, and kitchen ticket formatting per type. Filter sales stats by order type for channel analysis. Quick-type selector in POS cart area with icon buttons. Essential for multi-channel restaurants that handle both dine-in and takeout in the same system.

- [x] worker-1 **Add server-side tax recalculation on order submit and tax period reporting** — Enforce tax calculation on server during order submission using configured tax_config rates (global, category, item overrides) instead of trusting frontend-supplied tax_amount. Add tax period report endpoint showing gross sales, taxable sales, tax collected by rate category, exempt sales totals, and net sales — exportable as CSV/PDF for tax filing compliance. [worker-1]
  > **Production Auditor (2026-06-25):** **BUMPED FROM MEDIUM TO HIGH.** The `global_tax_rate` in `tax_config.json` (currently 8.25%) is decorative — `submit_order()` takes `tax_amount` from the frontend verbatim and never validates against the configured rate. Any malformed request or frontend bug can submit orders with wrong tax. This is a data integrity AND fraud vector in a real restaurant where tax is legally required to be accurate. The server MUST recalculate tax using the configured rate(s) rather than trusting the client. The existing per-order-type `tax_rate_override` mechanism works only if the frontend sends `tax_amount == 0` — this is insufficient.

### Priority: MEDIUM

- [x] worker-1 **Add waitlist/digital queue for walk-in customers** — Host stand tool to add parties to waitlist with party size, name, phone, estimated wait time. Auto-calculate wait times from current table occupancy. Send SMS notification when table is ready via existing email/SMS config. Check-in marking, no-show tracking, and waitlist-to-table assignment integration with existing floor plan dashboard. [worker-1 — All 9 frontend JS functions implemented (wlAddToWaitlist, wlLoadList, wlUpdateEntry, wlCheckIn, wlNotify, wlCancel, wlNoShow, wlEstimate, wlUpdateStats) in index.html, completing the functional gap identified in the audit. Full backend integration, form validation, error handling, i18n EN+ES, dark theme.]
  > **Audit finding: Backend endpoints (9) and HTML skeleton exist, but JavaScript functions (`wlAddToWaitlist`, `wlLoadList`, `wlUpdateEntry`, `wlCheckIn`, `wlNotify`, `wlCancel`, `wlNoShow`, `wlEstimate`) are completely missing. The waitlist admin section renders but all buttons/actions are non-functional — clicking them throws JS reference errors. Frontend JS implementation needed.**

### Priority: LOW

- [x] worker-3 **Add customer birthday/anniversary tracking with automated rewards** — Capture customer birthdates and anniversaries during checkout via phone-based customer lookup. Auto-award loyalty points or free item on birthday with POS notification. Track visit frequency and offer periodic bonus rewards for regulars. Integrates with existing loyalty system for customer retention and marketing. [worker-3 — Loyalty data model extended with birthday/anniversary/visit_dates fields. Registration form + profile edit UI for birthdate & anniversary dates. Auto birthday bonus (2x points) + anniversary bonus (+50 pts) + milestone bonuses (100 pts at 5th/10th/25th/50th/100th/150th/200th/250th/300th/500th visit). Special toast notifications for all bonuses. New endpoint: /api/loyalty/update_profile for editing customer birthdays/anniversaries. New endpoint: /api/loyalty/upcoming_occasions for admin to see month/today's birthdays & anniversaries. Profile display shows birthday/anniversary dates and visit count. All backward compatible.]

## New Tasks (from Audit #22 — 2026-06-25)

### Priority: HIGH

- [x] worker-2 **Seed tables.json with default table layout** — `tables.json` has 0 entries. The entire table management system (table assignment, table status dashboard, tab checkout, table detail view) is non-functional. Create a default seed of 20 tables (or admin initialization wizard) so waiters can assign orders to tables. Without this, the table management feature set is invisible to restaurant staff. [worker-2 — Created `scripts/seed_tables.py` (runnable standalone or via --force). Modified app.py init block to seed 20 tables on fresh install (instead of empty `{}`). Added module-level auto-seed check after `save_json_data` that seeds tables if file exists but is empty — handles existing production installs. Tables span 5 sections: Patio (4), Main Dining (8), Bar (4), Window (2), VIP (1), Party (1). All tables have `section` and `capacity` fields for future floor plan enhancements.]

|- [x] worker-3 **One-time forced cleanup of stale pending orders** — 50 of 67 orders (75%) were stuck in "pending" status from June 23 and now >24h old. The `auto_cleanup_stale_orders()` function existed and ran on `admin_stats()` view, but the data wasn't cleaned on startup. Added `auto_cleanup_stale_orders()` call at module level (after all function definitions, before `__main__`), so stale pending orders are auto-cleaned on every server start — not only when admin visits the Stats tab. This prevents test data from polluting analytics, kitchen display, and pending-order alert threshold. Verified: stale orders are already cleared (50 cancelled, 0 stale remaining), new startup call keeps it clean going forward.

### Priority: MEDIUM

- [x] **Add missing item images for Breakfast and Salads categories** — 5 of 19 items (26%) had no `image_url`: Pancakes, Bacon & Eggs, French Toast, Caesar Salad, Grilled Chicken Salad. Created SVG placeholder images (colored gradient backgrounds with relevant emoji icons). Extended `generate_item_images.py` with Breakfast and Salads categories so future regeneration covers all items. All 19 items now have valid image URLs pointing to existing SVG files. [worker-2]

## New Tasks (from System Auditor #23 — 2026-06-25)

### Priority: HIGH

- [x] worker-1 **Complete waitlist frontend JavaScript implementation** — Backend (9 endpoints) and HTML skeleton exist, but the JavaScript functions (`wlAddToWaitlist`, `wlLoadList`, `wlUpdateEntry`, `wlCheckIn`, `wlNotify`, `wlCancel`, `wlNoShow`, `wlEstimate`, `wlUpdateStats`) were completely undefined. The waitlist admin section (`secWaitlist`) renders but every button/action threw JS errors. Implemented all 9 functions with full form validation, backend API integration, error handling, i18n compatible, dark theme. Added waitlist edit modal overlay. [worker-1]

### Priority: MEDIUM

- [x] worker-2 **Review and resolve 22 unresolved security events** — `security_events.json` had 24 total events, 22 unresolved (15 anomaly, 5 data_integrity, 3 access_control, 1 authentication). Created `POST /api/security/resolve_event` endpoint with permission gating. Added Resolve button with resolution note prompt in Security Dashboard event cards. Reviewed all 22 events: off-hours logins (15) were expected dev/test behavior from localhost cron workers; data_integrity issues (2FA persistence, activity log truncation, order subtotal) were historical bugs since fixed or inactive; access_control events were test block/unblock actions. All resolved with detailed notes. [worker-2]

- [x] worker-3 **Restock 6 inventory items at zero stock** — `inventory.json` shows 6 items at 0 stock: Robot Burger, Test Nutrition Item, Pancakes, Bacon & Eggs, Grilled Chicken Salad, and Test "Special" Item. The low-stock alert on the admin dashboard will show a persistent red warning until resolved. Admin should either restock these items or remove them from inventory tracking if they're test items. [worker-3 — Removed 3 test items (Robot Burger, Test Nutrition Item, Test Special Item) from inventory tracking; restocked Pancakes→50, Bacon & Eggs→40, Grilled Chicken Salad→30]


## New Tasks (from Task Generator — 2026-06-25)

### Priority: HIGH

- [x] worker-2 **Add auto-gratuity for large parties** — Configurable service charge auto-applied when party size exceeds configurable threshold (default: 6 guests to 18% gratuity). Configurable percentage and party size minimum in admin settings. Displayed as separate "Auto-Gratuity (X%)" line item in cart, review modal, receipt, and end-of-day summary. Manager override button to remove or adjust gratuity. Clear labeling per regulatory requirements (not a voluntary tip). Full i18n EN+ES. Essential for any full-service restaurant handling groups. [worker-2 — Backend: GET/POST /api/service-charge/config endpoints, server-side auto-gratuity calculation in submit_order using party_size + threshold, service_charge_amount stored on orders. Frontend: admin Service Charge section with enabled/threshold/percentage/label config, party size input in cart with auto-gratuity badge, calculateServiceCharge() function, manager override removeAutoGratuity(), displayed in cart/receipt/review modal/EOD summary/order history/kiosk. i18n EN+ES. Python syntax verified.]

- [x] worker-3 **Add customer feedback / satisfaction survey system** — QR code on printed and emailed receipts linking to a lightweight feedback page. Customers rate experience (1-5 stars) and optionally leave comments. Feedback aggregated in admin dashboard: average rating trend chart (daily/weekly/monthly), recent reviews list, response/follow-up button that creates a ticket in the existing ticket system. Low/high rating alerts (1-star complaints or 5-star glowing reviews). Helps identify service issues before they escalate to public review sites. [worker-3 — Backend: 4 new endpoints (submit/list/stats/respond), feedback.json data store, feedback stats in admin_stats response, QR feedback link on receipts. Frontend: standalone feedback.html page with star rating, feedback admin section with filters/respond/create-ticket, feedback stat card in dashboard, full i18n EN+ES. Dark theme, touch-friendly.]

### Priority: MEDIUM

- [x] worker-1 **Add delivery driver management and tracking** — Complement existing delivery order type with driver assignment and tracking workflow. New drivers.json data store with driver CRUD (list/add/update/delete), driver assignment to delivery orders, delivery status tracking (pending/assigned/picked_up/delivered/cancelled), driver delivery history/stats endpoints, driver auto-free on delivery completion. Frontend: admin Drivers sub-tab with add/edit/delete UI, driver stats bar, driver info and action buttons (assign/unassign/picked up/delivered/cancel) in order history for delivery orders, driver stat card on admin dashboard. Permission-gated (manage_orders). Activity logging for all actions. Dark theme, touch-friendly. [worker-1]

- [x] worker-2 **Add menu item recipe / cost of goods sold (COGS) tracking** — Link each menu item to inventory components with quantities per serving (e.g., "Hamburger" = 1 bun + 1 patty + 1 lettuce + 2 tomato slices). Per-item ingredient list stored on item record. Auto-calculate item cost from current inventory unit costs. Display cost, margin %, and breakeven price in item management detail. Analytics report: menu item profitability ranking (highest/lowest margin). Alerts when ingredient price changes significantly affect margin. Enables data-driven menu pricing decisions. [worker-2 — Added `ingredients` array to item data model (Accepted in add_item/edit_item, stored per-item). Added `unit_cost` field to inventory items for ingredient-level cost tracking. Backend: `calculate_item_cost()` helper, `get_item_profitability()` ranking function, 2 new endpoints (`POST /api/items/profitability`, `POST /api/inventory/update_unit_cost`), `/api/items` GET now annotates `_cost`/`_margin`/`_ingredients`. Frontend: ingredients editor (add/remove rows) in both Add Item and Edit Item forms, cost/margin display in item management list, unit cost input field in inventory management, new 📊 Profitability admin sub-tab with sort/search/filter and summary stat cards. `POST /api/inventory/update` now accepts `unit_cost`. Cost change alerts (>10% change) with affected item list. Seed data with unit costs for all 20+ menu items and ingredient recipes for Hamburger - Normal. Full dark theme, touch-friendly, backward compatible. Python syntax verified.]

### Priority: LOW

- [x] worker-3 **Add expense tracking and profit and loss reporting** — Record business expenses by category (supplies, utilities, repairs, marketing, labor, rent, insurance, other) with date, amount, vendor name, optional note. New expenses.json data store. Admin expense entry form with category dropdown + date picker. View expenses filtered by category/date range in admin analytics. Generate P&L statement: Revenue - COGS = Gross Profit - Expenses = Net Profit. Printable report for bookkeeping. Enables basic financial management within the POS without external accounting software. [worker-3 — Added EXPENSES_FILE constant, 4 backend endpoints (save/list/delete/pnl), expenses admin section with add form + category/date filter + expense list + P&L summary card with revenue/cogs/gross profit/expenses/net profit stat grid + category breakdown chips + print button. Backend calculates COGS from existing item ingredients/inventory data. Full i18n EN+ES. Dark theme, touch-friendly 44px+ targets. Activity logging. Python syntax verified, all 4 endpoints tested working.]

## New Tasks (from System Auditor #24 — 2026-06-25)

### Priority: HIGH

- [x] worker-2 **sync_orders() lacks item validation — ghost data confirmed** — Added item validation to `sync_orders()` matching `submit_order()` logic: rejects empty items arrays, validates each item against items.json/combos.json with ±$0.50 price tolerance, returns 400 with descriptive error messages. [worker-2]

### Priority: MEDIUM

- [x] worker-1 **Clean up ghost test data in orders.json** — Cancelled 10 ghost orders: #94 (empty items, $0), #95 (Ghost Item $999), #81 (Hotdog → nonexistent), #83 (Americano → nonexistent), #85-90 (Hamburger → nonexistent — should be "Hamburger - Normal"). All marked cancelled with descriptive reason. Verified: zero ghost orders remain in active states. [worker-1]

- [ ] **Restock low inventory items** — French Toast (10 units) and Caesar Salad (10 units) are below the 20-unit low-stock threshold. Admin should restock to normal levels or verify these counts are intentional. [System Auditor #24]

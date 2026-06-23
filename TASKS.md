# POS System — Smart Task Queue

> Auto-managed by 3 Hermes Worker Crons (every 30 min each, staggered claims).
> Workers use `[~]` to claim tasks before working. Never pick a claimed task.
> Last updated: 2026-06-23 (audit #6 — system audit + lateness tracking section)

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

- [ ] **Timesheet approval workflow** — After pay period ends, timekeeper clicks "Submit for Approval" which locks that period's shifts from further edits. Employee can review and "Approve" (optional — small shops may skip). Locked shifts grayed out with 🔒 icon. Unlock requires owner permission. Approval status stored in new `timesheet_approvals.json` with period range, approved_by, timestamp.

- [ ] **PDF timesheet report export** — Generate a clean, printable timesheet report for the selected pay period. Employee name, shift dates/times, daily totals, period total, overtime, estimated pay, signature line. `POST /api/export/timesheet_pdf` endpoint. Print-friendly CSS with page breaks per employee. More professional than CSV for record-keeping and employee handouts.

- [ ] **Timesheet UI overhaul for timekeeper usability** — Current admin Timesheet tab shows raw shift list + raw admin login timesheet in two separate sections. Redesign as unified timekeeper dashboard: period selector at top → employee summary cards (name, total hours, overtime, estimated pay) → click employee to expand individual shifts → export button clearly visible (not buried). Dense data table for the shift list. Sortable columns (name, date, hours). Visual indicators for overtime, edited shifts, missing clock-outs.

- [ ] **Missing clock-out detection & alert** — Detect employees who clocked in but never clocked out (e.g., 8h+ since clock-in with no clock-out). Show alert banner in admin Timesheet: "⚠️ 2 employees have active shifts over 8 hours — possible forgotten clock-outs." Allow admin to force clock-out with estimated time + note.

### Priority: LOW

- [ ] **PTO / sick day tracking** — Optional accrual-based or manual tracking. `pto_balance` field per user. Admin can log PTO/sick days with date range and type. Excluded from "missing clock-out" alerts for those days.

- [ ] **Shift schedule builder** — Weekly schedule grid where manager assigns shifts (Mon 9-5: John, Tue 9-5: Maria, etc.). Compare scheduled vs actual hours. Visual schedule calendar in admin. Helps catch no-shows.

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

|- [x] worker-2 **Backup code login** — `POST /api/auth/2fa/backup_login`: if user lost their phone, they can use a backup code instead of TOTP. Accepts `user_id`, `backup_code` (plaintext). Hashes the code and checks against stored `totp_backup_codes`. If match: login succeeds, REMOVE that code from the list (one-time use). Return remaining backup code count in response: "Logged in. 6 backup codes remaining." If no match: 401. After last backup code used: 2FA is still enabled but no recovery — user should regenerate. Admin should be notified when backup codes run low. [worker-2]

- [x] worker-2 **Admin/owner 2FA management & reset** — In User Management: show 2FA status badge per user (🔒 Enabled, 🔓 Not Set Up). **Owner can reset/disable 2FA for ANY user** (employee lost phone, left the company, can't log in). Requires `manage_users` permission. This resets `totp_enabled = false`, clears `totp_secret`, clears `totp_backup_codes`. Reason required (logged in activity_log: `2fa_disabled_by_admin`, who did it, why). Only owner can disable 2FA on other admins. Also: "Regenerate Backup Codes" button that generates new codes (invalidating old ones) — useful when employee says "I used my last backup code."

### Priority: MEDIUM

- [ ] **2FA setup UI (frontend)** — New "🔒 Security" section in the settings/profile area. Button: "Enable Two-Factor Authentication (2FA)". On click: calls `/api/auth/2fa/setup` → shows QR code (rendered as `<img>` from `provisioning_uri` using `qrcode` library to generate a data URI, or use a JS QR library). Below QR: "Can't scan? Enter this code manually:" + the base32 secret in a monospace font. Below that: 6-digit code input + "Verify" button. On verify: shows the 8 backup codes in a grid with a "Download" and "Copy" button. Red warning banner: "⚠️ Save these codes now. They will never be shown again. Without these, losing your phone means you lose access to your account." Confirmation checkbox: "I have saved my backup codes." Then "Finish Setup" button → marks setup complete.

- [ ] **2FA login UI** — After PIN entry, if server returns `2fa_required: true`, show a smooth transition to a 6-digit code input. Auto-focus and auto-submit on 6th digit (like banking apps). "Use backup code instead" link below in smaller text (for when phone is lost). Error states: "Invalid code" (shake animation), "Too many attempts — account locked for 15 minutes", "Backup code already used." Success: normal redirect to POS.

- [ ] **Backup code management UI** — In Security settings: "View Backup Codes" button (requires re-entering PIN for security). Shows remaining codes count: "5 of 8 codes remaining." Lists the plaintext codes (user needs to save them). "Regenerate Codes" button with confirmation: "This will invalidate all existing backup codes. Continue?" Admin: same "Regenerate" available in User Management.

- [ ] **Rate limiting on 2FA attempts** — Track failed TOTP attempts per user in memory (not JSON — resets on server restart). Max 5 failed attempts per rolling 60-second window. After 5: lock for 15 minutes (store lock expiry in memory). Return `429 Too Many Requests` with `retry_after` seconds. Rate limit applies to both TOTP verify AND backup code attempts (same pool — prevents brute-force on backup codes too).

### Priority: LOW

- [ ] **Email/SMS recovery option** — If backup codes are all used AND admin isn't available, user can request email recovery (if email is set in profile). Sends a one-time 6-digit code to email, valid for 10 minutes. Email config already exists from receipt delivery feature. This is a "I'm locked out at 2am and the owner isn't awake" safety net.

- [ ] **Mandatory 2FA for admin/owner roles** — Configurable toggle: "Require 2FA for all admin accounts." If enabled, any admin without 2FA gets a persistent banner: "⚠️ Your account requires 2FA — set it up now." Blocks access to admin features until 2FA is enabled. Owner can exempt specific admins. This prevents the "boss's account gets hacked because they never set up 2FA" scenario.

- [ ] **2FA audit log** — All 2FA events go to activity_log: `2fa_setup`, `2fa_disabled`, `2fa_disabled_by_admin`, `2fa_backup_code_used`, `2fa_login_success`, `2fa_login_failed`, `2fa_rate_limited`, `2fa_backup_regenerated`. Filterable in Activity Log. Gives owner a trail: "Who disabled Carlos's 2FA and why?"

- [ ] **WebAuthn / Passkey support (future)** — Optional upgrade path: support for hardware security keys (YubiKey) and platform passkeys (Face ID, Touch ID, Windows Hello) via WebAuthn API. Faster than typing TOTP codes, phishing-resistant. Requires `webauthn` Python library. Phase this in after TOTP is stable.

## Account Recovery & Admin Controls (NEW — June 2026)

> Currently if an employee forgets their PIN, there's no recovery path — they're locked out until the owner manually edits `users.json`. The owner needs in-app controls to reset PINs, set temporary passwords, view login history, and recover accounts without touching raw JSON files.

### Priority: HIGH

- [x] worker-1 **Admin PIN reset for any user** — In User Management, owner/admin can click "Reset PIN" on any user. Prompts for new PIN (4-8 digits). Requires `manage_users` permission. Only owner can reset another admin's PIN. Logs to activity_log: `pin_reset_by_admin` with who did it, to whom, timestamp. User gets notified on next login: "⚠️ Your PIN was reset by Owner on June 23. Use your new PIN." Optional: "Force PIN change on next login" checkbox — if checked, user is prompted to choose a new PIN immediately after logging in with the temp one. [worker-1 — New `/api/users/reset_pin` endpoint with permission gating, PIN move logic, audit trail, and pin_reset_notification field. Frontend: Reset PIN button in user management with prompt flow. Notification shown as warning toast on next login.]

- [x] worker-3 **Temporary access code for locked-out employees** — Owner can generate a one-time temporary PIN for any user. Valid for 1 hour only, single-use (expires after login). Stored as `temp_pin` + `temp_pin_expiry` on user record. Login flow: if `temp_pin` exists and is not expired, accept it alongside the normal PIN. After use: clear the temp PIN. Use case: "Boss, I forgot my PIN and I'm standing at the register." Owner generates a temp code via their phone/admin panel, employee uses it once, then sets a new PIN.

- [x] worker-2 **Employee self-service PIN change** — "Change PIN" button in POS header/profile area. User enters current PIN → new PIN (twice for confirmation). Validates: new PIN must be 4-8 digits, can't be same as current, can't be easily guessable (no 1111, 1234, etc. — warn but don't block). `POST /api/auth/change_pin` endpoint. Logs to activity_log. If user has 2FA enabled, require TOTP code to change PIN (prevents someone who shoulder-surfed the PIN from locking the real user out). [worker-2 — New /api/auth/change_pin endpoint with validation, 2FA check, guessable PIN warning, frontend modal with TOTP field, session update]

- [x] worker-1 **Login attempt audit per user** — Track failed login attempts per user (in memory, resets on restart). After 5 failed PIN attempts: lock that user's account for 10 minutes. Show in User Management: "3 failed login attempts today." Activity log: `login_failed` events with IP (if available) and timestamp. Admin can "Clear Lockout" to immediately unlock a user. This is a simpler rate-limit on PIN entry (complementing the 2FA rate limit). [worker-1 — Added login_failed_attempts in-memory tracker, record_failed_login/check_lockout helpers, 429 on lockout after 5 failed PIN attempts, clear on successful login, /api/users/clear_lockout endpoint, IP tracking in all login log entries, failed_login_attempts/login_locked fields in /api/users, UI badge/count in user cards, clear lockout button for manage_users, i18n EN+ES]

- [-] worker-3 **Password support (optional PIN alternative)** — Cancelled: no implementation specification provided — too vague to implement.

### Priority: MEDIUM

- [ ] **Account lockout notification** — When a user gets locked out (too many failed PIN attempts), send Discord notification to admin channel: "🔒 Carlos (1234) locked out after 5 failed PIN attempts. [Unlock in User Management]." Also show a banner in admin Timesheet/Dashboard.

- [ ] **Login session management** — Track active sessions per user. Show "Active Sessions" in Security settings: list of devices/locations logged in, with "Log Out Everywhere" button. Sessions stored in memory with a session token + expiry (default 8h active, 24h idle). On PIN change: optionally "Log out all other sessions."

- [ ] **User account history timeline** — Per-user timeline in User Management: PIN changes, 2FA setup/disable, login successes/failures, lockouts, temp PIN usage, permission changes. Chronological, filterable. Gives owner full visibility into account activity. "Carlos's PIN was reset 3 times this month — is someone messing with him or does he keep forgetting?"

### Priority: LOW

- [ ] **Bulk PIN reset for shift change** — At shift change, owner can reset PINs for all clocked-out employees in one action. Each gets a unique random temp PIN delivered via printed slip or displayed on screen. Useful for high-turnover environments where new hires get fresh PINs each shift.

- [ ] **Biometric / device-bound PIN** — If the POS terminal has a fingerprint reader or camera, allow biometric auth as a faster alternative to PIN. Uses WebAuthn platform authenticator. "Tap to clock in" — employee taps fingerprint, auto-identified, clocked in. No PIN needed. This is aspirational but worth listing.

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

- [ ] **Off-server backup (scp/rsync to VPS backup location)** — Extend backup script to optionally copy the latest backup to a remote location:
  - Config in `timesheet_config.json`: `"offsite_backup": {"enabled": false, "host": "", "path": "", "ssh_key": ""}`
  - Uses `scp` with SSH key
  - Falls back gracefully if remote is unreachable (logs warning, doesn't fail)
  - Keeps same retention policy on remote

- [ ] **Restore procedure documentation + script** — Create `/root/pos-system-work/scripts/restore_db.py`:
  - Lists available backups with timestamps and sizes: `python3 restore_db.py --list`
  - Restore: `python3 restore_db.py backups/pos_2026-06-23_14-00-00.db.gz`
  - Steps: decompress → verify integrity → stop Flask → replace pos.db → restart Flask → verify app responds
  - Confirmation prompt: "⚠️ This will replace the current database. All changes since the backup will be lost. Continue? (yes/no)"
  - Creates a backup of the CURRENT database before restoring (safety net)
  - Also supports `--json` flag to restore from JSON backup (populates SQLite from JSON files)

- [ ] **Database migration rollback** — If SQLite migration goes wrong, the Database Architect worker can flip `use_database: false` to revert to JSON mode. But we also need a script that re-populates JSON files from SQLite (reverse migration), so the JSON files stay in sync during the transition period. `scripts/sync_json_from_db.py` — reads all tables, writes JSON files. Run by the Database Architect after each migration step.

- [ ] **Backup monitoring in Discord** — Extend the backup cron to send a daily summary at 6am: "📦 DB Backup Report: 24 hourly backups (all OK), 7 daily retained, oldest: June 16. Total backup size: 84MB (compressed). Last integrity check: PASSED." This gives the owner confidence that backups are working without having to check.

### Priority: LOW

- [ ] **Point-in-time recovery (WAL archive)** — SQLite WAL (Write-Ahead Log) mode enables point-in-time recovery. Configure `PRAGMA journal_mode=WAL` and periodically archive WAL files. Combined with full backups, this allows restoring to any point in time, not just hourly snapshots. More complex but essential for financial data (orders, payments).

- [ ] **Automated restore test** — Weekly cron: pick a random backup, restore it to a temp location, verify key metrics (table count, row count, recent order exists), report results. "Restore test: backup from June 20 restored successfully — 14 tables, 2,847 rows, all checks passed." Catches backup corruption before you need it. Delete temp DB after test.

- [ ] **Database migration to PostgreSQL (future)** — If the restaurant scales to multiple locations or needs concurrent write access, upgrade path from SQLite to PostgreSQL. `scripts/migrate_sqlite_to_pg.py` using pgloader or manual export/import. Keep this as a documented option, not an immediate task.

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

- [~] worker-1 **Ticket status notifications** — When admin approves/denies a ticket, employee sees a notification badge on their "📋 Requests" tab. In-tab alert banner: "Your time-off request was ✅ approved" or "❌ denied". Unread count badge on tab button.

- [ ] **API endpoints for ticket CRUD** — `POST /api/tickets/submit`, `POST /api/tickets/my`, `POST /api/tickets/queue`, `POST /api/tickets/respond`. Permission-gated.

### Priority: MEDIUM

- [ ] **Conflict detection for time-off requests** — When admin views a pending time-off, show warning if too many employees already approved for same dates.
- [ ] **Ticket filtering and search** — Admin queue: filter by type, status, employee, date range. Search by text.
- [ ] **Recurring time-off patterns** — Allow employee to request recurring time-off (e.g., "every Tuesday for the next 3 months").
- [ ] **Calendar view for time-off** — Visual calendar in admin showing who's off on which days.

### Priority: LOW

- [ ] **Issue/bug ticket triage labels** — Admin can tag issue tickets: "POS bug", "hardware", "menu error", "customer complaint", "other".
- [ ] **Ticket response templates** — Admin can save common response notes as templates.
- [ ] **Employee feedback analytics** — Aggregate feedback tickets by category over time.
- [ ] **Auto-approve for low-risk time-off** — Configurable rule: auto-approve time-off if requested >2 weeks in advance AND no other approvals for same date.

## Employee Pay Portal — Pay Stubs, History & Downloads (NEW — June 2026)

> Employees should be able to log in and see their own pay: hours worked, pay rate, gross/net, per-period and YTD totals, downloadable pay stubs, and a way to flag discrepancies.

### Key design decisions

- **Data source**: shift_log.json (clocked hours) × user pay_rate from users.json
- **No actual payroll processing** — this is informational/reporting, not ACH/bank integration
- **"Request Review"** feeds into the existing ticket system (type: `pay_review`)
- **Pay stubs are generated on the fly** from shift data — no separate pay_stubs.json needed

### Priority: HIGH

- [ ] **Employee "My Pay" tab** — New "💰 My Pay" tab visible to all logged-in employees. Shows three sections: **Current Period**, **Pay History**, **Year-to-Date** summary card.

- [ ] **Current pay period live tracker** — Shows current pay period date range, hours worked so far, pay rate, estimated gross pay so far. Auto-updates every 60 seconds while clocked in. Progress bar.

- [ ] **Pay history with period-by-period breakdown** — List of past pay periods with date range, total hours, pay rate, gross pay, shift count. Expand to detailed shift list.

- [ ] **Downloadable pay stub (PDF)** — "Download Pay Stub" button per pay period. Generates clean PDF with employee name, pay period dates, itemized shift list, total hours, pay rate, gross pay, YTD totals.

- [ ] **Pay history CSV export** — "Export My Pay History" button at bottom of Pay History.

- [ ] **"Request Pay Review" action** — "⚠️ Request Review" button on any pay period or shift. Opens pre-filled ticket form (type: `pay_review`).

### Priority: MEDIUM

- [ ] **Year-to-date (YTD) earnings card** — Summary card at top of My Pay showing YTD gross pay, YTD hours, average hours/week, average hourly rate.
- [ ] **Multi-rate support** — Per-shift or per-role pay rate override.
- [ ] **Pay stub email delivery** — Auto-email pay stub PDF to employee when admin marks a pay period as "paid".
- [ ] **Tip tracking in My Pay** — Aggregate tip data per pay period.

### Priority: LOW

- [ ] **Direct deposit info display** — Read-only display of employee's direct deposit details.
- [ ] **Pay comparison charts** — Bar chart in My Pay showing period-by-period gross pay for last 6 periods.
- [ ] **Tax withholding estimator** — Optional W-4 based tax estimates.

## Table-Side Digital Menu & Ad Display (NEW — June 2026)

> The existing `/tablet` page is a pure ad rotator. This needs to become a full table-side digital menu with ads as idle screensaver.

### What already exists
- `tablet.html` at `/tablet` — ad rotator with slideshow, swipe support, dot navigation
- `/api/ads/current` — returns active ads JSON
- `/api/items` (GET) — returns full menu with categories and items
- `/api/combos/list` (GET) — returns active combos
- Item images already supported

### Priority: HIGH

- [ ] **"View Menu" button overlay on ad screen** — Persistent floating button on the ad rotator: "🍽️ View Menu". When tapped, transitions to menu view. "← Back" returns to ad rotator.

- [ ] **Customer-facing menu display** — Full menu view with category tabs, item cards with images/descriptions/prices. Display-only, no ordering. Large touch targets (min 150px cards).

- [ ] **Item detail popup** — Tap item card → fullscreen overlay with large image, description, price, dietary badges, modifier options. Swipe left/right to browse category.

- [ ] **Combo/meal deal showcase section** — "🔥 Featured Combos" horizontal scrollable row with combo cards, child items listed, combo price with strikethrough savings.

- [ ] **Auto-return to ads after inactivity** — After 30-60 seconds of no touch interaction, auto-transition back to ad rotator with 5-second countdown toast.

- [ ] **Restaurant info bar** — Persistent footer: restaurant name, hours today, Wi-Fi info, "📞 Call Server" button (SocketIO `tablet_call_server` event), table number from URL param.

### Priority: MEDIUM

- [ ] **Dark/light theme toggle on tablet** — Sun/moon toggle in corner for customers.
- [ ] **Language toggle (EN/ES)** — UI labels translate, item names remain in admin's language.
- [ ] **Happy hour / specials badge on items** — Show "⚡ Happy Hour" badge with discounted price when scheduled pricing is active.
- [ ] **"Order This" QR code** — QR code icon on each item linking to online ordering page.

### Priority: LOW

- [ ] **Allergen filter toggle** — Filter button to show/hide items by allergen.
- [ ] **Nutritional info popup** — Optional per-item calorie/protein/carbs/fat display.
- [ ] **"Most Popular" badge** — Auto-calculated from most-ordered analytics.
- [ ] **Wake-on-proximity / screensaver mode** — Dim screen when no one nearby, brighten on motion.

## New Tasks (from Audit #7 — 2026-06-23)

- [x] worker-2 **HIGH: Kitchen offline degradation** — When WebSocket disconnects, the kitchen display silently stops showing new orders. Implement automatic polling fallback (every 8s) triggered by socket disconnect event, with visible "⚠️ Offline — updating every 8s" banner. Currently the main POS has polling fallback but kitchen view doesn't. This is critical for reliability during network blips.
  - Done: Added `startKitchenPolling()` / `stopKitchenPolling()` functions. Socket disconnect/connect_error triggers polling + offline banner. Socket connect stops polling + hides banner. `showKitchenView()` checks socket state before enabling polling. Animated red banner with i18n EN+ES. [worker-2]

- [ ] **MEDIUM: Table status overview dashboard** — Add a color-coded table grid view showing all tables with status (empty/occupied/order-in-progress/ready-to-serve/needs-bussing). Click a table to see its current tab/orders, mark it bussed, or transfer to another waiter. Most modern POS systems have this as the primary floor-plan view. Saves waiters from guessing which tables need attention.

|- [ ] **MEDIUM: Order transfer between waiters** — Add ability to transfer a table's active orders from one waiter to another via admin panel. Essential for shift changes, meal breaks, and when a waiter gets overwhelmed. Store `transferred_from` / `transferred_at` on order records for audit. Activity logging. Simple UI in admin tables section.

## New Tasks (from Audit #8 — 2026-06-23 Curation)

|- [ ] **MEDIUM: System-wide data backup & restore** — Currently only menu backups exist. Add full system backup endpoint (`POST /api/system/backup`) that creates a downloadable zip of all JSON data files (users, orders, items, configs, shifts, etc.). Add restore endpoint (`POST /api/system/restore`) to load from a backup zip. Admin UI in Settings panel with one-click backup download and file-upload restore. Auto-scheduled daily backup with configurable retention (keep last N backups). Critical for disaster recovery — without this, a disk failure or corruption means total data loss.

|- [ ] **MEDIUM: Customer online ordering portal** — Mobile-friendly standalone page (e.g. `/order`) for customers to browse menu, view item details + images, add to cart with modifiers/notes, and place pickup or delivery orders. Reuses existing backend (orders, items, combos, delivery addresses, payment processing). Integrates with existing pickup-display, kitchen queue, and order notification system. No staff intervention needed for order placement. Essential for any restaurant wanting to accept direct online orders without third-party delivery apps.

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

- [ ] **Touch target audit (all interactive elements ≥ 48px)** — Systematically check every button, input, select, and clickable element in index.html. Any element smaller than 48×48px on a tablet viewport is a fail. Common offenders: category tabs, quantity ± buttons, table selector dropdown, modifier checkboxes, timesheet sub-tabs. Fix by increasing min-height/min-width, adding padding, or wrapping in larger touch zones. This is the #1 real-world complaint: "I can't tap the right button."

- [ ] **Mobile viewport meta tag verification** — Confirm `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">` is present and correct. Test that the app doesn't zoom unexpectedly on input focus (iOS Safari notorious for this). Test on actual tablet dimensions: 768×1024 (iPad portrait), 1024×768 (iPad landscape), 800×1280 (Samsung tablet).

- [ ] **No hover-dependent interactions** — Tablets don't have hover. Audit the entire UI: any feature that requires hovering to reveal (tooltips, dropdown menus, hover cards, hover-to-expand) must have a tap alternative. Replace `:hover` CSS with `:active` or click-to-toggle patterns. Common offenders: admin sidebar sub-items, item detail tooltips, table tab hover states, shift edit buttons.

- [ ] **Scrollable areas with momentum scrolling** — All scrollable containers (item grid, order history, timesheet list, admin sections) must have `-webkit-overflow-scrolling: touch` and smooth momentum scrolling. Test on actual iPad — default scrolling is janky and feels broken. Add `overscroll-behavior: contain` to prevent page bounce when scrolling modals.

- [ ] **Form input optimization for tablets** — All number inputs should use `inputmode="numeric" pattern="[0-9]*"` to trigger the numeric keypad (not full keyboard) on tablets. PIN entry: `inputmode="numeric"` + `autocomplete="off"`. Quantity inputs: `type="number"` with min/max. Date inputs: native `<input type="date">` which renders as a touch-friendly date picker on tablets.

- [ ] **Orientation handling (portrait + landscape)** — Restaurant tablets get mounted in both orientations (landscape on counter stands, portrait when handheld). Test every view in both orientations. Ensure the POS item grid, kitchen display, and admin panels don't break or have hidden content. Use CSS media queries: `@media (orientation: portrait)` and `@media (orientation: landscape)`. Kitchen display especially — landscape is standard for wall-mounted screens.

- [ ] **Fast tap response (no 300ms delay)** — Mobile browsers add a 300ms delay to distinguish tap from double-tap. This makes the POS feel sluggish. Fix with: `touch-action: manipulation` on all interactive elements, or use a fastclick polyfill. The difference between "instant" and "300ms delay" is the difference between "professional POS" and "janky web app."

### Priority: HIGH — Real-World Workflow Gaps

- [ ] **Walkthrough: full shift lifecycle** — Clock in → take 10 orders across 5 tables → split payment on 2 → apply discount → add tips → clock out. Time the whole flow. Identify every place where the user has to stop and think, tap extra times, or work around the UI. Report friction points. Common issues: too many taps to switch tables between orders, can't easily split a check after items are rung up, tip entry should be at payment screen not cart.

- [ ] **Walkthrough: closing shift reconciliation** — Run the cash register closing flow: count drawer → enter expected cash → system compares to actual → variance report → clock out. Test with mismatches: $20 over, $5 short. Does the system flag these clearly? Does it force a reason for variance? Is there a paper trail?

- [ ] **Walkthrough: refund/void flow** — Ring up an order → submit → customer changes mind → void entire order. Ring up → submit → customer says "no onions" → refund single item. Test both. Does the refund button appear quickly? Is the reason required? Are refunded items removed from inventory? Is the refund visible in stats/reports?

- [ ] **Error state testing** — Test every endpoint with bad data: missing fields, wrong types, oversized values, SQL injection attempts. The app should return clear error messages, not 500 errors or blank screens. Common gaps: no try/catch on JSON.parse in frontend, no 404 handling for deleted items, no fallback when a JSON file is corrupted, no loading states during API calls.

- [ ] **Concurrent use testing** — Two waiters on separate tablets, same table. Both add items simultaneously. One submits → other's cart is now stale. Does the system handle this gracefully? Show "Table 5 has a new order since you started — refresh?" Also: two waiters clocking in/out simultaneously, two admins editing the same item. JSON file writes are atomic on Linux but race conditions still exist.

- [ ] **Offline → online recovery flow** — Turn off WiFi → ring up orders (offline queue) → turn WiFi back on. Verify: queued orders appear in correct order, payment splits preserved, tips preserved, table numbers preserved. Verify the offline badge showed during offline, synced badge showed during sync, clear badge after sync. Test with 10+ queued orders (not just 1-2).

### Priority: MEDIUM — Missing Production Features

- [ ] **Printer integration (ESC/POS thermal printers)** — Most restaurants use Epson TM-T88 or similar thermal receipt printers. Add optional printer support via `/api/print/receipt` endpoint that formats a receipt as ESC/POS commands and sends to a printer IP. Configurable printer IP in admin. Fallback: generate a clean HTML receipt for browser printing. Without printer support, the system can't print physical receipts — a dealbreaker for most restaurants.

- [ ] **Sound alerts for kitchen display** — Kitchen display already has a 3-note alarm. Verify it works on tablets (requires user gesture to unlock audio on iOS/Safari). Add a "first interaction" screen that enables audio: "Tap anywhere to enable kitchen alerts." Check volume levels — should be audible in a noisy kitchen but not deafening. Configurable sound on/off and volume in admin.

- [ ] **Idle timeout + auto-lock** — After 5 minutes of inactivity on the POS screen, auto-lock and require PIN re-entry. This prevents unauthorized use when a waiter walks away from the tablet. Configurable timeout (1-30 minutes). Show a countdown warning: "Locking in 30 seconds... tap to stay." Also: clock-out auto-lock — when an employee clocks out, force logout on that device.

- [ ] **Multi-language completeness check** — Audit the i18n keys. Are ALL user-visible strings translated to Spanish? Check toast messages, error messages, button labels, admin section headers, timesheet labels, security settings, backup codes UI. Common gap: error messages from the backend are English-only. Add server-side translation for common error messages.

- [ ] **Performance on low-end tablets** — The single-page index.html is 500KB+. On a $100 Android tablet with 2GB RAM, this might be slow. Profile: page load time, time-to-interactive, memory usage. Optimize: lazy-load Chart.js (only on stats tab), defer non-critical CSS, split kitchen display into separate lightweight page. Target: <3s load on 4G, smooth 60fps scrolling.

- [ ] **Accessibility basics (screen reader, contrast)** — This will be used by real employees, some with disabilities. Minimum: all buttons have aria-labels, form inputs have associated labels, color is never the only indicator (add icons alongside color badges), contrast ratio ≥ 4.5:1 for text. Test with VoiceOver (iPad) or TalkBack (Android). This is often legally required for workplace software.

### Priority: LOW — Polish & Professionalism

- [ ] **Loading skeleton screens** — Replace "Loading..." text with skeleton screens (animated gray placeholders) for: item grid, order history, timesheet, pay period. Makes the app feel 2x faster even if load time is the same. Perceived performance is real performance in a busy restaurant.

- [ ] **Smooth page transitions** — Currently switching between POS / History / Admin tabs is instant (jarring). Add subtle transitions: slide-left for forward navigation, slide-right for back, fade for modals. 150ms duration — fast enough to not feel slow, present enough to feel polished.

- [ ] **Haptic feedback on order submit** — On supported devices (iOS, modern Android), trigger a short vibration when an order is successfully submitted. `navigator.vibrate(50)`. This gives the waiter physical confirmation without looking at the screen — they can keep eyes on the customer.

- [ ] **Dark mode on the tablet menu page** — The `/tablet` customer-facing menu should respect the POS dark theme. Currently it's a separate page — verify it renders correctly in dark mode. Add theme toggle for customers who prefer light.

- [ ] **App icon + splash screen for PWA** — When installed to home screen (Add to Home Screen on iPad), the app should show a proper icon and splash screen. Verify manifest.json has all icon sizes (192px, 512px). Add `apple-touch-icon` and `apple-mobile-web-app-capable` meta tags for iOS.

## Security Operations Center — Owner Security Dashboard & Monitoring (NEW — June 2026)

> The owner needs a single pane of glass to see what's happening security-wise: who's logging in from where, what's being blocked, what looks suspicious. This is a security operations dashboard — not vulnerability scanning (that's the Security Sentinel's job), but live monitoring, threat response, and safety rails.

### Data Model

New `security_config.json`:
```json
{
  "ip_blocklist": ["192.168.1.100", "10.0.0.5"],
  "ip_allowlist": [],                    // if non-empty, ONLY these IPs can access
  "auto_block_threshold": 10,            // auto-block IP after N failed logins in 5 min
  "auto_block_duration_minutes": 60,     // how long auto-blocks last (0 = permanent)
  "geo_alert_countries": [],             // alert on logins from these countries
  "anomaly_hours_start": "23:00",        // flag logins between these hours
  "anomaly_hours_end": "05:00",
  "anomaly_rapid_orders_threshold": 10,  // flag if >N orders in 5 min from same user
  "anomaly_large_order_threshold": 500,  // flag orders over $N
  "require_2fa_for_external_ip": false   // force 2FA when logging in from non-local IP
}
```

New `security_events.json` (append-only log of flagged events):
```json
[{
  "id": "SEC-001",
  "timestamp": "2026-06-23T14:30:00",
  "event_type": "ip_blocked | failed_login_spike | anomalous_login | suspicious_order | geo_alert | rate_limit_triggered",
  "severity": "critical | high | medium | low",
  "user_id": "1234",
  "ip": "203.0.113.42",
  "details": "10 failed logins in 3 minutes from 203.0.113.42 — auto-blocked for 60 min",
  "resolved": false,
  "resolved_by": null,
  "resolution_note": null
}]
```

### Priority: HIGH

- [ ] **IP tracking on all requests** — Capture `request.remote_addr` on every Flask request. Add `ip_address` field to activity_log entries for login, clock-in, order submit, and any admin action. Store in `login_attempts.json`: `{user_id, ip, timestamp, success, user_agent}`. This is the foundation — without IP tracking, none of the below works. Handle `X-Forwarded-For` header for proxied requests (VPS behind nginx/Cloudflare).

- [ ] **Owner security dashboard — "🛡️ Security" admin tab** — New admin tab with real-time security overview:
  - **Live feed**: scrollable list of recent security events (logins, blocks, flags) — newest first, auto-refresh every 30s
  - **Summary cards**: "23 logins today (2 failed)", "3 IPs blocked", "1 active anomaly", "0 critical alerts"
  - **Login map** (optional, if GeoIP set up): world map with dots for login locations
  - **Active sessions**: who's logged in right now, from which IP, for how long
  - **Blocked IPs list**: table with IP, reason, blocked date, expires, "Unblock" button
  - Permission-gated: `view_stats` + owner-only for block/unblock actions

- [ ] **IP blocklist management** — `POST /api/security/blocklist/add` and `/remove` endpoints. Owner adds IP to blocklist → all requests from that IP get 403 Forbidden. Auto-block: after `auto_block_threshold` failed logins from same IP in 5 minutes, auto-add to blocklist for `auto_block_duration_minutes`. Auto-block events logged as security_events. Owner can set permanent block ("until manually removed"). IP allowlist mode: if `ip_allowlist` is non-empty, ONLY those IPs can access — everything else gets 403. This is the nuclear option for "only allow the restaurant's static IP."

- [ ] **Anomaly detection engine** — Background thread (or per-request check) that flags unusual patterns:
  - **Off-hours login**: login between `anomaly_hours_start` and `anomaly_hours_end` → flag as MEDIUM, log to security_events, show yellow banner on dashboard: "⚠️ Carlos logged in at 3:14 AM"
  - **Failed login spike**: >5 failed logins from same IP in 5 minutes → flag as HIGH, auto-block if enabled
  - **Rapid orders**: >10 orders in 5 minutes from same user → flag as MEDIUM (possible fraud or "fat finger" auto-submit)
  - **Large order**: single order over $500 → flag as LOW (just a heads-up — "Large order: $847.50 by Waiter John — review?")
  - **New IP for user**: user logs in from IP they've never used before → flag as MEDIUM ("Carlos logging in from new IP: 45.67.89.10 — account compromised?")
  - **Simultaneous logins**: same user logged in from 2 different IPs → flag as HIGH ("Carlos logged in from 192.168.1.5 AND 45.67.89.10 simultaneously")
  - All flags go to `security_events.json` with severity. Owner sees count badge on Security tab.

- [ ] **Account blocking & force logout** — In User Management, owner can click "🔒 Block Account" on any user. This sets `banned: true` (already exists), logs reason, and immediately invalidates all their sessions. Also: "Force Logout" button that ends all active sessions for a user without banning them (useful for "your session is acting weird, log out and back in"). `POST /api/security/block_user` and `/unblock_user` endpoints. Blocked users get "Account blocked — contact owner" on login attempt. Show block reason to the user.

### Priority: MEDIUM

- [ ] **Security event investigation workflow** — Owner clicks any flagged event in the dashboard → detail view with: full event data, related events (same IP, same user, same time window), timeline of that user's actions leading up to the event, and action buttons: "✅ Dismiss" (mark resolved, add note), "🔒 Block IP" (add to blocklist), "🔒 Block User" (ban account), "📋 Escalate" (mark as critical, notify Discord). This turns the dashboard from "here's a list of scary things" to "here's what to do about them."

- [ ] **Discord security alerts** — Critical/HIGH severity events fire a Discord notification immediately: "🚨 SECURITY: 10 failed logins from 203.0.113.42 — IP auto-blocked for 60 min." MEDIUM events batch into a digest every hour. Configurable per severity in security_config. The owner should know about a brute-force attack within seconds, not hours.

- [ ] **GeoIP lookup for login locations** — Optional: install `geoip2` Python library + free MaxMind GeoLite2 database. Resolve IP → country/city on login. Show in login feed: "Carlos logged in from Brownsville, TX, US 🇺🇸". Alert on logins from unexpected countries (configurable `geo_alert_countries`). Adds context to the login map on the dashboard. This is what makes the owner go "wait, why is someone logging in from Russia?"

- [ ] **Rate limiting middleware** — Flask before_request hook that enforces:
  - Global: max 60 requests/minute per IP (prevents basic DoS)
  - Login: max 10 attempts/minute per IP (already covered by anomaly detection)
  - API: max 30 requests/minute per IP for order-heavy endpoints
  - Returns 429 with `Retry-After` header
  - Configurable in security_config
  - Whitelist localhost/192.168.x.x so internal traffic isn't rate-limited

- [ ] **Security event retention & cleanup** — security_events.json will grow forever. Auto-purge: LOW severity >30 days, MEDIUM >90 days, HIGH/CRITICAL kept forever. Configurable retention in security_config. Export: "Download Security Log" button exports filtered events as CSV for external audit.

- [ ] **Suspicious order pattern detection** — Beyond the anomaly engine basics, add order-specific heuristics:
  - Same item ordered 50+ times in one order (possible testing/abuse)
  - Order total is negative (discount abuse)
  - Refund rate per employee is >20% (possible theft — "ring up, take cash, refund later")
  - Multiple high-value refunds in short window
  - These flag as MEDIUM security events for owner review

### Priority: LOW

- [ ] **Security health score** — Dashboard shows a computed score (0-100) based on: 2FA adoption rate, failed login rate, blocked IP count, unresolved security events, rate limit triggers. "Security Score: 87/100 — Good. Enable 2FA for 3 remaining admins to reach 95+." Gamifies security for the owner — gives them a clear number to improve.

- [ ] **Audit export for compliance** — One-click "Export Security Report" that generates a PDF/CSV with: all security events in date range, blocked IPs, active user sessions, failed login summary, anomaly detection summary. Useful if the owner needs to prove to an insurer or franchisor that they have security controls.

- [ ] **Honeypot endpoints** — Add fake admin endpoints (/admin, /wp-admin, /.env) that log and auto-block any IP that hits them. Real users never hit these — only bots and attackers. Instant permanent block. This is a low-effort, high-signal security measure.

- [ ] **Two-person rule for sensitive actions** — Require a second admin/owner approval for: deleting all orders, wiping the database, changing bank/payment config, disabling all 2FA. Shows "⚠️ This action requires a second admin to approve." Second admin enters their PIN to confirm. Prevents a single compromised admin account from nuking the system.

## Multi-Tenant Platform — Business Groups, Developer Account & White-Label Hosting (NEW — June 2026)

> This system is going from "one restaurant's POS" to "a platform that hosts multiple independent businesses." Each business gets its own isolated tenant with its own owner, employees, menu, orders, shifts — completely separate from other businesses. Jay (the developer/platform owner) has a **super admin** account to create, manage, and monitor all businesses. This is the foundation for selling POS as a service.

### Architecture Overview

```
SUPER ADMIN (Jay — developer account)
├── Business: "Maria's Tacos" (business_id: marias-tacos)
│   ├── Location: "Main Street" (location_id: main)
│   │   ├── Owner: Maria (PIN 2222)
│   │   ├── Admin: Carlos
│   │   └── Employees: Juan, Rosa, Luis
│   └── Location: "2nd Ave" (location_id: second-ave)
│       ├── Owner: Maria (same owner, cross-location)
│       └── Employees: Pedro, Ana
├── Business: "Bob's Burgers" (business_id: bobs-burgers)
│   └── Location: "Downtown" (single location)
│       ├── Owner: Bob (PIN 3333)
│       └── Employees: Tina, Gene, Louise
└── Business: "Sakura Sushi" (business_id: sakura-sushi)
    └── Location: "Uptown"
        ├── Owner: Kenji (PIN 4444)
        └── Employees: Yuki, Haru
```

### Data Isolation Strategy

**Phase 1 (JSON — current):** Directory-per-tenant
```
/data/tenants/<business_id>/<location_id>/
  users.json         # scoped to this location
  items.json         # shared across business locations? or per-location?
  orders.json
  shift_log.json
  inventory.json
  ...all other JSON files...
/data/global/
  businesses.json    # all registered businesses
  super_admins.json  # platform-level admin accounts
  platform_config.json
```

**Phase 2 (SQLite — future):** `business_id` + `location_id` columns on every table, or separate `.db` per business for stronger isolation.

### Key design decisions
- **business_id**: URL-safe slug (e.g., `marias-tacos`), used in login URL
- **location_id**: within a business, for multi-location chains (e.g., `main`, `downtown`)
- **Single business = single owner minimum**, can have multiple admins
- **Locations share menu items by default** (set once, appears everywhere), but can override per-location
- **Employees scoped to location** (Juan works at Main Street, can't accidentally clock in at 2nd Ave)
- **Super admin sees everything** — all businesses, all data, can impersonate any owner for support

### Priority: HIGH — Multi-Tenant Foundation

- [ ] **Global data model + platform config** — Create `/data/global/businesses.json`:
```json
{
  "marias-tacos": {
    "business_name": "Maria's Tacos",
    "business_id": "marias-tacos",
    "status": "active | suspended | pending_approval",
    "owner_user_id": "2222",           // the business owner's PIN (scoped to this business)
    "owner_name": "Maria Garcia",
    "owner_email": "maria@email.com",
    "owner_phone": "956-555-0100",
    "created_at": "2026-06-23",
    "plan": "free | basic | pro",     // for future billing
    "max_locations": 3,
    "max_users": 15,
    "features_enabled": ["pos", "kitchen", "timesheet", "inventory"],
    "locations": {
      "main": {"name": "Main Street", "address": "123 Main St", "timezone": "America/Chicago"},
      "second-ave": {"name": "2nd Ave", "address": "456 2nd Ave", "timezone": "America/Chicago"}
    }
  }
}
```
Create `/data/global/super_admins.json`: `{ "1111": {"name": "Jay", "role": "super_admin", "permissions": ["*"]} }`
Super admin PIN is separate from any business PIN. Super admin can create businesses, approve registrations, manage platform settings.

- [ ] **Tenant-aware Flask middleware** — `before_request` hook that resolves the current business/location context:
  - Subdomain routing: `marias-tacos.posapp.com` → business_id = `marias-tacos`
  - URL param fallback: `posapp.com/login?business=marias-tacos` → business_id = `marias-tacos`
  - Login form: user enters business_id + PIN (or selects business from dropdown if multiple)
  - After login: all API calls are scoped to `business_id` + `location_id` from session
  - All `load_json_data()` and `save_json_data()` calls route to `/data/tenants/<business_id>/<location_id>/` instead of root
  - Super admin bypass: if session is super_admin, routes to `/data/global/` or can switch into any business

- [ ] **Super admin dashboard — "🏢 Platform" view** — New admin section visible ONLY to super admins:
  - **Business list**: table of all businesses with status (active 🟢, suspended 🔴, pending 🟡), plan, user count, last active date
  - **Create business**: form with business_id (slug), business name, owner name, owner email, plan tier, max locations/users
  - **Approve/deny registration**: if self-registration is enabled, new businesses go to `pending_approval` status. Super admin reviews and approves/denies with reason note. Approved → business gets created, owner gets notified.
  - **Suspend/unsuspend**: suspend a business (owner can't log in, employees can't clock in, customers see "temporarily unavailable"). Unsuspend restores. Reason required, logged.
  - **Impersonate**: "Login as Owner" button → super admin is dropped into that business's POS as if they were the owner. Activity logged as `super_admin_impersonate`. Essential for support ("I can't figure out how to set up my menu" — Jay logs in as them and shows them).
  - **Platform analytics**: total businesses, total users, total orders across all businesses, MRR (if billing added later), active businesses in last 7 days

- [ ] **Business registration flow (self-serve)** — Public registration page at `/register`:
  - Form: business name, desired business_id (slug, auto-suggested from name, validated for uniqueness), owner name, email, phone, password/PIN
  - CAPTCHA or email verification to prevent bot registrations
  - Submit → status = `pending_approval` → notification to super admin (Discord + dashboard badge)
  - Super admin approves → business directory created, owner account created, email sent: "Your POS system is ready! Log in at marias-tacos.posapp.com"
  - Super admin denies → reason stored, email sent: "Your registration was not approved. Reason: [custom message]"
  - Configurable in platform_config: `"allow_self_registration": true/false` — super admin can toggle off if getting spam

- [ ] **Per-business isolation enforcement** — This is CRITICAL for production:
  - Every API endpoint MUST verify business context from session before reading/writing ANY data
  - Business A can NEVER access Business B's users, orders, shifts, items, etc.
  - `check_perm()` now also checks business scope — user's PIN is only valid within their business
  - PINs can be reused across businesses (Maria's employee 1234 is different from Bob's employee 1234) because they're scoped to business_id
  - Super admin bypass for support (logged and rate-limited)
  - Test: create two businesses → log in as Business A → try to curl Business B's endpoint → must get 403

### Priority: HIGH — Multi-Location Support

- [ ] **Location selector in POS header** — After login, if business has multiple locations, show a location dropdown/picker. "You're at: Main Street ▼". Switching locations reloads POS with that location's data. Defaults to last-used location (stored per user in localStorage). Employees are typically assigned to one location — if they try to access another, require manager override.

- [ ] **Cross-location menu sharing with overrides** — Default: menu items (items.json) are shared at the business level (all locations see the same menu). Admin can toggle per-item: "Available at: All locations / Main Street only / 2nd Ave only." Per-location price override: "Burger: $10.99 at Main, $12.99 at 2nd Ave (higher rent area)." This gives flexibility without duplicating the entire menu per location.

- [ ] **Cross-location reporting for owners** — If owner has multiple locations, Timesheet and Stats tabs get a "Location: All / Main Street / 2nd Ave" filter. Owner can see combined revenue, combined labor hours, or per-location breakdown. "Maria wants to know: did Main Street or 2nd Ave do better this week?" One-click comparison.

- [ ] **Location-specific settings** — Per-location overrides in config: tax rate (different cities), operating hours, timezone, printer IP, kitchen display URL. Business-level defaults with per-location overrides. Stored in business-level config, keyed by location_id.

### Priority: MEDIUM — Platform Management

- [ ] **Super admin business config templates** — When creating a new business, select a template: "Full-Service Restaurant" (POS + kitchen + tables + timesheet), "Quick-Service" (POS + kitchen only, no tables), "Coffee Shop" (POS + loyalty + inventory, simplified). Templates pre-configure which features are enabled, default categories, and roles. Speeds up onboarding from 30min to 2min.

- [ ] **Usage analytics & limits** — Track per-business: monthly order count, storage used, API requests, active users. If a business exceeds plan limits, show warning banner to owner: "You've reached your plan limit of 15 users. Upgrade to add more." Super admin sees usage across all businesses. Foundation for future billing.

- [ ] **Business migration/export** — If a business wants to leave the platform, super admin can export ALL their data as a zip: all JSON/SQLite files, uploaded images, config. `POST /api/platform/export_business` with business_id. Also: "Clone Business" to create a test copy for development/troubleshooting without touching live data.

- [ ] **Platform-wide announcements** — Super admin can post an announcement that appears as a banner on ALL business dashboards: "🚧 Scheduled maintenance: Sunday 2am-4am CT. System will be unavailable." or "🎉 New feature: 2FA now available! Enable in Security settings." Dismissible per user. Stored in platform_config with start/end dates.

### Priority: LOW — White-Label & Branding

- [ ] **Per-business branding** — Each business can customize: logo (shown in POS header), primary color (replaces accent color in CSS), business name in browser tab title. Loaded from business config. This makes each POS feel like the restaurant's own system, not a generic platform. "Maria's Tacos wants their green brand color, not our default red."

- [ ] **Custom domain support** — Business can point their own domain: `pos.mariastacos.com` → CNAME to platform. Platform handles SSL via Let's Encrypt. Configurable in business settings. Super admin approves custom domains to prevent abuse.

- [ ] **Business-facing status page** — `status.posapp.com` showing platform uptime, incident history, scheduled maintenance. Automatic — if the Reliability Bot detects an outage, it updates the status page. Gives business owners confidence that "it's not just me, the platform is down."

- [ ] **Multi-language per business** — While the platform supports EN+ES, some businesses may want additional languages (French, Chinese, Arabic). Per-business language config: enabled languages, default language. Menu items support translations per language. This is for international deployment.

## Done

|- [x] **2FA setup endpoint + QR code generation** — `POST /api/auth/2fa/setup`: generates TOTP secret via pyotp, stores on user, returns provisioning_uri + QR code data URI. 409 if 2FA already enabled. [worker-3]
|- [x] **Add scheduled_start field to users.json** — Backend: `scheduled_start` field in user data model (default null), exposed via `/api/users`, accepted in `/api/add_user`, new `POST /api/users/update_scheduled_start` endpoint with permission-gating and activity logging. Frontend: display in user management list, edit button (prompt for HH:MM), time input in add-user form, clear support. i18n EN + ES. [worker-3]
|- [x] **Scheduled start admin UI in User Management** — "Scheduled Start" time input per user (type="time") in add user form. Display + edit button in user entry cards. Stored/loaded from users.json. [worker-3]
|- [x] **Shift notes on clock-out** — When clocking out, optional textarea for shift notes. Stored as `notes` field on shift record. Displayed in timesheet view. Admin can also add notes. [worker-3]
- [x] **Admin shift edit / correction with audit trail** — `POST /api/clock/edit` endpoint with full audit trail. [worker-1]
- [x] **Add auto-table suggestion for waiters** — Auto-select last used table per user in localStorage. [worker-1]
- [x] **Add employee clock-in/clock-out system** — `/api/clock/in`, `/api/clock/out`, `/api/clock/status`, `/api/admin_shifts`, `/api/export/shifts_csv`. Punch clock button in POS header. Activity logging. i18n EN + ES. [worker-3]
- [x] **Add combo/meal deal builder** — Fixed-price combo deals. Admin builder UI. One-tap add to cart. i18n EN + ES. [worker-2]
- [x] **Add item visibility toggle** — Active/inactive toggle per item. Hidden items don't appear in POS/kiosk/search. i18n EN + ES. [worker-1]
- [x] **Add service charge / auto-gratuity** — Configurable auto-gratuity settings. i18n EN + ES. [worker-3]
- [x] **Add course/meal prep timing** — Appetizer/main/dessert course badges. [worker-3]
- [x] **Add recent-order quick-access on POS tab** — Last 5 orders for the waiter on POS tab. [worker-1]
- [x] **Add item images to grid cards** — Image URLs on items, thumbnails on grid/kitchen/kiosk. [worker-2]
- [x] **Add customer profile management (CRM)** — Extended customer data, endpoints, admin CRM tab. [worker-3]
- [x] **Add quick-change cash calculator** — Cash payment amount tendered + auto-change calculation. [worker-1]
- [x] **New endpoint `POST /api/clock/flag_late`** — Admin manually flags a shift as late with `late_minutes`, resets `late_excused` to false. Accepts `shift_index`, `late_minutes`, optional `note`. Logs `late_flagged` activity with old→new values and admin PIN. Permission-gated `view_timesheet`. [worker-3]
|- [x] **Add item modifier support** — Variants, modifiers, customizations with modifier editor. [worker-2]
|- [x] **New endpoint `POST /api/clock/excuse_late`** — Admin sets `late_excused = true` on a completed shift. Accepts `shift_index`, `adminPin`, optional `note`. Permission-gated (`view_timesheet`). Activity logged. [worker-1]
|- [x] **Admin/owner 2FA management & reset** — `POST /api/users/disable_2fa` (requires reason, manage_users, only owner on admins) and `POST /api/users/regenerate_backup_codes` endpoints. `GET /api/users` now returns `totp_enabled`. Frontend: 🔒/🔓 2FA status badge in user cards, Disable 2FA + Regenerate Codes buttons (manage_users-gated), modal showing new backup codes. i18n EN + ES. Activity logging for all actions. [worker-2]
|- [x] worker-3 **JSON backup script** — Created `/root/pos-system-work/scripts/backup_json.py` with validation, timestamped backups, tar.gz archiving, anomaly detection, dry-run and quiet modes.
|- [x] worker-1 **Employee ticket submission UI** — New "📋 Requests" tab with ticket submission form (time-off, issue, feedback, other), adaptive fields, "My Tickets" list with status badges. Backend: tickets.json data store, 4 API endpoints (submit, my, queue, respond), activity logging, validation. Full i18n EN + ES.
||- [x] worker-3 **Smart date picker for time-off requests** — Business day calculation (Mon-Fri), past-date validation, 30-day limit with override checkbox, overlap detection against existing pending/approved requests. Server-side and client-side validation. Backend: `business_days` field, overlap check, date validation. Frontend: validation messages, override checkbox, business day display in tickets. i18n EN + ES.

|## Done (older)

<details>
<summary>39 completed tasks from earlier development</summary>

|- [x] **Multi-language support** — English + Spanish with browser detection, toggle button. [worker-2]
|- [x] **Kitchen display queue system** — Full cook view: claim/complete/cancel, 8s auto-refresh, sound alerts, fullscreen. [worker-3]
|- [x] **Order notes field** — Per-item and per-order notes. [worker-1]
|- [x] **Receipt printing simulation** — Thermal printer CSS. [worker-2]
|- [x] **Discount/coupon code system** — Percentage and flat discounts. [worker-1]
|- [x] **Sales tax calculation support** — Global/per-category/per-item tax rates. [worker-2]
|- [x] **Touch-optimized item grid** — Category tabs, responsive grid. [worker-1]
|- [x] **Most-ordered items analytics** — `/api/analytics/most_ordered`. [worker-3]
|- [x] **Peak hour sales analytics** — `/api/analytics/hourly_sales`. [worker-2]
|- [x] **Daily revenue tracking** — `/api/analytics/daily_revenue`. [worker-1]
|- [x] **PWA manifest + service worker** — Installable app. [worker-3]
|- [x] **Loyalty points system** — Points earning/redeeming per customer. [worker-3]
|- [x] **Admin dashboard with Chart.js analytics** — Charts for daily revenue, payment methods, item trends. [worker-2]
|- [x] **Scheduled pricing (happy hour, daily specials)** — Time-based discount rules. [worker-1]
|- [x] **Fix order history for all users (BUG)** — New `/api/orders/list` endpoint. [worker-3]
|- [x] **Add auto-save draft orders to localStorage** — Cart auto-save with restore prompt on page load. [worker-1]
|- [x] **Per-user pay rate field** — Add `pay_rate` (hourly, float) to user profile. Shown in user management, timesheet/pay-period summary, and CSV/PDF exports. [worker-1]
|- [x] **Add item search/filter in POS item grid** — Real-time search bar. i18n EN + ES. [worker-2]
|- [x] **Add WebSocket support for real-time updates** — Flask-SocketIO with polling fallback. [worker-1]
|- [x] **Add delivery address management** — Delivery form, saved addresses API. i18n EN + ES. [worker-3]
|- [x] **Add customer-facing display mode** — `/customer-display` page with large-print order summary. [worker-1]
|- [x] **Add dark/light theme toggle** — CSS variables, localStorage persistence, toggle button. [worker-2]
|- [x] **Fix verify_admin blocking owners from tax/discount endpoints** — Replaced `verify_admin()` with `check_perm()`. [worker-2]
|- [x] **Fix menu history frontend parsing** — Changed `data.history` to `data.backups`. [worker-3]
|- [x] **Add quick-order favorites per user** — `favorites.json` data store with save/list/delete. [worker-1]
|- [x] **Add item popularity trend chart** — `/api/analytics/item_trends` comparing 7d vs prior 7d. [worker-3]
|- [x] **Add offline order queuing** — `/api/health` + `/api/sync_orders`, localStorage queue, auto-sync. [worker-3]
|- [x] **Refund/void order functionality** — POST /api/orders/refund with reason tracking. [worker-1]
|- [x] **Table tab management** — Checkout/close tab, tab history, quick-add. [worker-3]
|- [x] **Add inventory tracking** — Stock levels decremented on order, low-stock alerts. [worker-1]
|- [x] **Add split-payment support** — Multiple payment methods per order. [worker-3]
|- [x] **Add tip calculation UI** — Percentage buttons in POS cart. [worker-2]
|- [x] **Add employee performance dashboard** — Per-employee metrics with date filtering. [worker-2]
|- [x] **Add waste tracking** — Waste log with reason, estimated cost. [worker-2]
|- [x] **Kitchen queue audit & optimize** — Color-coded age, priority badge, quick-claim, alarm sound. [worker-1]
|- [x] **Table management system** — Admin assigns tablets to tables, running tabs. [worker-3]
|- [x] **Drive-through order display** — Drive-through TV view at `/drivethrough`. [worker-1]
|- [x] **Granular role/permission system** — Three-tier roles with 10 granular permissions. [worker-2]
|- [x] **Menu version history with restore** — Auto-backup, owner restores any day's menu. [worker-3]

</details>

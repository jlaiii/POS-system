# POS System — Smart Task Queue

> Auto-managed by 3 Hermes Worker Crons (every 30 min each, staggered claims).
> Workers use `[~]` to claim tasks before working. Never pick a claimed task.
> Last updated: 2026-06-23 (audit #7 — system audit)

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
- [ ] Add `scheduled_start` field to each user in `users.json` — a string like `"09:00"` (24h format, local time). This is the time the employee is expected to clock in each workday. If unset or null, no lateness check for that user.
- [ ] Admin can set this in the User Management panel — add a "Scheduled Start" time input per user (type="time"). Stored and loaded from `users.json`.

#### Auto-late detection on clock-in
- [ ] `POST /api/clock/in`: after recording the clock-in, compare the actual `clock_in_time` against the user's `scheduled_start` for today.
- [ ] If `scheduled_start` is set: parse today's date + scheduled time → `scheduled_dt`. If `clock_in_time > scheduled_dt + grace_period`, flag the shift as late.
- [ ] Grace period: configurable in admin (default 5 minutes). Stored in a new `timesheet_config.json` file: `{ "late_grace_minutes": 5 }`. Admin can change via a new `POST /api/timesheet/config` endpoint (read/write). Anyone within grace period is on-time, not late.
- [ ] Calculate `late_minutes = round((clock_in_time - scheduled_dt).total_seconds() / 60)`. Store on the active shift.

#### Late flag on shift records
- [ ] Add new fields to shift records in `shift_log.json` and `active_shifts`:
  - `scheduled_start`: string or null (the expected start time that was checked against)
  - `late_minutes`: int or null (minutes past scheduled + grace. null = on time or no schedule. >0 = late)
  - `late_excused`: boolean (default false, admin can toggle — see below)
  - `late_note`: string or null (reason if provided at clock-in, or admin note)
- [ ] `POST /api/clock/in` response includes `late_minutes` and `late_excused` so the clock-in toast can say "⚠️ Clocked in 23 minutes late" when applicable.

#### Admin late shift flagging & excuse
- [ ] New endpoint `POST /api/clock/excuse_late`: admin sets `late_excused = true` on a completed shift. Accepts `shift_index` (position in shift_log array), `adminPin`, optional `note`. Requires `view_timesheet` permission.
- [ ] New endpoint `POST /api/clock/flag_late`: admin manually flags a shift as late (even if auto-detection didn't catch it — e.g., no scheduled time set). Sets `late_minutes` to admin-provided value. Requires `view_timesheet` permission.
- [ ] Both endpoints log to activity_log: `late_excused` or `late_flagged` with old→new values and admin PIN.
- [ ] UI: in the Employee Shifts timesheet view, late shifts get a red 🕐 badge showing minutes late. Excused late shifts get a gray 🔕 badge instead. Admin clicks the badge to toggle excuse/flag via a small popover with note field.

#### Admin shift time edit / correction (completes + expands the existing task)
- [x] `POST /api/clock/edit`: admin can edit clock_in_time and/or clock_out_time on any completed shift. Accepts `shift_index` (position in shift_log array), `new_clock_in` (ISO string or null to keep original), `new_clock_out` (ISO string or null), `adminPin`, `reason` (required — text). Requires `view_timesheet` permission.
- [x] Recalculates `duration_hours` from edited times. Re-runs late detection on the edited `clock_in_time` (so if admin fixes a clock-in that was actually on-time, the late flag auto-clears).
- [x] Stores edit audit trail on the shift record under a new `edits` array.
- [x] Edited shifts show an ⚠️ "Edited" badge in the timesheet UI. Clicking the badge shows the full edit history (timestamps, who, reason, old→new values).
- [x] Activity log records `shift_edited` with full details.
- [x] **Clock-in for someone else's shift**: if admin needs to clock someone in retroactively, admin uses `/api/clock/edit` to set the clock_in_time on the shift record after the fact. System does NOT create a new shift — it edits the existing one.

#### Late clock-in reason (employee self-report)
- [ ] The clock-in POST body accepts an optional `late_note` field. If an employee knows they're late, they can include a reason: "Traffic on I-69", "Flat tire", etc.
- [ ] This is stored as `late_note` on the shift record.
- [ ] Displayed in the timesheet view next to the late badge.

#### Frontend changes summary
- [ ] **Clock button**: if user has a `scheduled_start` and they clock in late, the toast changes from "Clocked in successfully" to "⚠️ Clocked in — 23 min late". The clock button shows a red pulse animation for 30 seconds after a late clock-in.
- [ ] **Employee Shifts timesheet tab**: late shifts get red left-border + 🕐 badge showing minutes. Excused shifts get gray left-border + 🔕 badge. Click badge → popover with "Excuse" / "Flag Late" toggle + note textarea. Edited shifts get ⚠️ badge → click shows edit history.
- [ ] **Pay Period summary**: new column "Late Shifts" showing count of unexcused late shifts per employee. Late shifts with excused=true don't count against the employee in the summary.
- [ ] **User Management**: new "Scheduled Start" time input per user (type="time", empty = no schedule).
- [ ] **Admin Settings > Timesheet Config**: new section with "Late Grace Period (minutes)" number input, reads/writes `timesheet_config.json`.

### Priority: MEDIUM

- [ ] **Timesheet approval workflow** — After pay period ends, timekeeper clicks "Submit for Approval" which locks that period's shifts from further edits. Employee can review and "Approve" (optional — small shops may skip). Locked shifts grayed out with 🔒 icon. Unlock requires owner permission. Approval status stored in new `timesheet_approvals.json` with period range, approved_by, timestamp.

- [ ] **PDF timesheet report export** — Generate a clean, printable timesheet report for the selected pay period. Employee name, shift dates/times, daily totals, period total, overtime, estimated pay, signature line. `POST /api/export/timesheet_pdf` endpoint. Print-friendly CSS with page breaks per employee. More professional than CSV for record-keeping and employee handouts.

- [ ] **Timesheet UI overhaul for timekeeper usability** — Current admin Timesheet tab shows raw shift list + raw admin login timesheet in two separate sections. Redesign as unified timekeeper dashboard: period selector at top → employee summary cards (name, total hours, overtime, estimated pay) → click employee to expand individual shifts → export button clearly visible (not buried). Dense data table for the shift list. Sortable columns (name, date, hours). Visual indicators for overtime, edited shifts, missing clock-outs.

- [ ] **Missing clock-out detection & alert** — Detect employees who clocked in but never clocked out (e.g., 8h+ since clock-in with no clock-out). Show alert banner in admin Timesheet: "⚠️ 2 employees have active shifts over 8 hours — possible forgotten clock-outs." Allow admin to force clock-out with estimated time + note.

### Priority: LOW

- [ ] **PTO / sick day tracking** — Optional accrual-based or manual tracking. `pto_balance` field per user. Admin can log PTO/sick days with date range and type. Excluded from "missing clock-out" alerts for those days.

- [ ] **Shift schedule builder** — Weekly schedule grid where manager assigns shifts (Mon 9-5: John, Tue 9-5: Maria, etc.). Compare scheduled vs actual hours. Visual schedule calendar in admin. Helps catch no-shows.

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

- [ ] **Employee ticket submission UI** — New "📋 Requests" tab visible to all logged-in employees (not just admins). Clean form with dropdown to select type: "🕐 Time Off Request", "🐛 Report Issue", "💬 Feedback / Suggestion", "📝 Other". Form adapts to type: time-off shows date range picker, issue/feedback shows priority selector. Subject + description fields. Submit button stores to `tickets.json`. Toast confirmation. "My Tickets" list below form showing user's own submissions with status badges.

- [ ] **Smart date picker for time-off requests** — Two date inputs (from → to) with native date picker. Auto-calculates total business days requested. Validates: can't request past dates, can't request >30 days without override. Shows total days prominently. Prevents overlapping requests.

- [ ] **Admin/owner ticket management dashboard** — New admin sub-tab "📋 Ticket Queue" (permission-gated: `manage_users` or new `manage_tickets` perm). Two-column layout: **Pending** (left) and **Resolved** (right). Each ticket card shows type icon, employee name, subject, date submitted, priority badge. Approve ✅ and Deny ❌ buttons on pending tickets. Deny prompts for reason note (required). Approve auto-sets status and timestamp. Activity logging for all actions.

- [ ] **Ticket status notifications** — When admin approves/denies a ticket, employee sees a notification badge on their "📋 Requests" tab. In-tab alert banner: "Your time-off request was ✅ approved" or "❌ denied". Unread count badge on tab button.

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

- [ ] **HIGH: Kitchen offline degradation** — When WebSocket disconnects, the kitchen display silently stops showing new orders. Implement automatic polling fallback (every 8s) triggered by socket disconnect event, with visible "⚠️ Offline — updating every 8s" banner. Currently the main POS has polling fallback but kitchen view doesn't. This is critical for reliability during network blips.

- [ ] **MEDIUM: Table status overview dashboard** — Add a color-coded table grid view showing all tables with status (empty/occupied/order-in-progress/ready-to-serve/needs-bussing). Click a table to see its current tab/orders, mark it bussed, or transfer to another waiter. Most modern POS systems have this as the primary floor-plan view. Saves waiters from guessing which tables need attention.

- [ ] **MEDIUM: Order transfer between waiters** — Add ability to transfer a table's active orders from one waiter to another via admin panel. Essential for shift changes, meal breaks, and when a waiter gets overwhelmed. Store `transferred_from` / `transferred_at` on order records for audit. Activity logging. Simple UI in admin tables section.

## Done

- [x] **Shift notes on clock-out** — When clocking out, optional textarea for shift notes. Stored as `notes` field on shift record. Displayed in timesheet view. Admin can also add notes. [worker-3]
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
- [x] **Add item modifier support** — Variants, modifiers, customizations with modifier editor. [worker-2]
- [x] **Multi-language support** — English + Spanish with browser detection, toggle button. [worker-2]
- [x] **Kitchen display queue system** — Full cook view: claim/complete/cancel, 8s auto-refresh, sound alerts, fullscreen. [worker-3]
- [x] **Order notes field** — Per-item and per-order notes. [worker-1]
- [x] **Receipt printing simulation** — Thermal printer CSS. [worker-2]
- [x] **Discount/coupon code system** — Percentage and flat discounts. [worker-1]
- [x] **Sales tax calculation support** — Global/per-category/per-item tax rates. [worker-2]
- [x] **Touch-optimized item grid** — Category tabs, responsive grid. [worker-1]
- [x] **Most-ordered items analytics** — `/api/analytics/most_ordered`. [worker-3]
- [x] **Peak hour sales analytics** — `/api/analytics/hourly_sales`. [worker-2]
- [x] **Daily revenue tracking** — `/api/analytics/daily_revenue`. [worker-1]
- [x] **PWA manifest + service worker** — Installable app. [worker-3]
- [x] **Loyalty points system** — Points earning/redeeming per customer. [worker-3]
- [x] **Admin dashboard with Chart.js analytics** — Charts for daily revenue, payment methods, item trends. [worker-2]
- [x] **Scheduled pricing (happy hour, daily specials)** — Time-based discount rules. [worker-1]
- [x] **Fix order history for all users (BUG)** — New `/api/orders/list` endpoint. [worker-3]
- [x] **Add auto-save draft orders to localStorage** — Cart auto-save with restore prompt on page load. [worker-1]
- [x] **Per-user pay rate field** — Add `pay_rate` (hourly, float) to user profile. Shown in user management, timesheet/pay-period summary, and CSV/PDF exports. [worker-1]

## Done (older)

<details>
<summary>22 completed tasks from earlier development</summary>

- [x] **Add item search/filter in POS item grid** — Real-time search bar. i18n EN + ES. [worker-2]
- [x] **Add WebSocket support for real-time updates** — Flask-SocketIO with polling fallback. [worker-1]
- [x] **Add delivery address management** — Delivery form, saved addresses API. i18n EN + ES. [worker-3]
- [x] **Add customer-facing display mode** — `/customer-display` page with large-print order summary. [worker-1]
- [x] **Add dark/light theme toggle** — CSS variables, localStorage persistence, toggle button. [worker-2]
- [x] **Fix verify_admin blocking owners from tax/discount endpoints** — Replaced `verify_admin()` with `check_perm()`. [worker-2]
- [x] **Fix menu history frontend parsing** — Changed `data.history` to `data.backups`. [worker-3]
- [x] **Add quick-order favorites per user** — `favorites.json` data store with save/list/delete. [worker-1]
- [x] **Add item popularity trend chart** — `/api/analytics/item_trends` comparing 7d vs prior 7d. [worker-3]
- [x] **Add offline order queuing** — `/api/health` + `/api/sync_orders`, localStorage queue, auto-sync. [worker-3]
- [x] **Refund/void order functionality** — POST /api/orders/refund with reason tracking. [worker-1]
- [x] **Table tab management** — Checkout/close tab, tab history, quick-add. [worker-3]
- [x] **Add inventory tracking** — Stock levels decremented on order, low-stock alerts. [worker-1]
- [x] **Add split-payment support** — Multiple payment methods per order. [worker-3]
- [x] **Add tip calculation UI** — Percentage buttons in POS cart. [worker-2]
- [x] **Add employee performance dashboard** — Per-employee metrics with date filtering. [worker-2]
- [x] **Add waste tracking** — Waste log with reason, estimated cost. [worker-2]
- [x] **Kitchen queue audit & optimize** — Color-coded age, priority badge, quick-claim, alarm sound. [worker-1]
- [x] **Table management system** — Admin assigns tablets to tables, running tabs. [worker-3]
- [x] **Drive-through order display** — Drive-through TV view at `/drivethrough`. [worker-1]
- [x] **Granular role/permission system** — Three-tier roles with 10 granular permissions. [worker-2]
- [x] **Menu version history with restore** — Auto-backup, owner restores any day's menu. [worker-3]

</details>

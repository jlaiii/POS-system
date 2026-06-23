# POS System — Smart Task Queue

> Auto-managed by 3 Hermes Worker Crons (every 30 min each, staggered claims).
> Workers use `[~]` to claim tasks before working. Never pick a claimed task.
> Last updated: 2026-06-23 (audit #6 — system audit)

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

## New Tasks (from Audit #6)

- [x] **Add kitchen display table grouping** — Kitchen orders should be groupable by table number so cooks can see all items for a table together. Currently each order submission creates a separate card. When same table gets multiple orders (appetizers then mains), they should be visually grouped or merged in the kitchen queue. [worker-2 — Table-grouped collapsible cards with nested order display, table badge on standalone cards, backend sorted by table then date]

- [x] **Add auto-table suggestion for waiters** — When a waiter returns to the POS tab, auto-select the table they were last working on (stored per-user in localStorage). Saves 1-2 taps per order cycle, adds up over a shift.

## Timekeeper / Payroll System (NEW — June 2026)

> The clock-in/out system works but needs to be usable by a real timekeeper/payroll person. Currently: raw shift dump, no date filtering, no pay period concept, no overtime, no corrections, no break tracking. Below is what's needed to make it payroll-ready.

### Priority: HIGH

- [x] worker-2 **Add date range filtering to all timesheet/shift endpoints** — `/api/admin_shifts`, `/api/admin_timesheet`, `/api/export/shifts_csv`, `/api/export/timesheet_csv` all need `date_from`/`date_to` params. Currently they dump every record ever. Timekeeper needs to pull "this week" or "June 1-15" without scrolling through months of data. Server-side filter on `clock_in_time` / `login_time` fields. Backward-compatible (omit params = all records, same as today).

- [x] worker-1 **Add pay period summary endpoint + UI** — New `POST /api/timesheet/pay_period` endpoint with per-employee totals (hours, overtime, estimated pay). Frontend Pay Period sub-tab in Timesheet with summary bar, employee cards, and drill-down shift details. i18n compatible.

- [ ] **Pay period selector with Weekly / Bi-weekly / Monthly presets** — Date range picker in Timesheet view with quick-select buttons: "This Week", "Last Week", "This Month", "Last Month", "Custom". "This Week" and "Last Week" auto-calculate Mon-Sun. "Bi-weekly" option with pay period start date config. CSV/PDF export button that exports only the selected period. Replace the current bare "Export CSV" that dumps everything.

- [ ] **Overtime detection and flagging** — Configurable thresholds in admin (default: 8h/day, 40h/week). `POST /api/timesheet/pay_period` already flags overtime_hours per employee. Frontend: orange/red badges on shifts that push employee over daily/weekly limits. Pay period summary shows overtime breakdown. CSV export includes `Overtime Hours` column.

- [ ] **Admin shift edit / correction with audit trail** — Timekeeper needs ability to correct clock-in/out times (employee forgot to clock out, clocked in wrong, system error). New `POST /api/clock/edit` endpoint: accepts `shift_index` (from shift_log array), new `clock_in_time` / `clock_out_time` (or null to keep original). Logs edit in activity_log with old→new values and `edited_by` (admin PIN). Edited shifts flagged with ⚠️ icon in UI. Edit history viewable per shift. `edited` boolean stored on shift record. Permission-gated (manage_items or new `edit_timesheet` perm?).

- [ ] **Shift notes on clock-out** — When clocking out, optional textarea for shift notes (e.g., "covered closing duties", "stayed late for deep clean", "short shift — left early with permission"). Stored as `notes` field on shift record. Displayed in timesheet view. Admin can also add notes on individual shifts after the fact.

- [ ] **Break tracking (unpaid meal breaks)** — New "Start Break" / "End Break" option on clock button. Break time subtracted from total paid hours. Stored as `breaks: [{start, end, duration_minutes}]` array on shift record. Break duration visible in timesheet view. Total paid hours = `duration_hours - break_hours`.

- [ ] **Per-user pay rate field** — Add `pay_rate` (hourly, float) to user profile in `users.json`. Shown in user management. Timesheet summary multiplies `total_hours × pay_rate` for estimated gross pay per period. Displayed in pay period summary. CSV export includes `Pay Rate`, `Estimated Pay` columns. Rate changes don't retroactively apply — use rate at time of export.

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

- [ ] **Employee ticket submission UI** — New "📋 Requests" tab visible to all logged-in employees (not just admins). Clean form with dropdown to select type: "🕐 Time Off Request", "🐛 Report Issue", "💬 Feedback / Suggestion", "📝 Other". Form adapts to type: time-off shows date range picker (calendar-style start/end date with total days auto-calc), issue/feedback shows priority selector. Subject + description fields. Submit button stores to `tickets.json`. Toast confirmation. "My Tickets" list below form showing user's own submissions with status badges (🟡 pending, 🟢 approved, 🔴 denied).

- [ ] **Smart date picker for time-off requests** — Two date inputs (from → to) with a mini calendar or native date picker. Auto-calculates total business days requested (excludes weekends? toggle per config). Validates: can't request past dates, can't request >30 days without override. Shows total days prominently so employee sees "Requesting 3 days off" before submitting. Prevents overlapping requests (checks against existing approved time-off for same user in date range).

- [ ] **Admin/owner ticket management dashboard** — New admin sub-tab "📋 Ticket Queue" (permission-gated: `manage_users` or new `manage_tickets` perm). Two-column layout: **Pending** (left) and **Resolved** (right). Each ticket card shows: type icon, employee name, subject, date submitted, priority badge (for issues), date range (for time-off). Approve ✅ and Deny ❌ buttons on pending tickets. Deny prompts for reason note (required). Approve auto-sets status and timestamp. Resolved column shows all approved/denied with responder info, filterable by type and date. Activity logging for all approve/deny actions.

- [ ] **Ticket status notifications** — When admin approves/denies a ticket, employee sees a notification badge on their "📋 Requests" tab. In-tab alert banner: "Your time-off request for June 28-30 was ✅ approved" or "❌ denied — reason: short staffed that weekend". No email/push needed — in-app notification is sufficient for POS terminal context. Notification persists until employee views the ticket. Unread count badge on tab button.

- [ ] **API endpoints for ticket CRUD** — `POST /api/tickets/submit` (employee creates), `POST /api/tickets/my` (employee fetches their own), `POST /api/tickets/queue` (admin fetches all, filterable by status/type/user), `POST /api/tickets/respond` (admin approve/deny with note). All endpoints use existing `adminPin` auth pattern. Permission-gated: submit requires basic auth (any logged-in user), queue/respond requires `manage_users` or new `manage_tickets` permission.

### Priority: MEDIUM

- [ ] **Conflict detection for time-off requests** — When admin views a pending time-off, show warning if too many employees already approved for same dates ("⚠️ 3 of 5 servers already off June 28 — approving this leaves only 2"). Configurable per-role staffing minimums. Helps manager avoid accidentally approving everyone for the same weekend.

- [ ] **Ticket filtering and search** — Admin queue: filter by type (time_off/issue/feedback), status (pending/approved/denied), employee, date range. Search by subject/description text. Sort by date submitted, priority. Essential once there are 20+ tickets.

- [ ] **Recurring time-off patterns** — Allow employee to request recurring time-off (e.g., "every Tuesday for the next 3 months" for school/childcare). Auto-generates individual ticket entries or a parent ticket with child date instances. Admin approves the pattern once instead of weekly.

- [ ] **Calendar view for time-off** — Visual calendar in admin showing who's off on which days. Color-coded by employee. Month/week toggle. Click a day to see who's off. Makes staffing gaps obvious. Uses the same ticket data — just rendered as a calendar grid instead of a list.

### Priority: LOW

- [ ] **Issue/bug ticket triage labels** — Admin can tag issue tickets: "POS bug", "hardware", "menu error", "customer complaint", "other". Filter by label. Helps prioritize fixes.

- [ ] **Ticket response templates** — Admin can save common response notes as templates: "Approved — enjoy your time off", "Denied — peak season, please reschedule for after [date]", "Issue acknowledged — will investigate". Quick-select dropdown when responding.

- [ ] **Employee feedback analytics** — Aggregate feedback tickets by category over time. "Top 3 issues employees are reporting this month." Dashboard card in admin showing feedback trends. Helps owner spot systemic problems (e.g., "3 complaints about the same broken printer").

- [ ] **Auto-approve for low-risk time-off** — Configurable rule: auto-approve time-off if requested >2 weeks in advance AND no other approvals for same date. Reduces admin overhead. Can be toggled off.

## Employee Pay Portal — Pay Stubs, History & Downloads (NEW — June 2026)

> Employees should be able to log in and see their own pay: hours worked, pay rate, gross/net, per-period and YTD totals, downloadable pay stubs, and a way to flag discrepancies. This is the employee-facing side — the admin/timekeeper sees the full timesheet dashboard (from the Timekeeper section above). Employee only sees their own data.

### Key design decisions

- **Data source**: shift_log.json (clocked hours) × user pay_rate from users.json
- **No actual payroll processing** — this is informational/reporting, not ACH/bank integration
- **"Request Review"** feeds into the existing ticket system (type: `pay_review`) so admin can investigate
- **Pay stubs are generated on the fly** from shift data — no separate pay_stubs.json data store needed. Each "stub" is a computed view of a pay period's shifts + rates.

### Priority: HIGH

- [ ] **Employee "My Pay" tab** — New "💰 My Pay" tab visible to all logged-in employees (not admin-only). Shows three sections: **Current Period** (in-progress pay period with live hours so far), **Pay History** (list of past periods with totals), **Year-to-Date** summary card. Employee sees ONLY their own data — scoped by their `adminPin`/user_id. No permission needed beyond basic login.

- [ ] **Current pay period live tracker** — Shows the current pay period date range, hours worked so far (from completed shifts + currently clocked-in live duration), pay rate, estimated gross pay so far. Auto-updates every 60 seconds while clocked in. Progress bar showing what % of a standard 40h week is done. "You've worked 24.5 of 40 hours this week — estimated gross: $367.50." This is motivational and lets employees self-monitor.

- [ ] **Pay history with period-by-period breakdown** — List of past pay periods with: date range, total hours, pay rate at that time, gross pay, shift count. Click any period to expand into a detailed shift list (date, clock in/out, hours, breaks, notes). This is the employee's personal ledger — they should be able to trace every dollar back to specific shifts. Data pulled from `/api/timesheet/pay_period` filtered to the employee's user_id.

- [ ] **Downloadable pay stub (PDF)** — "Download Pay Stub" button per pay period in history. Generates a clean PDF with: employee name, pay period dates, itemized shift list with hours, total hours, pay rate, gross pay, YTD totals, employer info (configurable in admin settings), and a "This is not an official tax document" disclaimer. Uses the PDF export pipeline from the Timesheet system task. Stored in activity_log as `pay_stub_download` event.

- [ ] **Pay history CSV export** — "Export My Pay History" button at bottom of Pay History. Downloads a CSV with all past periods: period_start, period_end, hours, rate, gross, shift_count. Simple, clean, spreadsheet-ready. Employee can do their own math or share with accountant.

- [ ] **"Request Pay Review" action** — If employee thinks hours or pay are wrong, a "⚠️ Request Review" button on any pay period or shift. Opens a pre-filled ticket form (type: `pay_review`, subject auto-populated with period/suspected issue, description field for employee to explain). Feeds directly into the ticket system — admin sees it in the Ticket Queue. Links the pay period data so admin can cross-reference. This is the "something looks wrong, look into it" flow.

### Priority: MEDIUM

- [ ] **Year-to-date (YTD) earnings card** — Summary card at top of My Pay showing: YTD gross pay, YTD hours worked, average hours/week, average hourly effective rate (total gross ÷ total hours). Updates in real time as shifts are completed. Gives employees a quick financial snapshot without digging through periods.

- [ ] **Multi-rate support (different rates for different shifts)** — Some employees work multiple roles (e.g., server at $8/hr, cook at $15/hr). Allow per-shift or per-role pay rate override. If an employee clocks in as "cook" for half their shift and "server" for the other half, the pay period calculates a weighted average. Stored as optional `pay_rate_override` on shift record (null = use user default).

- [ ] **Pay stub email delivery** — Auto-email pay stub PDF to employee when admin marks a pay period as "paid" (from the timesheet approval workflow). Uses existing email config (SMTP from digital receipts feature). Employee gets a clean email: "Your pay stub for June 16-30 is ready. Gross: $1,247.50. Download attached PDF." Reduces "hey boss, can I get my stub?" conversations.

- [ ] **Tip tracking in My Pay** — Since tips are already tracked per order and employee, aggregate tip data per pay period in My Pay: total credit card tips, total cash tips (employee-entered). Separate line from hourly pay. "This period: Hours $380.00 + Tips $412.50 = $792.50." Helps tipped employees understand their true take-home.

### Priority: LOW

- [ ] **Direct deposit info display** — Read-only display of employee's direct deposit details (bank name, last 4 of account) stored in user profile. "Payments go to: Chase ****1234." Employee can verify but not edit — must request admin change. Reduces "which account is my deposit going to?" questions.

- [ ] **Pay comparison charts** — Simple bar chart in My Pay showing period-by-period gross pay for last 6 periods. Line overlay showing hours trend. Employee can see if their hours are trending up or down. Helps them plan finances.

- [ ] **Tax withholding estimator** — Optional: if employee fills in W-4 info (filing status, allowances), show estimated federal/state tax withholding per period. Gross → estimated net. Big disclaimer: "Estimate only — consult a tax professional." Gives employees a rough idea of take-home without running separate calculators.

## Table-Side Digital Menu & Ad Display (NEW — June 2026)

> The existing `/tablet` page (`tablet.html`) is a pure ad rotator — it cycles through promoted images. This needs to become a full table-side digital menu that customers pick up at their table. **Ads should still play as the idle/screensaver**, but there should be an overlay button to view the menu, browse items with images/prices, and see restaurant info. This is the customer-facing menu experience, not the POS ordering screen.

### What already exists
- `tablet.html` at `/tablet` — ad rotator with slideshow, swipe support, dot navigation, "Order in Progress" overlay
- `/api/ads/current` — returns active ads JSON (no auth needed, public endpoint)
- `/api/items` (GET) — returns full menu with categories and items (no auth needed)
- `/api/combos/list` (GET) — returns active combos (no auth needed)
- Item images already supported (from item images task above)

### Priority: HIGH

- [ ] **"View Menu" button overlay on ad screen** — Add a persistent floating button on the ad rotator screen: "🍽️ View Menu" (bottom-center, large, 60px+, semi-transparent bg). Always visible on top of ads. When tapped, transitions smoothly to the menu view (slide-up or fade). When in menu view, a "← Back" or "✕" button returns to the ad rotator. The button should be subtle enough not to ruin the ad aesthetic but obvious enough that customers find it. Configurable: admin can choose to auto-show menu on wake vs. show ads first.

- [ ] **Customer-facing menu display** — Full menu view with category tabs across the top (horizontally scrollable on mobile). Each category shows item cards in a grid: item image (or placeholder if no image), name, description (truncated to 2 lines), price. Large touch targets (min 150px cards). No "add to cart" or ordering functionality — this is display-only, not self-ordering. Pulls data from existing `/api/items` endpoint. Filters hidden items (`visible: false`). Honors category order from admin settings.

- [ ] **Item detail popup** — Tap an item card → fullscreen overlay with: large item image, full description, price, dietary badges (spicy 🌶️, vegetarian 🥬, gluten-free 🌾 — from item tags field), modifier options shown as bullet points (e.g., "Available in: Small / Medium / Large"). Swipe left/right to browse items in same category without closing the popup. Close button returns to menu grid.

- [ ] **Combo/meal deal showcase section** — Below the category tabs, a "🔥 Featured Combos" horizontal scrollable row showing combo cards: combo image (or collage of child item images), combo name, child items listed, combo price with strikethrough individual total (showing savings). Pulls from `/api/combos/list`. Only shows active combos. Tap opens combo detail with full breakdown.

- [ ] **Auto-return to ads after inactivity** — After 30-60 seconds of no touch interaction in the menu view, auto-transition back to the ad rotator. Shows a 5-second countdown toast: "Returning to ads in 5...". Tap anywhere to cancel. Prevents the menu from being stuck open when a customer walks away. Timeout configurable in admin.

- [ ] **Restaurant info bar** — Persistent footer bar showing: restaurant name (configurable), hours today (from config), Wi-Fi info if configured, "📞 Call Server" button (triggers a subtle notification on the POS/kitchen display — new SocketIO event `tablet_call_server` with table number). Table number displayed in corner so servers know which table to go to. Table number set via URL param: `/tablet?table=5`.

### Priority: MEDIUM

- [ ] **Dark/light theme toggle on tablet** — Tablet menu respects the POS system's dark theme (matches existing `tablet.html` dark aesthetic). Add a sun/moon toggle in the corner for customers who prefer light mode. Persists per-session only (resets when returning to ads after inactivity).

- [ ] **Language toggle (EN/ES)** — Same i18n system as the main POS. Tablet menu auto-detects browser language but allows manual toggle. Menu item names/descriptions remain in admin's language, but UI labels ("View Menu", "Featured Combos", "Call Server") translate. Essential for restaurants with Spanish-speaking clientele.

- [ ] **Happy hour / specials badge on items** — If scheduled pricing is active (from the existing happy hour system), show a "⚡ Happy Hour" or "🎉 Special" badge on the item card with the discounted price displayed in green next to the strikethrough original. Auto-hides when special ends. Makes the tablet feel alive and dynamic.

- [ ] **"Order This" QR code** — Small QR code icon on each item card or in the detail popup. When tapped (or on hover for non-touch), expands to show a QR code that links to an online ordering page or the item itself. Useful for restaurants that do app-based ordering alongside table service. QR data is a URL configurable per item or globally.

### Priority: LOW

- [ ] **Allergen filter toggle** — Filter button that lets customers show/hide items by allergen: "🥜 Peanuts", "🥛 Dairy", "🌾 Gluten", "🦐 Shellfish". Items tagged with allergens in admin get filtered out when toggle is on. Shows "3 items hidden" count. Data comes from a new `allergens` array field on items.

- [ ] **Nutritional info popup** — Optional per-item: calories, protein, carbs, fat. Stored as `nutrition: {calories, protein_g, carbs_g, fat_g}` on item. Shown in a collapsible section in the item detail popup. Appealing to health-conscious diners.

- [ ] **"Most Popular" badge** — Items tagged by admin as "popular" or auto-calculated from most-ordered analytics show a "⭐ Most Popular" badge on their card. Helps indecisive customers pick. Admin can manually pin popular items or let the system auto-rank from last 30 days of orders.

- [ ] **Wake-on-proximity / screensaver mode** — If the device supports it (camera-based), dim screen to 20% when no one is nearby, brighten to full when motion detected. Falls back to the ad rotator as screensaver. Works on tablets with front-facing cameras via a simple motion-detection approach (compare frames every 2 seconds for significant change).

## Done

- [x] **Add auto-table suggestion for waiters** — When a waiter returns to the POS tab, auto-select the table they were last working on (stored per-user in localStorage). Saves 1-2 taps per order cycle, adds up over a shift. [worker-1]

- [x] **Add employee clock-in/clock-out system** — New `/api/clock/in`, `/api/clock/out`, `/api/clock/status`, `/api/admin_shifts`, `/api/export/shifts_csv` endpoints. Punch clock button in POS header (⏰) showing Clock In/Out status with live duration. Shift records in admin Timesheet view with active/completed shift display. Activity logging for all clock events. i18n EN + ES. [worker-3]
- [x] **Add combo/meal deal builder for fixed-price bundled items** — Create fixed-price combo deals (e.g., "Lunch Special: Burger + Fries + Drink $12.99") as a single orderable item. Admin builder UI to select child items, set combo price, and manage active combos. One-tap add to cart expands child items for kitchen display. Increases average order value. i18n EN + ES. [worker-2]
- [x] **Add item visibility toggle (hide/show menu items without deleting)** — Active/inactive toggle per item in admin item management. Hidden items remain in database but do not appear in POS item grid, kiosk, or search. Useful for seasonal items, out-of-season ingredients, temporary supplier outages. Visual indicator (eye icon) in management list. i18n EN + ES. [worker-1]
- [x] **Add service charge / auto-gratuity for large parties** — Configurable auto-gratuity settings (party size threshold, default percentage) in admin. When cart item count reaches threshold, service charge line auto-appears with label and amount. Display on receipt, kiosk, and order history. Permission-gated (manage_items). i18n EN + ES. [worker-3]

- [x] **Add course/meal prep timing (appetizer/main/dessert)** — Allow marking items with course type so kitchen knows preparation order. Items marked as "Appetizer" show with 🥗 flag and suggested 5-min prep target, "Main" normal, "Dessert" 🍰 flagged to prepare after mains. Display course badge on kitchen order cards. [worker-3]

- [x] **Add recent-order quick-access on POS tab** — Show last 5 orders for the logged-in waiter directly on the POS tab (collapsible "Recent Orders" section above item grid). One-tap reload of entire order into cart without navigating to History tab. Saves 3+ taps for frequent reorders. [worker-1]

- [x] **Add item images to grid cards** — Allow attaching image URLs to menu items for visual identification. Display thumbnail images on item grid cards, kitchen tickets, and kiosk mode. Speeds up waiter item location in busy environments. i18n EN + ES. [worker-2]

- [x] **Add customer profile management (name, contact, order history, total spent)** — Currently customer info is limited to phone-based loyalty lookup. Extended customer data model with email, address, notes, total_spent, total_orders, last_visit. New endpoints: `/api/customers/list` (search), `/api/customers/detail` (order history), `/api/customers/update`. Spending auto-tracked on order submission. New admin "👥 Customers" CRM tab with search, sortable table, and full-profile detail overlay. Auto-creates customer records when orders come in with unrecognized phone. [worker-3]

- [x] **Add quick-change cash calculator for cash payments** — When Cash payment method is selected, shows "Amount Tendered" input with auto-calculated change due. Quick preset denomination buttons ($5, $10, $20, $50) fill the tendered amount. Change shown in large green font; negative (still owed) shown in red. i18n EN + ES. Dark theme compatible. Touch-friendly 48px+ targets. [worker-1]

- [x] **Add item modifier support (sizes, options, extras)** — Allow menu items to have variants (small/medium/large), modifiers (extra cheese, no onions), and customizations. Store modifiers in cart items, display on kitchen tickets and receipts. Industry-standard POS feature. Backend: `POST /api/items/modifiers/save` and `POST /api/items/modifiers/get` endpoints, modifier groups stored in items.json. Frontend: modifier selection overlay on item add, modifier badge on item cards, modifier display in cart/kitchen/receipt/order history/kiosk, admin modifier editor UI in item management. i18n EN + ES. [worker-2]

- [x] **Multi-language support** — English + Spanish with browser language detection, language toggle button (globe) in top bar.
- [x] **Kitchen display queue system** — Full cook view: order queue with claim/complete/cancel, 8s auto-refresh, sound alerts, fullscreen mode, role-based routing (cook role), order status pipeline (pending→preparing→completed/cancelled)
- [x] **Order notes field** — per-item note input in cart items, per-order notes textarea in cart.
- [x] **Receipt printing simulation** — print-friendly HTML receipt with thermal printer CSS.
- [x] **Discount/coupon code system** — percentage and flat discounts with admin management.
- [x] **Sales tax calculation support** — configurable global, per-category, and per-item tax rates.
- [x] **Touch-optimized item grid with category tabs**
- [x] **Most-ordered items analytics endpoint**
- [x] **Peak hour sales analytics**
- [x] **Daily revenue tracking**
- [x] **PWA manifest + service worker for installable app**
- [x] **Add loyalty points system per customer** — New `loyalty_points.json` data store. `POST /api/loyalty/register`, `/lookup`, `/redeem`, `/confirm_redeem`, `/adjust`, and `GET /api/loyalty/customers` endpoints. Points auto-earned on order submission (1 pt per $1 subtotal). Redeem 100 pts = $5 off, applied as discount in cart. Frontend: customer phone lookup+register in cart area with points display, "Redeem Points" button, ⭐ Loyalty admin tab with customer table and points adjustment. Points earned shown in toast and on receipt. Activity logging. Dark theme compatible. Touch-friendly 44px+ targets. [worker-3]
- [x] **Admin dashboard with Chart.js analytics**
- [x] **Add scheduled pricing (happy hour, daily specials)** — Time-based automatic discount rules (happy hour, daily specials). `scheduled_pricing.json` data store. CRUD endpoints with day-of-week + time-window matching. POS item grid shows green sale price with strikethrough original. Admin management tab with rule form (name, type, value, category, item filter, days, time range, toggle/delete). i18n EN + ES. Permission-gated (manage_items). [worker-1]
- [x] **Fix order history for all users (BUG)** — New `/api/orders/list` endpoint (basic auth only, no `view_stats` required). Frontend `loadOrderHistory()` calls new endpoint instead of `/api/admin_stats`. Waiters with only `pos_access` can now view order history without getting a misleading "Network error". [worker-3]
- [x] **Add auto-save draft orders to localStorage** — Auto-saves cart state to localStorage on every cart change (`pos_cart_draft` key). On page load, detects unsaved draft and prompts "Restore Draft?" with discard option. Clears draft on successful order submission. Saves: cart items, payment splits, discount, tip, order notes, delivery address, table number, loyalty customer. 24h expiry. i18n EN + ES. [worker-1]

## Done (older)

<details>
<summary>22 completed tasks from earlier development</summary>

- [x] **Add item search/filter in POS item grid** — Real-time search bar that filters menu items by name across all categories. Searches across all categories simultaneously with text highlighting, Escape to clear, auto-focus on tab switch, clears on category tab click. 48px+ touch-friendly input, i18n EN + ES. [worker-2]
- [x] **Add WebSocket support for real-time updates** — Replace polling (kitchen 8s, customer-display 2s, drive-through 2s) with Flask-SocketIO WebSockets for instant updates. Emits `kitchen_update`, `customer_update`, `drivethrough_update` events from order/display endpoints. Frontend falls back to polling if WebSocket fails. [worker-1]
- [x] **Add delivery address management** — Delivery address form (street, city, state, zip, instructions) toggleable in cart. Address stored per-order, shown on receipt and in order history. Saved addresses API for future reuse. i18n EN + ES. Touch-friendly 44px+ targets. [worker-3]
- [x] **Add customer-facing display mode (second screen showing order summary)** — New `/customer-display` page with large-print order summary view. Live 2s polling from `/api/customer-display/status`. Toggle button in POS cart area pushes cart items, subtotal, tax, tip, and total to display state. Shows idle/welcome screen when no order, building screen with item list during order, and thank-you screen on order submit. Dark theme (#1a1a2e bg, #e94560 accent, #16213e cards). Backend endpoints: update/status/complete/reset. Auto-resets on cart clear. [worker-1]
- [x] **Add dark/light theme toggle with persistence** — CSS variables for theming (light theme overrides `.light-theme` class on `<html>`), localStorage persistence (`pos_theme` key), theme toggle button in top bar, meta theme-color update, dark/light switch for all major UI elements with `--border`, `--hover`, `--card-alt` variables. Touch-friendly. [worker-2]
- [x] **Fix verify_admin blocking owners from tax/discount endpoints** — Replaced `verify_admin()` (which only checks role=='admin') with `check_perm(admin_pin, "manage_items")` in both `update_tax_config()` and `manage_discount()` endpoints. Owners with wildcard permissions can now manage tax config and discounts. [worker-2]
- [x] **Fix menu history frontend parsing** — Changed frontend from `data.history` to `data.backups` to match API response. Fixes TypeError when owner opens Menu History tab. [worker-3]
- [x] **Add quick-order favorites per user (save frequently ordered combos)** — New `favorites.json` data store. `POST /api/favorites/save`, `/api/favorites/list`, `/api/favorites/delete` endpoints. Frontend: "Save as Favorite" and "My Favorites" buttons in cart area, favorites overlay with load/delete, cart replace-or-merge on load, 20-favorite limit, duplicate name check, activity logging. i18n EN + ES. [worker-1]
- [x] **Add item popularity trend chart (which items rising/falling)** — New `/api/analytics/item_trends` endpoint comparing recent 7d vs prior 7d item counts with % change, direction (rising/falling/stable), and sorting. Frontend: horizontal bar chart in Charts section with green/red/gray bars, tooltip showing counts and delta. i18n EN + ES. [worker-3]
- [x] **Add offline order queuing (sync when connection restores)** — `/api/health` GET for connectivity check, `/api/sync_orders` POST for batch submission of queued orders. Frontend: localStorage queue on network error, auto-sync on reconnect + 30s interval, offline badge indicator with count, receipt shows queued status. i18n EN + ES. [worker-3]
- [x] **Refund/void order functionality with reason tracking** — POST /api/orders/refund endpoint marks orders as refunded with reason, timestamp, and staff ID. Double-refund prevention. Refund audit trail in refunded_orders.json. Activity log integration. Frontend: refund button (with manage_orders permission) in order history, refund dialog with reason textarea, REFUNDED badge and reason on refunded orders. Stats exclude refunded orders from revenue. i18n English + Spanish. [worker-1]
- [x] **Table tab management** — Checkout/close tab endpoint (POST /api/tables/tab/<table_number>/checkout) marks all active orders as paid in one action. Tab history endpoint (GET /api/tables/tab/<table_number>/history) shows completed orders per table with total revenue. Frontend: "Close Tab & Checkout" button in tab overlay with payment method/tip/notes dialog, "📋 History" button per table in admin panel, tab history overlay with order details, and "➕ Add Items" quick-add button that auto-selects table in POS. [worker-3]
- [x] **Add inventory tracking** — Separate inventory.json tracked per item name. Stock decremented on order submission. Low-stock alerts (stock <= threshold) and out-of-stock detection. Admin inventory management UI with per-item stock/threshold editing and bulk init. Stock level badges on POS item cards (colored: green/ok, yellow/low, red/out). Out-of-stock items disabled with visual indicator. Low-stock toast warnings on order submit. Auto-creates inventory entries for new menu items. [worker-1]
- [x] **Add split-payment support** — Support multiple payment methods per order (Cash/Card/Mobile Pay). Toggle payment method buttons with individual amount inputs. Split Evenly button. Validation ensures splits equal total. Payment breakdown stored in `payment_splits` array. Displayed on receipt, order history, kitchen display, and kiosk mode. Backward-compatible with legacy single-payment orders. [worker-3]
- [x] **Add tip calculation UI** — Percentage buttons (No tip/15%/18%/20%/Custom) in main POS cart tip row. Tip calculated on subtotal, shown in cart total, submitted with order, displayed on receipt and order history. [worker-2]
- [x] **Add employee performance dashboard** — New `/api/employee_performance` endpoint with date range filtering, per-employee metrics (orders count, revenue, avg order value, tips, items sold). Frontend: admin sub-tab with summary cards and sortable table, i18n EN/ES, permission-gated (view_stats). [worker-2]
- [x] **Add waste tracking (items thrown away, reason)** — New `waste_log.json` data store. `POST /api/waste/log` endpoint logs waste entries with item, quantity, reason (spoiled/expired, burned, spilled, damaged, overproduced, other), notes, estimated cost (based on item price). `POST /api/waste` endpoint retrieves log with date filtering. `POST /api/waste/summary` endpoint provides aggregated waste stats (total entries, items, cost, breakdown by reason, top items). Frontend: Admin Waste tab with log form (item dropdown, qty, reason, notes), summary cards, date-filtered log table with reason badges, i18n EN + ES. Activity logging. Permission-gated (manage_items for logging, view_stats for viewing). Dark theme compatible. [worker-2]
- [x] **Kitchen queue audit & optimize** — Prominent color-coded order age (warning at 5m, critical at 10m+ with pulsing animation), 🚨 PRIORITY badge for orders >10min, quick-claim by tapping entire card body, enhanced 3-note square wave alarm sound, fixed stats endpoint keys (pending/preparing/done_today), 1s clock update, 10s age recheck interval. [worker-1]
- [x] **Table management system** — Admin assigns tablets to tables by table number. Orders tagged with table number. Running tab tracking per table. Table management in admin panel with tab view modal. Table number selector in cart. [worker-3]
- [x] **Drive-through order display** — Drive-through tablet/TV view at `/drivethrough`. Shows live cart building with 2s polling, large high-contrast text for outdoor visibility. Cashier toggles "Drive-Through" mode in POS to push cart state live. Shows items, running total, tax. "Please Pull Forward" screen when order submitted. High-contrast dark theme (#0a0a1a bg, #ff3366 accent, #00cc66 success).
- [x] **Granular role/permission system** — Three-tier roles (owner/admin/user/cook) with 10 granular permissions. Owner has ["*"] wildcard, can grant/revoke specific perms per admin. Ban/unban users with reason tracking. Permission-aware UI hides unauthorized sections.
- [x] **Menu version history with restore** — Every menu change auto-saves timestamped backup to menu_backups/. Owner browses backup dates, restores any day's menu with safety backup of current state. Keep last 30 backups.

</details>

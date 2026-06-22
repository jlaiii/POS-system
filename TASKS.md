# POS System — Smart Task Queue

> Auto-managed by 3 Hermes Worker Crons (every 30 min each, staggered claims).
> Workers use `[~]` to claim tasks before working. Never pick a claimed task.
> Last updated: 2026-06-22

## Status Legend
- `[ ]` = pending (available for any worker)
- `[~]` = in progress (worker has claimed it — DO NOT TOUCH)
- `[x]` = completed
- `[-]` = cancelled / no longer relevant

## Priority: HIGH

- [x] **POS Kiosk / Customer Payment Mode** — Kiosk mode overlay with large-print cart display, tip calculator (No tip/15%/18%/20%/Custom), payment method selector, and "Thank You" screen with auto-return countdown. Toggle button in cart area. Tip amount stored in order data. [worker-2]
- [x] **Kitchen queue audit & optimize** — Review kitchen display end-to-end. Fast-paced: minimize button taps, prominent order age, sound alerts per new order, priority flagging for orders waiting >10 min. Test 8s polling under load. [worker-1]
- [ ] Add tip calculation UI (percentage buttons: 15%, 18%, 20%, custom)
- [ ] Add split-payment support (multiple payment methods per order)
- [ ] Add inventory tracking (decrement stock when ordered, alert on low stock)

## Priority: MEDIUM

- [ ] **Customer order lookup** — From the kiosk mode, allow looking up an order by order number or table number to pull it up for payment.
- [ ] **Table tab management** — Each table accumulates a running tab (orders placed from that table). Staff can view a table's tab, add items, and close it out (checkout). Tab history per table.
- [ ] **Owner activity log filter** — Let owner filter activity log by: admin user, action type, date range. Show who changed what and when.
- [ ] Add export data to CSV/Excel (orders, timesheet, activity log)
- [ ] Add date range filtering for order history and stats
- [ ] Add refund/void order functionality with reason tracking
- [ ] Add employee performance dashboard (orders per employee, avg order value)
- [ ] Add item popularity trend chart (which items rising/falling)
- [ ] Add quick-order favorites per user (save frequently ordered combos)
- [ ] Add dark/light theme toggle with persistence
- [ ] Add offline order queuing (sync when connection restores)

## Priority: LOW

- [ ] Add customer-facing display mode (second screen showing order summary)
- [ ] Add barcode scanner support for item lookup (camera or hardware scanner)
- [ ] Add loyalty points system per customer
- [ ] Add scheduled pricing (happy hour, daily specials)
- [ ] Add waste tracking (items thrown away, reason)
- [ ] Add delivery address management
- [ ] Add integration webhook for third-party delivery apps
- [ ] Add table-side ads system — rotating promotional images/videos on table tablets between orders

## Done

- [x] **Kitchen queue audit & optimize** — Prominent color-coded order age (warning at 5m, critical at 10m+ with pulsing animation), 🚨 PRIORITY badge for orders >10min, quick-claim by tapping entire card body, enhanced 3-note square wave alarm sound, fixed stats endpoint keys (pending/preparing/done_today), 1s clock update, 10s age recheck interval. [worker-1]
- [x] **Table management system** — Admin assigns tablets to tables by table number. Orders tagged with table number. Running tab tracking per table. Table management in admin panel with tab view modal. Table number selector in cart. [worker-3]
- [x] **Drive-through order display** — Drive-through tablet/TV view at `/drivethrough`. Shows live cart building with 2s polling, large high-contrast text for outdoor visibility. Cashier toggles "Drive-Through" mode in POS to push cart state live. Shows items, running total, tax. "Please Pull Forward" screen when order submitted. High-contrast dark theme (#0a0a1a bg, #ff3366 accent, #00cc66 success).
- [x] Granular role/permission system — Three-tier roles (owner/admin/user/cook) with 10 granular permissions. Owner has ["*"] wildcard, can grant/revoke specific perms per admin. Ban/unban users with reason tracking. Permission-aware UI hides unauthorized sections.
- [x] Menu version history with restore — Every menu change auto-saves timestamped backup to menu_backups/. Owner browses backup dates, restores any day's menu with safety backup of current state. Keep last 30 backups.
- [x] Multi-language support — English + Spanish with browser language detection, language toggle button (globe) in top bar.
- [x] Kitchen display queue system — Full cook view: order queue with claim/complete/cancel, 8s auto-refresh, sound alerts, fullscreen mode, role-based routing (cook role), order status pipeline (pending→preparing→completed/cancelled)
- [x] Order notes field — per-item note input in cart items, per-order notes textarea in cart.
- [x] Receipt printing simulation — print-friendly HTML receipt with thermal printer CSS.
- [x] Discount/coupon code system — percentage and flat discounts with admin management.
- [x] Sales tax calculation support — configurable global, per-category, and per-item tax rates.
- [x] Touch-optimized item grid with category tabs
- [x] Most-ordered items analytics endpoint
- [x] Peak hour sales analytics
- [x] Daily revenue tracking
- [x] PWA manifest + service worker for installable app
- [x] Admin dashboard with Chart.js analytics

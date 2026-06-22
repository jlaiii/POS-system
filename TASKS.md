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
- [x] **Add tip calculation UI** — Percentage buttons (No tip/15%/18%/20%/Custom) in main POS cart tip row. Tip amount calculated on subtotal, displayed in cart total, submitted with order, shown on receipt, and displayed in order history. [worker-2]

## Priority: MEDIUM

- [x] Customer order lookup
- [x] Owner activity log filter
- [x] Export data to CSV/Excel
- [x] **Add date range filtering for order history and stats** — Added `date_from`/`date_to` params to `/api/admin_stats` endpoint with server-side filtering. Frontend: date range (from/to) inputs in Order History replacing single date, date range filter in Stats section. Stats cards adapt labels (Today's / Filtered Range). i18n English + Spanish. Backward-compatible. [worker-3]
- [~] worker-3 Add item popularity trend chart (which items rising/falling)
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

- [x] **Refund/void order functionality with reason tracking** — POST /api/orders/refund endpoint marks orders as refunded with reason, timestamp, and staff ID. Double-refund prevention. Refund audit trail in refunded_orders.json. Activity log integration. Frontend: refund button (with manage_orders permission) in order history, refund dialog with reason textarea, REFUNDED badge and reason on refunded orders. Stats exclude refunded orders from revenue. i18n English + Spanish. [worker-1]
- [x] **Table tab management** — Checkout/close tab endpoint (POST /api/tables/tab/<table_number>/checkout) marks all active orders as paid in one action. Tab history endpoint (GET /api/tables/tab/<table_number>/history) shows completed orders per table with total revenue. Frontend: "Close Tab & Checkout" button in tab overlay with payment method/tip/notes dialog, "📋 History" button per table in admin panel, tab history overlay with order details, and "➕ Add Items" quick-add button that auto-selects table in POS. [worker-3]
- [x] **Add inventory tracking** — Separate inventory.json tracked per item name. Stock decremented on order submission. Low-stock alerts (stock <= threshold) and out-of-stock detection. Admin inventory management UI with per-item stock/threshold editing and bulk init. Stock level badges on POS item cards (colored: green/ok, yellow/low, red/out). Out-of-stock items disabled with visual indicator. Low-stock toast warnings on order submit. Auto-creates inventory entries for new menu items. [worker-1]
- [x] **Add split-payment support** — Support multiple payment methods per order (Cash/Card/Mobile Pay). Toggle payment method buttons with individual amount inputs. Split Evenly button. Validation ensures splits equal total. Payment breakdown stored in `payment_splits` array. Displayed on receipt, order history, kitchen display, and kiosk mode. Backward-compatible with legacy single-payment orders. [worker-3]
- [x] **Add tip calculation UI** — Percentage buttons (No tip/15%/18%/20%/Custom) in main POS cart tip row. Tip calculated on subtotal, shown in cart total, submitted with order, displayed on receipt and order history. [worker-2]
- [x] **Add employee performance dashboard** — New `/api/employee_performance` endpoint with date range filtering, per-employee metrics (orders count, revenue, avg order value, tips, items sold). Frontend: admin sub-tab with summary cards and sortable table, i18n EN/ES, permission-gated (view_stats). [worker-2]
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

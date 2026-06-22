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
- [x] **Add barcode scanner support for item lookup (camera or hardware scanner)** — Barcode lookup endpoint `/api/items/barcode/lookup` and setter endpoint `/api/items/set_barcode`. Barcode field in item data model. Frontend: barcode input field (hardware scanner compatible via keyboard wedge Enter), camera scan button (BarcodeDetector API), barcode display in admin item management, barcode field in add/edit item forms. i18n EN + ES. [worker-2]

## Priority: MEDIUM

- [x] Customer order lookup
- [x] Owner activity log filter
- [x] Export data to CSV/Excel
- [x] **Add date range filtering for order history and stats** — Added `date_from`/`date_to` params to `/api/admin_stats` endpoint with server-side filtering. Frontend: date range (from/to) inputs in Order History replacing single date, date range filter in Stats section. Stats cards adapt labels (Today's / Filtered Range). i18n English + Spanish. Backward-compatible. [worker-3]
- [x] **Add item popularity trend chart (which items rising/falling)** — New `/api/analytics/item_trends` endpoint comparing recent 7d vs prior 7d item counts with % change, direction (rising/falling/stable), and sorting. Frontend: horizontal bar chart in Charts section with green/red/gray bars, tooltip showing counts and delta. i18n EN + ES. [worker-3]
- [x] **Add offline order queuing (sync when connection restores)** — `/api/health` GET for connectivity check, `/api/sync_orders` POST for batch submission of queued orders. Frontend: localStorage queue on network error, auto-sync on reconnect + 30s interval, offline badge indicator with count, receipt shows queued status. i18n EN + ES. [worker-3]

## Priority: HIGH (NEW — Audit 2026-06-22)

- [~] worker-1 **Add reorder button in order history** — One-click to reload all items from a past order into the cart. Major waiter speed improvement: eliminates need to manually re-add frequent orders.

## Priority: LOW

- [~] worker-1 Add scheduled pricing (happy hour, daily specials)
- [ ] Add waste tracking (items thrown away, reason)
- [ ] Add delivery address management
- [ ] Add integration webhook for third-party delivery apps
- [ ] Add table-side ads system — rotating promotional images/videos on table tablets between orders

## Done

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
- [x] **Add loyalty points system per customer** — New `loyalty_points.json` data store. `POST /api/loyalty/register`, `/lookup`, `/redeem`, `/confirm_redeem`, `/adjust`, and `GET /api/loyalty/customers` endpoints. Points auto-earned on order submission (1 pt per $1 subtotal). Redeem 100 pts = $5 off, applied as discount in cart. Frontend: customer phone lookup+register in cart area with points display, "Redeem Points" button, ⭐ Loyalty admin tab with customer table and points adjustment. Points earned shown in toast and on receipt. Activity logging. Dark theme compatible. Touch-friendly 44px+ targets. [worker-3]
- [x] **Admin dashboard with Chart.js analytics**

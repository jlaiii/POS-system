# POS System — Smart Task Queue

> Auto-managed by Hermes Cron. Worker picks 1 task every 30 min.
> Last updated: 2026-06-22

## Status Legend
- `[ ]` = pending
- `[~]` = in progress (worker has claimed it)
- `[x]` = completed
- `[-]` = cancelled / no longer relevant

## Priority: HIGH

- [ ] **Granular role/permission system** — Three roles (owner/admin/user/cook) with toggleable permissions per admin. Owner has all perms, can grant/revoke specific perms per admin (ban_users, manage_items, manage_users, view_logs, etc). Owner can revert admin changes.
- [ ] **Menu version history with restore** — Every menu change auto-saves a backup. Owner can browse backup dates and restore items.json to any previous day. Shows diff preview before confirming restore.
- [ ] **User ban/unban system** — Owner and admins with ban_users perm can ban a user (disables their login). Banned users show in admin panel with unban button. Ban reason is logged.
- [ ] **Kitchen queue audit & optimize** — Review the kitchen display system end-to-end. Make sure it's fast-paced friendly: minimize button taps, show order age prominently, add sound alerts for every new order, add priority flagging for orders waiting too long. Test the 8s polling under load.
- [ ] Add tip calculation UI (percentage buttons: 15%, 18%, 20%, custom)
- [ ] Add split-payment support (multiple payment methods per order)
- [ ] Add inventory tracking (decrement stock when ordered, alert on low stock)

## Priority: MEDIUM

- [ ] **Permission management UI** — Admin panel section where owner sees all admins with toggle switches per permission (ban_users on/off, manage_items on/off, etc). Changes take effect immediately.
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

- [x] Add multi-language support (start with Spanish — detect browser language)
- [ ] Add customer-facing display mode (second screen showing order summary)
- [ ] Add barcode scanner support for item lookup (camera or hardware scanner)
- [ ] Add loyalty points system per customer
- [ ] Add scheduled pricing (happy hour, daily specials)
- [ ] Add waste tracking (items thrown away, reason)
- [ ] Add table management for dine-in (assign orders to tables)
- [ ] Add delivery address management
- [ ] Add integration webhook for third-party delivery apps

## Done

- [x] Multi-language support — English + Spanish with browser language detection, language toggle button (globe) in top bar, translation dictionary (L10N), `t()` helper function, `data-i18n` attributes for static HTML, persistent language preference in localStorage, all major UI strings translated. Use the 🌐 globe button in top bar to switch between English and Español.

- [x] Kitchen display queue system — Full cook view: order queue with claim/complete/cancel, 8s auto-refresh, sound alerts, fullscreen mode, role-based routing (cook role), order status pipeline (pending→preparing→completed/cancelled)
- [x] Order notes field — per-item note input in cart items, per-order notes textarea in cart, notes displayed on receipt and order history, stored in backend order records
- [x] Receipt printing simulation — print-friendly HTML receipt with thermal printer CSS, overlay after order submit, re-print from order history, @media print styles for 80mm thermal printer format
- [x] Discount/coupon code system — percentage and flat discounts with admin management, coupon input in cart, discount validation endpoint, usage limits, min order amounts
- [x] Sales tax calculation support — configurable global, per-category, and per-item tax rates with cart tax breakdown, order history display, and admin Tax panel
- [x] Touch-optimized item grid with category tabs
- [x] Most-ordered items analytics endpoint
- [x] Peak hour sales analytics
- [x] Daily revenue tracking
- [x] PWA manifest + service worker for installable app
- [x] Admin dashboard with Chart.js analytics

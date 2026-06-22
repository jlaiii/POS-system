# POS System — Smart Task Queue

> Auto-managed by Hermes Cron. Worker picks 1 task every 30 min.
> Last updated: 2026-06-22

## Status Legend
- `[ ]` = pending
- `[~]` = in progress (worker has claimed it)
- `[x]` = completed
- `[-]` = cancelled / no longer relevant

## Priority: HIGH

- [x] Add order notes field (special instructions per item or per order)
- [ ] Add multi-language support (start with Spanish — detect browser language)
- [ ] Add tip calculation UI (percentage buttons: 15%, 18%, 20%, custom)
- [ ] Add split-payment support (multiple payment methods per order)
- [ ] Add inventory tracking (decrement stock when ordered, alert on low stock)
- [ ] Add customer-facing display mode (second screen showing order summary)
- [ ] Add kitchen/order display view (orders queue for prep staff)

## Priority: MEDIUM

- [ ] Add export data to CSV/Excel (orders, timesheet, activity log)
- [ ] Add date range filtering for order history and stats
- [ ] Add refund/void order functionality with reason tracking
- [ ] Add employee performance dashboard (orders per employee, avg order value)
- [ ] Add item popularity trend chart (which items rising/falling)
- [ ] Add quick-order favorites per user (save frequently ordered combos)
- [ ] Add sound/haptic feedback on order submit (tablet-friendly)
- [ ] Add dark/light theme toggle with persistence
- [ ] Add offline order queuing (sync when connection restores)
- [ ] Add barcode scanner support for item lookup (camera or hardware scanner)

## Priority: LOW

- [ ] Add loyalty points system per customer
- [ ] Add scheduled pricing (happy hour, daily specials)
- [ ] Add ingredient-level inventory for combo items
- [ ] Add waste tracking (items thrown away, reason)
- [ ] Add supplier/order management for restocking
- [ ] Add email/SMS receipts to customers
- [ ] Add table management for dine-in (assign orders to tables)
- [ ] Add delivery address management
- [ ] Add integration webhook for third-party delivery apps
- [ ] Add profit margin calculator per item

## Done

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

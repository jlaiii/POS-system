# POS Production Readiness Audit
> Last run: 2026-06-25 09:30 CT
> Overall readiness: 56% (HIGH issues: 7, MEDIUM: 7)
> Workflow tested this run: C (First-time setup — add items/categories/employees/tax/discounts/combos via API)

## BLOCKERS (can't go live with these)

*No blockers identified.* The previous blocker (no order review/confirmation step) was resolved by worker-2 — review modal with item breakdown, modifier display, undo toast with 30s countdown, and `/api/orders/undo` endpoint all exist and are functional.

## HIGH (major friction, fix ASAP)

- [ ] **font-size: 13px and 14px on ~30 UI elements — still too small for restaurant use** — Remaining small text across `.perm-table` (13px), `.log-entry` (13px), `.pp-preset` (13px), `.cart-item` (14px), `.ho-meta` (13px), `.ts-dense-table` (13px), allergen chips (13px), `.emp-perf-card h4` (13px), `.recent-order-info` (12px), `.item-stock` (12px), `.sale-badge` (11px), `.popular-badge` (11px), `.filter-count` (11px). A waiter reading order details on a tablet at arm's length needs minimum 16px body text. Some of these are dense data tables where 13px is acceptable if expandable, but key action labels and order info should be ≥16px.

- [ ] **Zero comprehensive responsive breakpoints — layout is identical on 10" tablet and 27" monitor** — style.css has @media rules (600/768/900/1200px, orientation breakpoints) but the overall layout doesn't adapt meaningfully between iPad portrait (768×1024) and a 27" monitor. Admin sub-tabs row (17+ buttons) can still overflow. Item grid column count is adaptive (2→3→4→5 cols). Cart is a bottom-sheet on portrait (35-40vh) with expand toggle. Missing: a dedicated @media (max-width: 768px) layout switch that reflows admin sidebar, makes modals full-width, and reorders Stats cards. Many elements still rely on the same desktop-like layout on all screen sizes.

- [ ] **No offline mode support notice** — When the server goes down, there's no cached fallback UI. The app simply stops working. For a real restaurant, network outages happen. The offline badge exists and sw.js is present, but there's no evidence of a functioning offline queue that survives a full disconnect. The `/api/sync_orders` endpoint handles reconnection but the frontend has no visible offline queuing mechanism for orders entered while disconnected.

- [ ] **POS tab bottom buttons hidden on short screens** — On a 768px tablet in portrait mode, the cart area with Submit Order, payment methods, tip buttons, and mode toggles can overflow below the fold. The user has to scroll to find Submit Order. The `#cart` has `max-height: 40vh` on mobile but actions are not sticky at the bottom — they're inline in the flex layout after cart items. Critical actions (Submit Order, Clear Cart) should be sticky at the bottom of the cart container.

- [ ] **Admin stats endpoint lacks refund-inclusive total_orders** — The admin_stats endpoint returns `total_traffic` and `total_orders` as the same value (both exclude refunded orders). A manager needs to see total order count INCLUDING refunds for shift reports, separate from the revenue calculation.

- [ ] **Server-side tax enforcement missing — tax_config.json is decorative** — The `global_tax_rate` stored in `tax_config.json` (currently set to 8.25%) is never enforced server-side during order submission. `submit_order()` takes `tax_amount` from the frontend verbatim (line 5308: `tax_amount = float(data.get('tax_amount', 0))`). The only server-side tax calculation happens when `tax_rate_override` is set per order-type and the frontend supplied `tax_amount == 0`. Any malformed request or frontend bug can submit orders with wrong tax. This is a data integrity AND fraud vector. TASKS.md has this as a pending MEDIUM task (`Add server-side tax recalculation on order submit and tax period reporting`). Needs HIGH priority.

- [ ] **Remaining small touch targets (44px minimum not universal)** — Fixes from previous sessions addressed the worst offenders (cartToggle → 44px, shift-edit-btn → 44px with `btn-sm`). However, `.btn-sm` class is 36px min-height, which is still below the 48px WCAG minimum for touch targets. Used for: shift edit buttons, ghost toggles, modifier option add/remove, pay period details buttons. A systematic audit is needed to ensure all interactive elements are ≥44px.

## MEDIUM (annoying but workable)

- [ ] **"Call Server" button on tablet has no notification in POS** — The tablet page has a "📞 Call Server" button that calls the backend endpoint. Waiters never know a customer needs them. The backend stores calls and a `server_call` WebSocket event is emitted, but POS has no listener. Worker-3 added polling fallback + endpoint but this remains partially functional.

- [ ] **Kitchen display is embedded in 19K-line POS page — slow on cheap tablets** — Standalone `/kitchen` page exists (288 lines, 20KB) created by worker-1. However, the main POS still loads the full kitchen view inline within the 19K-line index.html. For dedicated kitchen display tablets, the standalone page works great, but waiters switching to kitchen view on the POS still load the heavy inline version.

- [ ] **No loading skeleton states** — All async operations show empty or "Loading..." text instead of skeleton screens. Perceived performance is poor, especially on the item grid and order history where waiters are tapping impatiently. (Worker-2 added skeleton screens — this may be partially or fully resolved.)

- [ ] **No haptic feedback on order submit** — `navigator.vibrate(50)` gives physical confirmation that the order went through. In a noisy restaurant, waiters can't hear toasts but can feel vibration. (Worker-2 added vibration on submit.)

- [ ] **Payment field stored as object in order #55** — Order #55 has `payment: {"method": "cash", "amount": 6.0}` (a dict) instead of a string. `submit_order` should coerce dict payment values to string. Currently just stores whatever it receives — data integrity issue.

- [x] **No safe-area-inset support for notched devices** — Fixed this session: added `env(safe-area-inset-*)` padding to `.modal-overlay`, `#receiptOverlay`, `#kioskOverlay`, and `.toast`. See FIXED section.

- [ ] **API parameter naming inconsistency** — The `update_scheduled_start` endpoint expects `scheduledStart` (camelCase), while the field in users.json is `scheduled_start` (snake_case). The frontend is internally consistent, but this creates confusion for any API-level integration or testing. Other endpoints use snake_case consistently (e.g., `admin_pin`, `user_id`). This inconsistency will cause errors for developers or scripts interacting with the API.

- [ ] **User creation auto-assigns permissions with no customization** — `add_user()` assigns permissions based on role with defaults (cook = only `kitchen_access`, user = only `pos_access`). If a cook also needs to view the menu or a user needs `view_stats`, the admin must use a separate permission-update flow. For first-time setup of a restaurant, this adds friction — "create user → realize they can't see X → hunt for permission settings."

## LOW (polish, nice-to-have)

- [ ] No smooth tab transitions — Tab switching is instant/jarring (Update: smooth transitions added by worker-1. slideInRight/slideInLeft animations)
- [ ] No apple-touch-icon meta tags for iOS PWA (already has apple-mobile-web-app-* metas)
- [ ] Manifest.json only has SVG icon — no 192×192 or 512×512 PNG icons (Update: PNG icons added by worker-2)
- [ ] No auto-generated placeholder images for items added without image_url — When a new item is added via API with empty `image_url`, the card renders without any visual. For a customer-facing tablet menu, every item should have at minimum a gradient placeholder with the item name centered. The frontend already handles empty image_url gracefully (no broken images), but the visual result is a text-only card that looks unfinished next to items with photos.
- [ ] No admin notification when new employee is created — No broadcast to other admin sessions when a new user is added. In multi-manager restaurants, the owner might want visibility into who's creating accounts.

## FIXED (this session)

- [x] **BLOCKER: No checkout workflow confirmation** — Worker-2 added full order review modal with item breakdown, modifier display, per-item notes, subtotal/tax/discount/tip breakdown, payment display, table + email info. 30-second undo grace period with countdown toast. `/api/orders/undo` endpoint restores inventory. This was the last remaining BLOCKER.
- [x] **Added safe-area-inset padding to all position:fixed elements** — Added `env(safe-area-inset-*)` padding to `.modal-overlay`, `#receiptOverlay`, `#kioskOverlay` (fixed overlays), and `bottom: max(20px, env(safe-area-inset-bottom))` to `.toast`. Prevents content from being hidden behind notches, rounded corners, and home indicators on iPhone X+ and modern tablets. Files: style.css lines 373-375, 395, 404-406, 656-666.

## PREVIOUSLY FIXED (archive)

- [x] **`.shift-edit-btn` touch target 32px → 44px** — Shift edit button in timesheet was only 32px tall. Increased padding, min-height to 44px. Verified in style.css.
- [x] **`#cartToggle` touch target 32px → 44px** — Cart expand/collapse toggle was only 32×32px. Increased to 44×44px. Verified in style.css.
- [x] **All 13 `:hover` CSS rules now properly wrapped in `@media (hover: hover)`** — Commit: `80b3a81`
- [x] **All inventory items had stock=0 causing false "OUT OF STOCK" warnings** — Commit: `0d968ac`
- [x] **Cart quantity +/- buttons too small (30×30px)** — Increased to 48px. Commit: `0d968ac`
- [x] **Viewport meta disallowed user scaling** — Commit: `f4fe0a7`, re-fixed: `80b3a81`
- [x] **Added `touch-action: manipulation` to global button/input styles** — Commit: `0d968ac`
- [x] **Added responsive breakpoints, cart expand/collapse, full-width modals** — worker-1
- [x] **Added inline min-height: 32px buttons → .btn-sm class** — worker-3
- [x] **Loading skeleton screens** — worker-2
- [x] **Haptic feedback on order submit** — worker-2
- [x] **Zero items have images, descriptions, or dietary tags** — Fixed: all 14 original items now have SVG images, descriptions, dietary tags. SVGs exist in static/images/.

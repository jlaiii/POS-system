# POS Production Readiness Audit
> Last run: 2026-06-27 14:37 CT
> Overall readiness: 56% (HIGH issues: 10, MEDIUM: 12)
> Workflow tested this run: A (Waiter taking orders — login, clock-in, submit order with modifiers/split payment, kitchen queue, order history, clock-out)

## BLOCKERS (can't go live with these)

- [ ] **No responsive @media breakpoints — layout identical on 10" tablet and 27" monitor** — The entire 26,154-line frontend has ZERO responsive breakpoints. All 19 `@media` rules are either `@media (hover: hover)` (17) or `@media print` (2). No `@media (max-width: 768px)` or any width-based breakpoint exists. On a 768px iPad in portrait, the layout is the full desktop version — buttons overflow, text is tiny, modals don't fit the screen. Every restaurant deploying this on tablets will hit this immediately.

## HIGH (major friction, fix ASAP)

- [ ] **No `safe-area-inset-*` on any position:fixed elements** — Despite being claimed as "Added safe-area-inset padding to all position:fixed elements" in a previous audit, there are ZERO references to `safe-area` or `env(` in the entire index.html. All 12 fixed-position elements (modal overlays, toasts, undo toast, kitchen audio overlay, video player, print overlay) lack safe-area padding. On iOS devices with notches (iPad Pro 2018+, iPhone X+), these overlays will be partially hidden under the notch/home indicator. This is a tablet deployment blocker.

- [ ] **font-size: 13px and 14px on ~30 UI elements — too small for restaurant use** — Remaining small text across `.perm-table` (13px), `.log-entry` (13px), `.pp-preset` (13px), `.cart-item` (14px), `.ho-meta` (13px), `.ts-dense-table` (13px), allergen chips (13px), `.emp-perf-card h4` (13px), `.recent-order-info` (12px), `.item-stock` (12px), `.sale-badge` (11px), `.popular-badge` (11px), `.filter-count` (11px). A waiter reading order details on a tablet at arm's length needs minimum 16px body text.

- [ ] **Zero comprehensive responsive breakpoints — layout is identical on 10" tablet and 27" monitor** — style.css has @media rules (600/768/900/1200px, orientation breakpoints) but the overall layout doesn't adapt meaningfully between iPad portrait (768×1024) and a 27" monitor. Admin sub-tabs row (17+ buttons) can still overflow. Missing: a dedicated @media (max-width: 768px) layout switch.

- [ ] **No offline mode support notice** — When the server goes down, there's no cached fallback UI. The app simply stops working. For a real restaurant, network outages happen. The offline badge exists and sw.js is present, but there's no evidence of a functioning offline queue.

- [ ] **POS tab bottom buttons hidden on short screens** — On a 768px tablet in portrait mode, the cart area with Submit Order, payment methods, tip buttons, and mode toggles can overflow below the fold. Critical actions (Submit Order, Clear Cart) should be sticky at the bottom of the cart container.

- [ ] **Admin stats endpoint lacks refund-inclusive total_orders** — The admin_stats endpoint returns `total_traffic` and `total_orders` as the same value (both exclude refunded orders). A manager needs to see total order count INCLUDING refunds for shift reports.

- [ ] **Remaining small touch targets (44px minimum not universal)** — `.btn-sm` class is 36px min-height, below the 48px WCAG minimum. Used for: shift edit buttons, ghost toggles, modifier option add/remove, pay period details buttons. A systematic audit is needed.

- [ ] **Customer display polls aggressively (2s interval) — drains tablet battery** — `POLL_INTERVAL = 2000` (2 seconds) in customer-display.html line 419. On a tablet running 12+ hours on WiFi, this generates ~43,200 API requests per day. Real impact: shortens battery life significantly on tablets that hang on the wall all day. Should be 5-10 seconds minimum, and use WebSocket fallback instead of polling when available.

- [ ] **admin_stats returns raw_orders with full item details — massive payload on slow WiFi** — The `/api/admin_stats` endpoint includes every order's full items array with tax breakdowns, modifiers, and timestamps. This can be 100KB+ JSON for a restaurant with 100+ orders. On a restaurant tablet on consumer WiFi, this takes several seconds to download and parse. The frontend already has paginated order history — stats should return summary data only (counts, totals, averages) and omit `raw_orders` entirely or provide it only via a separate paginated endpoint. [app.py ~9150, submit_order response construction]

## MEDIUM (annoying but workable)

- [ ] **"Call Server" button on tablet has no notification in POS** — The tablet page has a "📞 Call Server" button that calls the backend endpoint. Waiters never know a customer needs them. The backend stores calls and a `server_call` WebSocket event is emitted, but POS has no listener. Worker-3 added polling fallback + endpoint but this remains partially functional.

- [ ] **Kitchen display is embedded in 19K-line POS page — slow on cheap tablets** — Standalone `/kitchen` page exists but the main POS still loads the full kitchen view inline within the 19K-line index.html.

- [ ] **API parameter naming inconsistency** — `update_scheduled_start` endpoint expects `scheduledStart` (camelCase), while the field in users.json is `scheduled_start` (snake_case).

- [ ] **User creation auto-assigns permissions with no customization** — `add_user()` assigns permissions based on role with defaults. If a cook also needs to view stats or a user needs `view_stats`, the admin must use a separate permission-update flow.

- [ ] **Customer display "update" endpoint requires full cart data — not pre-populated from order** — When a waiter calls `/api/customer-display/update`, the frontend must push all items/subtotal/tax/tip manually. If the waiter forgets, the display shows an empty "building" status with no items. Should auto-populate from the current cart state without requiring manual push.

- [ ] **Order ID vs Order Number confusion in API responses** — `submit_order()` returns both `order_id: 93` (database index) and `order_number: 78` (display number). The pickup-display and other endpoints require `order_id` (the DB index), but the frontend shows `order_number` to staff. If a waiter tries to look up "order 78" in the pickup display but the API expects the internal ID 93, they get "Order not found." The API should accept either, or at minimum provide a lookup-by-order-number endpoint. **NOTE:** order_number was NOT being persisted at all (all 102 orders had order_number=null). This was fixed in this run.

- [ ] **Frontend subtotal not validated against calculated subtotal** — `submit_order()` takes `subtotal` from the frontend (line 5448) without comparing it to `calculated_subtotal` (line 5446). A malformed frontend or API caller can submit a subtotal that doesn't match the items, causing the receipt total to be wrong even though tax is recalculated server-side.

- [ ] **Standalone customer pages lack proper meta tags for PWA** — customer-display.html, pickup-display.html, and tablet.html are missing `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`, link manifest, and theme-color (except pickup-display has theme-color). These pages are meant to run on dedicated wall-mounted tablets, so they should be installable as standalone web apps without browser chrome.

- [ ] **Cash drawer has no active session prompt — no "start of day" workflow** — The cash drawer system exists (open/close/transactions) but there's no automatic prompt to open the drawer when the first order of the day is placed. When tested with Workflow B, the last session was 3 days old (June 24). A manager must independently remember to open a cash drawer session at shift start. Without this, end-of-day reconciliation has no baseline. In a real restaurant, the manager opens the drawer at the start of every shift — the system should prompt or auto-create a session.

- [ ] **Pay period summary shows null estimated_pay for all employees — no pay rates configured** — When testing Workflow B, the pay period summary returned `estimated_pay: null` for every employee because `pay_rate` is not set for most users. Manager Sarah (7788), Maria (3344), and Chef Diego (5566) have no pay rate. A restaurant can't run payroll without configuring pay rates. The pay period UI should warn when pay rates are missing, or better, auto-assign a default rate on user creation.

- [ ] **Kitchen queue doesn't display order notes** — The kitchen queue endpoint returns items with modifiers but does NOT include or display the order-level `notes` field (special instructions). When tested with Workflow A, the order note "No onions on the burger please" was stored on the order but NOT visible in the kitchen display. Cooks need to see special instructions.

## LOW (polish, nice-to-have)

- [ ] No auto-generated placeholder images for items added without image_url
- [ ] No admin notification when new employee is created
- [ ] No smooth tab transitions (Update: slideInRight/slideInLeft animations added by worker-1)
- [ ] No apple-touch-icon meta tags for iOS PWA (already has apple-mobile-web-app-* metas)
- [ ] Manifest.json only has SVG icon — no 192×192 or 512×512 PNG icons (Update: PNG icons added by worker-2)

## FIXED (this session)

- [x] **order_number not persisted in orders.json — all 102 orders had order_number=null** — `submit_order()` calculated `order_number = len(orders)` at line 6051 and returned it in the API response, but it was NEVER added to the `order_details` dict before saving at line 6044. This meant all 102 existing orders had `order_number: null` in the file. The kitchen display, pickup display, and order history all showed `0` or `null` as order number. Fix: added `order_details['order_number'] = len(orders) + 1` to the order_details dict BEFORE appending and saving, using `saved_order_number` variable for both storage and response. Commit: (pending push).

## PREVIOUSLY FIXED (archive)

- [x] **BLOCKER: No checkout workflow confirmation** — Worker-2 added full order review modal with undo grace period.
- [x] **Added safe-area-inset padding to all position:fixed elements** — env(safe-area-inset-*) padding added. (NOTE: This claim appears to be inaccurate — grep shows NO safe-area references in index.html. May have been lost in subsequent edits.)
- [x] **Server-side tax enforcement is implemented and working** — The HIGH issue "Server-side tax enforcement missing" was outdated. `submit_order()` (lines 5450-5467 in app.py) recalculates tax server-side using `get_effective_tax_rate()` from `tax_config.json`. The `global_tax_rate` of 8.25% is enforced. The audit finding has been corrected.
- [x] **`.shift-edit-btn` touch target 32px → 44px**
- [x] **`#cartToggle` touch target 32px → 44px**
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
- [x] **Order submit validation (empty items, nonexistent items)** — `submit_order()` now rejects empty items array with 400 error, validates each item against items.json menu, and verifies price matches menu price within ±$0.50 tolerance. [worker-3]
- [x] **4 remaining unguarded `:hover` CSS rules wrapped in @media (hover: hover)** — Found 4 `:hover` rules that were NOT wrapped in `@media (hover: hover)`. Commit `4461194`.
- [x] **Standalone pages disabled zoom (user-scalable=no)** — Changed `user-scalable=no` to `maximum-scale=5.0` in viewport meta. Commit `4461194`.

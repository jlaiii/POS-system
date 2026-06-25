# POS Production Readiness Audit
> Last run: 2026-06-25 00:30 CT
> Overall readiness: 46% (HIGH issues: 7, MEDIUM: 5)
> Workflow tested this run: A (Waiter taking orders — table 5 split payment, table 6 card)

## BLOCKERS (can't go live with these)

- [ ] **No checkout workflow confirmation — order submits immediately without review** — When a waiter taps "Submit Order" in the cart, it submits immediately. No "Review Order" step showing full breakdown with modifiers, notes, and total before final submit. Many POS systems have a 2-step: Cart → Review → Submit. Prevents costly mistakes (wrong modifiers, forgot items, wrong payment splits). In a real restaurant, this causes awkward "can you fix my order" conversations. Also: no undo/void-within-30s grace period.

## HIGH (major friction, fix ASAP)

- [ ] **font-size: 13px and 14px on 38+ UI elements — too small for restaurant use** — 38 instances of `font-size: 13px` or `14px` across index.html and style.css (down from 306 in previous audit due to CSS consolidation). Remaining small text: `.perm-table` (13px), `.log-entry` (13px), `.pp-preset` (13px), `.cart-item` (14px), `.ho-meta` (13px), `.ts-dense-table` (13px), allergen chips (13px), `.emp-perf-card h4` (13px), `.recent-order-info` (12px), `.item-stock` (12px), `.sale-badge` (11px), `.popular-badge` (11px), `.filter-count` (11px). Minimum body text should be 16px for production restaurant use. Partially addressed from previous audits but still pervasive in data-dense views.

- [ ] **Zero comprehensive responsive breakpoints — layout is identical on 10" tablet and 27" monitor** — style.css has comprehensive @media rules (600/768/900/1200px, orientation, 399px, 640px), but the overall layout doesn't adapt meaningfully between iPad portrait (768×1024) and a 27" monitor. Admin sub-tabs row (17+ buttons) can still overflow. Item grid column count is good (2→3→4→5 cols). Cart is a bottom-sheet on portrait (35vh) with expand toggle. Missing: dedicated @media (max-width: 768px) layout switch that reflows admin sidebar, makes modals full-width, and reorders Stats cards. Many elements still rely on the same desktop-like layout on all screen sizes.

- [ ] **No offline mode support notice** — When the server goes down, there's no cached fallback UI. The app simply stops working. For a real restaurant, network outages happen. The offline badge exists but there's no evidence of a functioning offline queue with SW (service worker).

- [ ] **POS tab bottom buttons hidden on short screens** — On a 768px tablet in portrait mode, the cart area with Submit Order, payment methods, tip buttons, and mode toggles can overflow below the fold. The user has to scroll to find Submit Order. Critical actions (Submit Order, Clear Cart) should be sticky/fixed at the bottom of the cart.

- [ ] **Admin stats missing `total_orders` field** — The admin_stats endpoint returns `total_traffic` but no `total_orders` field. The `total_traffic` number excludes refunded orders (correct for revenue), but a manager also needs to see total order count (including refunds) for shift reports.

- [ ] **Item cards show empty gray image placeholder boxes** — All item cards have a `.item-thumb` container with 80px height but since no items have `image_url` set for some test items, they render as empty gray rectangles. The production items (Foods/Drinks/Snacks) all have `image_url` set to SVG files in `static/images/` — these SVGs exist. But any new item added without an image_url will show the empty gray box. Either hide the thumbnail when no image is available, or add default gradient placeholders.

- [ ] **Remaining small touch targets (44px minimum not universal)** — `.shift-edit-btn` was at 32px (now fixed to 44px), `#cartToggle` was at 32px (now fixed to 44px). Some secondary buttons use `.btn-sm` at 36px. Add systematic audit to ensure all tap targets are ≥ 44px.

## MEDIUM (annoying but workable)

- [ ] **"Call Server" button on tablet has no notification in POS** — The tablet page has a "📞 Call Server" button that calls the backend endpoint. But the main POS has no polling or WebSocket listener for incoming server calls. Waiters never know a customer needs them. The WebSocket event `server_call` is emitted but nothing listens for it in the POS. TASKS.md has this as a pending task but it's been sitting open.

- [ ] **Kitchen display is embedded in 19K-line POS page — slow on cheap tablets** — The kitchen view is part of the massive index.html (19K lines, ~960KB). For $100 Android tablets used as kitchen displays, this is slow to load (~5s+). A standalone `/kitchen` page (~200 lines) would load in <1s. TASKS.md has this as a pending task. **Update: `/kitchen` standalone page was created by worker-1 (288 lines, 20KB).** However, the main POS still loads the full index.html with kitchen view inline.

- [ ] **No loading skeleton states** — All async operations show empty or "Loading..." text instead of skeleton screens. Perceived performance is poor, especially on the item grid and order history where waiters are tapping impatiently. **Update: Skeleton screens were added by worker-2. This may be partially or fully resolved.**

- [ ] **No haptic feedback on order submit** — `navigator.vibrate(50)` gives physical confirmation that the order went through. In a noisy restaurant, waiters can't hear toasts but can feel vibration. **Update: Vibration was added by worker-2. Both submitOrder() and kioskPayNow() vibrate on success.**

- [ ] **Payment field stored as object in order #55** — Order #55 has `payment: {"method": "cash", "amount": 6.0}` (a dict) instead of a string. Submit_order should coerce dict payment values to string. Currently just stores whatever it receives — data integrity issue.

## LOW (polish, nice-to-have)

- [ ] No smooth tab transitions — Tab switching is instant/jarring (Update: smooth transitions added by worker-1. slideInRight/slideInLeft animations)
- [ ] No apple-touch-icon meta tags for iOS PWA (already has apple-mobile-web-app-* metas)
- [ ] Manifest.json only has SVG icon — no 192×192 or 512×512 PNG icons (Update: PNG icons added by worker-2)
- [ ] **No safe-area-inset support for iPhone X+ notched devices** — All `position: fixed` elements and modals should use `padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)` to prevent content from being hidden behind the notch or home indicator.
- [ ] **`.kiosk-lookup-msg` has min-height: 32px** — Not a touch target (text display only), but inconsistent sizing.

## FIXED (this session)

- [x] **`.shift-edit-btn` touch target 32px → 44px** — Shift edit button in timesheet was only 32px tall, below the 48px minimum touch target. Increased padding (4px→8px), min-height (32px→44px), border-radius (4px→6px) for larger, more tappable surface. File: style.css line 303-315. Commit: pending.
- [x] **`#cartToggle` touch target 32px → 44px** — Cart expand/collapse toggle button was only 32×32px. Increased to 44×44px with adjusted padding for comfortable tapping on tablets. File: style.css line 809. Commit: pending.

## PREVIOUSLY FIXED (archive)

- [x] **All 13 `:hover` CSS rules now properly wrapped in `@media (hover: hover)`** — Commit: `80b3a81`
- [x] **All inventory items had stock=0 causing false "OUT OF STOCK" warnings** — Commit: `0d968ac`
- [x] **Cart quantity +/- buttons too small (30×30px)** — Increased to 48px. Commit: `0d968ac`
- [x] **Viewport meta disallowed user scaling** — Commit: `f4fe0a7`, re-fixed: `80b3a81`
- [x] **Added `touch-action: manipulation` to global button/input styles** — Commit: `0d968ac`
- [x] **Added responsive breakpoints, cart expand/collapse, full-width modals** — worker-1
- [x] **Added inline min-height: 32px buttons → .btn-sm class** — worker-3
- [x] **Loading skeleton screens** — worker-2
- [x] **Haptic feedback on order submit** — worker-2
- [x] **Zero items have images, descriptions, or dietary tags** — Fixed: all 14 items now have SVG images, descriptions, dietary tags. SVGs exist in static/images/.

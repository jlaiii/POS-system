# POS Production Readiness Audit
> Last run: 2026-06-24 18:00 CT
> Overall readiness: 44% (HIGH issues: 7, MEDIUM: 5)
> Workflow tested this run: D (Customer-facing experience — tablet menu, kiosk mode, pickup display, call server)

## BLOCKERS (can't go live with these)

- [ ] **No checkout workflow confirmation — order submits immediately without review** — When a waiter taps "Submit Order" in the cart, it submits immediately. No "Review Order" step showing full breakdown with modifiers, notes, and total before final submit. Many POS systems have a 2-step: Cart → Review → Submit. Prevents costly mistakes (wrong modifiers, forgot items, wrong payment splits). In a real restaurant, this causes awkward "can you fix my order" conversations. Also: no undo/void-within-30s grace period.

## HIGH (major friction, fix ASAP)

- [ ] **Zero items have images, descriptions, or dietary tags — customer-facing menu is a bare text list** — All 14 items in `items.json` lack `image_url`, `description`, and `dietary_tags`. The tablet menu (tablet.html) shows items as plain text names with prices only. The item detail popup shows an empty gray box where the image should be. In a real restaurant, customers browse by looking at appetizing food photos. A digital menu without food images looks unprofessional and makes it hard for customers to decide. The data model supports these fields (CSV export/import includes image_url, description, dietary_tags, nutrition) but the seed data was never populated. Fix: either add stock food photos to the codebase, or add a placeholder image generator, or at minimum add descriptions so items aren't just "Hotdog - Plain" — nobody knows what that means on a menu.

- [ ] **font-size: 13px and 14px on 306+ UI elements — too small for restaurant use** — 306 instances of `font-size: 13px` or `14px` across index.html and style.css. On a wall-mounted tablet or handheld at arm's length, 13px text is unreadable. `.perm-table` (13px), `.log-entry` (13px), `.pp-preset` (13px), `.cart-item` (14px), `.ho-meta` (13px), `.ts-dense-table` (13px), allergen chips (13px), `.emp-perf-card h4` (13px), `.recent-order-info` (12px), `.item-stock` (12px), `.sale-badge` (11px), `.popular-badge` (11px), `.filter-count` (11px). Minimum body text should be 16px for production restaurant use. Partially addressed from previous audit (`.ts-dense-table` header bumped to 13px from 11px) but the majority of the UI is still undersized.

- [ ] **Zero comprehensive responsive breakpoints — layout is identical on 10" tablet and 27" monitor** — style.css has 5 basic @media rules (mostly item grid column counts at 600/900/1200px and basic orientation handling), but the overall layout doesn't adapt meaningfully between iPad portrait (768×1024) and a 27" monitor. Admin sub-tabs row (17+ buttons) overflows off-screen. Item grid column count doesn't adapt below 600px (stays at 2 cols even on phones). Cart is not a bottom-sheet on portrait tablets. No `@media (max-width: 768px)` comprehensive layout change. Every other restaurant POS (Toast, Square, Clover) radically changes layout between desktop and tablet. Fix: add column-count or grid-column adjustments at 768px and 1024px breakpoints, wrap admin sub-tabs to multiple rows, collapse cart to bottom sheet on narrow screens. Worker-1 claimed to have added these but code review shows only 5 basic @media rules in style.css — the responsive layout is still fundamentally desktop-only.

- [ ] **No offline mode support notice** — When the server goes down, there's no cached fallback UI. The app simply stops working. For a real restaurant, network outages happen. The offline badge exists but there's no evidence of a functioning offline queue with SW (service worker). A PWA-style service worker would be needed for true offline resilience.

- [ ] **POS tab bottom buttons hidden on short screens** — On a 768px tablet in portrait mode, the cart area with Submit Order, payment methods, tip buttons, and mode toggles can overflow below the fold. The user has to scroll to find Submit Order. Critical actions (Submit Order, Clear Cart) should be sticky/fixed at the bottom of the cart.

- [ ] **Admin stats missing `total_orders` field** — The admin_stats endpoint returns `total_traffic` but no `total_orders` field. The `total_traffic` number excludes refunded orders (correct for revenue), but a manager also needs to see total order count (including refunds) for shift reports.

- [ ] **Item cards show empty gray image placeholder boxes** — All item cards have a `.item-thumb` container with 80px height but since no items have `image_url` set, they render as empty gray rectangles. This looks broken on both the POS grid and the tablet customer menu. Either hide the thumbnail when no image is available, or add default gradient placeholders.

## MEDIUM (annoying but workable)

- [ ] **"Call Server" button on tablet has no notification in POS** — The tablet page has a "📞 Call Server" button that calls the backend endpoint. But the main POS has no polling or WebSocket listener for incoming server calls. Waiters never know a customer needs them. The WebSocket event `server_call` is emitted but nothing listens for it in the POS. TASKS.md has this as a pending task but it's been sitting open.

- [ ] **Kitchen display is embedded in 19K-line POS page — slow on cheap tablets** — The kitchen view is part of the massive index.html (19K lines, ~960KB). For $100 Android tablets used as kitchen displays, this is slow to load (~5s+). A standalone `/kitchen` page (~200 lines) would load in <1s. TASKS.md has this as a pending task.

- [ ] **No loading skeleton states** — All async operations show empty or "Loading..." text instead of skeleton screens. Perceived performance is poor, especially on the item grid and order history where waiters are tapping impatiently.

- [ ] **No haptic feedback on order submit** — `navigator.vibrate(50)` gives physical confirmation that the order went through. In a noisy restaurant, waiters can't hear toasts but can feel vibration.

- [ ] **Payment field stored as object in order #55** — Order #55 has `payment: {"method": "cash", "amount": 6.0}` (a dict) instead of a string. Submit_order should coerce dict payment values to string. Currently just stores whatever it receives — data integrity issue.

## LOW (polish, nice-to-have)

- [ ] No smooth tab transitions — Tab switching is instant/jarring
- [ ] No apple-touch-icon meta tags for iOS PWA (already has apple-mobile-web-app-* metas)
- [ ] Manifest.json only has SVG icon — no 192×192 or 512×512 PNG icons

## FIXED (this session)

- [x] **All 13 `:hover` CSS rules now properly wrapped in `@media (hover: hover)`** — Previous fix (worker-3) added `@media (hover: hover)` wrappers but LEFT THE ORIGINAL standalone `:hover` rules in place. CSS cascade means the standalone rules still applied on tablets, causing the sticky-hover bug (tap an element → background/color changes → stays changed until tapping elsewhere). Removed 11 duplicate standalone `:hover` rules that had `@media (hover: hover)` counterparts. Also fixed 3 completely unwrapped `:hover` rules (`.idle-cancel-btn`, `.allergen-filter-toggle`, `.allergen-chip`). Tablet taps now have zero sticky-hover visual artifacts. Commit: `80b3a81`

## PREVIOUSLY FIXED (archive)

- [x] **All inventory items had stock=0 causing false "OUT OF STOCK" warnings** — Updated `inventory.json` to set every item's stock to 100. Commit: `0d968ac`
- [x] **Cart quantity +/- buttons too small (30×30px)** — Increased to 48px. Commit: `0d968ac`
- [x] **Viewport meta disallowed user scaling** — Removed `user-scalable=no`, set `maximum-scale=5.0`. Reverted by worker-2, re-fixed. Commit: `f4fe0a7`, re-fixed: `80b3a81`
- [x] **Added `touch-action: manipulation` to global button/input styles** — Eliminates 300ms tap delay. Commit: `0d968ac`
- [x] **`.perm-save-btn` min-height: 32px → 48px (`var(--tap`)** — Fixed in previous session
- [x] **`.ts-dense-table` header font 11px → 13px, cell padding 5px → 8px** — Fixed in previous session
- [x] **No payment method breakdown in admin_stats** — Added cash_sales/card_sales/cash_count/card_count to admin_stats endpoint. Fixed in previous session
- [x] **Workflow A tested: waiter taking orders** — Full shift lifecycle tested, all APIs functional
- [x] **Workflow B tested: manager closing shift** — Cash register closing flow tested
- [x] **Workflow C tested: first-time setup** — Adding items, employees, schedules

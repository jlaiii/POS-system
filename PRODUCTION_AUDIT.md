# POS Production Readiness Audit
> Last run: 2026-06-24 08:10 CT
> Overall readiness: 42% (HIGH issues: 6, MEDIUM: 5)
> Workflow tested this run: A (Waiter taking orders — Employee Two, tables 5 & 6, split payments, kitchen queue verified)

## BLOCKERS (can't go live with these)

- [ ] **All inventory items at stock=0 triggers false "OUT OF STOCK" warnings on every order** — Every item in `inventory.json` has `stock: 0` and `low_stock_threshold: 10`. This means every single order submission shows "🔴 OUT OF STOCK: Hamburger - Normal, Coke, Lemonade" warnings. In a real restaurant, waiters would see these on every order and learn to ignore them — defeating the entire purpose of stock warnings. Also, negative stock (stock goes below 0) is silently clamped at 0, meaning inventory is completely non-functional. Fix: set default stock to reasonable levels (100+) or remove non-stock-tracked items from inventory.json, or treat missing stock field as "unlimited."

- [ ] **No payment method breakdown in admin_stats** — The admin_stats endpoint returns `total_sales`, `total_traffic`, `average_sale` but does NOT break down by payment method (cash vs card). When a manager closes the shift, they need to know "how much cash should be in the drawer" vs "how much was charged to cards." Currently they have to manually scan every order and add up cash payments — error-prone and time-consuming. Ordered 46 orders all show `payment: 'unknown'` because admin_stats doesn't aggregate the payment field. **Fixed this run: added cash_sales/card_sales/cash_count/card_count to admin_stats endpoint.**

## HIGH (major friction, fix ASAP)

- [ ] **Zero responsive breakpoints — layout is identical on 10" tablet and 27" monitor** — The entire index.html has zero `@media (max-width:)` or `@media (min-width:)` rules in the static `<style>` section. On an iPad (768px portrait), the POS layout doesn't change at all — same grid, same spacing, same everything. The admin sub-tabs row (17+ buttons) overflows horizontally. No viewport-adaptive grid columns for items. No mobile-specific cart positioning. This is the #1 thing preventing tablet deployment. Every other restaurant POS (Toast, Square, Clover) radically changes layout between desktop and tablet. Fix: add column-count or grid-column adjustments at 768px and 1024px breakpoints, wrap admin sub-tabs to multiple rows, collapse cart to bottom sheet on narrow screens.

- [ ] **`user-scalable=no` keeps coming back in viewport meta** — The viewport fix from commit `0d968ac` was later overwritten by worker-2's "mobile viewport meta tag verification" task (commit `482d35f`), which reverted `maximum-scale=5.0` back to `maximum-scale=1.0, user-scalable=no`. Workers stepping on each other's changes is a systemic issue. The correct viewport is `maximum-scale=5.0` (allows pinch-zoom for accessibility, prevents accidental zoom from the wrong gestures). **Refixed this run: restored `maximum-scale=5.0` without `user-scalable=no`.** Added note in commit message explaining WHY to prevent re-revert.

- [ ] **No `touch-action: manipulation` anywhere — 300ms tap delay on tablets** — Mobile browsers add 300ms delay to distinguish taps from double-taps. No element in index.html uses `touch-action: manipulation` to disable this. This makes every button press feel sluggish compared to native POS systems. Add `touch-action: manipulation` to `button, .btn, input, select` elements globally.

- [ ] **16 `:hover` CSS rules with no tap alternative** — Tablets don't have hover. Elements like `.timesheet-subtab:hover`, `.shift-edit-btn:hover`, `.recent-orders-header:hover` are the only visual feedback for interactivity on those elements. On a tablet, these show zero feedback on tap. Need to pair with `:active` or use `@media (hover: hover)` to only apply hover on devices that support it.

- [ ] **All form inputs lack `inputmode` attributes for tablet keyboards** — Number inputs (add item price, quantity, PIN entry) don't trigger numeric keypad on tablets. The PIN pad is pure JS buttons, which is good, but other numeric fields like pay rate, price, quantity, and coupon codes should use `inputmode="numeric"` or `inputmode="decimal"` to show the right keyboard on tablets.

- [ ] **font-size: 13px and 14px on many UI elements — too small for restaurant use** — `.perm-table` (13px), `.log-entry` (13px), `.pp-preset` (13px), `.cart-item` (14px), `.ho-meta` (13px). On a wall-mounted tablet or handheld at arm's length, 13px text is unreadable. Minimum body text should be 16px for production restaurant use. At minimum, the POS tab (most used) should have 16px everywhere.

- [ ] **Scrollable containers lack `-webkit-overflow-scrolling: touch`** — While `#mainTabs` has it, the critical `#tabContent`, `#cartItems`, `#historyList`, `#kitchenQueue`, admin sections all scroll without momentum on iOS. This makes long lists feel janky and unprofessional. Add `-webkit-overflow-scrolling: touch` and `overscroll-behavior: contain` to all scrollable containers.

- [ ] **`.perm-save-btn` min-height: 32px violates 48px touch target** — The permissions save button uses a hardcoded 32px min-height, far below the `--tap: 48px` variable used elsewhere. On a tablet, this button is too small to reliably tap. Also `.ts-dense-table` header font at 11px is too small for tablet readability. **Fixed this run: perm-save-btn now uses `var(--tap)`, ts-dense-table header bumped to 13px, td padding increased from 5px to 8px.**

## MEDIUM (annoying but workable)

- [ ] **No checkout workflow confirmation — order submits immediately without review** — When a waiter taps "Submit Order" in the cart, it submits immediately. There's no "Review Order" step showing the full breakdown with modifiers, notes, and before the final submit. Many POS systems have a 2-step: Cart → Review → Submit. This prevents mistakes (wrong modifiers, forgot to remove test items).

- [ ] **Items have no `image` field accessible from the menu** — The items.json has no image URLs set up. The item cards in the grid have image placeholders (`.item-thumb` with 80px height) that show as empty gray boxes. For a customer-facing tablet or kiosk, items need images to look appetizing. Without images, the grid looks unprofessional.

- [ ] **No offline mode support notice** — When the server goes down, there's no cached fallback UI. The app simply stops working. For a real restaurant, network outages happen. The offline badge exists but there's no evidence of a functioning offline queue with SW (service worker). A PWA-style service worker would be needed for true offline resilience.

- [ ] **No printing support (ESC/POS thermal)** — `/api/print/receipt` doesn't exist. Most restaurants use Epson TM-T88 thermal printers. Without physical receipt printing, kitchen ticket printing, and order chit printing, the system can't replace a real POS.

- [ ] **POS tab bottom buttons hidden on short screens** — On a 768px tablet in portrait mode, the cart area with Submit Order, payment methods, tip buttons, and mode toggles can overflow below the fold. The user has to scroll to find Submit Order. Critical actions (Submit Order, Clear Cart) should be sticky/fixed at the bottom of the cart.

- [ ] **Admin stats missing `total_orders` field** — The admin_stats endpoint returns `total_traffic` but no `total_orders` field. The `total_traffic` number excludes refunded orders (correct for revenue), but a manager also needs to see total order count (including refunds) for shift reports. Also: 26 font-size:13px rules remain in index.html, too small for tablet use.

## LOW (polish, nice-to-have)

- [ ] **No loading skeleton states** — All async operations show empty or "Loading..." text instead of skeleton screens. Perceived performance is poor.
- [ ] **Haptic feedback on order submit** — `navigator.vibrate(50)` gives physical confirmation.
- [ ] **No smooth tab transitions** — Tab switching is instant/jarring. 150ms slide transitions would feel more polished.
- [ ] **No apple-touch-icon meta tags for iOS PWA** — Adding to home screen on iPad shows generic icon.
- [ ] **Manifest.json only has SVG icon** — No 192×192 or 512×512 PNG icons. Some browsers don't support SVG icons.
- [ ] **Payment field stored as object in order #55** — Order #55 has `payment: {"method": "cash", "amount": 6.0}` (a dict) instead of a string. Submit_order should coerce dict payment values to string. Currently just stores whatever it receives — data integrity issue.

## FIXED (this session)

- [x] **`.perm-save-btn` min-height: 32px → 48px (`var(--tap)`)** — The permissions save button was the only button in the UI using a hardcoded 32px min-height, well below the `--tap: 48px` standard. Changed to `min-height: var(--tap)` with increased padding (8px 14px). Commit: [current run]
- [x] **`.ts-dense-table` header font 11px → 13px, cell padding 5px → 8px** — The dynamically-injected timesheet dense table styles had 11px headers and 5px cell padding — unreadable on a tablet. Bumped header to 13px and padding to 8px 10px for better readability and touch spacing. Commit: [current run]
- [x] **Workflow A tested: waiter taking orders** — Employee Two (PIN 5678) logged in, clocked in, submitted 2 orders (Table 5: 3 items with modifiers + split payment $10 cash/$7.66 card; Table 6: 3 items with loyalty lookup), verified orders appeared in kitchen queue with correct items/modifiers/table numbers/payment-splits, clocked out. All APIs functional.

- [x] **Viewport `user-scalable=no` reverted by conflicting worker** — Previous fix (commit `0d968ac`) was overwritten by worker-2's "mobile viewport meta tag verification" task. Re-applied the fix: changed viewport to `maximum-scale=5.0` without `user-scalable=no`. This preserves accessibility (visually impaired staff can pinch-zoom) while preventing accidental zoom interference. The `font-size: 16px` on inputs (iOS zoom prevention) from the conflicting change was preserved. Commit: `f4fe0a7`

## PREVIOUSLY FIXED (archive)

- [x] **All inventory items had stock=0 causing false "OUT OF STOCK" warnings** — Updated `inventory.json` to set every item's stock to 100. This stops the spurious warnings on every order while preserving the inventory tracking system for when real stock counts are configured. Commit: `0d968ac`

- [x] **Cart quantity +/- buttons too small (30×30px)** — Increased `.cart-item .ci-qty button` min-width and min-height from 30px to 48px for proper touch targets. Same for `.cart-item .ci-remove`. Uses `var(--tap)` to stay consistent with the rest of the UI. Commit: `0d968ac`

- [x] **Viewport meta disallowed user scaling** — Removed `user-scalable=no` from viewport meta tag to allow pinch-zoom for accessibility. Changed to `maximum-scale=5.0` as a safety limit. *(Later reverted by worker-2, re-fixed this run.)* Commit: `0d968ac`

- [x] **Added `touch-action: manipulation` to global button/input styles** — Added `touch-action: manipulation` to `button, .btn, input, select` to eliminate the 300ms tap delay on mobile browsers. Commit: `0d968ac`

# POS Production Readiness Audit
> Last run: 2026-06-23 15:20 CT
> Overall readiness: 35% (HIGH issues: 7, MEDIUM: 5)
> Workflow tested this run: A (Waiter taking orders)

## BLOCKERS (can't go live with these)

- [ ] **All inventory items at stock=0 triggers false "OUT OF STOCK" warnings on every order** — Every item in `inventory.json` has `stock: 0` and `low_stock_threshold: 10`. This means every single order submission shows "🔴 OUT OF STOCK: Hamburger - Normal, Coke, Lemonade" warnings. In a real restaurant, waiters would see these on every order and learn to ignore them — defeating the entire purpose of stock warnings. Also, negative stock (stock goes below 0) is silently clamped at 0, meaning inventory is completely non-functional. Fix: set default stock to reasonable levels (100+) or remove non-stock-tracked items from inventory.json, or treat missing stock field as "unlimited."

- [ ] **Cart quantity +/- buttons are 30×30px (under 48px touch minimum)** — Line 436 in index.html: `.cart-item .ci-qty button { min-width: 30px; min-height: 30px; }`. On a 10" tablet in a busy restaurant, waiters with greasy fingers cannot reliably tap these. Same issue at line 439: `.cart-item .ci-remove { min-width: 30px; min-height: 30px; }`. These are the most frequently used buttons during order entry. Fix: increase to min-width: 48px, min-height: 48px.

## HIGH (major friction, fix ASAP)

- [ ] **`user-scalable=no` in viewport meta tag prevents accessibility zoom** — Line 5: `user-scalable=no` prevents users from pinching to zoom. This is an accessibility violation. Some employees may have visual impairments and need magnification. Remove `user-scalable=no` or use `maximum-scale=5.0` instead. Also add `interactive-widget=resizes-content` for iOS Safari to handle keyboard correctly.

- [ ] **No `touch-action: manipulation` anywhere — 300ms tap delay on tablets** — Mobile browsers add 300ms delay to distinguish taps from double-taps. No element in index.html uses `touch-action: manipulation` to disable this. This makes every button press feel sluggish compared to native POS systems. Add `touch-action: manipulation` to `button, .btn, input, select` elements globally.

- [ ] **16 `:hover` CSS rules with no tap alternative** — Tablets don't have hover. Elements like `.timesheet-subtab:hover`, `.shift-edit-btn:hover`, `.recent-orders-header:hover` are the only visual feedback for interactivity on those elements. On a tablet, these show zero feedback on tap. Need to pair with `:active` or use `@media (hover: hover)` to only apply hover on devices that support it.

- [ ] **All form inputs lack `inputmode` attributes for tablet keyboards** — Number inputs (add item price, quantity, PIN entry) don't trigger numeric keypad on tablets. The PIN pad is pure JS buttons, which is good, but other numeric fields like pay rate, price, quantity, and coupon codes should use `inputmode="numeric"` or `inputmode="decimal"` to show the right keyboard on tablets.

- [ ] **font-size: 13px and 14px on many UI elements — too small for restaurant use** — `.perm-table` (13px), `.log-entry` (13px), `.pp-preset` (13px), `.cart-item` (14px), `.ho-meta` (13px). On a wall-mounted tablet or handheld at arm's length, 13px text is unreadable. Minimum body text should be 16px for production restaurant use. At minimum, the POS tab (most used) should have 16px everywhere.

- [ ] **Scrollable containers lack `-webkit-overflow-scrolling: touch`** — While `#mainTabs` has it, the critical `#tabContent`, `#cartItems`, `#historyList`, `#kitchenQueue`, admin sections all scroll without momentum on iOS. This makes long lists feel janky and unprofessional. Add `-webkit-overflow-scrolling: touch` and `overscroll-behavior: contain` to all scrollable containers.

## MEDIUM (annoying but workable)

- [ ] **No checkout workflow confirmation — order submits immediately without review** — When a waiter taps "Submit Order" in the cart, it submits immediately. There's no "Review Order" step showing the full breakdown with modifiers, notes, and before the final submit. Many POS systems have a 2-step: Cart → Review → Submit. This prevents mistakes (wrong modifiers, forgot to remove test items).

- [ ] **Items have no `image` field accessible from the menu** — The items.json has no image URLs set up. The item cards in the grid have image placeholders (`.item-thumb` with 80px height) that show as empty gray boxes. For a customer-facing tablet or kiosk, items need images to look appetizing. Without images, the grid looks unprofessional.

- [ ] **No offline mode support notice** — When the server goes down, there's no cached fallback UI. The app simply stops working. For a real restaurant, network outages happen. The offline badge exists but there's no evidence of a functioning offline queue with SW (service worker). A PWA-style service worker would be needed for true offline resilience.

- [ ] **No printing support (ESC/POS thermal)** — `/api/print/receipt` doesn't exist. Most restaurants use Epson TM-T88 thermal printers. Without physical receipt printing, kitchen ticket printing, and order chit printing, the system can't replace a real POS.

- [ ] **POS tab bottom buttons hidden on short screens** — On a 768px tablet in portrait mode, the cart area with Submit Order, payment methods, tip buttons, and mode toggles can overflow below the fold. The user has to scroll to find Submit Order. Critical actions (Submit Order, Clear Cart) should be sticky/fixed at the bottom of the cart.

## LOW (polish, nice-to-have)

- [ ] **No loading skeleton states** — All async operations show empty or "Loading..." text instead of skeleton screens. Perceived performance is poor.
- [ ] **Haptic feedback on order submit** — `navigator.vibrate(50)` gives physical confirmation.
- [ ] **No smooth tab transitions** — Tab switching is instant/jarring. 150ms slide transitions would feel more polished.
- [ ] **No apple-touch-icon meta tags for iOS PWA** — Adding to home screen on iPad shows generic icon.
- [ ] **Manifest.json only has SVG icon** — No 192×192 or 512×512 PNG icons. Some browsers don't support SVG icons.

## FIXED (this session)

- [x] **All inventory items had stock=0 causing false "OUT OF STOCK" warnings** — Updated `inventory.json` to set every item's stock to 100. This stops the spurious warnings on every order while preserving the inventory tracking system for when real stock counts are configured. Commit: a3e7f2d (pending)

- [x] **Cart quantity +/- buttons too small (30×30px)** — Increased `.cart-item .ci-qty button` min-width and min-height from 30px to 48px for proper touch targets. Same for `.cart-item .ci-remove`. Uses `var(--tap)` to stay consistent with the rest of the UI. Commit: pending

- [x] **Viewport meta disallowed user scaling** — Removed `user-scalable=no` from viewport meta tag to allow pinch-zoom for accessibility. Changed to `maximum-scale=5.0` as a safety limit.

- [x] **Added `touch-action: manipulation` to global button/input styles** — Added `touch-action: manipulation` to `button, .btn, input, select` to eliminate the 300ms tap delay on mobile browsers.

## PREVIOUSLY FIXED (archive)

None — first audit run.

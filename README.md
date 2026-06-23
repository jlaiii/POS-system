# POS System

This Point of Sale (POS) system is provided for **personal use and testing purposes only**.

**If you intend to use this system in a production environment or for commercial purposes, you must contact the developer for licensing and a monthly fee.**

## Features

### Point of Sale
- Item grid with category tabs, search, and barcode scanner support
- Cart with modifiers, notes, discounts, service charges, and split payments
- Table management with running tabs and auto-table suggestion
- Kiosk / customer payment mode with tip calculator
- Cash register management (till opening/closing, cash drops, reconciliation)
- Customer profiles with loyalty points, order history, and total spent tracking
- Digital receipt delivery (email) and receipt reprint
- Offline order queuing with auto-sync on reconnect

### Kitchen & Display
- Kitchen display queue with claim/complete/cancel, sound alerts, and fullscreen mode
- Order-ready customer pickup display board
- Customer-facing display mode (second screen showing order summary)
- Drive-through order display with high-contrast outdoor theme
- Table-side digital menu & ad display (tablet.html)

### Employee Timekeeping
- Clock-in / clock-out with live duration tracking
- Admin timesheet view (completed + active shifts, date filtering, CSV export)
- Pay period summaries with per-employee hours, overtime, estimated pay
- **Scheduled shifts & lateness tracking** — per-user scheduled start times, auto-late detection on clock-in with configurable grace period, late flags with excuse toggle, admin shift time edit/correction with full audit trail, employee late notes
- Missing clock-out detection & alerts (coming soon)
- Break tracking for unpaid meal breaks (coming soon)

### Admin Panel
- Sales statistics dashboard with Chart.js analytics (revenue, orders, peak hours, item trends)
- User management with granular role/permission system (owner/admin/user/cook)
- Menu management (items, categories, modifiers, combos/meal deals, scheduled pricing)
- Inventory tracking with low-stock alerts
- Waste tracking (spoiled, burned, overproduced — with cost estimation)
- Activity log with filtering
- Webhook integration for third-party delivery apps
- Multi-language support (English + Spanish)

### Data
- All data stored as JSON files (users, orders, shifts, inventory, waste, loyalty points, tickets, etc.)
- CSV export for shifts, timesheets, and pay period summaries
- Menu version history with timestamped backups (last 30 retained)

## Setup and Running

1.  **Clone the repository:**

    ```bash
    git clone [your-repository-url]
    cd [your-repository-name]
    ```

2.  **Install Python dependencies:**

    ```bash
    pip install Flask Flask-Cors
    ```

3.  **Run the Flask backend:**

    ```bash
    python app.py
    ```

    The backend will run on `http://127.0.0.1:5000`.

4.  **Open the frontend:**
    Open `index.html` in your web browser.

## Default Credentials

* **Admin PIN:** `1111` (for admin panel access)

## Contact

For commercial use or any inquiries, please contact:
jlaiii@protnmail.com

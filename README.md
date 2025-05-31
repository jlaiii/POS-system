# Simple POS System with Login (HTML/CSS/JavaScript)

This is a basic Point-of-Sale (POS) web app with a user login, item selection, cart system, payment selection, and order logging feature. Everything is self-contained in a single HTML file—no backend or server required.

## 🔧 Features

- 🔐 **Login System** (4-digit user ID)
- 🍔 **Categorized Items**: Foods, Drinks, Snacks
- 🛒 **Cart System**: Add/remove items, live total calculation
- 💳 **Payment Selection**: Cash or Card
- 💾 **Order Logging**: Save each transaction as a `.txt` file with timestamp and user info

## 👨‍💻 How to Use

1. Open `index.html` in your browser.
2. Enter a valid 4-digit User ID to log in:
   - `1234` → TEST
   - `5678` → Bob
   - `9012` → Charlie
   - `3456` → Diana
   - `7890` → Ethan
3. Add items to the cart by clicking "Add" buttons.
4. Click an item in the cart to remove one instance.
5. Select payment method.
6. Click **Submit Order** to generate and download a `.txt` receipt.
7. Click **Clear Cart** to reset selections.

## 📁 File Structure

- `index.html` — All logic, UI, and styles in one file. No external dependencies.

## 🖥️ Screenshot

![POS Screenshot](screenshot.png) <!-- Optional: Add screenshot if available -->

## 📋 Notes

- Cart auto-updates total cost and item count.
- Clicking the same item increases quantity.
- Fully responsive and mobile-friendly.

## 📜 License

MIT License. Feel free to use, modify, and distribute.

---

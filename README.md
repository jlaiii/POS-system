# POS System

This Point of Sale (POS) system is provided for **personal use and testing purposes only**.

**If you intend to use this system in a production environment or for commercial purposes, you must contact the developer for licensing and a monthly fee.**

## Features

* User login with different roles (User, Admin)

* POS functionality for adding items to a cart and submitting orders

* Admin panel for:

    * Viewing sales statistics

    * Managing users (add, delete)

    * Managing menu items (add, edit, delete categories and items)

    * Viewing timesheet data

    * Viewing activity logs

* Data persistence using JSON files (users, orders, cleared orders, activity log, timesheet, items)

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

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
from datetime import datetime, timedelta
import os
import shutil
import glob
import hashlib
import secrets
import csv
import io
import threading
import urllib.request
import urllib.error
from collections import defaultdict, Counter

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all origins

# --- SocketIO for real-time updates ---
socketio = SocketIO(app, cors_allowed_origins="*")

USERS_FILE = 'users.json'
ORDERS_FILE = 'orders.json'
CLEARED_ORDERS_FILE = 'cleared_orders.json'
ACTIVITY_LOG_FILE = 'activity_log.json'  # New log file
TIMESHEET_FILE = 'timesheet.json'  # New timesheet file
ITEMS_FILE = 'items.json'  # New items file
TAX_CONFIG_FILE = 'tax_config.json'  # Tax configuration
DISCOUNTS_FILE = 'discounts.json'  # Discount/coupon codes
ORDER_COUNTER_FILE = 'order_counter.json'  # Auto-incrementing order counter
TABLES_FILE = 'tables.json'  # Table management data
INVENTORY_FILE = 'inventory.json'  # Inventory tracking
REFUNDED_ORDERS_FILE = 'refunded_orders.json'  # Track refunded/voided orders
FAVORITES_FILE = 'favorites.json'  # User quick-order favorites
LOYALTY_FILE = 'loyalty_points.json'  # Customer loyalty points tracking
SCHEDULED_PRICING_FILE = 'scheduled_pricing.json'  # Scheduled pricing rules (happy hour, daily specials)
WASTE_FILE = 'waste_log.json'  # Waste/throwaway tracking
DELIVERY_ADDRESSES_FILE = 'delivery_addresses.json'  # Saved delivery addresses
WEBHOOKS_FILE = 'webhooks.json'  # Webhook integration URLs for third-party delivery apps
TABLE_ADS_FILE = 'table_ads.json'  # Table-side promotional ads
MENU_BACKUPS_DIR = 'menu_backups'

# --- Loyalty Constants ---
LOYALTY_POINTS_PER_DOLLAR = 1  # 1 point per $1 spent
LOYALTY_REDEEM_RATE = 100      # 100 points = discount amount below
LOYALTY_REDEEM_DISCOUNT = 5.00 # $5 off per 100 points

# --- Permission Constants ---
DEFAULT_ADMIN_PERMISSIONS = [
    "manage_users", "ban_users", "manage_items", "manage_permissions",
    "view_stats", "view_logs", "view_timesheet", "manage_orders",
    "pos_access", "kitchen_access"
]
DEFAULT_USER_PERMISSIONS = ["pos_access"]
DEFAULT_COOK_PERMISSIONS = ["kitchen_access"]


# --- Utility Functions ---

def upgrade_user(user_data):
    """Ensure user has a permissions list matching their role, adding defaults if missing."""
    role = user_data.get('role', 'user')
    if role == 'owner':
        user_data['permissions'] = ["*"]
    elif role == 'admin' and 'permissions' not in user_data:
        user_data['permissions'] = list(DEFAULT_ADMIN_PERMISSIONS)
    elif role == 'user' and 'permissions' not in user_data:
        user_data['permissions'] = list(DEFAULT_USER_PERMISSIONS)
    elif role == 'cook' and 'permissions' not in user_data:
        user_data['permissions'] = list(DEFAULT_COOK_PERMISSIONS)
    return user_data


def check_perm(user_id, permission):
    """Check if a user has a specific permission. Returns True/False."""
    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return False
    user_data = users[user_id]
    user_data = upgrade_user(user_data)
    perms = user_data.get('permissions', [])
    if "*" in perms:
        return True
    if permission in perms:
        return True
    return False


def backup_menu():
    """Save a timestamped copy of items.json to menu_backups/, keeping last 30."""
    if not os.path.exists(MENU_BACKUPS_DIR):
        os.makedirs(MENU_BACKUPS_DIR, exist_ok=True)
    if not os.path.exists(ITEMS_FILE):
        return
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_filename = f'items_{timestamp}.json'
    backup_path = os.path.join(MENU_BACKUPS_DIR, backup_filename)
    shutil.copy2(ITEMS_FILE, backup_path)
    # Keep only the last 30 backups
    backups = sorted(
        glob.glob(os.path.join(MENU_BACKUPS_DIR, 'items_*.json')),
        key=os.path.getmtime
    )
    while len(backups) > 30:
        oldest = backups.pop(0)
        os.remove(oldest)


# Ensure JSON files exist and are initialized correctly
for f in [USERS_FILE, ORDERS_FILE, CLEARED_ORDERS_FILE, ACTIVITY_LOG_FILE, TIMESHEET_FILE, ITEMS_FILE, TAX_CONFIG_FILE, DISCOUNTS_FILE, ORDER_COUNTER_FILE, TABLES_FILE, INVENTORY_FILE, REFUNDED_ORDERS_FILE, FAVORITES_FILE, LOYALTY_FILE, SCHEDULED_PRICING_FILE, WASTE_FILE, DELIVERY_ADDRESSES_FILE, WEBHOOKS_FILE, TABLE_ADS_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as file:
            if f == USERS_FILE:
                json.dump({"1111": {"name": "Owner", "role": "owner", "permissions": ["*"]}}, file)
            elif f == TIMESHEET_FILE or f == ACTIVITY_LOG_FILE:
                json.dump([], file)  # Initialize as empty lists
            elif f == ITEMS_FILE:
                json.dump({
                    "Foods": [
                        {"name": "Hamburger - Normal", "price": 6, "barcode": ""},
                        {"name": "Hamburger - All the Fixings", "price": 8, "barcode": ""},
                        {"name": "Hotdog - Loaded", "price": 7, "barcode": ""},
                        {"name": "Hotdog - Plain", "price": 5, "barcode": ""},
                        {"name": "Taco - Beef & Cheese", "price": 7, "barcode": ""},
                        {"name": "Taco - Chicken with Salsa", "price": 7, "barcode": ""}
                    ],
                    "Drinks": [
                        {"name": "Lemonade", "price": 3, "barcode": ""},
                        {"name": "Coke", "price": 3, "barcode": ""},
                        {"name": "Water Bottle", "price": 2, "barcode": ""}
                    ],
                    "Snacks": [
                        {"name": "Raspia (Fruit Slush)", "price": 4, "barcode": ""},
                        {"name": "Chips (Large Bag)", "price": 3, "barcode": ""},
                        {"name": "Chocolate Bar", "price": 2, "barcode": ""},
                        {"name": "Mixed Nuts (Small Pack)", "price": 4, "barcode": ""},
                        {"name": "Granola Bar", "price": 2, "barcode": ""}
                    ]
                }, file, indent=4)  # Initialize with default items
            elif f == TAX_CONFIG_FILE:
                json.dump({
                    "global_tax_rate": 0.0,
                    "category_tax_rates": {},
                    "item_tax_overrides": {}
                }, file, indent=4)  # Initialize with 0% tax, no overrides
            elif f == DISCOUNTS_FILE:
                json.dump({}, file, indent=4)  # Initialize empty discounts
            elif f == ORDER_COUNTER_FILE:
                json.dump({"counter": 1}, file, indent=4)  # Initialize order counter at 1
            elif f == TABLES_FILE:
                json.dump({}, file, indent=4)  # Initialize empty tables
            elif f == INVENTORY_FILE:
                json.dump({}, file, indent=4)  # Initialize empty inventory
            elif f == FAVORITES_FILE:
                json.dump({}, file, indent=4)  # Initialize empty favorites dict (user_id -> list of combos)
            elif f == LOYALTY_FILE:
                json.dump({}, file, indent=4)  # Initialize empty loyalty points dict (phone -> data)
            elif f == WASTE_FILE:
                json.dump([], file, indent=4)  # Initialize empty waste log
            elif f == DELIVERY_ADDRESSES_FILE:
                json.dump({}, file, indent=4)  # Initialize empty delivery addresses dict
            elif f == WEBHOOKS_FILE:
                json.dump({}, file, indent=4)  # Initialize empty webhooks dict
            elif f == TABLE_ADS_FILE:
                json.dump({"ads": [], "rotation_interval": 10}, file, indent=4)  # Initialize empty table ads
            else:
                json.dump([], file)  # Initialize orders.json and cleared_orders.json as empty lists

# Ensure menu_backups directory exists at startup
if not os.path.exists(MENU_BACKUPS_DIR):
    os.makedirs(MENU_BACKUPS_DIR, exist_ok=True)


def load_json_data(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            if filepath == USERS_FILE and not isinstance(data, dict):
                print(f"Warning: {filepath} is not a dictionary. Initializing as empty dict.")
                return {}
            if filepath in [ORDERS_FILE, CLEARED_ORDERS_FILE, ACTIVITY_LOG_FILE, TIMESHEET_FILE] and not isinstance(data, list):
                print(f"Warning: {filepath} is not a list. Initializing as empty list.")
                return []
            if filepath == ITEMS_FILE and not isinstance(data, dict):
                print(f"Warning: {filepath} is not a dictionary. Initializing as empty dict.")
                return {}  # Items file should be a dict of categories
            if filepath == TAX_CONFIG_FILE and not isinstance(data, dict):
                print(f"Warning: {filepath} is not a dictionary. Initializing with defaults.")
                return {"global_tax_rate": 0.0, "category_tax_rates": {}, "item_tax_overrides": {}}
            if filepath == DISCOUNTS_FILE and not isinstance(data, dict):
                print(f"Warning: {filepath} is not a dictionary. Initializing as empty dict.")
                return {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"File not found or JSON decode error for {filepath}. Returning empty structure.")
        if filepath == USERS_FILE:
            return {}  # Return empty dict for users
        if filepath == ITEMS_FILE:
            return {}  # Return empty dict for items
        return []  # Return empty list for others


def save_json_data(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)


def hash_password(password, salt=None):
    """Hash a password with SHA-256 + salt. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt

def verify_password(password, stored_hash, stored_salt):
    """Verify a password against stored hash and salt."""
    h, _ = hash_password(password, stored_salt)
    return h == stored_hash

def log_activity(activity_type, user_id, user_role, details=None):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'type': activity_type,
        'user_id': user_id,
        'user_role': user_role,
        'details': details if details is not None else {}
    }
    logs = load_json_data(ACTIVITY_LOG_FILE)
    logs.append(log_entry)
    save_json_data(ACTIVITY_LOG_FILE, logs)


def fire_webhooks(order_data):
    """Send order data to all enabled webhook URLs in background thread."""
    webhooks = load_json_data(WEBHOOKS_FILE)
    if not isinstance(webhooks, dict):
        return
    for wh_id, wh in webhooks.items():
        if not wh.get('enabled', True):
            continue
        url = wh.get('url', '').strip()
        if not url:
            continue
        try:
            payload = json.dumps({
                'event': 'order.created',
                'timestamp': datetime.now().isoformat(),
                'data': order_data
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            # Short timeout so we don't block
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # Fire-and-forget; log failure silently


def fire_webhooks_async(order_data):
    """Fire webhooks in a daemon thread so the HTTP response isn't blocked."""
    t = threading.Thread(target=fire_webhooks, args=(order_data,), daemon=True)
    t.start()


# --- SocketIO Real-Time Event Handlers ---

KITCHEN_ROOM = 'kitchen'
CUSTOMER_ROOM = 'customer_display'
DRIVETHROUGH_ROOM = 'drivethrough'


@socketio.on('connect')
def handle_connect():
    """Client connects — they'll join a specific room via join events."""
    pass


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnects — no cleanup needed, rooms auto-left."""
    pass


@socketio.on('join_kitchen')
def handle_join_kitchen():
    """Frontend kitchen display joins the kitchen room for real-time updates."""
    join_room(KITCHEN_ROOM)


@socketio.on('leave_kitchen')
def handle_leave_kitchen():
    """Frontend kitchen display leaves the kitchen room."""
    leave_room(KITCHEN_ROOM)


@socketio.on('join_customer_display')
def handle_join_customer_display():
    """Customer display page joins the customer display room."""
    join_room(CUSTOMER_ROOM)


@socketio.on('leave_customer_display')
def handle_leave_customer_display():
    """Customer display page leaves the customer display room."""
    leave_room(CUSTOMER_ROOM)


@socketio.on('join_drivethrough')
def handle_join_drivethrough():
    """Drive-through display page joins the drive-through room."""
    join_room(DRIVETHROUGH_ROOM)


@socketio.on('leave_drivethrough')
def handle_leave_drivethrough():
    """Drive-through display page leaves the drive-through room."""
    leave_room(DRIVETHROUGH_ROOM)


def emit_kitchen_update():
    """Broadcast to kitchen room that order state changed."""
    socketio.emit('kitchen_update', {}, room=KITCHEN_ROOM)


def emit_customer_update():
    """Broadcast to customer display room that display state changed."""
    socketio.emit('customer_update', {}, room=CUSTOMER_ROOM)


def emit_drivethrough_update():
    """Broadcast to drive-through room that display state changed."""
    socketio.emit('drivethrough_update', {}, room=DRIVETHROUGH_ROOM)


# In-memory storage for active admin sessions (for timesheet calculation)
active_admin_sessions = {}  # {admin_id: login_time}

# --- User Management Endpoints ---

@app.route('/api/users', methods=['GET'])
def get_users():
    users = load_json_data(USERS_FILE)
    display_users = {}
    for uid, user_data in users.items():
        # Ensure permissions are upgraded before returning
        user_data = upgrade_user(user_data)
        display_users[uid] = {
            'name': user_data['name'],
            'role': user_data['role'],
            'permissions': user_data.get('permissions', []),
            'banned': user_data.get('banned', False),
            'banned_reason': user_data.get('banned_reason', '')
        }
    return jsonify(display_users)


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('userId')
    username = data.get('username')
    password = data.get('password')
    users = load_json_data(USERS_FILE)

    # Owner username+password login
    if username and password:
        for uid, u_data in users.items():
            if u_data.get('username') == username:
                stored_hash = u_data.get('password_hash')
                stored_salt = u_data.get('password_salt')
                if stored_hash and stored_salt and verify_password(password, stored_hash, stored_salt):
                    if u_data.get('banned', False):
                        reason = u_data.get('banned_reason', 'No reason provided')
                        return jsonify({'message': f'User is banned. Reason: {reason}', 'banned': True}), 403
                    u_data = upgrade_user(u_data)
                    users[uid] = u_data
                    save_json_data(USERS_FILE, users)
                    log_activity('login', uid, u_data['role'], {'status': 'success', 'method': 'password', 'user_name': u_data['name']})
                    if u_data['role'] in ('admin', 'owner'):
                        active_admin_sessions[uid] = datetime.now()
                    return jsonify({'message': 'Login successful', 'user': u_data['name'], 'role': u_data['role'], 'permissions': u_data.get('permissions', [])})
        log_activity('login', username, 'unknown', {'status': 'failed', 'method': 'password'})
        return jsonify({'message': 'Invalid username or password'}), 401

    # PIN login (existing)
    if user_id in users:
        user_info = users[user_id]
        user_info = upgrade_user(user_info)
        users[user_id] = user_info
        save_json_data(USERS_FILE, users)

        if user_info.get('banned', False):
            reason = user_info.get('banned_reason', 'No reason provided')
            log_activity('login', user_id, user_info.get('role', 'unknown'),
                         {'status': 'failed', 'reason': f'User is banned: {reason}'})
            return jsonify({'message': f'User is banned. Reason: {reason}', 'banned': True}), 403

        if user_info.get('role') in ['user', 'admin', 'owner', 'cook']:
            log_activity('login', user_id, user_info['role'], {'status': 'success', 'method': 'pin', 'user_name': user_info['name']})
            if user_info['role'] in ('admin', 'owner'):
                active_admin_sessions[user_id] = datetime.now()
            return jsonify({'message': 'Login successful', 'user': user_info['name'], 'role': user_info['role'], 'permissions': user_info.get('permissions', [])})
    log_activity('login', user_id, 'unknown', {'status': 'failed', 'method': 'pin'})
    return jsonify({'message': 'Invalid User ID or role'}), 401

# Owner credentials management
@app.route('/api/owner/credentials', methods=['POST'])
def owner_credentials():
    """Owner sets or updates their username and password."""
    data = request.json
    owner_pin = data.get('ownerPin')
    username = data.get('username')
    password = data.get('password')

    users = load_json_data(USERS_FILE)
    if owner_pin not in users or users[owner_pin].get('role') != 'owner':
        return jsonify({'message': 'Owner credentials required'}), 403

    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400
    if len(password) < 6:
        return jsonify({'message': 'Password must be at least 6 characters'}), 400
    if len(username) < 3:
        return jsonify({'message': 'Username must be at least 3 characters'}), 400

    # Check username not taken by another user
    for uid, u_data in users.items():
        if uid != owner_pin and u_data.get('username') == username:
            return jsonify({'message': 'Username already taken'}), 409

    pw_hash, pw_salt = hash_password(password)
    users[owner_pin]['username'] = username
    users[owner_pin]['password_hash'] = pw_hash
    users[owner_pin]['password_salt'] = pw_salt
    save_json_data(USERS_FILE, users)

    log_activity('owner_credentials', owner_pin, 'owner', {'status': 'success', 'username': username})
    return jsonify({'message': 'Owner credentials updated successfully'})

@app.route('/api/owner/credentials/status', methods=['GET'])
def owner_credentials_status():
    """Check if owner has set credentials."""
    users = load_json_data(USERS_FILE)
    for uid, u_data in users.items():
        if u_data.get('role') == 'owner':
            has_creds = bool(u_data.get('username') and u_data.get('password_hash'))
            return jsonify({'has_credentials': has_creds, 'username': u_data.get('username', '')})
    return jsonify({'has_credentials': False, 'username': ''})


@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json
    user_id = data.get('userId')
    user_role = data.get('userRole')

    log_activity('logout', user_id, user_role)

    # If the user was an admin, log their work duration
    if user_id in active_admin_sessions:
        login_time = active_admin_sessions.pop(user_id)
        logout_time = datetime.now()
        duration = (logout_time - login_time).total_seconds() / 3600  # duration in hours

        timesheet_entry = {
            'user_id': user_id,
            'login_time': login_time.isoformat(),
            'logout_time': logout_time.isoformat(),
            'duration_hours': round(duration, 2)
        }
        timesheet_data = load_json_data(TIMESHEET_FILE)
        timesheet_data.append(timesheet_entry)
        save_json_data(TIMESHEET_FILE, timesheet_data)

    return jsonify({'message': 'Logout successful'})


@app.route('/api/add_user', methods=['POST'])
def add_user():
    data = request.json
    admin_pin = data.get('adminPin')
    new_user_id = data.get('userId')
    new_user_name = data.get('userName')
    new_user_role = data.get('userRole')

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        log_activity('add_user', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)

    admin_user = users.get(admin_pin, None)

    if not new_user_id or not new_user_name or not new_user_role:
        log_activity('add_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'Missing data', 'new_user_id': new_user_id})
        return jsonify({'message': 'Missing user data.'}), 400
    if len(new_user_id) < 4 or len(new_user_id) > 10 or not new_user_id.isdigit():
        log_activity('add_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'Invalid User ID format', 'new_user_id': new_user_id})
        return jsonify({'message': 'User ID must be a 4-10 digit number.'}), 400
    if new_user_id in users:
        log_activity('add_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'User ID exists', 'new_user_id': new_user_id})
        return jsonify({'message': 'User ID already exists.'}), 409
    if new_user_role not in ['user', 'admin', 'owner', 'cook']:
        log_activity('add_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'Invalid user role', 'new_user_id': new_user_id})
        return jsonify({'message': 'Invalid user role. Must be "user", "admin", "owner", or "cook".'}), 400

    # Assign default permissions based on role
    new_user_data = {'name': new_user_name, 'role': new_user_role}
    if new_user_role == 'owner':
        new_user_data['permissions'] = ["*"]
    elif new_user_role == 'admin':
        new_user_data['permissions'] = list(DEFAULT_ADMIN_PERMISSIONS)
    elif new_user_role == 'cook':
        new_user_data['permissions'] = list(DEFAULT_COOK_PERMISSIONS)
    else:  # user
        new_user_data['permissions'] = list(DEFAULT_USER_PERMISSIONS)

    users[new_user_id] = new_user_data
    save_json_data(USERS_FILE, users)
    log_activity('add_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                 {'status': 'success', 'added_user_id': new_user_id, 'added_user_name': new_user_name, 'added_user_role': new_user_role})
    return jsonify({'message': 'User added successfully', 'user': {'id': new_user_id, 'name': new_user_name, 'role': new_user_role}})


@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    data = request.json
    admin_pin = data.get('adminPin')
    user_id_to_delete = data.get('userId')

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        log_activity('delete_user', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions', 'target_user_id': user_id_to_delete})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)
    admin_user = users.get(admin_pin, None)

    if not user_id_to_delete:
        log_activity('delete_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'Missing user ID to delete'})
        return jsonify({'message': 'Missing user ID to delete.'}), 400
    if user_id_to_delete not in users:
        log_activity('delete_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'User ID not found', 'target_user_id': user_id_to_delete})
        return jsonify({'message': 'User ID not found.'}), 404
    # Prevent deleting the last admin user
    if users[user_id_to_delete]['role'] == 'admin' and sum(1 for u in users.values() if u['role'] == 'admin') == 1:
        log_activity('delete_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                     {'status': 'failed', 'reason': 'Cannot delete last admin', 'target_user_id': user_id_to_delete})
        return jsonify({'message': 'Cannot delete the last admin user.'}), 400

    deleted_user_info = users[user_id_to_delete]
    del users[user_id_to_delete]
    save_json_data(USERS_FILE, users)
    log_activity('delete_user', admin_pin, admin_user['role'] if admin_user else 'unknown',
                 {'status': 'success', 'deleted_user_id': user_id_to_delete, 'deleted_user_name': deleted_user_info['name'], 'deleted_user_role': deleted_user_info['role']})
    return jsonify({'message': 'User deleted successfully', 'userId': user_id_to_delete})


# --- Item Management Endpoints ---

@app.route('/api/items', methods=['GET'])
def get_items():
    items = load_json_data(ITEMS_FILE)
    return jsonify(items)


def verify_admin(admin_pin):
    users = load_json_data(USERS_FILE)
    for uid, u_data in users.items():
        if u_data.get('role') == 'admin' and uid == admin_pin:
            return True, u_data
    return False, None


@app.route('/api/add_item', methods=['POST'])
def add_item():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('add_item', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    category = data.get('category')
    name = data.get('name')
    price = data.get('price')

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'

    if not all([category, name, price is not None]):
        log_activity('add_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Missing data', 'item_data': data})
        return jsonify({'message': 'Missing item data (category, name, or price).'}), 400

    try:
        price = float(price)
        if price <= 0:
            raise ValueError("Price must be positive.")
    except ValueError:
        log_activity('add_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Invalid price format', 'item_data': data})
        return jsonify({'message': 'Invalid price format. Must be a positive number.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        items_data[category] = []

    # Check for duplicate item name within the category
    for item in items_data[category]:
        if item['name'].lower() == name.lower():
            log_activity('add_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Item already exists', 'item_data': data})
            return jsonify({'message': f'Item "{name}" already exists in category "{category}".'}), 409

    items_data[category].append({"name": name, "price": price, "barcode": data.get('barcode', '')})
    save_json_data(ITEMS_FILE, items_data)
    backup_menu()  # Auto-backup after successful save
    
    # Auto-add inventory entry for the new item
    inventory = load_json_data(INVENTORY_FILE)
    if name not in inventory:
        inventory[name] = {
            'stock': 0,
            'low_stock_threshold': 10
        }
        save_json_data(INVENTORY_FILE, inventory)
    
    log_activity('add_item', admin_pin, admin_role, {'status': 'success', 'category': category, 'name': name, 'price': price})
    return jsonify({'message': 'Item added successfully', 'item': {'category': category, 'name': name, 'price': price}})


@app.route('/api/edit_item', methods=['POST'])
def edit_item():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('edit_item', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    old_category = data.get('oldCategory')
    old_name = data.get('oldName')
    new_category = data.get('newCategory')
    new_name = data.get('newName')
    new_price = data.get('newPrice')

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'

    if not all([old_category, old_name, new_category, new_name, new_price is not None]):
        log_activity('edit_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Missing data', 'item_data': data})
        return jsonify({'message': 'Missing item data for edit.'}), 400

    try:
        new_price = float(new_price)
        if new_price <= 0:
            raise ValueError("Price must be positive.")
    except ValueError:
        log_activity('edit_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Invalid new price format', 'item_data': data})
        return jsonify({'message': 'Invalid new price format. Must be a positive number.'}), 400

    items_data = load_json_data(ITEMS_FILE)

    if old_category not in items_data:
        log_activity('edit_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Old category not found', 'item_data': data})
        return jsonify({'message': f'Old category "{old_category}" not found.'}), 404

    item_found = False
    for i, item in enumerate(items_data[old_category]):
        if item['name'] == old_name:
            item_found = True
            # If category or name is changing, check for duplicates in new category
            if (old_category != new_category or old_name != new_name):
                if new_category in items_data:
                    for existing_item in items_data[new_category]:
                        if existing_item['name'].lower() == new_name.lower():
                            log_activity('edit_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'New item name already exists in target category', 'item_data': data})
                            return jsonify({'message': f'Item "{new_name}" already exists in category "{new_category}".'}), 409

            # Remove from old category if category is changing
            if old_category != new_category:
                del items_data[old_category][i]
                if not items_data[old_category]:  # Remove category if it becomes empty
                    del items_data[old_category]

                if new_category not in items_data:
                    items_data[new_category] = []
                items_data[new_category].append({"name": new_name, "price": new_price, "barcode": data.get('barcode', items_data[old_category][i].get('barcode', ''))})
            else:  # Only name/price/barcode changing within same category
                items_data[old_category][i]["name"] = new_name
                items_data[old_category][i]["price"] = new_price
                if 'barcode' in data and data.get('barcode') is not None:
                    items_data[old_category][i]["barcode"] = data.get('barcode', '')
            break

    if not item_found:
        log_activity('edit_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Old item not found in category', 'item_data': data})
        return jsonify({'message': f'Item "{old_name}" not found in category "{old_category}".'}), 404

    save_json_data(ITEMS_FILE, items_data)
    backup_menu()  # Auto-backup after successful save
    log_activity('edit_item', admin_pin, admin_role, {'status': 'success', 'old_item': {'category': old_category, 'name': old_name}, 'new_item': {'category': new_category, 'name': new_name, 'price': new_price}})
    return jsonify({'message': 'Item updated successfully'})


@app.route('/api/delete_item', methods=['POST'])
def delete_item():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('delete_item', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    category = data.get('category')
    name = data.get('name')

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'

    if not all([category, name]):
        log_activity('delete_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Missing data', 'item_data': data})
        return jsonify({'message': 'Missing item data (category or name).'}), 400

    items_data = load_json_data(ITEMS_FILE)

    if category not in items_data:
        log_activity('delete_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Category not found', 'item_data': data})
        return jsonify({'message': f'Category "{category}" not found.'}), 404

    item_found = False
    for i, item in enumerate(items_data[category]):
        if item['name'] == name:
            del items_data[category][i]
            item_found = True
            break

    if not item_found:
        log_activity('delete_item', admin_pin, admin_role, {'status': 'failed', 'reason': 'Item not found', 'item_data': data})
        return jsonify({'message': f'Item "{name}" not found in category "{category}".'}), 404

    if not items_data[category]:  # If category becomes empty after deletion
        del items_data[category]

    save_json_data(ITEMS_FILE, items_data)
    backup_menu()  # Auto-backup after successful save
    log_activity('delete_item', admin_pin, admin_role, {'status': 'success', 'category': category, 'name': name})
    return jsonify({'message': 'Item deleted successfully'})


@app.route('/api/items/barcode/lookup', methods=['POST'])
def barcode_lookup():
    """Look up an item by barcode. Returns the item info or 404."""
    data = request.json
    barcode = data.get('barcode', '').strip()
    if not barcode:
        return jsonify({'message': 'Barcode is required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    for cat, cat_items in items_data.items():
        for item in cat_items:
            item_barcode = item.get('barcode', '')
            if item_barcode and item_barcode == barcode:
                return jsonify({
                    'category': cat,
                    'name': item['name'],
                    'price': item['price'],
                    'barcode': item_barcode
                })
    return jsonify({'message': f'No item found with barcode "{barcode}".'}), 404


@app.route('/api/items/set_barcode', methods=['POST'])
def set_item_barcode():
    """Set or update the barcode for an existing item."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    category = data.get('category')
    name = data.get('name')
    barcode = data.get('barcode', '').strip()

    if not all([category, name]):
        return jsonify({'message': 'Category and name are required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        return jsonify({'message': f'Category "{category}" not found.'}), 404

    found = False
    for item in items_data[category]:
        if item['name'] == name:
            item['barcode'] = barcode
            found = True
            break

    if not found:
        return jsonify({'message': f'Item "{name}" not found in category "{category}".'}), 404

    save_json_data(ITEMS_FILE, items_data)
    backup_menu()
    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('set_barcode', admin_pin, admin_role, {'category': category, 'name': name, 'barcode': barcode})
    return jsonify({'message': 'Barcode updated successfully'})


# --- Order Management Endpoints ---

@app.route('/api/submit_order', methods=['POST'])
def submit_order():
    data = request.json
    items = data.get('items', [])

    # Check if user is banned
    user_id = data.get('user')
    if user_id:
        users = load_json_data(USERS_FILE)
        if user_id in users:
            user_info = users[user_id]
            user_info = upgrade_user(user_info)
            if user_info.get('banned', False):
                return jsonify({'message': 'User is banned'}), 403

    # Calculate subtotal from items for verification
    calculated_subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 1)) for item in items)

    # Accept tax info from frontend, or default to 0 for backward compatibility
    subtotal = float(data.get('subtotal', calculated_subtotal))
    tax_amount = float(data.get('tax_amount', 0))
    tip_amount = float(data.get('tip_amount', 0))

    # Accept total from frontend, or compute as subtotal + tax + tip
    total_from_request = data.get('total')
    if total_from_request is not None:
        total = float(total_from_request)
    else:
        total = subtotal + tax_amount + tip_amount

    # --- Kitchen: auto-increment order ID ---
    counter_data = load_json_data(ORDER_COUNTER_FILE)
    if not isinstance(counter_data, dict):
        counter_data = {"counter": 1}
    order_id = counter_data.get("counter", 1)

    # --- Handle split-payment support ---
    payment_splits = data.get('payment_splits')
    payment_display = data.get('payment', '')

    if payment_splits and isinstance(payment_splits, list) and len(payment_splits) > 0:
        # Build a readable payment summary from splits
        if len(payment_splits) == 1:
            payment_display = payment_splits[0]['method']
        else:
            parts = [f"{s['method']} ${float(s['amount']):.2f}" for s in payment_splits]
            payment_display = 'Split (' + ', '.join(parts) + ')'
    elif not payment_display:
        payment_display = data.get('payment', 'Cash')

    order_details = {
        'order_id': order_id,
        'status': 'pending',
        'claimed_by': None,
        'claimed_at': None,
        'completed_at': None,
        'date': datetime.now().isoformat(),
        'user': data.get('user'),
        'payment': payment_display,
        'payment_splits': payment_splits if payment_splits else None,
        'items': items,
        'subtotal': round(subtotal, 2),
        'tax_amount': round(tax_amount, 2),
        'tip_amount': round(tip_amount, 2),
        'discount_code': data.get('discount_code'),
        'discount_amount': round(float(data.get('discount_amount', 0)), 2),
        'total': round(total, 2),
        'notes': data.get('notes', ''),  # Per-order special instructions
        'item_notes': data.get('item_notes', {}),  # Per-item notes {index: note_string}
        'table_number': data.get('table_number'),  # Table number for table management
        'delivery_address': data.get('delivery_address')  # Delivery address info
    }
    orders = load_json_data(ORDERS_FILE)
    orders.append(order_details)
    save_json_data(ORDERS_FILE, orders)

    # Increment and save the counter
    counter_data["counter"] = order_id + 1
    save_json_data(ORDER_COUNTER_FILE, counter_data)

    order_number = len(orders)
    log_activity('submit_order', data.get('user'), 'user', {
        'order_id': order_id,
        'subtotal': order_details['subtotal'],
        'tax_amount': order_details['tax_amount'],
        'discount_code': order_details['discount_code'],
        'discount_amount': order_details['discount_amount'],
        'total': order_details['total'],
        'payment_method': order_details['payment'],
        'item_count': len(items)
    })

    # --- Inventory: decrement stock for each item in the order ---
    inventory = load_json_data(INVENTORY_FILE)
    low_stock_warnings = []
    for item in items:
        item_name = item.get('name', '')
        qty = int(item.get('qty', 1))
        if item_name in inventory:
            current_stock = inventory[item_name].get('stock', 0)
            new_stock = max(0, current_stock - qty)
            inventory[item_name]['stock'] = new_stock
            threshold = inventory[item_name].get('low_stock_threshold', 10)
            if new_stock <= 0:
                low_stock_warnings.append({
                    'item_name': item_name,
                    'stock': new_stock,
                    'status': 'out_of_stock'
                })
            elif new_stock <= threshold:
                low_stock_warnings.append({
                    'item_name': item_name,
                    'stock': new_stock,
                    'status': 'low_stock',
                    'threshold': threshold
                })
    save_json_data(INVENTORY_FILE, inventory)

    # --- Loyalty: award points if customer phone is provided ---
    loyalty_earned = 0
    customer_phone = data.get('customer_phone', '').strip()
    if customer_phone:
        loyalty_data = load_json_data(LOYALTY_FILE)
        if customer_phone in loyalty_data:
            earned = max(1, int(subtotal * LOYALTY_POINTS_PER_DOLLAR))
            loyalty_data[customer_phone]['points'] += earned
            loyalty_data[customer_phone]['total_earned'] += earned
            loyalty_data[customer_phone]['history'].append({
                'type': 'earned',
                'points': earned,
                'order_id': order_id,
                'subtotal': round(subtotal, 2),
                'date': datetime.now().isoformat()
            })
            loyalty_earned = earned
            save_json_data(LOYALTY_FILE, loyalty_data)
            log_activity('loyalty_earn', data.get('user', 'unknown'), 'user', {
                'customer_phone': customer_phone,
                'points_earned': earned,
                'order_id': order_id
            })

    # --- Webhooks: fire to third-party delivery integrations ---
    fire_webhooks_async(order_details)

    # --- SocketIO: notify kitchen, customer display, drivethrough ---
    emit_kitchen_update()
    emit_customer_update()
    emit_drivethrough_update()

    return jsonify({
        'message': 'Order submitted successfully',
        'order_number': order_number,
        'order_id': order_id,
        'low_stock_warnings': low_stock_warnings,
        'loyalty_earned': loyalty_earned
    })


@app.route('/api/clear_order', methods=['POST'])
def clear_order():
    data = request.json
    cleared_order_details = {
        'date': datetime.now().isoformat(),
        'user': data.get('user'),
        'reason': data.get('reason', 'N/A'),
        'items_at_clear': data.get('items'),
        'total_at_clear': float(data.get('total'))  # Ensure total is float for calculations
    }
    cleared_orders = load_json_data(CLEARED_ORDERS_FILE)
    cleared_orders.append(cleared_order_details)
    save_json_data(CLEARED_ORDERS_FILE, cleared_orders)
    log_activity('clear_cart', data.get('user'), 'user', {'reason': cleared_order_details['reason'], 'total_at_clear': cleared_order_details['total_at_clear']})
    return jsonify({'message': 'Cleared order logged successfully'})


# --- Offline Order Queuing & Sync ---

@app.route('/api/health', methods=['GET'])
def health_check():
    """Lightweight health check for frontend connectivity probing."""
    return jsonify({'status': 'ok'})


@app.route('/api/sync_orders', methods=['POST'])
def sync_orders():
    """
    Accept an array of offline-queued orders and process them sequentially.
    Each order in the array should have the same shape as a normal submit_order payload,
    plus a 'local_id' field for client-side dedup.
    Returns an array of results with local_id → server order_id mapping.
    """
    data = request.json
    orders = data.get('orders', [])
    if not isinstance(orders, list) or len(orders) == 0:
        return jsonify({'message': 'No orders provided'}), 400

    results = []
    orders_data = load_json_data(ORDERS_FILE)
    counter_data = load_json_data(ORDER_COUNTER_FILE)
    if not isinstance(counter_data, dict):
        counter_data = {"counter": 1}
    inventory = load_json_data(INVENTORY_FILE)

    for order_data in orders:
        local_id = order_data.get('local_id', None)
        items = order_data.get('items', [])

        # Calculate subtotal from items
        calculated_subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 1)) for item in items)
        subtotal = float(order_data.get('subtotal', calculated_subtotal))
        tax_amount = float(order_data.get('tax_amount', 0))
        tip_amount = float(order_data.get('tip_amount', 0))

        total_from_request = order_data.get('total')
        if total_from_request is not None:
            total = float(total_from_request)
        else:
            total = subtotal + tax_amount + tip_amount

        order_id = counter_data.get("counter", 1)

        # Handle payment splits
        payment_splits = order_data.get('payment_splits')
        payment_display = order_data.get('payment', '')

        if payment_splits and isinstance(payment_splits, list) and len(payment_splits) > 0:
            if len(payment_splits) == 1:
                payment_display = payment_splits[0]['method']
            else:
                parts = [f"{s['method']} ${float(s['amount']):.2f}" for s in payment_splits]
                payment_display = 'Split (' + ', '.join(parts) + ')'
        elif not payment_display:
            payment_display = 'Cash'

        order_details = {
            'order_id': order_id,
            'status': 'pending',
            'claimed_by': None,
            'claimed_at': None,
            'completed_at': None,
            'date': order_data.get('date', datetime.now().isoformat()),
            'user': order_data.get('user'),
            'payment': payment_display,
            'payment_splits': payment_splits if payment_splits else None,
            'items': items,
            'subtotal': round(subtotal, 2),
            'tax_amount': round(tax_amount, 2),
            'tip_amount': round(tip_amount, 2),
            'discount_code': order_data.get('discount_code'),
            'discount_amount': round(float(order_data.get('discount_amount', 0)), 2),
            'total': round(total, 2),
            'notes': order_data.get('notes', ''),
            'item_notes': order_data.get('item_notes', {}),
            'table_number': order_data.get('table_number'),
            'delivery_address': order_data.get('delivery_address')
        }
        orders_data.append(order_details)

        # Increment counter
        counter_data["counter"] = order_id + 1

        # Log activity
        log_activity('submit_order', order_data.get('user'), 'user', {
            'order_id': order_id,
            'subtotal': order_details['subtotal'],
            'tax_amount': order_details['tax_amount'],
            'discount_code': order_details['discount_code'],
            'discount_amount': order_details['discount_amount'],
            'total': order_details['total'],
            'payment_method': order_details['payment'],
            'item_count': len(items)
        })

        # Decrement inventory
        for item in items:
            item_name = item.get('name', '')
            qty = int(item.get('qty', 1))
            if item_name in inventory:
                current_stock = inventory[item_name].get('stock', 0)
                inventory[item_name]['stock'] = max(0, current_stock - qty)

        results.append({
            'local_id': local_id,
            'order_id': order_id,
            'order_number': len(orders_data),
            'status': 'success'
        })

    save_json_data(ORDERS_FILE, orders_data)
    save_json_data(ORDER_COUNTER_FILE, counter_data)
    save_json_data(INVENTORY_FILE, inventory)

    emit_kitchen_update()

    return jsonify({'results': results})


# --- Delivery Address Management Endpoints ---

@app.route('/api/orders/<int:order_id>/delivery_address', methods=['GET'])
def get_delivery_address(order_id):
    """Get delivery address for a specific order."""
    orders = load_json_data(ORDERS_FILE)
    for order in orders:
        if order.get('order_id') == order_id:
            addr = order.get('delivery_address')
            if addr:
                return jsonify({'delivery_address': addr})
            return jsonify({'delivery_address': None}), 404
    return jsonify({'message': 'Order not found'}), 404


@app.route('/api/orders/<int:order_id>/delivery_address', methods=['POST'])
def update_delivery_address(order_id):
    """Update delivery address for a specific order."""
    data = request.json
    address = data.get('address')
    if not address:
        return jsonify({'message': 'Address data is required'}), 400

    orders = load_json_data(ORDERS_FILE)
    found = False
    for order in orders:
        if order.get('order_id') == order_id:
            order['delivery_address'] = address
            found = True
            break

    if not found:
        return jsonify({'message': 'Order not found'}), 404

    save_json_data(ORDERS_FILE, orders)
    return jsonify({'message': 'Delivery address updated successfully'})


@app.route('/api/delivery_addresses', methods=['GET'])
def list_delivery_addresses():
    """List saved delivery addresses, optionally filtered by user or phone."""
    user_id = request.args.get('user', '')
    phone = request.args.get('phone', '')
    addresses = load_json_data(DELIVERY_ADDRESSES_FILE)

    if user_id:
        results = {k: v for k, v in addresses.items() if v.get('user') == user_id}
    elif phone:
        results = {k: v for k, v in addresses.items() if v.get('phone') == phone}
    else:
        results = addresses

    return jsonify({'addresses': results})


@app.route('/api/delivery_addresses/save', methods=['POST'])
def save_delivery_address():
    """Save a delivery address for future reuse."""
    data = request.json
    label = data.get('label', '').strip()
    address = data.get('address')
    user = data.get('user', '')
    phone = data.get('phone', '')

    if not address or not isinstance(address, dict):
        return jsonify({'message': 'Valid address data is required'}), 400

    addresses = load_json_data(DELIVERY_ADDRESSES_FILE)

    # Generate a unique key
    key = label if label else f"addr_{len(addresses) + 1}_{datetime.now().timestamp()}"
    addresses[key] = {
        'address': address,
        'user': user,
        'phone': phone,
        'label': label,
        'saved_at': datetime.now().isoformat()
    }

    save_json_data(DELIVERY_ADDRESSES_FILE, addresses)
    return jsonify({'message': 'Address saved successfully', 'key': key})


@app.route('/api/delivery_addresses/<path:key>', methods=['DELETE'])
def delete_delivery_address(key):
    """Delete a saved delivery address."""
    addresses = load_json_data(DELIVERY_ADDRESSES_FILE)
    if key not in addresses:
        return jsonify({'message': 'Address not found'}), 404

    del addresses[key]
    save_json_data(DELIVERY_ADDRESSES_FILE, addresses)
    return jsonify({'message': 'Address deleted successfully'})


# --- Public Orders List Endpoint (no view_stats required) ---

@app.route('/api/orders/list', methods=['POST'])
def orders_list():
    """
    Returns raw orders and cleared orders for the authenticated user.
    Does NOT require view_stats permission — any logged-in user (pos_access)
    can see orders. This fixes the bug where waiters got 'Network error'
    when clicking the History tab.
    """
    data = request.json
    admin_pin = data.get('adminPin')

    # Basic auth: just verify the user exists (don't require view_stats)
    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'User not found.'}), 403

    user_info = upgrade_user(users[admin_pin])
    if user_info.get('banned', False):
        return jsonify({'message': 'User is banned.'}), 403

    orders = load_json_data(ORDERS_FILE)
    cleared_orders = load_json_data(CLEARED_ORDERS_FILE)

    # --- Date range filtering ---
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()

    def filter_by_date_range(order_list, date_field='date'):
        filtered = order_list
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                filtered = [o for o in filtered if datetime.fromisoformat(o.get(date_field, '')) >= dt_from]
            except (ValueError, KeyError):
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                filtered = [o for o in filtered if datetime.fromisoformat(o.get(date_field, '')) <= dt_to]
            except (ValueError, KeyError):
                pass
        return filtered

    orders = filter_by_date_range(orders)
    cleared_orders = filter_by_date_range(cleared_orders)

    # Sort orders by date descending
    orders.sort(key=lambda o: o.get('date', ''), reverse=True)
    cleared_orders.sort(key=lambda o: o.get('date', ''), reverse=True)

    return jsonify({
        'message': 'Orders retrieved',
        'orders': orders,
        'cleared_orders': cleared_orders
    })


# --- Refund / Void Order Endpoint ---

@app.route('/api/orders/refund', methods=['POST'])
def refund_order():
    """
    Refund/void an order with reason tracking.
    Requires manage_orders permission.
    Marks the order as 'refunded' in orders.json with reason and timestamp.
    """
    data = request.json
    admin_pin = data.get('adminPin')
    order_id = data.get('order_id')
    reason = data.get('reason', '').strip()

    if not check_perm(admin_pin, "manage_orders"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if order_id is None:
        return jsonify({'message': 'Order ID is required.'}), 400

    orders = load_json_data(ORDERS_FILE)
    found_order = None

    for order in orders:
        if order.get('order_id') == int(order_id):
            if order.get('status') in ('refunded', 'voided'):
                return jsonify({'message': f'Order #{order_id} has already been refunded/voided.'}), 400
            found_order = order
            break

    if not found_order:
        return jsonify({'message': f'Order #{order_id} not found.'}), 404

    if not reason:
        reason = 'No reason provided'

    # Mark the order as refunded
    found_order['status'] = 'refunded'
    found_order['refund_reason'] = reason
    found_order['refunded_at'] = datetime.now().isoformat()
    found_order['refunded_by'] = admin_pin

    save_json_data(ORDERS_FILE, orders)

    # Also log to refunded_orders.json for easy audit trail
    refunded_orders = load_json_data(REFUNDED_ORDERS_FILE)
    refunded_orders.append({
        'order_id': int(order_id),
        'original_order': {k: v for k, v in found_order.items() if k != 'original_order'},
        'reason': reason,
        'refunded_at': found_order['refunded_at'],
        'refunded_by': admin_pin
    })
    save_json_data(REFUNDED_ORDERS_FILE, refunded_orders)

    # Log activity
    users = load_json_data(USERS_FILE)
    user_name = users.get(admin_pin, {}).get('name', 'Unknown')
    user_role = users.get(admin_pin, {}).get('role', 'unknown')
    log_activity('refund_order', admin_pin, user_role, {
        'order_id': int(order_id),
        'reason': reason,
        'refunded_by_name': user_name,
        'order_total': found_order.get('total', 0)
    })

    return jsonify({
        'message': f'Order #{order_id} refunded successfully.',
        'reason': reason
    })


# --- Refund History Endpoint ---

@app.route('/api/orders/refunds', methods=['POST'])
def get_refunds():
    """Return the list of refunded orders for audit."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_orders"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    refunded_orders = load_json_data(REFUNDED_ORDERS_FILE)
    return jsonify({'refunds': refunded_orders, 'count': len(refunded_orders)})


# --- Quick-Order Favorites Endpoints ---

@app.route('/api/favorites/save', methods=['POST'])
def save_favorite():
    """Save current cart items as a named favorite combo for the user."""
    data = request.json
    user_id = data.get('user_id')
    name = data.get('name', '').strip()
    items = data.get('items', [])

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400
    if not name:
        return jsonify({'message': 'Favorite name is required.'}), 400
    if not items or len(items) == 0:
        return jsonify({'message': 'Cart items are required to save a favorite.'}), 400
    if len(name) > 50:
        return jsonify({'message': 'Favorite name must be 50 characters or less.'}), 400

    favorites = load_json_data(FAVORITES_FILE)
    if user_id not in favorites:
        favorites[user_id] = []

    # Limit per user to 20 favorites
    if len(favorites[user_id]) >= 20:
        return jsonify({'message': 'Maximum of 20 favorites per user. Delete some first.'}), 400

    # Check for duplicate names
    for fav in favorites[user_id]:
        if fav['name'].lower() == name.lower():
            return jsonify({'message': 'A favorite with this name already exists.'}), 409

    # Normalize items — keep name, qty, category, price
    sanitized_items = []
    for item in items:
        sanitized_items.append({
            'name': item.get('name', ''),
            'qty': int(item.get('qty', 1)),
            'category': item.get('category', ''),
            'price': float(item.get('price', 0))
        })

    new_fav = {
        'id': secrets.token_hex(8),
        'name': name,
        'items': sanitized_items,
        'created_at': datetime.now().isoformat()
    }
    favorites[user_id].append(new_fav)
    save_json_data(FAVORITES_FILE, favorites)

    log_activity('save_favorite', user_id, 'user', {
        'favorite_id': new_fav['id'],
        'favorite_name': name,
        'item_count': len(sanitized_items)
    })

    return jsonify({
        'message': 'Favorite saved successfully',
        'favorite': new_fav
    })


@app.route('/api/favorites/list', methods=['POST'])
def list_favorites():
    """List all saved favorites for a user."""
    data = request.json
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    favorites = load_json_data(FAVORITES_FILE)
    user_favs = favorites.get(user_id, [])

    return jsonify({
        'favorites': user_favs,
        'count': len(user_favs)
    })


@app.route('/api/favorites/delete', methods=['POST'])
def delete_favorite():
    """Delete a saved favorite by ID."""
    data = request.json
    user_id = data.get('user_id')
    favorite_id = data.get('favorite_id')

    if not user_id or not favorite_id:
        return jsonify({'message': 'User ID and favorite ID are required.'}), 400

    favorites = load_json_data(FAVORITES_FILE)
    if user_id not in favorites:
        return jsonify({'message': 'No favorites found for this user.'}), 404

    before = len(favorites[user_id])
    favorites[user_id] = [f for f in favorites[user_id] if f.get('id') != favorite_id]

    if len(favorites[user_id]) == before:
        return jsonify({'message': 'Favorite not found.'}), 404

    save_json_data(FAVORITES_FILE, favorites)

    log_activity('delete_favorite', user_id, 'user', {
        'favorite_id': favorite_id
    })

    return jsonify({'message': 'Favorite deleted successfully'})


# --- Admin Panel Endpoints ---

@app.route('/api/admin_stats', methods=['POST'])
def admin_stats():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        log_activity('admin_login', admin_pin, 'unauthorized', {'status': 'failed'})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users_data = load_json_data(USERS_FILE)

    admin_user_id = admin_pin if admin_pin in users_data else None

    log_activity('admin_login', admin_pin, 'admin', {'status': 'success'})
    # Record admin login for timesheet if not already active
    if admin_user_id not in active_admin_sessions:
        active_admin_sessions[admin_user_id] = datetime.now()

    orders = load_json_data(ORDERS_FILE)
    cleared_orders = load_json_data(CLEARED_ORDERS_FILE)

    # --- Date range filtering ---
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()

    def filter_by_date_range(order_list, date_field='date'):
        """Filter a list of order dicts by date_from / date_to."""
        filtered = order_list
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                filtered = [o for o in filtered if datetime.fromisoformat(o.get(date_field, '')) >= dt_from]
            except (ValueError, KeyError):
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                filtered = [o for o in filtered if datetime.fromisoformat(o.get(date_field, '')) <= dt_to]
            except (ValueError, KeyError):
                pass
        return filtered

    orders = filter_by_date_range(orders)
    cleared_orders = filter_by_date_range(cleared_orders)

    processed_orders = []
    for order in orders:
        # Skip refunded/voided orders for revenue calculations
        if order.get('status') in ('refunded', 'voided'):
            continue
        try:
            order_total = float(order.get('total', 0))
            order['total'] = order_total
            processed_orders.append(order)
        except (ValueError, TypeError):
            print(f"Warning: Could not convert 'total' to float for order: {order}. Skipping for stats.")
            continue

    total_sales = sum(order['total'] for order in processed_orders)
    total_traffic = len(processed_orders)
    avg_sale = total_sales / total_traffic if total_traffic > 0 else 0

    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)  # Approx month

    weekly_sales = sum(order['total'] for order in processed_orders if datetime.fromisoformat(order['date']) >= week_ago)
    monthly_sales = sum(order['total'] for order in processed_orders if datetime.fromisoformat(order['date']) >= month_ago)

    stats = {
        'total_sales': round(total_sales, 2),
        'total_traffic': total_traffic,
        'average_sale': round(avg_sale, 2),
        'weekly_sales': round(weekly_sales, 2),
        'monthly_sales': round(monthly_sales, 2),
        'raw_orders': orders,
        'raw_cleared_orders': cleared_orders
    }
    return jsonify({'message': 'Admin data retrieved', 'stats': stats})


@app.route('/api/admin_timesheet', methods=['POST'])
def admin_timesheet():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    timesheet_data = load_json_data(TIMESHEET_FILE)
    return jsonify({'message': 'Timesheet data retrieved', 'timesheet': timesheet_data})


@app.route('/api/activity_log', methods=['POST'])
def activity_log():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_logs"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    logs = load_json_data(ACTIVITY_LOG_FILE)

    # Extract available types and users for filter dropdowns
    available_types = sorted(set(log.get('type', '') for log in logs))
    available_users = sorted(set(
        log.get('user_id', '') for log in logs
        if log.get('user_id')
    ))

    # Apply filters
    user_filter = (data.get('user_filter') or '').strip().lower()
    type_filter = (data.get('type_filter') or '').strip()
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()

    filtered = logs
    if user_filter:
        filtered = [log for log in filtered
                    if user_filter in log.get('user_id', '').lower()]
    if type_filter:
        filtered = [log for log in filtered
                    if log.get('type', '') == type_filter]
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filtered = [log for log in filtered
                        if datetime.fromisoformat(log['timestamp']) >= dt_from]
        except (ValueError, KeyError):
            pass
    if date_to:
        try:
            # Include the full end-date day (set time to 23:59:59)
            if 'T' not in date_to:
                dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
            else:
                dt_to = datetime.fromisoformat(date_to)
            filtered = [log for log in filtered
                        if datetime.fromisoformat(log['timestamp']) <= dt_to]
        except (ValueError, KeyError):
            pass

    return jsonify({
        'message': 'Activity log retrieved',
        'log': filtered,
        'available_types': available_types,
        'available_users': available_users
    })


# ============================================================
# --- Analytics Endpoints (Public - No Auth Required) ---
# ============================================================

@app.route('/api/analytics/most_ordered', methods=['GET'])
def analytics_most_ordered():
    """Returns top 20 most-ordered items by frequency across all orders."""
    try:
        orders = load_json_data(ORDERS_FILE)
        item_counter = Counter()

        for order in orders:
            items = order.get('items', [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'name' in item:
                        item_counter[item['name']] += 1
                    elif isinstance(item, str):
                        item_counter[item] += 1

        # Sort by count descending, take top 20
        most_ordered = [{'name': name, 'count': count}
                        for name, count in item_counter.most_common(20)]
        return jsonify({'most_ordered': most_ordered})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/hourly_sales', methods=['GET'])
def analytics_hourly_sales():
    """Returns sales counts grouped by hour of day (0-23) for all time."""
    try:
        orders = load_json_data(ORDERS_FILE)
        hourly_counts = [0] * 24  # Index 0 = midnight (00:00-00:59), ..., 23 = 11 PM

        for order in orders:
            try:
                order_date = order.get('date', '')
                if order_date:
                    dt = datetime.fromisoformat(order_date)
                    hour = dt.hour
                    hourly_counts[hour] += 1
            except (ValueError, TypeError):
                continue

        hourly_sales = [{'hour': h, 'count': c} for h, c in enumerate(hourly_counts)]
        # Sort by count descending
        hourly_sales.sort(key=lambda x: x['count'], reverse=True)
        return jsonify({'hourly_sales': hourly_sales})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/daily_revenue', methods=['GET'])
def analytics_daily_revenue():
    """Returns daily revenue for the last 30 days [{date, revenue, order_count}]."""
    try:
        orders = load_json_data(ORDERS_FILE)
        now = datetime.now()
        thirty_days_ago = now - timedelta(days=30)
        thirty_days_ago_date = thirty_days_ago.date()

        # Group by date
        daily_data = defaultdict(lambda: {'revenue': 0.0, 'order_count': 0})

        for order in orders:
            try:
                order_date = order.get('date', '')
                if not order_date:
                    continue
                dt = datetime.fromisoformat(order_date)
                date_key = dt.date().isoformat()

                if dt.date() >= thirty_days_ago_date:
                    total = order.get('total', 0)
                    daily_data[date_key]['revenue'] += float(total)
                    daily_data[date_key]['order_count'] += 1
            except (ValueError, TypeError):
                continue

        # Build result sorted by date descending
        daily_revenue = [
            {
                'date': date_key,
                'revenue': round(data['revenue'], 2),
                'order_count': data['order_count']
            }
            for date_key, data in daily_data.items()
        ]
        daily_revenue.sort(key=lambda x: x['date'], reverse=True)

        return jsonify({'daily_revenue': daily_revenue})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/popular_combos', methods=['GET'])
def analytics_popular_combos():
    """Returns items frequently ordered together (pairs that appear in same order at least 2 times)."""
    try:
        orders = load_json_data(ORDERS_FILE)
        pair_counter = Counter()

        for order in orders:
            items = order.get('items', [])
            if not isinstance(items, list):
                continue

            # Extract item names
            item_names = []
            for item in items:
                if isinstance(item, dict) and 'name' in item:
                    item_names.append(item['name'])
                elif isinstance(item, str):
                    item_names.append(item)

            # Generate all unique pairs (combinations of 2)
            sorted_names = sorted(set(item_names))
            n = len(sorted_names)
            for i in range(n):
                for j in range(i + 1, n):
                    pair = (sorted_names[i], sorted_names[j])
                    pair_counter[pair] += 1

        # Filter pairs that appear at least 2 times
        popular = [
            {'item1': pair[0], 'item2': pair[1], 'count': count}
            for pair, count in pair_counter.items()
            if count >= 2
        ]
        # Sort by count descending
        popular.sort(key=lambda x: x['count'], reverse=True)

        return jsonify({'popular_combos': popular})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/item_trends', methods=['GET'])
def analytics_item_trends():
    """Returns item popularity trends — comparing recent 7 days vs previous 7 days.
    Returns items sorted by trend (rising first), with change percentage and direction.
    """
    try:
        orders = load_json_data(ORDERS_FILE)
        now = datetime.now()

        # Define two periods: recent = last 7 days, previous = 7-14 days ago
        recent_cutoff = now - timedelta(days=7)
        previous_cutoff = now - timedelta(days=14)

        recent_counts = Counter()
        previous_counts = Counter()

        for order in orders:
            try:
                order_date = order.get('date', '')
                if not order_date:
                    continue
                dt = datetime.fromisoformat(order_date)
            except (ValueError, TypeError):
                continue

            items = order.get('items', [])
            if not isinstance(items, list):
                continue

            # Determine which period this order belongs to
            if dt >= recent_cutoff:
                counter = recent_counts
            elif dt >= previous_cutoff:
                counter = previous_counts
            else:
                continue  # Outside both windows

            for item in items:
                if isinstance(item, dict) and 'name' in item:
                    counter[item['name']] += int(item.get('qty', 1))
                elif isinstance(item, str):
                    counter[item] += 1

        # Build trend data for all items that appear in either period
        all_item_names = set(recent_counts.keys()) | set(previous_counts.keys())
        trends = []
        for name in all_item_names:
            recent = recent_counts.get(name, 0)
            previous = previous_counts.get(name, 0)

            # Calculate change percentage
            if previous > 0:
                change_pct = round(((recent - previous) / previous) * 100, 1)
            elif recent > 0:
                change_pct = 100.0  # New item (from 0 to something)
            else:
                change_pct = 0.0

            # Determine direction
            if change_pct > 5:
                direction = 'rising'
            elif change_pct < -5:
                direction = 'falling'
            else:
                direction = 'stable'

            trends.append({
                'name': name,
                'recent_count': recent,
                'previous_count': previous,
                'change': recent - previous,
                'change_pct': change_pct,
                'direction': direction
            })

        # Sort: rising first (by change_pct descending), then stable, then falling
        def sort_key(t):
            order = {'rising': 0, 'stable': 1, 'falling': 2}
            return (order[t['direction']], -t['change_pct'] if t['direction'] == 'rising' else t['change_pct'])

        trends.sort(key=sort_key)

        return jsonify({'trends': trends, 'period_days': 7})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/summary', methods=['GET'])
def analytics_summary():
    """Returns quick summary: total_orders_today, revenue_today, avg_order_today, top_item_today, active_users_count."""
    try:
        orders = load_json_data(ORDERS_FILE)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        today_orders = []
        for order in orders:
            try:
                order_date = order.get('date', '')
                if order_date:
                    dt = datetime.fromisoformat(order_date)
                    if dt >= today_start:
                        today_orders.append(order)
            except (ValueError, TypeError):
                continue

        total_orders_today = len(today_orders)
        revenue_today = sum(float(o.get('total', 0)) for o in today_orders)
        avg_order_today = round(revenue_today / total_orders_today, 2) if total_orders_today > 0 else 0.0

        # Top item today
        item_counter = Counter()
        for order in today_orders:
            items = order.get('items', [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'name' in item:
                        item_counter[item['name']] += 1
                    elif isinstance(item, str):
                        item_counter[item] += 1

        top_item_today = item_counter.most_common(1)
        top_item_today_name = top_item_today[0][0] if top_item_today else None

        # Active users count (users who placed an order today)
        active_users = set()
        for order in today_orders:
            user = order.get('user', '')
            if user:
                active_users.add(user)

        # Count payment methods (handle both legacy single and split payments)
        payment_counter = Counter()
        for order in today_orders:
            splits = order.get('payment_splits')
            if splits and isinstance(splits, list):
                for s in splits:
                    payment_counter[s['method']] += 1
            else:
                pm = order.get('payment', 'Unknown')
                payment_counter[pm] += 1

        summary = {
            'total_orders_today': total_orders_today,
            'revenue_today': round(revenue_today, 2),
            'avg_order_today': avg_order_today,
            'top_item_today': top_item_today_name,
            'active_users_count': len(active_users),
            'payment_methods': dict(payment_counter)
        }

        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/suggestions', methods=['POST'])
def get_suggestions():
    """Returns smart reorder suggestions based on user's past orders.
    Accepts {userId}. Looks at user's last 10 orders, returns most common items."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Missing request body'}), 400

        user_id = data.get('userId')
        if not user_id:
            return jsonify({'error': 'userId is required'}), 400

        # Validate user exists
        users = load_json_data(USERS_FILE)
        if user_id not in users:
            return jsonify({'error': 'Invalid userId'}), 404

        orders = load_json_data(ORDERS_FILE)

        # Filter orders by this user
        user_orders = [o for o in orders if str(o.get('user', '')) == str(user_id)]

        # Sort by date descending and take last 10
        def get_order_date(order):
            try:
                return datetime.fromisoformat(order.get('date', ''))
            except (ValueError, TypeError):
                return datetime.min

        user_orders.sort(key=get_order_date, reverse=True)
        last10 = user_orders[:10]

        # Count items in last 10 orders
        item_counter = Counter()
        for order in last10:
            items = order.get('items', [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'name' in item:
                        item_counter[item['name']] += 1
                    elif isinstance(item, str):
                        item_counter[item] += 1

        # Get most common items sorted by count descending
        suggestions = [
            {'name': name, 'times_ordered': count}
            for name, count in item_counter.most_common()
        ]

        return jsonify({
            'userId': user_id,
            'orders_analyzed': len(last10),
            'suggestions': suggestions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# --- Tax Configuration Endpoints ---
# ============================================================

def get_effective_tax_rate(item_name, category, tax_config):
    """Determine the effective tax rate for an item.
    Priority: item override > category override > global rate.
    """
    # Check item-specific override
    item_overrides = tax_config.get('item_tax_overrides', {})
    if item_name in item_overrides and item_overrides[item_name] is not None:
        return float(item_overrides[item_name])

    # Check category override
    cat_rates = tax_config.get('category_tax_rates', {})
    if category in cat_rates and cat_rates[category] is not None:
        return float(cat_rates[category])

    # Fall back to global rate
    return float(tax_config.get('global_tax_rate', 0.0))


@app.route('/api/tax_config', methods=['GET'])
def get_tax_config():
    """Get the current tax configuration (public, no auth required)."""
    config = load_json_data(TAX_CONFIG_FILE)
    return jsonify(config)


@app.route('/api/tax_config', methods=['POST'])
def update_tax_config():
    """Update tax configuration (admin/owner only)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('update_tax_config', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Unauthorized. Admin PIN or permission required.'}), 403

    config = load_json_data(TAX_CONFIG_FILE)

    if 'global_tax_rate' in data:
        try:
            rate = float(data['global_tax_rate'])
            if rate < 0 or rate > 100:
                return jsonify({'message': 'Tax rate must be between 0 and 100 percent.'}), 400
            config['global_tax_rate'] = rate
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid tax rate. Must be a number between 0 and 100.'}), 400

    if 'category_tax_rates' in data:
        config['category_tax_rates'] = data['category_tax_rates']

    if 'item_tax_overrides' in data:
        config['item_tax_overrides'] = data['item_tax_overrides']

    save_json_data(TAX_CONFIG_FILE, config)
    log_activity('update_tax_config', admin_pin, 'admin', {'new_config': config})
    return jsonify({'message': 'Tax configuration updated successfully', 'config': config})


# ============================================================
# --- Discount / Coupon Code Endpoints ---
# ============================================================

@app.route('/api/discounts', methods=['GET'])
def get_discounts():
    """Get all discount codes (public, no auth — used for validation on frontend)."""
    discounts = load_json_data(DISCOUNTS_FILE)
    # Return only active discounts for public view, include all for admin (filtered on frontend)
    return jsonify(discounts)


@app.route('/api/discounts', methods=['POST'])
def manage_discount():
    """Add, update, or delete discount codes (admin/owner only)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('manage_discount', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Unauthorized. Admin PIN or permission required.'}), 403

    action = data.get('action')  # 'add', 'update', 'delete'

    if action == 'add' or action == 'update':
        code = data.get('code')
        discount_type = data.get('discount_type')  # 'percent' or 'flat'
        value = data.get('value')
        min_order = data.get('min_order', 0)
        description = data.get('description', '')
        usage_limit = data.get('usage_limit')  # null = unlimited

        if not code or not discount_type or value is None:
            return jsonify({'message': 'Missing required fields: code, discount_type, value.'}), 400

        if discount_type not in ('percent', 'flat'):
            return jsonify({'message': 'discount_type must be "percent" or "flat".'}), 400

        try:
            value = float(value)
            if value <= 0:
                raise ValueError
            if discount_type == 'percent' and value > 100:
                return jsonify({'message': 'Percentage discount cannot exceed 100%.'}), 400
        except ValueError:
            return jsonify({'message': 'Invalid value. Must be a positive number.'}), 400

        try:
            min_order = float(min_order) if min_order else 0
        except ValueError:
            return jsonify({'message': 'Invalid min_order value.'}), 400

        discounts = load_json_data(DISCOUNTS_FILE)
        code_upper = code.upper().strip()

        if action == 'add' and code_upper in discounts:
            return jsonify({'message': f'Discount code "{code_upper}" already exists.'}), 409

        discounts[code_upper] = {
            'type': discount_type,
            'value': value,
            'min_order': min_order,
            'active': True,
            'description': description,
            'usage_limit': int(usage_limit) if usage_limit else None,
            'times_used': discounts.get(code_upper, {}).get('times_used', 0),
            'created_at': discounts.get(code_upper, {}).get('created_at', datetime.now().isoformat())
        }

        save_json_data(DISCOUNTS_FILE, discounts)
        log_activity('manage_discount', admin_pin, 'admin', {
            'action': action, 'code': code_upper, 'type': discount_type, 'value': value
        })
        return jsonify({'message': f'Discount code "{code_upper}" {action}ed successfully.', 'discounts': discounts})

    elif action == 'delete':
        code = data.get('code')
        if not code:
            return jsonify({'message': 'Missing discount code to delete.'}), 400

        discounts = load_json_data(DISCOUNTS_FILE)
        code_upper = code.upper().strip()

        if code_upper not in discounts:
            return jsonify({'message': f'Discount code "{code_upper}" not found.'}), 404

        del discounts[code_upper]
        save_json_data(DISCOUNTS_FILE, discounts)
        log_activity('manage_discount', admin_pin, 'admin', {
            'action': 'delete', 'code': code_upper
        })
        return jsonify({'message': f'Discount code "{code_upper}" deleted successfully.', 'discounts': discounts})

    elif action == 'toggle':
        code = data.get('code')
        if not code:
            return jsonify({'message': 'Missing discount code to toggle.'}), 400

        discounts = load_json_data(DISCOUNTS_FILE)
        code_upper = code.upper().strip()

        if code_upper not in discounts:
            return jsonify({'message': f'Discount code "{code_upper}" not found.'}), 404

        discounts[code_upper]['active'] = not discounts[code_upper].get('active', True)
        save_json_data(DISCOUNTS_FILE, discounts)
        status = 'enabled' if discounts[code_upper]['active'] else 'disabled'
        log_activity('manage_discount', admin_pin, 'admin', {
            'action': 'toggle', 'code': code_upper, 'status': status
        })
        return jsonify({'message': f'Discount code "{code_upper}" {status}.', 'discounts': discounts})

    return jsonify({'message': 'Invalid action. Use "add", "update", "delete", or "toggle".'}), 400


@app.route('/api/validate_discount', methods=['POST'])
def validate_discount():
    """Validate a discount code and return the discount amount for a given subtotal."""
    data = request.json
    code = data.get('code', '').upper().strip()
    subtotal = float(data.get('subtotal', 0))

    if not code:
        return jsonify({'valid': False, 'message': 'No discount code provided.'})

    discounts = load_json_data(DISCOUNTS_FILE)

    if code not in discounts:
        return jsonify({'valid': False, 'message': 'Invalid discount code.'})

    discount = discounts[code]

    if not discount.get('active', True):
        return jsonify({'valid': False, 'message': 'This discount code is no longer active.'})

    # Check usage limit
    usage_limit = discount.get('usage_limit')
    times_used = discount.get('times_used', 0)
    if usage_limit is not None and times_used >= usage_limit:
        return jsonify({'valid': False, 'message': 'This discount code has reached its usage limit.'})

    # Check minimum order
    min_order = discount.get('min_order', 0)
    if subtotal < min_order:
        return jsonify({
            'valid': False,
            'message': f'Minimum order of ${min_order:.2f} required for this code.'
        })

    # Calculate discount amount
    if discount['type'] == 'percent':
        discount_amount = subtotal * (discount['value'] / 100.0)
    else:  # flat
        discount_amount = discount['value']
        # Don't allow discount to exceed subtotal
        if discount_amount > subtotal:
            discount_amount = subtotal

    discount_amount = round(discount_amount, 2)

    return jsonify({
        'valid': True,
        'code': code,
        'type': discount['type'],
        'value': discount['value'],
        'discount_amount': discount_amount,
        'description': discount.get('description', ''),
        'message': f'Discount applied: {discount_amount:.2f}'
    })


# ============================================================
# --- Scheduled Pricing (Happy Hour, Daily Specials) ---
# ============================================================

def is_schedule_active(rule):
    """Check if a pricing rule is active right now based on day of week and time."""
    import datetime as dt
    now = dt.datetime.now()
    # Check days_of_week
    days = rule.get('days_of_week', [0,1,2,3,4,5,6])
    if now.weekday() not in days:
        return False
    # Check time range
    start_str = rule.get('start_time', '00:00')
    end_str = rule.get('end_time', '23:59')
    try:
        start_h, start_m = map(int, start_str.split(':'))
        end_h, end_m = map(int, end_str.split(':'))
        now_minutes = now.hour * 60 + now.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        if start_minutes <= end_minutes:
            return start_minutes <= now_minutes <= end_minutes
        else:
            # Overnight schedule (e.g., 22:00 - 02:00)
            return now_minutes >= start_minutes or now_minutes <= end_minutes
    except (ValueError, TypeError):
        return False

def get_active_scheduled_discounts():
    """Return list of pricing rules that are currently active."""
    rules = load_json_data(SCHEDULED_PRICING_FILE)
    if not isinstance(rules, list):
        return []
    active = [r for r in rules if r.get('active', True) and is_schedule_active(r)]
    return active

def get_scheduled_pricing_map(items_data):
    """Return a dict: item_name -> {original_price, discounted_price, discount_label}
    for all items affected by currently active scheduled pricing rules."""
    active_rules = get_active_scheduled_discounts()
    if not active_rules:
        return {}

    pricing_map = {}
    for cat, cat_items in items_data.items():
        for item in cat_items:
            name = item['name']
            orig_price = float(item['price'])
            best_price = orig_price
            best_label = ''
            for rule in active_rules:
                # Check if rule applies to this item
                rule_cat = rule.get('category', 'all')
                if rule_cat != 'all' and rule_cat != cat:
                    continue
                # Check item filter (optional)
                item_filter = rule.get('item_filter', 'all')
                if item_filter != 'all' and item_filter.lower() != name.lower():
                    continue

                discount_type = rule.get('discount_type', 'percent')
                value = float(rule.get('value', 0))
                if value <= 0:
                    continue

                if discount_type == 'percent':
                    disc_price = orig_price * (1 - value / 100.0)
                elif discount_type == 'flat':
                    disc_price = max(0, orig_price - value)
                else:
                    continue

                if disc_price < best_price:
                    best_price = disc_price
                    best_label = rule.get('name', 'Discount')

            best_price = round(best_price, 2)
            if best_price < orig_price:
                pricing_map[name] = {
                    'original_price': orig_price,
                    'discounted_price': best_price,
                    'discount_label': best_label,
                    'category': cat
                }
    return pricing_map


@app.route('/api/scheduled_pricing', methods=['GET'])
def get_scheduled_pricing():
    """List all scheduled pricing rules (admin/manage_items required)."""
    admin_pin = request.args.get('adminPin', '')
    if admin_pin and not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    rules = load_json_data(SCHEDULED_PRICING_FILE)
    if not isinstance(rules, list):
        rules = []
    return jsonify(rules)


@app.route('/api/scheduled_pricing/add', methods=['POST'])
def add_scheduled_pricing():
    """Add a new scheduled pricing rule."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    name = data.get('name', '').strip()
    discount_type = data.get('discount_type', 'percent')
    value = data.get('value')
    category = data.get('category', 'all')
    item_filter = data.get('item_filter', 'all')
    days_of_week = data.get('days_of_week', [0,1,2,3,4,5,6])
    start_time = data.get('start_time', '00:00')
    end_time = data.get('end_time', '23:59')

    if not name:
        return jsonify({'message': 'Rule name is required.'}), 400
    if value is None:
        return jsonify({'message': 'Discount value is required.'}), 400
    try:
        value = float(value)
        if value <= 0:
            raise ValueError
        if discount_type == 'percent' and value > 100:
            return jsonify({'message': 'Percentage discount cannot exceed 100%.'}), 400
    except ValueError:
        return jsonify({'message': 'Invalid discount value.'}), 400

    if discount_type not in ('percent', 'flat'):
        return jsonify({'message': 'discount_type must be "percent" or "flat".'}), 400

    # Validate time format HH:MM
    try:
        for t in [start_time, end_time]:
            h, m = map(int, t.split(':'))
            if h < 0 or h > 23 or m < 0 or m > 59:
                raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid time format. Use HH:MM (24-hour).'}), 400

    rules = load_json_data(SCHEDULED_PRICING_FILE)
    if not isinstance(rules, list):
        rules = []

    rule = {
        'id': len(rules) + 1,
        'name': name,
        'discount_type': discount_type,
        'value': value,
        'category': category,
        'item_filter': item_filter,
        'days_of_week': days_of_week,
        'start_time': start_time,
        'end_time': end_time,
        'active': True,
        'created_at': datetime.now().isoformat()
    }
    rules.append(rule)
    save_json_data(SCHEDULED_PRICING_FILE, rules)

    admin_user = load_json_data(USERS_FILE).get(admin_pin, {})
    log_activity('add_scheduled_pricing', admin_pin, admin_user.get('role', 'unknown'), {
        'rule_name': name, 'discount_type': discount_type, 'value': value
    })
    return jsonify({'message': 'Pricing rule added successfully.', 'rules': rules})


@app.route('/api/scheduled_pricing/delete', methods=['POST'])
def delete_scheduled_pricing():
    """Delete a scheduled pricing rule by id."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    rule_id = data.get('id')
    if rule_id is None:
        return jsonify({'message': 'Rule id is required.'}), 400

    rules = load_json_data(SCHEDULED_PRICING_FILE)
    if not isinstance(rules, list):
        return jsonify({'message': 'No rules found.'}), 404

    new_rules = [r for r in rules if r.get('id') != rule_id]
    if len(new_rules) == len(rules):
        return jsonify({'message': f'Rule id {rule_id} not found.'}), 404

    save_json_data(SCHEDULED_PRICING_FILE, new_rules)
    admin_user = load_json_data(USERS_FILE).get(admin_pin, {})
    log_activity('delete_scheduled_pricing', admin_pin, admin_user.get('role', 'unknown'), {
        'rule_id': rule_id
    })
    return jsonify({'message': 'Pricing rule deleted successfully.', 'rules': new_rules})


@app.route('/api/scheduled_pricing/toggle', methods=['POST'])
def toggle_scheduled_pricing():
    """Toggle a pricing rule's active status."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    rule_id = data.get('id')
    if rule_id is None:
        return jsonify({'message': 'Rule id is required.'}), 400

    rules = load_json_data(SCHEDULED_PRICING_FILE)
    if not isinstance(rules, list):
        return jsonify({'message': 'No rules found.'}), 404

    found = False
    for r in rules:
        if r.get('id') == rule_id:
            r['active'] = not r.get('active', True)
            found = True
            break

    if not found:
        return jsonify({'message': f'Rule id {rule_id} not found.'}), 404

    save_json_data(SCHEDULED_PRICING_FILE, rules)
    return jsonify({'message': 'Rule toggled.', 'rules': rules})


@app.route('/api/scheduled_pricing/active', methods=['GET'])
def active_scheduled_pricing():
    """Return currently active scheduled discounts as a pricing map."""
    items_data = load_json_data(ITEMS_FILE)
    if not isinstance(items_data, dict):
        items_data = {}
    pricing_map = get_scheduled_pricing_map(items_data)
    active_rules = get_active_scheduled_discounts()
    return jsonify({
        'active_rules': [{'id': r.get('id'), 'name': r.get('name'), 'discount_type': r.get('discount_type'), 'value': r.get('value'), 'category': r.get('category', 'all')} for r in active_rules],
        'pricing_map': pricing_map
    })


# ============================================================
# --- Admin Role & Permission Management ---
# ============================================================

@app.route('/api/admin/roles', methods=['GET'])
def admin_roles():
    """Returns list of all users with their roles and permissions (owner only)."""
    admin_pin = request.args.get('adminPin', '')
    if not admin_pin:
        return jsonify({'message': 'Missing adminPin parameter.'}), 400

    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'Unauthorized.'}), 403

    caller = users[admin_pin]
    caller = upgrade_user(caller)
    if caller.get('role') != 'owner':
        return jsonify({'message': 'Owner only.'}), 403

    user_list = []
    for uid, u_data in users.items():
        u_data = upgrade_user(u_data)
        user_list.append({
            'userId': uid,
            'name': u_data.get('name', ''),
            'role': u_data.get('role', 'user'),
            'permissions': u_data.get('permissions', [])
        })

    return jsonify({'users': user_list})


@app.route('/api/admin/update_permissions', methods=['POST'])
def update_permissions():
    """Update a user's permissions (owner only)."""
    data = request.json
    owner_pin = data.get('ownerPin')
    target_user_id = data.get('targetUserId')
    permissions = data.get('permissions')

    if not owner_pin or not target_user_id or permissions is None:
        return jsonify({'message': 'Missing required fields: ownerPin, targetUserId, permissions.'}), 400

    users = load_json_data(USERS_FILE)
    if owner_pin not in users:
        return jsonify({'message': 'Unauthorized.'}), 403

    owner = users[owner_pin]
    owner = upgrade_user(owner)
    if owner.get('role') != 'owner':
        return jsonify({'message': 'Owner only.'}), 403

    if target_user_id not in users:
        return jsonify({'message': 'Target user not found.'}), 404

    if not isinstance(permissions, list):
        return jsonify({'message': 'Permissions must be a list of strings.'}), 400

    users[target_user_id]['permissions'] = permissions
    save_json_data(USERS_FILE, users)
    log_activity('update_permissions', owner_pin, 'owner', {
        'target_user_id': target_user_id,
        'new_permissions': permissions
    })
    return jsonify({'message': 'Permissions updated successfully.', 'userId': target_user_id, 'permissions': permissions})


# ============================================================
# --- User Ban / Unban ---
# ============================================================

@app.route('/api/users/ban', methods=['POST'])
def ban_user():
    """Ban a user (requires ban_users permission)."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    reason = data.get('reason', 'No reason provided')

    if not admin_pin or not user_id:
        return jsonify({'message': 'Missing required fields: adminPin, userId.'}), 400

    if not check_perm(admin_pin, "ban_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    users[user_id]['banned'] = True
    users[user_id]['banned_reason'] = reason
    save_json_data(USERS_FILE, users)
    log_activity('ban_user', admin_pin, users.get(admin_pin, {}).get('role', 'unknown'), {
        'banned_user_id': user_id,
        'reason': reason
    })
    return jsonify({'message': f'User {user_id} banned successfully.', 'userId': user_id, 'reason': reason})


@app.route('/api/users/unban', methods=['POST'])
def unban_user():
    """Unban a user (requires ban_users permission)."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')

    if not admin_pin or not user_id:
        return jsonify({'message': 'Missing required fields: adminPin, userId.'}), 400

    if not check_perm(admin_pin, "ban_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    if 'banned' in users[user_id]:
        del users[user_id]['banned']
    if 'banned_reason' in users[user_id]:
        del users[user_id]['banned_reason']
    save_json_data(USERS_FILE, users)
    log_activity('unban_user', admin_pin, users.get(admin_pin, {}).get('role', 'unknown'), {
        'unbanned_user_id': user_id
    })
    return jsonify({'message': f'User {user_id} unbanned successfully.', 'userId': user_id})


# ============================================================
# --- Menu History & Restore ---
# ============================================================

@app.route('/api/menu/history', methods=['GET'])
def menu_history():
    """Returns list of all menu backup files, sorted newest first."""
    if not os.path.exists(MENU_BACKUPS_DIR):
        return jsonify({'backups': []})

    backup_files = glob.glob(os.path.join(MENU_BACKUPS_DIR, 'items_*.json'))
    backups = []
    for fpath in backup_files:
        filename = os.path.basename(fpath)
        # Parse date from filename: items_YYYY-MM-DD_HH-MM-SS.json
        stem = filename.replace('items_', '').replace('.json', '')
        try:
            dt = datetime.strptime(stem, '%Y-%m-%d_%H-%M-%S')
            backups.append({
                'filename': filename,
                'date': dt.strftime('%Y-%m-%d'),
                'timestamp': dt.isoformat()
            })
        except ValueError:
            # Skip files that don't match the expected pattern
            continue

    # Sort newest first
    backups.sort(key=lambda b: b['timestamp'], reverse=True)
    return jsonify({'backups': backups})


@app.route('/api/menu/restore', methods=['POST'])
def menu_restore():
    """Restore a menu backup by date (owner only)."""
    data = request.json
    owner_pin = data.get('ownerPin')
    date_str = data.get('date')

    if not owner_pin or not date_str:
        return jsonify({'message': 'Missing required fields: ownerPin, date.'}), 400

    users = load_json_data(USERS_FILE)
    if owner_pin not in users:
        return jsonify({'message': 'Unauthorized.'}), 403

    owner = users[owner_pin]
    owner = upgrade_user(owner)
    if owner.get('role') != 'owner':
        return jsonify({'message': 'Owner only.'}), 403

    # First create a safety backup of current items.json
    if os.path.exists(ITEMS_FILE):
        pre_restore_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        pre_restore_filename = f'items_PRE_RESTORE_{pre_restore_timestamp}.json'
        pre_restore_path = os.path.join(MENU_BACKUPS_DIR, pre_restore_filename)
        if not os.path.exists(MENU_BACKUPS_DIR):
            os.makedirs(MENU_BACKUPS_DIR, exist_ok=True)
        shutil.copy2(ITEMS_FILE, pre_restore_path)

    # Find backup file matching the given date: items_YYYY-MM-DD_*.json
    pattern = os.path.join(MENU_BACKUPS_DIR, f'items_{date_str}_*.json')
    matching_files = sorted(glob.glob(pattern))

    if not matching_files:
        return jsonify({'message': f'No backup found for date {date_str}.'}), 404

    # Use the first (oldest) matching backup for that date
    backup_path = matching_files[0]
    backup_filename = os.path.basename(backup_path)

    # Read the backup and write to items.json
    with open(backup_path, 'r') as f:
        backup_data = json.load(f)
    save_json_data(ITEMS_FILE, backup_data)

    log_activity('menu_restore', owner_pin, 'owner', {
        'restored_from': backup_filename,
        'date': date_str
    })
    return jsonify({'message': f'Menu restored from backup {backup_filename}.', 'filename': backup_filename})


# ============================================================
# --- Kitchen Order Queue System ---
# ============================================================

@app.route('/api/kitchen/queue', methods=['GET'])
def kitchen_queue():
    """Returns all orders where status is 'pending' or 'preparing', sorted oldest first."""
    try:
        orders = load_json_data(ORDERS_FILE)
        active_orders = [o for o in orders if o.get('status') in ('pending', 'preparing')]
        # Sort by date ascending (oldest first)
        active_orders.sort(key=lambda o: o.get('date', ''))
        return jsonify({'queue': active_orders, 'count': len(active_orders)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/kitchen/claim', methods=['POST'])
def kitchen_claim():
    """Claims an order for a cook: sets status='preparing', claimed_by, claimed_at."""
    data = request.json
    cook_id = data.get('cookId')
    order_id = data.get('order_id')

    if not cook_id:
        return jsonify({'error': 'cookId is required'}), 400
    if order_id is None:
        return jsonify({'error': 'order_id is required'}), 400

    try:
        orders = load_json_data(ORDERS_FILE)
        for order in orders:
            if order.get('order_id') == order_id:
                if order.get('status') != 'pending':
                    return jsonify({'error': f'Order #{order_id} is already {order.get("status")}'}), 409
                order['status'] = 'preparing'
                order['claimed_by'] = cook_id
                order['claimed_at'] = datetime.now().isoformat()
                save_json_data(ORDERS_FILE, orders)
                log_activity('kitchen_claim', cook_id, 'kitchen', {
                    'order_id': order_id, 'action': 'claimed'
                })
                emit_kitchen_update()
                return jsonify({'message': f'Order #{order_id} claimed', 'order': order})
        return jsonify({'error': f'Order #{order_id} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/kitchen/complete', methods=['POST'])
def kitchen_complete():
    """Marks an order as completed."""
    data = request.json
    cook_id = data.get('cookId')
    order_id = data.get('order_id')

    if not cook_id:
        return jsonify({'error': 'cookId is required'}), 400
    if order_id is None:
        return jsonify({'error': 'order_id is required'}), 400

    try:
        orders = load_json_data(ORDERS_FILE)
        for order in orders:
            if order.get('order_id') == order_id:
                if order.get('status') != 'preparing':
                    return jsonify({'error': f'Order #{order_id} is not in preparing status (current: {order.get("status")})'}), 409
                order['status'] = 'completed'
                order['completed_at'] = datetime.now().isoformat()
                save_json_data(ORDERS_FILE, orders)
                log_activity('kitchen_complete', cook_id, 'kitchen', {
                    'order_id': order_id, 'action': 'completed'
                })
                emit_kitchen_update()
                return jsonify({'message': f'Order #{order_id} completed', 'order': order})
        return jsonify({'error': f'Order #{order_id} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/kitchen/cancel', methods=['POST'])
def kitchen_cancel():
    """Cancels an order with a reason."""
    data = request.json
    cook_id = data.get('cookId')
    order_id = data.get('order_id')
    reason = data.get('reason', 'No reason provided')

    if not cook_id:
        return jsonify({'error': 'cookId is required'}), 400
    if order_id is None:
        return jsonify({'error': 'order_id is required'}), 400

    try:
        orders = load_json_data(ORDERS_FILE)
        for order in orders:
            if order.get('order_id') == order_id:
                if order.get('status') in ('completed', 'cancelled'):
                    return jsonify({'error': f'Order #{order_id} is already {order.get("status")}'}), 409
                order['status'] = 'cancelled'
                order['cancellation_reason'] = reason
                order['cancelled_by'] = cook_id
                order['cancelled_at'] = datetime.now().isoformat()
                save_json_data(ORDERS_FILE, orders)
                log_activity('kitchen_cancel', cook_id, 'kitchen', {
                    'order_id': order_id, 'action': 'cancelled', 'reason': reason
                })
                emit_kitchen_update()
                return jsonify({'message': f'Order #{order_id} cancelled', 'order': order})
        return jsonify({'error': f'Order #{order_id} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/kitchen/stats', methods=['GET'])
def kitchen_stats():
    """Returns kitchen stats: orders today, avg prep time, queue size, etc."""
    try:
        orders = load_json_data(ORDERS_FILE)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        today_orders = []
        for order in orders:
            try:
                order_date = order.get('date', '')
                if order_date:
                    dt = datetime.fromisoformat(order_date)
                    if dt >= today_start:
                        today_orders.append(order)
            except (ValueError, TypeError):
                continue

        total_orders_today = len(today_orders)
        orders_completed_today = sum(1 for o in today_orders if o.get('status') == 'completed')
        pending_count = sum(1 for o in orders if o.get('status') == 'pending')
        preparing_count = sum(1 for o in orders if o.get('status') == 'preparing')
        current_queue_size = pending_count + preparing_count

        # Average prep time for orders completed today
        prep_times = []
        for order in today_orders:
            if order.get('status') == 'completed' and order.get('claimed_at') and order.get('completed_at'):
                try:
                    claimed = datetime.fromisoformat(order['claimed_at'])
                    completed = datetime.fromisoformat(order['completed_at'])
                    delta_minutes = (completed - claimed).total_seconds() / 60.0
                    if delta_minutes >= 0:
                        prep_times.append(delta_minutes)
                except (ValueError, TypeError):
                    continue

        avg_prep_time_minutes = round(sum(prep_times) / len(prep_times), 1) if prep_times else 0.0

        stats = {
            'total_orders_today': total_orders_today,
            'avg_prep_time_minutes': avg_prep_time_minutes,
            'done_today': orders_completed_today,
            'pending': pending_count,
            'preparing': preparing_count,
            'current_queue_size': current_queue_size
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/kitchen/order/<int:order_id>', methods=['GET'])
def kitchen_order_detail(order_id):
    """Returns a single order by ID for detail view."""
    try:
        orders = load_json_data(ORDERS_FILE)
        for order in orders:
            if order.get('order_id') == order_id:
                return jsonify({'order': order})
        return jsonify({'error': f'Order #{order_id} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# Drive-through Display System
# ============================================================

# In-memory live cart state for the drive-through display
drive_through_state = {
    'items': [],
    'subtotal': 0,
    'tax': 0,
    'total': 0,
    'status': 'idle',  # 'idle', 'building', 'ready'
    'order_number': None,
    'updated_at': datetime.now().isoformat()
}


@app.route('/api/drivethrough/update', methods=['POST'])
def drivethrough_update():
    """POS frontend pushes current cart state to drive-through display."""
    global drive_through_state
    data = request.json
    items = data.get('items', [])
    subtotal = float(data.get('subtotal', 0))
    tax = float(data.get('tax', 0))
    total = float(data.get('total', 0))
    drive_through_state = {
        'items': items,
        'subtotal': subtotal,
        'tax': tax,
        'total': total,
        'status': 'building',
        'order_number': None,
        'updated_at': datetime.now().isoformat()
    }
    emit_drivethrough_update()
    return jsonify({'message': 'Drive-through display updated'})


@app.route('/api/drivethrough/status', methods=['GET'])
def drivethrough_status():
    """Drive-through display polls for current order status."""
    return jsonify(drive_through_state)


@app.route('/api/drivethrough/complete', methods=['POST'])
def drivethrough_complete():
    """Mark the current order as ready (shows 'Please pull forward')."""
    global drive_through_state
    data = request.json
    drive_through_state['status'] = 'ready'
    drive_through_state['order_number'] = data.get('order_number')
    drive_through_state['updated_at'] = datetime.now().isoformat()
    emit_drivethrough_update()
    return jsonify({'message': 'Order marked as ready'})


@app.route('/api/drivethrough/reset', methods=['POST'])
def drivethrough_reset():
    """Reset the drive-through display to idle."""
    global drive_through_state
    drive_through_state = {
        'items': [],
        'subtotal': 0,
        'tax': 0,
        'total': 0,
        'status': 'idle',
        'order_number': None,
        'updated_at': datetime.now().isoformat()
    }
    emit_drivethrough_update()
    return jsonify({'message': 'Drive-through display reset'})


# ============================================================
# Customer-Facing Display System
# ============================================================

# In-memory live cart state for customer-facing display
customer_display_state = {
    'items': [],
    'subtotal': 0,
    'tax': 0,
    'tip': 0,
    'total': 0,
    'status': 'idle',  # 'idle', 'building', 'complete'
    'order_number': None,
    'mode_active': False,
    'updated_at': datetime.now().isoformat()
}


@app.route('/api/customer-display/update', methods=['POST'])
def customer_display_update():
    """POS frontend pushes current cart state to customer display."""
    global customer_display_state
    data = request.json
    items = data.get('items', [])
    subtotal = float(data.get('subtotal', 0))
    tax = float(data.get('tax', 0))
    tip = float(data.get('tip', 0))
    total = float(data.get('total', 0))
    customer_display_state = {
        'items': items,
        'subtotal': subtotal,
        'tax': tax,
        'tip': tip,
        'total': total,
        'status': 'building',
        'order_number': data.get('order_number'),
        'mode_active': True,
        'updated_at': datetime.now().isoformat()
    }
    emit_customer_update()
    return jsonify({'message': 'Customer display updated'})


@app.route('/api/customer-display/status', methods=['GET'])
def customer_display_status():
    """Customer display polls for current order state."""
    return jsonify(customer_display_state)


@app.route('/api/customer-display/complete', methods=['POST'])
def customer_display_complete():
    """Mark the current order as complete (shows thank-you screen)."""
    global customer_display_state
    data = request.json
    customer_display_state['status'] = 'complete'
    customer_display_state['order_number'] = data.get('order_number')
    customer_display_state['updated_at'] = datetime.now().isoformat()
    emit_customer_update()
    return jsonify({'message': 'Order marked as complete'})


@app.route('/api/customer-display/reset', methods=['POST'])
def customer_display_reset():
    """Reset the customer display to idle."""
    global customer_display_state
    customer_display_state = {
        'items': [],
        'subtotal': 0,
        'tax': 0,
        'tip': 0,
        'total': 0,
        'status': 'idle',
        'order_number': None,
        'mode_active': customer_display_state.get('mode_active', False),
        'updated_at': datetime.now().isoformat()
    }
    emit_customer_update()
    return jsonify({'message': 'Customer display reset'})


# ============================================================
# Table Management System
# ============================================================


@app.route('/api/tables', methods=['GET'])
def get_tables():
    """Returns all tables with their assignments and running tab info."""
    tables = load_json_data(TABLES_FILE)
    orders = load_json_data(ORDERS_FILE)
    
    result = {}
    for table_num, tdata in tables.items():
        # Calculate running tab for this table (unpaid orders)
        table_orders = [o for o in orders if o.get('table_number') == int(table_num) and o.get('status') in ('pending', 'preparing')]
        tab_total = sum(float(o.get('total', 0)) for o in table_orders)
        tab_items_count = sum(len(o.get('items', [])) for o in table_orders)
        
        result[table_num] = {
            'number': tdata.get('number'),
            'name': tdata.get('name', f"Table {table_num}"),
            'tablet_id': tdata.get('tablet_id', ''),
            'status': tdata.get('status', 'available'),
            'created_at': tdata.get('created_at', ''),
            'tab_total': round(tab_total, 2),
            'tab_order_count': len(table_orders),
            'tab_items_count': tab_items_count
        }
    return jsonify(result)


@app.route('/api/tables/assign', methods=['POST'])
def assign_table():
    """Admin assigns a tablet to a table or creates a new table."""
    data = request.json
    admin_pin = data.get('adminPin')
    
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    
    table_number = data.get('table_number')
    tablet_id = data.get('tablet_id', '')
    name = data.get('name', f"Table {table_number}")
    
    if not table_number:
        return jsonify({'message': 'Table number is required.'}), 400
    
    try:
        table_number = int(table_number)
        if table_number < 1:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'Table number must be a positive integer.'}), 400
    
    tables = load_json_data(TABLES_FILE)
    key = str(table_number)
    
    tables[key] = {
        'number': table_number,
        'name': name,
        'tablet_id': tablet_id,
        'status': 'available',
        'created_at': datetime.now().isoformat()
    }
    save_json_data(TABLES_FILE, tables)
    
    admin_user = load_json_data(USERS_FILE).get(admin_pin, {})
    log_activity('assign_table', admin_pin, admin_user.get('role', 'admin'), {
        'table_number': table_number,
        'tablet_id': tablet_id,
        'name': name
    })
    return jsonify({'message': f'Table {table_number} assigned successfully.', 'table': tables[key]})


@app.route('/api/tables/remove', methods=['POST'])
def remove_table():
    """Admin removes a table assignment."""
    data = request.json
    admin_pin = data.get('adminPin')
    
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    
    table_number = data.get('table_number')
    if not table_number:
        return jsonify({'message': 'Table number is required.'}), 400
    
    tables = load_json_data(TABLES_FILE)
    key = str(table_number)
    
    if key not in tables:
        return jsonify({'message': f'Table {table_number} not found.'}), 404
    
    del tables[key]
    save_json_data(TABLES_FILE, tables)
    
    admin_user = load_json_data(USERS_FILE).get(admin_pin, {})
    log_activity('remove_table', admin_pin, admin_user.get('role', 'admin'), {
        'table_number': table_number
    })
    return jsonify({'message': f'Table {table_number} removed successfully.'})


@app.route('/api/tables/tab/<int:table_number>', methods=['GET'])
def get_table_tab(table_number):
    """Returns the running tab for a table — all unpaid orders with their totals."""
    orders = load_json_data(ORDERS_FILE)
    table_orders = [o for o in orders if o.get('table_number') == table_number and o.get('status') in ('pending', 'preparing')]
    
    # Sort by date ascending
    table_orders.sort(key=lambda o: o.get('date', ''))
    
    tab_subtotal = 0
    tab_tax = 0
    tab_total = 0
    
    for o in table_orders:
        tab_subtotal += float(o.get('subtotal', 0))
        tab_tax += float(o.get('tax_amount', 0))
        tab_total += float(o.get('total', 0))
    
    return jsonify({
        'table_number': table_number,
        'orders': table_orders,
        'order_count': len(table_orders),
        'subtotal': round(tab_subtotal, 2),
        'tax': round(tab_tax, 2),
        'total': round(tab_total, 2)
    })


@app.route('/api/tables/tab/<int:table_number>/checkout', methods=['POST'])
def checkout_table_tab(table_number):
    """Closes out all active (pending/preparing) orders for a table — marks them as completed with payment info."""
    data = request.json
    user_id = data.get('userId', '')
    payment_method = data.get('payment', 'Cash')
    payment_splits = data.get('payment_splits')
    tip_amount = float(data.get('tip_amount', 0))
    notes = data.get('notes', '')

    if not user_id:
        return jsonify({'error': 'userId is required'}), 400

    orders = load_json_data(ORDERS_FILE)
    
    # Find all active orders for this table
    table_orders = []
    for order in orders:
        if order.get('table_number') == table_number and order.get('status') in ('pending', 'preparing'):
            table_orders.append(order)
    
    if not table_orders:
        return jsonify({'error': f'No active orders for table #{table_number}'}), 404
    
    now = datetime.now().isoformat()
    checkout_total = 0
    checkout_subtotal = 0
    checkout_tax = 0
    checkout_item_count = 0
    
    for order in table_orders:
        order['status'] = 'completed'
        order['completed_at'] = now
        order['tab_checkout'] = True
        order['tab_checkout_at'] = now
        order['tab_checkout_by'] = user_id
        if tip_amount > 0 and order.get('tip_amount', 0) == 0:
            order['tip_amount'] = round(tip_amount, 2)
            order['total'] = round(float(order.get('total', 0)) + tip_amount, 2)
        if payment_splits and isinstance(payment_splits, list) and len(payment_splits) > 0:
            order['payment_splits'] = payment_splits
            if len(payment_splits) == 1:
                order['payment'] = payment_splits[0]['method']
            else:
                parts = [f"{s['method']} ${float(s['amount']):.2f}" for s in payment_splits]
                order['payment'] = 'Split (' + ', '.join(parts) + ')'
        else:
            order['payment'] = payment_method
        order['tab_checkout_notes'] = notes
        checkout_subtotal += float(order.get('subtotal', 0))
        checkout_tax += float(order.get('tax_amount', 0))
        checkout_total += float(order.get('total', 0))
        checkout_item_count += len(order.get('items', []))
    
    save_json_data(ORDERS_FILE, orders)
    
    log_activity('tab_checkout', user_id, 'admin', {
        'table_number': table_number,
        'order_count': len(table_orders),
        'total': round(checkout_total, 2),
        'payment': payment_method
    })
    
    return jsonify({
        'message': f'Table #{table_number} tab closed successfully.',
        'table_number': table_number,
        'order_count': len(table_orders),
        'item_count': checkout_item_count,
        'subtotal': round(checkout_subtotal, 2),
        'tax': round(checkout_tax, 2),
        'total': round(checkout_total, 2),
        'payment': payment_method,
        'orders': [{'order_id': o['order_id'], 'status': o['status']} for o in table_orders]
    })


@app.route('/api/tables/tab/<int:table_number>/history', methods=['GET'])
def get_table_tab_history(table_number):
    """Returns completed/cancelled orders for a table (tab history)."""
    orders = load_json_data(ORDERS_FILE)
    table_orders = [o for o in orders if o.get('table_number') == table_number and o.get('status') in ('completed', 'cancelled')]
    
    # Sort by date descending (most recent first)
    table_orders.sort(key=lambda o: o.get('date', ''), reverse=True)
    
    history_total = sum(float(o.get('total', 0)) for o in table_orders)
    history_subtotal = sum(float(o.get('subtotal', 0)) for o in table_orders)
    history_tax = sum(float(o.get('tax_amount', 0)) for o in table_orders)
    
    return jsonify({
        'table_number': table_number,
        'orders': table_orders,
        'order_count': len(table_orders),
        'subtotal': round(history_subtotal, 2),
        'tax': round(history_tax, 2),
        'total': round(history_total, 2)
    })


# ============================================================
# Inventory Tracking System
# ============================================================


@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Returns all inventory data merged with item names from menu."""
    inventory = load_json_data(INVENTORY_FILE)
    items = load_json_data(ITEMS_FILE)
    
    # Build a lookup of all item names from menu
    menu_item_names = set()
    for cat, cat_items in items.items():
        for item in cat_items:
            menu_item_names.add(item['name'])
    
    # Auto-populate inventory for menu items that don't have an entry yet
    changed = False
    for item_name in menu_item_names:
        if item_name not in inventory:
            inventory[item_name] = {
                'stock': 0,
                'low_stock_threshold': 10
            }
            changed = True
    
    if changed:
        save_json_data(INVENTORY_FILE, inventory)
    
    return jsonify(inventory)


@app.route('/api/inventory/update', methods=['POST'])
def update_inventory():
    """Update stock or threshold for an item (admin only, manage_items)."""
    data = request.json
    admin_pin = data.get('adminPin')
    
    if not check_perm(admin_pin, "manage_items"):
        log_activity('update_inventory', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403
    
    item_name = data.get('item_name')
    stock = data.get('stock')
    low_stock_threshold = data.get('low_stock_threshold')
    
    if not item_name:
        return jsonify({'message': 'item_name is required.'}), 400
    
    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    
    inventory = load_json_data(INVENTORY_FILE)
    
    if item_name not in inventory:
        inventory[item_name] = {
            'stock': 0,
            'low_stock_threshold': 10
        }
    
    if stock is not None:
        try:
            stock = int(stock)
            if stock < 0:
                raise ValueError
            inventory[item_name]['stock'] = stock
        except (ValueError, TypeError):
            return jsonify({'message': 'Stock must be a non-negative integer.'}), 400
    
    if low_stock_threshold is not None:
        try:
            low_stock_threshold = int(low_stock_threshold)
            if low_stock_threshold < 0:
                raise ValueError
            inventory[item_name]['low_stock_threshold'] = low_stock_threshold
        except (ValueError, TypeError):
            return jsonify({'message': 'Low stock threshold must be a non-negative integer.'}), 400
    
    save_json_data(INVENTORY_FILE, inventory)
    log_activity('update_inventory', admin_pin, admin_role, {
        'item_name': item_name,
        'stock': inventory[item_name]['stock'],
        'low_stock_threshold': inventory[item_name]['low_stock_threshold']
    })
    return jsonify({
        'message': f'Inventory for "{item_name}" updated.',
        'inventory': inventory[item_name]
    })


@app.route('/api/inventory/low_stock', methods=['GET'])
def low_stock_alerts():
    """Returns items that are low on stock or out of stock."""
    inventory = load_json_data(INVENTORY_FILE)
    items = load_json_data(ITEMS_FILE)
    
    # Build item name -> category mapping
    item_categories = {}
    for cat, cat_items in items.items():
        for item in cat_items:
            if item['name'] not in item_categories:
                item_categories[item['name']] = cat
    
    low_stock_items = []
    for item_name, inv_data in inventory.items():
        stock = inv_data.get('stock', 0)
        threshold = inv_data.get('low_stock_threshold', 10)
        category = item_categories.get(item_name, '')
        
        if stock <= 0:
            low_stock_items.append({
                'item_name': item_name,
                'stock': stock,
                'threshold': threshold,
                'category': category,
                'status': 'out_of_stock'
            })
        elif stock <= threshold:
            low_stock_items.append({
                'item_name': item_name,
                'stock': stock,
                'threshold': threshold,
                'category': category,
                'status': 'low_stock'
            })
    
    return jsonify({'low_stock_items': low_stock_items})


# ============================================================
# Waste / Throwaway Tracking System
# ============================================================


@app.route('/api/waste/log', methods=['POST'])
def log_waste():
    """Log a waste/throwaway event (admin only, manage_items)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('log_waste', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    item_name = data.get('item_name', '').strip()
    quantity = data.get('quantity')
    reason = data.get('reason', '').strip()
    notes = data.get('notes', '').strip()

    if not item_name:
        return jsonify({'message': 'item_name is required.'}), 400
    if not reason:
        return jsonify({'message': 'reason is required.'}), 400
    try:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'quantity must be a positive integer.'}), 400

    valid_reasons = ['spoiled_expired', 'burned', 'spilled', 'damaged', 'overproduced', 'other']
    if reason not in valid_reasons:
        return jsonify({'message': f'reason must be one of: {", ".join(valid_reasons)}.'}), 400

    users_data = load_json_data(USERS_FILE)
    admin_user = users_data.get(admin_pin, {})
    admin_role = admin_user.get('role', 'unknown')

    # Look up item price from menu for cost estimation
    items_data = load_json_data(ITEMS_FILE)
    item_price = 0.0
    for cat, cat_items in items_data.items():
        for item in cat_items:
            if item['name'] == item_name:
                item_price = float(item.get('price', 0))
                break
        if item_price > 0:
            break

    waste_log = load_json_data(WASTE_FILE)
    entry = {
        'id': len(waste_log) + 1,
        'date': datetime.now().isoformat(),
        'item_name': item_name,
        'quantity': quantity,
        'reason': reason,
        'notes': notes,
        'logged_by': admin_pin,
        'logged_by_name': admin_user.get('name', 'Unknown'),
        'estimated_cost': round(item_price * quantity, 2),
        'item_price': item_price
    }
    waste_log.append(entry)
    save_json_data(WASTE_FILE, waste_log)

    log_activity('log_waste', admin_pin, admin_role, {
        'item_name': item_name,
        'quantity': quantity,
        'reason': reason,
        'estimated_cost': entry['estimated_cost'],
        'notes': notes
    })

    return jsonify({'message': 'Waste logged successfully.', 'entry': entry})


@app.route('/api/waste', methods=['POST'])
def get_waste_log():
    """Get waste log entries with optional date filtering (view_stats permission)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    waste_log = load_json_data(WASTE_FILE)

    # Date filtering
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            waste_log = [e for e in waste_log if datetime.fromisoformat(e.get('date', '')) >= dt_from]
        except (ValueError, KeyError):
            pass

    if date_to:
        try:
            if 'T' not in date_to:
                dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
            else:
                dt_to = datetime.fromisoformat(date_to)
            waste_log = [e for e in waste_log if datetime.fromisoformat(e.get('date', '')) <= dt_to]
        except (ValueError, KeyError):
            pass

    # Sort by date descending (most recent first)
    waste_log.sort(key=lambda e: e.get('date', ''), reverse=True)

    return jsonify({'waste_log': waste_log})


@app.route('/api/waste/summary', methods=['POST'])
def waste_summary():
    """Get aggregated waste summary (view_stats permission)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    waste_log = load_json_data(WASTE_FILE)

    total_items = sum(e.get('quantity', 0) for e in waste_log)
    total_cost = sum(e.get('estimated_cost', 0) for e in waste_log)
    total_entries = len(waste_log)

    # Breakdown by reason
    by_reason = {}
    for e in waste_log:
        r = e.get('reason', 'other')
        if r not in by_reason:
            by_reason[r] = {'count': 0, 'quantity': 0, 'cost': 0.0}
        by_reason[r]['count'] += 1
        by_reason[r]['quantity'] += e.get('quantity', 0)
        by_reason[r]['cost'] += e.get('estimated_cost', 0)

    # Breakdown by item
    by_item = {}
    for e in waste_log:
        name = e.get('item_name', '')
        if name not in by_item:
            by_item[name] = {'count': 0, 'quantity': 0, 'cost': 0.0}
        by_item[name]['count'] += 1
        by_item[name]['quantity'] += e.get('quantity', 0)
        by_item[name]['cost'] += e.get('estimated_cost', 0)

    # Top wasted items by cost
    top_items = sorted(by_item.items(), key=lambda x: x[1]['cost'], reverse=True)[:10]
    top_items_list = [{'item_name': name, 'quantity': v['quantity'], 'cost': round(v['cost'], 2), 'entries': v['count']} for name, v in top_items]

    return jsonify({
        'total_entries': total_entries,
        'total_items_wasted': total_items,
        'total_estimated_cost': round(total_cost, 2),
        'by_reason': {r: {'entries': v['count'], 'quantity': v['quantity'], 'cost': round(v['cost'], 2)} for r, v in by_reason.items()},
        'top_items': top_items_list
    })


# ============================================================
# Loyalty Points System
# ============================================================


@app.route('/api/loyalty/lookup', methods=['POST'])
def loyalty_lookup():
    """Look up a customer by phone number and return their loyalty data."""
    data = request.json
    phone = data.get('phone', '').strip()

    if not phone:
        return jsonify({'found': False, 'message': 'Phone number is required.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)

    if phone not in loyalty_data:
        return jsonify({'found': False, 'message': 'Customer not found. Please register first.'})

    return jsonify({
        'found': True,
        'customer': loyalty_data[phone]
    })


@app.route('/api/loyalty/register', methods=['POST'])
def loyalty_register():
    """Register a new customer for loyalty points."""
    data = request.json
    phone = data.get('phone', '').strip()
    name = data.get('name', '').strip()

    if not phone or not name:
        return jsonify({'message': 'Phone number and name are required.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)

    if phone in loyalty_data:
        return jsonify({'message': 'Customer with this phone number already exists.'}), 409

    loyalty_data[phone] = {
        'phone': phone,
        'name': name,
        'points': 0,
        'total_earned': 0,
        'total_redeemed': 0,
        'created_at': datetime.now().isoformat(),
        'history': []
    }

    save_json_data(LOYALTY_FILE, loyalty_data)

    log_activity('loyalty_register', data.get('adminPin', 'unknown'), 'admin', {
        'customer_phone': phone,
        'customer_name': name
    })

    return jsonify({'message': f'Customer {name} registered for loyalty points!', 'customer': loyalty_data[phone]})


@app.route('/api/loyalty/redeem', methods=['POST'])
def loyalty_redeem():
    """Redeem loyalty points for a discount. Returns the discount amount."""
    data = request.json
    phone = data.get('phone', '').strip()
    subtotal = float(data.get('subtotal', 0))

    if not phone:
        return jsonify({'message': 'Phone number is required.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)

    if phone not in loyalty_data:
        return jsonify({'message': 'Customer not found.'}), 404

    customer = loyalty_data[phone]
    points = customer.get('points', 0)

    # Calculate how many full redemption units they have
    units = points // LOYALTY_REDEEM_RATE
    if units == 0:
        return jsonify({
            'can_redeem': False,
            'message': f'Not enough points. {LOYALTY_REDEEM_RATE} points = ${LOYALTY_REDEEM_DISCOUNT:.2f} off. You have {points} points.',
            'points': points,
            'points_needed': LOYALTY_REDEEM_RATE
        })

    # Calculate max discount available
    max_discount = units * LOYALTY_REDEEM_DISCOUNT
    # Don't allow discount to exceed subtotal
    discount_amount = min(max_discount, subtotal)
    discount_amount = round(discount_amount, 2)

    # Calculate points to deduct
    points_to_deduct = int((discount_amount / LOYALTY_REDEEM_DISCOUNT) * LOYALTY_REDEEM_RATE)

    return jsonify({
        'can_redeem': True,
        'points': points,
        'points_to_deduct': points_to_deduct,
        'units': units,
        'discount_amount': discount_amount,
        'message': f'Redeem {points_to_deduct} points for ${discount_amount:.2f} off?'
    })


@app.route('/api/loyalty/confirm_redeem', methods=['POST'])
def loyalty_confirm_redeem():
    """Confirm the redemption: deduct points and return the discount code to apply."""
    data = request.json
    phone = data.get('phone', '').strip()
    points_to_deduct = int(data.get('points_to_deduct', 0))
    discount_amount = float(data.get('discount_amount', 0))
    order_id_used = data.get('order_id')

    if not phone or points_to_deduct <= 0:
        return jsonify({'message': 'Invalid redemption request.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)

    if phone not in loyalty_data:
        return jsonify({'message': 'Customer not found.'}), 404

    customer = loyalty_data[phone]
    if customer.get('points', 0) < points_to_deduct:
        return jsonify({'message': 'Insufficient points after confirmation. Points may have been used elsewhere.'}), 409

    # Deduct points
    customer['points'] -= points_to_deduct
    customer['total_redeemed'] += points_to_deduct
    customer['history'].append({
        'type': 'redeemed',
        'points': -points_to_deduct,
        'discount': round(discount_amount, 2),
        'order_id': order_id_used,
        'date': datetime.now().isoformat()
    })

    save_json_data(LOYALTY_FILE, loyalty_data)

    log_activity('loyalty_redeem', data.get('user', 'unknown'), 'user', {
        'customer_phone': phone,
        'points_deducted': points_to_deduct,
        'discount_amount': discount_amount,
        'order_id': order_id_used
    })

    return jsonify({
        'message': f'{points_to_deduct} points redeemed for ${discount_amount:.2f} off!',
        'remaining_points': customer['points'],
        'discount_amount': discount_amount
    })


@app.route('/api/loyalty/customers', methods=['GET'])
def loyalty_customers():
    """List all loyalty customers (admin only)."""
    admin_pin = request.args.get('adminPin', '')

    if not admin_pin or not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    loyalty_data = load_json_data(LOYALTY_FILE)

    customers = []
    for phone, data in loyalty_data.items():
        customers.append({
            'phone': data.get('phone', phone),
            'name': data.get('name', 'Unknown'),
            'points': data.get('points', 0),
            'total_earned': data.get('total_earned', 0),
            'total_redeemed': data.get('total_redeemed', 0),
            'created_at': data.get('created_at', '')
        })

    # Sort by points descending
    customers.sort(key=lambda c: c['points'], reverse=True)

    return jsonify({'customers': customers})


@app.route('/api/loyalty/adjust', methods=['POST'])
def loyalty_adjust():
    """Admin adjustment: add or remove points from a customer."""
    data = request.json
    admin_pin = data.get('adminPin', '')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    phone = data.get('phone', '').strip()
    points_adjust = int(data.get('points', 0))
    reason = data.get('reason', 'Admin adjustment')

    if not phone or points_adjust == 0:
        return jsonify({'message': 'Phone and non-zero points adjustment required.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)

    if phone not in loyalty_data:
        return jsonify({'message': 'Customer not found.'}), 404

    customer = loyalty_data[phone]
    customer['points'] += points_adjust
    if points_adjust > 0:
        customer['total_earned'] += points_adjust
    else:
        customer['total_redeemed'] += abs(points_adjust)

    customer['history'].append({
        'type': 'adjustment',
        'points': points_adjust,
        'reason': reason,
        'date': datetime.now().isoformat()
    })

    save_json_data(LOYALTY_FILE, loyalty_data)

    admin_user = load_json_data(USERS_FILE).get(admin_pin, {})
    admin_role = admin_user.get('role', 'unknown')
    log_activity('loyalty_adjust', admin_pin, admin_role, {
        'customer_phone': phone,
        'points_adjustment': points_adjust,
        'reason': reason
    })

    return jsonify({
        'message': f'Points adjusted by {points_adjust} for {customer["name"]}. New balance: {customer["points"]}.',
        'customer': customer
    })


# ============================================================
# Kiosk Order Lookup & Payment
# ============================================================


@app.route('/api/orders/lookup', methods=['GET'])
def order_lookup():
    """Look up an order by order_id or table_number (for kiosk payment)."""
    order_id = request.args.get('order_id', type=int)
    table_number = request.args.get('table_number', type=int)

    if order_id is None and table_number is None:
        return jsonify({'error': 'Provide order_id or table_number'}), 400

    orders = load_json_data(ORDERS_FILE)

    if order_id is not None:
        for order in orders:
            if order.get('order_id') == order_id:
                # Don't allow re-paying already-paid or cancelled orders
                if order.get('status') == 'cancelled':
                    return jsonify({'found': False, 'message': f'Order #{order_id} was cancelled.'}), 404
                if order.get('kiosk_paid'):
                    return jsonify({'found': False, 'message': f'Order #{order_id} has already been paid.'}), 404
                return jsonify({'order': order, 'found': True})
        return jsonify({'found': False, 'message': f'Order #{order_id} not found'}), 404

    # Lookup by table number — return unpaid orders
    table_orders = [
        o for o in orders
        if o.get('table_number') == table_number
        and o.get('status') != 'cancelled'
        and not o.get('kiosk_paid')
    ]
    if not table_orders:
        return jsonify({
            'found': False,
            'message': f'No unpaid orders found for Table {table_number}',
            'orders': []
        }), 404

    return jsonify({
        'found': True,
        'orders': table_orders,
        'table_number': table_number,
        'order_count': len(table_orders)
    })


@app.route('/api/orders/kiosk_pay', methods=['POST'])
def kiosk_pay():
    """Pay for an existing order from kiosk mode. Adds tip and payment info."""
    data = request.json
    order_id = data.get('order_id')
    payment_splits = data.get('payment_splits', [])
    tip_amount = float(data.get('tip_amount', 0))
    user_id = data.get('user', 'kiosk')

    if order_id is None:
        return jsonify({'message': 'order_id is required'}), 400

    orders = load_json_data(ORDERS_FILE)

    for order in orders:
        if order.get('order_id') == order_id:
            if order.get('status') == 'cancelled':
                return jsonify({'message': f'Order #{order_id} was cancelled.'}), 409
            if order.get('kiosk_paid'):
                return jsonify({'message': f'Order #{order_id} has already been paid.'}), 409

            # Update payment info
            order['payment_splits'] = payment_splits if payment_splits else order.get('payment_splits')
            order['tip_amount'] = float(order.get('tip_amount', 0)) + tip_amount
            order['kiosk_paid'] = True
            order['kiosk_paid_at'] = datetime.now().isoformat()
            order['kiosk_paid_by'] = user_id

            # Build payment display string
            if payment_splits and isinstance(payment_splits, list) and len(payment_splits) > 0:
                if len(payment_splits) == 1:
                    order['payment'] = payment_splits[0]['method']
                else:
                    parts = [f"{s['method']} ${float(s['amount']):.2f}" for s in payment_splits]
                    order['payment'] = 'Split (' + ', '.join(parts) + ')'

            # Add tip to total
            old_total = float(order.get('total', 0))
            order['total'] = round(old_total + tip_amount, 2)

            save_json_data(ORDERS_FILE, orders)

            log_activity('kiosk_pay', user_id, 'kiosk', {
                'order_id': order_id,
                'payment_splits': payment_splits,
                'tip_amount': tip_amount,
                'total': order['total']
            })

            return jsonify({
                'message': 'Payment successful',
                'order_id': order_id,
                'total': order['total'],
                'order_number': order_id
            })

    return jsonify({'message': f'Order #{order_id} not found'}), 404


# ============================================================
# CSV Export Endpoints
# ============================================================


def generate_csv(rows, headers):
    """Generate CSV string from a list of dicts with given headers."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, '') for h in headers])
    result = output.getvalue()
    output.close()
    return result


@app.route('/api/employee_performance', methods=['POST'])
def employee_performance():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users_data = load_json_data(USERS_FILE)
    orders = load_json_data(ORDERS_FILE)

    # --- Date range filtering ---
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()

    def filter_by_date_range(order_list, date_field='date'):
        filtered = order_list
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                filtered = [o for o in filtered if datetime.fromisoformat(o.get(date_field, '')) >= dt_from]
            except (ValueError, KeyError):
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                filtered = [o for o in filtered if datetime.fromisoformat(o.get(date_field, '')) <= dt_to]
            except (ValueError, KeyError):
                pass
        return filtered

    orders = filter_by_date_range(orders)

    # Track per-employee metrics: user_id -> {orders, revenue, tips, items_count}
    employee_data = {}

    for order in orders:
        # Skip refunded/voided orders
        if order.get('status') in ('refunded', 'voided'):
            continue

        user_id = order.get('user', '')
        if not user_id:
            continue

        if user_id not in employee_data:
            employee_data[user_id] = {
                'orders_count': 0,
                'total_revenue': 0.0,
                'total_tips': 0.0,
                'item_count': 0
            }

        try:
            total = float(order.get('total', 0))
            tip = float(order.get('tip_amount', 0))
            items_list = order.get('items', [])
            items_qty = sum(int(i.get('qty', 1)) for i in items_list)

            employee_data[user_id]['orders_count'] += 1
            employee_data[user_id]['total_revenue'] += total
            employee_data[user_id]['total_tips'] += tip
            employee_data[user_id]['item_count'] += items_qty
        except (ValueError, TypeError):
            continue

    # Build response array sorted by revenue (descending)
    result = []
    for uid, metrics in employee_data.items():
        user_info = users_data.get(uid, {})
        user_info = upgrade_user(user_info)
        avg_order = metrics['total_revenue'] / metrics['orders_count'] if metrics['orders_count'] > 0 else 0

        result.append({
            'user_id': uid,
            'user_name': user_info.get('name', 'Unknown'),
            'user_role': user_info.get('role', 'unknown'),
            'orders_count': metrics['orders_count'],
            'total_revenue': round(metrics['total_revenue'], 2),
            'average_order_value': round(avg_order, 2),
            'total_tips': round(metrics['total_tips'], 2),
            'items_sold': metrics['item_count']
        })

    # Sort by total revenue descending
    result.sort(key=lambda x: x['total_revenue'], reverse=True)

    return jsonify({
        'message': 'Employee performance data retrieved',
        'employees': result
    })


@app.route('/api/export/orders_csv', methods=['POST'])
def export_orders_csv():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    orders = load_json_data(ORDERS_FILE)
    headers = ['Order ID', 'Date', 'User', 'Items', 'Subtotal', 'Tax Amount',
               'Tip Amount', 'Discount Amount', 'Total', 'Payment', 'Status', 'Notes', 'Table']

    rows = []
    for order in orders:
        items_str = '; '.join([
            f"{i.get('name', '')} x{i.get('qty', 1)}"
            for i in order.get('items', [])
        ])
        rows.append({
            'Order ID': order.get('order_id', ''),
            'Date': order.get('date', ''),
            'User': order.get('user', ''),
            'Items': items_str,
            'Subtotal': order.get('subtotal', 0),
            'Tax Amount': order.get('tax_amount', 0),
            'Tip Amount': order.get('tip_amount', 0),
            'Discount Amount': order.get('discount_amount', 0),
            'Total': order.get('total', 0),
            'Payment': order.get('payment', ''),
            'Status': order.get('status', ''),
            'Notes': order.get('notes', ''),
            'Table': order.get('table_number', '')
        })

    csv_content = generate_csv(rows, headers)
    return jsonify({'csv': csv_content, 'filename': 'orders_export.csv'})


@app.route('/api/export/timesheet_csv', methods=['POST'])
def export_timesheet_csv():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    timesheet = load_json_data(TIMESHEET_FILE)
    headers = ['User ID', 'Login Time', 'Logout Time', 'Duration (Hours)']

    rows = []
    for entry in timesheet:
        rows.append({
            'User ID': entry.get('user_id', ''),
            'Login Time': entry.get('login_time', ''),
            'Logout Time': entry.get('logout_time', ''),
            'Duration (Hours)': entry.get('duration_hours', 0)
        })

    csv_content = generate_csv(rows, headers)
    return jsonify({'csv': csv_content, 'filename': 'timesheet_export.csv'})


@app.route('/api/export/activity_log_csv', methods=['POST'])
def export_activity_log_csv():
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_logs"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    logs = load_json_data(ACTIVITY_LOG_FILE)
    headers = ['Timestamp', 'Type', 'User ID', 'User Role', 'Details']

    rows = []
    for log in logs:
        details = log.get('details', {})
        details_str = json.dumps(details) if details else ''
        rows.append({
            'Timestamp': log.get('timestamp', ''),
            'Type': log.get('type', ''),
            'User ID': log.get('user_id', ''),
            'User Role': log.get('user_role', ''),
            'Details': details_str
        })

    csv_content = generate_csv(rows, headers)
    return jsonify({'csv': csv_content, 'filename': 'activity_log_export.csv'})


# ============================================================
# Webhook Integration Endpoints
# ============================================================

@app.route('/api/webhooks', methods=['GET'])
def get_webhooks():
    """List all configured webhooks. Requires manage_items permission."""
    data = request.json if request.is_json else {}
    admin_pin = data.get('adminPin', request.args.get('adminPin', ''))
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    webhooks = load_json_data(WEBHOOKS_FILE)
    if not isinstance(webhooks, dict):
        webhooks = {}
    return jsonify({'message': 'Webhooks retrieved', 'webhooks': webhooks})


@app.route('/api/webhooks', methods=['POST'])
def add_webhook():
    """Add a new webhook URL. Requires manage_items permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    url = data.get('url', '').strip()
    name = data.get('name', '').strip()

    if not url:
        return jsonify({'message': 'URL is required.'}), 400
    if not url.startswith('http://') and not url.startswith('https://'):
        return jsonify({'message': 'URL must start with http:// or https://'}), 400
    if not name:
        name = url

    webhooks = load_json_data(WEBHOOKS_FILE)
    if not isinstance(webhooks, dict):
        webhooks = {}

    wh_id = str(int(datetime.now().timestamp()))
    webhooks[wh_id] = {
        'id': wh_id,
        'url': url,
        'name': name,
        'enabled': True,
        'created_at': datetime.now().isoformat()
    }
    save_json_data(WEBHOOKS_FILE, webhooks)

    log_activity('webhook_add', admin_pin, 'admin', {'name': name, 'url': url})

    return jsonify({'message': 'Webhook added successfully', 'webhook': webhooks[wh_id]})


@app.route('/api/webhooks/<wh_id>', methods=['DELETE'])
def delete_webhook(wh_id):
    """Delete a webhook. Requires manage_items permission."""
    data = request.json if request.is_json else {}
    admin_pin = data.get('adminPin', request.args.get('adminPin', ''))
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    webhooks = load_json_data(WEBHOOKS_FILE)
    if not isinstance(webhooks, dict) or wh_id not in webhooks:
        return jsonify({'message': 'Webhook not found.'}), 404

    removed = webhooks.pop(wh_id)
    save_json_data(WEBHOOKS_FILE, webhooks)

    log_activity('webhook_delete', admin_pin, 'admin', {'name': removed.get('name'), 'url': removed.get('url')})

    return jsonify({'message': 'Webhook deleted successfully'})


@app.route('/api/webhooks/<wh_id>/toggle', methods=['POST'])
def toggle_webhook(wh_id):
    """Enable/disable a webhook. Requires manage_items permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    webhooks = load_json_data(WEBHOOKS_FILE)
    if not isinstance(webhooks, dict) or wh_id not in webhooks:
        return jsonify({'message': 'Webhook not found.'}), 404

    webhooks[wh_id]['enabled'] = not webhooks[wh_id].get('enabled', True)
    save_json_data(WEBHOOKS_FILE, webhooks)

    status = 'enabled' if webhooks[wh_id]['enabled'] else 'disabled'
    log_activity('webhook_toggle', admin_pin, 'admin', {'name': webhooks[wh_id].get('name'), 'status': status})

    return jsonify({'message': f'Webhook {status}', 'webhook': webhooks[wh_id]})


@app.route('/api/webhooks/<wh_id>/test', methods=['POST'])
def test_webhook(wh_id):
    """Send a test payload to a webhook. Requires manage_items permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    webhooks = load_json_data(WEBHOOKS_FILE)
    if not isinstance(webhooks, dict) or wh_id not in webhooks:
        return jsonify({'message': 'Webhook not found.'}), 404

    wh = webhooks[wh_id]
    test_payload = {
        'event': 'test',
        'timestamp': datetime.now().isoformat(),
        'data': {'message': 'This is a test from POS System'}
    }

    try:
        payload = json.dumps(test_payload).encode('utf-8')
        req = urllib.request.Request(wh['url'], data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST')
        urllib.request.urlopen(req, timeout=10)
        return jsonify({'message': 'Test webhook sent successfully'})
    except urllib.error.HTTPError as e:
        return jsonify({'message': f'HTTP error: {e.code} {e.reason}'}), 400
    except urllib.error.URLError as e:
        return jsonify({'message': f'Connection error: {e.reason}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error: {str(e)}'}), 400


# ============================================================
# Table-side Ads System
# ============================================================

@app.route('/api/ads', methods=['GET'])
def get_ads():
    """List all ads. Requires manage_items permission."""
    data = load_json_data(TABLE_ADS_FILE)
    return jsonify(data)


@app.route('/api/ads/add', methods=['POST'])
def add_ad():
    """Add a new ad. Requires manage_items permission."""
    req = request.json
    admin_pin = req.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    title = req.get('title', '').strip()
    image_url = req.get('image_url', '').strip()
    link_url = req.get('link_url', '').strip()
    duration = int(req.get('duration', 10))

    if not title or not image_url:
        return jsonify({'message': 'Title and image URL are required.'}), 400

    ads_data = load_json_data(TABLE_ADS_FILE)
    if not isinstance(ads_data, dict):
        ads_data = {"ads": [], "rotation_interval": 10}
    
    ad_id = str(secrets.token_hex(4))
    new_ad = {
        'id': ad_id,
        'title': title,
        'image_url': image_url,
        'link_url': link_url,
        'duration': max(5, min(60, duration)),  # 5-60 seconds
        'active': True,
        'created_at': datetime.now().isoformat()
    }
    ads_data['ads'].append(new_ad)
    save_json_data(TABLE_ADS_FILE, ads_data)

    log_activity('ad_add', admin_pin, 'admin', {'title': title})
    return jsonify({'message': 'Ad added successfully', 'ad': new_ad})


@app.route('/api/ads/<ad_id>/update', methods=['PUT'])
def update_ad(ad_id):
    """Update an ad. Requires manage_items permission."""
    req = request.json
    admin_pin = req.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    ads_data = load_json_data(TABLE_ADS_FILE)
    if not isinstance(ads_data, dict):
        return jsonify({'message': 'No ads data.'}), 404

    found = None
    for ad in ads_data.get('ads', []):
        if ad.get('id') == ad_id:
            found = ad
            break

    if not found:
        return jsonify({'message': 'Ad not found.'}), 404

    if 'title' in req and req['title'].strip():
        found['title'] = req['title'].strip()
    if 'image_url' in req and req['image_url'].strip():
        found['image_url'] = req['image_url'].strip()
    if 'link_url' in req:
        found['link_url'] = req['link_url'].strip()
    if 'duration' in req:
        found['duration'] = max(5, min(60, int(req['duration'])))

    save_json_data(TABLE_ADS_FILE, ads_data)
    log_activity('ad_update', admin_pin, 'admin', {'ad_id': ad_id, 'title': found['title']})
    return jsonify({'message': 'Ad updated successfully', 'ad': found})


@app.route('/api/ads/<ad_id>/toggle', methods=['POST'])
def toggle_ad(ad_id):
    """Toggle ad active/inactive. Requires manage_items permission."""
    req = request.json
    admin_pin = req.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    ads_data = load_json_data(TABLE_ADS_FILE)
    if not isinstance(ads_data, dict):
        return jsonify({'message': 'No ads data.'}), 404

    found = None
    for ad in ads_data.get('ads', []):
        if ad.get('id') == ad_id:
            found = ad
            break

    if not found:
        return jsonify({'message': 'Ad not found.'}), 404

    found['active'] = not found.get('active', True)
    save_json_data(TABLE_ADS_FILE, ads_data)

    status = 'enabled' if found['active'] else 'disabled'
    log_activity('ad_toggle', admin_pin, 'admin', {'ad_id': ad_id, 'status': status})
    return jsonify({'message': f'Ad {status}', 'ad': found})


@app.route('/api/ads/<ad_id>/delete', methods=['DELETE'])
def delete_ad(ad_id):
    """Delete an ad. Requires manage_items permission."""
    req = request.json if request.is_json else {}
    admin_pin = req.get('adminPin', request.args.get('adminPin', ''))
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    ads_data = load_json_data(TABLE_ADS_FILE)
    if not isinstance(ads_data, dict):
        return jsonify({'message': 'No ads data.'}), 404

    ads_list = ads_data.get('ads', [])
    found = None
    for ad in ads_list:
        if ad.get('id') == ad_id:
            found = ad
            break

    if not found:
        return jsonify({'message': 'Ad not found.'}), 404

    ads_data['ads'] = [a for a in ads_list if a.get('id') != ad_id]
    save_json_data(TABLE_ADS_FILE, ads_data)

    log_activity('ad_delete', admin_pin, 'admin', {'title': found.get('title')})
    return jsonify({'message': 'Ad deleted successfully'})


@app.route('/api/ads/interval', methods=['POST'])
def set_ads_interval():
    """Set the global rotation interval. Requires manage_items permission."""
    req = request.json
    admin_pin = req.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    interval = int(req.get('interval', 10))
    interval = max(5, min(120, interval))

    ads_data = load_json_data(TABLE_ADS_FILE)
    if not isinstance(ads_data, dict):
        ads_data = {"ads": [], "rotation_interval": 10}
    ads_data['rotation_interval'] = interval
    save_json_data(TABLE_ADS_FILE, ads_data)

    return jsonify({'message': f'Rotation interval set to {interval}s', 'interval': interval})


@app.route('/api/ads/current')
def get_current_ad():
    """Return the currently active ads for table tablets to display."""
    ads_data = load_json_data(TABLE_ADS_FILE)
    if not isinstance(ads_data, dict):
        return jsonify({'ads': [], 'interval': 10})

    active_ads = [a for a in ads_data.get('ads', []) if a.get('active', True)]
    interval = ads_data.get('rotation_interval', 10)

    return jsonify({
        'ads': active_ads,
        'interval': interval,
        'total': len(active_ads)
    })


# ============================================================
# Serve the frontend
# ============================================================

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/drivethrough')
def serve_drivethrough():
    return send_from_directory(app.static_folder, 'drivethrough.html')


@app.route('/customer-display')
def serve_customer_display():
    return send_from_directory(app.static_folder, 'customer-display.html')


@app.route('/tablet')
def serve_tablet():
    """Serve the table-side ad display page for table tablets."""
    return send_from_directory(app.static_folder, 'tablet.html')


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)

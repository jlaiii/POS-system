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
CASH_DRAWER_FILE = 'cash_drawer.json'  # Cash register management
COMBOS_FILE = 'combos.json'  # Combo/meal deal bundles
SERVICE_CHARGE_FILE = 'service_charge_config.json'  # Auto-gratuity / service charge settings
EMAIL_CONFIG_FILE = 'email_config.json'  # Email/SMTP configuration for digital receipts
SHIFT_FILE = 'shift_log.json'  # Employee shift clock-in/clock-out records

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
for f in [USERS_FILE, ORDERS_FILE, CLEARED_ORDERS_FILE, ACTIVITY_LOG_FILE, TIMESHEET_FILE, ITEMS_FILE, TAX_CONFIG_FILE, DISCOUNTS_FILE, ORDER_COUNTER_FILE, TABLES_FILE, INVENTORY_FILE, REFUNDED_ORDERS_FILE, FAVORITES_FILE, LOYALTY_FILE, SCHEDULED_PRICING_FILE, WASTE_FILE, DELIVERY_ADDRESSES_FILE, WEBHOOKS_FILE, TABLE_ADS_FILE, CASH_DRAWER_FILE, COMBOS_FILE, SERVICE_CHARGE_FILE, EMAIL_CONFIG_FILE, SHIFT_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as file:
            if f == USERS_FILE:
                json.dump({"1111": {"name": "Owner", "role": "owner", "permissions": ["*"]}}, file)
            elif f == TIMESHEET_FILE or f == ACTIVITY_LOG_FILE or f == SHIFT_FILE:
                json.dump([], file)  # Initialize as empty lists
            elif f == ITEMS_FILE:
                json.dump({
                    "Foods": [
                        {"name": "Hamburger - Normal", "price": 6, "barcode": "", "image_url": ""},
                        {"name": "Hamburger - All the Fixings", "price": 8, "barcode": "", "image_url": ""},
                        {"name": "Hotdog - Loaded", "price": 7, "barcode": "", "image_url": ""},
                        {"name": "Hotdog - Plain", "price": 5, "barcode": "", "image_url": ""},
                        {"name": "Taco - Beef & Cheese", "price": 7, "barcode": "", "image_url": ""},
                        {"name": "Taco - Chicken with Salsa", "price": 7, "barcode": "", "image_url": ""}
                    ],
                    "Drinks": [
                        {"name": "Lemonade", "price": 3, "barcode": "", "image_url": ""},
                        {"name": "Coke", "price": 3, "barcode": "", "image_url": ""},
                        {"name": "Water Bottle", "price": 2, "barcode": "", "image_url": ""}
                    ],
                    "Snacks": [
                        {"name": "Raspia (Fruit Slush)", "price": 4, "barcode": "", "image_url": ""},
                        {"name": "Chips (Large Bag)", "price": 3, "barcode": "", "image_url": ""},
                        {"name": "Chocolate Bar", "price": 2, "barcode": "", "image_url": ""},
                        {"name": "Mixed Nuts (Small Pack)", "price": 4, "barcode": "", "image_url": ""},
                        {"name": "Granola Bar", "price": 2, "barcode": "", "image_url": ""}
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
            elif f == CASH_DRAWER_FILE:
                json.dump({"sessions": [], "transactions": []}, file, indent=4)  # Initialize cash drawer
            elif f == COMBOS_FILE:
                json.dump({"combos": []}, file, indent=4)  # Initialize combos
            elif f == SERVICE_CHARGE_FILE:
                json.dump({"enabled": True, "threshold": 8, "percentage": 18.0, "label": "Auto-Gratuity (18%)"}, file, indent=4)  # Initialize service charge config
            elif f == EMAIL_CONFIG_FILE:
                json.dump({"server": "", "port": 587, "username": "", "password": "", "from_addr": "", "use_tls": True, "enabled": False}, file, indent=4)  # Initialize email config
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
PICKUP_ROOM = 'pickup'


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


@socketio.on('join_pickup')
def handle_join_pickup():
    """Pickup display page joins the pickup room."""
    join_room(PICKUP_ROOM)


@socketio.on('leave_pickup')
def handle_leave_pickup():
    """Pickup display page leaves the pickup room."""
    leave_room(PICKUP_ROOM)


def emit_kitchen_update():
    """Broadcast to kitchen room that order state changed."""
    socketio.emit('kitchen_update', {}, room=KITCHEN_ROOM)


def emit_customer_update():
    """Broadcast to customer display room that display state changed."""
    socketio.emit('customer_update', {}, room=CUSTOMER_ROOM)


def emit_drivethrough_update():
    """Broadcast to drive-through room that display state changed."""
    socketio.emit('drivethrough_update', {}, room=DRIVETHROUGH_ROOM)


def emit_pickup_update():
    """Broadcast to pickup display room that pickup state changed."""
    socketio.emit('pickup_update', {}, room=PICKUP_ROOM)


# In-memory storage for active admin sessions (for timesheet calculation)
active_admin_sessions = {}  # {admin_id: login_time}

# In-memory storage for employee clock-in/clock-out shifts
active_shifts = {}  # {user_id: {clock_in_time: datetime, user_name: str}}

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

    items_data[category].append({"name": name, "price": price, "barcode": data.get('barcode', ''), "image_url": data.get('image_url', ''), "course": data.get('course', 'main'), "active": True})
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
                # Preserve image_url from old item
                old_image_url = items_data[old_category][i].get('image_url', '')
                old_barcode = items_data[old_category][i].get('barcode', '')
                old_course = item.get('course', 'main')
                old_active = item.get('active', True)
                items_data[new_category].append({"name": new_name, "price": new_price, "barcode": data.get('barcode', old_barcode), "image_url": data.get('image_url', old_image_url), "course": data.get('course', old_course), "active": old_active})
            else:  # Only name/price/barcode changing within same category
                items_data[old_category][i]["name"] = new_name
                items_data[old_category][i]["price"] = new_price
                if 'barcode' in data and data.get('barcode') is not None:
                    items_data[old_category][i]["barcode"] = data.get('barcode', '')
                if 'image_url' in data and data.get('image_url') is not None:
                    items_data[old_category][i]["image_url"] = data.get('image_url', '')
                if 'course' in data and data.get('course') is not None:
                    items_data[old_category][i]["course"] = data.get('course', 'main')
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
            if item.get('active', True) is False:
                continue
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


@app.route('/api/items/set_image', methods=['POST'])
def set_item_image():
    """Set or update the image URL for an existing item."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    category = data.get('category')
    name = data.get('name')
    image_url = data.get('image_url', '').strip()

    if not all([category, name]):
        return jsonify({'message': 'Category and name are required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        return jsonify({'message': f'Category "{category}" not found.'}), 404

    found = False
    for item in items_data[category]:
        if item['name'] == name:
            item['image_url'] = image_url
            found = True
            break

    if not found:
        return jsonify({'message': f'Item "{name}" not found in category "{category}".'}), 404

    save_json_data(ITEMS_FILE, items_data)
    backup_menu()
    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('set_item_image', admin_pin, admin_role, {'category': category, 'name': name, 'image_url': image_url})
    return jsonify({'message': 'Image URL updated successfully'})


@app.route('/api/items/toggle_visibility', methods=['POST'])
def toggle_item_visibility():
    """Toggle the active/inactive state of a menu item. Inactive items don't appear in POS/kiosk."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    category = data.get('category')
    name = data.get('name')

    if not all([category, name]):
        return jsonify({'message': 'Category and name are required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        return jsonify({'message': f'Category "{category}" not found.'}), 404

    found = False
    for item in items_data[category]:
        if item['name'] == name:
            current = item.get('active', True)
            item['active'] = not current
            found = True
            new_state = item['active']
            break

    if not found:
        return jsonify({'message': f'Item "{name}" not found in category "{category}".'}), 404

    save_json_data(ITEMS_FILE, items_data)
    backup_menu()
    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('toggle_item_visibility', admin_pin, admin_role, {
        'category': category, 'name': name, 'new_active': new_state
    })
    return jsonify({'message': 'Item visibility toggled', 'active': new_state})


# --- Item Modifier Support Endpoints ---

@app.route('/api/items/modifiers/save', methods=['POST'])
def save_item_modifiers():
    """Save modifier groups for an item. Each group has name, type (single/multiple), and options list."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    category = data.get('category')
    name = data.get('name')
    modifier_groups = data.get('modifiers', [])

    if not category or not name:
        return jsonify({'message': 'Category and item name are required.'}), 400

    # Validate modifier structure
    if not isinstance(modifier_groups, list):
        return jsonify({'message': 'Modifiers must be an array of groups.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        return jsonify({'message': f'Category "{category}" not found.'}), 404

    clean_groups = []
    found = False
    for item in items_data[category]:
        if item['name'] == name:
            # Save validated modifier groups
            for group in modifier_groups:
                clean_group = {
                    'name': str(group.get('name', '')).strip(),
                    'type': 'single' if str(group.get('type', 'single')) not in ('single', 'multiple') else str(group.get('type')),
                    'options': []
                }
                if not clean_group['name']:
                    continue
                for opt in group.get('options', []):
                    opt_name = str(opt.get('name', '')).strip()
                    if not opt_name:
                        continue
                    try:
                        price_mod = float(opt.get('price_mod', 0))
                    except (ValueError, TypeError):
                        price_mod = 0.0
                    clean_group['options'].append({
                        'name': opt_name,
                        'price_mod': price_mod
                    })
                if clean_group['options']:
                    clean_groups.append(clean_group)
            item['modifiers'] = {'groups': clean_groups}
            found = True
            break

    if not found:
        return jsonify({'message': f'Item "{name}" not found in category "{category}".'}), 404

    save_json_data(ITEMS_FILE, items_data)
    backup_menu()

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('save_item_modifiers', admin_pin, admin_role, {
        'category': category, 'name': name, 'groups_count': len(clean_groups)
    })
    return jsonify({'message': 'Modifiers saved successfully', 'item': {'category': category, 'name': name}})


@app.route('/api/items/modifiers/get', methods=['POST'])
def get_item_modifiers():
    """Get modifier groups for a specific item."""
    data = request.json
    category = data.get('category')
    name = data.get('name')

    if not category or not name:
        return jsonify({'message': 'Category and item name are required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        return jsonify({'message': f'Category "{category}" not found.'}), 404

    for item in items_data[category]:
        if item['name'] == name:
            modifiers = item.get('modifiers', {})
            return jsonify({'modifiers': modifiers.get('groups', [])})

    return jsonify({'message': f'Item "{name}" not found.'}), 404


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
    service_charge_amount = float(data.get('service_charge_amount', 0))

    # Accept total from frontend, or compute as subtotal + tax + tip + service charge
    total_from_request = data.get('total')
    if total_from_request is not None:
        total = float(total_from_request)
    else:
        total = subtotal + tax_amount + tip_amount + service_charge_amount

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
        'service_charge_amount': round(service_charge_amount, 2),
        'discount_code': data.get('discount_code'),
        'discount_amount': round(float(data.get('discount_amount', 0)), 2),
        'total': round(total, 2),
        'notes': data.get('notes', ''),  # Per-order special instructions
        'item_notes': data.get('item_notes', {}),  # Per-item notes {index: note_string}
        'table_number': data.get('table_number'),  # Table number for table management
        'delivery_address': data.get('delivery_address'),  # Delivery address info
        'customer_email': data.get('customer_email', '')  # Email for digital receipt delivery
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
        # If item is a combo, decrement child items instead
        if item.get('is_combo') and item.get('child_items'):
            for ci in item['child_items']:
                ci_name = ci.get('name', '')
                ci_qty = int(ci.get('qty', 1)) * int(item.get('qty', 1))
                if ci_name in inventory:
                    current_stock = inventory[ci_name].get('stock', 0)
                    new_stock = max(0, current_stock - ci_qty)
                    inventory[ci_name]['stock'] = new_stock
                    threshold = inventory[ci_name].get('low_stock_threshold', 10)
                    if new_stock <= 0:
                        low_stock_warnings.append({'item_name': ci_name, 'stock': new_stock, 'status': 'out_of_stock'})
                    elif new_stock <= threshold:
                        low_stock_warnings.append({'item_name': ci_name, 'stock': new_stock, 'status': 'low_stock', 'threshold': threshold})
            continue
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
        if customer_phone not in loyalty_data:
            # Auto-create a minimal record for spending tracking
            loyalty_data[customer_phone] = {
                'phone': customer_phone,
                'name': customer_phone,
                'email': '',
                'notes': '',
                'address': '',
                'points': 0,
                'total_earned': 0,
                'total_redeemed': 0,
                'total_spent': 0.0,
                'total_orders': 0,
                'last_visit': '',
                'created_at': datetime.now().isoformat(),
                'history': []
            }
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
        # Track total spending and visit
        loyalty_data[customer_phone]['total_spent'] = round(loyalty_data[customer_phone].get('total_spent', 0) + subtotal, 2)
        loyalty_data[customer_phone]['total_orders'] = loyalty_data[customer_phone].get('total_orders', 0) + 1
        loyalty_data[customer_phone]['last_visit'] = datetime.now().isoformat()
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
        service_charge_amount = float(order_data.get('service_charge_amount', 0))

        total_from_request = order_data.get('total')
        if total_from_request is not None:
            total = float(total_from_request)
        else:
            total = subtotal + tax_amount + tip_amount + service_charge_amount

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
            'service_charge_amount': round(service_charge_amount, 2),
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


@app.route('/api/orders/recent', methods=['POST'])
def orders_recent():
    """Return the last 5 orders for the logged-in user (waiter)."""
    data = request.json
    admin_pin = data.get('adminPin')

    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'User not found.'}), 403

    user_info = upgrade_user(users[admin_pin])
    if user_info.get('banned', False):
        return jsonify({'message': 'User is banned.'}), 403

    username = user_info.get('name', '')

    orders = load_json_data(ORDERS_FILE)
    cleared_orders = load_json_data(CLEARED_ORDERS_FILE)

    # Filter by this user's orders (user field stores the PIN/id)
    user_orders = [o for o in orders if str(o.get('user', '')) == str(admin_pin)]
    user_cleared = [o for o in cleared_orders if str(o.get('user', '')) == str(admin_pin)]

    # Merge and sort by date descending
    all_user_orders = user_orders + user_cleared
    all_user_orders.sort(key=lambda o: o.get('date', ''), reverse=True)

    # Take last 5
    recent = all_user_orders[:5]

    return jsonify({
        'message': 'Recent orders retrieved',
        'orders': recent
    })


# --- Email / SMTP Config Endpoints ---

@app.route('/api/email/config', methods=['GET'])
def get_email_config():
    """Get the current SMTP email configuration."""
    config = load_json_data(EMAIL_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {"server": "", "port": 587, "username": "", "password": "", "from_addr": "", "use_tls": True, "enabled": False}
    # Never expose the password in full
    safe_config = dict(config)
    if safe_config.get('password'):
        safe_config['password'] = '••••••••'
    return jsonify(safe_config)


@app.route('/api/email/config', methods=['POST'])
def save_email_config():
    """Save SMTP email configuration. Requires manage_items permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not admin_pin:
        return jsonify({'message': 'Authentication required'}), 403

    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'Invalid user'}), 403
    user_info = users[admin_pin]
    user_info = upgrade_user(user_info)
    perms = user_info.get('permissions', [])
    if '*' not in perms and 'manage_items' not in perms:
        return jsonify({'message': 'Permission denied'}), 403

    config = load_json_data(EMAIL_CONFIG_FILE)
    # If config is a list (file didn't exist or wrong format), start fresh
    if not isinstance(config, dict):
        config = {"server": "", "port": 587, "username": "", "password": "", "from_addr": "", "use_tls": True, "enabled": False}
    if 'server' in data:
        config['server'] = str(data['server']).strip()
    if 'port' in data:
        config['port'] = int(data['port'])
    if 'username' in data:
        config['username'] = str(data['username']).strip()
    if 'password' in data and data['password'] and data['password'] != '••••••••':
        config['password'] = data['password']
    if 'from_addr' in data:
        config['from_addr'] = str(data['from_addr']).strip()
    if 'use_tls' in data:
        config['use_tls'] = bool(data['use_tls'])
    if 'enabled' in data:
        config['enabled'] = bool(data['enabled'])

    save_json_data(EMAIL_CONFIG_FILE, config)
    log_activity('save_email_config', admin_pin, user_info.get('role', 'user'), {})
    return jsonify({'message': 'Email configuration saved'})


# --- Receipt Generation & Email Endpoints ---

@app.route('/api/orders/receipt/<int:order_id>', methods=['GET'])
def get_order_receipt(order_id):
    """Return receipt HTML for a completed order."""
    # Look in both orders and cleared orders
    all_orders = load_json_data(ORDERS_FILE) + load_json_data(CLEARED_ORDERS_FILE)
    order = None
    for o in all_orders:
        if o.get('order_id') == order_id:
            order = o
            break
    if not order:
        return jsonify({'message': 'Order not found'}), 404

    items = order.get('items', [])
    date_str = order.get('date', '')
    try:
        dt = datetime.fromisoformat(date_str) if date_str else datetime.now()
        formatted_date = dt.strftime('%Y-%m-%d %I:%M %p')
    except:
        formatted_date = date_str

    item_rows = ''.join(
        f'<tr><td style="padding:4px 8px;text-align:left;">{item.get("name","")} x{item.get("qty",1)}</td>'
        f'<td style="padding:4px 8px;text-align:right;">${float(item.get("price",0))*int(item.get("qty",1)):.2f}</td></tr>'
        for item in items
    )

    subtotal = float(order.get('subtotal', 0))
    tax = float(order.get('tax_amount', 0))
    tip = float(order.get('tip_amount', 0))
    service_charge = float(order.get('service_charge_amount', 0))
    discount = float(order.get('discount_amount', 0))
    total = float(order.get('total', 0))
    payment = order.get('payment', 'N/A')
    user = order.get('user', '—')

    discount_line = ''
    if discount > 0:
        discount_line = f'<tr><td style="padding:2px 8px;text-align:left;">Discount ({order.get("discount_code","")})</td><td style="padding:2px 8px;text-align:right;">−${discount:.2f}</td></tr>'

    service_charge_line = ''
    if service_charge > 0:
        service_charge_line = f'<tr><td style="padding:2px 8px;text-align:left;">Service Charge</td><td style="padding:2px 8px;text-align:right;">+${service_charge:.2f}</td></tr>'

    tip_line = ''
    if tip > 0:
        tip_line = f'<tr><td style="padding:2px 8px;text-align:left;">Tip</td><td style="padding:2px 8px;text-align:right;">+${tip:.2f}</td></tr>'

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Receipt #{order_id}</title>
<style>
  body {{ font-family: 'Courier New', monospace; margin: 0; padding: 20px; max-width: 360px; margin: auto; }}
  h2 {{ text-align: center; margin: 0 0 4px; }}
  .info {{ text-align: center; color: #555; font-size: 12px; margin: 2px 0; }}
  table {{ width: 100%; border-collapse: collapse; }}
  hr {{ border: none; border-top: 1px dashed #999; margin: 8px 0; }}
  .total {{ font-weight: bold; font-size: 15px; }}
  .footer {{ text-align: center; color: #555; font-size: 12px; margin-top: 12px; }}
</style>
</head>
<body>
  <h2>🍽️ POS System</h2>
  <div class="info">{formatted_date}</div>
  <div class="info">Order #{order_id}</div>
  <div class="info">Payment: {payment}</div>
  <div class="info">Cashier: {user}</div>
  <hr>
  <table>{item_rows}</table>
  <hr>
  <table>
    <tr><td style="padding:2px 8px;">Subtotal</td><td style="padding:2px 8px;text-align:right;">${subtotal:.2f}</td></tr>'''
    if tax > 0:
        html += f'<tr><td style="padding:2px 8px;">Tax</td><td style="padding:2px 8px;text-align:right;">${tax:.2f}</td></tr>'
    html += discount_line + service_charge_line + tip_line
    html += f'''
    <tr class="total"><td style="padding:6px 8px;border-top:1px solid #555;">TOTAL</td><td style="padding:6px 8px;text-align:right;border-top:1px solid #555;">${total:.2f}</td></tr>
  </table>
  <hr>
  <div class="footer">Thank you for your business!<br>Have a great day 🎉</div>
</body>
</html>'''

    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/api/orders/email_receipt', methods=['POST'])
def email_receipt():
    """Send a receipt for a completed order via email."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    data = request.json
    admin_pin = data.get('adminPin')
    order_id = data.get('order_id')
    recipient_email = data.get('recipient_email', '').strip()

    if not admin_pin:
        return jsonify({'message': 'Authentication required'}), 403
    if not order_id:
        return jsonify({'message': 'Order ID required'}), 400
    if not recipient_email or '@' not in recipient_email:
        return jsonify({'message': 'Valid recipient email required'}), 400

    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'Invalid user'}), 403

    # Get email config
    email_config = load_json_data(EMAIL_CONFIG_FILE)
    if not isinstance(email_config, dict):
        email_config = {"server": "", "port": 587, "username": "", "password": "", "from_addr": "", "use_tls": True, "enabled": False}
    if not email_config.get('enabled'):
        return jsonify({'message': 'Email sending is not configured. Go to Admin → Email Settings to set up SMTP.'}), 400
    if not email_config.get('server') or not email_config.get('from_addr'):
        return jsonify({'message': 'SMTP server or from address not configured.'}), 400

    # Find the order
    all_orders = load_json_data(ORDERS_FILE) + load_json_data(CLEARED_ORDERS_FILE)
    order = None
    for o in all_orders:
        if o.get('order_id') == order_id:
            order = o
            break
    if not order:
        return jsonify({'message': 'Order not found'}), 404

    # Generate receipt HTML
    items = order.get('items', [])
    date_str = order.get('date', '')
    try:
        dt = datetime.fromisoformat(date_str) if date_str else datetime.now()
        formatted_date = dt.strftime('%Y-%m-%d %I:%M %p')
    except:
        formatted_date = date_str

    item_rows = ''.join(
        f'<tr><td style="padding:4px 8px;text-align:left;">{item.get("name","")} x{item.get("qty",1)}</td>'
        f'<td style="padding:4px 8px;text-align:right;">${float(item.get("price",0))*int(item.get("qty",1)):.2f}</td></tr>'
        for item in items
    )
    subtotal = float(order.get('subtotal', 0))
    tax = float(order.get('tax_amount', 0))
    tip = float(order.get('tip_amount', 0))
    service_charge = float(order.get('service_charge_amount', 0))
    discount = float(order.get('discount_amount', 0))
    total = float(order.get('total', 0))
    payment = order.get('payment', 'N/A')

    receipt_html_body = f'''
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Receipt #{order_id}</title>
<style>
  body {{ font-family: 'Courier New', monospace; max-width: 360px; margin: auto; padding: 20px; }}
  h2 {{ text-align: center; margin: 0 0 4px; }}
  .info {{ text-align: center; color: #555; font-size: 12px; margin: 2px 0; }}
  table {{ width: 100%; border-collapse: collapse; }}
  hr {{ border: none; border-top: 1px dashed #999; margin: 8px 0; }}
  .total {{ font-weight: bold; font-size: 15px; }}
  .footer {{ text-align: center; color: #555; font-size: 12px; margin-top: 12px; }}
</style>
</head>
<body>
  <h2>🍽️ POS System</h2>
  <div class="info">{formatted_date}</div>
  <div class="info">Order #{order_id}</div>
  <div class="info">Payment: {payment}</div>
  <hr>
  <table>{item_rows}</table>
  <hr>
  <table>
    <tr><td style="padding:2px 8px;">Subtotal</td><td style="padding:2px 8px;text-align:right;">${subtotal:.2f}</td></tr>'''
    if tax > 0:
        receipt_html_body += f'<tr><td style="padding:2px 8px;">Tax</td><td style="padding:2px 8px;text-align:right;">${tax:.2f}</td></tr>'
    if discount > 0:
        receipt_html_body += f'<tr><td style="padding:2px 8px;">Discount ({order.get("discount_code","")})</td><td style="padding:2px 8px;text-align:right;">−${discount:.2f}</td></tr>'
    if service_charge > 0:
        receipt_html_body += f'<tr><td style="padding:2px 8px;">Service Charge</td><td style="padding:2px 8px;text-align:right;">+${service_charge:.2f}</td></tr>'
    if tip > 0:
        receipt_html_body += f'<tr><td style="padding:2px 8px;">Tip</td><td style="padding:2px 8px;text-align:right;">+${tip:.2f}</td></tr>'
    receipt_html_body += f'''
    <tr class="total"><td style="padding:6px 8px;border-top:1px solid #555;">TOTAL</td><td style="padding:6px 8px;text-align:right;border-top:1px solid #555;">${total:.2f}</td></tr>
  </table>
  <hr>
  <div class="footer">Thank you for your business!<br>Have a great day 🎉</div>
</body>
</html>'''

    # Build and send email
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Your Receipt — Order #{order_id}'
        msg['From'] = email_config.get('from_addr', '')
        msg['To'] = recipient_email
        msg.attach(MIMEText(f'Your receipt for Order #{order_id} (Total: ${total:.2f}) is attached.\n\nThank you!', 'plain'))
        msg.attach(MIMEText(receipt_html_body, 'html'))

        smtp_server = email_config.get('server', '')
        smtp_port = int(email_config.get('port', 587))
        use_tls = email_config.get('use_tls', True)
        username = email_config.get('username', '')
        password = email_config.get('password', '')

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
        server.quit()

        log_activity('email_receipt', admin_pin, users.get(admin_pin, {}).get('role', 'user'), {
            'order_id': order_id,
            'recipient': recipient_email
        })

        return jsonify({'message': f'Receipt sent to {recipient_email}'})
    except smtplib.SMTPAuthenticationError:
        return jsonify({'message': 'SMTP authentication failed. Check username/password.'}), 400
    except smtplib.SMTPException as e:
        return jsonify({'message': f'SMTP error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Failed to send email: {str(e)}'}), 500


@app.route('/api/orders/test_email', methods=['POST'])
def test_email():
    """Send a test email using configured SMTP settings."""
    import smtplib
    from email.mime.text import MIMEText

    data = request.json
    admin_pin = data.get('adminPin')
    test_email = data.get('test_email', '').strip()

    if not admin_pin:
        return jsonify({'message': 'Authentication required'}), 403
    if not test_email or '@' not in test_email:
        return jsonify({'message': 'Valid test email required'}), 400

    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'Invalid user'}), 403

    email_config = load_json_data(EMAIL_CONFIG_FILE)
    if not isinstance(email_config, dict):
        email_config = {"server": "", "port": 587, "username": "", "password": "", "from_addr": "", "use_tls": True, "enabled": False}
    if not email_config.get('server') or not email_config.get('from_addr'):
        return jsonify({'message': 'SMTP server or from address not configured.'}), 400

    try:
        msg = MIMEText('This is a test email from your POS System.\n\nIf you received this, your SMTP settings are working correctly!')
        msg['Subject'] = 'POS System — Test Email'
        msg['From'] = email_config.get('from_addr', '')
        msg['To'] = test_email

        smtp_server = email_config.get('server', '')
        smtp_port = int(email_config.get('port', 587))
        use_tls = email_config.get('use_tls', True)
        username = email_config.get('username', '')
        password = email_config.get('password', '')

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
        server.quit()

        return jsonify({'message': 'Test email sent successfully!'})
    except smtplib.SMTPAuthenticationError:
        return jsonify({'message': 'SMTP authentication failed. Check username/password.'}), 400
    except smtplib.SMTPException as e:
        return jsonify({'message': f'SMTP error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Failed to send test email: {str(e)}'}), 500


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


# --- Employee Clock-In / Clock-Out System ---

@app.route('/api/clock/in', methods=['POST'])
def clock_in():
    """Clock in an employee for their shift. Records start time."""
    data = request.json
    user_id = data.get('adminPin')  # Uses adminPin field for user identification

    if not user_id:
        return jsonify({'message': 'User ID required.'}), 400

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = users[user_id]
    if user_data.get('banned', False):
        return jsonify({'message': 'User is banned.'}), 403

    if user_id in active_shifts:
        return jsonify({'message': 'Already clocked in.'}), 409

    now = datetime.now()
    active_shifts[user_id] = {
        'clock_in_time': now,
        'user_name': user_data.get('name', 'Unknown')
    }

    log_activity('clock_in', user_id, user_data.get('role', 'user'), {
        'status': 'success',
        'user_name': user_data.get('name', 'Unknown'),
        'clock_in_time': now.isoformat()
    })

    return jsonify({
        'message': 'Clocked in successfully.',
        'clock_in_time': now.isoformat(),
        'user_name': user_data.get('name', 'Unknown')
    })


@app.route('/api/clock/out', methods=['POST'])
def clock_out():
    """Clock out an employee. Records end time and duration."""
    data = request.json
    user_id = data.get('adminPin')

    if not user_id:
        return jsonify({'message': 'User ID required.'}), 400

    if user_id not in active_shifts:
        return jsonify({'message': 'Not clocked in.'}), 409

    users = load_json_data(USERS_FILE)
    user_data = users.get(user_id, {})
    user_name = user_data.get('name', active_shifts[user_id].get('user_name', 'Unknown'))

    shift = active_shifts.pop(user_id)
    clock_in_time = shift['clock_in_time']
    clock_out_time = datetime.now()
    duration_hours = round((clock_out_time - clock_in_time).total_seconds() / 3600, 2)

    shift_record = {
        'user_id': user_id,
        'user_name': user_name,
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours
    }

    shift_log = load_json_data(SHIFT_FILE)
    shift_log.append(shift_record)
    save_json_data(SHIFT_FILE, shift_log)

    log_activity('clock_out', user_id, user_data.get('role', 'user'), {
        'status': 'success',
        'user_name': user_name,
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours
    })

    return jsonify({
        'message': 'Clocked out successfully.',
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours
    })


@app.route('/api/clock/status', methods=['POST'])
def clock_status():
    """Check if the current user is clocked in and get their shift info."""
    data = request.json
    user_id = data.get('adminPin')

    if not user_id:
        return jsonify({'message': 'User ID required.'}), 400

    users = load_json_data(USERS_FILE)
    user_data = users.get(user_id, {})
    user_name = user_data.get('name', 'Unknown')

    if user_id in active_shifts:
        shift = active_shifts[user_id]
        clock_in_time = shift['clock_in_time']
        now = datetime.now()
        duration_hours = round((now - clock_in_time).total_seconds() / 3600, 2)
        return jsonify({
            'clocked_in': True,
            'clock_in_time': clock_in_time.isoformat(),
            'duration_hours': duration_hours,
            'user_name': user_name
        })
    else:
        return jsonify({
            'clocked_in': False,
            'user_name': user_name
        })


@app.route('/api/admin_shifts', methods=['POST'])
def admin_shifts():
    """Get all shift records (completed) for admin timesheet view."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)
    # Also include active (currently clocked-in) shifts
    active_shift_list = []
    for uid, shift in active_shifts.items():
        users = load_json_data(USERS_FILE)
        user_data = users.get(uid, {})
        now = datetime.now()
        duration_hours = round((now - shift['clock_in_time']).total_seconds() / 3600, 2)
        active_shift_list.append({
            'user_id': uid,
            'user_name': shift.get('user_name', user_data.get('name', 'Unknown')),
            'clock_in_time': shift['clock_in_time'].isoformat(),
            'clock_out_time': None,
            'duration_hours': duration_hours,
            'active': True
        })

    return jsonify({
        'message': 'Shift data retrieved',
        'shifts': shift_log,
        'active_shifts': active_shift_list
    })


@app.route('/api/export/shifts_csv', methods=['POST'])
def export_shifts_csv():
    """Export employee shift records as CSV."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)
    headers = ['User ID', 'User Name', 'Clock In Time', 'Clock Out Time', 'Duration (Hours)']

    rows = []
    for entry in shift_log:
        rows.append({
            'User ID': entry.get('user_id', ''),
            'User Name': entry.get('user_name', ''),
            'Clock In Time': entry.get('clock_in_time', ''),
            'Clock Out Time': entry.get('clock_out_time', ''),
            'Duration (Hours)': entry.get('duration_hours', 0)
        })

    csv_content = generate_csv(rows, headers)
    return jsonify({'csv': csv_content, 'filename': 'shifts_export.csv'})


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
# --- Service Charge / Auto-Gratuity Endpoints ---
# ============================================================

@app.route('/api/service-charge/config', methods=['GET'])
def get_service_charge_config():
    """Get the current service charge config (public, no auth)."""
    config = load_json_data(SERVICE_CHARGE_FILE)
    return jsonify(config)


@app.route('/api/service-charge/config', methods=['POST'])
def update_service_charge_config():
    """Update service charge config (admin/owner only, manage_items permission)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        log_activity('update_service_charge', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Unauthorized. Admin PIN or permission required.'}), 403

    config = load_json_data(SERVICE_CHARGE_FILE)

    if 'enabled' in data:
        config['enabled'] = bool(data['enabled'])
    if 'threshold' in data:
        try:
            config['threshold'] = int(data['threshold'])
        except (ValueError, TypeError):
            return jsonify({'message': 'Threshold must be a number.'}), 400
    if 'percentage' in data:
        try:
            val = float(data['percentage'])
            if val < 0 or val > 100:
                return jsonify({'message': 'Percentage must be between 0 and 100.'}), 400
            config['percentage'] = val
        except (ValueError, TypeError):
            return jsonify({'message': 'Percentage must be a number.'}), 400
    if 'label' in data:
        config['label'] = str(data['label']).strip()

    save_json_data(SERVICE_CHARGE_FILE, config)
    log_activity('update_service_charge', admin_pin, 'admin', {'new_config': config})
    return jsonify({'message': 'Service charge configuration updated successfully', 'config': config})


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
# Pickup Display Board System
# ============================================================

PICKUP_DISPLAY_FILE = 'pickup_display.json'  # Tracks orders on the pickup board


def load_pickup_display():
    """Load the pickup display state from disk."""
    default = {'orders': []}
    data = load_json_data(PICKUP_DISPLAY_FILE)
    if isinstance(data, dict) and 'orders' in data:
        return data
    return default


def save_pickup_display(data):
    """Save pickup display state to disk."""
    with open(PICKUP_DISPLAY_FILE, 'w') as f:
        json.dump(data, f, indent=2)


@app.route('/api/pickup-display/queue', methods=['GET'])
def pickup_display_queue():
    """Return orders on the pickup board (ready for pickup, not yet collected)."""
    orders = load_json_data(ORDERS_FILE)
    pickup_orders = []
    for o in orders:
        if o.get('ready_for_pickup') is True and o.get('collected_at') is None:
            ready_at = o.get('ready_for_pickup_at', o.get('completed_at', o.get('date', '')))
            pickup_orders.append({
                'order_id': o.get('order_id'),
                'order_number': o.get('order_id'),
                'customer_name': o.get('customer_name', ''),
                'items': o.get('items', []),
                'item_count': len(o.get('items', [])),
                'total': float(o.get('total', 0)),
                'ready_at': ready_at,
                'status': 'ready'
            })
    # Sort: newest first (most recently ready at top)
    pickup_orders.sort(key=lambda o: o.get('ready_at', ''), reverse=True)
    # Mark first N as "new" if they arrived within last 60 seconds
    now = datetime.now()
    for po in pickup_orders:
        try:
            ready_dt = datetime.fromisoformat(po['ready_at'])
            diff = (now - ready_dt).total_seconds()
            if diff < 60:
                po['status'] = 'new'
        except (ValueError, TypeError):
            pass
    return jsonify({'queue': pickup_orders, 'count': len(pickup_orders)})


@app.route('/api/pickup-display/mark-ready', methods=['POST'])
def pickup_display_mark_ready():
    """Mark an order as ready for pickup. Sets ready_for_pickup flag on the order."""
    data = request.json
    order_id = data.get('order_id')
    if order_id is None:
        return jsonify({'error': 'order_id is required'}), 400

    orders = load_json_data(ORDERS_FILE)
    for order in orders:
        if order.get('order_id') == order_id:
            if order.get('ready_for_pickup'):
                return jsonify({'message': f'Order #{order_id} is already marked ready for pickup'}), 200
            order['ready_for_pickup'] = True
            order['ready_for_pickup_at'] = datetime.now().isoformat()
            save_json_data(ORDERS_FILE, orders)
            log_activity('pickup_mark_ready', data.get('user', 'unknown'), 'user', {
                'order_id': order_id, 'action': 'marked ready for pickup'
            })
            emit_pickup_update()
            return jsonify({'message': f'Order #{order_id} marked ready for pickup'})
    return jsonify({'error': f'Order #{order_id} not found'}), 404


@app.route('/api/pickup-display/collected', methods=['POST'])
def pickup_display_collected():
    """Mark an order as collected by the customer."""
    data = request.json
    order_id = data.get('order_id')
    if order_id is None:
        return jsonify({'error': 'order_id is required'}), 400

    orders = load_json_data(ORDERS_FILE)
    for order in orders:
        if order.get('order_id') == order_id:
            if order.get('collected_at'):
                return jsonify({'message': f'Order #{order_id} was already collected'}), 200
            order['collected_at'] = datetime.now().isoformat()
            save_json_data(ORDERS_FILE, orders)
            log_activity('pickup_collected', data.get('user', 'unknown'), 'user', {
                'order_id': order_id, 'action': 'collected by customer'
            })
            emit_pickup_update()
            return jsonify({'message': f'Order #{order_id} marked as collected'})
    return jsonify({'error': f'Order #{order_id} not found'}), 404


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
        'customer': {
            'phone': loyalty_data[phone].get('phone', phone),
            'name': loyalty_data[phone].get('name', ''),
            'email': loyalty_data[phone].get('email', ''),
            'notes': loyalty_data[phone].get('notes', ''),
            'address': loyalty_data[phone].get('address', ''),
            'points': loyalty_data[phone].get('points', 0),
            'total_earned': loyalty_data[phone].get('total_earned', 0),
            'total_redeemed': loyalty_data[phone].get('total_redeemed', 0),
            'total_spent': loyalty_data[phone].get('total_spent', 0.0),
            'total_orders': loyalty_data[phone].get('total_orders', 0),
            'last_visit': loyalty_data[phone].get('last_visit', ''),
            'created_at': loyalty_data[phone].get('created_at', '')
        }
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
        'email': '',
        'notes': '',
        'address': '',
        'points': 0,
        'total_earned': 0,
        'total_redeemed': 0,
        'total_spent': 0.0,
        'total_orders': 0,
        'last_visit': '',
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
            'email': data.get('email', ''),
            'points': data.get('points', 0),
            'total_earned': data.get('total_earned', 0),
            'total_redeemed': data.get('total_redeemed', 0),
            'total_spent': data.get('total_spent', 0.0),
            'total_orders': data.get('total_orders', 0),
            'last_visit': data.get('last_visit', ''),
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
# Customer Profile Management (CRM)
# ============================================================


@app.route('/api/customers/list', methods=['POST'])
def customers_list():
    """List/search customers (admin-only). Supports search by name or phone."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')

    if not admin_pin or not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    search_query = data.get('search', '').strip().lower()
    loyalty_data = load_json_data(LOYALTY_FILE)

    customers = []
    for phone, cd in loyalty_data.items():
        # Skip if search filter provided and doesn't match
        if search_query:
            if search_query not in cd.get('name', '').lower() and search_query not in phone:
                continue

        customers.append({
            'phone': cd.get('phone', phone),
            'name': cd.get('name', 'Unknown'),
            'email': cd.get('email', ''),
            'points': cd.get('points', 0),
            'total_earned': cd.get('total_earned', 0),
            'total_redeemed': cd.get('total_redeemed', 0),
            'total_spent': cd.get('total_spent', 0.0),
            'total_orders': cd.get('total_orders', 0),
            'last_visit': cd.get('last_visit', ''),
            'created_at': cd.get('created_at', '')
        })

    # Sort by total_spent descending
    customers.sort(key=lambda c: c['total_spent'], reverse=True)

    return jsonify({'customers': customers})


@app.route('/api/customers/detail', methods=['POST'])
def customer_detail():
    """Get full customer profile with order history."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    phone = data.get('phone', '').strip()

    if not admin_pin or not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not phone:
        return jsonify({'message': 'Phone number is required.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)
    if phone not in loyalty_data:
        return jsonify({'message': 'Customer not found.'}), 404

    customer = loyalty_data[phone]

    # Gather order history from orders.json
    orders = load_json_data(ORDERS_FILE)
    order_history = []
    for o in orders:
        if o.get('customer_phone', '').strip() == phone:
            order_history.append({
                'order_id': o.get('order_id', o.get('id', 0)),
                'order_number': o.get('order_number', 0),
                'date': o.get('date', o.get('timestamp', '')),
                'subtotal': o.get('subtotal', 0),
                'total': o.get('total', 0),
                'items': o.get('items', []),
                'payment_method': o.get('payment', o.get('payment_method', '')),
                'status': o.get('status', 'pending')
            })

    # Also check cleared_orders for this phone
    cleared = load_json_data(CLEARED_ORDERS_FILE)
    for co in cleared:
        if co.get('customer_phone', '').strip() == phone:
            order_history.append({
                'order_id': co.get('order_id', 0),
                'order_number': co.get('order_number', 0),
                'date': co.get('date', co.get('timestamp', '')),
                'subtotal': co.get('subtotal', 0),
                'total': co.get('total', 0),
                'items': co.get('items', []),
                'payment_method': co.get('payment', co.get('payment_method', '')),
                'status': 'cleared'
            })

    # Sort by date descending
    order_history.sort(key=lambda o: o.get('date', ''), reverse=True)

    # Limit to last 50 orders
    order_history = order_history[:50]

    return jsonify({
        'customer': {
            'phone': customer.get('phone', phone),
            'name': customer.get('name', 'Unknown'),
            'email': customer.get('email', ''),
            'notes': customer.get('notes', ''),
            'address': customer.get('address', ''),
            'points': customer.get('points', 0),
            'total_earned': customer.get('total_earned', 0),
            'total_redeemed': customer.get('total_redeemed', 0),
            'total_spent': customer.get('total_spent', 0.0),
            'total_orders': customer.get('total_orders', 0),
            'last_visit': customer.get('last_visit', ''),
            'created_at': customer.get('created_at', ''),
            'history': customer.get('history', [])
        },
        'order_history': order_history
    })


@app.route('/api/customers/update', methods=['POST'])
def customer_update():
    """Update customer profile fields (email, notes, address)."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    phone = data.get('phone', '').strip()

    if not admin_pin or not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not phone:
        return jsonify({'message': 'Phone number is required.'}), 400

    loyalty_data = load_json_data(LOYALTY_FILE)
    if phone not in loyalty_data:
        return jsonify({'message': 'Customer not found.'}), 404

    customer = loyalty_data[phone]

    # Update editable fields
    if 'email' in data:
        customer['email'] = data['email'].strip()
    if 'notes' in data:
        customer['notes'] = data['notes'].strip()
    if 'address' in data:
        customer['address'] = data['address'].strip()
    if 'name' in data:
        customer['name'] = data['name'].strip()

    save_json_data(LOYALTY_FILE, loyalty_data)

    log_activity('customer_update', admin_pin, 'admin', {
        'customer_phone': phone,
        'updated_fields': [k for k in ['name', 'email', 'notes', 'address'] if k in data]
    })

    return jsonify({
        'message': f'Customer {customer["name"]} updated successfully.',
        'customer': {
            'phone': customer.get('phone', phone),
            'name': customer.get('name', 'Unknown'),
            'email': customer.get('email', ''),
            'notes': customer.get('notes', ''),
            'address': customer.get('address', ''),
            'points': customer.get('points', 0),
            'total_spent': customer.get('total_spent', 0.0),
            'total_orders': customer.get('total_orders', 0),
            'last_visit': customer.get('last_visit', '')
        }
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
# Cash Register / Drawer Management System
# ============================================================


def get_cash_drawer_data():
    """Load cash drawer data."""
    return load_json_data(CASH_DRAWER_FILE)


def save_cash_drawer_data(data):
    """Save cash drawer data."""
    save_json_data(CASH_DRAWER_FILE, data)


def get_active_session(drawer_data):
    """Return the currently open session (status='open'), or None."""
    for s in drawer_data.get('sessions', []):
        if s.get('status') == 'open':
            return s
    return None


def calculate_expected_balance(session, drawer_data):
    """Calculate the expected cash balance for a session.
    expected = opening_balance + sum(cash_in) - sum(cash_out)
    """
    opening = float(session.get('opening_balance', 0))
    total_in = 0.0
    total_out = 0.0
    session_id = session.get('id')
    for txn in drawer_data.get('transactions', []):
        if txn.get('session_id') != session_id:
            continue
        txn_type = txn.get('type', '')
        amount = float(txn.get('amount', 0))
        if txn_type == 'cash_in':
            total_in += amount
        elif txn_type == 'cash_out':
            total_out += amount
    expected = opening + total_in - total_out
    return round(expected, 2), round(total_in, 2), round(total_out, 2)


@app.route('/api/cash_drawer/open', methods=['POST'])
def cash_drawer_open():
    """Open a new cash drawer session with an opening balance."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    opening_balance = data.get('opening_balance')
    if opening_balance is None:
        return jsonify({'message': 'Opening balance is required.'}), 400

    try:
        opening_balance = float(opening_balance)
        if opening_balance < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'Opening balance must be a non-negative number.'}), 400

    drawer = get_cash_drawer_data()

    # Check there isn't already an open session
    active = get_active_session(drawer)
    if active:
        return jsonify({'message': 'A cash drawer session is already open. Close it first.'}), 409

    users_data = load_json_data(USERS_FILE)
    admin_user = users_data.get(admin_pin, {})
    admin_name = admin_user.get('name', 'Unknown')

    session_id = secrets.token_hex(8)
    session = {
        'id': session_id,
        'opened_at': datetime.now().isoformat(),
        'opened_by': admin_pin,
        'opened_by_name': admin_name,
        'opening_balance': opening_balance,
        'closed_at': None,
        'closed_by': None,
        'closed_by_name': None,
        'closing_balance': None,
        'expected_balance': None,
        'difference': None,
        'notes': data.get('notes', ''),
        'status': 'open'
    }

    drawer['sessions'].append(session)
    save_cash_drawer_data(drawer)

    log_activity('cash_drawer_open', admin_pin, admin_user.get('role', 'unknown'), {
        'session_id': session_id,
        'opening_balance': opening_balance
    })

    return jsonify({'message': 'Cash drawer opened successfully.', 'session': session})


@app.route('/api/cash_drawer/transaction', methods=['POST'])
def cash_drawer_transaction():
    """Record a cash-in or cash-out transaction."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    txn_type = data.get('type')  # 'cash_in' or 'cash_out'
    amount = data.get('amount')
    reason = data.get('reason', '').strip()

    if txn_type not in ('cash_in', 'cash_out'):
        return jsonify({'message': 'Type must be \"cash_in\" or \"cash_out\".'}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'Amount must be a positive number.'}), 400

    if not reason:
        return jsonify({'message': 'Reason is required for cash transactions.'}), 400

    drawer = get_cash_drawer_data()

    # Find active session
    session = get_active_session(drawer)
    if not session:
        return jsonify({'message': 'No open cash drawer session. Open one first.'}), 409

    users_data = load_json_data(USERS_FILE)
    admin_user = users_data.get(admin_pin, {})
    admin_name = admin_user.get('name', 'Unknown')

    txn_id = secrets.token_hex(8)
    transaction = {
        'id': txn_id,
        'session_id': session['id'],
        'type': txn_type,
        'amount': amount,
        'reason': reason,
        'created_at': datetime.now().isoformat(),
        'created_by': admin_pin,
        'created_by_name': admin_name,
        'related_order_id': data.get('related_order_id')
    }

    drawer['transactions'].append(transaction)
    save_cash_drawer_data(drawer)

    label = 'Cash In' if txn_type == 'cash_in' else 'Cash Out'
    log_activity('cash_drawer_transaction', admin_pin, admin_user.get('role', 'unknown'), {
        'session_id': session['id'],
        'type': txn_type,
        'amount': amount,
        'reason': reason
    })

    return jsonify({
        'message': f'{label} of ${amount:.2f} recorded.',
        'transaction': transaction
    })


@app.route('/api/cash_drawer/close', methods=['POST'])
def cash_drawer_close():
    """Close the current cash drawer session with reconciliation."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    closing_balance = data.get('closing_balance')
    if closing_balance is None:
        return jsonify({'message': 'Closing balance (actual count) is required.'}), 400

    try:
        closing_balance = float(closing_balance)
        if closing_balance < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'Closing balance must be a non-negative number.'}), 400

    drawer = get_cash_drawer_data()
    session = get_active_session(drawer)
    if not session:
        return jsonify({'message': 'No open cash drawer session found.'}), 409

    users_data = load_json_data(USERS_FILE)
    admin_user = users_data.get(admin_pin, {})
    admin_name = admin_user.get('name', 'Unknown')

    # Calculate expected balance
    expected, total_in, total_out = calculate_expected_balance(session, drawer)
    difference = round(closing_balance - expected, 2)

    session['closed_at'] = datetime.now().isoformat()
    session['closed_by'] = admin_pin
    session['closed_by_name'] = admin_name
    session['closing_balance'] = closing_balance
    session['expected_balance'] = expected
    session['difference'] = difference
    session['status'] = 'closed'
    session['notes'] = data.get('notes', session.get('notes', ''))
    session['total_cash_in'] = total_in
    session['total_cash_out'] = total_out

    save_cash_drawer_data(drawer)

    log_activity('cash_drawer_close', admin_pin, admin_user.get('role', 'unknown'), {
        'session_id': session['id'],
        'opening_balance': session['opening_balance'],
        'expected_balance': expected,
        'closing_balance': closing_balance,
        'difference': difference
    })

    return jsonify({
        'message': 'Cash drawer closed and reconciled.',
        'session': session,
        'reconciliation': {
            'opening_balance': session['opening_balance'],
            'total_cash_in': total_in,
            'total_cash_out': total_out,
            'expected_balance': expected,
            'closing_balance': closing_balance,
            'difference': difference
        }
    })


@app.route('/api/cash_drawer/status', methods=['POST'])
def cash_drawer_status():
    """Get the current cash drawer session status."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    drawer = get_cash_drawer_data()
    session = get_active_session(drawer)

    if not session:
        # Return the last closed session info
        sessions = drawer.get('sessions', [])
        last_closed = None
        for s in reversed(sessions):
            if s.get('status') == 'closed':
                last_closed = s
                break
        return jsonify({
            'active': False,
            'last_closed': last_closed,
            'sessions_count': len(sessions)
        })

    # Calculate expected balance for current session
    expected, total_in, total_out = calculate_expected_balance(session, drawer)
    return jsonify({
        'active': True,
        'session': session,
        'expected_balance': expected,
        'total_cash_in': total_in,
        'total_cash_out': total_out
    })


@app.route('/api/cash_drawer/history', methods=['POST'])
def cash_drawer_history():
    """Get all cash drawer sessions with their transactions."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    drawer = get_cash_drawer_data()
    sessions = drawer.get('sessions', [])
    transactions = drawer.get('transactions', [])

    # Build session summaries with transaction counts
    result = []
    for s in reversed(sessions):  # newest first
        session_txns = [t for t in transactions if t.get('session_id') == s.get('id')]
        result.append({
            **s,
            'transaction_count': len(session_txns),
            'transactions': session_txns
        })

    return jsonify({
        'sessions': result,
        'total_sessions': len(sessions)
    })


@app.route('/api/cash_drawer/report', methods=['POST'])
def cash_drawer_report():
    """Get a reconciliation report for a specific session or all sessions."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    drawer = get_cash_drawer_data()
    session_id = data.get('session_id')

    sessions = drawer.get('sessions', [])
    transactions = drawer.get('transactions', [])

    if session_id:
        # Report for a specific session
        session = None
        for s in sessions:
            if s.get('id') == session_id:
                session = s
                break
        if not session:
            return jsonify({'message': 'Session not found.'}), 404

        session_txns = [t for t in transactions if t.get('session_id') == session_id]
        expected, total_in, total_out = calculate_expected_balance(session, drawer)
        return jsonify({
            'session': session,
            'transactions': session_txns,
            'expected_balance': expected,
            'total_cash_in': total_in,
            'total_cash_out': total_out
        })
    else:
        # Summary of all closed sessions
        summary = []
        for s in sessions:
            if s.get('status') == 'closed':
                summary.append({
                    'id': s.get('id'),
                    'opened_at': s.get('opened_at'),
                    'closed_at': s.get('closed_at'),
                    'opened_by_name': s.get('opened_by_name'),
                    'closed_by_name': s.get('closed_by_name'),
                    'opening_balance': s.get('opening_balance'),
                    'expected_balance': s.get('expected_balance'),
                    'closing_balance': s.get('closing_balance'),
                    'difference': s.get('difference'),
                    'total_cash_in': s.get('total_cash_in', 0),
                    'total_cash_out': s.get('total_cash_out', 0)
                })
        return jsonify({'closed_sessions': summary})


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


@app.route('/pickup-display')
def serve_pickup_display():
    """Serve the pickup display board page."""
    return send_from_directory(app.static_folder, 'pickup-display.html')


@app.route('/tablet')
def serve_tablet():
    """Serve the table-side ad display page for table tablets."""
    return send_from_directory(app.static_folder, 'tablet.html')


# ══════════════════════════════════════════════════
# Category Management API
# ══════════════════════════════════════════════════

@app.route('/api/categories/list', methods=['POST'])
def categories_list():
    """Return all categories with item counts. Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    items_data = load_json_data(ITEMS_FILE)
    categories = []
    for cat_name, cat_items in items_data.items():
        categories.append({
            'name': cat_name,
            'item_count': len(cat_items)
        })
    return jsonify({'categories': categories})


@app.route('/api/categories/create', methods=['POST'])
def categories_create():
    """Create a new empty category. Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'message': 'Category name is required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if name in items_data:
        return jsonify({'message': f'Category "{name}" already exists.'}), 409

    items_data[name] = []
    save_json_data(ITEMS_FILE, items_data)
    backup_menu()

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('category_create', admin_pin, admin_role, {'name': name})

    return jsonify({'message': f'Category "{name}" created.', 'category': name})


@app.route('/api/categories/rename', methods=['POST'])
def categories_rename():
    """Rename a category. All items move to the new key. Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    old_name = (data.get('oldName') or '').strip()
    new_name = (data.get('newName') or '').strip()

    if not old_name or not new_name:
        return jsonify({'message': 'Both old and new category names are required.'}), 400
    if old_name == new_name:
        return jsonify({'message': 'New name is the same as the old name.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if old_name not in items_data:
        return jsonify({'message': f'Category "{old_name}" not found.'}), 404
    if new_name in items_data:
        return jsonify({'message': f'Category "{new_name}" already exists.'}), 409

    # Rebuild dict with new key in the same position
    new_items_data = {}
    for cat, cat_items in items_data.items():
        if cat == old_name:
            new_items_data[new_name] = cat_items
        else:
            new_items_data[cat] = cat_items

    save_json_data(ITEMS_FILE, new_items_data)
    backup_menu()

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('category_rename', admin_pin, admin_role, {'old_name': old_name, 'new_name': new_name})

    return jsonify({'message': f'Category renamed from "{old_name}" to "{new_name}".'})


@app.route('/api/categories/delete', methods=['POST'])
def categories_delete():
    """Delete a category (only if empty). Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'message': 'Category name is required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    if name not in items_data:
        return jsonify({'message': f'Category "{name}" not found.'}), 404

    if len(items_data[name]) > 0:
        return jsonify({'message': f'Cannot delete category "{name}" — it contains {len(items_data[name])} item(s). Move or delete them first.', 'item_count': len(items_data[name])}), 400

    del items_data[name]
    save_json_data(ITEMS_FILE, items_data)
    backup_menu()

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('category_delete', admin_pin, admin_role, {'name': name})

    return jsonify({'message': f'Category "{name}" deleted.'})


@app.route('/api/categories/reorder', methods=['POST'])
def categories_reorder():
    """Reorder categories. Accepts an ordered array of category names.
    Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    order = data.get('order')
    if not isinstance(order, list) or len(order) == 0:
        return jsonify({'message': 'Order array is required.'}), 400

    items_data = load_json_data(ITEMS_FILE)
    # Validate all names in order exist in current data
    for cat_name in order:
        if cat_name not in items_data:
            return jsonify({'message': f'Category "{cat_name}" not found.'}), 404

    # Check that all existing categories are in the order array
    for cat_name in items_data:
        if cat_name not in order:
            return jsonify({'message': f'Missing category "{cat_name}" in order array.'}), 400

    # Rebuild dict preserving new order
    new_items_data = {}
    for cat_name in order:
        new_items_data[cat_name] = items_data[cat_name]

    save_json_data(ITEMS_FILE, new_items_data)
    backup_menu()

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('category_reorder', admin_pin, admin_role, {'order': order})

    return jsonify({'message': 'Categories reordered successfully.'})


# ═══════════════════════════════════════════
# COMBO / MEAL DEAL BUILDER
# ═══════════════════════════════════════════

def load_combos():
    data = load_json_data(COMBOS_FILE)
    if isinstance(data, dict) and 'combos' in data:
        return data['combos']
    return []

def save_combos(combos_list):
    save_json_data(COMBOS_FILE, {'combos': combos_list})


@app.route('/api/combos/list', methods=['GET'])
def combos_list():
    """Return all combos."""
    return jsonify({'combos': load_combos()})


@app.route('/api/combos/save', methods=['POST'])
def combos_save():
    """Create or update a combo. If id is provided, update existing; else create new.
    Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    combo_id = data.get('id', '').strip()
    name = (data.get('name') or '').strip()
    combo_price = data.get('combo_price')
    description = (data.get('description') or '').strip()
    child_items = data.get('child_items', [])

    if not name:
        return jsonify({'message': 'Combo name is required.'}), 400
    if combo_price is None:
        return jsonify({'message': 'Combo price is required.'}), 400
    try:
        combo_price = float(combo_price)
        if combo_price <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'message': 'Combo price must be a positive number.'}), 400
    if not child_items or not isinstance(child_items, list):
        return jsonify({'message': 'At least one child item is required.'}), 400
    for ci in child_items:
        if not ci.get('name') or not ci.get('category'):
            return jsonify({'message': 'Each child item must have a name and category.'}), 400

    combos = load_combos()
    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'

    if combo_id:
        # Update existing
        found = False
        for i, c in enumerate(combos):
            if c.get('id') == combo_id:
                combos[i] = {
                    'id': combo_id,
                    'name': name,
                    'combo_price': combo_price,
                    'description': description,
                    'child_items': child_items,
                    'active': data.get('active', c.get('active', True)),
                    'created_at': c.get('created_at', datetime.now().isoformat()),
                    'updated_at': datetime.now().isoformat()
                }
                found = True
                log_activity('combo_update', admin_pin, admin_role, {'combo_id': combo_id, 'name': name, 'price': combo_price})
                break
        if not found:
            return jsonify({'message': f'Combo with id \"{combo_id}\" not found.'}), 404
    else:
        # Create new
        combo_id = f'combo_{int(datetime.now().timestamp())}'
        combo_entry = {
            'id': combo_id,
            'name': name,
            'combo_price': combo_price,
            'description': description,
            'child_items': child_items,
            'active': True,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        combos.append(combo_entry)
        log_activity('combo_create', admin_pin, admin_role, {'combo_id': combo_id, 'name': name, 'price': combo_price})

    save_combos(combos)
    return jsonify({'message': 'Combo saved successfully!', 'combos': combos})


@app.route('/api/combos/delete', methods=['POST'])
def combos_delete():
    """Delete a combo by id. Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    combo_id = data.get('id', '').strip()
    if not combo_id:
        return jsonify({'message': 'Combo id is required.'}), 400

    combos = load_combos()
    new_combos = [c for c in combos if c.get('id') != combo_id]
    if len(new_combos) == len(combos):
        return jsonify({'message': f'Combo \"{combo_id}\" not found.'}), 404

    save_combos(new_combos)

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('combo_delete', admin_pin, admin_role, {'combo_id': combo_id})

    return jsonify({'message': 'Combo deleted successfully!', 'combos': new_combos})


@app.route('/api/combos/toggle', methods=['POST'])
def combos_toggle():
    """Toggle a combo's active status. Permission: manage_items."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    combo_id = data.get('id', '').strip()
    if not combo_id:
        return jsonify({'message': 'Combo id is required.'}), 400

    combos = load_combos()
    found = False
    for c in combos:
        if c.get('id') == combo_id:
            c['active'] = not c.get('active', True)
            c['updated_at'] = datetime.now().isoformat()
            found = True
            break

    if not found:
        return jsonify({'message': f'Combo \"{combo_id}\" not found.'}), 404

    save_combos(combos)

    admin_user = load_json_data(USERS_FILE).get(admin_pin, None)
    admin_role = admin_user['role'] if admin_user else 'unknown'
    log_activity('combo_toggle', admin_pin, admin_role, {'combo_id': combo_id})

    return jsonify({'message': 'Combo toggled successfully!', 'combos': combos})


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)

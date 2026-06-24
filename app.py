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
import base64
import threading
import urllib.request
import urllib.error
from collections import defaultdict, Counter
import pyotp
import qrcode
import html as _html
import re
from functools import wraps

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all origins

# --- SocketIO for real-time updates ---
# NOTE: Production deployment uses gunicorn + eventlet:
#   gunicorn -k eventlet -w 1 app:app
# The `app` Flask object is used as the WSGI entry point; Flask-SocketIO
# hooks into the gevent async worker transparently when async_mode='gevent'.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# --- IP Blocklist / Allowlist Enforcement (before every request) ---
# In-memory IP failed attempt tracking for auto-block
# Structure: {ip: {'count': int, 'window_start': datetime}}
ip_failed_attempts = {}

# --- Anomaly Detection Engine — In-Memory Trackers ---
# Tracks orders per user for rapid-order detection
user_order_tracker = defaultdict(lambda: {'count': 0, 'window_start': None, 'total': 0.0})
_lock_for_order_tracker = threading.Lock()
# Tracks known IPs per user for new-IP detection
user_known_ips = defaultdict(set)
# Tracks active login sessions per user for simultaneous-login detection
user_login_sessions = defaultdict(list)

# Session management — tracks active sessions per user with tokens
# Structure: { user_id: { session_token: { token, ip, user_agent, device_info, login_time, last_active, user_id, user_name, role } } }
# Session expiry: 8h active (session token valid), 24h idle (last_active cutoff)
active_user_sessions = defaultdict(dict)
SESSION_ACTIVE_HOURS = 8  # session token considered active
SESSION_IDLE_HOURS = 24   # session considered "active" in listing if last_active within this

@app.before_request
def enforce_ip_blocklist():
    """Check client IP against blocklist/allowlist before every request.
    Returns 403 if IP is blocked or not allowed."""
    # Skip static files, health check, and unblock endpoints (so owner can recover)
    if request.path.startswith('/static') or request.path == '/favicon.ico':
        return None
    if request.path in ('/api/health', '/api/security/unblock_ip', '/api/security/blocklist/add'):
        return None

    client_ip = get_client_ip()
    # Localhost is always allowed (admin access from server console)
    if client_ip in ('127.0.0.1', '::1', 'localhost'):
        return None

    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}

    # IP Allowlist mode: if allowlist is non-empty, ONLY those IPs are allowed
    ip_allowlist = config.get('ip_allowlist', [])
    if ip_allowlist and client_ip not in ip_allowlist:
        return jsonify({
            'message': 'Access denied: your IP is not in the allowed list.',
            'code': 'ip_not_allowed'
        }), 403

    # IP Blocklist check
    blocked_ips = config.get('blocked_ips', [])
    for entry in blocked_ips:
        if isinstance(entry, dict) and entry.get('ip') == client_ip:
            reason = entry.get('reason', 'No reason provided')
            return jsonify({
                'message': f'Access denied: your IP ({client_ip}) is blocked. Reason: {reason}',
                'code': 'ip_blocked'
            }), 403
        elif isinstance(entry, str) and entry == client_ip:
            return jsonify({
                'message': f'Access denied: your IP ({client_ip}) is blocked.',
                'code': 'ip_blocked'
            }), 403

    return None

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
TIMESHEET_CONFIG_FILE = 'timesheet_config.json'  # Timesheet configuration (overtime thresholds, late grace period)
TICKETS_FILE = 'tickets.json'  # Employee self-service tickets/requests
APPROVALS_FILE = 'timesheet_approvals.json'  # Timesheet pay period approvals
RESTAURANT_CONFIG_FILE = 'restaurant_config.json'  # Restaurant info for tablet display (name, hours, wifi)
LOGIN_ATTEMPTS_FILE = 'login_attempts.json'  # Persistent login attempt records (user_id, ip, timestamp, success, user_agent)
SECURITY_EVENTS_FILE = 'security_events.json'  # Security events/incidents log
SECURITY_CONFIG_FILE = 'security_config.json'  # Security config (blocked IPs, thresholds)

# --- Platform / Multi-Tenant Constants ---
GLOCAL_DIR = 'data/global'  # Global platform data directory
BUSINESSES_FILE = os.path.join(GLOCAL_DIR, 'businesses.json')  # All registered businesses
SUPER_ADMINS_FILE = os.path.join(GLOCAL_DIR, 'super_admins.json')  # Super admin accounts

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
    # Ensure pay_rate field exists
    if 'pay_rate' not in user_data:
        user_data['pay_rate'] = None
    # Ensure scheduled_start field exists
    if 'scheduled_start' not in user_data:
        user_data['scheduled_start'] = None
    # Ensure 2FA/TOTP fields exist
    if 'totp_secret' not in user_data:
        user_data['totp_secret'] = None
    if 'totp_enabled' not in user_data:
        user_data['totp_enabled'] = False
    if 'totp_backup_codes' not in user_data:
        user_data['totp_backup_codes'] = []
    if 'totp_setup_at' not in user_data:
        user_data['totp_setup_at'] = None
    # Ensure PIN reset notification field exists
    if 'pin_reset_notification' not in user_data:
        user_data['pin_reset_notification'] = None
    # Ensure force_pin_change field exists
    if 'force_pin_change' not in user_data:
        user_data['force_pin_change'] = False
    # Ensure temp_pin and temp_pin_expiry fields exist
    if 'temp_pin' not in user_data:
        user_data['temp_pin'] = None
    if 'temp_pin_expiry' not in user_data:
        user_data['temp_pin_expiry'] = None
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
for f in [USERS_FILE, ORDERS_FILE, CLEARED_ORDERS_FILE, ACTIVITY_LOG_FILE, TIMESHEET_FILE, ITEMS_FILE, TAX_CONFIG_FILE, DISCOUNTS_FILE, ORDER_COUNTER_FILE, TABLES_FILE, INVENTORY_FILE, REFUNDED_ORDERS_FILE, FAVORITES_FILE, LOYALTY_FILE, SCHEDULED_PRICING_FILE, WASTE_FILE, DELIVERY_ADDRESSES_FILE, WEBHOOKS_FILE, TABLE_ADS_FILE, CASH_DRAWER_FILE, COMBOS_FILE, SERVICE_CHARGE_FILE, EMAIL_CONFIG_FILE, SHIFT_FILE, TICKETS_FILE, APPROVALS_FILE, RESTAURANT_CONFIG_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as file:
            if f == USERS_FILE:
                json.dump({"1111": {"name": "Owner", "role": "owner", "permissions": ["*"]}}, file)
            elif f == TIMESHEET_FILE or f == ACTIVITY_LOG_FILE or f == SHIFT_FILE or f == APPROVALS_FILE:
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
            elif f == RESTAURANT_CONFIG_FILE:
                json.dump({"name": "Our Restaurant", "hours_today": "Mon-Fri: 11:00 AM - 10:00 PM", "wifi_name": "Guest WiFi", "wifi_password": ""}, file, indent=4)  # Initialize restaurant config
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
            if filepath in [ORDERS_FILE, CLEARED_ORDERS_FILE, ACTIVITY_LOG_FILE, TIMESHEET_FILE, TICKETS_FILE] and not isinstance(data, list):
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
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)


# --- Platform / Multi-Tenant Helpers ---

def load_businesses():
    """Load the businesses registry from data/global/businesses.json."""
    return load_json_data(BUSINESSES_FILE)


def save_businesses(data):
    """Save the businesses registry."""
    if not isinstance(data, dict):
        data = {}
    save_json_data(BUSINESSES_FILE, data)


def load_super_admins():
    """Load super admin accounts from data/global/super_admins.json."""
    return load_json_data(SUPER_ADMINS_FILE)


def save_super_admins(data):
    """Save super admin accounts."""
    if not isinstance(data, dict):
        data = {}
    save_json_data(SUPER_ADMINS_FILE, data)


def verify_super_admin(pin):
    """Check if a PIN belongs to a super admin. Returns the user dict or None."""
    supers = load_super_admins()
    if pin in supers:
        return supers[pin]
    return None


def get_business_context():
    """Get the current business context from session.
    Returns dict with 'business_id', 'location_id' or None if not in a business context.
    This is a stub — full tenant-aware middleware will be implemented in the next task."""
    # For now, return None (no business context = legacy single-tenant mode)
    # In the future, this will extract business_id from the request/session
    return None


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
        'ip_address': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', ''),
        'details': details if details is not None else {}
    }
    logs = load_json_data(ACTIVITY_LOG_FILE)
    logs.append(log_entry)
    save_json_data(ACTIVITY_LOG_FILE, logs)


def log_security_event(severity, category, summary, detail=None, affected_user=None, affected_user_name=None, related_event=None):
    """Log a security event to security_events.json (append-only).
    
    Args:
        severity: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'
        category: event category (e.g., 'authentication', 'access_control', 'data_integrity')
        summary: short description of the event
        detail: optional longer description
        affected_user: optional user PIN affected
        affected_user_name: optional user name affected
        related_event: optional related event ID
    Returns:
        The event dict that was logged (with assigned ID)
    """
    events = load_json_data(SECURITY_EVENTS_FILE)
    if not isinstance(events, list):
        events = []
    # Generate event ID
    event_num = len(events) + 1
    event_id = f"SEC-{event_num:03d}"
    # Make sure ID is unique (in case of gaps/deletions)
    existing_ids = {e.get('id') for e in events if e.get('id')}
    while event_id in existing_ids:
        event_num += 1
        event_id = f"SEC-{event_num:03d}"
    
    event = {
        'id': event_id,
        'created_at': datetime.now().isoformat(),
        'severity': severity.upper() if severity else 'LOW',
        'category': category,
        'status': 'unresolved',
        'summary': summary,
        'detail': detail or summary,
        'affected_user': affected_user,
        'affected_user_name': affected_user_name,
        'related_event': related_event,
        'reported_by': 'IP Blocklist Manager',
        'resolved_at': None,
        'resolution': None
    }
    events.append(event)
    save_json_data(SECURITY_EVENTS_FILE, events)
    return event


# ══════════════════════════════════════════════
# Anomaly Detection Engine
# ══════════════════════════════════════════════

def check_anomalies_after_login(user_id, user_name, client_ip):
    """Check for anomalies after a successful login.
    
    Checks:
    1. Off-hours login — login between anomaly_hours_start and anomaly_hours_end
    2. New IP for user — user logs in from an IP they've never used before
    3. Simultaneous logins — same user logged in from 2 different IPs
    """
    now = datetime.now()
    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}
    
    # 1. Off-hours login check
    try:
        ah_start = config.get('anomaly_hours_start', '22:00')
        ah_end = config.get('anomaly_hours_end', '06:00')
        current_time_str = now.strftime('%H:%M')
        start_h, start_m = map(int, ah_start.split(':'))
        end_h, end_m = map(int, ah_end.split(':'))
        current_h, current_m = map(int, current_time_str.split(':'))
        current_minutes = current_h * 60 + current_m
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        
        is_off_hours = False
        if start_minutes > end_minutes:
            # Range crosses midnight (e.g., 22:00-06:00)
            if current_minutes >= start_minutes or current_minutes <= end_minutes:
                is_off_hours = True
        else:
            # Same-day range
            if start_minutes <= current_minutes <= end_minutes:
                is_off_hours = True
        
        if is_off_hours:
            log_security_event(
                'MEDIUM', 'anomaly',
                f"⚠️ Off-hours login: {user_name} ({user_id}) at {current_time_str}",
                detail=f"User {user_name} (PIN {user_id}) logged in during off-hours ({ah_start}–{ah_end}) from IP {client_ip}.",
                affected_user=user_id, affected_user_name=user_name
            )
    except (ValueError, TypeError):
        pass
    
    # 2. New IP for user check
    known_ips = user_known_ips[user_id]
    if client_ip not in known_ips:
        if known_ips:  # Only flag if we have seen this user before
            log_security_event(
                'MEDIUM', 'anomaly',
                f"🆕 New IP for {user_name} ({user_id}): {client_ip}",
                detail=f"User {user_name} logged in from new IP {client_ip}. Previously seen: {', '.join(known_ips)}.",
                affected_user=user_id, affected_user_name=user_name
            )
        known_ips.add(client_ip)
    else:
        known_ips.add(client_ip)
    
    # 3. Simultaneous logins check
    sessions = user_login_sessions[user_id]
    now_ts = now.timestamp()
    # Purge sessions older than 1 hour
    sessions[:] = [(ip, ts) for ip, ts in sessions if now_ts - ts < 3600]
    # Check for different IPs in last hour
    other_ips = set(ip for ip, ts in sessions if ip != client_ip and now_ts - ts < 3600)
    if other_ips:
        log_security_event(
            'HIGH', 'anomaly',
            f"🔄 Simultaneous logins: {user_name} ({user_id}) from {client_ip} and {', '.join(other_ips)}",
            detail=f"User was already active from IP(s): {', '.join(other_ips)} and now also from {client_ip}.",
            affected_user=user_id, affected_user_name=user_name
        )
    sessions.append((client_ip, now_ts))


def check_anomalies_after_order(user_id, order_total, item_count):
    """Check for anomalies after order submission.
    
    Checks:
    1. Rapid orders — N+ orders in M minutes from same user
    2. Large order — single order over configurable threshold
    """
    now = datetime.now()
    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}
    
    rapid_threshold = config.get('rapid_order_threshold', 10)
    rapid_window = config.get('rapid_order_window_minutes', 5)
    large_threshold = config.get('max_order_total', 500)
    
    # 1. Rapid orders check
    with _lock_for_order_tracker:
        tracker = user_order_tracker[user_id]
        if tracker['window_start'] is None or (now - tracker['window_start']).total_seconds() > rapid_window * 60:
            tracker['window_start'] = now
            tracker['count'] = 0
            tracker['total'] = 0.0
        tracker['count'] += 1
        tracker['total'] += float(order_total)
        if tracker['count'] >= rapid_threshold:
            log_security_event(
                'MEDIUM', 'anomaly',
                f"⚡ Rapid orders: {user_id} — {tracker['count']} orders in {rapid_window} min (${tracker['total']:.2f})",
                detail=f"User PIN {user_id} submitted {tracker['count']} orders totaling ${tracker['total']:.2f} within {rapid_window} minutes.",
                affected_user=user_id
            )
            tracker['count'] = 0  # Avoid repeat flags
    
    # 2. Large order check
    if float(order_total) > large_threshold:
        users = load_json_data(USERS_FILE)
        name = users.get(user_id, {}).get('name', user_id) if isinstance(users, dict) else user_id
        log_security_event(
            'LOW', 'anomaly',
            f"💰 Large order: ${float(order_total):.2f} by {name} ({user_id})",
            detail=f"Order with {item_count} items totaling ${float(order_total):.2f}. Threshold: ${large_threshold:.2f}.",
            affected_user=user_id, affected_user_name=name
        )


def get_anomaly_event_counts():
    """Return counts of unresolved anomaly events by severity."""
    events = load_json_data(SECURITY_EVENTS_FILE)
    if not isinstance(events, list):
        return {'total': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    counts = {'total': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for e in events:
        if e.get('category') == 'anomaly' and e.get('status') == 'unresolved':
            sev = e.get('severity', 'LOW').upper()
            if sev in counts:
                counts[sev] += 1
            counts['total'] += 1
    return counts


# ══════════════════════════════════════════════
# Session Management Helpers
# ══════════════════════════════════════════════

def create_user_session(user_id, user_name, role, client_ip, user_agent='', device_info=''):
    """Create a new session token for a user and store it in active_user_sessions.
    Returns the session token string."""
    token = secrets.token_hex(32)
    now = datetime.now()
    session = {
        'token': token,
        'user_id': user_id,
        'user_name': user_name,
        'role': role,
        'ip': client_ip,
        'user_agent': user_agent,
        'device_info': device_info,
        'login_time': now.isoformat(),
        'last_active': now.isoformat()
    }
    active_user_sessions[user_id][token] = session
    return token


def cleanup_user_sessions(user_id, keep_token=None):
    """Remove expired sessions for a user. If keep_token is provided, that session is preserved.
    Returns the count of remaining sessions."""
    now = datetime.now()
    sessions = active_user_sessions.get(user_id, {})
    expired_tokens = []
    for token, session in sessions.items():
        if keep_token and token == keep_token:
            continue
        # Check idle expiry (24h since last_active)
        last_active = session.get('last_active')
        if last_active:
            try:
                last_active_dt = datetime.fromisoformat(last_active)
                if now - last_active_dt > timedelta(hours=SESSION_IDLE_HOURS):
                    expired_tokens.append(token)
                    continue
            except (ValueError, TypeError):
                expired_tokens.append(token)
                continue
        # Check active expiry (8h since login)
        login_time = session.get('login_time')
        if login_time:
            try:
                login_dt = datetime.fromisoformat(login_time)
                if now - login_dt > timedelta(hours=SESSION_ACTIVE_HOURS):
                    expired_tokens.append(token)
            except (ValueError, TypeError):
                expired_tokens.append(token)
    for t in expired_tokens:
        del sessions[t]
    return len(sessions)


def get_active_sessions(user_id=None):
    """Return all active (non-expired) sessions. If user_id is given, only for that user.
    Returns list of session dicts sorted by login_time descending."""
    now = datetime.now()
    result = []
    users_to_check = [user_id] if user_id else list(active_user_sessions.keys())
    for uid in users_to_check:
        sessions = active_user_sessions.get(uid, {})
        for token, session in sessions.items():
            # Skip expired
            try:
                last_active = session.get('last_active')
                if last_active:
                    last_active_dt = datetime.fromisoformat(last_active)
                    if now - last_active_dt > timedelta(hours=SESSION_IDLE_HOURS):
                        continue
                login_time = session.get('login_time')
                if login_time:
                    login_dt = datetime.fromisoformat(login_time)
                    if now - login_dt > timedelta(hours=SESSION_ACTIVE_HOURS):
                        continue
            except (ValueError, TypeError):
                pass
            result.append(dict(session))
    # Sort by login_time descending
    result.sort(key=lambda s: s.get('login_time', ''), reverse=True)
    return result


def logout_session(user_id, token):
    """Remove a specific session for a user. Returns True if found and removed."""
    sessions = active_user_sessions.get(user_id, {})
    if token in sessions:
        del sessions[token]
        return True
    return False


def logout_all_sessions(user_id, except_token=None):
    """Remove all sessions for a user, optionally keeping one.
    Returns count of sessions removed."""
    sessions = active_user_sessions.get(user_id, {})
    removed = 0
    tokens_to_remove = list(sessions.keys())
    for token in tokens_to_remove:
        if except_token and token == except_token:
            continue
        del sessions[token]
        removed += 1
    return removed


def check_get_auth(admin_pin, permission):
    """Check authentication for GET endpoints that pass adminPin as query param.
    Returns (user_data, None) on success, or (None, (response, status_code)) on failure."""
    if not admin_pin:
        return None, (jsonify({'message': 'Authentication required.'}), 401)
    if not check_perm(admin_pin, permission):
        log_activity('unauthorized_access', admin_pin, 'unknown',
                     {'status': 'denied', 'reason': f'Missing {permission} permission',
                      'endpoint': request.path})
        return None, (jsonify({'message': 'Insufficient permissions.'}), 403)
    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return None, (jsonify({'message': 'Unauthorized.'}), 403)
    return users[admin_pin], None


def get_timesheet_config():
    """Load timesheet config with defaults."""
    defaults = {
        'overtime_daily_threshold': 8,   # hours per day before OT kicks in
        'overtime_weekly_threshold': 40, # hours per week before OT kicks in
        'late_grace_minutes': 5,
        'max_staff_off_per_day': 3,      # max employees off same day before warning
        'offsite_backup': {
            'enabled': False,
            'host': '',
            'path': '',
            'ssh_key': ''
        }
    }
    try:
        config = load_json_data(TIMESHEET_CONFIG_FILE)
        if not isinstance(config, dict):
            config = defaults
        for k, v in defaults.items():
            if k not in config:
                config[k] = v
        return config
    except (FileNotFoundError, json.JSONDecodeError):
        save_json_data(TIMESHEET_CONFIG_FILE, defaults)
        return dict(defaults)


def save_timesheet_config(config):
    """Save timesheet config (ensure all keys present)."""
    defaults = {
        'overtime_daily_threshold': 8,
        'overtime_weekly_threshold': 40,
        'late_grace_minutes': 5,
        'max_staff_off_per_day': 3,
        'offsite_backup': {
            'enabled': False,
            'host': '',
            'path': '',
            'ssh_key': ''
        }
    }
    for k, v in defaults.items():
        if k not in config:
            config[k] = v
    save_json_data(TIMESHEET_CONFIG_FILE, config)



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


@socketio.on('tablet_call_server')
def handle_tablet_call_server(data):
    """Tablet customer pressed 'Call Server' — notify all staff clients."""
    table_number = data.get('table_number', 'Unknown')
    timestamp = datetime.now().isoformat()
    socketio.emit('server_call', {'table_number': table_number, 'timestamp': timestamp})


# In-memory storage for active admin sessions (for timesheet calculation)
active_admin_sessions = {}  # {admin_id: login_time}

# In-memory storage for employee clock-in/clock-out shifts
active_shifts = {}  # {user_id: {clock_in_time: datetime, user_name: str}}
clock_lock = threading.Lock()  # Prevents race conditions on clock-in/out operations

# In-memory 2FA rate limiting — resets on server restart
twofa_failed_attempts = {}  # {user_id: {'count': int, 'lock_until': datetime or None, 'window_start': datetime}}

# In-memory PIN login attempt tracking — resets on server restart
# Structure: {user_id: {'count': int, 'lock_until': datetime or None, 'window_start': datetime}}
login_failed_attempts = {}

# In-memory clock in/out attempt tracking — resets on server restart
# Structure: {ip_or_user_id: {'count': int, 'lock_until': datetime or None, 'window_start': datetime}}
clock_failed_attempts = {}

# ─── Discord Alert Support ─────────────────────────────────────────
# Sends formatted alert messages to a Discord webhook (if configured).
# Used for security events like account lockouts.
DISCORD_ALERT_COOLDOWN = {}  # {key: last_sent} — prevent spam

def send_discord_alert(message, level='warning'):
    """Send a message to the configured Discord webhook.
    Returns True if sent, False if no webhook configured or on failure.
    Level is used for embed color: warning=orange, danger=red, info=green.
    """
    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        return False
    webhook_url = config.get('discord_webhook_url', '').strip()
    if not webhook_url:
        return False
    embed_color = {
        'danger': 0xe74c3c,
        'warning': 0xf39c12,
        'info': 0x2ecc71,
    }.get(level, 0xf39c12)
    payload = {
        'embeds': [{
            'title': '🔒 POS Security Alert',
            'description': message,
            'color': embed_color,
            'footer': {'text': f'POS System · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'}
        }]
    }
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(webhook_url, data=data,
            headers={'Content-Type': 'application/json'},
            method='POST')
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False

def send_discord_alert_async(message, level='warning'):
    """Fire Discord alert in a background thread (non-blocking)."""
    t = threading.Thread(target=send_discord_alert, args=(message, level), daemon=True)
    t.start()

def maybe_notify_lockout(user_id, user_name, user_role):
    """Send a one-time Discord notification about a user lockout.
    Uses a cooldown per user_id to avoid spamming on rapid retries.
    """
    now = datetime.now()
    last = DISCORD_ALERT_COOLDOWN.get(user_id)
    if last and (now - last).total_seconds() < 300:  # 5 min cooldown
        return
    DISCORD_ALERT_COOLDOWN[user_id] = now
    role_display = user_role or 'unknown'
    msg = f"🔒 **{user_name}** (`{user_id}`) locked out after 5 failed PIN attempts. Role: {role_display}. [Unlock in User Management]"
    send_discord_alert_async(msg, level='danger')

def _record_clock_failure(key):
    """Record a failed clock in/out attempt. Locks after 10 failures per 60s window for 15min."""
    now = datetime.now()
    if key not in clock_failed_attempts:
        clock_failed_attempts[key] = {'count': 0, 'lock_until': None, 'window_start': now}
    attempt = clock_failed_attempts[key]
    if attempt.get('window_start') and (now - attempt['window_start']).total_seconds() > 60:
        attempt['count'] = 0
        attempt['window_start'] = now
    attempt['count'] += 1
    if attempt['window_start'] is None:
        attempt['window_start'] = now
    if attempt['count'] >= 10:
        attempt['lock_until'] = now + timedelta(minutes=15)



def get_client_ip():
    """Get client IP from request, handling X-Forwarded-For for proxied requests."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def record_login_attempt(user_id, success, method, client_ip=None, details=None):
    """Record a login attempt to login_attempts.json (persistent).
    
    Args:
        user_id: The user ID/PIN that was attempted
        success: True if login succeeded, False if failed
        method: 'pin', 'password', 'temp_pin', '2fa', 'backup_code'
        client_ip: Client IP address (auto-detected if None)
        details: Optional dict with additional context (e.g. failure reason)
    """
    if client_ip is None:
        client_ip = get_client_ip()
    attempts = load_json_data(LOGIN_ATTEMPTS_FILE)
    if not isinstance(attempts, list):
        attempts = []
    attempts.append({
        'user_id': user_id,
        'ip': client_ip,
        'timestamp': datetime.now().isoformat(),
        'success': success,
        'user_agent': request.headers.get('User-Agent', ''),
        'method': method,
        'details': details or {}
    })
    # Cap at 10,000 entries to prevent unbounded growth (oldest trimmed)
    if len(attempts) > 10000:
        attempts = attempts[-5000:]
    save_json_data(LOGIN_ATTEMPTS_FILE, attempts)

    # --- Auto-block IP on repeated failed logins ---
    if not success:
        now = datetime.now()
        # Track per-IP failed attempts in memory
        if client_ip not in ip_failed_attempts:
            ip_failed_attempts[client_ip] = {'count': 0, 'window_start': now}
        ip_attempt = ip_failed_attempts[client_ip]
        # Reset window if outside the tracking window (default 5 min)
        if (now - ip_attempt['window_start']).total_seconds() > 300:
            ip_attempt['count'] = 0
            ip_attempt['window_start'] = now
        ip_attempt['count'] += 1

        # Check if IP should be auto-blocked
        config = load_json_data(SECURITY_CONFIG_FILE)
        if not isinstance(config, dict):
            config = {}
        threshold = config.get('auto_block_threshold', 5)
        duration_minutes = config.get('auto_block_duration_minutes', 60)

        if ip_attempt['count'] >= threshold:
            # Auto-block this IP
            blocked = config.get('blocked_ips', [])
            if not isinstance(blocked, list):
                blocked = []
            # Only auto-block if not already blocked
            already_blocked = False
            for entry in blocked:
                if isinstance(entry, dict) and entry.get('ip') == client_ip:
                    already_blocked = True
                    break
            if not already_blocked:
                blocked.append({
                    'ip': client_ip,
                    'reason': f'Auto-blocked after {ip_attempt["count"]} failed logins in 5 minutes',
                    'blocked_at': now.isoformat(),
                    'auto_blocked': True,
                    'permanent': False,
                    'auto_block_duration_minutes': duration_minutes
                })
                config['blocked_ips'] = blocked
                save_json_data(SECURITY_CONFIG_FILE, config)
                # Log security event
                log_security_event(
                    'HIGH',
                    'authentication',
                    f"IP {client_ip} auto-blocked after {ip_attempt['count']} failed logins",
                    detail=f"IP {client_ip} was automatically added to blocklist after {ip_attempt['count']} failed login attempts within 5 minutes. Block duration: {duration_minutes} minutes.",
                    affected_user=user_id
                )
                # Reset counter so we don't keep re-blocking
                ip_attempt['count'] = 0


# --- User Management Endpoints ---

@app.route('/api/users', methods=['GET'])
def get_users():
    # Require authentication — adminPin as query param, must have manage_users permission
    admin_pin = request.args.get('adminPin', '')
    if not admin_pin:
        log_activity('get_users', 'anonymous', 'unauthorized', {'status': 'failed', 'reason': 'Missing adminPin'})
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, "manage_users"):
        log_activity('get_users', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Insufficient permissions'})
        return jsonify({'message': 'Insufficient permissions.'}), 403
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
            'banned_reason': user_data.get('banned_reason', ''),
            'pay_rate': user_data.get('pay_rate', None),
            'scheduled_start': user_data.get('scheduled_start', None),
            'email': user_data.get('email', ''),
            'totp_enabled': user_data.get('totp_enabled', False),
            'pin_reset_notification': user_data.get('pin_reset_notification', None),
            'force_pin_change': user_data.get('force_pin_change', False),
            'failed_login_attempts': 0,
            'login_locked': False
        }
        # Enrich with in-memory failed login tracking
        if uid in login_failed_attempts:
            attempt_info = login_failed_attempts[uid]
            now = datetime.now()
            display_users[uid]['failed_login_attempts'] = attempt_info.get('count', 0)
            is_locked = attempt_info.get('lock_until') and now < attempt_info['lock_until']
            display_users[uid]['login_locked'] = is_locked
    return jsonify(display_users)


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('userId')
    username = data.get('username')
    password = data.get('password')
    users = load_json_data(USERS_FILE)
    client_ip = get_client_ip()
    now = datetime.now()

    def record_failed_login(uid, user_name=None, user_role=None):
        """Track failed login attempt, lock after 5. Returns (count, locked, retry_after)."""
        if uid not in login_failed_attempts:
            login_failed_attempts[uid] = {'count': 0, 'lock_until': None, 'window_start': now}
        attempt = login_failed_attempts[uid]
        # Reset window if >60s have passed
        if attempt.get('window_start') and (now - attempt['window_start']).total_seconds() > 60:
            attempt['count'] = 0
        attempt['count'] += 1
        if attempt['window_start'] is None:
            attempt['window_start'] = now
        locked = False
        retry_after = None
        if attempt['count'] >= 5:
            attempt['lock_until'] = now + timedelta(minutes=10)
            locked = True
            retry_after = 600
            # Fire Discord notification on lockout (non-blocking)
            # Try to enrich user info from the users dict (available via closure)
            if user_name is None or user_role is None:
                if uid in users:
                    u_info = users[uid]
                    user_name = user_name or u_info.get('name', uid)
                    user_role = user_role or u_info.get('role', 'unknown')
            display_name = user_name or uid
            maybe_notify_lockout(uid, display_name, user_role)
        return attempt['count'], locked, retry_after

    def check_lockout(uid):
        """Check if user is currently locked out. Returns (locked, retry_after) or (False, None)."""
        if uid in login_failed_attempts:
            attempt = login_failed_attempts[uid]
            if attempt.get('lock_until') and now < attempt['lock_until']:
                remaining = int((attempt['lock_until'] - now).total_seconds())
                return True, remaining
            # Clear lock if expired
            if attempt.get('lock_until') and now >= attempt['lock_until']:
                attempt['lock_until'] = None
                attempt['count'] = 0
        return False, None

    # Owner username+password login
    if username and password:
        for uid, u_data in users.items():
            if u_data.get('username') == username:
                stored_hash = u_data.get('password_hash')
                stored_salt = u_data.get('password_salt')
                if stored_hash and stored_salt and verify_password(password, stored_hash, stored_salt):
                    if u_data.get('banned', False):
                        reason = u_data.get('banned_reason', 'No reason provided')
                        record_login_attempt(uid, False, 'password', client_ip, {'reason': 'banned'})
                        return jsonify({'message': f'User is banned. Reason: {reason}', 'banned': True}), 403
                    # Clear failed attempts on success
                    if uid in login_failed_attempts:
                        del login_failed_attempts[uid]
                    u_data = upgrade_user(u_data)
                    # Check if 2FA is enabled — require 2FA challenge before issuing session
                    if u_data.get('totp_enabled', False):
                        log_activity('login', uid, u_data['role'], {'status': '2fa_required', 'method': 'password', 'user_name': u_data['name'], 'ip': client_ip})
                        record_login_attempt(uid, True, 'password', client_ip, {'status': '2fa_required'})
                        return jsonify({'2fa_required': True, 'user_id': uid, 'user_name': u_data['name']}), 200
                    users[uid] = u_data
                    save_json_data(USERS_FILE, users)
                    log_activity('login', uid, u_data['role'], {'status': 'success', 'method': 'password', 'user_name': u_data['name'], 'ip': client_ip})
                    record_login_attempt(uid, True, 'password', client_ip, {'status': 'success'})
                    if u_data['role'] in ('admin', 'owner'):
                        active_admin_sessions[uid] = datetime.now()

                    # Check for PIN reset notification (password login path)
                    pin_reset_info = None
                    force_change_required = False
                    if u_data.get('pin_reset_notification'):
                        notif = u_data['pin_reset_notification']
                        pin_reset_info = {
                            'message': f'⚠️ Your PIN was reset by {notif.get("reset_by_name", "Unknown")} on {notif.get("reset_at", "unknown")}. Reason: {notif.get("reason", "Not provided")}. Use your new PIN.',
                            'reset_by': notif.get('reset_by_name', 'Unknown'),
                            'reset_at': notif.get('reset_at', ''),
                            'reason': notif.get('reason', '')
                        }
                        users[uid]['pin_reset_notification'] = None

                    if u_data.get('force_pin_change', False):
                        force_change_required = True
                        users[uid]['force_pin_change'] = False

                    if pin_reset_info or force_change_required:
                        save_json_data(USERS_FILE, users)

                    # Create session token
                    user_agent = request.headers.get('User-Agent', '')
                    session_token = create_user_session(uid, u_data['name'], u_data['role'], client_ip, user_agent)

                    response_data = {
                        'message': 'Login successful',
                        'user': u_data['name'],
                        'role': u_data['role'],
                        'permissions': u_data.get('permissions', []),
                        'totp_enabled': u_data.get('totp_enabled', False),
                        'session_token': session_token
                    }
                    if pin_reset_info:
                        response_data['pin_reset_info'] = pin_reset_info
                    if force_change_required:
                        response_data['force_pin_change_required'] = True
                    try:
                        check_anomalies_after_login(uid, u_data['name'], client_ip)
                    except Exception:
                        pass
                    return jsonify(response_data)
                # Wrong password for this user
                break  # Username found but wrong password
        # Failed password login — log it
        log_activity('login_failed', username or user_id, 'unknown', {'status': 'failed', 'method': 'password', 'ip': client_ip})
        record_login_attempt(username or user_id, False, 'password', client_ip, {'reason': 'invalid_credentials'})
        return jsonify({'message': 'Invalid username or password'}), 401

    # PIN login (existing)
    # Check if user_id matches a temp_pin (temporary access code)
    temp_pin_user_id = None
    temp_pin_user_data = None
    if user_id not in users:
        # Scan for a user whose temp_pin matches the entered PIN
        for uid, u_data in users.items():
            u_data = upgrade_user(u_data)
            tp = u_data.get('temp_pin')
            tpe = u_data.get('temp_pin_expiry')
            if tp and str(tp) == str(user_id) and tpe:
                try:
                    expiry_dt = datetime.fromisoformat(tpe)
                    if datetime.now() < expiry_dt:
                        temp_pin_user_id = uid
                        temp_pin_user_data = u_data
                        break
                    else:
                        # Expired — clean up
                        u_data['temp_pin'] = None
                        u_data['temp_pin_expiry'] = None
                        save_json_data(USERS_FILE, users)
                except (ValueError, TypeError):
                    pass
    
    if temp_pin_user_id:
        # Log in via temp PIN
        user_id = temp_pin_user_id
        user_info = temp_pin_user_data
        users[user_id] = user_info
        # Clear the temp PIN (single-use)
        users[user_id]['temp_pin'] = None
        users[user_id]['temp_pin_expiry'] = None
        save_json_data(USERS_FILE, users)
        
        if user_info.get('banned', False):
            reason = user_info.get('banned_reason', 'No reason provided')
            log_activity('login', user_id, user_info.get('role', 'unknown'),
                         {'status': 'failed', 'reason': f'User is banned: {reason}', 'ip': client_ip})
            record_login_attempt(user_id, False, 'temp_pin', client_ip, {'reason': 'banned'})
            return jsonify({'message': f'User is banned. Reason: {reason}', 'banned': True}), 403
        
        if user_info.get('role') in ['user', 'admin', 'owner', 'cook']:
            # Clear failed attempts on successful temp PIN login
            if user_id in login_failed_attempts:
                del login_failed_attempts[user_id]
            # Check if 2FA is enabled
            if user_info.get('totp_enabled', False):
                log_activity('login', user_id, user_info['role'], {'status': '2fa_required', 'method': 'temp_pin', 'user_name': user_info['name'], 'ip': client_ip})
                record_login_attempt(user_id, True, 'temp_pin', client_ip, {'status': '2fa_required'})
                return jsonify({'2fa_required': True, 'user_id': user_id, 'user_name': user_info['name']}), 200
            
            log_activity('login', user_id, user_info['role'], {'status': 'success', 'method': 'temp_pin', 'user_name': user_info['name'], 'ip': client_ip})
            record_login_attempt(user_id, True, 'temp_pin', client_ip, {'status': 'success'})
            if user_info['role'] in ('admin', 'owner'):
                active_admin_sessions[user_id] = datetime.now()

            # Create session token
            user_agent = request.headers.get('User-Agent', '')
            session_token = create_user_session(user_id, user_info['name'], user_info['role'], client_ip, user_agent)

            response_data = {
                'message': 'Login successful (temporary PIN)',
                'user': user_info['name'],
                'role': user_info['role'],
                'permissions': user_info.get('permissions', []),
                'temp_pin_used': True,
                'totp_enabled': user_info.get('totp_enabled', False),
                'session_token': session_token
            }
            try:
                check_anomalies_after_login(user_id, user_info['name'], client_ip)
            except Exception:
                pass
            return jsonify(response_data)
        log_activity('login_failed', user_id, 'unknown', {'status': 'failed', 'method': 'temp_pin', 'ip': client_ip})
        record_login_attempt(user_id, False, 'temp_pin', client_ip, {'reason': 'invalid_role'})
        return jsonify({'message': 'Invalid User ID or role'}), 401

    if user_id in users:
        # --- Lockout check (PIN login) ---
        locked, retry_after = check_lockout(user_id)
        if locked:
            log_activity('login_failed', user_id, 'unknown', {'status': 'locked', 'reason': 'account_locked_10min', 'ip': client_ip})
            record_login_attempt(user_id, False, 'pin', client_ip, {'reason': 'account_locked'})
            return jsonify({
                'message': f'Account locked due to too many failed attempts. Try again in {retry_after} seconds.',
                'locked': True,
                'retry_after': retry_after
            }), 429

        user_info = users[user_id]
        user_info = upgrade_user(user_info)
        users[user_id] = user_info
        save_json_data(USERS_FILE, users)

        if user_info.get('banned', False):
            reason = user_info.get('banned_reason', 'No reason provided')
            log_activity('login', user_id, user_info.get('role', 'unknown'),
                         {'status': 'failed', 'reason': f'User is banned: {reason}', 'ip': client_ip})
            record_login_attempt(user_id, False, 'pin', client_ip, {'reason': 'banned'})
            return jsonify({'message': f'User is banned. Reason: {reason}', 'banned': True}), 403

        if user_info.get('role') in ['user', 'admin', 'owner', 'cook']:
            # Check if 2FA is enabled — require 2FA challenge before issuing session
            if user_info.get('totp_enabled', False):
                log_activity('login', user_id, user_info['role'], {'status': '2fa_required', 'method': 'pin', 'user_name': user_info['name'], 'ip': client_ip})
                record_login_attempt(user_id, True, 'pin', client_ip, {'status': '2fa_required'})
                return jsonify({'2fa_required': True, 'user_id': user_id, 'user_name': user_info['name']}), 200

            # Clear failed attempts on successful login
            if user_id in login_failed_attempts:
                del login_failed_attempts[user_id]

            log_activity('login', user_id, user_info['role'], {'status': 'success', 'method': 'pin', 'user_name': user_info['name'], 'ip': client_ip})
            record_login_attempt(user_id, True, 'pin', client_ip, {'status': 'success'})
            if user_info['role'] in ('admin', 'owner'):
                active_admin_sessions[user_id] = datetime.now()

            # Check for PIN reset notification
            pin_reset_info = None
            force_change_required = False
            if user_info.get('pin_reset_notification'):
                notif = user_info['pin_reset_notification']
                pin_reset_info = {
                    'message': f'⚠️ Your PIN was reset by {notif.get("reset_by_name", "Unknown")} on {notif.get("reset_at", "unknown")}. Reason: {notif.get("reason", "Not provided")}. Use your new PIN.',
                    'reset_by': notif.get('reset_by_name', 'Unknown'),
                    'reset_at': notif.get('reset_at', ''),
                    'reason': notif.get('reason', '')
                }
                users[user_id]['pin_reset_notification'] = None

            if user_info.get('force_pin_change', False):
                force_change_required = True
                users[user_id]['force_pin_change'] = False

            if pin_reset_info or force_change_required:
                save_json_data(USERS_FILE, users)

            # Create session token
            user_agent = request.headers.get('User-Agent', '')
            session_token = create_user_session(user_id, user_info['name'], user_info['role'], client_ip, user_agent)

            response_data = {
                'message': 'Login successful',
                'user': user_info['name'],
                'role': user_info['role'],
                'permissions': user_info.get('permissions', []),
                'totp_enabled': user_info.get('totp_enabled', False),
                'session_token': session_token
            }
            if pin_reset_info:
                response_data['pin_reset_info'] = pin_reset_info
            if force_change_required:
                response_data['force_pin_change_required'] = True
            try:
                check_anomalies_after_login(user_id, user_info['name'], client_ip)
            except Exception:
                pass
            return jsonify(response_data)

    # Record failed login attempt for PIN login
    failed_count, locked, retry_after = record_failed_login(user_id)
    log_activity('login_failed', user_id, 'unknown', {
        'status': 'failed', 'method': 'pin', 'ip': client_ip, 'attempt': failed_count
    })
    record_login_attempt(user_id, False, 'pin', client_ip, {'reason': 'invalid_pin', 'attempt': failed_count})
    if locked:
        return jsonify({
            'message': 'Too many failed attempts. Account locked for 10 minutes.',
            'locked': True,
            'retry_after': retry_after
        }), 429
    remaining = 5 - failed_count
    return jsonify({
        'message': f'Invalid User ID or role. {remaining} attempt(s) remaining.',
        'remaining_attempts': remaining
    }), 401


@app.route('/api/security/login_attempts', methods=['GET'])
def get_login_attempts():
    """Return login attempts from login_attempts.json. Requires manage_users permission.
    Supports optional query params: limit (default 100), user_id (filter by user).
    Used by the owner security dashboard."""
    admin_pin = request.args.get('adminPin', '')
    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    
    attempts = load_json_data(LOGIN_ATTEMPTS_FILE)
    if not isinstance(attempts, list):
        attempts = []
    
    # Filter by user_id if provided
    filter_user = request.args.get('user_id', '').strip()
    if filter_user:
        attempts = [a for a in attempts if a.get('user_id') == filter_user]
    
    # Apply limit (default 100, newest first)
    limit_str = request.args.get('limit', '100').strip()
    try:
        limit = max(1, min(5000, int(limit_str)))
    except (ValueError, TypeError):
        limit = 100
    
    # Return newest first
    attempts.reverse()
    attempts = attempts[:limit]
    
    return jsonify({
        'count': len(attempts),
        'attempts': attempts
    })


@app.route('/api/security/dashboard', methods=['POST'])
def security_dashboard():
    """Return security dashboard data: summary, recent events, blocked IPs, active sessions.
    Requires view_stats permission."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, "view_stats"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    # --- Load data ---
    attempts = load_json_data(LOGIN_ATTEMPTS_FILE)
    if not isinstance(attempts, list):
        attempts = []
    events = load_json_data(SECURITY_EVENTS_FILE)
    if not isinstance(events, list):
        events = []
    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # --- Summary stats ---
    total_today = 0
    failed_today = 0
    for a in attempts:
        try:
            ts = datetime.fromisoformat(a.get('timestamp', ''))
            if ts >= today_start:
                total_today += 1
                if not a.get('success'):
                    failed_today += 1
        except (ValueError, TypeError):
            pass

    blocked_ips = config.get('blocked_ips', [])
    open_events = [e for e in events if e.get('status') == 'unresolved']
    critical_events = [e for e in open_events if e.get('severity') in ('CRITICAL', 'HIGH')]

    # --- Recent login stream (newest 50) ---
    recent_attempts = list(reversed(attempts[-50:]))

    # --- Recent security events (newest 20) ---
    recent_events = list(reversed(events[-20:]))

    # --- Active sessions from in-memory tracking ---
    active_sessions_list = get_active_sessions()
    # Enrich with user names from users.json
    users = load_json_data(USERS_FILE)
    if not isinstance(users, dict):
        users = {}
    for s in active_sessions_list:
        uid = s.get('user_id', '')
        if uid in users:
            s['user_name'] = users[uid].get('name', s.get('user_name', ''))
        # Strip token from response for security
        s.pop('token', None)

    return jsonify({
        'summary': {
            'total_logins_today': total_today,
            'failed_logins_today': failed_today,
            'blocked_ips_count': len(blocked_ips),
            'open_events_count': len(open_events),
            'critical_events_count': len(critical_events),
            'active_sessions_count': len(active_sessions_list)
        },
        'recent_attempts': recent_attempts,
        'recent_events': recent_events,
        'blocked_ips': blocked_ips,
        'active_sessions': active_sessions_list,
        'anomaly_counts': get_anomaly_event_counts(),
        'config': config
    })


@app.route('/api/security/blocklist/add', methods=['POST'])
def security_blocklist_add():
    """Add an IP to the blocklist. Requires manage_users permission.
    Body: { adminPin, ip, reason?, permanent? }
    If permanent=true, the IP stays blocked until manually removed (no auto-expiry).
    """
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    ip_to_block = data.get('ip', '').strip()
    reason = data.get('reason', '').strip()
    permanent = data.get('permanent', False)
    
    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    if not ip_to_block:
        return jsonify({'message': 'IP address is required.'}), 400
    # Basic IP format validation
    import re
    if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip_to_block) and ip_to_block != '::1':
        return jsonify({'message': 'Invalid IP address format.'}), 400

    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}
    blocked = config.get('blocked_ips', [])
    if not isinstance(blocked, list):
        blocked = []

    # Check if already blocked
    for entry in blocked:
        if isinstance(entry, dict) and entry.get('ip') == ip_to_block:
            return jsonify({'message': 'IP is already in blocklist.', 'ip': ip_to_block}), 409
    
    blocked.append({
        'ip': ip_to_block,
        'reason': reason or 'Blocked by admin',
        'blocked_at': datetime.now().isoformat(),
        'auto_blocked': False,
        'permanent': permanent
    })
    config['blocked_ips'] = blocked
    save_json_data(SECURITY_CONFIG_FILE, config)

    # Log activity
    users = load_json_data(USERS_FILE)
    admin_name = users.get(admin_pin, {}).get('name', admin_pin) if isinstance(users, dict) else admin_pin
    log_activity('ip_blocked', admin_pin, admin_name, {'ip': ip_to_block, 'reason': reason, 'permanent': permanent})
    
    # Log security event
    log_security_event(
        'HIGH' if permanent else 'MEDIUM',
        'access_control',
        f"IP {ip_to_block} blocked by admin ({admin_name})",
        detail=f"IP {ip_to_block} was manually added to blocklist by {admin_name}. Reason: {reason or 'Not specified'}. Permanent: {permanent}",
        affected_user=admin_pin,
        affected_user_name=admin_name
    )

    return jsonify({'message': 'IP blocked successfully.', 'blocked_ips': blocked})


@app.route('/api/security/blocklist/allowlist', methods=['POST'])
def security_blocklist_allowlist():
    """Manage IP allowlist. Requires manage_users permission.
    Body: { adminPin, action: 'add'|'remove'|'set'|'get', ip?, ips? }
    If allowlist is non-empty, ONLY those IPs can access the system.
    """
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    action = data.get('action', 'get')
    
    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}
    
    ip_allowlist = config.get('ip_allowlist', [])
    if not isinstance(ip_allowlist, list):
        ip_allowlist = []

    users = load_json_data(USERS_FILE)
    admin_name = users.get(admin_pin, {}).get('name', admin_pin) if isinstance(users, dict) else admin_pin

    if action == 'add':
        ip_to_add = data.get('ip', '').strip()
        if not ip_to_add:
            return jsonify({'message': 'IP address is required.'}), 400
        if ip_to_add not in ip_allowlist:
            ip_allowlist.append(ip_to_add)
            config['ip_allowlist'] = ip_allowlist
            save_json_data(SECURITY_CONFIG_FILE, config)
            log_activity('allowlist_add', admin_pin, admin_name, {'ip': ip_to_add})
        return jsonify({'message': 'IP added to allowlist.', 'ip_allowlist': ip_allowlist})

    elif action == 'remove':
        ip_to_remove = data.get('ip', '').strip()
        if not ip_to_remove:
            return jsonify({'message': 'IP address is required.'}), 400
        if ip_to_remove in ip_allowlist:
            ip_allowlist.remove(ip_to_remove)
            config['ip_allowlist'] = ip_allowlist
            save_json_data(SECURITY_CONFIG_FILE, config)
            log_activity('allowlist_remove', admin_pin, admin_name, {'ip': ip_to_remove})
        return jsonify({'message': 'IP removed from allowlist.', 'ip_allowlist': ip_allowlist})

    elif action == 'set':
        ips = data.get('ips', [])
        if not isinstance(ips, list):
            return jsonify({'message': 'ips must be an array.'}), 400
        config['ip_allowlist'] = ips
        save_json_data(SECURITY_CONFIG_FILE, config)
        log_activity('allowlist_set', admin_pin, admin_name, {'count': len(ips)})
        return jsonify({'message': f'Allowlist set to {len(ips)} IPs.', 'ip_allowlist': ips})

    # action == 'get'
    return jsonify({'ip_allowlist': ip_allowlist})


@app.route('/api/security/unblock_ip', methods=['POST'])
def security_unblock_ip():
    """Remove an IP from the blocklist. Requires manage_users permission."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    ip_to_unblock = data.get('ip', '').strip()
    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    if not ip_to_unblock:
        return jsonify({'message': 'IP address is required.'}), 400

    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}
    blocked = config.get('blocked_ips', [])
    found = False
    for b in list(blocked):
        if b.get('ip') == ip_to_unblock:
            blocked.remove(b)
            found = True
    if not found:
        return jsonify({'message': 'IP was not in blocklist.'}), 404

    config['blocked_ips'] = blocked
    save_json_data(SECURITY_CONFIG_FILE, config)

    # Log the activity
    users = load_json_data(USERS_FILE)
    admin_name = users.get(admin_pin, {}).get('name', admin_pin) if isinstance(users, dict) else admin_pin
    log_activity('ip_unblocked', admin_pin, admin_name, {'ip': ip_to_unblock, 'action': 'unblocked'})
    
    # Log security event for unblock
    log_security_event(
        'LOW',
        'access_control',
        f"IP {ip_to_unblock} unblocked by admin ({admin_name})",
        detail=f"IP {ip_to_unblock} was removed from blocklist by {admin_name}.",
        affected_user=admin_pin,
        affected_user_name=admin_name
    )

    return jsonify({'message': 'IP unblocked successfully.', 'blocked_ips': blocked})


@app.route('/api/security/block_user', methods=['POST'])
def security_block_user():
    """Block a user account and invalidate all sessions. Requires ban_users permission.
    Body: { adminPin, userId, reason (optional) }
    Sets banned=true + banned_reason, removes from active_admin_sessions."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    user_id = str(data.get('userId', ''))
    reason = data.get('reason', '').strip() or 'No reason provided'

    if not admin_pin or not user_id:
        return jsonify({'message': 'Missing required fields: adminPin, userId.'}), 400
    if not check_perm(admin_pin, "ban_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)
    if not isinstance(users, dict):
        return jsonify({'message': 'Users data not found.'}), 500
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    users[user_id]['banned'] = True
    users[user_id]['banned_reason'] = reason
    save_json_data(USERS_FILE, users)

    # Invalidate all sessions for this user
    if user_id in active_admin_sessions:
        del active_admin_sessions[user_id]

    admin_data = users.get(admin_pin, {})
    admin_name = admin_data.get('name', admin_pin)
    log_activity('user_blocked', admin_pin, admin_data.get('role', 'unknown'), {
        'blocked_user_id': user_id,
        'blocked_user_name': users[user_id].get('name', ''),
        'reason': reason,
        'sessions_cleared': True
    })
    
    log_security_event(
        'HIGH',
        'access_control',
        f"User {users[user_id].get('name', user_id)} blocked by admin ({admin_name})",
        detail=f"User {user_id} ({users[user_id].get('name', '')}) was blocked. Reason: {reason}. All sessions invalidated.",
        affected_user=user_id,
        affected_user_name=users[user_id].get('name', '')
    )

    return jsonify({'message': f'User {user_id} blocked successfully. Sessions invalidated.', 'userId': user_id, 'reason': reason})


@app.route('/api/security/unblock_user', methods=['POST'])
def security_unblock_user():
    """Unblock a user account. Requires ban_users permission.
    Body: { adminPin, userId }
    Removes banned and banned_reason flags."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    user_id = str(data.get('userId', ''))

    if not admin_pin or not user_id:
        return jsonify({'message': 'Missing required fields: adminPin, userId.'}), 400
    if not check_perm(admin_pin, "ban_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)
    if not isinstance(users, dict):
        return jsonify({'message': 'Users data not found.'}), 500
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    if 'banned' in users[user_id]:
        del users[user_id]['banned']
    if 'banned_reason' in users[user_id]:
        del users[user_id]['banned_reason']
    save_json_data(USERS_FILE, users)

    admin_data = users.get(admin_pin, {})
    admin_name = admin_data.get('name', admin_pin)
    log_activity('user_unblocked', admin_pin, admin_data.get('role', 'unknown'), {
        'unblocked_user_id': user_id,
        'unblocked_user_name': users[user_id].get('name', '')
    })

    log_security_event(
        'MEDIUM',
        'access_control',
        f"User {users[user_id].get('name', user_id)} unblocked by admin ({admin_name})",
        detail=f"User {user_id} ({users[user_id].get('name', '')}) was unblocked.",
        affected_user=user_id,
        affected_user_name=users[user_id].get('name', '')
    )

    return jsonify({'message': f'User {user_id} unblocked successfully.', 'userId': user_id})


@app.route('/api/security/force_logout', methods=['POST'])
def security_force_logout():
    """Force logout a user by ending all their active sessions without banning them.
    Requires manage_users permission.
    Body: { adminPin, userId }
    Removes user from active_admin_sessions."""
    data = request.json or {}
    admin_pin = data.get('adminPin', '')
    user_id = str(data.get('userId', ''))

    if not admin_pin or not user_id:
        return jsonify({'message': 'Missing required fields: adminPin, userId.'}), 400
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    users = load_json_data(USERS_FILE)
    if not isinstance(users, dict):
        return jsonify({'message': 'Users data not found.'}), 500
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    had_session = user_id in active_admin_sessions
    if had_session:
        del active_admin_sessions[user_id]

    admin_data = users.get(admin_pin, {})
    user_name = users[user_id].get('name', user_id)
    log_activity('force_logout', admin_pin, admin_data.get('role', 'unknown'), {
        'target_user_id': user_id,
        'target_user_name': user_name,
        'had_active_session': had_session
    })

    log_security_event(
        'MEDIUM',
        'access_control',
        f"Force logout for {user_name} by admin",
        detail=f"Admin forced logout for user {user_id} ({user_name}). Had session: {had_session}.",
        affected_user=user_id,
        affected_user_name=user_name
    )

    return jsonify({
        'message': f'User {user_name} logged out successfully.',
        'userId': user_id,
        'had_active_session': had_session
    })


# ─── Discord Webhook Config ────────────────────────────────────────

@app.route('/api/security/discord_webhook', methods=['POST'])
def security_discord_webhook():
    """Get or set the Discord webhook URL for alert notifications.
    POST with { adminPin, url } to set. POST with { adminPin } to read.
    Requires manage_users permission.
    """
    data = request.json or {}
    admin_pin = data.get('adminPin', '')

    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, 'manage_users'):
        return jsonify({'message': 'Permission denied.'}), 403

    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {}

    url = data.get('url')
    if url is not None:
        # Set mode
        config['discord_webhook_url'] = str(url).strip()
        save_json_data(SECURITY_CONFIG_FILE, config)
        admin_data = load_json_data(USERS_FILE).get(admin_pin, {})
        log_activity('discord_webhook_set', admin_pin, admin_data.get('role', 'unknown'), {
            'has_url': bool(config['discord_webhook_url'])
        })
        return jsonify({'message': 'Discord webhook URL updated.', 'set': True})

    # Get mode — return the URL (masked)
    stored = config.get('discord_webhook_url', '')
    display = stored[:20] + '••••' if len(stored) > 24 else ('(not set)' if not stored else stored)
    return jsonify({
        'discord_webhook_url': stored,
        'display': display,
        'is_set': bool(stored)
    })


@app.route('/api/security/lockout_state', methods=['POST'])
def security_lockout_state():
    """Return current lockout state for the frontend banner.
    POST with { adminPin }. Returns list of currently locked-out users.
    """
    data = request.json or {}
    admin_pin = data.get('adminPin', '')

    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, 'manage_users'):
        return jsonify({'message': 'Permission denied.'}), 403

    now = datetime.now()
    users = load_json_data(USERS_FILE)
    if not isinstance(users, dict):
        users = {}

    locked_users = []
    for uid, attempt in login_failed_attempts.items():
        lock_until = attempt.get('lock_until')
        if lock_until and now < lock_until:
            user_data = users.get(uid, {})
            locked_users.append({
                'user_id': uid,
                'user_name': user_data.get('name', uid),
                'role': user_data.get('role', 'unknown'),
                'locked_until': lock_until.isoformat(),
                'retry_after': int((lock_until - now).total_seconds())
            })

    return jsonify({
        'locked_count': len(locked_users),
        'locked_users': locked_users
    })


@app.route('/api/security/test_discord_webhook', methods=['POST'])
def security_test_discord_webhook():
    """Send a test message to the configured Discord webhook.
    POST with { adminPin }. Requires manage_users permission.
    """
    data = request.json or {}
    admin_pin = data.get('adminPin', '')

    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, 'manage_users'):
        return jsonify({'message': 'Permission denied.'}), 403

    config = load_json_data(SECURITY_CONFIG_FILE)
    if not isinstance(config, dict) or not config.get('discord_webhook_url', '').strip():
        return jsonify({'message': 'No Discord webhook URL configured.'}), 400

    sent = send_discord_alert(
        "🧪 **Test Alert** — This is a test message from your POS system security alert system.\nIf you see this, the webhook is configured correctly.",
        level='info'
    )
    if sent:
        return jsonify({'message': 'Test message sent to Discord successfully.'})
    else:
        return jsonify({'message': 'Failed to send test message. Check the webhook URL.'}), 500


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
    """Check if owner has set credentials. Requires manage_users permission."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_users")
    if err_response:
        return err_response
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


@app.route('/api/auth/2fa/setup', methods=['POST'])
def twofa_setup():
    """User requests to enable 2FA. Generates a TOTP secret and returns provisioning URI + QR code data URI."""
    data = request.json
    user_id = str(data.get('userId', ''))

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = upgrade_user(users[user_id])

    # Check if 2FA is already enabled
    if user_data.get('totp_enabled', False):
        return jsonify({'message': '2FA already enabled — disable first.'}), 409

    # Generate a new TOTP secret
    secret = pyotp.random_base32()
    user_name = user_data.get('name', 'User')
    issuer = 'POS System'

    # Create provisioning URI for authenticator app
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user_name, issuer_name=issuer)

    # Generate QR code as a base64 data URI
    qr = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')

    # Store the secret (but totp_enabled stays False until verified)
    user_data['totp_secret'] = secret
    users[user_id] = user_data
    save_json_data(USERS_FILE, users)

    log_activity('2fa_setup_initiated', user_id, user_data.get('role', 'unknown'),
                 {'status': 'secret_generated', 'totp_secret_length': len(secret)})

    return jsonify({
        'secret': secret,
        'provisioning_uri': provisioning_uri,
        'qr_data_uri': qr_data_uri,
        'issuer': issuer,
        'user_name': user_name
    })


@app.route('/api/auth/2fa/verify', methods=['POST'])
def twofa_verify():
    """User submits a 6-digit TOTP code to confirm 2FA setup.
    If valid: enables 2FA, generates 8 backup codes, returns them."""
    data = request.json
    user_id = str(data.get('userId', ''))
    code = data.get('code', '')

    if not user_id or not code:
        return jsonify({'message': 'User ID and verification code are required.'}), 400

    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return jsonify({'message': 'Invalid code format. Must be 6 digits.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = upgrade_user(users[user_id])

    # Check if 2FA is already enabled
    if user_data.get('totp_enabled', False):
        return jsonify({'message': '2FA is already enabled.'}), 409

    secret = user_data.get('totp_secret')
    if not secret:
        return jsonify({'message': '2FA not initialized. Call /api/auth/2fa/setup first.'}), 400

    # Validate the TOTP code
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        log_activity('2fa_verify_failed', user_id, user_data.get('role', 'unknown'),
                     {'status': 'invalid_code'})
        return jsonify({'message': 'Invalid code. Try again.'}), 400

    # Code is valid — generate 8 backup codes
    backup_codes = []
    hashed_codes = []
    for _ in range(8):
        plain_code = secrets.token_hex(5).upper()  # 10-char alphanumeric
        backup_codes.append(plain_code)
        hashed_codes.append(hashlib.sha256(plain_code.encode()).hexdigest())

    # Enable 2FA
    user_data['totp_enabled'] = True
    user_data['totp_backup_codes'] = hashed_codes
    user_data['totp_setup_at'] = datetime.now().isoformat()
    users[user_id] = user_data
    save_json_data(USERS_FILE, users)

    log_activity('2fa_verify_success', user_id, user_data.get('role', 'unknown'),
                 {'status': 'enabled', 'backup_codes_count': len(backup_codes)})

    return jsonify({
        'message': '2FA enabled successfully.',
        'backup_codes': backup_codes,
        'backup_codes_count': len(backup_codes),
        'warn': 'Save these backup codes now. They will never be shown again. Store them somewhere safe.'
    })


@app.route('/api/auth/2fa/verify_login', methods=['POST'])
def twofa_verify_login():
    """Validate TOTP code during login when 2FA is enabled.
    If valid: issues the session (same as normal login response).
    Rate-limited: max 5 attempts per rolling 60-second window, then locked for 15 minutes."""
    data = request.json
    user_id = str(data.get('userId', ''))
    code = data.get('code', '')

    if not user_id or not code:
        return jsonify({'message': 'User ID and verification code are required.'}), 400

    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return jsonify({'message': 'Invalid code format. Must be 6 digits.'}), 400

    now = datetime.now()

    # --- Rate limit check ---
    if user_id in twofa_failed_attempts:
        attempt = twofa_failed_attempts[user_id]
        # Check if currently locked
        if attempt.get('lock_until') and now < attempt['lock_until']:
            remaining_seconds = int((attempt['lock_until'] - now).total_seconds())
            log_activity('2fa_login_rate_limited', user_id, 'unknown', {'reason': 'account_locked', 'remaining_seconds': remaining_seconds})
            return jsonify({
                'message': f'Too many failed attempts. Account locked for {remaining_seconds} more seconds.',
                'locked': True,
                'retry_after': remaining_seconds
            }), 429
        # Reset window if more than 60 seconds have passed since window_start
        if attempt.get('window_start') and (now - attempt['window_start']).total_seconds() > 60:
            attempt['count'] = 0
            attempt['window_start'] = now

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = upgrade_user(users[user_id])

    # Check that 2FA is actually enabled
    if not user_data.get('totp_enabled', False):
        return jsonify({'message': '2FA is not enabled for this user.'}), 400

    secret = user_data.get('totp_secret')
    if not secret:
        return jsonify({'message': '2FA not properly configured. Contact admin.'}), 400

    # Validate the TOTP code
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        # Increment failed attempts
        if user_id not in twofa_failed_attempts:
            twofa_failed_attempts[user_id] = {'count': 0, 'lock_until': None, 'window_start': now}
        attempt = twofa_failed_attempts[user_id]
        attempt['count'] += 1
        if attempt['window_start'] is None:
            attempt['window_start'] = now

        log_activity('2fa_login_failed', user_id, user_data.get('role', 'unknown'),
                     {'status': 'invalid_code', 'attempt': attempt['count']})
        record_login_attempt(user_id, False, '2fa', None, {'reason': 'invalid_totp', 'attempt': attempt['count']})

        # Lock after 5 failed attempts
        if attempt['count'] >= 5:
            attempt['lock_until'] = now + timedelta(minutes=15)
            log_activity('2fa_login_locked', user_id, user_data.get('role', 'unknown'),
                         {'status': 'account_locked_15min', 'attempts': attempt['count']})
            return jsonify({
                'message': 'Too many failed attempts. Account locked for 15 minutes.',
                'locked': True,
                'retry_after': 900
            }), 429

        remaining = 5 - attempt['count']
        return jsonify({
            'message': f'Invalid code. {remaining} attempt(s) remaining.',
            'remaining_attempts': remaining
        }), 401

    # Code is valid — clear rate limit and issue session
    if user_id in twofa_failed_attempts:
        del twofa_failed_attempts[user_id]

    # Save user data in case upgrade_user made changes
    users[user_id] = user_data
    save_json_data(USERS_FILE, users)

    log_activity('2fa_login_success', user_id, user_data.get('role', 'unknown'),
                 {'status': 'success', 'user_name': user_data['name']})
    record_login_attempt(user_id, True, '2fa', None, {'status': 'success'})

    if user_data['role'] in ('admin', 'owner'):
        active_admin_sessions[user_id] = datetime.now()

    # Create session token
    user_agent = request.headers.get('User-Agent', '')
    client_ip = get_client_ip()
    session_token = create_user_session(user_id, user_data['name'], user_data['role'], client_ip, user_agent)

    # Check for PIN reset notification
    response_data = {
        'message': 'Login successful',
        'user': user_data['name'],
        'role': user_data['role'],
        'permissions': user_data.get('permissions', []),
        'totp_enabled': user_data.get('totp_enabled', False),
        'session_token': session_token
    }
    if user_data.get('pin_reset_notification'):
        notif = user_data['pin_reset_notification']
        response_data['pin_reset_info'] = {
            'message': f'⚠️ Your PIN was reset by {notif.get("reset_by_name", "Unknown")} on {notif.get("reset_at", "unknown")}. Reason: {notif.get("reason", "Not provided")}. Use your new PIN.',
            'reset_by': notif.get('reset_by_name', 'Unknown'),
            'reset_at': notif.get('reset_at', ''),
            'reason': notif.get('reason', '')
        }
        users[user_id]['pin_reset_notification'] = None
        save_json_data(USERS_FILE, users)

    if user_data.get('force_pin_change', False):
        response_data['force_pin_change_required'] = True
        users[user_id]['force_pin_change'] = False
        save_json_data(USERS_FILE, users)

    try:
        check_anomalies_after_login(user_id, user_data['name'], get_client_ip())
    except Exception:
        pass
    return jsonify(response_data)


@app.route('/api/auth/2fa/backup_login', methods=['POST'])
def twofa_backup_login():
    """Login using a backup code instead of TOTP (when user lost their phone).
    One-time use: the used backup code is removed from the list.
    Rate-limited via the same twofa_failed_attempts tracker."""
    data = request.json
    user_id = str(data.get('userId', ''))
    backup_code = data.get('backup_code', '')

    if not user_id or not backup_code:
        return jsonify({'message': 'User ID and backup code are required.'}), 400

    backup_code = backup_code.strip()
    now = datetime.now()

    # --- Rate limit check (shared with TOTP login) ---
    if user_id in twofa_failed_attempts:
        attempt = twofa_failed_attempts[user_id]
        if attempt.get('lock_until') and now < attempt['lock_until']:
            remaining_seconds = int((attempt['lock_until'] - now).total_seconds())
            log_activity('2fa_login_rate_limited', user_id, 'unknown', {'reason': 'backup_code_locked', 'remaining_seconds': remaining_seconds})
            return jsonify({
                'message': f'Too many failed attempts. Account locked for {remaining_seconds} more seconds.',
                'locked': True,
                'retry_after': remaining_seconds
            }), 429
        if attempt.get('window_start') and (now - attempt['window_start']).total_seconds() > 60:
            attempt['count'] = 0
            attempt['window_start'] = now

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = upgrade_user(users[user_id])

    # Check that 2FA is enabled
    if not user_data.get('totp_enabled', False):
        return jsonify({'message': '2FA is not enabled for this user.'}), 400

    hashed_codes = user_data.get('totp_backup_codes', [])
    if not hashed_codes:
        return jsonify({
            'message': 'No backup codes remaining. Contact admin to regenerate backup codes or disable 2FA.',
            'no_codes_remaining': True
        }), 401

    # Hash the provided backup code and look for a match
    provided_hash = hashlib.sha256(backup_code.encode()).hexdigest()

    match_index = None
    for i, stored_hash in enumerate(hashed_codes):
        if stored_hash == provided_hash:
            match_index = i
            break

    if match_index is None:
        # Increment failed attempts
        if user_id not in twofa_failed_attempts:
            twofa_failed_attempts[user_id] = {'count': 0, 'lock_until': None, 'window_start': now}
        attempt = twofa_failed_attempts[user_id]
        attempt['count'] += 1
        if attempt['window_start'] is None:
            attempt['window_start'] = now

        log_activity('2fa_login_failed', user_id, user_data.get('role', 'unknown'),
                     {'status': 'invalid_backup_code', 'attempt': attempt['count']})
        record_login_attempt(user_id, False, 'backup_code', None, {'reason': 'invalid_backup_code', 'attempt': attempt['count']})

        # Lock after 5 failed attempts
        if attempt['count'] >= 5:
            attempt['lock_until'] = now + timedelta(minutes=15)
            log_activity('2fa_login_locked', user_id, user_data.get('role', 'unknown'),
                         {'status': 'account_locked_15min_backup', 'attempts': attempt['count']})
            return jsonify({
                'message': 'Too many failed attempts. Account locked for 15 minutes.',
                'locked': True,
                'retry_after': 900
            }), 429

        remaining = 5 - attempt['count']
        return jsonify({
            'message': f'Invalid backup code. {remaining} attempt(s) remaining.',
            'remaining_attempts': remaining
        }), 401

    # --- Backup code matched — one-time use, remove it ---
    removed_code = hashed_codes.pop(match_index)
    remaining_codes = len(hashed_codes)
    user_data['totp_backup_codes'] = hashed_codes
    users[user_id] = user_data
    save_json_data(USERS_FILE, users)

    # Clear rate limit on success
    if user_id in twofa_failed_attempts:
        del twofa_failed_attempts[user_id]

    log_activity('2fa_backup_code_used', user_id, user_data.get('role', 'unknown'),
                 {'status': 'login_success', 'remaining_codes': remaining_codes,
                  'user_name': user_data['name']})
    record_login_attempt(user_id, True, 'backup_code', None, {'status': 'success', 'remaining_codes': remaining_codes})

    # Issue session (same as normal login)
    if user_data['role'] in ('admin', 'owner'):
        active_admin_sessions[user_id] = datetime.now()

    response_msg = f'Logged in. {remaining_codes} backup code(s) remaining.'
    if remaining_codes <= 2:
        response_msg += ' ⚠️ Backup codes running low — consider regenerating them in Security settings.'
        log_activity('2fa_backup_codes_low', user_id, user_data.get('role', 'unknown'),
                     {'remaining_codes': remaining_codes, 'user_name': user_data['name']})

    response_data = {
        'message': response_msg,
        'user': user_data['name'],
        'role': user_data['role'],
        'permissions': user_data.get('permissions', []),
        'backup_codes_remaining': remaining_codes,
        'logged_in_via_backup_code': True
    }

    # Check for PIN reset notification
    if user_data.get('pin_reset_notification'):
        notif = user_data['pin_reset_notification']
        response_data['pin_reset_info'] = {
            'message': f'⚠️ Your PIN was reset by {notif.get("reset_by_name", "Unknown")} on {notif.get("reset_at", "unknown")}. Reason: {notif.get("reason", "Not provided")}. Use your new PIN.',
            'reset_by': notif.get('reset_by_name', 'Unknown'),
            'reset_at': notif.get('reset_at', ''),
            'reason': notif.get('reason', '')
        }
        users[user_id]['pin_reset_notification'] = None
        save_json_data(USERS_FILE, users)

    if user_data.get('force_pin_change', False):
        response_data['force_pin_change_required'] = True
        users[user_id]['force_pin_change'] = False
        save_json_data(USERS_FILE, users)

    try:
        check_anomalies_after_login(user_id, user_data['name'], get_client_ip())
    except Exception:
        pass
    return jsonify(response_data)


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

    # Store pay_rate if provided
    pay_rate = data.get('payRate')
    if pay_rate is not None:
        try:
            new_user_data['pay_rate'] = float(pay_rate)
        except (ValueError, TypeError):
            new_user_data['pay_rate'] = None
    else:
        new_user_data['pay_rate'] = None

    # Store scheduled_start if provided
    scheduled_start = data.get('scheduledStart')
    if scheduled_start is not None and isinstance(scheduled_start, str) and scheduled_start.strip():
        # Basic validation: HH:MM format
        import re
        if re.match(r'^\d{2}:\d{2}$', scheduled_start.strip()):
            new_user_data['scheduled_start'] = scheduled_start.strip()
        else:
            new_user_data['scheduled_start'] = None
    else:
        new_user_data['scheduled_start'] = None

    # Store email if provided
    email = data.get('email', '').strip()
    if email and '@' in email and '.' in email:
        new_user_data['email'] = email
    else:
        new_user_data['email'] = ''

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


@app.route('/api/users/update_pay_rate', methods=['POST'])
def update_user_pay_rate():
    """Update pay_rate for an existing user."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    pay_rate = data.get('payRate')

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    admin_user = users.get(admin_pin, {})

    # Store the old value for audit
    old_pay_rate = users[user_id].get('pay_rate', None)

    # Update pay_rate
    if pay_rate is not None:
        try:
            users[user_id]['pay_rate'] = float(pay_rate)
        except (ValueError, TypeError):
            return jsonify({'message': 'Pay rate must be a number.'}), 400
    else:
        users[user_id]['pay_rate'] = None

    save_json_data(USERS_FILE, users)

    log_activity('update_pay_rate', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'target_user_id': user_id,
                  'old_pay_rate': old_pay_rate, 'new_pay_rate': users[user_id]['pay_rate'],
                  'user_name': users[user_id].get('name', 'Unknown')})

    return jsonify({
        'message': 'Pay rate updated successfully.',
        'user_id': user_id,
        'pay_rate': users[user_id]['pay_rate']
    })


@app.route('/api/users/update_scheduled_start', methods=['POST'])
def update_user_scheduled_start():
    """Update scheduled_start for an existing user."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    scheduled_start = data.get('scheduledStart')

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    admin_user = users.get(admin_pin, {})

    # Store the old value for audit
    old_scheduled_start = users[user_id].get('scheduled_start', None)

    # Update scheduled_start
    if scheduled_start is not None and isinstance(scheduled_start, str) and scheduled_start.strip():
        import re
        if re.match(r'^\d{2}:\d{2}$', scheduled_start.strip()):
            users[user_id]['scheduled_start'] = scheduled_start.strip()
        else:
            return jsonify({'message': 'Scheduled start must be in HH:MM format (e.g., 09:00).'}), 400
    else:
        users[user_id]['scheduled_start'] = None

    save_json_data(USERS_FILE, users)

    log_activity('update_scheduled_start', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'target_user_id': user_id,
                  'old_scheduled_start': old_scheduled_start, 'new_scheduled_start': users[user_id]['scheduled_start'],
                  'user_name': users[user_id].get('name', 'Unknown')})

    return jsonify({
        'message': 'Scheduled start time updated successfully.',
        'user_id': user_id,
        'scheduled_start': users[user_id]['scheduled_start']
    })


@app.route('/api/users/update_email', methods=['POST'])
def update_user_email():
    """Update email address for an existing user."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    email = (data.get('email') or '').strip()

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    admin_user = users.get(admin_pin, {})

    # Validate email format
    if email and ('@' not in email or '.' not in email):
        return jsonify({'message': 'Invalid email address format.'}), 400

    old_email = users[user_id].get('email', '')
    users[user_id]['email'] = email

    save_json_data(USERS_FILE, users)

    log_activity('update_email', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'target_user_id': user_id,
                  'old_email': old_email, 'new_email': email,
                  'user_name': users[user_id].get('name', 'Unknown')})

    return jsonify({
        'message': 'Email address updated successfully.',
        'user_id': user_id,
        'email': email
    })


@app.route('/api/users/disable_2fa', methods=['POST'])
def disable_user_2fa():
    """Admin/owner disables 2FA for a user. Resets totp fields, requires reason.
    Only owner can disable 2FA on other admins. Requires manage_users permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    reason = data.get('reason', '')

    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    if not reason or not reason.strip():
        return jsonify({'message': 'Reason is required to disable 2FA.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    admin_user = users.get(admin_pin, {})
    target_user = users[user_id]

    # Only owner can disable 2FA on other admins
    if target_user.get('role') == 'admin' and admin_user.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can disable 2FA on admin accounts.'}), 403

    # Check if 2FA is actually enabled
    if not target_user.get('totp_enabled', False):
        return jsonify({'message': '2FA is not enabled for this user.'}), 400

    old_values = {
        'totp_enabled': target_user.get('totp_enabled'),
        'totp_secret_set': target_user.get('totp_secret') is not None,
        'totp_backup_codes_count': len(target_user.get('totp_backup_codes', [])),
        'totp_setup_at': target_user.get('totp_setup_at')
    }

    # Reset all 2FA fields
    users[user_id]['totp_enabled'] = False
    users[user_id]['totp_secret'] = None
    users[user_id]['totp_backup_codes'] = []
    users[user_id]['totp_setup_at'] = None

    save_json_data(USERS_FILE, users)

    log_activity('2fa_disabled_by_admin', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'target_user_id': user_id,
                  'target_user_name': target_user.get('name', 'Unknown'),
                  'target_user_role': target_user.get('role', 'unknown'),
                  'reason': reason.strip(),
                  'old_values': old_values})

    return jsonify({
        'message': f'2FA disabled for user {target_user.get("name", user_id)}.',
        'user_id': user_id
    })


@app.route('/api/users/regenerate_backup_codes', methods=['POST'])
def regenerate_backup_codes():
    """Admin regenerates backup codes for a user. Invalidates old codes.
    Requires manage_users permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')

    if not check_perm(admin_pin, "manage_users"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    admin_user = users.get(admin_pin, {})
    target_user = users[user_id]

    # Only owner can regenerate codes for admins
    if target_user.get('role') == 'admin' and admin_user.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can regenerate backup codes for admin accounts.'}), 403

    # Check that 2FA is enabled (backup codes only make sense with 2FA)
    if not target_user.get('totp_enabled', False):
        return jsonify({'message': '2FA is not enabled for this user. Enable 2FA first.'}), 400

    # Generate 8 new backup codes (same logic as 2fa/verify)
    backup_codes = []
    hashed_codes = []
    for _ in range(8):
        plain_code = secrets.token_hex(5).upper()
        backup_codes.append(plain_code)
        hashed_codes.append(hashlib.sha256(plain_code.encode()).hexdigest())

    old_count = len(target_user.get('totp_backup_codes', []))

    users[user_id]['totp_backup_codes'] = hashed_codes
    save_json_data(USERS_FILE, users)

    log_activity('2fa_backup_regenerated', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'target_user_id': user_id,
                  'target_user_name': target_user.get('name', 'Unknown'),
                  'old_codes_count': old_count, 'new_codes_count': len(backup_codes)})

    return jsonify({
        'message': f'Backup codes regenerated for {target_user.get("name", user_id)}.',
        'backup_codes': backup_codes,
        'backup_codes_count': len(backup_codes),
        'user_id': user_id,
        'warn': 'Save these backup codes now. The old codes have been invalidated.'
    })


@app.route('/api/users/timeline', methods=['POST'])
def user_timeline():
    """Per-user account history timeline.
    Returns chronological, filterable activity log entries for a specific user.
    Covers: PIN changes, 2FA setup/disable, login successes/failures, lockouts,
    temp PIN usage, permission changes, pay rate changes, bans, force logouts.
    Requires manage_users permission.
    """
    data = request.json
    admin_pin = str(data.get('adminPin', ''))
    target_user_id = str(data.get('userId', ''))
    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    type_filter = (data.get('type_filter') or '').strip()

    if not admin_pin:
        return jsonify({'message': 'Authentication required.'}), 401
    if not check_perm(admin_pin, 'manage_users'):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    if not target_user_id:
        return jsonify({'message': 'userId is required.'}), 400

    users = load_json_data(USERS_FILE)
    target_user = users.get(target_user_id, {})
    target_name = target_user.get('name', target_user_id)

    logs = load_json_data(ACTIVITY_LOG_FILE)

    # Activity types relevant to user account timeline
    relevant_types = {
        'login', 'login_failed', 'pin_changed', 'pin_change_failed',
        'pin_change_logout_sessions', 'pin_reset_by_admin',
        '2fa_setup_initiated', '2fa_verify_success', '2fa_verify_failed',
        '2fa_login_success', '2fa_login_failed', '2fa_login_locked',
        '2fa_login_rate_limited', '2fa_backup_code_used', '2fa_backup_codes_low',
        '2fa_disabled_by_admin', '2fa_backup_regenerated',
        'user_blocked', 'user_unblocked', 'force_logout',
        'update_pay_rate', 'update_scheduled_start', 'update_permissions',
        'ban_user', 'user_banned', 'clear_lockout',
        'add_user', 'delete_user',
        'temp_pin_generated', 'temp_pin_used',
    }

    filtered = []
    for log in logs:
        # Must be a relevant type
        if log.get('type') not in relevant_types:
            continue
        # Must involve this user
        log_user_id = log.get('user_id', '')
        details = log.get('details', {}) or {}
        related_user = str(details.get('target_user_id', '')) or str(details.get('userId', ''))
        if log_user_id != target_user_id and related_user != target_user_id:
            # Also check if the event is about this user (banned, etc.)
            if not (details.get('user_name') == target_name or details.get('target_user_name') == target_name):
                continue

        # Date filter
        ts = log.get('timestamp', '')
        if date_from and ts < date_from:
            continue
        if date_to:
            # Include entries up to end of date_to day
            date_to_end = date_to + 'T23:59:59'
            if ts > date_to_end:
                continue

        # Type filter
        if type_filter and log.get('type') != type_filter:
            continue

        filtered.append(log)

    # Sort by timestamp descending (most recent first)
    filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    # Limit to 500
    filtered = filtered[:500]

    # Build human-readable labels
    type_labels = {
        'login': ('🔑 Login', '#2ecc71'),
        'login_failed': ('❌ Login Failed', '#e74c3c'),
        'pin_changed': ('🔐 PIN Changed', '#3498db'),
        'pin_change_failed': ('❌ PIN Change Failed', '#e74c3c'),
        'pin_change_logout_sessions': ('🔐 PIN Change — Sessions Ended', '#e67e22'),
        'pin_reset_by_admin': ('🔐 PIN Reset by Admin', '#e67e22'),
        '2fa_setup_initiated': ('🔒 2FA Setup Started', '#3498db'),
        '2fa_verify_success': ('🔒 2FA Setup Verified', '#2ecc71'),
        '2fa_verify_failed': ('❌ 2FA Verification Failed', '#e74c3c'),
        '2fa_login_success': ('🔑 2FA Login Success', '#2ecc71'),
        '2fa_login_failed': ('❌ 2FA Login Failed', '#e74c3c'),
        '2fa_login_locked': ('🔒 2FA Account Locked', '#e74c3c'),
        '2fa_login_rate_limited': ('⏳ 2FA Rate Limited', '#e67e22'),
        '2fa_backup_code_used': ('🔑 Backup Code Used', '#e67e22'),
        '2fa_backup_codes_low': ('⚠️ Backup Codes Low', '#e67e22'),
        '2fa_disabled_by_admin': ('🔓 2FA Disabled by Admin', '#e74c3c'),
        '2fa_backup_regenerated': ('🔄 Backup Codes Regenerated', '#3498db'),
        'user_blocked': ('🚫 User Blocked', '#e74c3c'),
        'user_unblocked': ('✅ User Unblocked', '#2ecc71'),
        'force_logout': ('🚪 Force Logout', '#e67e22'),
        'update_pay_rate': ('💰 Pay Rate Updated', '#3498db'),
        'update_scheduled_start': ('📅 Scheduled Start Updated', '#3498db'),
        'update_permissions': ('🛡️ Permissions Updated', '#e67e22'),
        'ban_user': ('🚫 Account Banned', '#e74c3c'),
        'user_banned': ('🚫 User Banned', '#e74c3c'),
        'clear_lockout': ('🔓 Lockout Cleared', '#2ecc71'),
        'add_user': ('➕ User Created', '#2ecc71'),
        'delete_user': ('🗑️ User Deleted', '#e74c3c'),
        'temp_pin_generated': ('🔑 Temp PIN Generated', '#e67e22'),
        'temp_pin_used': ('🔑 Temp PIN Used', '#e67e22'),
    }

    # Gather available types in results for filtering
    available_types = sorted(set(
        type_labels.get(e.get('type', ''), (e.get('type', ''), '#95a5a6'))[0]
        for e in filtered
    ))

    result = []
    for entry in filtered:
        label, color = type_labels.get(entry.get('type', ''), (entry.get('type', ''), '#95a5a6'))
        result.append({
            'timestamp': entry.get('timestamp', ''),
            'type': entry.get('type', ''),
            'label': label,
            'color': color,
            'user_role': entry.get('user_role', ''),
            'ip_address': entry.get('ip_address', ''),
            'details': entry.get('details', {}),
        })

    return jsonify({
        'timeline': result,
        'target_user_id': target_user_id,
        'target_user_name': target_name,
        'total': len(result),
        'available_types': available_types,
    })


@app.route('/api/auth/change_pin', methods=['POST'])
def change_pin():
    """Employee self-service PIN change.
    User enters current PIN, new PIN (twice), and optionally a TOTP code if 2FA is enabled.
    Validates: new PIN 4-8 digits, not same as current, not already taken.
    Warns on easily guessable PINs but does not block.
    Moves user record from old PIN key to new PIN key in users.json.
    Logs to activity_log.
    """
    data = request.json
    user_id = str(data.get('userId', ''))
    current_pin = str(data.get('currentPin', ''))
    new_pin = str(data.get('newPin', ''))
    new_pin_confirm = str(data.get('newPinConfirm', ''))
    totp_code = str(data.get('totpCode', '')).strip()

    if not user_id or not current_pin or not new_pin or not new_pin_confirm:
        return jsonify({'message': 'All fields are required.'}), 400

    # Validate current PIN matches user_id (PIN is the user ID key)
    if current_pin != user_id:
        return jsonify({'message': 'Current PIN is incorrect.'}), 403

    # Validate new PIN format
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
        return jsonify({'message': 'New PIN must be 4-8 digits.'}), 400

    # Validate new PIN confirmation matches
    if new_pin != new_pin_confirm:
        return jsonify({'message': 'New PIN confirmation does not match.'}), 400

    # Validate new PIN is different
    if new_pin == current_pin:
        return jsonify({'message': 'New PIN must be different from current PIN.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = upgrade_user(users[user_id])

    # Check new PIN is not already taken by another user
    if new_pin in users:
        return jsonify({'message': 'New PIN is already in use by another user.'}), 409

    # If user has 2FA enabled, require a valid TOTP code
    if user_data.get('totp_enabled', False):
        if not totp_code:
            return jsonify({'message': '2FA is enabled. Please provide your 6-digit TOTP code.'}), 400
        if not totp_code.isdigit() or len(totp_code) != 6:
            return jsonify({'message': 'TOTP code must be 6 digits.'}), 400
        secret = user_data.get('totp_secret')
        if not secret:
            return jsonify({'message': '2FA configuration error. Contact admin.'}), 500
        totp = pyotp.TOTP(secret)
        if not totp.verify(totp_code, valid_window=1):
            log_activity('pin_change_failed', user_id, user_data.get('role', 'unknown'),
                         {'status': 'invalid_totp', 'user_name': user_data.get('name', 'Unknown')})
            return jsonify({'message': 'Invalid TOTP code. Try again.'}), 400

    # Check for easily guessable PINs — warn but don't block
    guessable_patterns = ['1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999',
                          '0000', '1234', '4321', '1212', '1122', '12345', '123456', '12345678',
                          '000000', '111111', '222222']
    is_guessable = new_pin in guessable_patterns

    # Optionally log out all other sessions on PIN change
    logout_other = data.get('logoutOtherSessions', False)
    if logout_other:
        session_token = str(data.get('sessionToken', ''))
        removed = 0
        if session_token:
            removed = logout_all_sessions(user_id, except_token=session_token)
        else:
            removed = logout_all_sessions(user_id)
        log_activity('pin_change_logout_sessions', user_id, user_data.get('role', 'unknown'),
                     {'old_user_id': user_id, 'sessions_removed': removed})

    # Move user data from old PIN to new PIN
    user_data_copy = dict(user_data)
    del users[user_id]
    users[new_pin] = user_data_copy
    save_json_data(USERS_FILE, users)

    # Move sessions from old user_id to new user_id
    if user_id in active_user_sessions:
        active_user_sessions[new_pin] = active_user_sessions.pop(user_id)

    log_activity('pin_changed', new_pin, user_data_copy.get('role', 'unknown'),
                 {'old_user_id': user_id, 'new_user_id': new_pin,
                  'user_name': user_data_copy.get('name', 'Unknown'),
                  'totp_verified': user_data.get('totp_enabled', False)})

    response = {
        'message': 'PIN changed successfully.',
        'new_user_id': new_pin,
        'user_name': user_data_copy.get('name', 'Unknown'),
        'user_role': user_data_copy.get('role', 'unknown')
    }
    if is_guessable:
        response['warn'] = 'Your new PIN is easy to guess. Consider choosing a more secure PIN.'

    return jsonify(response)


@app.route('/api/users/reset_pin', methods=['POST'])
def reset_user_pin():
    """Admin/owner resets another user's PIN. Requires manage_users permission.
    The user's login ID (PIN) is changed to the new value.
    Only owner can reset an admin's PIN. Logs to activity_log with audit trail.
    Optionally sets force_pin_change flag so user is prompted to change PIN on next login."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    new_pin = data.get('newPin')
    reason = data.get('reason', '')
    force_change = data.get('forceChange', False)

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        log_activity('pin_reset_by_admin', admin_pin, 'unauthorized',
                     {'status': 'failed', 'reason': 'Insufficient permissions',
                      'target_user_id': user_id})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    if not new_pin or not isinstance(new_pin, str):
        return jsonify({'message': 'New PIN is required.'}), 400

    # Validate new PIN: 4-8 digits
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
        return jsonify({'message': 'New PIN must be 4-8 digits.'}), 400

    if not reason or not reason.strip():
        return jsonify({'message': 'Reason is required to reset PIN.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    # Check new PIN is not already taken
    if new_pin in users:
        return jsonify({'message': 'New PIN is already in use by another user.'}), 409

    admin_user = users.get(admin_pin, {})
    target_user = users[user_id]
    target_user = upgrade_user(target_user)

    # Only owner can reset PIN on admins
    if target_user.get('role') == 'admin' and admin_user.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can reset PINs for admin accounts.'}), 403

    # Only owner can reset PIN on owner
    if target_user.get('role') == 'owner' and admin_user.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can reset the owner PIN.'}), 403

    # Don't allow self-reset
    if admin_pin == user_id:
        return jsonify({'message': 'Use the Change PIN feature to change your own PIN.'}), 400

    # Move user data from old PIN to new PIN
    user_data = users[user_id]

    # Set PIN reset notification (shown on next login)
    user_data['pin_reset_notification'] = {
        'reset_by': admin_pin,
        'reset_by_name': admin_user.get('name', 'Unknown'),
        'reset_by_role': admin_user.get('role', 'unknown'),
        'reset_at': datetime.now().isoformat(),
        'reason': reason.strip()
    }

    # Optionally force PIN change on next login
    if force_change:
        user_data['force_pin_change'] = True

    # Remove old entry and create new one under the new PIN
    del users[user_id]
    users[new_pin] = user_data

    save_json_data(USERS_FILE, users)

    log_activity('pin_reset_by_admin', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'old_user_id': user_id, 'new_user_id': new_pin,
                  'target_user_name': target_user.get('name', 'Unknown'),
                  'target_user_role': target_user.get('role', 'unknown'),
                  'reason': reason.strip(),
                  'force_pin_change': force_change})

    return jsonify({
        'message': f'PIN reset for {target_user.get("name", user_id)}. New PIN: {new_pin}. User will be notified on next login.',
        'user_id': new_pin,
        'old_user_id': user_id,
        'force_pin_change': force_change
    })


@app.route('/api/users/generate_temp_pin', methods=['POST'])
def generate_temp_pin():
    """Owner/admin generates a one-time temporary PIN for a locked-out employee.
    Valid for 1 hour, single-use (expires after login or expiry).
    Requires manage_users permission. Only owner can generate for admin accounts.
    Logs to activity_log."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = data.get('userId')
    reason = data.get('reason', '')

    # Verify caller has manage_users permission
    if not check_perm(admin_pin, "manage_users"):
        log_activity('generate_temp_pin', admin_pin, 'unauthorized',
                     {'status': 'failed', 'reason': 'Insufficient permissions',
                      'target_user_id': user_id})
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    admin_user = users.get(admin_pin, {})
    target_user = users[user_id]
    target_user = upgrade_user(target_user)

    # Only owner can generate temp PIN for admins
    if target_user.get('role') == 'admin' and admin_user.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can generate temp PINs for admin accounts.'}), 403

    # Only owner can generate temp PIN for owner
    if target_user.get('role') == 'owner' and admin_user.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can generate temp PINs for the owner.'}), 403

    # Don't allow self-generation
    if admin_pin == user_id:
        return jsonify({'message': 'Use the Change PIN feature to change your own PIN.'}), 400

    # Generate a random 6-digit temp PIN
    temp_pin = str(secrets.randbelow(900000) + 100000)  # 100000-999999

    # Set expiry to 1 hour from now
    expiry = (datetime.now() + timedelta(hours=1)).isoformat()

    # Store on user record
    users[user_id]['temp_pin'] = temp_pin
    users[user_id]['temp_pin_expiry'] = expiry

    save_json_data(USERS_FILE, users)

    log_activity('generate_temp_pin', admin_pin, admin_user.get('role', 'unknown'),
                 {'status': 'success', 'target_user_id': user_id,
                  'target_user_name': target_user.get('name', 'Unknown'),
                  'temp_pin': temp_pin, 'expiry': expiry,
                  'reason': reason.strip() if reason else ''})

    return jsonify({
        'message': f'Temporary PIN generated for {target_user.get("name", user_id)}. Valid for 1 hour.',
        'temp_pin': temp_pin,
        'expiry': expiry,
        'user_id': user_id,
        'user_name': target_user.get('name', 'Unknown'),
        'warn': 'This code can only be used once. Share it securely with the employee.'
    })


# ══════════════════════════════════════════════
# Session Management Endpoints
# ══════════════════════════════════════════════

@app.route('/api/sessions', methods=['GET', 'POST'])
def sessions_list():
    """Get active sessions for a user or all users (admin).
    GET: query params { userId, adminPin } — if adminPin has view_stats, returns sessions for userId or all
    POST: body { userId, sessionToken } — returns sessions for the user (self-service).
    Returns list of active sessions sorted by login_time descending."""
    if request.method == 'POST':
        data = request.json or {}
        user_id = str(data.get('userId', ''))
        session_token = str(data.get('sessionToken', ''))
        if not user_id or not session_token:
            return jsonify({'message': 'userId and sessionToken are required.'}), 400
        # Verify the session token belongs to this user
        sessions = active_user_sessions.get(user_id, {})
        if session_token not in sessions:
            return jsonify({'message': 'Invalid session token.'}), 403
        # Update last_active
        sessions[session_token]['last_active'] = datetime.now().isoformat()
        active_sessions = get_active_sessions(user_id)
        return jsonify({'sessions': active_sessions, 'count': len(active_sessions)})

    # GET mode — admin view
    admin_pin = request.args.get('adminPin', '')
    user_id = request.args.get('userId', '')
    if not check_perm(admin_pin, 'view_stats'):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    if user_id:
        active_sessions = get_active_sessions(user_id)
    else:
        active_sessions = get_active_sessions()
    return jsonify({'sessions': active_sessions, 'count': len(active_sessions)})


@app.route('/api/sessions/logout', methods=['POST'])
def sessions_logout():
    """Logout a specific session.
    Body: { userId, sessionToken, targetToken? }
    If targetToken provided, that specific session is logged out (admin or self).
    If no targetToken, the sessionToken's session is logged out (self-logout).
    """
    data = request.json or {}
    user_id = str(data.get('userId', ''))
    session_token = str(data.get('sessionToken', ''))
    target_token = str(data.get('targetToken', '')) or session_token
    if not user_id or not session_token:
        return jsonify({'message': 'userId and sessionToken are required.'}), 400
    # Verify the requesting session belongs to this user
    sessions = active_user_sessions.get(user_id, {})
    if session_token not in sessions:
        return jsonify({'message': 'Invalid session token.'}), 403
    if logout_session(user_id, target_token):
        return jsonify({'message': 'Session logged out successfully.'})
    return jsonify({'message': 'Session not found.'}), 404


@app.route('/api/sessions/logout_all', methods=['POST'])
def sessions_logout_all():
    """Logout all sessions for a user (optionally keeping the current one).
    Body: { userId, sessionToken, keepCurrent (bool, default true) }
    """
    data = request.json or {}
    user_id = str(data.get('userId', ''))
    session_token = str(data.get('sessionToken', ''))
    keep_current = data.get('keepCurrent', True)
    if not user_id or not session_token:
        return jsonify({'message': 'userId and sessionToken are required.'}), 400
    # Verify the requesting session belongs to this user
    sessions = active_user_sessions.get(user_id, {})
    if session_token not in sessions:
        return jsonify({'message': 'Invalid session token.'}), 403
    except_token = session_token if keep_current else None
    removed = logout_all_sessions(user_id, except_token=except_token)
    return jsonify({
        'message': f'Logged out {removed} session(s).' if removed else 'No other sessions to logout.',
        'removed': removed
    })


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

    items_data[category].append({"name": name, "price": price, "barcode": data.get('barcode', ''), "image_url": data.get('image_url', ''), "course": data.get('course', 'main'), "active": True, "dietary_tags": data.get('dietary_tags', [])})
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
                items_data[new_category].append({"name": new_name, "price": new_price, "barcode": data.get('barcode', old_barcode), "image_url": data.get('image_url', old_image_url), "course": data.get('course', old_course), "active": old_active, "dietary_tags": item.get('dietary_tags', [])})
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

    # --- Concurrent use staleness check ---
    # If composed_since is provided, check if any new orders exist for this table
    # since the waiter started composing. Prevents blind overwrite when two
    # waiters work the same table simultaneously.
    composed_since = data.get('composed_since')
    if composed_since and order_details.get('table_number') is not None:
        conflicting = []
        for o in orders:
            if o.get('table_number') == order_details['table_number'] and o.get('date', '') > composed_since:
                conflicting.append({
                    'order_id': o.get('order_id'),
                    'date': o.get('date'),
                    'user': o.get('user')
                })
        if conflicting:
            return jsonify({
                'message': 'This table has new orders since you started composing. Refresh cart or submit anyway.',
                'conflict': True,
                'conflicting_orders': conflicting,
                'table_number': order_details['table_number']
            }), 409

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

    # Anomaly detection: check rapid orders, large order
    try:
        check_anomalies_after_order(
            str(data.get('user', 'unknown')),
            order_details['total'],
            len(items)
        )
    except Exception:
        pass

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

        # --- Dedup check: skip if this local_id was already synced ---
        if local_id:
            already_processed = any(
                o.get('local_id') == local_id for o in orders_data
            )
            if already_processed:
                # Find the existing order_id for this synced order
                existing = next((o for o in orders_data if o.get('local_id') == local_id), None)
                results.append({
                    'local_id': local_id,
                    'order_id': existing['order_id'] if existing else None,
                    'status': 'already_exists'
                })
                continue

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
            'local_id': local_id,  # stored for dedup on re-sync
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
            'customer_email': order_data.get('customer_email', ''),
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

        # Decrement inventory (with combo child_items support)
        for item in items:
            if item.get('is_combo') and item.get('child_items'):
                for ci in item['child_items']:
                    ci_name = ci.get('name', '')
                    ci_qty = int(ci.get('qty', 1)) * int(item.get('qty', 1))
                    if ci_name in inventory:
                        current_stock = inventory[ci_name].get('stock', 0)
                        inventory[ci_name]['stock'] = max(0, current_stock - ci_qty)
                continue
            item_name = item.get('name', '')
            qty = int(item.get('qty', 1))
            if item_name in inventory:
                current_stock = inventory[item_name].get('stock', 0)
                inventory[item_name]['stock'] = max(0, current_stock - qty)

        # Award loyalty points if customer phone provided
        customer_phone = order_data.get('customer_phone', '').strip()
        if customer_phone:
            loyalty_data = load_json_data(LOYALTY_FILE)
            if customer_phone not in loyalty_data:
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
            loyalty_data[customer_phone]['total_spent'] = round(loyalty_data[customer_phone].get('total_spent', 0) + subtotal, 2)
            loyalty_data[customer_phone]['total_orders'] = loyalty_data[customer_phone].get('total_orders', 0) + 1
            loyalty_data[customer_phone]['last_visit'] = datetime.now().isoformat()
            save_json_data(LOYALTY_FILE, loyalty_data)
            log_activity('loyalty_earn', order_data.get('user', 'unknown'), 'user', {
                'customer_phone': customer_phone,
                'points_earned': earned,
                'order_id': order_id,
                'source': 'sync_orders'
            })

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
    """Get delivery address for a specific order. Requires manage_orders permission."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_orders")
    if err_response:
        return err_response
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
    """List saved delivery addresses, optionally filtered by user or phone.
    Requires manage_orders permission."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_orders")
    if err_response:
        return err_response
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
    """Get the current SMTP email configuration. Requires manage_items permission."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_items")
    if err_response:
        return err_response
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
    """Return receipt HTML for a completed order. Requires manage_orders permission."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_orders")
    if err_response:
        return err_response
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

    # --- Restore inventory: add stock back for each refunded item ---
    inventory = load_json_data(INVENTORY_FILE)
    restored_items = []
    for item in found_order.get('items', []):
        # Handle combo items: restore child items instead of the combo itself
        if item.get('is_combo') and item.get('child_items'):
            for ci in item['child_items']:
                ci_name = ci.get('name', '')
                ci_qty = int(ci.get('qty', 1)) * int(item.get('qty', 1))
                if ci_name in inventory:
                    current_stock = inventory[ci_name].get('stock', 0)
                    inventory[ci_name]['stock'] = current_stock + ci_qty
                    restored_items.append(f"{ci_name} x{ci_qty}")
            continue
        # Regular item
        item_name = item.get('name', '')
        qty = int(item.get('qty', 1))
        if item_name in inventory:
            current_stock = inventory[item_name].get('stock', 0)
            inventory[item_name]['stock'] = current_stock + qty
            restored_items.append(f"{item_name} x{qty}")
    save_json_data(INVENTORY_FILE, inventory)

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
        'order_total': found_order.get('total', 0),
        'inventory_restored': restored_items
    })

    return jsonify({
        'message': f'Order #{order_id} refunded successfully.',
        'reason': reason
    })


# --- Single-Item / Partial Refund Endpoint ---

@app.route('/api/orders/refund_item', methods=['POST'])
def refund_item():
    """
    Refund/void specific line items within an order (partial refund).
    Requires manage_orders permission.
    Accepts order_id + list of item_indices to refund.
    Marks those items as refunded in the order record, restores inventory,
    and recalculates effective totals. Does NOT change order status unless
    ALL items are refunded (then marks order as refunded).
    """
    data = request.json
    admin_pin = data.get('adminPin')
    order_id = data.get('order_id')
    item_indices = data.get('item_indices', [])
    reason = data.get('reason', '').strip()

    if not check_perm(admin_pin, "manage_orders"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if order_id is None:
        return jsonify({'message': 'Order ID is required.'}), 400

    if not item_indices or not isinstance(item_indices, list):
        return jsonify({'message': 'item_indices list is required.'}), 400

    # Validate indices are integers
    try:
        item_indices = [int(i) for i in item_indices]
    except (ValueError, TypeError):
        return jsonify({'message': 'item_indices must be a list of integers.'}), 400

    orders = load_json_data(ORDERS_FILE)
    found_order = None
    order_idx = None

    for idx, order in enumerate(orders):
        if order.get('order_id') == int(order_id):
            if order.get('status') in ('refunded', 'voided'):
                return jsonify({'message': f'Order #{order_id} has already been fully refunded/voided.'}), 400
            found_order = order
            order_idx = idx
            break

    if not found_order:
        return jsonify({'message': f'Order #{order_id} not found.'}), 404

    if not reason:
        reason = 'No reason provided'

    items = found_order.get('items', [])
    if not items:
        return jsonify({'message': 'Order has no items to refund.'}), 400

    # Validate item indices are within range
    invalid_indices = [i for i in item_indices if i < 0 or i >= len(items)]
    if invalid_indices:
        return jsonify({'message': f'Invalid item indices: {invalid_indices}. Order has {len(items)} items (0-{len(items)-1}).'}), 400

    # Deduplicate and sort indices
    item_indices = sorted(set(item_indices))

    # Check if any of these items were already refunded
    existing_refunded = found_order.get('refunded_items', [])
    already_refunded = [ri for ri in existing_refunded if ri.get('item_index') in item_indices]
    if already_refunded:
        already_names = [ri.get('name', 'item') for ri in already_refunded]
        return jsonify({'message': f'Items already refunded: {", ".join(already_names)}'}), 400

    # --- Process the refund ---
    refunded_at = datetime.now().isoformat()
    inventory = load_json_data(INVENTORY_FILE)
    refund_entries = []
    restored_items = []
    total_refund_amount = 0.0

    for idx in item_indices:
        item = items[idx]
        item_name = item.get('name', '')
        item_price = float(item.get('price', 0))
        item_qty = int(item.get('qty', 1))
        item_total = item_price * item_qty

        refund_entry = {
            'item_index': idx,
            'name': item_name,
            'price': item_price,
            'qty': item_qty,
            'total': item_total,
            'reason': reason,
            'refunded_at': refunded_at,
            'refunded_by': admin_pin
        }
        refund_entries.append(refund_entry)
        total_refund_amount += item_total

        # Restore inventory
        if item.get('is_combo') and item.get('child_items'):
            for ci in item['child_items']:
                ci_name = ci.get('name', '')
                ci_qty = int(ci.get('qty', 1)) * item_qty
                if ci_name in inventory:
                    current_stock = inventory[ci_name].get('stock', 0)
                    inventory[ci_name]['stock'] = current_stock + ci_qty
                    restored_items.append(f"{ci_name} x{ci_qty}")
        else:
            if item_name in inventory:
                current_stock = inventory[item_name].get('stock', 0)
                inventory[item_name]['stock'] = current_stock + item_qty
                restored_items.append(f"{item_name} x{item_qty}")

    save_json_data(INVENTORY_FILE, inventory)

    # Add refund entries to order's refunded_items list
    if 'refunded_items' not in found_order:
        found_order['refunded_items'] = []
    found_order['refunded_items'].extend(refund_entries)

    # Check if ALL items are now refunded
    total_item_count = len(items)
    refunded_indices_count = len(set(
        [ri.get('item_index') for ri in found_order['refunded_items']]
    ))

    if refunded_indices_count >= total_item_count:
        # All items refunded — mark entire order as refunded
        found_order['status'] = 'refunded'
        found_order['refund_reason'] = reason
        found_order['refunded_at'] = refunded_at
        found_order['refunded_by'] = admin_pin

    save_json_data(ORDERS_FILE, orders)

    # Log to refunded_orders.json for audit trail
    refunded_orders = load_json_data(REFUNDED_ORDERS_FILE)
    refunded_orders.append({
        'order_id': int(order_id),
        'refund_type': 'partial',
        'item_indices': item_indices,
        'refund_entries': refund_entries,
        'total_refund_amount': round(total_refund_amount, 2),
        'reason': reason,
        'refunded_at': refunded_at,
        'refunded_by': admin_pin
    })
    save_json_data(REFUNDED_ORDERS_FILE, refunded_orders)

    # Log activity
    users = load_json_data(USERS_FILE)
    user_name = users.get(admin_pin, {}).get('name', 'Unknown')
    user_role = users.get(admin_pin, {}).get('role', 'unknown')
    log_activity('refund_item', admin_pin, user_role, {
        'order_id': int(order_id),
        'item_indices': item_indices,
        'refunded_items': [e.get('name') for e in refund_entries],
        'total_refund_amount': round(total_refund_amount, 2),
        'reason': reason,
        'refunded_by_name': user_name,
        'inventory_restored': restored_items,
        'order_fully_refunded': refunded_indices_count >= total_item_count
    })

    return jsonify({
        'message': f'Order #{order_id}: {len(refund_entries)} item(s) refunded.',
        'refunded_count': len(refund_entries),
        'total_refund_amount': round(total_refund_amount, 2),
        'order_fully_refunded': refunded_indices_count >= total_item_count,
        'refunded_items': refund_entries
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
            # Subtract partially refunded items from the total
            refunded_items = order.get('refunded_items', [])
            if refunded_items:
                refunded_sum = sum(
                    float(ri.get('total', ri.get('price', 0) * ri.get('qty', 1)))
                    for ri in refunded_items
                )
                order_total = max(0, order_total - refunded_sum)
            order['total'] = order_total
            processed_orders.append(order)
        except (ValueError, TypeError):
            print(f"Warning: Could not convert 'total' to float for order: {order}. Skipping for stats.")
            continue

    total_sales = sum(order['total'] for order in processed_orders)
    total_traffic = len(processed_orders)
    avg_sale = total_sales / total_traffic if total_traffic > 0 else 0

    # --- Payment method breakdown ---
    cash_total = 0.0
    card_total = 0.0
    other_total = 0.0
    cash_count = 0
    card_count = 0
    other_count = 0
    for order in processed_orders:
        payment = str(order.get('payment', '')).strip().lower()
        total = order['total']
        if payment == 'cash' or (payment.startswith('split') and 'cash' in payment):
            # For split payments, attribute the cash portion if available
            splits = order.get('payment_splits')
            if splits and isinstance(splits, list):
                cash_portion = sum(float(s.get('amount', 0)) for s in splits if s.get('method', '').lower() == 'cash')
                card_portion = sum(float(s.get('amount', 0)) for s in splits if s.get('method', '').lower() in ('card', 'credit card', 'debit'))
                if cash_portion > 0 or card_portion > 0:
                    # Cap attribution at the actual total (split amounts may exceed total due to discounts/tips)
                    split_sum = cash_portion + card_portion
                    if split_sum > total and split_sum > 0:
                        ratio = total / split_sum
                        cash_portion = round(cash_portion * ratio, 2)
                        card_portion = round(card_portion * ratio, 2)
                    cash_total += cash_portion
                    card_total += card_portion
                    if cash_portion > 0: cash_count += 1
                    if card_portion > 0: card_count += 1
                    continue
            cash_total += total
            cash_count += 1
        elif payment in ('card', 'credit card', 'debit', 'credit'):
            card_total += total
            card_count += 1
        else:
            other_total += total
            other_count += 1

    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)  # Approx month

    weekly_sales = sum(order['total'] for order in processed_orders if datetime.fromisoformat(order['date']) >= week_ago)
    monthly_sales = sum(order['total'] for order in processed_orders if datetime.fromisoformat(order['date']) >= month_ago)

    stats = {
        'total_sales': round(total_sales, 2),
        'total_traffic': total_traffic,
        'total_orders': total_traffic,
        'average_sale': round(avg_sale, 2),
        'weekly_sales': round(weekly_sales, 2),
        'monthly_sales': round(monthly_sales, 2),
        'cash_sales': round(cash_total, 2),
        'card_sales': round(card_total, 2),
        'other_sales': round(other_total, 2),
        'cash_count': cash_count,
        'card_count': card_count,
        'other_count': other_count,
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

    # Apply optional date range filtering on login_time
    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    if date_from or date_to:
        filtered = []
        for entry in timesheet_data:
            login_time_str = entry.get('login_time', '')
            if not login_time_str:
                continue
            try:
                login_dt = datetime.fromisoformat(login_time_str)
            except (ValueError, TypeError):
                continue
            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from)
                    if login_dt < dt_from:
                        continue
                except ValueError:
                    pass
            if date_to:
                try:
                    if 'T' not in date_to:
                        dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                    else:
                        dt_to = datetime.fromisoformat(date_to)
                    if login_dt > dt_to:
                        continue
                except ValueError:
                    pass
            filtered.append(entry)
        timesheet_data = filtered

    return jsonify({'message': 'Timesheet data retrieved', 'timesheet': timesheet_data})


# --- Employee Clock-In / Clock-Out System ---

@app.route('/api/clock/in', methods=['POST'])
def clock_in():
    """Clock in an employee for their shift. Records start time."""
    data = request.json
    user_id = data.get('adminPin')  # Uses adminPin field for user identification
    client_ip = get_client_ip()
    now = datetime.now()

    if not user_id:
        return jsonify({'message': 'User ID required.'}), 400

    # --- Rate limiting: IP-based (prevents bulk PIN enumeration) ---
    def check_clock_rate_limit(key):
        """Track rate limit by IP or user_id. 10 attempts per 60s, lock 15min."""
        if key not in clock_failed_attempts:
            clock_failed_attempts[key] = {'count': 0, 'lock_until': None, 'window_start': now}
        attempt = clock_failed_attempts[key]
        if attempt.get('window_start') and (now - attempt['window_start']).total_seconds() > 60:
            attempt['count'] = 0
            attempt['window_start'] = now
        # Check lock
        if attempt.get('lock_until') and now < attempt['lock_until']:
            remaining = int((attempt['lock_until'] - now).total_seconds())
            return True, remaining
        # Clear expired lock
        if attempt.get('lock_until') and now >= attempt['lock_until']:
            attempt['lock_until'] = None
            attempt['count'] = 0
        return False, None

    # Check IP-based rate limit
    ip_locked, ip_retry = check_clock_rate_limit(f'ip:{client_ip}')
    if ip_locked:
        log_activity('clock_in_rate_limited', 'ip:' + client_ip, 'unknown',
                     {'reason': 'ip_locked', 'remaining_seconds': ip_retry})
        return jsonify({'message': 'Too many attempts. Try again later.'}), 429

    # Check user_id-based rate limit (if user_id looks like a valid PIN)
    if user_id and user_id.isdigit():
        uid_locked, uid_retry = check_clock_rate_limit(f'uid:{user_id}')
        if uid_locked:
            log_activity('clock_in_rate_limited', user_id, 'unknown',
                         {'reason': 'user_locked', 'remaining_seconds': uid_retry})
            return jsonify({'message': 'Too many attempts. Try again later.'}), 429

    users = load_json_data(USERS_FILE)

    # Generic error path — same message whether user exists or not (prevents enumeration)
    if user_id not in users:
        _record_clock_failure(f'ip:{client_ip}')
        if user_id and user_id.isdigit():
            _record_clock_failure(f'uid:{user_id}')
        log_activity('clock_in_failed', user_id or 'unknown', 'unknown',
                     {'status': 'failed', 'reason': 'invalid_pin', 'ip': client_ip})
        return jsonify({'message': 'Invalid PIN.'}), 401

    user_data = users[user_id]
    if user_data.get('banned', False):
        _record_clock_failure(f'ip:{client_ip}')
        if user_id and user_id.isdigit():
            _record_clock_failure(f'uid:{user_id}')
        return jsonify({'message': 'Invalid PIN.'}), 401

    # Atomic check-and-set to prevent concurrent double clock-in
    with clock_lock:
        if user_id in active_shifts:
            return jsonify({'message': 'Already clocked in.'}), 409

        # --- Late detection ---
        scheduled_start = user_data.get('scheduled_start')
        late_minutes = None
        late_excused = False
        late_note = (data.get('late_note') or '').strip() or None

        if scheduled_start:
            try:
                parts = scheduled_start.split(':')
                scheduled_hour = int(parts[0])
                scheduled_min = int(parts[1])

                # Build today's scheduled datetime
                scheduled_dt = now.replace(hour=scheduled_hour, minute=scheduled_min, second=0, microsecond=0)

                # Get grace period from timesheet config
                ts_config = get_timesheet_config()
                grace_minutes = ts_config.get('late_grace_minutes', 5)

                # Threshold = scheduled time + grace period
                threshold_dt = scheduled_dt + timedelta(minutes=grace_minutes)

                # Compare clock-in time against threshold
                if now > threshold_dt:
                    late_minutes = round((now - scheduled_dt).total_seconds() / 60)
                    if late_minutes < 0:
                        late_minutes = 0
            except (ValueError, TypeError, IndexError):
                pass  # Invalid scheduled_start format, skip late detection
        # --- End late detection ---

        active_shifts[user_id] = {
            'clock_in_time': now,
            'user_name': user_data.get('name', 'Unknown'),
            'breaks': [],
            'on_break': False,
            'scheduled_start': scheduled_start,
            'late_minutes': late_minutes,
            'late_excused': late_excused,
            'late_note': late_note
        }

    # Lock released — proceed with non-critical I/O

    # Clear rate limit on success
    if f'ip:{client_ip}' in clock_failed_attempts:
        del clock_failed_attempts[f'ip:{client_ip}']
    if f'uid:{user_id}' in clock_failed_attempts:
        del clock_failed_attempts[f'uid:{user_id}']

    log_activity('clock_in', user_id, user_data.get('role', 'user'), {
        'status': 'success',
        'user_name': user_data.get('name', 'Unknown'),
        'clock_in_time': now.isoformat(),
        'late_minutes': late_minutes,
        'scheduled_start': scheduled_start
    })

    return jsonify({
        'message': 'Clocked in successfully.',
        'clock_in_time': now.isoformat(),
        'user_name': user_data.get('name', 'Unknown'),
        'late_minutes': late_minutes,
        'late_excused': late_excused
    })


@app.route('/api/clock/out', methods=['POST'])
def clock_out():
    """Clock out an employee. Records end time and duration."""
    data = request.json
    user_id = data.get('adminPin')
    client_ip = get_client_ip()
    now = datetime.now()

    if not user_id:
        return jsonify({'message': 'User ID required.'}), 400

    # --- Rate limiting (IP + user_id based) ---
    def check_clock_out_rate_limit(key):
        if key not in clock_failed_attempts:
            clock_failed_attempts[key] = {'count': 0, 'lock_until': None, 'window_start': now}
        attempt = clock_failed_attempts[key]
        if attempt.get('window_start') and (now - attempt['window_start']).total_seconds() > 60:
            attempt['count'] = 0
            attempt['window_start'] = now
        if attempt.get('lock_until') and now < attempt['lock_until']:
            remaining = int((attempt['lock_until'] - now).total_seconds())
            return True, remaining
        if attempt.get('lock_until') and now >= attempt['lock_until']:
            attempt['lock_until'] = None
            attempt['count'] = 0
        return False, None

    ip_locked, ip_retry = check_clock_out_rate_limit(f'clock_out_ip:{client_ip}')
    if ip_locked:
        return jsonify({'message': 'Too many attempts. Try again later.'}), 429

    if user_id and user_id.isdigit():
        uid_locked, uid_retry = check_clock_out_rate_limit(f'clock_out_uid:{user_id}')
        if uid_locked:
            return jsonify({'message': 'Too many attempts. Try again later.'}), 429

    # Atomic check-and-pop to prevent concurrent double clock-out
    with clock_lock:
        if user_id not in active_shifts:
            _record_clock_failure(f'clock_out_ip:{client_ip}')
            if user_id and user_id.isdigit():
                _record_clock_failure(f'clock_out_uid:{user_id}')
            return jsonify({'message': 'Not clocked in.'}), 409

        users = load_json_data(USERS_FILE)
        user_data = users.get(user_id, {})
        user_name = user_data.get('name', active_shifts[user_id].get('user_name', 'Unknown'))

        shift = active_shifts.pop(user_id)
    # Lock released
    clock_in_time = shift['clock_in_time']
    clock_out_time = datetime.now()
    duration_hours = round((clock_out_time - clock_in_time).total_seconds() / 3600, 2)

    # Calculate break total
    breaks = shift.get('breaks', [])
    total_break_minutes = 0
    completed_breaks = []
    for b in breaks:
        if b.get('end') is None and b.get('start'):
            # Auto-close open break on clock-out
            try:
                start_dt = datetime.fromisoformat(b['start'])
                dur = (clock_out_time - start_dt).total_seconds() / 60
                b['end'] = clock_out_time.isoformat()
                b['duration_minutes'] = round(dur, 1)
            except (ValueError, TypeError):
                b['end'] = clock_out_time.isoformat()
                b['duration_minutes'] = 0
        mins = b.get('duration_minutes', 0) or 0
        total_break_minutes += mins
        completed_breaks.append(b)

    break_hours = round(total_break_minutes / 60, 2)
    paid_hours = round(duration_hours - break_hours, 2)

    shift_record = {
        'user_id': user_id,
        'user_name': user_name,
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours,
        'breaks': completed_breaks,
        'break_hours': break_hours,
        'paid_hours': paid_hours,
        'scheduled_start': shift.get('scheduled_start'),
        'late_minutes': shift.get('late_minutes'),
        'late_excused': shift.get('late_excused', False),
        'late_note': shift.get('late_note'),
        'pay_rate': user_data.get('pay_rate')  # Capture rate at clock-out time
    }

    # Store optional notes from employee
    notes = (data.get('notes') or '').strip()
    if notes:
        shift_record['notes'] = notes

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

    # Clear rate limits on success
    if f'clock_out_ip:{client_ip}' in clock_failed_attempts:
        del clock_failed_attempts[f'clock_out_ip:{client_ip}']
    if f'clock_out_uid:{user_id}' in clock_failed_attempts:
        del clock_failed_attempts[f'clock_out_uid:{user_id}']

    return jsonify({
        'message': 'Clocked out successfully.',
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours,
        'break_hours': break_hours,
        'paid_hours': paid_hours,
        'notes': notes if notes else None
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
        breaks = shift.get('breaks', [])
        total_break_minutes = sum(
            (b.get('duration_minutes') or 0) for b in breaks
            if b.get('duration_minutes') is not None
        )
        # Include any currently-running break in total
        if shift.get('on_break'):
            for b in reversed(breaks):
                if b.get('end') is None and b.get('start'):
                    try:
                        sd = datetime.fromisoformat(b['start'])
                        total_break_minutes += (now - sd).total_seconds() / 60
                    except (ValueError, TypeError):
                        pass
                    break
        break_hours = round(total_break_minutes / 60, 2)
        return jsonify({
            'clocked_in': True,
            'clock_in_time': clock_in_time.isoformat(),
            'duration_hours': duration_hours,
            'user_name': user_name,
            'on_break': shift.get('on_break', False),
            'break_count': len(breaks),
            'break_hours': break_hours,
            'paid_hours': round(duration_hours - break_hours, 2),
            'late_minutes': shift.get('late_minutes'),
            'late_excused': shift.get('late_excused', False),
            'scheduled_start': shift.get('scheduled_start')
        })
    else:
        return jsonify({
            'clocked_in': False,
            'user_name': user_name
        })


@app.route('/api/clock/edit', methods=['POST'])
def clock_edit():
    """Admin edit shift clock-in/out times with audit trail."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_index = data.get('shift_index')
    if shift_index is None or not isinstance(shift_index, int):
        return jsonify({'message': 'shift_index (integer) is required.'}), 400

    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'message': 'reason is required.'}), 400

    shift_log = load_json_data(SHIFT_FILE)
    if shift_index < 0 or shift_index >= len(shift_log):
        return jsonify({'message': 'Invalid shift_index.'}), 404

    shift = shift_log[shift_index]

    # Check if this shift's period is locked by an approval
    clock_in_str = shift.get('clock_in_time', '')
    approvals = load_json_data(APPROVALS_FILE)
    for app in approvals:
        if app.get('status') in ('pending', 'approved'):
            a_from = app.get('date_from', '')
            a_to = app.get('date_to', '')
            if shift_in_period(clock_in_str, a_from, a_to):
                return jsonify({'message': f'Cannot edit: this pay period ({a_from} to {a_to}) is locked for approval. Owner must unlock first.'}), 423

    new_clock_in_str = data.get('new_clock_in')
    new_clock_out_str = data.get('new_clock_out')
    new_pay_rate = data.get('new_pay_rate')

    if not new_clock_in_str and not new_clock_out_str and new_pay_rate is None:
        return jsonify({'message': 'Provide at least one of new_clock_in, new_clock_out, or new_pay_rate.'}), 400

    changes = {}
    old_clock_in = shift.get('clock_in_time')
    old_clock_out = shift.get('clock_out_time')

    if new_clock_in_str:
        try:
            datetime.fromisoformat(new_clock_in_str)
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid new_clock_in format. Use ISO format (e.g. 2026-06-23T09:00:00).'}), 400
        changes['clock_in_time'] = {'old': old_clock_in, 'new': new_clock_in_str}
        shift['clock_in_time'] = new_clock_in_str

    if new_clock_out_str:
        try:
            datetime.fromisoformat(new_clock_out_str)
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid new_clock_out format. Use ISO format (e.g. 2026-06-23T17:00:00).'}), 400
        changes['clock_out_time'] = {'old': old_clock_out, 'new': new_clock_out_str}
        shift['clock_out_time'] = new_clock_out_str

    # Handle pay_rate change
    if new_pay_rate is not None:
        try:
            new_rate = float(new_pay_rate)
            if new_rate < 0:
                return jsonify({'message': 'Pay rate cannot be negative.'}), 400
            old_rate = shift.get('pay_rate')
            changes['pay_rate'] = {'old': old_rate, 'new': new_rate}
            shift['pay_rate'] = new_rate
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid new_pay_rate. Must be a number.'}), 400

    # Recalculate duration
    try:
        ci = datetime.fromisoformat(shift['clock_in_time'])
        co = datetime.fromisoformat(shift['clock_out_time']) if shift.get('clock_out_time') else None
        if co:
            shift['duration_hours'] = round((co - ci).total_seconds() / 3600, 2)
        else:
            shift['duration_hours'] = 0
    except (ValueError, TypeError):
        shift['duration_hours'] = 0

    # Recalculate break_hours and paid_hours
    existing_break_hours = shift.get('break_hours', 0)
    shift['break_hours'] = existing_break_hours
    shift['paid_hours'] = round(shift['duration_hours'] - existing_break_hours, 2)

    # Re-run late detection if clock_in_time changed
    if new_clock_in_str:
        try:
            users = load_json_data(USERS_FILE)
            uid = shift.get('user_id')
            user_data = users.get(uid, {})
            scheduled_start = user_data.get('scheduled_start')
            if scheduled_start:
                parts = scheduled_start.split(':')
                sched_hour = int(parts[0])
                sched_min = int(parts[1])
                ci_dt = datetime.fromisoformat(shift['clock_in_time'])
                scheduled_dt = ci_dt.replace(hour=sched_hour, minute=sched_min, second=0, microsecond=0)
                ts_config = get_timesheet_config()
                grace_minutes = ts_config.get('late_grace_minutes', 5)
                threshold_dt = scheduled_dt + timedelta(minutes=grace_minutes)
                if ci_dt > threshold_dt:
                    new_late = round((ci_dt - scheduled_dt).total_seconds() / 60)
                    if new_late < 0:
                        new_late = 0
                else:
                    new_late = None
            else:
                new_late = None

            old_late = shift.get('late_minutes')
            if old_late != new_late:
                changes['late_minutes'] = {'old': old_late, 'new': new_late}
                shift['late_minutes'] = new_late
                if new_late is None:
                    shift['late_excused'] = False
                    changes['late_excused'] = {'old': shift.get('late_excused', False), 'new': False}
        except (ValueError, TypeError, IndexError):
            pass

    # Get admin name for audit trail
    users = load_json_data(USERS_FILE)
    admin_user = users.get(admin_pin, {})
    admin_name = admin_user.get('name', admin_pin)

    # Build/append edits array
    if 'edits' not in shift:
        shift['edits'] = []
    shift['edits'].append({
        'edited_by': admin_pin,
        'edited_by_name': admin_name,
        'edited_at': datetime.now().isoformat(),
        'reason': reason,
        'changes': changes
    })
    shift['edited'] = True

    save_json_data(SHIFT_FILE, shift_log)

    log_activity('shift_edited', admin_pin, admin_user.get('role', 'admin'), {
        'shift_index': shift_index,
        'user_id': shift.get('user_id'),
        'user_name': shift.get('user_name'),
        'changes': changes,
        'reason': reason
    })

    return jsonify({
        'message': 'Shift updated successfully.',
        'shift': shift
    })


@app.route('/api/clock/note', methods=['POST'])
def clock_note():
    """Admin add/edit notes on a completed shift."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_index = data.get('shift_index')
    if shift_index is None or not isinstance(shift_index, int):
        return jsonify({'message': 'shift_index (integer) is required.'}), 400

    notes = (data.get('notes') or '').strip()

    shift_log = load_json_data(SHIFT_FILE)
    if shift_index < 0 or shift_index >= len(shift_log):
        return jsonify({'message': 'Invalid shift_index.'}), 404

    shift = shift_log[shift_index]
    old_notes = shift.get('notes')
    if notes:
        shift['notes'] = notes
    else:
        shift.pop('notes', None)

    save_json_data(SHIFT_FILE, shift_log)

    users = load_json_data(USERS_FILE)
    admin_user = users.get(admin_pin, {})
    admin_name = admin_user.get('name', admin_pin)

    log_activity('shift_note_edited', admin_pin, admin_user.get('role', 'admin'), {
        'shift_index': shift_index,
        'user_id': shift.get('user_id'),
        'user_name': shift.get('user_name'),
        'old_notes': old_notes,
        'new_notes': notes
    })

    return jsonify({
        'message': 'Shift notes updated.' if notes else 'Shift notes cleared.',
        'notes': notes
    })


@app.route('/api/clock/excuse_late', methods=['POST'])
def clock_excuse_late():
    """Admin excuses a late shift (sets late_excused = true)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_index = data.get('shift_index')
    if shift_index is None or not isinstance(shift_index, int):
        return jsonify({'message': 'shift_index (integer) is required.'}), 400

    note = (data.get('note') or '').strip()

    shift_log = load_json_data(SHIFT_FILE)
    if shift_index < 0 or shift_index >= len(shift_log):
        return jsonify({'message': 'Invalid shift_index.'}), 404

    shift = shift_log[shift_index]

    # Check if this shift's period is locked
    lock_check = load_json_data(APPROVALS_FILE)
    ci = shift.get('clock_in_time', '')
    for app in lock_check:
        if app.get('status') in ('pending', 'approved'):
            if shift_in_period(ci, app.get('date_from', ''), app.get('date_to', '')):
                return jsonify({'message': f'Cannot excuse: pay period locked for approval. Owner must unlock first.'}), 423

    old_late_excused = shift.get('late_excused', False)
    if old_late_excused:
        return jsonify({'message': 'Shift is already excused.'}), 409

    old_late_note = shift.get('late_note')
    shift['late_excused'] = True
    if note:
        shift['late_note'] = note

    save_json_data(SHIFT_FILE, shift_log)

    users = load_json_data(USERS_FILE)
    admin_user = users.get(admin_pin, {})
    admin_name = admin_user.get('name', admin_pin)

    log_activity('late_excused', admin_pin, admin_user.get('role', 'admin'), {
        'admin_pin': admin_pin,
        'admin_name': admin_name,
        'shift_index': shift_index,
        'user_id': shift.get('user_id'),
        'user_name': shift.get('user_name'),
        'old_late_excused': old_late_excused,
        'new_late_excused': True,
        'note': note
    })

    return jsonify({
        'message': 'Shift late mark excused successfully.',
        'shift': shift
    })


@app.route('/api/clock/flag_late', methods=['POST'])
def clock_flag_late():
    """Admin manually flags a shift as late (with late_minutes)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_index = data.get('shift_index')
    if shift_index is None or not isinstance(shift_index, int):
        return jsonify({'message': 'shift_index (integer) is required.'}), 400

    late_minutes = data.get('late_minutes')
    if late_minutes is None or not isinstance(late_minutes, (int, float)):
        return jsonify({'message': 'late_minutes (number) is required.'}), 400
    late_minutes = int(round(late_minutes))

    note = (data.get('note') or '').strip()

    shift_log = load_json_data(SHIFT_FILE)
    if shift_index < 0 or shift_index >= len(shift_log):
        return jsonify({'message': 'Invalid shift_index.'}), 404

    shift = shift_log[shift_index]

    # Check if this shift's period is locked
    lock_check2 = load_json_data(APPROVALS_FILE)
    ci2 = shift.get('clock_in_time', '')
    for app in lock_check2:
        if app.get('status') in ('pending', 'approved'):
            if shift_in_period(ci2, app.get('date_from', ''), app.get('date_to', '')):
                return jsonify({'message': f'Cannot flag: pay period locked for approval. Owner must unlock first.'}), 423

    old_late_minutes = shift.get('late_minutes')
    old_late_excused = shift.get('late_excused', False)

    shift['late_minutes'] = late_minutes
    shift['late_excused'] = False  # freshly flagged, not excused
    if note:
        shift['late_note'] = note

    save_json_data(SHIFT_FILE, shift_log)

    users = load_json_data(USERS_FILE)
    admin_user = users.get(admin_pin, {})
    admin_name = admin_user.get('name', admin_pin)

    log_activity('late_flagged', admin_pin, admin_user.get('role', 'admin'), {
        'admin_pin': admin_pin,
        'admin_name': admin_name,
        'shift_index': shift_index,
        'user_id': shift.get('user_id'),
        'user_name': shift.get('user_name'),
        'old_late_minutes': old_late_minutes,
        'new_late_minutes': late_minutes,
        'old_late_excused': old_late_excused,
        'new_late_excused': False,
        'note': note
    })

    return jsonify({
        'message': 'Shift flagged as late successfully.',
        'shift': shift
    })


@app.route('/api/clock/break', methods=['POST'])
def clock_break():
    """Start or end a break for a clocked-in employee."""
    data = request.json
    user_id = data.get('adminPin')
    action = data.get('action', '').strip().lower()

    if not user_id:
        return jsonify({'message': 'User ID required.'}), 400

    if action not in ('start', 'end'):
        return jsonify({'message': 'Action must be "start" or "end".'}), 400

    if user_id not in active_shifts:
        return jsonify({'message': 'Not clocked in.'}), 409

    shift = active_shifts[user_id]

    if action == 'start':
        if shift.get('on_break'):
            return jsonify({'message': 'Already on break.'}), 409
        if 'breaks' not in shift:
            shift['breaks'] = []
        shift['breaks'].append({
            'start': datetime.now().isoformat(),
            'end': None,
            'duration_minutes': None
        })
        shift['on_break'] = True
        return jsonify({
            'message': 'Break started.',
            'on_break': True,
            'break_count': len(shift['breaks'])
        })
    else:  # action == 'end'
        if not shift.get('on_break'):
            return jsonify({'message': 'Not currently on break.'}), 409
        breaks = shift.get('breaks', [])
        # Find the last break without an end
        for b in reversed(breaks):
            if b.get('end') is None and b.get('start'):
                try:
                    start_dt = datetime.fromisoformat(b['start'])
                    end_dt = datetime.now()
                    duration = (end_dt - start_dt).total_seconds() / 60
                    b['end'] = end_dt.isoformat()
                    b['duration_minutes'] = round(duration, 1)
                except (ValueError, TypeError):
                    b['end'] = datetime.now().isoformat()
                    b['duration_minutes'] = 0
                break
        shift['on_break'] = False
        total_break_minutes = sum(
            bk.get('duration_minutes', 0) or 0
            for bk in shift.get('breaks', [])
        )
        return jsonify({
            'message': 'Break ended.',
            'on_break': False,
            'break_duration_minutes': total_break_minutes,
            'break_count': len(shift.get('breaks', []))
        })


@app.route('/api/clock/missing_clockout', methods=['POST'])
def clock_missing_clockout():
    """Detect active shifts over 8 hours (potential forgotten clock-outs)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    now = datetime.now()
    threshold_hours = 8
    users = load_json_data(USERS_FILE)
    overdue = []

    for uid, shift in list(active_shifts.items()):
        duration_hours = (now - shift['clock_in_time']).total_seconds() / 3600
        if duration_hours >= threshold_hours:
            user_data = users.get(uid, {})
            overdue.append({
                'user_id': uid,
                'user_name': shift.get('user_name', user_data.get('name', 'Unknown')),
                'clock_in_time': shift['clock_in_time'].isoformat(),
                'duration_hours': round(duration_hours, 2),
                'on_break': shift.get('on_break', False),
                'breaks': shift.get('breaks', []),
                'scheduled_start': shift.get('scheduled_start'),
                'late_minutes': shift.get('late_minutes'),
                'late_excused': shift.get('late_excused', False),
                'late_note': shift.get('late_note')
            })

    return jsonify({
        'count': len(overdue),
        'overdue_shifts': overdue
    })


@app.route('/api/clock/force_out', methods=['POST'])
def clock_force_out():
    """Admin force-clocks out an employee with estimated time + reason."""
    data = request.json
    admin_pin = data.get('adminPin')
    target_user_id = (data.get('user_id') or '').strip()
    clock_out_str = (data.get('clock_out_time') or '').strip()
    reason = (data.get('reason') or '').strip()

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not target_user_id:
        return jsonify({'message': 'Target user_id is required.'}), 400

    if not reason:
        return jsonify({'message': 'Reason is required.'}), 400

    if target_user_id not in active_shifts:
        return jsonify({'message': 'User is not clocked in.'}), 409

    now = datetime.now()

    # Parse estimated clock-out time
    if clock_out_str and clock_out_str.lower() != 'now':
        try:
            clock_out_time = datetime.fromisoformat(clock_out_str)
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid clock_out_time format. Use ISO format or "now".'}), 400
    else:
        clock_out_time = now

    users = load_json_data(USERS_FILE)
    user_data = users.get(target_user_id, {})

    shift = active_shifts.pop(target_user_id)
    clock_in_time = shift['clock_in_time']
    duration_hours = round((clock_out_time - clock_in_time).total_seconds() / 3600, 2)

    # Calculate break total
    breaks = shift.get('breaks', [])
    total_break_minutes = 0
    completed_breaks = []
    for b in breaks:
        if b.get('end') is None and b.get('start'):
            try:
                start_dt = datetime.fromisoformat(b['start'])
                dur = (clock_out_time - start_dt).total_seconds() / 60
                b['end'] = clock_out_time.isoformat()
                b['duration_minutes'] = round(dur, 1)
            except (ValueError, TypeError):
                b['end'] = clock_out_time.isoformat()
                b['duration_minutes'] = 0
        mins = b.get('duration_minutes', 0) or 0
        total_break_minutes += mins
        completed_breaks.append(b)

    break_hours = round(total_break_minutes / 60, 2)
    paid_hours = round(duration_hours - break_hours, 2)

    shift_record = {
        'user_id': target_user_id,
        'user_name': shift.get('user_name', user_data.get('name', 'Unknown')),
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours,
        'breaks': completed_breaks,
        'break_hours': break_hours,
        'paid_hours': paid_hours,
        'scheduled_start': shift.get('scheduled_start'),
        'late_minutes': shift.get('late_minutes'),
        'late_excused': shift.get('late_excused', False),
        'late_note': shift.get('late_note'),
        'forced': True,
        'force_out_reason': reason,
        'force_out_by': admin_pin,
        'force_out_at': now.isoformat()
    }

    shift_log = load_json_data(SHIFT_FILE)
    shift_log.append(shift_record)
    save_json_data(SHIFT_FILE, shift_log)

    log_activity('clock_force_out', admin_pin, user_data.get('role', 'admin'), {
        'action': 'force_clock_out',
        'target_user': target_user_id,
        'target_user_name': shift_record['user_name'],
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours,
        'reason': reason
    })

    return jsonify({
        'message': f'Force clocked out {shift_record["user_name"]} successfully.',
        'user_name': shift_record['user_name'],
        'clock_in_time': clock_in_time.isoformat(),
        'clock_out_time': clock_out_time.isoformat(),
        'duration_hours': duration_hours,
        'paid_hours': paid_hours,
        'reason': reason
    })


@app.route('/api/admin_shifts', methods=['POST'])
def admin_shifts():
    """Get all shift records (completed) for admin timesheet view."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)

    # Apply optional date range filtering on clock_in_time
    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    if date_from or date_to:
        filtered = []
        for entry in shift_log:
            clock_in_str = entry.get('clock_in_time', '')
            if not clock_in_str:
                continue
            try:
                clock_in_dt = datetime.fromisoformat(clock_in_str)
            except (ValueError, TypeError):
                continue
            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from)
                    if clock_in_dt < dt_from:
                        continue
                except ValueError:
                    pass
            if date_to:
                try:
                    if 'T' not in date_to:
                        dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                    else:
                        dt_to = datetime.fromisoformat(date_to)
                    if clock_in_dt > dt_to:
                        continue
                except ValueError:
                    pass
            filtered.append(entry)
        shift_log = filtered

    # Also include active (currently clocked-in) shifts
    active_shift_list = []
    for uid, shift in active_shifts.items():
        users = load_json_data(USERS_FILE)
        user_data = users.get(uid, {})
        now = datetime.now()
        duration_hours = round((now - shift['clock_in_time']).total_seconds() / 3600, 2)
        breaks = shift.get('breaks', [])
        total_break_minutes = sum(
            (b.get('duration_minutes') or 0) for b in breaks
            if b.get('duration_minutes') is not None
        )
        if shift.get('on_break'):
            for b in reversed(breaks):
                if b.get('end') is None and b.get('start'):
                    try:
                        sd = datetime.fromisoformat(b['start'])
                        total_break_minutes += (now - sd).total_seconds() / 60
                    except (ValueError, TypeError):
                        pass
                    break
        break_hours = round(total_break_minutes / 60, 2)
        active_shift_list.append({
            'user_id': uid,
            'user_name': shift.get('user_name', user_data.get('name', 'Unknown')),
            'clock_in_time': shift['clock_in_time'].isoformat(),
            'clock_out_time': None,
            'duration_hours': duration_hours,
            'active': True,
            'on_break': shift.get('on_break', False),
            'breaks': breaks,
            'break_hours': break_hours,
            'paid_hours': round(duration_hours - break_hours, 2),
            'late_minutes': shift.get('late_minutes'),
            'late_excused': shift.get('late_excused', False),
            'scheduled_start': shift.get('scheduled_start')
        })

    return jsonify({
        'message': 'Shift data retrieved',
        'shifts': shift_log,
        'active_shifts': active_shift_list
    })


@app.route('/api/employee/my_pay', methods=['POST'])
def employee_my_pay():
    """Employee-facing pay info: current period, pay history, YTD totals.
    No admin permission required — user can only see their own data.
    """
    data = request.json
    user_id = (data.get('userId') or '').strip()

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = users[user_id]
    pay_rate = user_data.get('pay_rate')
    has_pay_rate = pay_rate is not None and pay_rate > 0
    pay_rate_val = pay_rate or 0
    user_name = user_data.get('name', 'Unknown')

    shift_log = load_json_data(SHIFT_FILE)

    # Filter shifts for this user only
    user_shifts = [s for s in shift_log if s.get('user_id') == user_id]

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Calculate current week (Mon-Sun)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

    # Helper to get paid hours from a shift
    def get_paid_hours(s):
        return s.get('paid_hours', s.get('duration_hours', 0))

    # Load orders for tip aggregation
    orders_data = load_json_data(ORDERS_FILE)
    user_orders = [o for o in orders_data if o.get('user') == user_id]

    # Helper to get tip from an order safely
    def get_tip(o):
        return float(o.get('tip_amount') or 0)

    # --- Current Period (this week) ---
    current_shifts = []
    current_period_hours = 0.0
    active_shift_hours = 0.0
    is_clocked_in = user_id in active_shifts

    for s in user_shifts:
        ck = s.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
        except (ValueError, TypeError):
            continue
        if monday <= dt <= sunday:
            paid = get_paid_hours(s)
            current_shifts.append({
                'clock_in_time': ck,
                'clock_out_time': s.get('clock_out_time', ''),
                'duration_hours': s.get('duration_hours', 0),
                'paid_hours': paid,
                'break_hours': s.get('break_hours', 0),
                'active': False,
                'pay_rate': s.get('pay_rate')  # Per-shift rate override
            })
            current_period_hours += paid

    # Include active shift if clocked in
    if is_clocked_in:
        active_shift = active_shifts[user_id]
        active_duration = round((now - active_shift['clock_in_time']).total_seconds() / 3600, 2)
        breaks = active_shift.get('breaks', [])
        total_break_minutes = sum(
            (b.get('duration_minutes') or 0) for b in breaks
            if b.get('duration_minutes') is not None
        )
        if active_shift.get('on_break'):
            for b in reversed(breaks):
                if b.get('end') is None and b.get('start'):
                    try:
                        sd = datetime.fromisoformat(b['start'])
                        total_break_minutes += (now - sd).total_seconds() / 60
                    except (ValueError, TypeError):
                        pass
                    break
        active_break_hours = round(total_break_minutes / 60, 2)
        active_paid = round(max(0, active_duration - active_break_hours), 2)
        active_shift_hours = active_paid
        current_period_hours += active_paid
        current_shifts.append({
            'clock_in_time': active_shift['clock_in_time'].isoformat(),
            'clock_out_time': None,
            'duration_hours': active_duration,
            'paid_hours': active_paid,
            'break_hours': active_break_hours,
            'active': True,
            'pay_rate': pay_rate_val if has_pay_rate else None  # Current rate for active shift
        })

    current_period_hours = round(current_period_hours, 2)
    estimated_gross = round(current_period_hours * pay_rate_val, 2) if has_pay_rate else None

    # Aggregate tips for current period from orders
    current_period_tips = 0.0
    current_tip_count = 0
    for o in user_orders:
        odate = o.get('date', '')
        if not odate:
            continue
        try:
            odt = datetime.fromisoformat(odate)
        except (ValueError, TypeError):
            continue
        if monday <= odt <= sunday:
            tip = get_tip(o)
            if tip > 0:
                current_period_tips += tip
                current_tip_count += 1
    current_period_tips = round(current_period_tips, 2)

    current_period = {
        'start_date': monday.strftime('%Y-%m-%d'),
        'end_date': sunday.strftime('%Y-%m-%d'),
        'hours': current_period_hours,
        'pay_rate': pay_rate_val if has_pay_rate else None,
        'has_pay_rate': has_pay_rate,
        'estimated_gross': estimated_gross,
        'shift_count': len(current_shifts),
        'is_clocked_in': is_clocked_in,
        'active_shift_hours': active_shift_hours,
        'tips': current_period_tips,
        'tip_count': current_tip_count,
        'shifts': current_shifts
    }

    # --- Pay History (past periods, grouped by week) ---
    # Collect all week keys from completed shifts
    week_map = {}
    for s in user_shifts:
        ck = s.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
        except (ValueError, TypeError):
            continue
        # Week starting Monday
        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime('%Y-%m-%d')
        if week_key not in week_map:
            week_map[week_key] = {
                'start_date': week_start.strftime('%Y-%m-%d'),
                'end_date': (week_start + timedelta(days=6)).strftime('%Y-%m-%d'),
                'hours': 0.0,
                'shift_count': 0,
                'pay_rate': pay_rate_val if has_pay_rate else None,
                'has_pay_rate': has_pay_rate,
                'estimated_gross': 0.0,
                'tips': 0.0,
                'tip_count': 0,
                'shifts': []
            }
        paid = get_paid_hours(s)
        week_map[week_key]['hours'] += paid
        week_map[week_key]['shift_count'] += 1
        week_map[week_key]['shifts'].append({
            'clock_in_time': ck,
            'clock_out_time': s.get('clock_out_time', ''),
            'duration_hours': s.get('duration_hours', 0),
            'paid_hours': paid,
            'break_hours': s.get('break_hours', 0),
            'pay_rate': s.get('pay_rate')  # Per-shift rate override
        })

    # Round hours and calculate gross for each period using per-shift rates
    # Also aggregate tips from orders for each period
    for wk in week_map.values():
        wk['hours'] = round(wk['hours'], 2)
        wk_gross = 0.0
        wk_has_rate = False
        for shift in wk['shifts']:
            srate = shift.get('pay_rate') or pay_rate_val or 0
            if srate > 0:
                wk_has_rate = True
            wk_gross += shift.get('paid_hours', 0) * srate
        wk['estimated_gross'] = round(wk_gross, 2) if wk_has_rate else None
        wk['has_pay_rate'] = wk_has_rate
        # Effective rate for this period
        wk_rate = round(wk_gross / wk['hours'], 2) if wk_has_rate and wk['hours'] > 0 else pay_rate_val
        wk['pay_rate'] = wk_rate if wk_has_rate else (pay_rate_val if has_pay_rate else None)

        # Aggregate tips from orders for this period
        try:
            ws = datetime.strptime(wk['start_date'], '%Y-%m-%d')
            we = datetime.strptime(wk['end_date'], '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
        except (ValueError, TypeError):
            ws = we = None
        if ws and we:
            wk_tips = 0.0
            wk_tip_count = 0
            for o in user_orders:
                odate = o.get('date', '')
                if not odate:
                    continue
                try:
                    odt = datetime.fromisoformat(odate)
                except (ValueError, TypeError):
                    continue
                if ws <= odt <= we:
                    tip = get_tip(o)
                    if tip > 0:
                        wk_tips += tip
                        wk_tip_count += 1
            wk['tips'] = round(wk_tips, 2)
            wk['tip_count'] = wk_tip_count

    # Sort periods newest first, exclude current week (already in current_period)
    current_week_key = monday.strftime('%Y-%m-%d')
    past_periods = sorted(
        [wk for wk_key, wk in week_map.items() if wk_key != current_week_key],
        key=lambda p: p['start_date'],
        reverse=True
    )

    # --- Year-to-Date ---
    ytd_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    ytd_hours = 0.0
    ytd_shift_count = 0
    for s in user_shifts:
        ck = s.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
        except (ValueError, TypeError):
            continue
        if dt >= ytd_start:
            paid = get_paid_hours(s)
            ytd_hours += paid
            ytd_shift_count += 1

    # Include active shift in YTD
    if is_clocked_in:
        ytd_hours += active_shift_hours
        ytd_shift_count += 1

    ytd_hours = round(ytd_hours, 2)
    ytd_gross = round(ytd_hours * pay_rate_val, 2) if has_pay_rate else None

    # Calculate average hours per week YTD
    days_since_jan1 = (now.date() - ytd_start.date()).days
    num_weeks_ytd = max(1, round(days_since_jan1 / 7, 1)) if days_since_jan1 > 0 else 1
    avg_hours_per_week = round(ytd_hours / num_weeks_ytd, 1) if ytd_hours > 0 else 0

    # Average hourly rate (effective or base)
    if has_pay_rate and ytd_hours > 0:
        avg_hourly_rate = round(ytd_gross / ytd_hours, 2) if ytd_gross else pay_rate_val
        avg_hourly_rate = max(avg_hourly_rate, pay_rate_val)  # floor at pay_rate
    elif has_pay_rate:
        avg_hourly_rate = pay_rate_val
    else:
        avg_hourly_rate = None

    # Aggregate YTD tips from orders
    ytd_tips = 0.0
    ytd_tip_count = 0
    for o in user_orders:
        odate = o.get('date', '')
        if not odate:
            continue
        try:
            odt = datetime.fromisoformat(odate)
        except (ValueError, TypeError):
            continue
        if odt >= ytd_start:
            tip = get_tip(o)
            if tip > 0:
                ytd_tips += tip
                ytd_tip_count += 1
    ytd_tips = round(ytd_tips, 2)

    ytd = {
        'hours': ytd_hours,
        'gross_pay': ytd_gross,
        'has_pay_rate': has_pay_rate,
        'shift_count': ytd_shift_count,
        'pay_rate': pay_rate_val if has_pay_rate else None,
        'avg_hours_per_week': avg_hours_per_week,
        'avg_hourly_rate': avg_hourly_rate,
        'tips': ytd_tips,
        'tip_count': ytd_tip_count
    }

    return jsonify({
        'message': 'Employee pay data retrieved',
        'user_name': user_name,
        'pay_rate': pay_rate_val if has_pay_rate else None,
        'has_pay_rate': has_pay_rate,
        'current_period': current_period,
        'pay_history': past_periods,
        'ytd': ytd
    })


@app.route('/api/employee/pay_stub_pdf', methods=['POST'])
def employee_pay_stub_pdf():
    """Generate a printable HTML pay stub for an employee for a specific pay period.
    Returns printer-friendly HTML for use with browser Print → Save as PDF.
    """
    data = request.json
    user_id = (data.get('userId') or '').strip()
    start_date = (data.get('start_date') or '').strip()

    if not user_id or not start_date:
        return jsonify({'message': 'userId and start_date are required.'}), 400

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = users[user_id]
    user_name = user_data.get('name', 'Unknown')
    pay_rate = user_data.get('pay_rate') or 0
    has_pay_rate = pay_rate > 0

    # Calculate the week range (Mon-Sun) from the start_date
    try:
        week_start = datetime.fromisoformat(start_date)
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid start_date format. Use YYYY-MM-DD.'}), 400

    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    shift_log = load_json_data(SHIFT_FILE)

    # Filter shifts for this user within this week
    user_shifts = []
    for s in shift_log:
        if s.get('user_id') != user_id:
            continue
        ck = s.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
        except (ValueError, TypeError):
            continue
        if week_start <= dt <= week_end:
            user_shifts.append(s)

    # Sort by clock_in_time
    user_shifts.sort(key=lambda x: x.get('clock_in_time', ''))

    # Calculate totals
    total_paid_hours = 0.0
    total_duration_hours = 0.0
    total_break_hours = 0.0
    for s in user_shifts:
        dur = s.get('duration_hours', 0)
        paid = s.get('paid_hours', dur)
        total_duration_hours += dur
        total_paid_hours += paid
        total_break_hours += s.get('break_hours', 0)

    total_paid_hours = round(total_paid_hours, 2)
    # Calculate gross pay using per-shift rates
    gross_pay = 0.0
    gross_has_rate = False
    for s in user_shifts:
        sp = s.get('paid_hours', s.get('duration_hours', 0))
        sr = s.get('pay_rate') or pay_rate
        if s.get('pay_rate'):
            gross_has_rate = True
        gross_pay += sp * sr
    gross_pay = round(gross_pay, 2) if (has_pay_rate or gross_has_rate) else 0
    # Effective rate for display
    eff_rate = round(gross_pay / total_paid_hours, 2) if (has_pay_rate or gross_has_rate) and total_paid_hours > 0 else pay_rate

    # YTD calculations
    now = datetime.now()
    ytd_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    ytd_hours = 0.0
    ytd_shift_count = 0
    for s in shift_log:
        if s.get('user_id') != user_id:
            continue
        ck = s.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
        except (ValueError, TypeError):
            continue
        if dt >= ytd_start:
            dur = s.get('duration_hours', 0)
            paid = s.get('paid_hours', dur)
            ytd_hours += paid
            ytd_shift_count += 1
    ytd_hours = round(ytd_hours, 2)
    ytd_gross = round(ytd_hours * pay_rate, 2) if has_pay_rate else 0

    # Include active shift in YTD if applicable
    if user_id in active_shifts:
        active_shift = active_shifts[user_id]
        active_duration = round((now - active_shift['clock_in_time']).total_seconds() / 3600, 2)
        breaks = active_shift.get('breaks', [])
        total_break_minutes = sum(
            (b.get('duration_minutes') or 0) for b in breaks
            if b.get('duration_minutes') is not None
        )
        if active_shift.get('on_break'):
            for b in reversed(breaks):
                if b.get('end') is None and b.get('start'):
                    try:
                        sd = datetime.fromisoformat(b['start'])
                        total_break_minutes += (now - sd).total_seconds() / 60
                    except (ValueError, TypeError):
                        pass
                    break
        active_break_hours = round(total_break_minutes / 60, 2)
        active_paid = round(max(0, active_duration - active_break_hours), 2)
        ytd_hours += active_paid
        ytd_shift_count += 1
        ytd_hours = round(ytd_hours, 2)
        # Recalculate YTD gross with per-shift rates
        ytd_gross = 0.0
        ytd_has_rate = False
        for s in shift_log:
            if s.get('user_id') != user_id:
                continue
            ck = s.get('clock_in_time', '')
            if not ck:
                continue
            try:
                dt = datetime.fromisoformat(ck)
            except (ValueError, TypeError):
                continue
            if dt >= ytd_start:
                sp = s.get('paid_hours', s.get('duration_hours', 0))
                sr = s.get('pay_rate') or pay_rate
                if s.get('pay_rate'):
                    ytd_has_rate = True
                ytd_gross += sp * sr
        ytd_gross = round(ytd_gross, 2) if (has_pay_rate or ytd_has_rate) else 0

    period_label = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Build shift detail rows
    shift_rows = ''
    for s in user_shifts:
        ci = s.get('clock_in_time', '—')
        co = s.get('clock_out_time', '—')
        dur = s.get('duration_hours', 0)
        paid = s.get('paid_hours', dur)
        bk = s.get('break_hours', 0)
        # Parse date nicely
        try:
            d = datetime.fromisoformat(ci)
            date_str = d.strftime('%a %b %d')
            in_str = d.strftime('%I:%M %p').lstrip('0')
        except (ValueError, TypeError):
            date_str = ci
            in_str = ci
        try:
            if co:
                d_out = datetime.fromisoformat(co)
                out_str = d_out.strftime('%I:%M %p').lstrip('0')
            else:
                out_str = '—'
        except (ValueError, TypeError):
            out_str = co or '—'
        shift_rows += f'''<tr>
            <td>{date_str}</td>
            <td>{in_str}</td>
            <td>{out_str}</td>
            <td>{dur:.2f}</td>
            <td>{paid:.2f}</td>
            <td>{bk:.2f}</td>
        </tr>'''

    if not shift_rows:
        shift_rows = '<tr><td colspan="6" style="text-align:center;color:#999;">No shifts in this period.</td></tr>'

    # Pre-compute strings to avoid f-string expression limitations
    pay_rate_row = ''
    if has_pay_rate or gross_has_rate:
        pay_rate_row = f'<tr><td class="total-label">Pay Rate</td><td class="right total-value pay-rate">${eff_rate:.2f}/hr</td></tr>'
    gross_pay_str = f'${gross_pay:,.2f}' if (has_pay_rate or gross_has_rate) else '$0.00'
    ytd_gross_str = f'${ytd_gross:,.2f}' if (has_pay_rate or ytd_has_rate) else '$0.00'
    rate_display = f'${eff_rate:.2f}/hr' if (has_pay_rate or gross_has_rate) else 'Not set'
    safe_name = _html.escape(user_name)
    safe_id = _html.escape(user_id)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pay Stub — {safe_name}</title>
<style>
  @page {{ margin: 15mm 12mm; size: letter; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; color: #222; line-height: 1.5; margin: 0; padding: 0; }}
  .header {{ text-align: center; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 3px solid #1a1a2e; }}
  .header h1 {{ font-size: 20pt; margin: 0 0 4px; color: #1a1a2e; }}
  .header .business {{ font-size: 11pt; color: #666; }}
  .header .period {{ font-size: 10pt; color: #888; }}
  .employee-info {{ display: flex; justify-content: space-between; margin-bottom: 16px; padding: 12px 14px; background: #f5f5fa; border-radius: 6px; }}
  .employee-info div {{ font-size: 10pt; }}
  .employee-info .label {{ color: #888; font-size: 8pt; text-transform: uppercase; letter-spacing: 0.5px; }}
  .employee-info .value {{ font-weight: 600; font-size: 11pt; color: #1a1a2e; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
  th {{ background: #1a1a2e; color: #fff; padding: 7px 8px; text-align: left; font-size: 8pt; text-transform: uppercase; letter-spacing: 0.3px; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; font-size: 9pt; }}
  tr:nth-child(even) {{ background: #f8f8fc; }}
  .right {{ text-align: right; }}
  .center {{ text-align: center; }}
  .summary {{ margin-top: 6px; }}
  .summary table {{ margin-bottom: 0; }}
  .summary td {{ border: none; padding: 4px 8px; font-size: 9pt; }}
  .summary .total-label {{ font-weight: 600; color: #1a1a2e; }}
  .summary .total-value {{ font-weight: 700; font-size: 10pt; color: #1a1a2e; }}
  .grand-total td {{ font-weight: 700; font-size: 10pt; border-top: 2px solid #1a1a2e; padding-top: 8px; color: #1a1a2e; }}
  .pay-rate {{ color: #666; }}
  .footer {{ margin-top: 30px; font-size: 8pt; color: #aaa; text-align: center; border-top: 1px solid #ddd; padding-top: 8px; }}
  .footer strong {{ color: #666; }}
  .print-btn {{ display: block; margin: 20px auto; padding: 12px 30px; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; font-size: 12pt; cursor: pointer; }}
  @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">🖨️ Print / Save PDF</button>

<div class="header">
  <h1>Pay Stub</h1>
  <div class="business">POS System</div>
  <div class="period">Pay Period: {period_label}</div>
</div>

<div class="employee-info">
  <div>
    <div class="label">Employee</div>
    <div class="value">{safe_name}</div>
  </div>
  <div>
    <div class="label">Employee ID</div>
    <div class="value">{safe_id}</div>
  </div>
  <div>
    <div class="label">Pay Rate</div>
    <div class="value">{rate_display}</div>
  </div>
  <div>
    <div class="label">Generated</div>
    <div class="value">{now_str}</div>
  </div>
</div>

<h3 style="font-size:11pt;color:#1a1a2e;margin:16px 0 8px;">Shift Details</h3>
<table>
<thead>
<tr>
  <th>Date</th>
  <th>Clock In</th>
  <th>Clock Out</th>
  <th class="right">Duration (h)</th>
  <th class="right">Paid (h)</th>
  <th class="right">Break (h)</th>
</tr>
</thead>
<tbody>
{shift_rows}
</tbody>
</table>

<div class="summary">
<table>
  <tr>
    <td class="total-label">Total Duration Hours</td>
    <td class="right total-value">{total_duration_hours:.2f}</td>
  </tr>
  <tr>
    <td class="total-label">Total Break Hours</td>
    <td class="right total-value">{total_break_hours:.2f}</td>
  </tr>
  <tr>
    <td class="total-label">Total Paid Hours</td>
    <td class="right total-value">{total_paid_hours:.2f}</td>
  </tr>
  {pay_rate_row}
  <tr class="grand-total">
    <td>Gross Pay (This Period)</td>
    <td class="right">{gross_pay_str}</td>
  </tr>
</table>
</div>

<div style="margin-top:20px;padding-top:14px;border-top:1px solid #ddd;">
  <h3 style="font-size:11pt;color:#1a1a2e;margin:0 0 8px;">Year-to-Date Summary</h3>
  <table>
    <tr><td>Total Hours</td><td class="right">{ytd_hours:.2f}</td></tr>
    <tr><td>Total Shifts</td><td class="right">{ytd_shift_count}</td></tr>
    <tr style="font-weight:700;color:#1a1a2e;"><td>YTD Gross Pay</td><td class="right">{ytd_gross_str}</td></tr>
  </table>
</div>

<div class="footer">
  <strong>POS System</strong> — Pay Stub generated on {now_str}<br>
  This is not an official tax document. For informational purposes only.
</div>

<script>
  // Auto-print for "Open in new tab" workflow
  if (window.location.search.includes('autoPrint=true')) {{
    window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 500); }};
  }}
</script>
</body>
</html>'''

    period_slug = week_start.strftime('%Y-%m-%d')
    return jsonify({
        'html': html,
        'filename': f'pay_stub_{user_id}_{period_slug}.html'
    })


@app.route('/api/employee/pay_history_csv', methods=['POST'])
def employee_pay_history_csv():
    """Export employee pay history as CSV.
    Employee-facing: no admin permission required — user can only export their own data.
    """
    data = request.json
    user_id = (data.get('userId') or '').strip()

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_data = users[user_id]
    pay_rate = user_data.get('pay_rate')
    has_pay_rate = pay_rate is not None and pay_rate > 0
    pay_rate_val = pay_rate or 0
    user_name = user_data.get('name', 'Unknown')

    shift_log = load_json_data(SHIFT_FILE)

    # Filter shifts for this user only
    user_shifts = [s for s in shift_log if s.get('user_id') == user_id]

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Calculate current week (Mon-Sun) to exclude from history
    monday = today - timedelta(days=today.weekday())
    current_week_key = monday.strftime('%Y-%m-%d')

    def get_paid_hours(s):
        return s.get('paid_hours', s.get('duration_hours', 0))

    # Group completed shifts by week
    week_map = {}
    for s in user_shifts:
        ck = s.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
        except (ValueError, TypeError):
            continue
        # Week starting Monday
        week_start = dt - timedelta(days=dt.weekday())
        week_key = week_start.strftime('%Y-%m-%d')
        if week_key == current_week_key:
            continue  # Skip current period
        if week_key not in week_map:
            week_map[week_key] = {
                'start_date': week_start.strftime('%Y-%m-%d'),
                'end_date': (week_start + timedelta(days=6)).strftime('%Y-%m-%d'),
                'hours': 0.0,
                'shift_count': 0,
                'pay_rate': pay_rate_val if has_pay_rate else 0,
                'has_pay_rate': has_pay_rate,
                'estimated_gross': 0.0
            }
        paid = get_paid_hours(s)
        week_map[week_key]['hours'] += paid
        week_map[week_key]['shift_count'] += 1

    # Sort periods newest first
    past_periods = sorted(
        week_map.values(),
        key=lambda p: p['start_date'],
        reverse=True
    )

    headers = ['Period Start', 'Period End', 'Shifts', 'Total Hours', 'Pay Rate', 'Gross Pay']
    rows = []
    for period in past_periods:
        hours = round(period['hours'], 2)
        gross = round(hours * pay_rate_val, 2) if has_pay_rate else 0
        rate_display = f"${pay_rate_val:.2f}/hr" if has_pay_rate else 'N/A'
        gross_display = f"${gross:.2f}" if has_pay_rate else 'N/A'
        rows.append({
            'Period Start': period['start_date'],
            'Period End': period['end_date'],
            'Shifts': period['shift_count'],
            'Total Hours': hours,
            'Pay Rate': rate_display,
            'Gross Pay': gross_display
        })

    csv_content = generate_csv(rows, headers)
    return jsonify({
        'csv': csv_content,
        'filename': f'pay_history_{user_id}.csv'
    })


@app.route('/api/export/shifts_csv', methods=['POST'])
def export_shifts_csv():
    """Export employee shift records as CSV."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)

    # Apply optional date range filtering on clock_in_time
    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    if date_from or date_to:
        filtered = []
        for entry in shift_log:
            clock_in_str = entry.get('clock_in_time', '')
            if not clock_in_str:
                continue
            try:
                clock_in_dt = datetime.fromisoformat(clock_in_str)
            except (ValueError, TypeError):
                continue
            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from)
                    if clock_in_dt < dt_from:
                        continue
                except ValueError:
                    pass
            if date_to:
                try:
                    if 'T' not in date_to:
                        dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                    else:
                        dt_to = datetime.fromisoformat(date_to)
                    if clock_in_dt > dt_to:
                        continue
                except ValueError:
                    pass
            filtered.append(entry)
        shift_log = filtered

    headers = ['User ID', 'User Name', 'Clock In Time', 'Clock Out Time', 'Duration (Hours)', 'Break (Hours)', 'Paid (Hours)', 'Late (Minutes)', 'Late Excused', 'Notes']

    rows = []
    for entry in shift_log:
        rows.append({
            'User ID': entry.get('user_id', ''),
            'User Name': entry.get('user_name', ''),
            'Clock In Time': entry.get('clock_in_time', ''),
            'Clock Out Time': entry.get('clock_out_time', ''),
            'Duration (Hours)': entry.get('duration_hours', 0),
            'Break (Hours)': entry.get('break_hours', 0),
            'Paid (Hours)': entry.get('paid_hours', entry.get('duration_hours', 0)),
            'Late (Minutes)': entry.get('late_minutes') if entry.get('late_minutes') else '',
            'Late Excused': 'Yes' if entry.get('late_excused') else '',
            'Notes': entry.get('notes', '')
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
    """Returns top 20 most-ordered items by frequency across all orders.
    Requires view_stats permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "view_stats")
    if err_response:
        return err_response
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
    """Returns sales counts grouped by hour of day (0-23) for all time.
    Requires view_stats permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "view_stats")
    if err_response:
        return err_response
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
    """Returns daily revenue for the last 30 days [{date, revenue, order_count}].
    Requires view_stats permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "view_stats")
    if err_response:
        return err_response
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
    """Returns items frequently ordered together (pairs that appear in same order at least 2 times).
    Requires view_stats permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "view_stats")
    if err_response:
        return err_response
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
    Requires view_stats permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "view_stats")
    if err_response:
        return err_response
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
    """Returns quick summary: total_orders_today, revenue_today, avg_order_today, top_item_today, active_users_count.
    Requires view_stats permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "view_stats")
    if err_response:
        return err_response
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


@app.route('/api/users/clear_lockout', methods=['POST'])
def clear_lockout():
    """Admin clears the failed login lockout for a user. Requires manage_users permission."""
    data = request.json
    admin_pin = data.get('adminPin')
    user_id = str(data.get('userId', ''))

    if not admin_pin or not user_id:
        return jsonify({'message': 'Admin PIN and User ID required.'}), 400

    users = load_json_data(USERS_FILE)
    if admin_pin not in users:
        return jsonify({'message': 'Admin not found.'}), 403
    if not check_perm(admin_pin, 'manage_users'):
        return jsonify({'message': 'Permission denied. manage_users required.'}), 403

    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    if user_id in login_failed_attempts:
        del login_failed_attempts[user_id]

    admin_name = users.get(admin_pin, {}).get('name', 'Unknown')
    user_name = users.get(user_id, {}).get('name', 'Unknown')
    log_activity('clear_lockout', admin_pin, users.get(admin_pin, {}).get('role', 'unknown'), {
        'cleared_lockout_for': user_id,
        'user_name': user_name
    })
    return jsonify({'message': f'Login lockout cleared for {user_name}.'})


# ============================================================
# --- Menu History & Restore ---
# ============================================================

@app.route('/api/menu/history', methods=['GET'])
def menu_history():
    """Returns list of all menu backup files, sorted newest first.
    Requires manage_items permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_items")
    if err_response:
        return err_response
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
    """Returns all orders where status is 'pending' or 'preparing', sorted oldest first.
    Orders are grouped by table_number so same-table orders appear together."""
    try:
        orders = load_json_data(ORDERS_FILE)
        active_orders = [o for o in orders if o.get('status') in ('pending', 'preparing')]
        # Sort by table_number first (null/None last), then by date ascending
        def sort_key(o):
            tbl = o.get('table_number')
            # Orders with a table number sort before those without
            tbl_sort = str(tbl).zfill(10) if tbl else 'zzzzzzzzzz'
            date_val = o.get('date', '') or ''
            return (tbl_sort, date_val)
        active_orders.sort(key=sort_key)
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
    """Returns all tables with their assignments, running tab info, and derived status."""
    tables = load_json_data(TABLES_FILE)
    orders = load_json_data(ORDERS_FILE)
    
    def derive_status(table_num, raw_status):
        """Derive smart table status from orders data."""
        table_orders = [o for o in orders if o.get('table_number') == int(table_num)]
        
        if not table_orders:
            return 'empty'
        
        active_orders = [o for o in table_orders if o.get('status') in ('pending', 'preparing')]
        completed_orders = [o for o in table_orders if o.get('status') == 'completed']
        
        # Has preparing orders → order_in_progress
        if any(o.get('status') == 'preparing' for o in active_orders):
            return 'order_in_progress'
        
        # Has pending orders → occupied (order submitted, not yet cooking)
        if any(o.get('status') == 'pending' for o in active_orders):
            return 'occupied'
        
        # Has completed orders with no active orders → needs_bussing
        if completed_orders and not active_orders:
            return 'needs_bussing'
        
        return 'empty'
    
    result = {}
    for table_num, tdata in tables.items():
        # Calculate running tab for this table (unpaid orders)
        table_orders = [o for o in orders if o.get('table_number') == int(table_num) and o.get('status') in ('pending', 'preparing')]
        tab_total = sum(float(o.get('total', 0)) for o in table_orders)
        tab_items_count = sum(len(o.get('items', [])) for o in table_orders)
        
        ds = derive_status(table_num, tdata.get('status', 'available'))
        
        # Count completed unpaid orders (ready to serve)
        completed_unpaid = []
        if ds == 'needs_bussing' or ds == 'empty':
            completed_unpaid = [o for o in orders if o.get('table_number') == int(table_num) and o.get('status') == 'completed']
        
        result[table_num] = {
            'number': tdata.get('number'),
            'name': tdata.get('name', f"Table {table_num}"),
            'tablet_id': tdata.get('tablet_id', ''),
            'status': ds,
            'raw_status': tdata.get('status', 'available'),
            'created_at': tdata.get('created_at', ''),
            'last_bussed_at': tdata.get('last_bussed_at'),
            'tab_total': round(tab_total, 2),
            'tab_order_count': len(table_orders),
            'tab_items_count': tab_items_count,
            'completed_count': len(completed_unpaid) if completed_unpaid else 0
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


@app.route('/api/tables/mark_bussed', methods=['POST'])
def mark_table_bussed():
    """Marks a table as bussed/cleaned — resets status to available."""
    data = request.json
    admin_pin = data.get('adminPin')
    table_number = data.get('table_number')

    if not check_perm(admin_pin, "manage_items"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    if not table_number:
        return jsonify({'message': 'Table number is required.'}), 400

    tables = load_json_data(TABLES_FILE)
    key = str(table_number)
    if key not in tables:
        return jsonify({'message': 'Table not found.'}), 404

    tables[key]['last_bussed_at'] = datetime.now().isoformat()
    tables[key]['status'] = 'available'
    save_json_data(TABLES_FILE, tables)

    admin_user = load_json_data(USERS_FILE).get(admin_pin, {})
    log_activity('mark_table_bussed', admin_pin, admin_user.get('role', 'admin'), {
        'table_number': table_number,
        'status': 'available',
        'last_bussed_at': tables[key]['last_bussed_at']
    })
    return jsonify({'message': f'Table {table_number} marked as bussed.', 'last_bussed_at': tables[key]['last_bussed_at']})


@app.route('/api/tables/tab/<int:table_number>/detail', methods=['GET'])
def get_table_detail(table_number):
    """Returns full table detail with all orders (not just active)."""
    orders = load_json_data(ORDERS_FILE)
    table_orders = [o for o in orders if o.get('table_number') == table_number]
    table_orders.sort(key=lambda o: o.get('date', ''))

    tables = load_json_data(TABLES_FILE)
    table_info = tables.get(str(table_number), {})

    # Derive status for the detail view
    def derive_detail_status():
        table_orders_all = [o for o in orders if o.get('table_number') == table_number]
        if not table_orders_all:
            return 'empty'
        active_orders = [o for o in table_orders_all if o.get('status') in ('pending', 'preparing')]
        completed_orders = [o for o in table_orders_all if o.get('status') == 'completed']
        if any(o.get('status') == 'preparing' for o in active_orders):
            return 'order_in_progress'
        if any(o.get('status') == 'pending' for o in active_orders):
            return 'occupied'
        if completed_orders and not active_orders:
            return 'needs_bussing'
        return 'empty'

    # Aggregate order stats
    active_orders = [o for o in table_orders if o.get('status') in ('pending', 'preparing')]
    completed_raw = [o for o in table_orders if o.get('status') == 'completed']
    total_spent = sum(float(o.get('total', 0)) for o in completed_raw)
    active_total = sum(float(o.get('total', 0)) for o in active_orders)
    active_items_count = sum(len(o.get('items', [])) for o in active_orders)

    return jsonify({
        'table': {
            'number': table_info.get('number'),
            'name': table_info.get('name', f'Table {table_number}'),
            'tablet_id': table_info.get('tablet_id', ''),
            'created_at': table_info.get('created_at', ''),
            'last_bussed_at': table_info.get('last_bussed_at'),
            'status': derive_detail_status()
        },
        'orders': table_orders,
        'order_count': len(table_orders),
        'active_order_count': len(active_orders),
        'completed_order_count': len(completed_raw),
        'total_spent': round(total_spent, 2),
        'active_total': round(active_total, 2),
        'active_items_count': active_items_count
    })


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

    # Verify the user has POS access permission
    if not check_perm(user_id, "pos_access"):
        log_activity('tab_checkout_unauthorized', user_id, 'unknown',
                     {'status': 'denied', 'reason': 'Missing pos_access permission',
                      'table_number': table_number})
        return jsonify({'error': 'Unauthorized. Valid employee PIN required.'}), 403

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


@app.route('/api/tables/transfer_orders', methods=['POST'])
def transfer_table_orders():
    """Transfer all active orders for a table from one waiter to another."""
    data = request.json
    admin_pin = data.get('adminPin', '')
    table_number = data.get('table_number')
    target_user_id = str(data.get('target_user_id', ''))

    if not admin_pin or not check_perm(admin_pin, 'manage_items'):
        return jsonify({'error': 'Insufficient permissions.'}), 403

    if table_number is None or not target_user_id:
        return jsonify({'error': 'table_number and target_user_id are required.'}), 400

    users = load_json_data(USERS_FILE)
    if target_user_id not in users:
        return jsonify({'error': 'Target user not found.'}), 404

    orders = load_json_data(ORDERS_FILE)
    active_orders = []
    remaining = []
    now = datetime.now().isoformat()

    for order in orders:
        if order.get('table_number') == int(table_number) and order.get('status') in ('pending', 'preparing'):
            original_user = order.get('user', 'unknown')
            # Store transfer audit trail on the order
            transfers = order.get('transfers', [])
            transfers.append({
                'transferred_from': original_user,
                'transferred_from_name': users.get(original_user, {}).get('name', 'Unknown'),
                'transferred_to': target_user_id,
                'transferred_to_name': users.get(target_user_id, {}).get('name', 'Unknown'),
                'transferred_at': now,
                'transferred_by': admin_pin,
                'transferred_by_name': users.get(admin_pin, {}).get('name', 'Unknown')
            })
            order['transfers'] = transfers
            order['user'] = target_user_id
            active_orders.append(order)
        remaining.append(order)

    if not active_orders:
        return jsonify({'error': f'No active orders for table #{table_number}.'}), 404

    save_json_data(ORDERS_FILE, remaining)

    target_name = users.get(target_user_id, {}).get('name', 'Unknown')
    log_activity('table_orders_transferred', admin_pin, 'admin', {
        'table_number': table_number,
        'from_user': active_orders[0].get('transfers', [])[-1].get('transferred_from', ''),
        'from_name': active_orders[0].get('transfers', [])[-1].get('transferred_from_name', ''),
        'to_user': target_user_id,
        'to_name': target_name,
        'order_count': len(active_orders),
        'order_ids': [o.get('order_id') for o in active_orders]
    })

    return jsonify({
        'message': f'✅ Transferred {len(active_orders)} active order(s) from Table #{table_number} to {_html.escape(target_name)}.',
        'table_number': table_number,
        'order_count': len(active_orders),
        'target_user_id': target_user_id,
        'target_name': target_name,
        'order_ids': [o.get('order_id') for o in active_orders]
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
    """Returns all inventory data merged with item names from menu.
    Requires manage_items permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_items")
    if err_response:
        return err_response
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
    """Returns items that are low on stock or out of stock.
    Requires manage_items permission (adminPin as query param)."""
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_items")
    if err_response:
        return err_response
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
            # Subtract partially refunded items from the total
            refunded_items = order.get('refunded_items', [])
            if refunded_items:
                refunded_sum = sum(
                    float(ri.get('total', ri.get('price', 0) * ri.get('qty', 1)))
                    for ri in refunded_items
                )
                total = max(0, total - refunded_sum)
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

    # Apply optional date range filtering on login_time
    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    if date_from or date_to:
        filtered = []
        for entry in timesheet:
            login_time_str = entry.get('login_time', '')
            if not login_time_str:
                continue
            try:
                login_dt = datetime.fromisoformat(login_time_str)
            except (ValueError, TypeError):
                continue
            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from)
                    if login_dt < dt_from:
                        continue
                except ValueError:
                    pass
            if date_to:
                try:
                    if 'T' not in date_to:
                        dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                    else:
                        dt_to = datetime.fromisoformat(date_to)
                    if login_dt > dt_to:
                        continue
                except ValueError:
                    pass
            filtered.append(entry)
        timesheet = filtered

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


@app.route('/api/export/timesheet_pdf', methods=['POST'])
def export_timesheet_pdf():
    """Generate a printable HTML timesheet report (browser Print → PDF) from employee shift data.
    Shows employee name, shift dates/times, daily totals, period total, overtime, estimated pay,
    and signature line. Page breaks per employee."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)
    users = load_json_data(USERS_FILE)
    ts_config = get_timesheet_config()
    OT_DAILY = ts_config.get('overtime_daily_threshold', 8)
    OT_WEEKLY = ts_config.get('overtime_weekly_threshold', 40)

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    def shift_in_range(entry):
        clock_in_str = entry.get('clock_in_time', '')
        if not clock_in_str:
            return False
        try:
            clock_in_dt = datetime.fromisoformat(clock_in_str)
        except (ValueError, TypeError):
            return False
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                if clock_in_dt < dt_from:
                    return False
            except ValueError:
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                if clock_in_dt > dt_to:
                    return False
            except ValueError:
                pass
        return True

    filtered_shifts = [entry for entry in shift_log if shift_in_range(entry)]

    if not filtered_shifts:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        period_label = f"{date_from or 'Earliest'} to {date_to or 'Latest'}"
        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Timesheet Report</title>
<style>
  @page {{ margin: 20mm 15mm; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; color: #222; line-height: 1.4; }}
  .empty {{ text-align: center; padding: 60px 20px; color: #999; }}
</style></head>
<body>
<div class="empty">
  <h2>📄 Timesheet Report</h2>
  <p>No shifts found for the selected period.</p>
  <p><strong>Period:</strong> {period_label}</p>
  <p><strong>Generated:</strong> {now_str}</p>
</div>
</body>
</html>"""
        return jsonify({'html': html, 'filename': f'timesheet_report_{date_from or "all"}_{date_to or "all"}.html'})

    # Group shifts by user
    user_data_map = {}
    for entry in filtered_shifts:
        uid = entry.get('user_id', 'unknown')
        if uid not in users:
            continue
        if uid not in user_data_map:
            user_data_map[uid] = {
                'user_name': entry.get('user_name', users[uid].get('name', 'Unknown')),
                'total_hours': 0.0,
                'total_break_hours': 0.0,
                'total_paid_hours': 0.0,
                'shift_count': 0,
                'shifts': []
            }
        ud = user_data_map[uid]
        dur = entry.get('duration_hours', 0)
        break_hrs = entry.get('break_hours', 0)
        paid_hrs = entry.get('paid_hours', dur)
        ud['total_hours'] += dur
        ud['total_break_hours'] += break_hrs
        ud['total_paid_hours'] += paid_hrs
        ud['shift_count'] += 1
        ud['shifts'].append(entry)

    # Weekly OT by user
    weekly_hours_by_user = defaultdict(lambda: defaultdict(float))
    for entry in filtered_shifts:
        uid = entry.get('user_id', '')
        ck = entry.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
            week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            weekly_hours_by_user[uid][week_key] += entry.get('duration_hours', 0)
        except (ValueError, TypeError):
            pass

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    period_label = f"{date_from or 'Earliest'} to {date_to or 'Latest'}"

    # Build HTML
    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Timesheet Report</title>
<style>
  @page { margin: 20mm 15mm; }
  @media print {
    .employee-section { page-break-before: always; }
    .employee-section:first-of-type { page-break-before: avoid; }
    .page-break { page-break-before: always; }
  }
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; color: #222; line-height: 1.4; margin: 0; padding: 0; }
  .report-header { text-align: center; margin-bottom: 20px; border-bottom: 3px solid #1a1a2e; padding-bottom: 10px; }
  .report-header h1 { font-size: 20pt; margin: 0 0 4px 0; color: #1a1a2e; letter-spacing: 0.5px; }
  .report-header .meta { font-size: 9pt; color: #666; margin: 2px 0; }
  .summary-table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
  .summary-table th { background: #1a1a2e; color: #fff; padding: 8px 10px; text-align: left; font-size: 9pt; }
  .summary-table td { padding: 6px 10px; border-bottom: 1px solid #ddd; font-size: 9pt; }
  .summary-table tr:nth-child(even) { background: #f8f8fc; }
  .total-row { font-weight: bold; background: #eef0f7 !important; }
  .ot { color: #e94560; font-weight: 600; }
  .section-title { font-size: 14pt; font-weight: 700; margin: 0 0 8px 0; color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 4px; }
  .employee-section { margin-bottom: 30px; padding-top: 10px; }
  .employee-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
  .employee-header h3 { margin: 0; font-size: 13pt; color: #16213e; }
  .employee-header .emp-totals { font-size: 10pt; color: #555; }
  .shift-table { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
  .shift-table th { background: #16213e; color: #fff; padding: 6px 8px; text-align: left; font-size: 8.5pt; }
  .shift-table td { padding: 5px 8px; border-bottom: 1px solid #ddd; font-size: 8.5pt; }
  .shift-table tr:nth-child(even) { background: #f8f8fc; }
  .daily-total-row { font-weight: 600; background: #e8ecf4 !important; }
  .daily-total-row td { border-top: 2px solid #16213e; }
  .emp-total-row { font-weight: bold; background: #dde0ed !important; }
  .sig-line { margin-top: 40px; padding-top: 10px; border-top: 1px solid #999; }
  .sig-line .sig-label { display: inline-block; width: 180px; margin-right: 40px; }
  .sig-line .sig-x { display: inline-block; width: 250px; border-bottom: 1px solid #222; height: 1.2em; margin-right: 40px; }
  .footer { margin-top: 30px; font-size: 7.5pt; color: #999; text-align: center; border-top: 1px solid #ddd; padding-top: 8px; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 8pt; font-weight: 600; }
  .badge-ot { background: #ffe0e0; color: #e94560; }
  .badge-late { background: #fff3cd; color: #856404; }
</style></head>
<body>

<div class="report-header">
  <h1>📊 Timesheet Report</h1>
  <div class="meta"><strong>Period:</strong> """ + period_label + """</div>
  <div class="meta"><strong>Generated:</strong> """ + now_str + """</div>
  <div class="meta"><strong>Total Employees:</strong> """ + str(len(user_data_map)) + """ | <strong>Total Shifts:</strong> """ + str(len(filtered_shifts)) + """</div>
</div>"""

    # Summary table
    html += '<h2 class="section-title" style="font-size:13pt;">Employee Summary</h2>'
    html += """<table class="summary-table">
<thead><tr>
  <th>Employee</th>
  <th>Total Hours</th>
  <th>Break (hrs)</th>
  <th>Paid Hours</th>
  <th>Overtime</th>
  <th>Pay Rate</th>
  <th>Est. Gross Pay</th>
  <th>Shifts</th>
</tr></thead>
<tbody>"""
    grand_total_hours = 0
    grand_total_paid = 0
    grand_total_pay = 0
    grand_total_ot = 0

    for uid, ud in sorted(user_data_map.items(), key=lambda x: x[1]['user_name']):
        total_hours = round(ud['total_hours'], 2)
        total_paid = round(ud['total_paid_hours'], 2)
        total_break = round(ud['total_break_hours'], 2)
        week_ots = []
        for wk, wh in weekly_hours_by_user.get(uid, {}).items():
            if wh > OT_WEEKLY:
                week_ots.append(round(wh - OT_WEEKLY, 2))
        ot_hours = round(sum(week_ots), 2)
        pay_rate = users.get(uid, {}).get('pay_rate', 0) or 0
        estimated_pay = round(total_paid * pay_rate, 2) if pay_rate > 0 else 0
        grand_total_hours += total_hours
        grand_total_paid += total_paid
        grand_total_pay += estimated_pay
        grand_total_ot += ot_hours
        ot_str = f'<span class="ot">{ot_hours:.2f}</span>' if ot_hours > 0 else '0.00'
        rate_str = f'${pay_rate:.2f}/hr' if pay_rate > 0 else '—'
        pay_str = f'${estimated_pay:.2f}' if pay_rate > 0 else '—'
        html += f"<tr><td><strong>{_html.escape(ud['user_name'])}</strong> ({uid})</td><td>{total_hours:.2f}</td><td>{total_break:.2f}</td><td>{total_paid:.2f}</td><td>{ot_str}</td><td>{rate_str}</td><td>{pay_str}</td><td>{ud['shift_count']}</td></tr>"

    html += f"""</tbody>
<tfoot>
<tr class="total-row">
  <td><strong>TOTAL</strong> ({len(user_data_map)} employees)</td>
  <td>{grand_total_hours:.2f}</td>
  <td>{round(grand_total_paid-grand_total_hours, 2):.2f}</td>
  <td>{grand_total_paid:.2f}</td>
  <td>{grand_total_ot:.2f}</td>
  <td>—</td>
  <td>${grand_total_pay:.2f}</td>
  <td>{len(filtered_shifts)}</td>
</tr>
</tfoot>
</table>"""

    # Detailed shift logs per employee with daily grouping
    html += '<h2 class="section-title" style="font-size:13pt;margin-top:30px;">Shift Details by Employee</h2>'
    for uid, ud in sorted(user_data_map.items(), key=lambda x: x[1]['user_name']):
        total_hours = round(ud['total_hours'], 2)
        total_paid = round(ud['total_paid_hours'], 2)
        total_break = round(ud['total_break_hours'], 2)
        pay_rate = users.get(uid, {}).get('pay_rate', 0) or 0
        estimated_pay = round(total_paid * pay_rate, 2) if pay_rate > 0 else 0

        html += f"""<div class="employee-section">
<div class="employee-header">
  <h3>👤 {_html.escape(ud['user_name'])} ({uid})</h3>
  <div class="emp-totals">{ud['shift_count']} shift(s) | {total_hours:.2f} hrs total | {total_break:.2f} hrs break | {total_paid:.2f} hrs paid | Est. ${estimated_pay:.2f}</div>
</div>
<table class="shift-table">
<thead><tr>
  <th>Date</th>
  <th>Clock In</th>
  <th>Clock Out</th>
  <th>Duration</th>
  <th>Break</th>
  <th>Paid</th>
  <th>Daily OT</th>
  <th>Notes</th>
</tr></thead>
<tbody>"""

        # Group shifts by date
        shift_rows = sorted(ud['shifts'], key=lambda x: x.get('clock_in_time', ''))
        daily_groups = defaultdict(list)
        for s in shift_rows:
            ck = s.get('clock_in_time', '')
            day_key = ck[:10] if ck else 'unknown'
            daily_groups[day_key].append(s)

        for day_key in sorted(daily_groups.keys()):
            day_shifts = daily_groups[day_key]
            day_total = 0
            day_break = 0
            day_paid = 0
            for s in day_shifts:
                dur = s.get('duration_hours', 0)
                brk = s.get('break_hours', 0)
                paid = s.get('paid_hours', dur)
                day_total += dur
                day_break += brk
                day_paid += paid
            day_ot = max(0, round(day_total - OT_DAILY, 2))
            # Show individual shifts in day
            for s_idx, s in enumerate(day_shifts):
                ci = s.get('clock_in_time', '—')
                co = s.get('clock_out_time', '—')
                dur = s.get('duration_hours', 0)
                brk = s.get('break_hours', 0)
                paid = s.get('paid_hours', dur)
                notes = _html.escape(s.get('notes', ''))
                late_mins = s.get('late_minutes')
                late_badge = f' <span class="badge badge-late">🕐 {late_mins}min late</span>' if late_mins else ''
                # Show date on first row of day only
                date_display = _html.escape(day_key) if s_idx == 0 else ''
                ot_cell = '—' if day_ot == 0 else '<span class="badge badge-ot">⬆ {:.2f}h OT</span>'.format(day_ot)
                html += '<tr><td>{}</td><td>{}</td><td>{}</td><td>{:.2f}h</td><td>{:.2f}h</td><td>{:.2f}h</td><td>{}</td><td>{}{}</td></tr>'.format(
                    date_display, _html.escape(ci), _html.escape(co), dur, brk, paid, ot_cell, notes, late_badge)
            # Daily total row
            ot_cell2 = '—' if day_ot == 0 else '<span class="badge badge-ot">⬆ {:.2f}h OT</span>'.format(day_ot)
            html += '<tr class="daily-total-row"><td colspan="2"><strong>📅 {} Total</strong></td><td></td><td><strong>{:.2f}h</strong></td><td><strong>{:.2f}h</strong></td><td><strong>{:.2f}h</strong></td><td>{}</td><td></td></tr>'.format(
                _html.escape(day_key), day_total, day_break, day_paid, ot_cell2)

        # Employee total row
        ot_total = 0
        for wk, wh in weekly_hours_by_user.get(uid, {}).items():
            if wh > OT_WEEKLY:
                ot_total += round(wh - OT_WEEKLY, 2)
        emp_ot_cell = '—' if ot_total == 0 else '<span class="badge badge-ot">⬆ {:.2f}h OT</span>'.format(ot_total)
        html += '<tr class="emp-total-row"><td colspan="2"><strong>🏁 {} Total</strong></td><td></td><td><strong>{:.2f}h</strong></td><td><strong>{:.2f}h</strong></td><td><strong>{:.2f}h</strong></td><td>{}</td><td></td></tr>'.format(
            _html.escape(ud["user_name"]), total_hours, total_break, total_paid, emp_ot_cell)

        html += '</tbody></table></div>'

    # Signature line
    html += f"""<div class="sig-line">
  <div><span class="sig-label">Employee Signature:</span><span class="sig-x"></span><span class="sig-label">Date:</span><span class="sig-x"></span></div>
  <div style="margin-top:12px;"><span class="sig-label">Manager Signature:</span><span class="sig-x"></span><span class="sig-label">Date:</span><span class="sig-x"></span></div>
  <div style="margin-top:8px;font-size:9pt;color:#888;">By signing, I confirm the hours listed above accurately reflect the time I worked during this period.</div>
</div>"""

    html += f"""<div class="footer">Timesheet Report — Generated by POS System on {now_str} | This is not an official tax document</div>
</body>
</html>"""

    return jsonify({'html': html, 'filename': f'timesheet_report_{date_from or "all"}_{date_to or "all"}.html'})


@app.route('/api/timesheet/config', methods=['GET', 'POST'])
def timesheet_config_endpoint():
    """Get or save timesheet configuration (overtime thresholds, grace period, etc.)."""
    if request.method == 'GET':
        config = get_timesheet_config()
        return jsonify(config)
    
    # POST: save config
    data = request.json
    admin_pin = data.get('adminPin')
    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403
    
    new_config = data.get('config', {})
    if not isinstance(new_config, dict):
        return jsonify({'message': 'Invalid config format.'}), 400
    
    save_timesheet_config(new_config)
    
    log_activity('timesheet_config_updated', admin_pin, 'admin', {
        'config': new_config
    })
    
    return jsonify({'message': 'Timesheet config saved.', 'config': get_timesheet_config()})


@app.route('/api/timesheet/pay_period', methods=['POST'])
def timesheet_pay_period():
    """Get pay period summary with per-employee totals: hours, overtime, estimated pay."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)
    users = load_json_data(USERS_FILE)
    ts_config = get_timesheet_config()
    OT_DAILY = ts_config.get('overtime_daily_threshold', 8)
    OT_WEEKLY = ts_config.get('overtime_weekly_threshold', 40)

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    user_id_filter = (data.get('user_id') or '').strip()

    def shift_in_range(entry, clock_in_key='clock_in_time'):
        """Check if a shift's clock_in_time falls within the date range."""
        clock_in_str = entry.get(clock_in_key, '')
        if not clock_in_str:
            return False
        try:
            clock_in_dt = datetime.fromisoformat(clock_in_str)
        except (ValueError, TypeError):
            return False
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                if clock_in_dt < dt_from:
                    return False
            except ValueError:
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                if clock_in_dt > dt_to:
                    return False
            except ValueError:
                pass
        return True

    # Filter completed shifts
    filtered_shifts = []
    for entry in shift_log:
        uid = entry.get('user_id', '')
        if user_id_filter and uid != user_id_filter:
            continue
        if shift_in_range(entry):
            filtered_shifts.append(entry)

    # Also include currently active shifts in range
    for uid, shift in list(active_shifts.items()):
        if user_id_filter and uid != user_id_filter:
            continue
        if uid not in users:
            continue
        now = datetime.now()
        shift_entry = {
            'user_id': uid,
            'user_name': shift.get('user_name', users.get(uid, {}).get('name', 'Unknown')),
            'clock_in_time': shift['clock_in_time'].isoformat(),
            'clock_out_time': None,
            'duration_hours': round((now - shift['clock_in_time']).total_seconds() / 3600, 2),
            'active': True
        }
        if shift_in_range(shift_entry):
            filtered_shifts.append(shift_entry)

    # Group by user_id
    user_data_map = {}
    for entry in filtered_shifts:
        uid = entry.get('user_id', 'unknown')
        if uid not in users:
            continue
        if uid not in user_data_map:
            user_data_map[uid] = {
                'user_name': entry.get('user_name', users[uid].get('name', 'Unknown')),
                'total_hours': 0.0,
                'shift_count': 0,
                'shifts': []
            }
        ud = user_data_map[uid]
        # Use paid_hours if available, else fall back to duration_hours
        shift_hours = entry.get('paid_hours', entry.get('duration_hours', 0))
        ud['total_hours'] += shift_hours
        ud['shift_count'] += 1
        ud['shifts'].append({
            'clock_in_time': entry.get('clock_in_time', ''),
            'clock_out_time': entry.get('clock_out_time', ''),
            'duration_hours': entry.get('duration_hours', 0),
            'break_hours': entry.get('break_hours', 0),
            'paid_hours': shift_hours,
            'active': entry.get('active', False),
            'late_minutes': entry.get('late_minutes'),
            'late_excused': entry.get('late_excused', False),
            'late_note': entry.get('late_note'),
            'pay_rate': entry.get('pay_rate')  # Per-shift pay rate override
        })

    # Calculate weekly overtime: group completed shifts by ISO week
    weekly_hours_by_user = defaultdict(lambda: defaultdict(float))
    for entry in filtered_shifts:
        uid = entry.get('user_id', '')
        if uid not in users:
            continue
        ck = entry.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
            week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            weekly_hours_by_user[uid][week_key] += entry.get('duration_hours', 0)
        except (ValueError, TypeError):
            pass

    # Also compute daily totals per user (for daily OT flag on shifts)
    daily_hours_by_user = defaultdict(lambda: defaultdict(float))
    for entry in filtered_shifts:
        uid = entry.get('user_id', '')
        ck = entry.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
            day_key = dt.strftime('%Y-%m-%d')
            daily_hours_by_user[uid][day_key] += entry.get('duration_hours', 0)
        except (ValueError, TypeError):
            pass

    results = []
    for uid, ud in user_data_map.items():
        total_hours = round(ud['total_hours'], 2)
        # Overtime: sum of (week_hours - threshold) for each week where week_hours > threshold
        week_ots = []
        for wk, wh in weekly_hours_by_user.get(uid, {}).items():
            if wh > OT_WEEKLY:
                week_ots.append(round(wh - OT_WEEKLY, 2))
        overtime_hours = round(sum(week_ots), 2)

        # Pay rate from user profile (default)
        default_pay_rate = users.get(uid, {}).get('pay_rate', None)
        has_any_rate = default_pay_rate is not None and default_pay_rate > 0

        # Calculate estimated pay using per-shift pay_rate overrides
        # If a shift has its own pay_rate, use that; otherwise use the user's default rate
        estimated_pay = None
        per_shift_earnings = 0.0
        for s in shifts_sorted:
            shift_hours = s.get('paid_hours', s.get('duration_hours', 0))
            shift_rate = s.get('pay_rate') or default_pay_rate or 0
            if shift_rate > 0:
                has_any_rate = True
            per_shift_earnings += shift_hours * shift_rate
        if has_any_rate:
            estimated_pay = round(per_shift_earnings, 2)

        # Effective rate (weighted average for display)
        effective_rate = round(per_shift_earnings / total_hours, 2) if has_any_rate and total_hours > 0 else (default_pay_rate or 0)

        # Sort shifts by clock_in_time
        shifts_sorted = sorted(ud['shifts'], key=lambda s: s.get('clock_in_time', ''))

        # Add per-shift OT flags
        shifts_with_ot = []
        for s in shifts_sorted:
            ck = s.get('clock_in_time', '')
            day_key = ''
            try:
                dt = datetime.fromisoformat(ck)
                day_key = dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
            day_total = daily_hours_by_user.get(uid, {}).get(day_key, 0)
            shifts_with_ot.append({
                'clock_in_time': s.get('clock_in_time', ''),
                'clock_out_time': s.get('clock_out_time', ''),
                'duration_hours': s.get('duration_hours', 0),
                'break_hours': s.get('break_hours', 0),
                'paid_hours': s.get('paid_hours', s.get('duration_hours', 0)),
                'active': s.get('active', False),
                'exceeds_daily_ot': s.get('duration_hours', 0) > OT_DAILY,
                'exceeds_weekly_ot': overtime_hours > 0,
                'day_total_hours': round(day_total, 2),
                'edited': s.get('edited', False),
                'notes': s.get('notes', ''),
                'late_note': s.get('late_note', ''),
                'pay_rate': s.get('pay_rate')  # Per-shift pay rate override
            })

        results.append({
            'user_id': uid,
            'user_name': ud['user_name'],
            'total_hours': total_hours,
            'shift_count': ud['shift_count'],
            'overtime_hours': overtime_hours,
            'pay_rate': default_pay_rate,
            'effective_pay_rate': effective_rate,
            'has_pay_rate': has_any_rate,
            'estimated_pay': estimated_pay,
            'shifts': shifts_with_ot
        })

    # Sort by total_hours descending
    results.sort(key=lambda r: r['total_hours'], reverse=True)

    return jsonify({
        'message': 'Pay period summary retrieved',
        'employees': results,
        'total_employees': len(results)
    })


# ═══════════ TIMESHEET APPROVAL WORKFLOW ═══════════

def load_approvals():
    """Load timesheet_approvals.json (list of approval records)."""
    return load_json_data(APPROVALS_FILE)


def save_approvals(data):
    """Save timesheet_approvals.json."""
    save_json_data(APPROVALS_FILE, data)


def shift_in_period(shift_clock_in_str, date_from, date_to):
    """Check if a shift's clock_in falls within a date range (inclusive)."""
    if not shift_clock_in_str:
        return False
    try:
        dt = datetime.fromisoformat(shift_clock_in_str)
    except (ValueError, TypeError):
        return False
    if date_from:
        try:
            df = datetime.fromisoformat(date_from)
            if dt < df:
                return False
        except ValueError:
            pass
    if date_to:
        try:
            if 'T' not in date_to:
                dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
            else:
                dt_to = datetime.fromisoformat(date_to)
            if dt > dt_to:
                return False
        except ValueError:
            pass
    return True


def is_period_locked(date_from, date_to):
    """Check if any shifts in the given date range belong to a locked approval period.
    Returns None if not locked, or the approval record dict if locked."""
    approvals = load_approvals()
    for app in approvals:
        if app.get('status') in ('pending', 'approved'):
            # Check if ranges overlap
            a_from = app.get('date_from', '')
            a_to = app.get('date_to', '')
            if not a_from or not a_to:
                continue
            # Overlap: app range and queried range intersect
            try:
                qf = datetime.fromisoformat(date_from) if date_from else datetime.min
                qt = datetime.fromisoformat(date_to + 'T23:59:59') if date_to else datetime.max
                af = datetime.fromisoformat(a_from)
                at = datetime.fromisoformat(a_to + 'T23:59:59')
                # Check overlap: qf <= at and qt >= af
                if qf <= at and qt >= af:
                    return app
            except (ValueError, TypeError):
                continue
    return None


def get_period_lock_status(date_from, date_to):
    """Get the lock status for a specific date range. Returns status string or None."""
    approvals = load_approvals()
    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            return app
    return None


@app.route('/api/timesheet/approval/submit', methods=['POST'])
def timesheet_approval_submit():
    """Submit a pay period for approval. Locks shifts in the period from editing."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    # Validate dates
    try:
        datetime.fromisoformat(date_from)
        if 'T' not in date_to:
            datetime.fromisoformat(date_to + 'T23:59:59')
        else:
            datetime.fromisoformat(date_to)
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD or ISO.'}), 400

    approvals = load_approvals()
    users = load_json_data(USERS_FILE)
    admin_name = users.get(admin_pin, {}).get('name', 'Unknown')

    # Check if already submitted for this exact range
    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            if app.get('status') == 'approved':
                return jsonify({'message': 'This pay period is already approved.'}), 409
            if app.get('status') == 'pending':
                return jsonify({'message': 'This pay period is already submitted for approval. Unlock by owner to resubmit.'}), 409

    # Create approval record
    approval_record = {
        'date_from': date_from,
        'date_to': date_to,
        'status': 'pending',
        'submitted_by': admin_pin,
        'submitted_by_name': admin_name,
        'submitted_at': datetime.now().isoformat(),
        'approved_by': None,
        'approved_at': None,
        'unlocked_by': None,
        'unlocked_at': None,
        'unlock_reason': None,
        'employee_approvals': []  # list of { user_id, user_name, approved_at }
    }

    approvals.append(approval_record)
    save_approvals(approvals)

    log_activity('timesheet_approval_submitted', admin_pin, 'admin', {
        'date_from': date_from,
        'date_to': date_to,
        'status': 'pending'
    })

    return jsonify({
        'message': 'Pay period submitted for approval. Shifts in this period are now locked.',
        'approval': approval_record
    })


@app.route('/api/timesheet/approval/approve', methods=['POST'])
def timesheet_approval_approve():
    """Employee approves their own shifts in a submitted pay period."""
    data = request.json
    user_id = (data.get('userId') or '').strip()

    if not user_id:
        return jsonify({'message': 'User ID is required.'}), 400

    users = load_json_data(USERS_FILE)
    if user_id not in users:
        return jsonify({'message': 'User not found.'}), 404

    user_name = users[user_id].get('name', 'Unknown')
    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    approvals = load_approvals()

    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            if app.get('status') != 'pending':
                return jsonify({'message': 'This pay period is not pending approval.'}), 400

            # Check if this user already approved
            for ea in app.get('employee_approvals', []):
                if ea.get('user_id') == user_id:
                    return jsonify({'message': 'You have already approved your shifts for this period.'}), 409

            if 'employee_approvals' not in app:
                app['employee_approvals'] = []

            app['employee_approvals'].append({
                'user_id': user_id,
                'user_name': user_name,
                'approved_at': datetime.now().isoformat()
            })

            save_approvals(approvals)

            log_activity('timesheet_approval_employee_approved', user_id, user_name, {
                'date_from': date_from,
                'date_to': date_to
            })

            return jsonify({
                'message': 'Your shifts in this pay period have been approved.',
                'employee_approvals': app['employee_approvals']
            })

    return jsonify({'message': 'No pending approval found for this date range.'}), 404


@app.route('/api/timesheet/approval/finalize', methods=['POST'])
def timesheet_approval_finalize():
    """Admin/owner marks a pending approval as fully approved (finalized)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    users = load_json_data(USERS_FILE)
    admin_name = users.get(admin_pin, {}).get('name', 'Unknown')
    approvals = load_approvals()

    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            if app.get('status') != 'pending':
                return jsonify({'message': 'This pay period is not in pending status.'}), 400

            app['status'] = 'approved'
            app['approved_by'] = admin_pin
            app['approved_by_name'] = admin_name
            app['approved_at'] = datetime.now().isoformat()

            save_approvals(approvals)

            log_activity('timesheet_approval_finalized', admin_pin, 'admin', {
                'date_from': date_from,
                'date_to': date_to,
                'employee_approvals': len(app.get('employee_approvals', []))
            })

            return jsonify({
                'message': 'Pay period has been approved and finalized.',
                'approval': app
            })

    return jsonify({'message': 'No pending approval found for this date range.'}), 404


@app.route('/api/timesheet/pay_period/mark_paid', methods=['POST'])
def timesheet_mark_paid():
    """Auto-email pay stub PDFs to all employees when admin marks a pay period as paid."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    # Validate email config
    email_config = load_json_data(EMAIL_CONFIG_FILE)
    if not isinstance(email_config, dict):
        email_config = {"server": "", "port": 587, "username": "", "password": "", "from_addr": "", "use_tls": True, "enabled": False}
    if not email_config.get('enabled'):
        return jsonify({'message': 'Email sending is not configured. Go to Admin → Email Settings to set up SMTP.'}), 400
    if not target_approval:
        return jsonify({'message': 'No finalized approval found for this date range.'}), 400

    current_status = target_approval.get('status', 'unknown')
    if current_status != 'approved':
        return jsonify({'message': f'Pay period must be in "approved" status first (current: {current_status}). Finalize the approval before marking as paid.'}), 400

    users = load_json_data(USERS_FILE)
    shift_log = load_json_data(SHIFT_FILE)
    admin_user = users.get(admin_pin, {})
    admin_name = admin_user.get('name', 'Admin')
    pay_rate_global = admin_user.get('pay_rate') or 0

    # Get all employees who worked during this period
    def shift_in_range(entry):
        clock_in_str = entry.get('clock_in_time', '')
        if not clock_in_str:
            return False
        try:
            dt = datetime.fromisoformat(clock_in_str)
        except (ValueError, TypeError):
            return False
        if date_from:
            try:
                df = datetime.fromisoformat(date_from)
                if dt < df:
                    return False
            except ValueError:
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                if dt > dt_to:
                    return False
            except ValueError:
                pass
        return True

    # Group shifts by user
    employee_shifts = {}
    for entry in shift_log:
        uid = entry.get('user_id', '')
        if not uid or uid not in users:
            continue
        if not shift_in_range(entry):
            continue
        if uid not in employee_shifts:
            employee_shifts[uid] = []
        employee_shifts[uid].append(entry)

    if not employee_shifts:
        return jsonify({'message': 'No employees with shifts found in this pay period.'}), 400

    # Generate and email pay stub for each employee with an email
    sent = []
    skipped = []
    failed = []

    smtp_server = email_config.get('server', '')
    smtp_port = int(email_config.get('port', 587))
    use_tls = email_config.get('use_tls', True)
    smtp_username = email_config.get('username', '')
    smtp_password = email_config.get('password', '')

    for uid in employee_shifts:
        user_data = users.get(uid, {})
        user_email = user_data.get('email', '').strip()
        user_name = user_data.get('name', 'Unknown')
        user_pay_rate = user_data.get('pay_rate') or 0

        if not user_email or '@' not in user_email:
            skipped.append({'user_id': uid, 'user_name': user_name, 'reason': 'No email address set'})
            continue

        # Calculate pay period data for this employee (simplified from pay_stub_pdf)
        user_shifts = employee_shifts[uid]
        user_shifts.sort(key=lambda x: x.get('clock_in_time', ''))

        total_paid_hours = 0.0
        total_duration_hours = 0.0
        total_break_hours = 0.0
        for s in user_shifts:
            dur = s.get('duration_hours', 0)
            paid = s.get('paid_hours', dur)
            total_duration_hours += dur
            total_paid_hours += paid
            total_break_hours += s.get('break_hours', 0)
        total_paid_hours = round(total_paid_hours, 2)

        gross_pay = 0.0
        gross_has_rate = False
        for s in user_shifts:
            sp = s.get('paid_hours', s.get('duration_hours', 0))
            sr = s.get('pay_rate') or user_pay_rate
            if s.get('pay_rate'):
                gross_has_rate = True
            gross_pay += sp * sr
        gross_pay = round(gross_pay, 2) if (user_pay_rate > 0 or gross_has_rate) else 0
        eff_rate = round(gross_pay / total_paid_hours, 2) if (user_pay_rate > 0 or gross_has_rate) and total_paid_hours > 0 else user_pay_rate

        # Build shift rows
        shift_rows = ''
        for s in user_shifts:
            ci = s.get('clock_in_time', '—')
            co = s.get('clock_out_time', '—')
            dur = s.get('duration_hours', 0)
            paid = s.get('paid_hours', dur)
            bk = s.get('break_hours', 0)
            try:
                d = datetime.fromisoformat(ci)
                date_str = d.strftime('%a %b %d')
                in_str = d.strftime('%I:%M %p').lstrip('0')
            except (ValueError, TypeError):
                date_str = ci
                in_str = ci
            try:
                if co:
                    d_out = datetime.fromisoformat(co)
                    out_str = d_out.strftime('%I:%M %p').lstrip('0')
                else:
                    out_str = '—'
            except (ValueError, TypeError):
                out_str = co or '—'
            shift_rows += f'<tr><td>{date_str}</td><td>{in_str}</td><td>{out_str}</td><td style="text-align:right;">{dur:.2f}</td><td style="text-align:right;">{paid:.2f}</td><td style="text-align:right;">{bk:.2f}</td></tr>'

        if not shift_rows:
            shift_rows = '<tr><td colspan="6" style="text-align:center;color:#999;">No shifts in this period.</td></tr>'

        period_label = f"{date_from} to {date_to}"
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        gross_pay_str = f'${gross_pay:,.2f}' if (user_pay_rate > 0 or gross_has_rate) else '$0.00'
        rate_display = f'${eff_rate:.2f}/hr' if (user_pay_rate > 0 or gross_has_rate) else 'Not set'
        rate_row = ''
        if user_pay_rate > 0 or gross_has_rate:
            rate_row = f'<tr><td>Effective Rate</td><td style="text-align:right;">{rate_display}</td></tr>'
        safe_name = user_name
        safe_id = uid

        pay_stub_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pay Stub — {safe_name}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; color: #222; line-height: 1.5; margin: 0; padding: 20px; }}
  h1 {{ font-size: 20pt; margin: 0 0 4px; color: #1a1a2e; text-align: center; }}
  .period {{ text-align: center; color: #888; font-size: 10pt; margin-bottom: 16px; }}
  .info-box {{ display: flex; justify-content: space-between; margin-bottom: 16px; padding: 12px 14px; background: #f5f5fa; border-radius: 6px; }}
  .info-box .lbl {{ color: #888; font-size: 8pt; text-transform: uppercase; }}
  .info-box .val {{ font-weight: 600; font-size: 11pt; color: #1a1a2e; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
  th {{ background: #1a1a2e; color: #fff; padding: 7px 8px; text-align: left; font-size: 8pt; text-transform: uppercase; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; font-size: 9pt; }}
  tr:nth-child(even) {{ background: #f8f8fc; }}
  .grand {{ font-weight: 700; font-size: 10pt; border-top: 2px solid #1a1a2e; color: #1a1a2e; }}
  .footer {{ margin-top: 30px; font-size: 8pt; color: #aaa; text-align: center; }}
</style>
</head>
<body>
<h1>Pay Stub</h1>
<div class="period">Pay Period: {period_label}</div>
<div class="info-box">
  <div><div class="lbl">Employee</div><div class="val">{safe_name}</div></div>
  <div><div class="lbl">ID</div><div class="val">{safe_id}</div></div>
  <div><div class="lbl">Rate</div><div class="val">{rate_display}</div></div>
  <div><div class="lbl">Generated</div><div class="val">{now_str}</div></div>
</div>
<h3 style="font-size:11pt;color:#1a1a2e;margin:16px 0 8px;">Shift Details</h3>
<table>
<thead><tr><th>Date</th><th>In</th><th>Out</th><th style="text-align:right;">Dur (h)</th><th style="text-align:right;">Paid (h)</th><th style="text-align:right;">Break (h)</th></tr></thead>
<tbody>{shift_rows}</tbody>
</table>
<div style="margin-top:12px;">
<table>
  <tr><td>Total Break Hours</td><td style="text-align:right;">{total_break_hours:.2f}</td></tr>
  <tr><td>Total Paid Hours</td><td style="text-align:right;">{total_paid_hours:.2f}</td></tr>
  {rate_row}
  <tr class="grand"><td>Gross Pay</td><td style="text-align:right;">{gross_pay_str}</td></tr>
</table>
</div>
<div class="footer">POS System — Pay stub for informational purposes only.</div>
</body>
</html>'''

        # Send email
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Your Pay Stub — {period_label}'
            msg['From'] = email_config.get('from_addr', '')
            msg['To'] = user_email
            msg.attach(MIMEText(f'Your pay stub for period {period_label} is attached.\n\nGross Pay: {gross_pay_str}\nTotal Paid Hours: {total_paid_hours:.2f}\n\nThank you!', 'plain'))
            msg.attach(MIMEText(pay_stub_html, 'html'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)
            server.quit()

            sent.append({'user_id': uid, 'user_name': user_name, 'email': user_email})
        except smtplib.SMTPAuthenticationError:
            failed.append({'user_id': uid, 'user_name': user_name, 'email': user_email, 'error': 'SMTP authentication failed'})
        except smtplib.SMTPException as e:
            failed.append({'user_id': uid, 'user_name': user_name, 'email': user_email, 'error': str(e)})
        except Exception as e:
            failed.append({'user_id': uid, 'user_name': user_name, 'email': user_email, 'error': str(e)})

    # Update approval record to paid status
    target_approval['status'] = 'paid'
    target_approval['paid_at'] = datetime.now().isoformat()
    target_approval['paid_by'] = admin_pin
    target_approval['paid_by_name'] = admin_name
    target_approval['pay_stub_email_summary'] = {
        'sent': len(sent),
        'skipped': len(skipped),
        'failed': len(failed),
        'sent_details': sent,
        'skipped_details': skipped,
        'failed_details': failed
    }
    save_approvals(approvals)

    log_activity('pay_period_marked_paid', admin_pin, 'admin', {
        'date_from': date_from,
        'date_to': date_to,
        'sent': len(sent),
        'skipped': len(skipped),
        'failed': len(failed),
        'sent_list': [s['user_name'] for s in sent],
        'skipped_list': [s['user_name'] for s in skipped],
        'failed_list': [s['user_name'] for s in failed]
    })

    return jsonify({
        'message': f'Pay period marked as paid. Emails sent: {len(sent)}, skipped: {len(skipped)}, failed: {len(failed)}.',
        'sent': sent,
        'skipped': skipped,
        'failed': failed,
        'total_employees': len(employee_shifts)
    })


@app.route('/api/timesheet/approval/unlock', methods=['POST'])
def timesheet_approval_unlock():
    """Owner unlocks a locked pay period so shifts can be edited again."""
    data = request.json
    admin_pin = data.get('adminPin')

    # Only owner can unlock
    users = load_json_data(USERS_FILE)
    user_data = users.get(admin_pin, {})
    if user_data.get('role') != 'owner':
        return jsonify({'message': 'Only the owner can unlock a locked pay period.'}), 403

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()
    reason = (data.get('reason') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    if not reason:
        return jsonify({'message': 'Reason for unlocking is required.'}), 400

    owner_name = user_data.get('name', 'Owner')
    approvals = load_approvals()

    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            if app.get('status') not in ('pending', 'approved'):
                return jsonify({'message': 'This pay period is not locked.'}), 400

            old_status = app.get('status')
            app['status'] = 'unlocked'
            app['unlocked_by'] = admin_pin
            app['unlocked_by_name'] = owner_name
            app['unlocked_at'] = datetime.now().isoformat()
            app['unlock_reason'] = reason

            save_approvals(approvals)

            log_activity('timesheet_approval_unlocked', admin_pin, 'owner', {
                'date_from': date_from,
                'date_to': date_to,
                'old_status': old_status,
                'reason': reason
            })

            return jsonify({
                'message': 'Pay period has been unlocked. Shifts can now be edited.',
                'approval': app
            })

    return jsonify({'message': 'No locked approval found for this date range.'}), 404


@app.route('/api/timesheet/approval/status', methods=['POST'])
def timesheet_approval_status():
    """Get the approval status for a specific date range."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    approvals = load_approvals()

    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            return jsonify({
                'message': 'Approval status retrieved.',
                'approval': app
            })

    return jsonify({
        'message': 'No approval record found for this date range.',
        'approval': None
    })


@app.route('/api/timesheet/approval/list', methods=['POST'])
def timesheet_approval_list():
    """List all approval records."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    approvals = load_approvals()
    # Sort by date_from descending (newest first)
    approvals_sorted = sorted(approvals, key=lambda a: a.get('date_from', ''), reverse=True)

    return jsonify({
        'message': 'Approval records retrieved.',
        'approvals': approvals_sorted,
        'total': len(approvals_sorted)
    })


# Now lock the clock/edit endpoint — check if a shift's period is locked
# We inject a lock check into the clock_edit function.
# We also check in the excuse_late, flag_late endpoints.


@app.route('/api/timesheet/approval/check_lock', methods=['POST'])
def timesheet_approval_check_lock():
    """Check if a shift at a given index is in a locked period.
    Returns { locked: true/false, approval: {...} or null }
    """
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_index = data.get('shift_index')
    if shift_index is None or not isinstance(shift_index, int):
        return jsonify({'message': 'shift_index (integer) is required.'}), 400

    shift_log = load_json_data(SHIFT_FILE)
    if shift_index < 0 or shift_index >= len(shift_log):
        return jsonify({'message': 'Invalid shift_index.'}), 404

    shift = shift_log[shift_index]
    clock_in_str = shift.get('clock_in_time', '')

    approvals = load_approvals()
    for app in approvals:
        if app.get('status') not in ('pending', 'approved'):
            continue
        a_from = app.get('date_from', '')
        a_to = app.get('date_to', '')
        if shift_in_period(clock_in_str, a_from, a_to):
            return jsonify({
                'locked': True,
                'approval': app
            })

    return jsonify({
        'locked': False,
        'approval': None
    })


@app.route('/api/timesheet/approval/employee_approvals', methods=['POST'])
def timesheet_approval_employee_approvals():
    """Get which employees have approved for a specific period."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    if not date_from or not date_to:
        return jsonify({'message': 'date_from and date_to are required.'}), 400

    approvals = load_approvals()
    for app in approvals:
        if app.get('date_from') == date_from and app.get('date_to') == date_to:
            return jsonify({
                'employee_approvals': app.get('employee_approvals', []),
                'total_approved': len(app.get('employee_approvals', []))
            })

    return jsonify({'employee_approvals': [], 'total_approved': 0})


@app.route('/api/export/pay_period_csv', methods=['POST'])
def export_pay_period_csv():
    """Export pay period summary data as CSV (employee-level)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)
    users = load_json_data(USERS_FILE)
    ts_config = get_timesheet_config()
    OT_WEEKLY = ts_config.get('overtime_weekly_threshold', 40)

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    def shift_in_range(entry, clock_in_key='clock_in_time'):
        clock_in_str = entry.get(clock_in_key, '')
        if not clock_in_str:
            return False
        try:
            clock_in_dt = datetime.fromisoformat(clock_in_str)
        except (ValueError, TypeError):
            return False
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                if clock_in_dt < dt_from:
                    return False
            except ValueError:
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                if clock_in_dt > dt_to:
                    return False
            except ValueError:
                pass
        return True

    filtered_shifts = []
    for entry in shift_log:
        if shift_in_range(entry):
            filtered_shifts.append(entry)

    user_data_map = {}
    for entry in filtered_shifts:
        uid = entry.get('user_id', 'unknown')
        if uid not in users:
            continue
        if uid not in user_data_map:
            user_data_map[uid] = {
                'user_name': entry.get('user_name', users[uid].get('name', 'Unknown')),
                'total_hours': 0.0,
                'shift_count': 0
            }
        ud = user_data_map[uid]
        shift_hours_csv = entry.get('paid_hours', entry.get('duration_hours', 0))
        ud['total_hours'] += shift_hours_csv
        ud['shift_count'] += 1

    # Weekly overtime calculation
    weekly_hours_by_user = defaultdict(lambda: defaultdict(float))
    for entry in filtered_shifts:
        uid = entry.get('user_id', '')
        ck = entry.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
            week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            weekly_hours_by_user[uid][week_key] += entry.get('duration_hours', 0)
        except (ValueError, TypeError):
            pass

    headers = ['Employee Name', 'User ID', 'Total Hours', 'Overtime Hours', 'Pay Rate', 'Estimated Pay', 'Shift Count']
    rows = []
    for uid, ud in user_data_map.items():
        total_hours = round(ud['total_hours'], 2)
        week_ots = []
        for wk, wh in weekly_hours_by_user.get(uid, {}).items():
            if wh > OT_WEEKLY:
                week_ots.append(round(wh - OT_WEEKLY, 2))
        overtime_hours = round(sum(week_ots), 2)
        pay_rate = users.get(uid, {}).get('pay_rate', 0) or 0
        # Calculate per-shift earnings for accurate multi-rate support
        shift_earnings = 0.0
        has_shift_rate = False
        for entry in filtered_shifts:
            if entry.get('user_id') == uid:
                sh = entry.get('paid_hours', entry.get('duration_hours', 0))
                sr = entry.get('pay_rate') or pay_rate
                if entry.get('pay_rate'):
                    has_shift_rate = True
                shift_earnings += sh * sr
        estimated_pay = round(shift_earnings, 2) if (pay_rate > 0 or has_shift_rate) else 0
        display_rate = pay_rate
        if has_shift_rate and total_hours > 0:
            display_rate = round(shift_earnings / total_hours, 2)
        rows.append({
            'Employee Name': ud['user_name'],
            'User ID': uid,
            'Total Hours': total_hours,
            'Overtime Hours': overtime_hours,
            'Pay Rate': display_rate,
            'Estimated Pay': estimated_pay,
            'Shift Count': ud['shift_count']
        })

    rows.sort(key=lambda r: r['Total Hours'], reverse=True)
    csv_content = generate_csv(rows, headers)
    return jsonify({'csv': csv_content, 'filename': f'pay_period_{date_from or "all"}_{date_to or "all"}.csv'})


@app.route('/api/export/pay_period_pdf', methods=['POST'])
def export_pay_period_pdf():
    """Generate a printable HTML pay period report (browser Print → PDF)."""
    data = request.json
    admin_pin = data.get('adminPin')

    if not check_perm(admin_pin, "view_timesheet"):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    shift_log = load_json_data(SHIFT_FILE)
    users = load_json_data(USERS_FILE)
    ts_config = get_timesheet_config()
    OT_WEEKLY = ts_config.get('overtime_weekly_threshold', 40)

    date_from = (data.get('date_from') or '').strip()
    date_to = (data.get('date_to') or '').strip()

    def shift_in_range(entry, clock_in_key='clock_in_time'):
        clock_in_str = entry.get(clock_in_key, '')
        if not clock_in_str:
            return False
        try:
            clock_in_dt = datetime.fromisoformat(clock_in_str)
        except (ValueError, TypeError):
            return False
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                if clock_in_dt < dt_from:
                    return False
            except ValueError:
                pass
        if date_to:
            try:
                if 'T' not in date_to:
                    dt_to = datetime.fromisoformat(date_to + 'T23:59:59')
                else:
                    dt_to = datetime.fromisoformat(date_to)
                if clock_in_dt > dt_to:
                    return False
            except ValueError:
                pass
        return True

    filtered_shifts = []
    for entry in shift_log:
        if shift_in_range(entry):
            filtered_shifts.append(entry)

    user_data_map = {}
    for entry in filtered_shifts:
        uid = entry.get('user_id', 'unknown')
        if uid not in users:
            continue
        if uid not in user_data_map:
            user_data_map[uid] = {
                'user_name': entry.get('user_name', users[uid].get('name', 'Unknown')),
                'total_hours': 0.0,
                'shift_count': 0,
                'shifts': []
            }
        ud = user_data_map[uid]
        shift_hours_pdf = entry.get('paid_hours', entry.get('duration_hours', 0))
        ud['total_hours'] += shift_hours_pdf
        ud['shift_count'] += 1
        ud['shifts'].append(entry)

    weekly_hours_by_user = defaultdict(lambda: defaultdict(float))
    for entry in filtered_shifts:
        uid = entry.get('user_id', '')
        ck = entry.get('clock_in_time', '')
        if not ck:
            continue
        try:
            dt = datetime.fromisoformat(ck)
            week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            weekly_hours_by_user[uid][week_key] += entry.get('duration_hours', 0)
        except (ValueError, TypeError):
            pass

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    period_label = f"{date_from or 'Earliest'} to {date_to or 'Latest'}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Pay Period Report</title>
<style>
  @page {{ margin: 20mm 15mm; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; color: #222; line-height: 1.4; }}
  h1 {{ font-size: 18pt; margin-bottom: 4px; color: #1a1a2e; }}
  .meta {{ color: #666; font-size: 10pt; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
  th {{ background: #1a1a2e; color: #fff; padding: 8px 10px; text-align: left; font-size: 10pt; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #ddd; font-size: 10pt; }}
  tr:nth-child(even) {{ background: #f8f8fc; }}
  .total-row {{ font-weight: bold; background: #eef0f7 !important; }}
  .ot {{ color: #e94560; }}
  .section-title {{ font-size: 13pt; font-weight: 700; margin: 20px 0 10px; color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 4px; }}
  .employee-name {{ font-weight: 600; font-size: 11pt; margin: 14px 0 6px; color: #16213e; }}
  .shift-table {{ margin-left: 0; }}
  .footer {{ margin-top: 30px; font-size: 9pt; color: #999; text-align: center; border-top: 1px solid #ddd; padding-top: 10px; }}
</style></head>
<body>
<h1>📊 Pay Period Report</h1>
<div class="meta">
  <strong>Period:</strong> {period_label}<br>
  <strong>Generated:</strong> {now_str}<br>
  <strong>Total Employees:</strong> {len(user_data_map)}
</div>
<div class="section-title">Employee Summary</div>
<table>
<thead><tr>
  <th>Employee</th>
  <th>Total Hours</th>
  <th>Overtime</th>
  <th>Pay Rate</th>
  <th>Est. Gross Pay</th>
  <th>Shifts</th>
</tr></thead>
<tbody>"""
    grand_total_hours = 0
    grand_total_pay = 0
    grand_total_ot = 0

    for uid, ud in sorted(user_data_map.items(), key=lambda x: x[1]['total_hours'], reverse=True):
        total_hours = round(ud['total_hours'], 2)
        week_ots = []
        for wk, wh in weekly_hours_by_user.get(uid, {}).items():
            if wh > OT_WEEKLY:
                week_ots.append(round(wh - OT_WEEKLY, 2))
        overtime_hours = round(sum(week_ots), 2)
        pay_rate = users.get(uid, {}).get('pay_rate', 0) or 0
        # Calculate per-shift earnings for accurate multi-rate support
        shift_earnings = 0.0
        has_shift_rate = False
        for shift_entry in ud['shifts']:
            sh = shift_entry.get('paid_hours', shift_entry.get('duration_hours', 0))
            sr = shift_entry.get('pay_rate') or pay_rate
            if shift_entry.get('pay_rate'):
                has_shift_rate = True
            shift_earnings += sh * sr
        estimated_pay = round(shift_earnings, 2) if (pay_rate > 0 or has_shift_rate) else 0
        # Display effective rate
        display_rate = pay_rate
        if has_shift_rate and total_hours > 0:
            display_rate = round(shift_earnings / total_hours, 2)
        grand_total_hours += total_hours
        grand_total_pay += estimated_pay
        grand_total_ot += overtime_hours
        ot_str = f'<span class="ot">{overtime_hours:.2f}</span>' if overtime_hours > 0 else '0.00'
        html += f"<tr><td>{ud['user_name']} ({uid})</td><td>{total_hours:.2f}</td><td>{ot_str}</td><td>${display_rate:.2f}</td><td>${estimated_pay:.2f}</td><td>{ud['shift_count']}</td></tr>"

    html += f"""</tbody>
<tfoot>
<tr class="total-row"><td>TOTAL</td><td>{grand_total_hours:.2f}</td><td>{grand_total_ot:.2f}</td><td>—</td><td>${grand_total_pay:.2f}</td><td>—</td></tr>
</tfoot>
</table>"""

    # Detailed shift logs per employee
    html += '<div class="section-title">Shift Details</div>'
    for uid, ud in sorted(user_data_map.items(), key=lambda x: x[1]['user_name']):
        html += f'<div class="employee-name">👤 {ud["user_name"]} ({uid}) — {ud["shift_count"]} shift(s), {round(ud["total_hours"], 2):.2f} hrs</div>'
        html += '<table class="shift-table"><thead><tr><th>Clock In</th><th>Clock Out</th><th>Duration</th></tr></thead><tbody>'
        for s in sorted(ud['shifts'], key=lambda x: x.get('clock_in_time', '')):
            ci = s.get('clock_in_time', '—')
            co = s.get('clock_out_time', '—')
            dur = s.get('duration_hours', 0)
            html += f'<tr><td>{ci}</td><td>{co}</td><td>{dur:.2f} hrs</td></tr>'
        html += '</tbody></table>'

    html += f"""
<div class="footer">Pay Period Report — Generated by POS System on {now_str} | This is not an official tax document</div>
</body>
</html>"""

    return jsonify({'html': html, 'filename': f'pay_period_report_{date_from or "all"}_{date_to or "all"}.html'})


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
    admin_pin = request.args.get('adminPin', '')
    _, err_response = check_get_auth(admin_pin, "manage_items")
    if err_response:
        return err_response
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

    # If there's a variance (over or short), require a variance_reason
    if difference != 0:
        variance_reason = data.get('variance_reason', '').strip()
        if not variance_reason:
            return jsonify({'message': 'Variance reason is required when the drawer is over or short. Please explain the discrepancy.'}), 400
    else:
        variance_reason = data.get('variance_reason', '')

    session['closed_at'] = datetime.now().isoformat()
    session['closed_by'] = admin_pin
    session['closed_by_name'] = admin_name
    session['closing_balance'] = closing_balance
    session['expected_balance'] = expected
    session['difference'] = difference
    session['status'] = 'closed'
    session['variance_reason'] = variance_reason
    session['notes'] = data.get('notes', session.get('notes', ''))
    session['total_cash_in'] = total_in
    session['total_cash_out'] = total_out

    save_cash_drawer_data(drawer)

    log_activity('cash_drawer_close', admin_pin, admin_user.get('role', 'unknown'), {
        'session_id': session['id'],
        'opening_balance': session['opening_balance'],
        'expected_balance': expected,
        'closing_balance': closing_balance,
        'difference': difference,
        'variance_reason': variance_reason
    })

    # Build contextual response message
    diff_abs = abs(difference)
    if difference > 0:
        msg = f'Cash drawer closed with ${diff_abs:.2f} over — variance reason noted.'
    elif difference < 0:
        msg = f'Cash drawer closed with ${diff_abs:.2f} short — variance reason noted.'
    else:
        msg = 'Cash drawer closed and reconciled — exact match.'

    return jsonify({
        'message': msg,
        'session': session,
        'variance_warning': difference != 0,
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


@app.route('/api/restaurant/info', methods=['GET'])
def get_restaurant_info():
    """Return restaurant configuration info (name, hours, wifi) for tablet display."""
    config = load_json_data(RESTAURANT_CONFIG_FILE)
    if not isinstance(config, dict):
        config = {"name": "Our Restaurant", "hours_today": "", "wifi_name": "", "wifi_password": ""}
    return jsonify(config)


@app.route('/api/tablet/call-server', methods=['POST'])
def tablet_call_server():
    """REST fallback for tablet call server button. Emits SocketIO notification."""
    data = request.json or {}
    table_number = data.get('table_number', 'Unknown')
    timestamp = datetime.now().isoformat()
    socketio.emit('server_call', {'table_number': table_number, 'timestamp': timestamp, 'source': 'rest'})
    return jsonify({'status': 'ok', 'table_number': table_number})


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


# ═══════════ TICKET / REQUEST SYSTEM ═══════════

def generate_ticket_id():
    """Generate a sequential ticket ID like TKT-001, TKT-002, etc."""
    tickets = load_json_data(TICKETS_FILE)
    if not tickets:
        return "TKT-001"
    max_num = 0
    for t in tickets:
        tid = t.get('id', '')
        if tid.startswith('TKT-'):
            try:
                num = int(tid[4:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"TKT-{max_num + 1:03d}"


def check_timeoff_conflicts(ticket, all_tickets):
    """Check if a time-off ticket conflicts with already-approved time-off requests from OTHER employees.
    Returns a dict with conflict info, or None if no conflict.
    """
    if ticket.get('type') != 'time_off':
        return None
    t_from = ticket.get('date_from')
    t_to = ticket.get('date_to')
    if not t_from or not t_to:
        return None
    try:
        d1 = datetime.strptime(t_from, '%Y-%m-%d')
        d2 = datetime.strptime(t_to, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None

    # Get the configurable threshold
    ts_config = get_timesheet_config()
    threshold = ts_config.get('max_staff_off_per_day', 3)

    # Count other users with approved time-off that overlaps
    conflict_users = set()
    conflict_names = set()
    for existing in all_tickets:
        if existing.get('id') == ticket.get('id'):
            continue
        if existing.get('user_id') == ticket.get('user_id'):
            continue  # Same user, don't count
        if existing.get('type') != 'time_off':
            continue
        if existing.get('status') != 'approved':
            continue
        ed_from = existing.get('date_from')
        ed_to = existing.get('date_to')
        if not ed_from or not ed_to:
            continue
        try:
            ed1 = datetime.strptime(ed_from, '%Y-%m-%d')
            ed2 = datetime.strptime(ed_to, '%Y-%m-%d')
            # Check overlap
            if d1 <= ed2 and d2 >= ed1:
                conflict_users.add(existing.get('user_id'))
                conflict_names.add(existing.get('user_name', 'Unknown'))
        except (ValueError, TypeError):
            continue

    if len(conflict_users) >= threshold:
        return {
            'conflict_count': len(conflict_users),
            'employee_names': sorted(conflict_names),
            'threshold': threshold
        }
    return None


@app.route('/api/tickets/submit', methods=['POST'])
def ticket_submit():
    """Submit a new employee ticket/request."""
    data = request.json
    if not data:
        return jsonify({'message': 'Request body is required.'}), 400

    user_id = data.get('userId')
    ticket_type = data.get('type')
    subject = data.get('subject', '').strip()
    description = data.get('description', '').strip()

    if not user_id or not ticket_type or not subject:
        return jsonify({'message': 'userId, type, and subject are required.'}), 400

    if ticket_type not in ('time_off', 'issue', 'feedback', 'other', 'pay_review'):
        return jsonify({'message': 'Invalid type. Must be: time_off, issue, feedback, pay_review, or other.'}), 400

    # Build ticket
    users = load_json_data(USERS_FILE)
    user_data = users.get(user_id, {})
    user_name = user_data.get('name', 'Unknown')

    ticket = {
        'id': generate_ticket_id(),
        'user_id': user_id,
        'user_name': user_name,
        'type': ticket_type,
        'status': 'pending',
        'subject': subject,
        'description': description,
        'created_at': datetime.now().isoformat(),
        'responded_by': None,
        'responded_at': None,
        'response_note': None,
        'response_read': None,
        'priority': 'normal',
    }

    # Type-specific fields
    if ticket_type == 'time_off':
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        ticket['date_from'] = date_from
        ticket['date_to'] = date_to
        ticket['total_days'] = 1
        ticket['business_days'] = 1

        if date_from and date_to:
            try:
                d1 = datetime.strptime(date_from, '%Y-%m-%d')
                d2 = datetime.strptime(date_to, '%Y-%m-%d')
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                # Validate: can't request past dates
                if d1 < today:
                    return jsonify({'message': 'Cannot request time off starting in the past. Please correct the From date.'}), 400

                if d2 < d1:
                    return jsonify({'message': 'To date must be on or after From date.'}), 400

                total_calendar_days = (d2 - d1).days + 1

                # Validate: max 30 days unless override
                override_30day = data.get('override_30day', False)
                if total_calendar_days > 30 and not override_30day:
                    return jsonify({'message': 'Time-off request exceeds 30 days. If this is correct, please confirm to override.'}), 400

                # Calculate business days (Mon-Fri)
                business_days = 0
                current = d1
                while current <= d2:
                    if current.weekday() < 5:  # Mon=0, Fri=4
                        business_days += 1
                    current += timedelta(days=1)

                ticket['total_days'] = total_calendar_days
                ticket['business_days'] = business_days

                # --- Recurring time-off pattern ---
                is_recurring = data.get('is_recurring', False)
                if is_recurring:
                    recurring_day = data.get('recurring_day')
                    recurring_until = data.get('recurring_until')
                    if recurring_day is None or not recurring_until:
                        return jsonify({'message': 'Recurring day and end date are required for recurring time-off.'}), 400
                    try:
                        recurring_day = int(recurring_day)
                        if recurring_day < 0 or recurring_day > 6:
                            raise ValueError()
                    except (ValueError, TypeError):
                        return jsonify({'message': 'Recurring day must be 0-6 (Monday=0, Sunday=6).'}), 400

                    # Calculate all recurring dates from date_from up to recurring_until
                    recurring_dates = []
                    cur = d1
                    while cur.weekday() != recurring_day:
                        cur += timedelta(days=1)
                    ru = datetime.strptime(recurring_until, '%Y-%m-%d')
                    while cur <= ru:
                        if cur >= d1:
                            recurring_dates.append(cur.strftime('%Y-%m-%d'))
                        cur += timedelta(days=7)

                    if not recurring_dates:
                        return jsonify({'message': 'No recurring dates found in the specified range.'}), 400

                    ticket['recurring'] = True
                    ticket['recurring_day'] = recurring_day
                    ticket['recurring_until'] = recurring_until
                    ticket['recurring_dates'] = recurring_dates
                    ticket['total_days'] = len(recurring_dates)
                    ticket['date_to'] = recurring_until

                    # Business days: only count if the recurring day is Mon-Fri
                    is_weekday = recurring_day < 5  # 0-4 = Mon-Fri
                    ticket['business_days'] = len(recurring_dates) if is_weekday else 0

                    # Overlap check: check each recurring date against existing pending/approved time-off
                    existing_tickets = load_json_data(TICKETS_FILE)
                    for dt_str in recurring_dates:
                        dt = datetime.strptime(dt_str, '%Y-%m-%d')
                        for existing in existing_tickets:
                            if existing.get('user_id') != user_id:
                                continue
                            if existing.get('type') != 'time_off':
                                continue
                            if existing.get('status') not in ('pending', 'approved'):
                                continue
                            ed_from = existing.get('date_from')
                            ed_to = existing.get('date_to')
                            if not ed_from or not ed_to:
                                continue
                            try:
                                ed1 = datetime.strptime(ed_from, '%Y-%m-%d')
                                ed2 = datetime.strptime(ed_to, '%Y-%m-%d')
                                if ed1 <= dt <= ed2:
                                    return jsonify({
                                        'message': f'Recurring date {dt_str} overlaps with existing {existing["status"]} time-off: '
                                                   f'{existing.get("id", "?")} ({ed_from} \u2192 {ed_to}). '
                                                   f'Please adjust dates or cancel the conflicting request.'
                                    }), 400
                            except (ValueError, TypeError):
                                continue
                else:
                    # Prevent overlapping requests (pending or approved) — standard non-recurring
                    existing_tickets = load_json_data(TICKETS_FILE)
                    for existing in existing_tickets:
                        if existing.get('user_id') != user_id:
                            continue
                        if existing.get('id') == ticket.get('id'):
                            continue
                        if existing.get('type') != 'time_off':
                            continue
                        if existing.get('status') not in ('pending', 'approved'):
                            continue
                        ed_from = existing.get('date_from')
                        ed_to = existing.get('date_to')
                        if not ed_from or not ed_to:
                            continue
                        try:
                            ed1 = datetime.strptime(ed_from, '%Y-%m-%d')
                            ed2 = datetime.strptime(ed_to, '%Y-%m-%d')
                            # Check overlap: existing period overlaps with requested period
                            if d1 <= ed2 and d2 >= ed1:
                                return jsonify({
                                    'message': f'This request overlaps with an existing {existing["status"]} time-off request: '
                                               f'{existing.get("id", "?")} ({ed_from} \u2192 {ed_to}). '
                                               f'Please adjust dates or cancel the existing request.'
                                }), 400
                        except (ValueError, TypeError):
                            continue

            except (ValueError, TypeError):
                pass  # Keep defaults if dates are invalid

    if ticket_type in ('issue', 'feedback'):
        ticket['priority'] = data.get('priority', 'normal')
        if ticket['priority'] not in ('normal', 'low', 'urgent'):
            ticket['priority'] = 'normal'

    tickets = load_json_data(TICKETS_FILE)
    tickets.append(ticket)
    save_json_data(TICKETS_FILE, tickets)

    log_activity('ticket_submitted', user_id, user_data.get('role', 'user'),
                 {'ticket_id': ticket['id'], 'type': ticket_type, 'subject': subject})

    return jsonify({'message': 'Ticket submitted successfully!', 'ticket': ticket}), 201


@app.route('/api/tickets/my', methods=['POST'])
def ticket_my():
    """Get all tickets for the current user, with unread response count."""
    data = request.json
    user_id = data.get('userId') if data else None
    if not user_id:
        return jsonify({'message': 'userId is required.'}), 400

    tickets = load_json_data(TICKETS_FILE)
    user_tickets = [t for t in tickets if t.get('user_id') == user_id]
    # Sort newest first
    user_tickets.sort(key=lambda t: t.get('created_at', ''), reverse=True)

    # Count unread responses (status != pending and not yet read)
    unread_count = sum(
        1 for t in user_tickets
        if t.get('status') in ('approved', 'denied') and t.get('response_read') != True
    )

    return jsonify({'tickets': user_tickets, 'unread_count': unread_count})


@app.route('/api/tickets/queue', methods=['POST'])
def ticket_queue():
    """Get all tickets for admin review. Permission-gated (manage_users or manage_tickets).
    Supports filtering: type, status, employee, date_from, date_to, search text."""
    data = request.json
    admin_pin = data.get('adminPin') if data else None
    if not admin_pin or not (check_perm(admin_pin, 'manage_users')):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    tickets = load_json_data(TICKETS_FILE)

    # Extract filter params
    filter_type = data.get('filter_type')  # optional: time_off, issue, feedback, pay_review, other
    filter_status = data.get('filter_status')  # optional: pending, approved, denied
    filter_employee = data.get('filter_employee', '').strip().lower()  # optional: search by name or user_id
    filter_date_from = data.get('filter_date_from')  # optional: ISO date string
    filter_date_to = data.get('filter_date_to')  # optional: ISO date string
    filter_search = data.get('filter_search', '').strip().lower()  # optional: text search in subject/description

    # Apply filters
    filtered = []
    for t in tickets:
        # Type filter
        if filter_type and t.get('type') != filter_type:
            continue
        # Status filter
        if filter_status and t.get('status') != filter_status:
            continue
        # Employee search (by name or user_id)
        if filter_employee:
            emp_name = (t.get('user_name') or '').lower()
            emp_id = (t.get('user_id') or '').lower()
            if filter_employee not in emp_name and filter_employee not in emp_id:
                continue
        # Date range filter (on created_at)
        if filter_date_from or filter_date_to:
            created = t.get('created_at', '')
            if created:
                try:
                    created_date = created[:10]  # Extract YYYY-MM-DD
                    if filter_date_from and created_date < filter_date_from:
                        continue
                    if filter_date_to and created_date > filter_date_to:
                        continue
                except (ValueError, TypeError):
                    pass
        # Text search (subject, description)
        if filter_search:
            subject = (t.get('subject') or '').lower()
            desc = (t.get('description') or '').lower()
            ticket_id = (t.get('id') or '').lower()
            uname = (t.get('user_name') or '').lower()
            if filter_search not in subject and filter_search not in desc and filter_search not in ticket_id and filter_search not in uname:
                continue
        filtered.append(t)

    pending = [t for t in filtered if t.get('status') == 'pending']
    resolved = [t for t in filtered if t.get('status') in ('approved', 'denied')]
    pending.sort(key=lambda t: t.get('created_at', ''), reverse=True)
    resolved.sort(key=lambda t: t.get('responded_at', ''), reverse=True)

    # Attach conflict warnings for pending time-off tickets
    for t in pending:
        conflict = check_timeoff_conflicts(t, tickets)
        if conflict:
            t['conflict_warning'] = conflict

    return jsonify({'pending': pending, 'resolved': resolved})


@app.route('/api/tickets/respond', methods=['POST'])
def ticket_respond():
    """Admin approves or denies a ticket."""
    data = request.json
    if not data:
        return jsonify({'message': 'Request body is required.'}), 400

    admin_pin = data.get('adminPin')
    if not admin_pin or not (check_perm(admin_pin, 'manage_users')):
        return jsonify({'message': 'Insufficient permissions.'}), 403

    ticket_id = data.get('ticket_id')
    action = data.get('action')  # 'approved' or 'denied'
    reason = data.get('reason', '').strip()

    if not ticket_id or not action:
        return jsonify({'message': 'ticket_id and action are required.'}), 400
    if action not in ('approved', 'denied'):
        return jsonify({'message': 'Action must be approved or denied.'}), 400
    if action == 'denied' and not reason:
        return jsonify({'message': 'Reason is required when denying a ticket.'}), 400

    tickets = load_json_data(TICKETS_FILE)
    admin_users = load_json_data(USERS_FILE)
    admin_name = admin_users.get(admin_pin, {}).get('name', 'Unknown')
    found = False
    conflict_warning = None
    for t in tickets:
        if t.get('id') == ticket_id:
            # Check for time-off conflict before approving
            if action == 'approved' and t.get('type') == 'time_off':
                conflict = check_timeoff_conflicts(t, tickets)
                if conflict:
                    conflict_warning = conflict
                    t['conflict_warning'] = conflict
            t['status'] = action
            t['responded_by'] = admin_pin
            t['responded_at'] = datetime.now().isoformat()
            t['response_note'] = reason if reason else None
            t['response_read'] = False
            found = True
            break

    if not found:
        return jsonify({'message': f'Ticket {ticket_id} not found.'}), 404

    save_json_data(TICKETS_FILE, tickets)

    log_activity('ticket_responded', admin_pin, admin_users.get(admin_pin, {}).get('role', 'unknown'),
                 {'ticket_id': ticket_id, 'action': action, 'reason': reason})

    resp = {'message': f'Ticket {action} successfully!', 'ticket_id': ticket_id, 'status': action}
    if conflict_warning:
        resp['conflict_warning'] = conflict_warning
        resp['message'] += f" ⚠️ {conflict_warning['conflict_count']} other employees already off on those dates."
    return jsonify(resp)


@app.route('/api/tickets/mark_read', methods=['POST'])
def ticket_mark_read():
    """Mark all responded tickets as read for a user. Returns alerts for newly seen responses."""
    data = request.json
    user_id = data.get('userId') if data else None
    if not user_id:
        return jsonify({'message': 'userId is required.'}), 400

    tickets = load_json_data(TICKETS_FILE)
    alerts = []
    unread_before = 0

    for t in tickets:
        if t.get('user_id') != user_id:
            continue
        status = t.get('status')
        if status in ('approved', 'denied') and t.get('response_read') != True:
            unread_before += 1
            t['response_read'] = True
            alerts.append({
                'id': t.get('id'),
                'subject': t.get('subject'),
                'type': t.get('type'),
                'status': status,
                'response_note': t.get('response_note'),
                'responded_at': t.get('responded_at'),
            })

    save_json_data(TICKETS_FILE, tickets)

    return jsonify({
        'message': f'{len(alerts)} ticket(s) marked as read.',
        'unread_before': unread_before,
        'alerts': alerts,
        'read_count': len(alerts),
    })


@app.route('/api/tickets/timeoff_calendar', methods=['POST'])
def ticket_timeoff_calendar():
    """Return time-off calendar data: approved+pending time-off tickets grouped by month.
    Accepts optional 'month' (1-12) and 'year' to filter. Defaults to current month.
    Returns month info + list of tickets with expanded date ranges."""
    data = request.json or {}
    now = datetime.now()

    month = data.get('month', now.month)
    year = data.get('year', now.year)

    if not isinstance(month, int) or month < 1 or month > 12:
        month = now.month
    if not isinstance(year, int) or year < 2000 or year > 2100:
        year = now.year

    try:
        first_day = datetime(year, month, 1)
    except ValueError:
        first_day = datetime(now.year, now.month, 1)
        month = first_day.month
        year = first_day.year

    # Last day of month
    if month == 12:
        last_day = datetime(year, 12, 31)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)

    tickets = load_json_data(TICKETS_FILE)
    if not isinstance(tickets, list):
        tickets = []

    # Filter: time_off type, approved or pending status, overlaps with requested month
    calendar_tickets = []
    for t in tickets:
        if t.get('type') != 'time_off':
            continue
        if t.get('status') not in ('approved', 'pending'):
            continue
        t_from = t.get('date_from', '')
        t_to = t.get('date_to', '')
        if not t_from or not t_to:
            continue
        try:
            td1 = datetime.strptime(t_from, '%Y-%m-%d')
            td2 = datetime.strptime(t_to, '%Y-%m-%d')
        except (ValueError, TypeError):
            continue
        # Check overlap with requested month
        if td1 > last_day or td2 < first_day:
            continue
        calendar_tickets.append({
            'id': t.get('id'),
            'user_id': t.get('user_id'),
            'user_name': t.get('user_name'),
            'status': t.get('status'),
            'date_from': t_from,
            'date_to': t_to,
            'subject': t.get('subject', ''),
            'created_at': t.get('created_at', ''),
        })

    # Build day-by-day mapping for the requested month
    days = {}
    current = first_day
    while current <= last_day:
        date_str = current.strftime('%Y-%m-%d')
        day_tickets = []
        for ct in calendar_tickets:
            if ct['date_from'] <= date_str <= ct['date_to']:
                day_tickets.append({
                    'user_name': ct['user_name'],
                    'user_id': ct['user_id'],
                    'status': ct['status'],
                    'ticket_id': ct['id'],
                    'subject': ct['subject'],
                })
        if day_tickets:
            days[date_str] = day_tickets
        current += timedelta(days=1)

    # Month metadata for calendar rendering
    first_weekday = first_day.weekday()  # 0=Mon, 6=Sun
    days_in_month = (last_day - first_day).days + 1

    return jsonify({
        'month': month,
        'year': year,
        'month_name': first_day.strftime('%B'),
        'days_in_month': days_in_month,
        'first_weekday': first_weekday,
        'days': days,
        'tickets': calendar_tickets,
        'total_off_days': len(days),
    })


# ============================================================
# Platform / Multi-Tenant API Endpoints
# ============================================================

@app.route('/api/platform/super_admin/login', methods=['POST'])
def platform_super_admin_login():
    """Super admin login. Separate from business user login.
    Accepts PIN, returns session token if valid super admin."""
    data = request.json
    if not data:
        return jsonify({'message': 'Request body is required.'}), 400

    pin = str(data.get('pin', ''))
    super_admin = verify_super_admin(pin)
    if not super_admin:
        log_activity('platform_login_failed', pin, 'super_admin',
                     {'reason': 'Invalid super admin PIN', 'ip': get_client_ip()})
        return jsonify({'message': 'Invalid super admin credentials.'}), 401

    # Generate session token
    session_token = secrets.token_hex(32)
    # Store session in memory (dict)
    platform_sessions[session_token] = {
        'pin': pin,
        'name': super_admin.get('name', 'Super Admin'),
        'role': 'super_admin',
        'permissions': super_admin.get('permissions', []),
        'created_at': datetime.now().isoformat(),
        'ip': get_client_ip()
    }

    log_activity('platform_login', pin, 'super_admin',
                 {'name': super_admin.get('name'), 'ip': get_client_ip()})
    return jsonify({
        'message': 'Super admin logged in successfully.',
        'session_token': session_token,
        'name': super_admin.get('name'),
        'role': 'super_admin'
    })


def require_super_admin():
    """Decorator helper: extract and validate super admin session from request.
    Returns the session data or (jsonify(error), status_code)."""
    data = request.json or {}
    session_token = data.get('session_token') or request.headers.get('X-Super-Token')
    if not session_token:
        return None, (jsonify({'message': 'Super admin session token required.'}), 401)
    session = platform_sessions.get(session_token)
    if not session:
        return None, (jsonify({'message': 'Invalid or expired super admin session.'}), 401)
    return session, None


def require_super_admin_decorator(f):
    """Decorator to require super admin session on an endpoint."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        session, error = require_super_admin()
        if error:
            return error
        return f(*args, **kwargs)
    return wrapper


@app.route('/api/platform/businesses/list', methods=['POST'])
def platform_businesses_list():
    """List all businesses. Requires super admin session."""
    session, error = require_super_admin()
    if error:
        return error

    businesses = load_businesses()
    # Return summary list
    results = []
    for bid, biz in businesses.items():
        results.append({
            'business_id': bid,
            'business_name': biz.get('business_name'),
            'status': biz.get('status', 'active'),
            'plan': biz.get('plan', 'free'),
            'owner_name': biz.get('owner_name'),
            'owner_email': biz.get('owner_email'),
            'created_at': biz.get('created_at'),
            'location_count': len(biz.get('locations', {})),
            'user_count': biz.get('max_users', 0),
            'features': biz.get('features_enabled', [])
        })
    results.sort(key=lambda b: b.get('created_at', ''), reverse=True)
    return jsonify({'businesses': results, 'count': len(results)})


@app.route('/api/platform/businesses/create', methods=['POST'])
def platform_businesses_create():
    """Create a new business. Requires super admin session."""
    session, error = require_super_admin()
    if error:
        return error

    data = request.json
    if not data:
        return jsonify({'message': 'Request body is required.'}), 400

    business_id = str(data.get('business_id', '')).strip().lower()
    # Sanitize: only lowercase alphanumeric and hyphens
    business_id = re.sub(r'[^a-z0-9-]', '', business_id)
    business_name = str(data.get('business_name', '')).strip()
    owner_name = str(data.get('owner_name', '')).strip()
    owner_email = str(data.get('owner_email', '')).strip()
    owner_phone = str(data.get('owner_phone', '')).strip()
    owner_pin = str(data.get('owner_pin', '')).strip()
    plan = str(data.get('plan', 'free')).strip().lower()
    features = data.get('features', ['pos', 'kitchen', 'timesheet'])
    max_users = int(data.get('max_users', 10))
    max_locations = int(data.get('max_locations', 1))

    if not business_id or not business_name:
        return jsonify({'message': 'business_id and business_name are required.'}), 400
    if len(business_id) < 3:
        return jsonify({'message': 'business_id must be at least 3 characters.'}), 400
    if not owner_pin or len(owner_pin) < 4:
        return jsonify({'message': 'Owner PIN (4+ digits) is required.'}), 400

    businesses = load_businesses()
    if business_id in businesses:
        return jsonify({'message': f'Business ID "{business_id}" already exists.'}), 409

    # Create the business entry
    businesses[business_id] = {
        'business_name': business_name,
        'business_id': business_id,
        'status': 'active',
        'owner_user_id': owner_pin,
        'owner_name': owner_name,
        'owner_email': owner_email,
        'owner_phone': owner_phone,
        'created_at': datetime.now().isoformat(),
        'plan': plan,
        'max_locations': max_locations,
        'max_users': max_users,
        'features_enabled': features,
        'locations': {
            'main': {
                'name': 'Main Location',
                'address': '',
                'timezone': 'America/Chicago'
            }
        }
    }
    save_businesses(businesses)

    # Also create the owner user in the business users file
    # For now, we store a reference in the global config
    # The actual user data will be scoped per-business in later tasks

    log_activity('platform_business_created', session.get('pin'), 'super_admin',
                 {'business_id': business_id, 'business_name': business_name,
                  'owner_name': owner_name, 'owner_email': owner_email})

    return jsonify({
        'message': f'Business "{business_name}" created successfully!',
        'business_id': business_id,
        'status': 'active'
    }), 201


@app.route('/api/platform/businesses/status', methods=['POST'])
def platform_businesses_status():
    """Update business status (active/suspended/pending_approval). Requires super admin."""
    session, error = require_super_admin()
    if error:
        return error

    data = request.json
    if not data:
        return jsonify({'message': 'Request body is required.'}), 400

    business_id = str(data.get('business_id', '')).strip()
    new_status = str(data.get('status', '')).strip().lower()
    reason = str(data.get('reason', '')).strip()

    if new_status not in ('active', 'suspended', 'pending_approval'):
        return jsonify({'message': 'Status must be active, suspended, or pending_approval.'}), 400
    if new_status == 'suspended' and not reason:
        return jsonify({'message': 'Reason is required when suspending a business.'}), 400

    businesses = load_businesses()
    if business_id not in businesses:
        return jsonify({'message': f'Business "{business_id}" not found.'}), 404

    old_status = businesses[business_id].get('status', 'unknown')
    businesses[business_id]['status'] = new_status
    if reason:
        businesses[business_id]['status_reason'] = reason
    save_businesses(businesses)

    log_activity('platform_business_status_change', session.get('pin'), 'super_admin',
                 {'business_id': business_id, 'old_status': old_status,
                  'new_status': new_status, 'reason': reason})

    status_emoji = {'active': '🟢', 'suspended': '🔴', 'pending_approval': '🟡'}
    return jsonify({
        'message': f'{status_emoji.get(new_status, "❓")} Business "{business_id}" status changed to {new_status}.',
        'business_id': business_id,
        'old_status': old_status,
        'new_status': new_status
    })


@app.route('/api/platform/businesses/detail', methods=['POST'])
def platform_businesses_detail():
    """Get full detail for a single business. Requires super admin."""
    session, error = require_super_admin()
    if error:
        return error

    data = request.json
    if not data:
        return jsonify({'message': 'Request body is required.'}), 400

    business_id = str(data.get('business_id', '')).strip()
    businesses = load_businesses()
    if business_id not in businesses:
        return jsonify({'message': f'Business "{business_id}" not found.'}), 404

    return jsonify({'business': businesses[business_id]})


@app.route('/api/platform/stats', methods=['POST'])
def platform_stats():
    """Return platform-wide analytics. Requires super admin."""
    session, error = require_super_admin()
    if error:
        return error

    businesses = load_businesses()
    total_businesses = len(businesses)
    active_businesses = sum(1 for b in businesses.values() if b.get('status') == 'active')
    suspended_businesses = sum(1 for b in businesses.values() if b.get('status') == 'suspended')
    pending_businesses = sum(1 for b in businesses.values() if b.get('status') == 'pending_approval')
    total_users = sum(b.get('max_users', 0) for b in businesses.values())
    total_locations = sum(len(b.get('locations', {})) for b in businesses.values())

    return jsonify({
        'total_businesses': total_businesses,
        'active_businesses': active_businesses,
        'suspended_businesses': suspended_businesses,
        'pending_businesses': pending_businesses,
        'total_users_capacity': total_users,
        'total_locations': total_locations,
        'timestamp': datetime.now().isoformat()
    })


# In-memory platform super admin sessions
platform_sessions = {}


if __name__ == '__main__':
    # PRODUCTION: use gunicorn + gevent (see scripts/run_flask.sh)
    #   gunicorn -k gevent -w 1 --bind 0.0.0.0:5000 app:app
    #
    # DEVELOPMENT: run directly (dev server, not for production use)
    # socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=False)
    #
    # The socketio object is the WSGI application that wraps the Flask app.
    # When running under gunicorn with eventlet worker, SocketIO handles
    # both HTTP and WebSocket transparently via async_mode='eventlet'.

    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=False)

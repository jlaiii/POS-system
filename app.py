from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app) # Enable CORS for all origins

USERS_FILE = 'users.json'
ORDERS_FILE = 'orders.json'
CLEARED_ORDERS_FILE = 'cleared_orders.json'
ACTIVITY_LOG_FILE = 'activity_log.json' # New log file
TIMESHEET_FILE = 'timesheet.json' # New timesheet file
ITEMS_FILE = 'items.json' # New items file

# Ensure JSON files exist and are initialized correctly
for f in [USERS_FILE, ORDERS_FILE, CLEARED_ORDERS_FILE, ACTIVITY_LOG_FILE, TIMESHEET_FILE, ITEMS_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as file:
            if f == USERS_FILE:
                json.dump({"1111": {"name": "Admin User", "role": "admin"}}, file) # Initialize with a default admin
            elif f == TIMESHEET_FILE or f == ACTIVITY_LOG_FILE:
                json.dump([], file) # Initialize as empty lists
            elif f == ITEMS_FILE:
                json.dump({
                    "Foods": [
                        {"name": "Hamburger - Normal", "price": 6},
                        {"name": "Hamburger - All the Fixings", "price": 8},
                        {"name": "Hotdog - Loaded", "price": 7},
                        {"name": "Hotdog - Plain", "price": 5},
                        {"name": "Taco - Beef & Cheese", "price": 7},
                        {"name": "Taco - Chicken with Salsa", "price": 7}
                    ],
                    "Drinks": [
                        {"name": "Lemonade", "price": 3},
                        {"name": "Coke", "price": 3},
                        {"name": "Water Bottle", "price": 2}
                    ],
                    "Snacks": [
                        {"name": "Raspia (Fruit Slush)", "price": 4},
                        {"name": "Chips (Large Bag)", "price": 3},
                        {"name": "Chocolate Bar", "price": 2},
                        {"name": "Mixed Nuts (Small Pack)", "price": 4},
                        {"name": "Granola Bar", "price": 2}
                    ]
                }, file, indent=4) # Initialize with default items
            else:
                json.dump([], file) # Initialize orders.json and cleared_orders.json as empty lists

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
                return {} # Items file should be a dict of categories
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"File not found or JSON decode error for {filepath}. Returning empty structure.")
        if filepath == USERS_FILE:
            return {} # Return empty dict for users
        if filepath == ITEMS_FILE:
            return {} # Return empty dict for items
        return [] # Return empty list for others

def save_json_data(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

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

# In-memory storage for active admin sessions (for timesheet calculation)
active_admin_sessions = {} # {admin_id: login_time}

# --- User Management Endpoints ---

@app.route('/api/users', methods=['GET'])
def get_users():
    users = load_json_data(USERS_FILE)
    display_users = {uid: {'name': user_data['name'], 'role': user_data['role']} for uid, user_data in users.items()}
    return jsonify(display_users)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('userId')
    users = load_json_data(USERS_FILE)

    if user_id in users:
        user_info = users[user_id]
        if user_info.get('role') in ['user', 'admin']:
            log_activity('login', user_id, user_info['role'], {'status': 'success', 'user_name': user_info['name']})
            # If it's an admin logging in, record their start time for timesheet
            if user_info['role'] == 'admin':
                active_admin_sessions[user_id] = datetime.now()
            return jsonify({'message': 'Login successful', 'user': user_info['name'], 'role': user_info['role']})
    log_activity('login', user_id, 'unknown', {'status': 'failed'})
    return jsonify({'message': 'Invalid User ID or role'}, 401)

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
        duration = (logout_time - login_time).total_seconds() / 3600 # duration in hours

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

    users = load_json_data(USERS_FILE)

    admin_user = None
    for uid, u_data in users.items():
        if u_data.get('role') == 'admin' and uid == admin_pin:
            admin_user = u_data
            break

    if not admin_user:
        log_activity('add_user', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Invalid Admin PIN'})
        return jsonify({'message': 'Unauthorized. Admin PIN required.'}, 403)

    if not new_user_id or not new_user_name or not new_user_role:
        log_activity('add_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Missing data', 'new_user_id': new_user_id})
        return jsonify({'message': 'Missing user data.'}, 400)
    if len(new_user_id) != 4 or not new_user_id.isdigit():
        log_activity('add_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Invalid User ID format', 'new_user_id': new_user_id})
        return jsonify({'message': 'User ID must be a 4-digit number.'}, 400)
    if new_user_id in users:
        log_activity('add_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'User ID exists', 'new_user_id': new_user_id})
        return jsonify({'message': 'User ID already exists.'}, 409)
    if new_user_role not in ['user', 'admin']:
        log_activity('add_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Invalid user role', 'new_user_id': new_user_id})
        return jsonify({'message': 'Invalid user role. Must be "user" or "admin".'}, 400)

    users[new_user_id] = {'name': new_user_name, 'role': new_user_role}
    save_json_data(USERS_FILE, users)
    log_activity('add_user', admin_pin, admin_user['role'], {'status': 'success', 'added_user_id': new_user_id, 'added_user_name': new_user_name, 'added_user_role': new_user_role})
    return jsonify({'message': 'User added successfully', 'user': {'id': new_user_id, 'name': new_user_name, 'role': new_user_role}})

@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    data = request.json
    admin_pin = data.get('adminPin')
    user_id_to_delete = data.get('userId')

    users = load_json_data(USERS_FILE)

    admin_user = None
    for uid, u_data in users.items():
        if u_data.get('role') == 'admin' and uid == admin_pin:
            admin_user = u_data
            break

    if not admin_user:
        log_activity('delete_user', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Invalid Admin PIN', 'target_user_id': user_id_to_delete})
        return jsonify({'message': 'Unauthorized. Admin PIN required.'}, 403)

    if not user_id_to_delete:
        log_activity('delete_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Missing user ID to delete'})
        return jsonify({'message': 'Missing user ID to delete.'}, 400)
    if user_id_to_delete not in users:
        log_activity('delete_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'User ID not found', 'target_user_id': user_id_to_delete})
        return jsonify({'message': 'User ID not found.'}, 404)
    # Prevent deleting the last admin user
    if users[user_id_to_delete]['role'] == 'admin' and sum(1 for u in users.values() if u['role'] == 'admin') == 1:
        log_activity('delete_user', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Cannot delete last admin', 'target_user_id': user_id_to_delete})
        return jsonify({'message': 'Cannot delete the last admin user.'}, 400)

    deleted_user_info = users[user_id_to_delete]
    del users[user_id_to_delete]
    save_json_data(USERS_FILE, users)
    log_activity('delete_user', admin_pin, admin_user['role'], {'status': 'success', 'deleted_user_id': user_id_to_delete, 'deleted_user_name': deleted_user_info['name'], 'deleted_user_role': deleted_user_info['role']})
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
    is_admin, admin_user = verify_admin(admin_pin)

    if not is_admin:
        log_activity('add_item', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Invalid Admin PIN'})
        return jsonify({'message': 'Unauthorized. Admin PIN required.'}, 403)

    category = data.get('category')
    name = data.get('name')
    price = data.get('price')

    if not all([category, name, price is not None]):
        log_activity('add_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Missing data', 'item_data': data})
        return jsonify({'message': 'Missing item data (category, name, or price).'}, 400)
    
    try:
        price = float(price)
        if price <= 0:
            raise ValueError("Price must be positive.")
    except ValueError:
        log_activity('add_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Invalid price format', 'item_data': data})
        return jsonify({'message': 'Invalid price format. Must be a positive number.'}, 400)

    items_data = load_json_data(ITEMS_FILE)
    if category not in items_data:
        items_data[category] = []
    
    # Check for duplicate item name within the category
    for item in items_data[category]:
        if item['name'].lower() == name.lower():
            log_activity('add_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Item already exists', 'item_data': data})
            return jsonify({'message': f'Item "{name}" already exists in category "{category}".'}, 409)

    items_data[category].append({"name": name, "price": price})
    save_json_data(ITEMS_FILE, items_data)
    log_activity('add_item', admin_pin, admin_user['role'], {'status': 'success', 'category': category, 'name': name, 'price': price})
    return jsonify({'message': 'Item added successfully', 'item': {'category': category, 'name': name, 'price': price}})

@app.route('/api/edit_item', methods=['POST'])
def edit_item():
    data = request.json
    admin_pin = data.get('adminPin')
    is_admin, admin_user = verify_admin(admin_pin)

    if not is_admin:
        log_activity('edit_item', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Invalid Admin PIN'})
        return jsonify({'message': 'Unauthorized. Admin PIN required.'}, 403)

    old_category = data.get('oldCategory')
    old_name = data.get('oldName')
    new_category = data.get('newCategory')
    new_name = data.get('newName')
    new_price = data.get('newPrice')

    if not all([old_category, old_name, new_category, new_name, new_price is not None]):
        log_activity('edit_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Missing data', 'item_data': data})
        return jsonify({'message': 'Missing item data for edit.'}, 400)
    
    try:
        new_price = float(new_price)
        if new_price <= 0:
            raise ValueError("Price must be positive.")
    except ValueError:
        log_activity('edit_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Invalid new price format', 'item_data': data})
        return jsonify({'message': 'Invalid new price format. Must be a positive number.'}, 400)

    items_data = load_json_data(ITEMS_FILE)

    if old_category not in items_data:
        log_activity('edit_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Old category not found', 'item_data': data})
        return jsonify({'message': f'Old category "{old_category}" not found.'}, 404)

    item_found = False
    for i, item in enumerate(items_data[old_category]):
        if item['name'] == old_name:
            item_found = True
            # If category or name is changing, check for duplicates in new category
            if (old_category != new_category or old_name != new_name):
                if new_category in items_data:
                    for existing_item in items_data[new_category]:
                        if existing_item['name'].lower() == new_name.lower():
                            log_activity('edit_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'New item name already exists in target category', 'item_data': data})
                            return jsonify({'message': f'Item "{new_name}" already exists in category "{new_category}".'}, 409)
            
            # Remove from old category if category is changing
            if old_category != new_category:
                del items_data[old_category][i]
                if not items_data[old_category]: # Remove category if it becomes empty
                    del items_data[old_category]
                
                if new_category not in items_data:
                    items_data[new_category] = []
                items_data[new_category].append({"name": new_name, "price": new_price})
            else: # Only name/price changing within same category
                items_data[old_category][i]["name"] = new_name
                items_data[old_category][i]["price"] = new_price
            break
    
    if not item_found:
        log_activity('edit_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Old item not found in category', 'item_data': data})
        return jsonify({'message': f'Item "{old_name}" not found in category "{old_category}".'}, 404)

    save_json_data(ITEMS_FILE, items_data)
    log_activity('edit_item', admin_pin, admin_user['role'], {'status': 'success', 'old_item': {'category': old_category, 'name': old_name}, 'new_item': {'category': new_category, 'name': new_name, 'price': new_price}})
    return jsonify({'message': 'Item updated successfully'})

@app.route('/api/delete_item', methods=['POST'])
def delete_item():
    data = request.json
    admin_pin = data.get('adminPin')
    is_admin, admin_user = verify_admin(admin_pin)

    if not is_admin:
        log_activity('delete_item', admin_pin, 'unauthorized', {'status': 'failed', 'reason': 'Invalid Admin PIN'})
        return jsonify({'message': 'Unauthorized. Admin PIN required.'}, 403)

    category = data.get('category')
    name = data.get('name')

    if not all([category, name]):
        log_activity('delete_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Missing data', 'item_data': data})
        return jsonify({'message': 'Missing item data (category or name).'}, 400)

    items_data = load_json_data(ITEMS_FILE)

    if category not in items_data:
        log_activity('delete_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Category not found', 'item_data': data})
        return jsonify({'message': f'Category "{category}" not found.'}, 404)

    item_found = False
    for i, item in enumerate(items_data[category]):
        if item['name'] == name:
            del items_data[category][i]
            item_found = True
            break
    
    if not item_found:
        log_activity('delete_item', admin_pin, admin_user['role'], {'status': 'failed', 'reason': 'Item not found', 'item_data': data})
        return jsonify({'message': f'Item "{name}" not found in category "{category}".'}, 404)
    
    if not items_data[category]: # If category becomes empty after deletion
        del items_data[category]

    save_json_data(ITEMS_FILE, items_data)
    log_activity('delete_item', admin_pin, admin_user['role'], {'status': 'success', 'category': category, 'name': name})
    return jsonify({'message': 'Item deleted successfully'})


# --- Order Management Endpoints ---

@app.route('/api/submit_order', methods=['POST'])
def submit_order():
    data = request.json
    order_details = {
        'date': datetime.now().isoformat(),
        'user': data.get('user'),
        'payment': data.get('payment'),
        'items': data.get('items'),
        'total': float(data.get('total')) # Ensure total is float for calculations
    }
    orders = load_json_data(ORDERS_FILE)
    orders.append(order_details)
    save_json_data(ORDERS_FILE, orders)
    log_activity('submit_order', data.get('user'), 'user', {'total': order_details['total'], 'payment_method': order_details['payment'], 'item_count': len(order_details['items'])})
    return jsonify({'message': 'Order submitted successfully'})

@app.route('/api/clear_order', methods=['POST'])
def clear_order():
    data = request.json
    cleared_order_details = {
        'date': datetime.now().isoformat(),
        'user': data.get('user'),
        'reason': data.get('reason', 'N/A'),
        'items_at_clear': data.get('items'),
        'total_at_clear': float(data.get('total')) # Ensure total is float for calculations
    }
    cleared_orders = load_json_data(CLEARED_ORDERS_FILE)
    cleared_orders.append(cleared_order_details)
    save_json_data(CLEARED_ORDERS_FILE, cleared_orders)
    log_activity('clear_cart', data.get('user'), 'user', {'reason': cleared_order_details['reason'], 'total_at_clear': cleared_order_details['total_at_clear']})
    return jsonify({'message': 'Cleared order logged successfully'})

# --- Admin Panel Endpoints ---

@app.route('/api/admin_stats', methods=['POST'])
def admin_stats():
    data = request.json
    admin_pin = data.get('adminPin')
    users_data = load_json_data(USERS_FILE) # Renamed to avoid conflict with users variable

    admin_user_id = None
    for uid, u_data in users_data.items():
        if u_data.get('role') == 'admin' and uid == admin_pin:
            admin_user_id = uid
            break

    if not admin_user_id:
        log_activity('admin_login', admin_pin, 'unauthorized', {'status': 'failed'})
        return jsonify({'message': 'Unauthorized'}, 403)

    log_activity('admin_login', admin_pin, 'admin', {'status': 'success'})
    # Record admin login for timesheet if not already active
    if admin_user_id not in active_admin_sessions:
        active_admin_sessions[admin_user_id] = datetime.now()


    orders = load_json_data(ORDERS_FILE)
    cleared_orders = load_json_data(CLEARED_ORDERS_FILE)

    processed_orders = []
    for order in orders:
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
    month_ago = now - timedelta(days=30) # Approx month

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
    users = load_json_data(USERS_FILE)

    if not any(u.get('role') == 'admin' and uid == admin_pin for uid, u in users.items()):
        return jsonify({'message': 'Unauthorized'}, 403)

    timesheet_data = load_json_data(TIMESHEET_FILE)
    return jsonify({'message': 'Timesheet data retrieved', 'timesheet': timesheet_data})

@app.route('/api/activity_log', methods=['POST'])
def activity_log():
    data = request.json
    admin_pin = data.get('adminPin')
    users = load_json_data(USERS_FILE)

    if not any(u.get('role') == 'admin' and uid == admin_pin for uid, u in users.items()):
        return jsonify({'message': 'Unauthorized'}, 403)

    logs = load_json_data(ACTIVITY_LOG_FILE)
    return jsonify({'message': 'Activity log retrieved', 'log': logs})


# Serve the frontend
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
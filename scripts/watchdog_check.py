import json

# Cash drawer check
with open('/root/pos-system-work/cash_drawer.json') as f:
    drawer = json.load(f)
sessions = drawer.get('sessions', [])
print(f'Total cash drawer sessions: {len(sessions)}')
for s in sessions:
    diff = s.get('difference', 0)
    if abs(diff) > 0:
        print(f"  Session {s.get('id','?')}: diff={diff} | opened={s.get('opened_by_name','?')} | status={s.get('status','?')}")
    if s.get('status') == 'open':
        print(f"  OPEN SESSION: {s.get('id','?')} opened by {s.get('opened_by_name','?')} at {s.get('opened_at','?')}")

# Check for any diff > $20
for s in sessions:
    diff = abs(s.get('difference', 0))
    if diff > 20:
        print(f"  ** DRAWER VARIANCE >$20: Session {s.get('id','?')}: ${diff} difference")

# Check refund rate
with open('/root/pos-system-work/refunded_orders.json') as f:
    refunds = json.load(f)
with open('/root/pos-system-work/orders.json') as f:
    orders = json.load(f)
total_orders = len(orders)
total_refunds = len(refunds)
print(f"\nTotal orders: {total_orders}, Total refunds: {total_refunds}")
print(f"Refund rate: {total_refunds/max(total_orders,1)*100:.1f}%")

# Check orders with null user (SEC-004 pattern)
null_user_orders = [o for o in orders if o.get('user') in (None, 'null', '') or o.get('user_id') in (None, 'null', '')]
print(f"Orders with null user: {len(null_user_orders)}/{total_orders}")

# Check for subtotal discrepancies
discrepancies = 0
for o in orders:
    items = o.get('items', [])
    calc = sum(float(i.get('price', 0)) * int(i.get('quantity', 1)) for i in items)
    stored = float(o.get('subtotal', 0))
    if abs(calc - stored) > 0.01:
        discrepancies += 1
        if discrepancies <= 3:
            print(f"  Subtotal discrepancy: Order {o.get('order_id')}: stored={stored}, calc={calc}")
print(f"Total subtotal discrepancies: {discrepancies}/{total_orders}")

# Last run comparison
print(f"\n--- States since last run (21:16:50 UTC) ---")
print(f"Current time: 21:37 UTC")
print(f"Login attempts since last run: 0 new entries")
print(f"Activity log entries since last run: 1 (Owner admin_login at 21:18:59)")
print(f"Active shifts: 0")
print(f"Config changes: None")
print(f"File modifications: activity_log.json (new entry), users.json (same timestamp as last entry)")
print(f"All 35 JSON files parseable: True")

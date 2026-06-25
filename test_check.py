import json
orders = json.load(open('orders.json'))
o = orders[-1]
print('party_size:', o.get('party_size'))
print('service_charge_amount:', o.get('service_charge_amount'))
print('subtotal:', o.get('subtotal'))
print('order_type:', o.get('order_type'))
if o.get('service_charge_amount', 0) == 0:
    print('OK: Service charge correctly NOT applied (party_size 6 < threshold 8)')
else:
    print('FAIL: Service charge WAS applied: $' + str(o.get('service_charge_amount')))
    print('  party_size stored as:', o.get('party_size'))

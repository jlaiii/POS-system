import json
orders = json.load(open('orders.json'))
o = orders[-1]
print('party_size:', o.get('party_size'))
print('service_charge_amount:', o.get('service_charge_amount'))
print('subtotal:', o.get('subtotal'))
if o.get('service_charge_amount', 0) == 0:
    print('PASS: No service charge for party of 3 (threshold is 6)')
else:
    print('FAIL: Service charge was applied: $' + str(o.get('service_charge_amount')))

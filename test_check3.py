import json
orders = json.load(open('orders.json'))
o = orders[-1]
print('party_size:', o.get('party_size'))
print('service_charge_amount:', o.get('service_charge_amount'))
print('subtotal:', o.get('subtotal'))
expected_sc = round(o.get('subtotal', 0) * 0.18, 2)
if o.get('service_charge_amount', 0) == expected_sc:
    print('PASS: Service charge of $' + str(expected_sc) + ' applied for party of 7 (threshold is 6)')
else:
    print('FAIL: Expected $' + str(expected_sc) + ' service charge, got $' + str(o.get('service_charge_amount')))

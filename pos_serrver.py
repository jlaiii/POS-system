from http.server import SimpleHTTPRequestHandler, HTTPServer
import json
from datetime import datetime
import random

# File to store logs
LOG_FILE = "transaction_log.txt"

class POSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.order_ids = set()
        super().__init__(*args, **kwargs)

    def generate_order_id(self):
        while True:
            order_id = random.randint(10**4, 10**5 - 1)  # Generate random 5-digit order ID
            if order_id not in self.order_ids:
                self.order_ids.add(order_id)
                return order_id

    def do_POST(self):
        if self.path == '/log':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            # Get current date and time
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H:%M:%S")

            # Calculate total amount
            total_amount = sum(item['count'] * item['price'] for item in data['items'].values())

            # Generate random order ID
            order_id = self.generate_order_id()

            # Log order with date, time, order ID, total amount, and payment method to file
            with open(LOG_FILE, 'a') as log_file:
                log_file.write(f"Order ID: {order_id}, Date: {current_time}, Total Amount: ${total_amount:.2f}, Payment Method: {data['paymentMethod']}, Order: {json.dumps(data['items'])}\n")

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Order logged successfully')
        else:
            super().do_POST()

def run_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, POSRequestHandler)
    print('Starting POS server...')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()

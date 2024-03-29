Point of Sale System

This is a simple Point of Sale (POS) system implemented using a Python HTTP server script. It allows users to add items to a virtual cart, view the total amount, select a payment method (cash or card), and submit the order.
How to Use

    Clone or download the repository.
    Run the Python script pos_http_server.py.
    Open a web browser and navigate to http://localhost:8000.

Features

    Adding Items: Users can add items to the cart by clicking the "Add to Cart" button next to each item.
    Removing Items: Items can be removed from the cart by clicking on them in the cart list.
    Total Amount: The total amount of the items in the cart is dynamically updated as items are added or removed.
    Payment Method: Users can select either "Cash" or "Card" as the payment method.
    Submitting Order: Once items are added to the cart and a payment method is selected, users can submit the order. The order data is sent to the server via a POST request.
    Clearing Cart: Users can clear the cart at any time, removing all items and resetting the total amount and payment method.

Technologies Used

    Python (for the HTTP server)
    HTML/CSS/JavaScript (for the frontend UI)

Code Structure

    HTML: Defines the structure of the POS system and includes buttons for adding items, displaying the cart, selecting payment method, and submitting/clearing the order.
    CSS: Provides basic styling for the UI elements.
    JavaScript: Handles user interactions such as adding/removing items from the cart, updating the total amount, selecting a payment method, submitting orders, and clearing the cart.
    Python HTTP Server Script: Implements the server-side logic for handling HTTP requests, including serving HTML, JavaScript, and processing order submissions.

Note

This POS system is a basic implementation intended for demonstration purposes. It does not include features such as user authentication, persistence (e.g., saving orders to a database), or security measures. It can be extended and enhanced based on specific requirements and use cases.

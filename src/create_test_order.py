import os
import random
from dotenv import load_dotenv
import razorpay

load_dotenv()

client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))

amount = random.choice([49900, 99900, 149900])  # in paise

order = client.order.create({
    "amount": amount,
    "currency": "INR",
    "payment_capture": 1,
})

print("Order created successfully:")
print(f"  Order ID: {order['id']}")
print(f"  Amount: ₹{amount / 100:.2f}")
print("\nUse this Order ID in the checkout HTML page next.")
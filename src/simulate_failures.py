import json
import random
from datetime import datetime, timedelta

# Simulates a batch of failed Razorpay payments, using Razorpay's real
# payment-entity failure fields (error_code, error_reason, error_source, error_step).
# In production this data would come from Razorpay's payment.failed webhook.

FAILURE_TYPES = [
    {
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Your payment could not be completed as the issuing bank declined the transaction due to insufficient funds.",
        "error_reason": "insufficient_funds",
        "error_source": "bank",
        "error_step": "payment_authorization",
    },
    {
        "error_code": "GATEWAY_ERROR",
        "error_description": "The card has expired. Please use a different card.",
        "error_reason": "expired_card",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    {
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "The transaction was declined by the card issuer.",
        "error_reason": "card_declined",
        "error_source": "issuer",
        "error_step": "payment_authorization",
    },
    {
        "error_code": "GATEWAY_ERROR",
        "error_description": "The payment gateway of the issuing bank is currently down.",
        "error_reason": "issuer_unavailable",
        "error_source": "issuer",
        "error_step": "payment_authorization",
    },
    {
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "The OTP entered was incorrect.",
        "error_reason": "incorrect_otp",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    {
        "error_code": "GATEWAY_ERROR",
        "error_description": "This transaction was flagged for suspected fraudulent activity and requires manual review.",
        "error_reason": "suspected_fraud",
        "error_source": "business",
        "error_step": "risk_screening",
    },
]

CUSTOMER_NAMES = ["Aarav Sharma", "Priya Nair", "Rohan Mehta", "Sneha Iyer",
                  "Karan Malhotra", "Divya Reddy", "Arjun Kapoor", "Ishita Sen"]


def generate_failed_payment(index):
    failure = random.choice(FAILURE_TYPES)
    created_at = datetime.now() - timedelta(hours=random.randint(1, 72))
    return {
        "id": f"pay_test{1000 + index}",
        "amount": random.choice([49900, 99900, 149900, 199900, 299900]),  # in paise
        "currency": "INR",
        "status": "failed",
        "method": random.choice(["card", "upi", "netbanking"]),
        "customer_name": random.choice(CUSTOMER_NAMES),
        "customer_email": f"customer{index}@example.com",
        "created_at": created_at.isoformat(),
        **failure,
    }


def main():
    batch_size = 25
    failed_payments = [generate_failed_payment(i) for i in range(batch_size)]

    with open("../data/failed_payments.json", "w") as f:
        json.dump(failed_payments, f, indent=2)

    print(f"Generated {batch_size} simulated failed payments -> failed_payments.json")


if __name__ == "__main__":
    main()
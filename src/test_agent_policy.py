from agent import diagnose_and_recommend
from policy import evaluate

test_cases = [
    {
        "amount": 149900,
        "method": "card",
        "error_reason": "issuer_unavailable",
        "error_description": "The payment gateway of the issuing bank is currently down.",
        "prior_attempts": 0,
    },
    {
        "amount": 49900,
        "method": "card",
        "error_reason": "suspected_fraud",
        "error_description": "This transaction was flagged for suspected fraudulent activity and requires manual review.",
        "prior_attempts": 0,
    },
    {
        "amount": 149900,
        "method": "card",
        "error_reason": "insufficient_funds",
        "error_description": "Your payment could not be completed as the issuing bank declined the transaction due to insufficient funds.",
        "prior_attempts": 3,
    },
]

for payment in test_cases:
    print(f"\n--- {payment['error_reason']} ---")
    ai_result = diagnose_and_recommend(payment)
    print("AI recommendation:", ai_result)
    policy_result = evaluate(payment, ai_result)
    print("Policy decision:", policy_result)
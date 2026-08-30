import json
import os
import random
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()  # loads GEMINI_API_KEY from the .env file at project root

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.5-flash-lite")

MAX_ATTEMPTS = 3  # stopping rule: stop retrying after this many tries

# Maps each failure reason to the right recovery action and a rough
# probability of success per attempt (used only for our simulation —
# in a real system this would come from actual retry outcomes).
ACTION_MAP = {
    "insufficient_funds": {"action": "retry_later", "success_prob": 0.35},
    "card_declined": {"action": "retry_later", "success_prob": 0.30},
    "expired_card": {"action": "request_new_payment_method", "success_prob": 0.55},
    "issuer_unavailable": {"action": "retry_soon", "success_prob": 0.60},
    "incorrect_otp": {"action": "retry_immediately", "success_prob": 0.70},
}

# How far apart retries happen, depending on the action type.
# This reflects real dunning/retry practice — immediate issues (like OTP)
# get retried within minutes, while bank/fund issues need more time to resolve.
RETRY_SPACING = {
    "retry_immediately": timedelta(minutes=5),
    "retry_soon": timedelta(hours=2),
    "retry_later": timedelta(hours=12),
    "request_new_payment_method": timedelta(hours=6),
}


def call_gemini_with_retry(prompt, max_retries=5):
    """Calls Gemini, automatically waiting and retrying if we hit a rate limit."""
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                wait_time = 20  # seconds — safely above the per-minute reset window
                print(f"  Rate limited, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError("Failed after max retries due to rate limiting.")


def generate_recovery_email(payment):
    """Ask Gemini to draft a short recovery email for this failed payment."""
    prompt = f"""Write a short, polite payment recovery email for a customer whose payment failed.

Customer name: {payment['customer_name']}
Amount: ₹{payment['amount'] / 100:.2f}
Failure reason: {payment['error_description']}
Recommended action: {ACTION_MAP[payment['error_reason']]['action']}

Return ONLY valid JSON in this exact format, nothing else:
{{"subject": "...", "body": "..."}}

Keep the body under 80 words. Be warm but concise. Don't be pushy."""

    response = call_gemini_with_retry(prompt)
    text = response.text.strip()

    # Gemini sometimes wraps JSON in markdown code fences — strip those if present
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback if the model doesn't return clean JSON
        return {
            "subject": "We couldn't process your payment",
            "body": f"Hi {payment['customer_name']}, your recent payment of "
                    f"₹{payment['amount'] / 100:.2f} didn't go through. Please try again.",
        }


def simulate_recovery_attempts(payment):
    """Simulate retry attempts up to MAX_ATTEMPTS, spaced realistically, stopping on success."""
    config = ACTION_MAP[payment["error_reason"]]
    spacing = RETRY_SPACING[config["action"]]
    attempts_log = []
    recovered = False

    attempt_time = datetime.now()

    for attempt_num in range(1, MAX_ATTEMPTS + 1):
        success = random.random() < config["success_prob"]
        attempts_log.append({
            "attempt": attempt_num,
            "timestamp": attempt_time.isoformat(),
            "outcome": "recovered" if success else "still_failed",
        })
        if success:
            recovered = True
            break  # stopping rule: don't keep retrying once recovered
        attempt_time += spacing  # schedule next attempt realistically in the future

    return recovered, attempts_log


def main():
    with open("../data/failed_payments.json", "r") as f:
        failed_payments = json.load(f)

    results = []
    recovered_count = 0
    total_amount_recovered = 0

    for payment in failed_payments:
        print(f"Processing {payment['id']} ({payment['error_reason']})...")

        action = ACTION_MAP[payment["error_reason"]]["action"]
        email = generate_recovery_email(payment)
        recovered, attempts_log = simulate_recovery_attempts(payment)

        if recovered:
            recovered_count += 1
            total_amount_recovered += payment["amount"]

        results.append({
            "payment_id": payment["id"],
            "customer_name": payment["customer_name"],
            "amount": payment["amount"],
            "error_reason": payment["error_reason"],
            "action_taken": action,
            "recovery_email": email,
            "attempts": attempts_log,
            "final_status": "recovered" if recovered else "unrecovered",
        })

        time.sleep(4)  # small delay to stay well within free-tier rate limits

    summary = {
        "total_processed": len(failed_payments),
        "recovered_count": recovered_count,
        "recovery_rate_pct": round(recovered_count / len(failed_payments) * 100, 1),
        "total_amount_recovered_rupees": total_amount_recovered / 100,
        "generated_at": datetime.now().isoformat(),
    }

    output = {"summary": summary, "results": results}

    with open("../output/recovery_log.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n--- Summary ---")
    print(f"Processed: {summary['total_processed']}")
    print(f"Recovered: {summary['recovered_count']} ({summary['recovery_rate_pct']}%)")
    print(f"Amount recovered: ₹{summary['total_amount_recovered_rupees']:.2f}")
    print("Full audit trail -> output/recovery_log.json")


if __name__ == "__main__":
    main()
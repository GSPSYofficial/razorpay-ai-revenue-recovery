import json
import os
import random
from datetime import datetime

from dotenv import load_dotenv

from agent import diagnose_and_recommend, call_gemini_with_retry
from policy import evaluate, RETRY_SPACING

load_dotenv()

# Simulation-only: how likely a given failure reason is to resolve if the
# execution layer's chosen action is carried out. This is NOT used by the
# AI or the policy layer to make decisions — it only drives what happens
# in our simulated outcome, since we don't have real gateway responses.
SIMULATED_SUCCESS_PROB = {
    "insufficient_funds": 0.35,
    "card_declined": 0.30,
    "expired_card": 0.55,
    "issuer_unavailable": 0.60,
    "incorrect_otp": 0.70,
    "payment_failed": 0.40,
    "international_transaction_not_allowed": 0.50,
    "suspected_fraud": 0.0,  # never auto-retried; see policy.py
}


def generate_recovery_email(payment, ai_diagnosis, final_action):
    """Ask Gemini to draft a short recovery email, informed by the AI's
    own diagnosis/reasoning so the message reflects the actual decision made."""
    prompt = f"""Write a short, polite payment recovery email for a customer whose payment failed.

Customer name: {payment['customer_name']}
Amount: ₹{payment['amount'] / 100:.2f}
Failure reason: {payment['error_description']}
Diagnosis: {ai_diagnosis['diagnosis']}
Action being taken: {final_action}

Return ONLY valid JSON in this exact format, nothing else:
{{"subject": "...", "body": "..."}}

Keep the body under 80 words. Be warm but concise. Don't be pushy."""

    response = call_gemini_with_retry(prompt)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "subject": "We couldn't process your payment",
            "body": f"Hi {payment['customer_name']}, your recent payment of "
                    f"₹{payment['amount'] / 100:.2f} didn't go through. Please try again.",
        }


def execute_recovery(payment, policy_decision):
    """
    Deterministically executes the strategy the policy layer approved.
    Returns (final_status, attempts_log, escalation_reason_or_None).
    This is where 'observe result, decide recovered/retry/escalate/stop'
    actually happens — no further AI calls here, by design.
    """
    final_action = policy_decision["final_action"]
    max_attempts = policy_decision["max_attempts"]

    if final_action == "escalate_to_human":
        reason = "; ".join(policy_decision["policy_notes"]) or "Escalated at initial diagnosis."
        return "escalated", [], reason

    if final_action == "no_action":
        return "no_action", [], None

    # Remaining actions (retry_immediately, retry_soon, retry_later,
    # request_new_payment_method) all execute as a bounded retry loop.
    spacing = RETRY_SPACING[final_action]
    success_prob = SIMULATED_SUCCESS_PROB.get(payment["error_reason"], 0.3)
    attempts_log = []
    attempt_time = datetime.now()

    for attempt_num in range(1, max_attempts + 1):
        success = random.random() < success_prob
        attempts_log.append({
            "attempt": attempt_num,
            "timestamp": attempt_time.isoformat(),
            "outcome": "recovered" if success else "still_failed",
        })
        if success:
            return "recovered", attempts_log, None
        attempt_time += spacing

    # Attempts exhausted without success — stop automated recovery, escalate.
    return "escalated", attempts_log, f"Retries exhausted ({max_attempts} attempts) without recovery."


def process_payment(payment):
    """Runs one payment through the full agent → policy → execution pipeline."""
    ai_diagnosis = diagnose_and_recommend(payment)
    policy_decision = evaluate(payment, ai_diagnosis)

    final_status, attempts_log, escalation_reason = execute_recovery(payment, policy_decision)

    # Skip customer email for escalation cases with no attempts (e.g. fraud) —
    # sending a "please retry" email during a fraud review would be wrong.
    email = None
    if policy_decision["final_action"] not in ("escalate_to_human", "no_action"):
        email = generate_recovery_email(payment, ai_diagnosis, policy_decision["final_action"])

    return {
        "payment_id": payment["id"],
        "customer_name": payment["customer_name"],
        "amount": payment["amount"],
        "error_reason": payment["error_reason"],
        "data_source": payment.get("data_source", "simulated"),
        "ai_diagnosis": ai_diagnosis,
        "policy_decision": policy_decision,
        "recovery_email": email,
        "attempts": attempts_log,
        "final_status": final_status,
        "escalation_reason": escalation_reason,
    }


def main():
    with open("../data/failed_payments.json", "r") as f:
        simulated_payments = json.load(f)
        for p in simulated_payments:
            p["data_source"] = "simulated"

    try:
        with open("../data/real_failed_payments.json", "r") as f:
            real_payments = json.load(f)
    except FileNotFoundError:
        real_payments = []

    failed_payments = real_payments + simulated_payments

    results = []
    recovered_count = 0
    escalated_count = 0
    no_action_count = 0
    total_amount_recovered = 0

    for payment in failed_payments:
        print(f"Processing {payment['id']} ({payment['error_reason']})...")
        result = process_payment(payment)
        results.append(result)

        if result["final_status"] == "recovered":
            recovered_count += 1
            total_amount_recovered += payment["amount"]
        elif result["final_status"] == "escalated":
            escalated_count += 1
        elif result["final_status"] == "no_action":
            no_action_count += 1

    summary = {
        "total_processed": len(failed_payments),
        "recovered_count": recovered_count,
        "escalated_count": escalated_count,
        "no_action_count": no_action_count,
        "unrecovered_other_count": len(failed_payments) - recovered_count - escalated_count - no_action_count,
        "recovery_rate_pct": round(recovered_count / len(failed_payments) * 100, 1),
        "total_amount_recovered_rupees": total_amount_recovered / 100,
        "generated_at": datetime.now().isoformat(),
        "note": "Recovery outcomes are simulated (SIMULATED_SUCCESS_PROB), "
                "not observed from real gateway responses.",
    }

    escalation_queue = [
        {
            "payment_id": r["payment_id"],
            "customer_name": r["customer_name"],
            "amount": r["amount"],
            "error_reason": r["error_reason"],
            "ai_diagnosis": r["ai_diagnosis"]["diagnosis"],
            "escalation_reason": r["escalation_reason"],
            "attempts_made": len(r["attempts"]),
        }
        for r in results if r["final_status"] == "escalated"
    ]

    with open("../output/escalation_queue.json", "w") as f:
        json.dump(escalation_queue, f, indent=2)

    output = {"summary": summary, "results": results}

    with open("../output/recovery_log.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n--- Summary ---")
    print(f"Processed: {summary['total_processed']}")
    print(f"Recovered: {summary['recovered_count']} ({summary['recovery_rate_pct']}%)")
    print(f"Escalated: {summary['escalated_count']}")
    print(f"No action: {summary['no_action_count']}")
    print(f"Amount recovered: ₹{summary['total_amount_recovered_rupees']:.2f}")
    print("Full audit trail -> output/recovery_log.json")


if __name__ == "__main__":
    main()
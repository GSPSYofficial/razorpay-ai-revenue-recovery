import json
import random

random.seed(42)

# GROUND TRUTH for actions that retry the SAME payment method.
GROUND_TRUTH_SUCCESS_PROB = {
    ("insufficient_funds", "retry_later"): 0.35,
    ("insufficient_funds", "retry_soon"): 0.15,
    ("insufficient_funds", "retry_immediately"): 0.05,
    ("card_declined", "retry_later"): 0.30,
    ("expired_card", "retry_later"): 0.02,
    ("issuer_unavailable", "retry_soon"): 0.60,
    ("issuer_unavailable", "retry_later"): 0.50,
    ("incorrect_otp", "retry_immediately"): 0.70,
    ("incorrect_otp", "retry_later"): 0.40,
    ("payment_failed", "retry_later"): 0.40,
    ("international_transaction_not_allowed", "retry_later"): 0.02,
    ("suspected_fraud", "retry_later"): 0.0,
}
DEFAULT_PROB = 0.1

# GROUND TRUTH for the request_new_payment_method workflow: independent of
# retry probabilities, since it's a genuinely different action.
GROUND_TRUTH_CUSTOMER_UPDATE_PROB = 0.45
GROUND_TRUTH_NEW_METHOD_SUCCESS_PROB = 0.85


def simulate_outcome(error_reason, action, max_attempts):
    """Applies the ground-truth model to decide if a given action recovers
    the payment, within max_attempts. Returns (success: bool, attempts_used: int)."""
    if action in ("escalate_to_human", "no_action"):
        return False, 0

    if action == "request_new_payment_method":
        for attempt in range(1, max_attempts + 1):
            if random.random() < GROUND_TRUTH_CUSTOMER_UPDATE_PROB:
                if random.random() < GROUND_TRUTH_NEW_METHOD_SUCCESS_PROB:
                    return True, attempt
                return False, attempt  # customer updated, but payment still failed
        return False, max_attempts

    prob = GROUND_TRUTH_SUCCESS_PROB.get((error_reason, action), DEFAULT_PROB)
    for attempt in range(1, max_attempts + 1):
        if random.random() < prob:
            return True, attempt
    return False, max_attempts


def main():
    with open("../data/failed_payments.json", "r") as f:
        simulated = json.load(f)
    try:
        with open("../data/real_failed_payments.json", "r") as f:
            real = json.load(f)
    except FileNotFoundError:
        real = []
    all_payments = {p["id"]: p for p in (real + simulated)}

    with open("../output/recovery_log.json", "r") as f:
        agent_log = json.load(f)

    baseline_recovered_amount = 0
    baseline_recovered_count = 0
    baseline_total_attempts = 0

    agent_recovered_amount = 0
    agent_recovered_count = 0
    agent_total_attempts = 0

    for result in agent_log["results"]:
        payment_id = result["payment_id"]
        payment = all_payments[payment_id]
        reason = payment["error_reason"]
        amount = payment["amount"]

        baseline_success, baseline_attempts = simulate_outcome(reason, "retry_later", 3)
        baseline_total_attempts += baseline_attempts
        if baseline_success:
            baseline_recovered_amount += amount
            baseline_recovered_count += 1

        agent_action = result["policy_decision"]["final_action"]
        agent_max_attempts = result["policy_decision"]["max_attempts"]
        agent_success, agent_attempts = simulate_outcome(reason, agent_action, agent_max_attempts)
        agent_total_attempts += agent_attempts
        if agent_success:
            agent_recovered_amount += amount
            agent_recovered_count += 1

    total_payments = len(agent_log["results"])
    total_amount_at_risk = sum(p["amount"] for p in all_payments.values())

    print("=== EVALUATION (ground-truth model, fixed seed=42) ===")
    print(f"Total payments: {total_payments}")
    print(f"Total amount at risk: ₹{total_amount_at_risk / 100:.2f}\n")

    print(f"Baseline (naive retry_later for everyone):")
    print(f"  Recovered: {baseline_recovered_count}/{total_payments}")
    print(f"  Amount recovered: ₹{baseline_recovered_amount / 100:.2f}")
    print(f"  Total retry attempts used: {baseline_total_attempts}\n")

    print(f"Agent (AI diagnosis + policy-bounded action):")
    print(f"  Recovered: {agent_recovered_count}/{total_payments}")
    print(f"  Amount recovered: ₹{agent_recovered_amount / 100:.2f}")
    print(f"  Total retry attempts used: {agent_total_attempts}\n")

    lift = agent_recovered_amount - baseline_recovered_amount
    print(f"Amount lift: ₹{lift / 100:.2f} ({'+' if lift >= 0 else ''}{lift / max(baseline_recovered_amount,1) * 100:.1f}% vs baseline)")

    attempt_diff = agent_total_attempts - baseline_total_attempts
    print(f"Attempt difference: {attempt_diff} ({'+' if attempt_diff >= 0 else ''}{attempt_diff / max(baseline_total_attempts,1) * 100:.1f}% vs baseline)")


if __name__ == "__main__":
    main()
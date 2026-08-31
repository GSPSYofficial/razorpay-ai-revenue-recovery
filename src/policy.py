from datetime import timedelta

LOW_VALUE_THRESHOLD = 99900  # ₹999.00, in paise
DEFAULT_MAX_ATTEMPTS = 3

RETRY_SPACING = {
    "retry_immediately": timedelta(minutes=5),
    "retry_soon": timedelta(hours=2),
    "retry_later": timedelta(hours=12),
    "request_new_payment_method": timedelta(hours=6),
}

# Failure reasons where retrying the same payment method is pointless —
# the AI is not trusted to override this on its own.
NO_RETRY_REASONS = {
    "expired_card",
    "international_transaction_not_allowed",
}

# Failure reasons treated as high-risk: automated retry is never permitted,
# no matter what the AI recommends. Deliberate, demonstrable policy override.
FORCE_ESCALATE_REASONS = {
    "suspected_fraud",
}


def evaluate(payment, ai_recommendation):
    """
    Deterministic safety/policy gate. The AI proposes an action; this
    function decides what the system is actually allowed to do. Every
    override is recorded so the audit trail shows exactly where and why
    policy diverged from the AI's recommendation.
    """
    notes = []
    proposed_action = ai_recommendation["recommended_action"]
    final_action = proposed_action
    reason = payment["error_reason"]
    amount = payment["amount"]
    prior_attempts = payment.get("prior_attempts", 0)

    if reason in FORCE_ESCALATE_REASONS:
        if final_action != "escalate_to_human":
            notes.append(
                f"Overrode AI recommendation '{proposed_action}': "
                f"'{reason}' is high-risk and always escalates."
            )
        final_action = "escalate_to_human"

    elif reason in NO_RETRY_REASONS and final_action.startswith("retry"):
        notes.append(
            f"Overrode AI recommendation '{proposed_action}': retrying isn't "
            f"viable for reason '{reason}'; redirected to request_new_payment_method."
        )
        final_action = "request_new_payment_method"

    if final_action.startswith("retry") and prior_attempts >= DEFAULT_MAX_ATTEMPTS:
        notes.append(
            f"Overrode AI recommendation '{proposed_action}': attempts already "
            f"exhausted ({prior_attempts}); escalating."
        )
        final_action = "escalate_to_human"

    if amount < LOW_VALUE_THRESHOLD:
        max_attempts = 1
        if final_action.startswith("retry"):
            notes.append("Low-value payment (<₹999): retry cap reduced to 1 attempt.")
    else:
        max_attempts = DEFAULT_MAX_ATTEMPTS

    return {
        "proposed_action": proposed_action,
        "final_action": final_action,
        "max_attempts": max_attempts,
        "policy_notes": notes,
        "was_overridden": final_action != proposed_action,
    }
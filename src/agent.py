import json
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.1-flash-lite")

ALLOWED_ACTIONS = [
    "retry_immediately",
    "retry_soon",
    "retry_later",
    "request_new_payment_method",
    "escalate_to_human",
    "no_action",
]


def call_gemini_with_retry(prompt, max_retries=5):
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                print("  Rate limited, waiting 20s before retry...")
                time.sleep(20)
            else:
                raise
    raise RuntimeError("Failed after max retries due to rate limiting.")


def diagnose_and_recommend(payment):
    """
    Ask Gemini to diagnose the failure and recommend ONE recovery action.
    This is where the AI actually makes a judgment call — the action is not
    decided in advance. policy.py reviews this recommendation afterward and
    can override it; this function only proposes.
    """
    prompt = f"""You are a payment recovery assistant. A payment has failed.
Diagnose the situation and recommend ONE recovery action.

Payment context:
- Amount: ₹{payment['amount'] / 100:.2f}
- Payment method: {payment.get('method', 'unknown')}
- Failure reason code: {payment['error_reason']}
- Failure description: {payment['error_description']}

Allowed actions (choose exactly one):
- retry_immediately: safe to retry within minutes (e.g. transient auth issues)
- retry_soon: retry within a couple of hours (e.g. temporary bank-side issue)
- retry_later: retry after a longer wait (e.g. funds/decline issues needing time)
- request_new_payment_method: retrying the same method won't help (e.g. expired/unsupported card)
- escalate_to_human: automated recovery is not appropriate or has been exhausted
- no_action: no further action is warranted

Return ONLY valid JSON in this exact format, nothing else:
{{"diagnosis": "one sentence on what actually happened", "recommended_action": "one of the allowed actions above", "confidence": 0.0 to 1.0, "reasoning": "one sentence on why this action"}}"""

    response = call_gemini_with_retry(prompt)
    text = response.text.strip().replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
        if result.get("recommended_action") not in ALLOWED_ACTIONS:
            raise ValueError("model returned an action outside the allowed set")
        return result
    except (json.JSONDecodeError, ValueError, KeyError):
        # Fail safe: if the model's output can't be trusted, don't guess —
        # hand it to a human rather than silently picking an action.
        return {
            "diagnosis": "Could not reliably parse AI diagnosis.",
            "recommended_action": "escalate_to_human",
            "confidence": 0.0,
            "reasoning": "Fallback: AI output was invalid or malformed.",
        }
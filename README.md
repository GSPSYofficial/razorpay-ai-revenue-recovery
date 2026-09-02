# AI Revenue Recovery — Bounded AI Agent for Failed Payment Recovery

Built for the Razorpay Buildathon (AI Revenue Recovery track).

## Problem

Businesses lose meaningful revenue every day to failed payments — card declines,
expired cards, insufficient funds, unavailable issuer banks, incorrect OTPs, and
suspected fraud. Not every failure should be handled the same way: retrying an
expired card is nearly pointless, while a temporary bank outage often resolves
itself within hours. Deciding the *right* response, safely and explainably, is
the actual problem — not just detecting that something failed.

## Objective

This prototype is a small, bounded AI agent that closes the loop from detecting
a failed payment to a final, auditable outcome:

1. **Detect** — a failed payment comes in, either from Razorpay's real test-mode
   API or a realistic simulated batch
2. **Diagnose & recommend** — an LLM (Gemini) reasons about the specific failure
   and proposes one recovery action, from a fixed, constrained vocabulary
3. **Govern** — a deterministic policy layer reviews the AI's recommendation.
   It can approve it, override it, or force escalation — and always logs why
4. **Execute** — the approved action runs as a bounded, realistically-spaced
   retry sequence (or an immediate escalation, if that's what policy decided)
5. **Resolve** — each payment ends in exactly one outcome: recovered, escalated,
   or no action taken
6. **Audit** — every step of this chain is recorded per payment: what the AI
   saw, what it recommended, what policy decided (and why, if overridden),
   what was executed, and the final result

## Why the AI proposes and policy decides

Early in development, the recovery action was chosen entirely by a hard-coded
lookup table, and the LLM was only used to write the follow-up email. That's a
rules-based pipeline with a language-generation layer on top — not an agent
that actually participates in the decision.

This version inverts that: **the AI diagnoses the failure and recommends an
action with its own reasoning. A separate, deterministic policy layer decides
what the system is actually allowed to do.** The AI cannot execute anything on
its own, and it never sees prior-attempt history — retry-count enforcement is
policy's responsibility alone, not something the AI can reason its way around.
This makes the safety boundary meaningful and testable, rather than something
the AI could quietly talk itself past.

Two situations are deliberately hard-coded to always force escalation,
regardless of what the AI recommends:
- `suspected_fraud` — never auto-retried
- Any payment where retry attempts are already exhausted (enforced by policy,
  independent of the AI's recommendation)

Every policy override is logged with the AI's original proposal, the final
action taken, and the specific reason for the override — this is directly
visible per-payment in `output/recovery_log.json` via `was_overridden` and
`policy_notes`.

## What makes this more than a synthetic demo

- **Real Razorpay API integration.** A subset of the failed payments in this
  pipeline come from actually creating a live test-mode Order via Razorpay's
  Orders API, running it through Razorpay's real hosted checkout, and
  triggering a genuine failure response on their mock bank page. The payment
  IDs, order IDs, and error payloads in `data/real_failed_payments.json` are
  real responses from Razorpay's own system, not authored by this project.
  (`src/create_test_order.py` + `src/checkout_test.html`)

- **A provable safety boundary, not just a claimed one.** `src/test_agent_policy.py`
  demonstrates a clean, reproducible case where the AI recommends continuing
  to retry a payment, and the policy layer catches that retries are already
  exhausted and overrides it to escalation. This isn't cherry-picked — it
  reproduces reliably on every run, and the same override mechanism fires on
  the full batch (see `output/recovery_log.json`, `was_overridden: true`).

- **Cost-aware retry logic.** Low-value payments (below ₹999) are capped at a
  single retry attempt, since the operational cost of repeated follow-ups can
  outweigh the amount recovered. This cap is enforced by policy, visible
  per-payment as `retry_cap_applied`.

## Evaluation methodology

Recovery outcomes throughout this project are simulated — there is no real
gateway outcome data available in a test-mode sandbox. To make any recovery
rate or ₹-recovered figure meaningful rather than arbitrary, `src/evaluate.py`
scores the agent's actual recorded decisions (from `recovery_log.json`)
against a **fixed, independently-defined ground-truth success model**
(`GROUND_TRUTH_SUCCESS_PROB` in `evaluate.py`), created before looking at any
evaluation results, and applied identically to both the agent and a baseline.

**Baseline:** a naive strategy that applies `retry_later` with 3 attempts to
every payment, with no diagnosis at all — representing a system with no
intelligence in the loop.

**Agent:** whatever action and attempt cap the AI + policy layer actually
chose for that payment.

Both are scored against the same ground-truth model, with a fixed random seed
for reproducibility.

### Result (batch of 62 payments, fixed seed)

| | Recovered | Amount recovered | Retry attempts used |
|---|---|---|---|
| Baseline (naive retry) | 34/62 | ₹52,466 | 130 |
| Agent (AI + policy) | 40/62 | ₹65,960 | 74 |
| **Difference** | **+6** | **+₹13,494 (+25.7%)** | **-56 (-43.1%)** |

The agent recovered more payments and more total revenue than the naive
baseline, while using under half the retry attempts — reflecting that it
correctly avoids wasting retries on cases where retrying the same method
won't help (e.g. an expired card), and reserves attempts for cases where
retrying is actually likely to succeed.

**Honest caveat:** this is a single simulated batch scored against a
ground-truth model we defined ourselves, not observed real-world outcomes.
An earlier, smaller batch (27 payments) showed a noisier, less favorable
result on the ₹-recovered metric specifically — the attempt-efficiency gain
was consistent across both batch sizes, since it follows directly from the
policy design rather than from chance.

## Architecture

failed payment (real Razorpay API response OR simulated, same schema)
│
▼
agent.py: Gemini diagnoses the failure and recommends ONE action
from a fixed vocabulary, with reasoning. Never sees prior-attempt
history. Fails safe (escalate_to_human) if output is invalid.
│
▼
policy.py: deterministic review of the AI's recommendation

can approve, override, or force escalation
enforces retry-attempt caps (cost-aware, based on amount)
always logs proposed vs. final action and why
│
▼
execute_recovery(): runs the approved action
retry actions: staggered, realistically-spaced attempts
escalate_to_human: stops immediately, logs reason
no_action: stops immediately
│
▼
outcome: recovered / escalated / no_action
│
▼
audit log (output/recovery_log.json)
per-payment: AI diagnosis, policy decision (+ override notes),
action executed, every attempt + timestamp, final outcome
summary: recovery rate, total amount recovered, escalation count
escalation queue (output/escalation_queue.json)
just the cases needing human review, with reason and diagnosis


## Allowed agent actions

| Action | Meaning | Retry spacing (if applicable) |
|---|---|---|
| `retry_immediately` | Safe to retry within minutes | 5 minutes |
| `retry_soon` | Retry within a couple of hours | 2 hours |
| `retry_later` | Retry after a longer wait | 12 hours |
| `request_new_payment_method` | Retrying the same method won't help | 6 hours |
| `escalate_to_human` | Automated recovery isn't appropriate or is exhausted | — |
| `no_action` | No further action warranted | — |

The AI must choose exactly one of these — any invalid or unparseable output
from the model causes an automatic fail-safe to `escalate_to_human`, never a
guess.

## Tech stack

- Python 3
- Google Gemini API (`gemini-3.5-flash-lite`, free tier) — diagnosis, action
  recommendation, and recovery email generation
- Razorpay Python SDK + real test-mode Orders API — genuine failure capture
- Razorpay Checkout.js — hosted checkout used to trigger real failure responses

## How to run

```bash
python -m venv venv
source venv/bin/activate      # Windows: .\venv\Scripts\Activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
GEMINI_API_KEY=your_gemini_key


Run the full pipeline:
```bash
cd src
python simulate_failures.py       # generates a fresh simulated batch
python diagnose_and_recover.py    # runs the full agent -> policy -> execution loop
python verify_log.py              # sanity-checks the output (recommended after every run)
python evaluate.py                # scores agent vs. baseline against ground truth
```

To verify the policy override mechanism directly, in isolation:
```bash
python test_agent_policy.py
```

To look up any single payment's full decision chain without opening the whole log:
```bash
python find_payment.py <payment_id>
```

To capture a fresh real failure via Razorpay's actual checkout flow:
```bash
python create_test_order.py        # creates a real test-mode order
cd ..
python -m http.server 8000
# open http://localhost:8000/src/checkout_test.html in a browser,
# use a Razorpay test card, and click "Failure" on the mock bank page
```

Output: `data/failed_payments.json` (simulated batch), `output/recovery_log.json`
(full audit trail + summary), `output/escalation_queue.json` (cases needing
human review).

## Current scope & honest limitations

- Most failed-payment data is simulated (using Razorpay's documented
  payment-entity error fields), supplemented by a small number of genuinely
  captured real failures from Razorpay's test-mode checkout.
- Recovery emails are generated but not actually sent (simulated send).
- Retry success/failure and evaluation outcomes are simulated via a
  ground-truth probability model, not observed from real gateway responses.
- The AI diagnoses once per payment and does not re-consult on each retry
  attempt — retry execution and outcome-checking are deterministic after the
  initial diagnosis. This is a deliberate choice: re-calling the LLM on every
  retry attempt would be wasteful and harder to bound/explain, not an
  oversight.
- The `confidence` field returned by the AI is the model's own self-reported
  assessment, included as part of its reasoning output — it is not a
  statistically calibrated probability.
- Cost-aware retry logic uses a single fixed ₹999 threshold; a production
  version would likely tune this dynamically.

## Planned next steps

- Capture a larger and more varied sample of real failures across more
  documented Razorpay error scenarios
- Simple dashboard visualizing recovery rate, escalation reasons, and
  agent-vs-baseline comparison
- Explore whether the ground-truth evaluation model itself could be
  calibrated against any available real-world benchmarks, rather than
  hand-estimated
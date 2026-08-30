# AI Revenue Recovery — Payment Failure Recovery Pipeline

Built for the Razorpay Buildathon (AI Revenue Recovery track).

## Problem

Businesses lose meaningful revenue every day to failed payments — card declines,
expired cards, insufficient funds, unavailable issuer banks, incorrect OTPs.
Most of these failures are recoverable if addressed quickly and correctly, but
manually diagnosing each failure and writing a tailored follow-up doesn't scale.

## Objective

This prototype automates the failed-payment recovery loop end-to-end:

1. **Detect** — a failed payment comes in, either from Razorpay's real test-mode
   API or a realistic simulated batch
2. **Diagnose** — classify the failure reason and decide the correct recovery action
3. **Recover** — generate a personalized recovery email via an LLM (Gemini) and
   simulate a realistic, staggered retry schedule
4. **Stop** — enforce a cost-aware retry cap per payment (no blanket retry policy,
   and no infinite retry loops)
5. **Audit** — log every decision, message, and attempt outcome for review

The goal was a small, fully working, explainable pipeline — not a broad but
shallow feature set.

## What makes this more than a synthetic demo

- **Real Razorpay API integration.** A subset of the failed payments in this
  pipeline are not invented — they come from actually creating a live test-mode
  Order via Razorpay's Orders API, running it through Razorpay's real hosted
  checkout, and triggering a genuine failure response on their mock bank page.
  The payment IDs, order IDs, and error payloads in `data/real_failed_payments.json`
  are real responses from Razorpay's own system, not authored by this project.
  (`src/create_test_order.py` + `src/checkout_test.html`)

- **Cost-aware retry logic.** Rather than a fixed retry count for every failure,
  the system caps retries based on transaction value — low-value payments
  (below ₹999) get a single attempt, since the cost of repeated follow-ups
  (customer friction, support overhead) can outweigh the amount recovered.
  Higher-value payments get the full retry sequence. This is visible per-payment
  in the audit trail via `retry_cap_applied`.

## Architecture

failed payment (real Razorpay API response OR simulated, same schema)
│
▼
classify error_reason ──► map to recovery action + retry spacing
│
▼
Gemini generates personalized recovery email (subject + body)
│
▼
simulate staggered retry attempts

cost-aware cap: 1 attempt if amount < ₹999, else 3
spacing depends on action type
stops immediately once recovered
│
▼
audit log (output/recovery_log.json)
per-payment: action taken, retry cap applied, email sent,
every attempt + timestamp, final status, data source (real vs simulated)
summary: recovery rate %, total amount recovered

## Action mapping

| Failure reason                          | Action                      | Retry spacing |
|-------------------------------------------|------------------------------|----------------|
| `insufficient_funds`                      | retry_later                  | 12 hours       |
| `card_declined`                           | retry_later                  | 12 hours       |
| `expired_card`                            | request_new_payment_method   | 6 hours        |
| `issuer_unavailable`                      | retry_soon                   | 2 hours        |
| `incorrect_otp`                           | retry_immediately            | 5 minutes      |
| `payment_failed`                          | retry_later                  | 12 hours       |
| `international_transaction_not_allowed`   | request_new_payment_method   | 6 hours        |

*(The last two reasons were discovered from real Razorpay API responses during testing.)*

## Sample results (batch of 25 simulated + 2 real failed payments)

- **Recovery rate:** 74–92% across test runs
- **Amount recovered:** ₹35,000–₹45,000 per batch
- Full per-payment audit trail in `output/recovery_log.json`

## Tech stack

- Python 3
- Google Gemini API (`gemini-3.5-flash-lite`, free tier) — recovery email generation
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


Run the full pipeline (simulated batch + existing real captures):
```bash
cd src
python diagnose_and_recover.py
```

To capture a fresh real failure via Razorpay's actual checkout flow:
```bash
python create_test_order.py        # creates a real test-mode order
# then, from the project root:
python -m http.server 8000
# open http://localhost:8000/src/checkout_test.html in a browser,
# use a Razorpay test card, and click "Failure" on the mock bank page
```

Output: `data/failed_payments.json` (simulated batch) and
`output/recovery_log.json` (full audit trail + summary).

## Current scope & honest limitations

- The majority of failed-payment data is still simulated (using Razorpay's
  documented payment-entity error fields), supplemented by a small number of
  genuinely captured real failures.
- Recovery emails are generated but not actually sent (simulated send).
- Retry success/failure is simulated via probability, not real gateway responses.
- Cost-aware retry logic currently uses a single fixed threshold (₹999);
  a production version would likely tune this dynamically.

## Planned next steps

- Capture a larger and more varied sample of real failures across more
  documented error scenarios
- Simple dashboard visualizing recovery rate and funnel by failure type,
  and by real vs. simulated source
- Explore whether retry probability itself should be informed by
  historical recovery data rather than fixed estimates
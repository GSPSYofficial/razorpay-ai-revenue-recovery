# AI Revenue Recovery — Payment Failure Recovery Pipeline

Built for the Razorpay Buildathon (AI Revenue Recovery track).

## Problem

Businesses lose meaningful revenue every day to failed payments — card declines,
expired cards, insufficient funds, unavailable issuer banks, incorrect OTPs.
Most of these failures are recoverable if addressed quickly and correctly, but
manually diagnosing each failure and writing a tailored follow-up doesn't scale.

## Objective

This prototype automates the failed-payment recovery loop end-to-end:

1. **Detect** — a failed payment comes in (Razorpay payment-entity structure)
2. **Diagnose** — classify the failure reason and decide the correct recovery action
3. **Recover** — generate a personalized recovery email via an LLM (Gemini) and
   simulate a realistic, staggered retry schedule
4. **Stop** — enforce a maximum retry limit per payment (no infinite retry loops)
5. **Audit** — log every decision, message, and attempt outcome for review

The goal was a small, fully working, explainable pipeline — not a broad but
shallow feature set.

## Architecture

failed payment (Razorpay payment entity fields)
│
▼
classify error_reason ──► map to recovery action + retry spacing
│
▼
Gemini generates personalized recovery email (subject + body)
│
▼
simulate staggered retry attempts (spacing depends on action type)

stops immediately once recovered
hard cap at 3 attempts
│
▼
audit log (output/recovery_log.json)
per-payment: action taken, email sent, every attempt + timestamp, final status
summary: recovery rate %, total amount recovered


## Action mapping

| Failure reason        | Action                      | Retry spacing |
|------------------------|------------------------------|----------------|
| `insufficient_funds`   | retry_later                  | 12 hours       |
| `card_declined`        | retry_later                  | 12 hours       |
| `expired_card`         | request_new_payment_method   | 6 hours        |
| `issuer_unavailable`   | retry_soon                   | 2 hours        |
| `incorrect_otp`        | retry_immediately             | 5 minutes      |

## Sample results (from a run of 25 simulated failed payments)

- **Recovery rate:** 80–92% across test runs
- **Amount recovered:** ₹30,000–₹42,000 per batch
- Full per-payment audit trail in `output/recovery_log.json`

## Tech stack

- Python 3
- Google Gemini API (`gemini-3.5-flash-lite`, free tier) — recovery email generation
- Razorpay payment-entity field structure (for realistic failure simulation)

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


Then run the full pipeline:
```bash
cd src
python run_pipeline.py
```

Output: `data/failed_payments.json` (simulated batch) and
`output/recovery_log.json` (full audit trail + summary).

## Current scope & honest limitations

- Failed-payment data is currently simulated using Razorpay's real
  payment-entity error fields (`error_code`, `error_reason`, `error_source`,
  `error_step`) rather than pulled from live webhook traffic.
- Recovery emails are generated but not actually sent (simulated send).
- Retry success/failure is simulated via probability, not real gateway responses.

## Planned next steps

- Trigger real failures via Razorpay's test-mode API using documented test
  card numbers, rather than fully synthetic data
- Add a cost-aware decision layer (e.g., cap retries for low-value transactions
  where the cost of repeated attempts may outweigh recovery value)
- Simple dashboard visualizing recovery rate and funnel by failure type
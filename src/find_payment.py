import json
import sys

payment_id = sys.argv[1]

with open("../output/recovery_log.json", "r") as f:
    log = json.load(f)

for r in log["results"]:
    if r["payment_id"] == payment_id:
        print("AI recommended:", r["ai_diagnosis"]["recommended_action"])
        print("Policy final action:", r["policy_decision"]["final_action"])
        print("Was overridden:", r["policy_decision"]["was_overridden"])
        print("Policy notes:", r["policy_decision"]["policy_notes"])
        break
else:
    print("Payment ID not found in recovery_log.json.")

# Also check the raw source data directly
with open("../data/failed_payments.json", "r") as f:
    payments = json.load(f)

for p in payments:
    if p["id"] == payment_id:
        print("\nRaw payment data prior_attempts:", p.get("prior_attempts", "MISSING"))
        break
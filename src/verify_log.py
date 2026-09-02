import json

with open("../output/recovery_log.json", "r") as f:
    log = json.load(f)

results = log["results"]
summary = log["summary"]

print("=== SUMMARY ===")
print(summary)

print("\n=== CHECKS ===")

# Every result should have all the expected fields
required_fields = {"ai_diagnosis", "policy_decision", "final_status", "attempts"}
missing = [r["payment_id"] for r in results if not required_fields.issubset(r.keys())]
print(f"Entries missing required fields: {len(missing)}")

# At least one override should exist somewhere in the batch
overrides = [r for r in results if r["policy_decision"]["was_overridden"]]
print(f"Policy overrides found: {len(overrides)}")
if overrides:
    print(f"  Example: {overrides[0]['payment_id']} -> {overrides[0]['policy_decision']['policy_notes']}")

# Escalations should have a reason
escalated = [r for r in results if r["final_status"] == "escalated"]
bad_escalations = [r["payment_id"] for r in escalated if not r.get("escalation_reason")]
print(f"Escalated: {len(escalated)}, missing reason: {len(bad_escalations)}")

# Recovered count should match summary
actual_recovered = len([r for r in results if r["final_status"] == "recovered"])
print(f"Recovered count matches summary: {actual_recovered == summary['recovered_count']}")

print("\n=== DONE ===")
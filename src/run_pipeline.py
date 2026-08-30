import subprocess
import sys

def run_step(script_name, description):
    print(f"\n{'='*50}")
    print(f"STEP: {description}")
    print('='*50)
    result = subprocess.run([sys.executable, script_name])
    if result.returncode != 0:
        print(f"\n❌ {script_name} failed. Stopping pipeline.")
        sys.exit(1)

if __name__ == "__main__":
    run_step("simulate_failures.py", "Simulating failed payments")
    run_step("diagnose_and_recover.py", "Diagnosing failures and running recovery")
    print(f"\n{'='*50}")
    print("✅ Pipeline complete. Check ../output/recovery_log.json")
    print('='*50)
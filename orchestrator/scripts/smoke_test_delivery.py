#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import ROOT, JOBS_DIR, write_json, timestamp, prompt_confirm

def run_smoke_delivery():
    print("🚀 Starting Smoke Test: Build & Delivery Pipeline...")
    
    # 1. Setup metadata
    test_id = f"smoke-delivery-{timestamp()}"
    # Just use current branch, don't change anything
    branch_output = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT)).decode("utf-8").strip()
    branch = branch_output
    job_file = JOBS_DIR / f"{test_id}.json"
    
    print(f"      - Test ID: {test_id}")
    print(f"      - Current Branch: {branch}")

    try:
        # 2. Create Mock Job JSON
        job_data = {
            "job_id": test_id,
            "title": "Smoke Test Delivery",
            "status": "review-needed",
            "branch": branch,
            "issue_number": 9999,
            "builder": "gemini",
            "reviewer": "gemini",
            "planner": "gemini",
            "testers": "enmeskin@gmail.com",
            "groups": "internal-testers"
        }
        write_json(job_file, job_data)
        print(f"      - Created mock job: {job_file.name}")

        # 3. Trigger Actual Delivery
        print("\n🔥 TRIGGERING ACTUAL BUILD AND DELIVERY...")
        print("      - This will use your real Firebase and Xcode configuration.")
        print("      - Expect this to take 5-10 minutes.")
        
        deliver_script = SCRIPTS_DIR / "deliver_build.py"
        # We pass the job file to deliver_build.py and stream output directly
        # We add --testers override to ensure it goes directly to the user
        res = subprocess.call([sys.executable, str(deliver_script), str(job_file)], cwd=str(ROOT), stdout=sys.stdout, stderr=sys.stderr)

        if res == 0:
            print("\n✨ SMOKE TEST SUCCESSFUL!")
            print("      - Build should be appearing on your device soon.")
        else:
            print(f"\n❌ SMOKE TEST FAILED with exit code {res}.")

        print("\n\033[96mCheck the logs above for Firebase distribution URLs.\033[0m")
        print("\033[90m(The smoke test creates a temporary mock job in ai/jobs/ for the distribution pipeline.)\033[0m")
        
        # We use a forced final wait here only if we aren't in CI mode
        # But actually, the dev_console run_script handles this better.
        # We'll just do the cleanup and exit.
        
        if prompt_confirm("Cleanup: Delete temporary mock job?", default=True):
            print("      - Deleting temporary job file...")
            if job_file.exists():
                os.remove(job_file)
            print("      - Done.")
        else:
            print("      - Temporary job file preserved in ai/jobs/.")

    except Exception as e:
        print(f"\n!!! Error during smoke test: {e}")
        if job_file.exists():
            if prompt_confirm("Emergency Cleanup: Delete temporary mock job?", default=True):
                os.remove(job_file)
                print("      - Deleted temporary job file.")

if __name__ == "__main__":
    run_smoke_delivery()

#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import ROOT, CONFIG_DIR, read_json

def run_local_check() -> dict[str, Any]:
    print("      - Running local model checks...")
    cmd = [sys.executable, str(SCRIPTS_DIR / "live_check_workflow.py"), "--checks", "models", "--models", "all", "--json-only"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        return json.loads(res.stdout.strip())
    except Exception as e:
        return {"error": f"Failed to parse JSON: {e}", "stdout": res.stdout, "stderr": res.stderr}

def run_remote_check(machine: dict[str, Any]) -> dict[str, Any]:
    name = machine["name"]
    target = machine["ssh_target"]
    if isinstance(target, list):
        target = target[0] # Use first target for check
    repo_path = machine["repo_path"]
    
    print(f"      - Running remote model checks on {name} ({target})...")
    remote_cmd = f"cd {repo_path} && python3 -m orchestrator.scripts.live_check_workflow --checks models --models all --json-only"
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", target, remote_cmd]
    
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return {"error": f"SSH command failed with code {res.returncode}", "stderr": res.stderr}
        
    try:
        return json.loads(res.stdout.strip())
    except Exception as e:
        return {"error": f"Failed to parse JSON: {e}", "stdout": res.stdout, "stderr": res.stderr}

def print_machine_summary(name: str, report: dict[str, Any]):
    print(f"\n--- Machine: {name} ---")
    if "error" in report:
        print(f"  ❌ ERROR: {report['error']}")
        if report.get("stderr"):
            print(f"     {report['stderr'].strip()}")
        return

    models_report = report.get("checks", {}).get("models", {})
    if not models_report:
        print("  ⚠️  No model results found.")
        return

    passed = []
    failed = []
    limited = []

    for model, result in models_report.items():
        status = result.get("status")
        if status == "passed":
            passed.append(model)
        elif status == "limited":
            limited.append(model)
        else:
            failed.append((model, result.get("error") or "Unknown error"))

    if passed:
        print(f"  ✅ PASSED ({len(passed)}): {', '.join(passed)}")
    
    if limited:
        print(f"  🟡 LIMITED ({len(limited)}): {', '.join(limited)}")

    if failed:
        print(f"  ❌ FAILED ({len(failed)}):")
        for model, err in failed:
            print(f"     - {model}: {err}")

def main():
    print("🚀 Starting Fleet-Wide LLM Connectivity Check...\n")
    
    machines_path = CONFIG_DIR / "machines.json"
    if not machines_path.exists():
        print(f"❌ Error: {machines_path} not found.")
        sys.exit(1)
        
    try:
        machines_data = read_json(machines_path)
        machines = machines_data.get("machines", [])
    except Exception as e:
        print(f"❌ Error reading machines.json: {e}")
        sys.exit(1)

    all_results = {}
    
    for m in machines:
        if not m.get("enabled", True):
            continue
            
        name = m["name"]
        if m.get("execution_mode") == "local":
            report = run_local_check()
        else:
            report = run_remote_check(m)
            
        all_results[name] = report
        print_machine_summary(name, report)

    print("\n" + "="*40)
    print("Fleet Check Complete.")

if __name__ == "__main__":
    main()

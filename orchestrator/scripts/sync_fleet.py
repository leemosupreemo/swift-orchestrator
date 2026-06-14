#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import ROOT, print_phase
from schedule_job import load_machines, probe_machine, get_local_git_state, sync_code_to_remote

def sync_all():
    print_phase("scheduling", subtext="fleet-wide synchronization")
    
    machines = load_machines()
    local_state = get_local_git_state()
    
    print(f"Local state: branch='{local_state['branch']}', hash='{local_state['hash'][:8]}', dirty={local_state['dirty']}")
    
    results = {}
    
    for machine in machines:
        name = machine["name"]
        if machine.get("execution_mode") == "local":
            print(f"\n--- Machine: {name} (Local) ---")
            print("      - Skipping synchronization for local machine.")
            results[name] = True
            continue
            
        print(f"\n--- Machine: {name} ---")
        try:
            print(f"      - \033[1;96mProbing {name}...\033[0m")
            probe = probe_machine(machine)
            
            if not probe.get("reachable"):
                print(f"      - ❌ ERROR: Machine unreachable: {probe.get('probe_error', 'Unknown error')}")
                results[name] = False
                continue
                
            success = sync_code_to_remote(machine, local_state, probe)
            results[name] = success
            
        except Exception as e:
            print(f"      - ❌ ERROR: Sync failed: {e}")
            results[name] = False

    print("\n" + "="*40)
    print("Fleet Synchronization Summary:")
    all_ok = True
    for name, success in results.items():
        status = "✅ OK" if success else "❌ FAILED"
        print(f"  {name:15}: {status}")
        if not success: all_ok = False
        
    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    sync_all()

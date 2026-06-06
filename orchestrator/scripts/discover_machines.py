#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import socket
import os
from pathlib import Path
from typing import Any

# Ensure we can find common.py
import sys
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from common import ROOT

def get_local_ssh_hosts() -> list[str]:
    """Uses dns-sd to find machines on the local network advertising SSH."""
    print("🔍 Scanning local network for SSH services (mDNS)...")
    try:
        # Run dns-sd for 2 seconds and capture output
        # _ssh._tcp is the standard service type for SSH
        cmd = ["dns-sd", "-B", "_ssh._tcp", "local"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate()

        hosts = set()
        for line in stdout.splitlines():
            if "Instance Name" in line or "---" in line or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 7:
                # The hostname is often the last part of the instance name + .local
                name = parts[6]
                hosts.add(f"{name}.local")
        return sorted(list(hosts))
    except Exception as e:
        print(f"!!! Error during mDNS scan: {e}")
        return []

def check_machine_suitability(host: str) -> dict[str, Any] | None:
    """Attempts a quick SSH check to see if the machine is a valid fleet candidate."""
    print(f"  - Checking {host}...")
    
    # Try to get system info and check for requirements
    check_cmd = "python3 --version && xcodebuild -version && uname -n"
    ssh_cmd = ["ssh", "-o", "ConnectTimeout=2", "-o", "BatchMode=yes", host, check_cmd]
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            return {
                "host": host,
                "python": lines[0] if len(lines) > 0 else "unknown",
                "xcode": lines[1] if len(lines) > 1 else "unknown",
                "hostname": lines[-1] if len(lines) > 0 else host
            }
    except:
        pass
    return None

def main():
    hosts = get_local_ssh_hosts()
    if not hosts:
        print("No SSH hosts discovered via mDNS.")
        return

    candidates = []
    for host in hosts:
        # Skip local machine
        if host.lower() == socket.gethostname().lower() or host.lower() == socket.gethostname().lower() + ".local":
            continue
            
        info = check_machine_suitability(host)
        if info:
            candidates.append(info)

    if not candidates:
        print("\nNo suitable candidates found (SSH reachable with Python/Xcode).")
        return

    print(f"\n✨ Found {len(candidates)} potential machine(s) for your fleet:")
    
    for c in candidates:
        print(f"\n--- Candidate: {c['hostname']} ---")
        print(f"  SSH Target: {c['host']}")
        print(f"  Python:     {c['python']}")
        print(f"  Xcode:      {c['xcode']}")
        
        entry = {
            "name": c['hostname'].split('.')[0],
            "enabled": True,
            "execution_mode": "ssh",
            "ssh_target": c['host'],
            "repo_path": "/Users/CHANGEME/Documents/YourSwiftProject",
            "roles": ["worker", "build", "test"],
            "models": ["gemini", "codex", "claude-opus"],
            "priority": 80,
            "max_concurrent_jobs": 2,
            "max_heavy_jobs": 1,
            "supports_xcode": True,
            "supports_simulator": True,
            "tags": ["remote", "discovered"]
        }
        print("\nCopy this into ai/config/machines.json:")
        print(json.dumps(entry, indent=2))

if __name__ == "__main__":
    main()

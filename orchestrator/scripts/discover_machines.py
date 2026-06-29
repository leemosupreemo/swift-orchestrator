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

def resolve_instance_name(instance_name: str) -> str | None:
    """Uses dns-sd to resolve the service instance name to its target hostname."""
    try:
        cmd = ["dns-sd", "-L", instance_name, "_ssh._tcp", "local"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, _ = process.communicate(timeout=1.5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate()
            
        for line in stdout.splitlines():
            if "can be reached at" in line:
                parts = line.split("can be reached at ")
                if len(parts) > 1:
                    target = parts[1].split()[0]
                    if ":" in target:
                        hostname = target.split(":")[0]
                    else:
                        hostname = target
                    return hostname.rstrip(".")
    except Exception as e:
        print(f"!!! Error resolving {instance_name}: {e}")
    return None

def get_local_hostnames() -> set[str]:
    """Retrieves all names identifying the local machine to avoid adding it to the remote fleet."""
    names = {socket.gethostname().lower(), "localhost", "127.0.0.1", "::1"}
    try:
        res = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True)
        if res.returncode == 0:
            name = res.stdout.strip()
            names.add(name.lower())
            names.add(f"{name.lower()}.local")
    except:
        pass
    return names

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

        instances = set()
        for line in stdout.splitlines():
            if "Instance Name" in line or "---" in line or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 7:
                # Reconstruct full instance name which might contain spaces
                instance_name = " ".join(parts[6:])
                instances.add(instance_name)
        
        hosts = set()
        for instance in instances:
            host = resolve_instance_name(instance)
            if host:
                hosts.add(host)
        return sorted(list(hosts))
    except Exception as e:
        print(f"!!! Error during mDNS scan: {e}")
        return []

def check_machine_suitability(host: str) -> dict[str, Any] | None:
    """Attempts a quick SSH check to see if the machine is a valid fleet candidate."""
    print(f"  - Checking {host}...")
    
    # Try to get system info and check for requirements
    check_cmd = "python3 --version && xcodebuild -version && uname -n"
    ssh_cmd = [
        "ssh",
        "-o", "ConnectTimeout=2",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        host,
        check_cmd
    ]
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            return {
                "status": "suitable",
                "host": host,
                "python": lines[0] if len(lines) > 0 else "unknown",
                "xcode": lines[1] if len(lines) > 1 else "unknown",
                "hostname": lines[-1] if len(lines) > 0 else host
            }
        else:
            # Check if it was an SSH authentication failure or connection failure
            err = result.stderr.lower()
            if "permission denied" in err or "publickey" in err or "password" in err:
                return {
                    "status": "needs_ssh_keys",
                    "host": host,
                    "error": "SSH authentication failed (Permission denied)."
                }
            elif "timeout" in err or "port 22" in err or "host is down" in err or "no route to host" in err:
                return {
                    "status": "unreachable",
                    "host": host,
                    "error": "Connection timed out / unreachable."
                }
            else:
                return {
                    "status": "missing_requirements",
                    "host": host,
                    "error": f"Connected, but requirements check failed: {result.stderr.strip() or result.stdout.strip() or 'Unknown error'}"
                }
    except Exception as e:
        return {
            "status": "error",
            "host": host,
            "error": str(e)
        }

def main():
    hosts = get_local_ssh_hosts()
    if not hosts:
        print("No SSH hosts discovered via mDNS.")
        return

    local_names = get_local_hostnames()
    suitable = []
    needs_keys = []
    unsuitable = []

    for host in hosts:
        # Skip local machine
        if host.lower() in local_names:
            continue
            
        info = check_machine_suitability(host)
        if not info:
            continue
            
        status = info.get("status")
        if status == "suitable":
            suitable.append(info)
        elif status == "needs_ssh_keys":
            needs_keys.append(info)
        else:
            unsuitable.append(info)

    # Print suitable candidates
    if suitable:
        print(f"\n✨ Found {len(suitable)} suitable machine(s) for your fleet:")
        for c in suitable:
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
            print("\nCopy this into .orchestrator/config/machines.json:")
            print(json.dumps(entry, indent=2))
    
    # Print candidates needing setup
    if needs_keys:
        print(f"\n⚠️ ACTION REQUIRED: 🔑 Found {len(needs_keys)} machine(s) needing SSH key authorization:")
        for c in needs_keys:
            print(f"\n--- Machine: {c['host']} ---")
            print("  Status:     Authentication failed (passwordless SSH is not set up).")
            print("  How to fix: Run the following command in a new terminal to copy your SSH key:")
            import getpass
            current_user = getpass.getuser()
            print(f"\033[1;96m    ssh-copy-id {current_user}@{c['host']}\033[0m")
            print("              (Or specify the target username if it differs, e.g. ssh-copy-id username@host)")

    # Print unsuitable candidates
    if unsuitable:
        print(f"\n⚠️  Found {len(unsuitable)} machine(s) with missing requirements or connection errors:")
        for c in unsuitable:
            print(f"\n--- Machine: {c['host']} ---")
            print(f"  Error:      {c['error']}")

    if not suitable and not needs_keys and not unsuitable:
        print("\nNo remote candidates found (excluding local machine).")

if __name__ == "__main__":
    main()

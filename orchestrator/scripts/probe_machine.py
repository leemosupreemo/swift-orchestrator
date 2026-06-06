#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from common import CONFIG_DIR, MACHINE_STATE_DIR, now_iso, read_json, run


def load_machines() -> list[dict[str, Any]]:
    config = read_json(CONFIG_DIR / "machines.json")
    return config["machines"]


def count_matching_processes(pattern: str) -> int:
    result = subprocess.run(
        ["pgrep", "-fl", pattern],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def probe_mem_free_mb() -> tuple[int, str]:
    total_mem_result = subprocess.run(
        ["sysctl", "-n", "hw.memsize"],
        check=False,
        capture_output=True,
        text=True,
    )
    vm_stat_result = subprocess.run(
        ["vm_stat"],
        check=False,
        capture_output=True,
        text=True,
    )

    total_mem_bytes = int(total_mem_result.stdout.strip()) if total_mem_result.returncode == 0 and total_mem_result.stdout.strip() else 0
    page_size = 4096
    match = re.search(r"page size of (\d+) bytes", vm_stat_result.stdout)
    if match:
        page_size = int(match.group(1))

    pages: dict[str, int] = {}
    for line in vm_stat_result.stdout.splitlines():
        page_match = re.match(r"^(Pages [^:]+):\s+(\d+)\.", line.strip())
        if page_match:
            pages[page_match.group(1)] = int(page_match.group(2))

    freeish_pages = (
        pages.get("Pages free", 0)
        + pages.get("Pages inactive", 0)
        + pages.get("Pages speculative", 0)
    )
    free_mb = int((freeish_pages * page_size) / (1024 * 1024))

    pressure = "unknown"
    if total_mem_bytes > 0:
        free_ratio = free_mb / (total_mem_bytes / (1024 * 1024))
        if free_ratio >= 0.15:
            pressure = "normal"
        elif free_ratio >= 0.08:
            pressure = "warning"
        else:
            pressure = "critical"
    elif free_mb >= 4096:
        pressure = "normal"
    elif free_mb >= 2048:
        pressure = "warning"
    else:
        pressure = "critical"

    return free_mb, pressure


def probe_disk_space(path: str) -> tuple[int, int]:
    """Returns (free_gb, total_gb) for the given path."""
    try:
        # Use df -g for GB units on macOS
        res = subprocess.run(["df", "-g", path], capture_output=True, text=True, check=False)
        lines = res.stdout.strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            # On macOS df -g: Filesystem, Size, Used, Avail, Capacity, iused, ifree, %iused, Mounted on
            # Parts index 3 is Avail (GB), index 1 is Size (GB)
            total = int(parts[1])
            avail = int(parts[3])
            return avail, total
    except:
        pass
    return 0, 0


def read_machine_state(machine_name: str) -> dict[str, Any]:
    state_path = MACHINE_STATE_DIR / f"{machine_name}.json"
    if not state_path.exists():
        return {}
    return read_json(state_path)


def probe_hardware_specs() -> dict[str, Any]:
    """Gathers detailed hardware specifications."""
    def get_sysctl(name: str) -> str:
        try:
            return subprocess.check_output(["sysctl", "-n", name], text=True).strip()
        except:
            return "0"

    cpu_model = get_sysctl("machdep.cpu.brand_string")
    if "Apple" in cpu_model:
        # Simplification for Apple Silicon
        cpu_model = cpu_model.split("Apple ")[-1]
    
    logical_cores = int(get_sysctl("hw.ncpu"))
    physical_cores = int(get_sysctl("hw.physicalcpu") or logical_cores)
    total_mem_bytes = int(get_sysctl("hw.memsize"))
    total_mem_gb = round(total_mem_bytes / (1024**3))

    return {
        "cpu_model": cpu_model,
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "total_mem_gb": total_mem_gb
    }


def check_stale_processes() -> list[dict[str, Any]]:
    """Identifies xcodebuild or Simulator processes running longer than 12 hours."""
    try:
        # ps -eo pid,etime,comm | grep -E "xcodebuild|Simulator|simctl"
        # etime format is [[dd-]hh:]mm:ss
        res = subprocess.run(["ps", "-eo", "pid,etime,comm"], capture_output=True, text=True, check=False)
        stale = []
        for line in res.stdout.splitlines():
            if any(x in line for x in ["xcodebuild", "Simulator", "simctl"]):
                parts = line.strip().split()
                if len(parts) < 3: continue
                pid = parts[0]
                etime = parts[1]
                # If etime contains a dash (-), it has been running for days.
                # If it has 2 colons but no dash, check hours.
                if "-" in etime or etime.count(":") >= 2:
                    # Very simple heuristic: if it's more than just mm:ss, we flag it for review
                    stale.append({"pid": pid, "etime": etime, "comm": parts[2]})
        return stale
    except:
        return []

def probe_local(machine_name: str, repo_path: str) -> dict[str, Any]:
    try:
        load_1m, load_5m, _load_15m = os.getloadavg()
    except OSError:
        load_1m = 0.0
        load_5m = 0.0

    free_mb, mem_pressure = probe_mem_free_mb()
    repo = Path(repo_path)
    state = read_machine_state(machine_name)
    active_jobs = state.get("active_jobs", [])
    hw = probe_hardware_specs()
    disk_free, disk_total = probe_disk_space(repo_path)
    if os.environ.get("SWIFT_ORCHESTRATOR_FAKE_DISK_FREE_GB"):
        disk_free = int(os.environ["SWIFT_ORCHESTRATOR_FAKE_DISK_FREE_GB"])
        disk_total = max(disk_total, disk_free)
    
    # Dependency check for CLIs
    import shutil
    binaries = ["gemini", "claude", "codex", "gh", "ollama", "opencode", "xcodebuild", "firebase"]
    
    # Robust path checking for Apple Silicon and common installer locations
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", os.path.expanduser("~/.npm-global/bin")]
    current_path = os.environ.get("PATH", "")
    search_path = ":".join([current_path] + extra_paths)
    
    installed_bins = {b: shutil.which(b, path=search_path) is not None for b in binaries}

    git_branch = "unknown"
    git_head_hash = "unknown"
    git_dirty = False
    
    if repo.exists():
        try:
            git_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo), text=True).strip()
            git_head_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo), text=True).strip()
            git_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(repo), text=True).strip()
            git_dirty = len(git_status) > 0
        except:
            pass

    return {
        "machine": machine_name,
        "reachable": True,
        "hw": hw,
        "cpu_load_1m": round(load_1m, 2),
        "cpu_load_5m": round(load_5m, 2),
        "mem_free_mb": free_mb,
        "mem_pressure": mem_pressure,
        "disk_free_gb": disk_free,
        "disk_total_gb": disk_total,
        "active_xcodebuild_count": count_matching_processes("xcodebuild"),
        "active_simulator_count": count_matching_processes("Simulator.app/Contents/MacOS/Simulator"),
        "active_ai_jobs": len(active_jobs),
        "repo_exists": repo.exists(),
        "repo_path_ok": repo.exists(),
        "git_branch": git_branch,
        "git_head_hash": git_head_hash,
        "git_dirty": git_dirty,
        "binaries": installed_bins,
        "stale_processes": check_stale_processes(),
        "timestamp": now_iso(),
    }


def probe_machine(machine: dict[str, Any]) -> dict[str, Any]:
    """Unified wrapper to probe a machine locally or remotely."""
    if machine["execution_mode"] == "local":
        payload = probe_local(machine["name"], machine["repo_path"])
    elif machine["execution_mode"] == "ssh":
        payload = probe_remote(machine)
    else:
        raise ValueError(f"Unsupported execution mode: {machine['execution_mode']}")

    payload.setdefault("supports_xcode", machine.get("supports_xcode", False))
    return payload


def probe_remote(machine: dict[str, Any]) -> dict[str, Any]:
    ssh_targets = machine.get("ssh_target")
    if isinstance(ssh_targets, str):
        ssh_targets = [ssh_targets]
    elif not ssh_targets:
        ssh_targets = []

    repo_path = machine["repo_path"]
    machine_name = machine["name"]
    
    local_script_path = Path(__file__).resolve()
    remote_tmp_script_path = f"/tmp/probe_{local_script_path.name}"

    print(f"      - \033[96mProbing remote machine {machine_name}...\033[0m")
    
    last_result = None
    successful_target = None
    
    for target in ssh_targets:
        # 1. Sync the probe script itself to a temp location
        try:
            subprocess.run(["scp", "-o", "ConnectTimeout=5", "-q", str(local_script_path), f"{target}:{remote_tmp_script_path}"], check=True)
        except Exception as e:
            last_result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=str(e))
            continue

        # 2. Execute the synced script
        remote_script_cmd = (
            f"cd {shlex.quote(repo_path)} && "
            f"python3 {remote_tmp_script_path} --probe-local "
            f"--machine-name {shlex.quote(machine_name)} "
            f"--repo-path {shlex.quote(repo_path)}"
        )

        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", target, remote_script_cmd],
            capture_output=True, text=True, check=False
        )
        last_result = result
        
        # 3. Cleanup the temp script
        try:
            subprocess.run(["ssh", "-o", "ConnectTimeout=2", target, f"rm {remote_tmp_script_path}"], capture_output=True, check=False)
        except:
            pass # Ignore cleanup failures

        if result.returncode == 0:
            successful_target = target
            break

    if not successful_target or not last_result or last_result.returncode != 0:
        error_msg = last_result.stderr.strip() or last_result.stdout.strip() or "remote probe failed on all targets" if last_result else "no ssh targets configured"
        return {
            "machine": machine_name,
            "reachable": False,
            "cpu_load_1m": 0.0,
            "cpu_load_5m": 0.0,
            "mem_free_mb": 0,
            "mem_pressure": "unknown",
            "active_xcodebuild_count": 0,
            "active_simulator_count": 0,
            "active_ai_jobs": 0,
            "repo_exists": False,
            "repo_path_ok": False,
            "probe_error": error_msg,
            "timestamp": now_iso(),
        }

    try:
        payload = json.loads(last_result.stdout.strip())
    except json.JSONDecodeError as exc:
        return {
            "machine": machine_name,
            "reachable": False,
            "cpu_load_1m": 0.0,
            "cpu_load_5m": 0.0,
            "mem_free_mb": 0,
            "mem_pressure": "unknown",
            "active_xcodebuild_count": 0,
            "active_simulator_count": 0,
            "active_ai_jobs": 0,
            "repo_exists": False,
            "repo_path_ok": False,
            "probe_error": f"invalid probe output: {exc}",
            "timestamp": now_iso(),
        }

    payload["machine"] = machine_name
    payload["reachable"] = True
    payload["active_ssh_target"] = successful_target
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine-name")
    parser.add_argument("--repo-path")
    parser.add_argument("--probe-local", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.probe_local:
        if not args.machine_name or not args.repo_path:
            raise ValueError("--probe-local requires --machine-name and --repo-path")
        payload = probe_local(args.machine_name, args.repo_path)
    else:
        if not args.machine_name:
            raise ValueError("Provide --machine-name when probing from machines.json")
        machines = {machine["name"]: machine for machine in load_machines()}
        machine = machines[args.machine_name]
        if machine["execution_mode"] == "local":
            payload = probe_local(machine["name"], machine["repo_path"])
        else:
            payload = probe_remote(machine)

    if args.json or args.probe_local:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"{payload['machine']}: reachable={payload['reachable']} "
            f"load1={payload['cpu_load_1m']} mem_free_mb={payload['mem_free_mb']} "
            f"disk_free_gb={payload.get('disk_free_gb', 0)} "
            f"xcodebuild={payload['active_xcodebuild_count']} simulator={payload['active_simulator_count']}"
        )


if __name__ == "__main__":
    main()

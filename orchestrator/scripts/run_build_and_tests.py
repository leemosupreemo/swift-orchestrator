#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import re
import shlex
from pathlib import Path

from common import (
    DOCS_DIR, 
    OUTPUT_DIR, 
    PROMPTS_DIR,
    ROOT, 
    run_shell, 
    write_text, 
    extract_commands, 
    print_phase, 
    is_disk_full_error, 
    purge_zombie_processes,
    get_best_simulator_destination
)
from llm import run_llm
from model_router import ModelRole


class EnvironmentValidationError(RuntimeError):
    """Raised when local machine setup prevents meaningful build/test validation."""


def detect_simulator_environment_issue(output: str) -> str | None:
    if "There is no XCFramework found at" in output and ".swiftpm/artifacts" in output:
        return (
            "Stale or incomplete SwiftPM binary artifact cache: Xcode is resolving package "
            "XCFrameworks from missing .swiftpm/artifacts paths. Clear the worker's DerivedData "
            "and .swiftpm package cache, then re-resolve package dependencies on the worker machine."
        )

    if "CoreSimulator is out of date" in output:
        return (
            "Xcode/CoreSimulator mismatch: CoreSimulator is out of date for the selected Xcode. "
            "Restart the machine or CoreSimulator services, then reopen Xcode. If the issue persists, "
            "finish installing Xcode components."
        )

    if "iOS 26.5 is not installed" in output or "Please download and install the platform from Xcode > Settings > Components" in output:
        return (
            "Missing iOS simulator platform: install the required iOS platform from "
            "Xcode > Settings > Components on the worker machine."
        )

    if "Unable to find a device matching the provided destination specifier" in output and "no available devices matched" in output:
        return (
            "Unavailable simulator destination: the requested simulator/device is not available on this worker. "
            "Install the required runtime or select an available simulator destination."
        )

    return None


def nice_timestamp() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def capture_system_logs(out_path: Path):
    """Captures recent simulator logs if a simulator is booted."""
    try:
        # Try to find a booted simulator
        cmd = ["xcrun", "simctl", "list", "devices", "booted", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            booted = []
            for runtime in data.get("devices", {}).values():
                for device in runtime:
                    booted.append(device["udid"])
            
            if booted:
                # Capture last 2 minutes of logs from the first booted sim
                udid = booted[0]
                print(f"      - Capturing system logs from simulator {udid}...")
                log_cmd = ["xcrun", "simctl", "spawn", udid, "log", "show", "--last", "2m", "--style", "syslog"]
                log_res = subprocess.run(log_cmd, capture_output=True, text=True)
                if log_res.returncode == 0:
                    write_text(out_path, log_res.stdout)
                    return True
    except Exception as e:
        print(f"      - Warning: Failed to capture system logs: {e}")
    return False

def analyze_failure(kind: str, output: str) -> str:
    prompt = (PROMPTS_DIR / "build_checker.md").read_text(encoding="utf-8")
    analysis, _, session_id = run_llm("gemini", f"{prompt}\n\nFailure type: {kind}\n\nOutput:\n{output}\n", cwd=ROOT, role=ModelRole.REVIEWER)
    return analysis


def extract_xcresult_summary(output: str) -> str:
    """Extracts xcresult path from xcodebuild output and generates a text summary of failures."""
    match = re.search(r"Test session results, code coverage, and logs:\s+(.*\.xcresult)", output)
    if not match:
        return ""
    
    xcresult_path = match.group(1).strip()
    try:
        # Get the summary of the test run
        cmd = ["xcrun", "xcresulttool", "get", "--path", xcresult_path, "--format", "json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return f"Failed to run xcresulttool: {res.stderr}"
        
        data = json.loads(res.stdout)
        
        # This is a high-level summary. To get detailed failures, we'd need to traverse the actions.
        # For now, let's just provide the path and the high-level summary if available.
        # A more detailed parsing could be added if needed.
        return f"\n--- XCRESULT DATA ---\nPath: {xcresult_path}\n" + json.dumps(data, indent=2)[:5000] + "\n"
    except Exception as e:
        return f"Error parsing xcresult: {e}"


def resolve_command(cmd: str) -> str:
    """Resolves $(pwd) and injects the best local simulator into a command string."""
    if not cmd: return cmd
    
    # 1. Resolve $(pwd) locally
    cmd = cmd.replace("$(pwd)", str(ROOT))
    
    # 2. Inject/Replace local simulator destination if it's an xcodebuild command
    if "xcodebuild" in cmd:
        try:
            dest = get_best_simulator_destination()
            parts = shlex.split(cmd)
            dest_indices = [i for i, x in enumerate(parts) if x == "-destination"]

            if dest_indices:
                for idx in reversed(dest_indices):
                    if idx + 1 < len(parts): del parts[idx + 1]
                    del parts[idx]
            
            # Add the local destination
            parts.extend(["-destination", dest])
            return shlex.join(parts)
        except Exception:
            # Fallback for complex strings
            return cmd
    return cmd


def run_build_and_tests(job: dict, summary_file: Path) -> tuple[bool, bool]:
    out_dir = OUTPUT_DIR / job["job_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    
    ts = nice_timestamp()

    likely_files = job.get("plan", {}).get("likely_files", [])
    is_infra = any("orchestrator/" in f or "scripts/" in f for f in likely_files)
    
    raw_build_cmd, raw_test_cmd = extract_commands()

    # Determine test command first to see if we should skip build
    test_cmd = raw_test_cmd
    override = job.get("test_command_override")
    
    is_standalone_test = False
    if override:
        o = override.strip().lower()
        # Robust N/A check
        is_na = any(x in o for x in {"n/a", "none", "no tests", "no specific tests", "skipped", "validated"})
        
        if is_na:
            test_cmd = None
        elif "python3" in override or "pytest" in override or "sh " in override or "./" in override:
            test_cmd = override
            is_standalone_test = True
        elif "xcodebuild test" in override:
            test_cmd = override
        elif override.startswith("-only-testing") or override.startswith("-skip-testing"):
            # Traditional -only-testing override
            test_cmd = f"{raw_test_cmd} {override}"
        else:
            # If it's just some random text from the LLM, don't execute it
            print(f"      - Warning: Ignoring malformed test command override: {override}")
            test_cmd = raw_test_cmd

    # Resolve commands locally on the worker machine
    build_cmd = resolve_command(raw_build_cmd)
    final_test_cmd = resolve_command(test_cmd)

    # Only run xcodebuild build if it's not a standalone non-ios test or if we are forced
    if is_infra and is_standalone_test:
        print_phase("skipping_ios_build", subtext="infra task with standalone tests")
        build_ok = True
    else:
        print_phase("building")
        # Retry loop for disk full
        max_retries = 1
        build_ok = False
        for attempt in range(max_retries + 1):
            print(f"      - Running build: {build_cmd} (Attempt {attempt + 1})")
            build_result = run_shell(build_cmd, cwd=ROOT, check=False, capture=False)

            if build_result.returncode != 0:
                cap_result = run_shell(build_cmd, cwd=ROOT, check=False, capture=True)
                full_output = cap_result.stdout + "\n" + cap_result.stderr
                environment_issue = detect_simulator_environment_issue(full_output)
                if environment_issue:
                    write_text(out_dir / "environment_failure.md", environment_issue + "\n\n--- Raw output ---\n" + full_output)
                    write_text(out_dir / "build.log", full_output)
                    raise EnvironmentValidationError(environment_issue)

                if is_disk_full_error(full_output) and attempt < max_retries:
                    print("\n\033[1;93m⚠️  DISK FULL DETECTED. Attempting automated recovery...\033[0m")
                    purge_zombie_processes([job.get("assigned_machine", "local")], silent=False)
                    print("\033[1;92m✅ Cleanup complete. Retrying build...\033[0m\n")
                    continue
                print("      - Build FAILED. Analyzing errors...")
                analysis = analyze_failure("build", full_output)
                write_text(out_dir / f"build_analysis_{ts}.md", analysis)
                write_text(out_dir / "build.log", full_output)
                return False, False
            build_ok = True
            write_text(out_dir / "build.log", "** BUILD SUCCEEDED **")
            break

    if not final_test_cmd:
        print_phase("skipping_tests", subtext="no test command provided or N/A")
        return build_ok, True

    print_phase("testing")
    
    # Retry loop for disk full during test execution
    max_retries = 1
    test_ok = False
    for attempt in range(max_retries + 1):
        print(f"      - Running tests: {final_test_cmd} (Attempt {attempt + 1})")
        test_result = run_shell(final_test_cmd, cwd=ROOT, check=False, capture=True)
        full_test_output = test_result.stdout + "\n\nSTDERR:\n" + test_result.stderr
        
        if test_result.returncode != 0 and is_disk_full_error(full_test_output) and attempt < max_retries:
            print("\n\033[1;93m⚠️  DISK FULL DETECTED during tests. Attempting automated recovery...\033[0m")
            purge_zombie_processes([job.get("assigned_machine", "local")], silent=False)
            print("\033[1;92m✅ Cleanup complete. Retrying tests...\033[0m\n")
            continue
        
        write_text(out_dir / f"test_{ts}.log", full_test_output)
        write_text(out_dir / "test.log", full_test_output)

        if test_result.returncode == 0:
            print("      - Tests passed.")
            return True, True

        if test_result.returncode != 0:
            environment_issue = detect_simulator_environment_issue(full_test_output)
            if environment_issue:
                write_text(out_dir / "environment_failure.md", environment_issue + "\n\n--- Raw output ---\n" + full_test_output)
                raise EnvironmentValidationError(environment_issue)

            print("\n\033[1;91m" + "!"*60)
            print("  ❌  TESTS FAILED. Analyzing failures...  ❌")
            print("!"*60 + "\033[0m\n")
            
            # ... (rest of the failure analysis)
        
        # Extract specific failures for immediate console visibility
        failures = []
        for line in test_result.stdout.splitlines():
            if "Test case" in line and "failed" in line:
                failures.append(line.strip())
            elif "Test suite" in line and "failed" in line:
                failures.append(line.strip())
        
        if failures:
            print("\n--- Failure Summary ---")
            for f in failures[:10]: # Don't flood the console if many failed
                print(f"  {f}")
            if len(failures) > 10:
                print(f"  ... and {len(failures) - 10} more")
            print("-----------------------\n")

        analysis = analyze_failure("test", full_test_output)
        
        print(f"--- AI Analysis Summary ---")
        # Print first few lines of analysis to provide immediate context
        print("\n".join(analysis.splitlines()[:15]))
        print("... (Full analysis in test_analysis.md)")
        print("---------------------------\n")

        # Extract xcresult summary
        xc_summary = extract_xcresult_summary(test_result.stdout)
        if xc_summary:
            write_text(out_dir / f"test_results_{ts}.txt", xc_summary)

        write_text(out_dir / f"test_analysis_{ts}.md", analysis)
        
        # Capture system logs on failure
        capture_system_logs(out_dir / f"system_{ts}.log")
        
        return True, False

    print("      - Tests passed.")
    return True, True

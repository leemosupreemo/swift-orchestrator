#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from common import OUTPUT_DIR, ROOT, now_iso, write_json
from probe_machine import load_machines
from run_build_and_tests import extract_commands
from common import run, run_shell
from llm import SUPPORTED_MODELS, get_llm_command, get_llm_env


def shell_result_dict(result: Any) -> dict[str, Any]:
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def normalize_maybe_bytes(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_gh_auth_status() -> dict[str, Any]:
    result = run(["gh", "auth", "status"], cwd=ROOT, check=False)
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": ["gh", "auth", "status"],
        "result": shell_result_dict(result),
    }


def run_ssh_probe(machine_name: str) -> dict[str, Any]:
    machines = {machine["name"]: machine for machine in load_machines()}
    machine = machines[machine_name]
    if machine["execution_mode"] != "ssh":
        raise ValueError(f"{machine_name} is not an SSH machine")

    repo_path = shlex.quote(machine["repo_path"])
    remote_command = (
        f"if [ -d {repo_path} ]; then "
        f"echo REPO_OK; "
        f"cd {repo_path}; "
        f"pwd; "
        f"python3 -c 'import orchestrator.scripts.probe_machine' >/dev/null 2>&1 && echo PROBE_SCRIPT_OK || echo PROBE_SCRIPT_MISSING; "
        f"else echo REPO_MISSING; exit 3; fi"
    )
    result = run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", machine["ssh_target"], remote_command],
        cwd=ROOT,
        check=False,
    )
    result_dict = shell_result_dict(result)
    if result.returncode == 255:
        result_dict["hint"] = f"SSH failed to connect to '{machine['ssh_target']}'. Check your ~/.ssh/config or if the machine is online."

    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "machine": machine_name,
        "command": ["ssh", "-o", "BatchMode=yes", machine["ssh_target"], remote_command],
        "result": result_dict,
    }


def run_model_check(model: str, prompt: str, timeout_sec: int) -> dict[str, Any]:
    # Use a temp file for the prompt to avoid "stdin is not a terminal" issues
    # and to match the pattern used in llm.py
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md", encoding="utf-8") as f:
        f.write(prompt)
        prompt_file = f.name

    cmd = get_llm_command(model, prompt_file)
    env = get_llm_env()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            shell=True,
            executable="/bin/bash",
            timeout=timeout_sec,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "model": model,
            "error": f"timed out after {timeout_sec}s",
            "stdout": normalize_maybe_bytes(exc.stdout),
            "stderr": normalize_maybe_bytes(exc.stderr),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "model": model,
            "error": str(exc),
        }
    finally:
        if os.path.exists(prompt_file):
            os.remove(prompt_file)

    if result.returncode != 0:
        error_msg = result.stderr or result.stdout
        is_quota = any(x in error_msg.lower() for x in ["usage limit", "quota", "rate limit", "credits"])
        
        return {
            "status": "limited" if is_quota else "failed",
            "model": model,
            "returncode": result.returncode,
            "error": "Resource quota/limit reached" if is_quota else f"Command failed with code {result.returncode}",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    # Check for the expected response in stdout
    # Some models might output warnings (like MCP issues) along with the response
    passed = "LIVE_OK" in result.stdout
    return {
        "status": "passed" if passed else "failed",
        "model": model,
        "error": None if passed else "Expected 'LIVE_OK' not found in output",
        "output_preview": result.stdout[:400],
    }


def with_derived_data(command: str, derived_data_path: Path) -> str:
    escaped_path = shlex.quote(str(derived_data_path))
    return f"{command} -derivedDataPath {escaped_path}"


def run_xcode_build(derived_data_path: Path) -> dict[str, Any]:
    build_cmd, _test_cmd = extract_commands()
    command = with_derived_data(build_cmd, derived_data_path)
    result = run_shell(command, cwd=ROOT, check=False, capture=True)
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": command,
        "derived_data_path": str(derived_data_path),
        "result": shell_result_dict(result),
    }


def run_xcode_test(derived_data_path: Path) -> dict[str, Any]:
    _build_cmd, test_cmd = extract_commands()
    command = with_derived_data(test_cmd, derived_data_path)
    result = run_shell(command, cwd=ROOT, check=False, capture=True)
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": command,
        "derived_data_path": str(derived_data_path),
        "result": shell_result_dict(result),
    }


def output_path() -> Path:
    out_dir = OUTPUT_DIR / "live-checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{now_iso().replace(':', '').replace('-', '')}-report.json"


def make_derived_data_path() -> Path:
    return Path(tempfile.mkdtemp(prefix="thirteen-live-check-", dir="/tmp"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run live workflow integration checks against real GitHub auth, SSH, model CLIs, and Xcode."
    )
    parser.add_argument(
        "--checks",
        nargs="+",
        choices=["github", "ssh", "models", "xcode-build", "xcode-test", "all"],
        default=["all"],
    )
    parser.add_argument(
        "--ssh-machine",
        default="mac2-ssh",
        help="Machine name from ai/config/machines.json for the live SSH probe",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemini", "codex", "claude-opus"],
        help="Models to probe when running the models check. Use 'all' for every supported model.",
    )
    parser.add_argument(
        "--model-prompt",
        default="Reply with exactly: LIVE_OK",
        help="Prompt used for live model CLI checks",
    )
    parser.add_argument(
        "--model-timeout-sec",
        type=int,
        default=60,
        help="Timeout per live model CLI invocation",
    )
    parser.add_argument(
        "--derived-data-path",
        help="Optional DerivedData path for live Xcode checks. Defaults to a fresh temp directory per run.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Suppress normal output and only print the final JSON report to stdout.",
    )
    args = parser.parse_args()

    requested = set(args.checks)
    if "all" in requested:
        requested = {"github", "ssh", "models", "xcode-build", "xcode-test"}

    models_to_test = args.models
    if "all" in models_to_test:
        models_to_test = sorted(list(SUPPORTED_MODELS))

    report: dict[str, Any] = {
        "timestamp": now_iso(),
        "cwd": str(ROOT),
        "checks": {},
    }
    derived_data_path: Path | None = None
    if "xcode-build" in requested or "xcode-test" in requested:
        derived_data_path = Path(args.derived_data_path).resolve() if args.derived_data_path else make_derived_data_path()
        derived_data_path.mkdir(parents=True, exist_ok=True)
        report["derived_data_path"] = str(derived_data_path)

    if "github" in requested:
        report["checks"]["github"] = run_gh_auth_status()
    if "ssh" in requested:
        report["checks"]["ssh"] = run_ssh_probe(args.ssh_machine)
    if "models" in requested:
        report["checks"]["models"] = {
            model: run_model_check(model, args.model_prompt, args.model_timeout_sec)
            for model in models_to_test
        }
    if "xcode-build" in requested:
        assert derived_data_path is not None
        report["checks"]["xcode-build"] = run_xcode_build(derived_data_path)
    if "xcode-test" in requested:
        assert derived_data_path is not None
        report["checks"]["xcode-test"] = run_xcode_test(derived_data_path)

    path = output_path()
    write_json(path, report)
    
    if args.json_only:
        print(json.dumps(report))
    else:
        print(f"Wrote live check report: {path}")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import schedule_job
import worker_run
import debug_job
from common import ROOT
from orchestrator.project_config import PACKAGE_ROOT


FIXTURES_DIR = PACKAGE_ROOT.parent / "tests" / "fixtures"


def completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def write_temp_job(job: dict[str, Any], temp_dir: Path) -> Path:
    job_path = temp_dir / "job.json"
    job_path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    return job_path


def make_local_machine() -> dict[str, Any]:
    return {
        "name": "mac1",
        "enabled": True,
        "execution_mode": "local",
        "ssh_target": None,
        "repo_path": str(ROOT),
        "roles": ["planner", "reviewer", "worker", "build", "test"],
        "models": ["gemini", "codex", "claude-opus"],
        "priority": 100,
        "max_concurrent_jobs": 2,
        "max_heavy_jobs": 1,
        "supports_xcode": True,
        "supports_simulator": True,
        "supports_backend_tests": True,
        "interactive_reserved": False,
        "tags": ["interactive", "primary"],
    }


def make_local_probe() -> dict[str, Any]:
    return {
        "machine": "mac1",
        "reachable": True,
        "repo_exists": True,
        "disk_free_gb": 100,
        "mem_free_mb": 12000,
        "active_ai_jobs": 0,
        "active_xcodebuild_count": 0,
        "active_simulator_count": 0,
        "cpu_load_1m": 0.3,
    }


def make_remote_machine() -> dict[str, Any]:
    return {
        "name": "mac2",
        "enabled": True,
        "execution_mode": "ssh",
        "ssh_target": "Leemo",
        "repo_path": "/Users/worker/Documents/SwiftFixture",
        "roles": ["worker", "build", "test"],
        "models": ["gemini", "codex", "claude-opus"],
        "priority": 90,
        "max_concurrent_jobs": 2,
        "max_heavy_jobs": 1,
        "supports_xcode": True,
        "supports_simulator": True,
        "supports_backend_tests": True,
        "interactive_reserved": False,
        "tags": ["remote", "preferred-build"],
    }


def make_remote_probe() -> dict[str, Any]:
    return {
        "machine": "mac2",
        "reachable": True,
        "repo_exists": True,
        "disk_free_gb": 100,
        "mem_free_mb": 14000,
        "active_ai_jobs": 0,
        "active_xcodebuild_count": 0,
        "active_simulator_count": 0,
        "cpu_load_1m": 0.4,
    }


def expected_branch(job: dict[str, Any]) -> str:
    return f"ai/issue-{job['issue_number']}-{worker_run.slugify(job['title'])}"


def run_local_scenario(success: bool) -> None:
    job = load_fixture("legacy_bug_job.json")
    machine = make_local_machine()
    probe = make_local_probe()

    with tempfile.TemporaryDirectory(prefix="workflow-smoke-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        job_path = write_temp_job(job, temp_dir)
        argv = ["schedule_job.py", str(job_path)]

        with (
            patch.object(sys, "argv", argv),
            patch.object(schedule_job, "load_machines", return_value=[machine]),
            patch.object(schedule_job, "probe_machine", return_value=probe),
            patch.object(worker_run, "run", return_value=completed()),
            patch.object(worker_run, "run_shell", return_value=completed(stdout="")),
            patch.object(worker_run.subprocess, "run", return_value=completed()),
            patch.object(worker_run, "is_firebase_configured", return_value=False),
            patch.object(worker_run, "send_notifications"),
            patch.object(worker_run, "update_issue_status"),
            patch.object(debug_job, "run_debug_iteration"),
            patch.object(
                worker_run,
                "run_builder",
                return_value=(success, success, Path("/tmp/summary.md")),
            ),
            patch.object(worker_run, "open_or_update_pr", return_value=321),
        ):
            schedule_job.main()

        result = json.loads(job_path.read_text(encoding="utf-8"))
        if success:
            assert result["status"] == "review-needed", result
            assert result["pr_number"] == 321, result
        else:
            assert result["status"] == "debugging", result
            assert result["pr_number"] is None, result

        assert result["assigned_machine"] == "mac1", result
        assert result["assigned_model"] == "codex", result
        assert result["branch"] == expected_branch(job), result
        assert result["task_groups"][0]["status"] == "scheduled", result
        assert len(result["dispatch_history"]) == 1, result

        print(
            f"Scenario {'local-success' if success else 'local-failure'} passed. "
            f"Final status: {result['status']}."
        )


def run_remote_dispatch_scenario() -> None:
    job = load_fixture("legacy_bug_job.json")
    machine = make_remote_machine()
    probe = make_remote_probe()
    commands: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check, capture
        commands.append(cmd)
        return completed()

    with tempfile.TemporaryDirectory(prefix="workflow-smoke-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        job_path = write_temp_job(job, temp_dir)
        argv = ["schedule_job.py", str(job_path)]

        with (
            patch.object(sys, "argv", argv),
            patch.object(schedule_job, "load_machines", return_value=[machine]),
            patch.object(schedule_job, "probe_machine", return_value=probe),
            patch.object(schedule_job, "sync_code_to_remote", return_value=True),
            patch.object(schedule_job, "run", side_effect=fake_run),
        ):
            schedule_job.main()

        result = json.loads(job_path.read_text(encoding="utf-8"))
        assert result["assigned_machine"] == "mac2", result
        assert result["assigned_model"] == "codex", result
        assert result["status"] == "planned", result
        assert result["task_groups"][0]["status"] == "scheduled", result
        assert len(commands) >= 3, commands
        assert commands[0][0] == "ssh", commands
        assert "import orchestrator.scripts.worker_run" in commands[0][-1], commands
        assert commands[1][0] == "ssh", commands
        assert commands[2][0] == "scp", commands
        assert commands[3][0] == "ssh", commands
        assert "PYTHONPATH=" in commands[3][-1], commands
        assert ".swift-orchestrator/jobs/inbox" in commands[3][-1], commands

        print("Scenario remote-dispatch passed. Remote dispatch commands were emitted as expected.")


def run_remote_missing_package_scenario() -> None:
    job = load_fixture("legacy_bug_job.json")
    machine = make_remote_machine()
    probe = make_remote_probe()
    commands: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check, capture
        commands.append(cmd)
        if "import orchestrator.scripts.worker_run" in cmd[-1]:
            return completed(stderr="No module named orchestrator", returncode=1)
        return completed()

    with tempfile.TemporaryDirectory(prefix="workflow-smoke-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        job_path = write_temp_job(job, temp_dir)
        argv = ["schedule_job.py", str(job_path)]

        with (
            patch.object(sys, "argv", argv),
            patch.object(schedule_job, "load_machines", return_value=[machine]),
            patch.object(schedule_job, "probe_machine", return_value=probe),
            patch.object(schedule_job, "sync_code_to_remote", return_value=True),
            patch.object(schedule_job, "run", side_effect=fake_run),
        ):
            try:
                schedule_job.main()
            except SystemExit as exc:
                assert exc.code == 1, exc
            else:
                raise AssertionError("Expected remote dispatch to exit when package is missing")

        assert len(commands) == 1, commands
        assert "import orchestrator.scripts.worker_run" in commands[0][-1], commands
        print("Scenario remote-missing-package passed. Dispatch stopped before sync.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run opt-in smoke tests for the AI workflow without touching real GitHub, SSH, or Xcode."
    )
    parser.add_argument(
        "--scenario",
        choices=["local-success", "local-failure", "remote-dispatch", "remote-missing-package", "all"],
        default="all",
    )
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario != "all" else [
        "local-success",
        "local-failure",
        "remote-dispatch",
        "remote-missing-package",
    ]

    for scenario in scenarios:
        if scenario == "local-success":
            run_local_scenario(success=True)
        elif scenario == "local-failure":
            run_local_scenario(success=False)
        elif scenario == "remote-dispatch":
            run_remote_dispatch_scenario()
        elif scenario == "remote-missing-package":
            run_remote_missing_package_scenario()
        else:
            raise ValueError(f"Unsupported scenario: {scenario}")


if __name__ == "__main__":
    main()

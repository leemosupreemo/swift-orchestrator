#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from common import ROOT
from orchestrator.project_config import PACKAGE_ROOT


PLANNER_OUTPUT = {
    "title": "Settings name updates are not reflected in detail view without restart",
    "summary": "When a user edits their display name in settings, the detail view continues to display the old name.",
    "repro_steps": [
        "Launch the app and navigate to settings.",
        "Edit the display name.",
        "Open the detail view.",
    ],
    "expected_behavior": "The detail view should reflect the new display name without restart.",
    "acceptance_criteria": [
        "Display name changes in settings are reactively updated in the detail view.",
    ],
    "constraints": [
        "Must adhere to existing SwiftUI state management patterns.",
    ],
    "complexity": "complex",
    "recommended_job_type": "bug-fix",
    "likely_files": [
        "MyApp/SettingsViewModel.swift",
        "MyApp/DetailView.swift",
    ],
    "test_recommendations": [
        "Add a focused unit test.",
    ],
}

PLANNER_FEATURE_OUTPUT = {
    "title": "Add dark mode toggle to settings",
    "summary": "Implement a toggle in the settings view to switch between light and dark modes.",
    "assumptions": ["App uses a central theme manager."],
    "constraints": ["Must support iOS 15+."],
    "risks": ["Potential UI flickering on switch."],
    "tasks": [
        {
            "title": "Add toggle to SettingsView",
            "description": "Insert a Toggle component in the SettingsView.",
            "acceptance_criteria": ["Toggle appears in settings.", "Toggle state is persisted."],
            "likely_files": ["MyApp/SettingsView.swift"],
            "tests": ["testTogglePersistence"],
            "complexity": "simple"
        }
    ]
}


SCRIPTS_DIR = Path(__file__).resolve().parent


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_fake_binaries(fake_bin_dir: Path) -> None:
    planner_json = json.dumps(PLANNER_OUTPUT)
    feature_planner_json = json.dumps(PLANNER_FEATURE_OUTPUT)
    verifier_json = json.dumps({
        "status": "approved",
        "comments": "The plan looks solid. All architectural considerations are met.",
        "suggested_additions": ["Verify SwiftUI state updates on main thread"],
        "risks_identified": []
    })
    builder_json = json.dumps({
        "hypothesis": "Display name state is not being propagated to the detail view model.",
        "implementation_plan": "1. Update SettingsViewModel to publish name changes. 2. Observe changes in DetailView.",
        "files_changed": ["MyApp/SettingsViewModel.swift", "MyApp/DetailView.swift"],
        "summary": "Implemented reactive display name updates."
    })

    write_executable(
        fake_bin_dir / "gemini",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import os
            import sys

            prompt = sys.stdin.read()
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("gemini " + prompt[:120].replace("\\n", " ") + "\\n")

            if "Raw input:" in prompt:
                if "VISION:" in prompt:
                    print({feature_planner_json!r})
                else:
                    print({planner_json!r})
            elif "Role: Senior System Architect" in prompt:
                print({verifier_json!r})
            elif "You are the build-analysis agent" in prompt:
                if log_path:
                    with open(log_path, "a", encoding="utf-8") as handle:
                        handle.write("gemini build-analysis-agent-trigger\\n")
                print("Failure analysis from fake build-analysis agent")
            else:
                print("Gemini placeholder")
            """
        ),
    )

    write_executable(
        fake_bin_dir / "codex",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import os
            import sys

            prompt = sys.stdin.read()
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("codex " + prompt[:120].replace("\\n", " ") + "\\n")
            
            if "implementation agent" in prompt:
                print({builder_json!r})
            else:
                print("Builder summary from fake codex")
            """
        ),
    )

    write_executable(
        fake_bin_dir / "claude",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            prompt = sys.stdin.read()
            if "Role: Senior System Architect" in prompt:
                print({verifier_json!r})
            else:
                print("Claude placeholder")
            """
        ),
    )

    write_executable(
        fake_bin_dir / "opencode",
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            prompt = sys.stdin.read()
            if "Role: Senior System Architect" in prompt:
                print({verifier_json!r})
            elif "implementation agent" in prompt:
                print({builder_json!r})
            else:
                print("OpenCode placeholder")
            """
        ),
    )

    write_executable(
        fake_bin_dir / "git",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import sys

            args = sys.argv[1:]
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("git " + " ".join(args) + "\\n")

            if args[:2] == ["branch", "--list"]:
                print("")
            sys.exit(0)
            """
        ),
    )

    write_executable(
        fake_bin_dir / "gh",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys

            args = sys.argv[1:]
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("gh " + " ".join(args) + "\\n")

            if args[:2] == ["issue", "create"]:
                print("https://example.test/issues/9001")
            elif args[:2] == ["issue", "edit"]:
                print("")
            elif args[:2] == ["pr", "list"]:
                print("[]")
            elif args[:2] == ["pr", "create"]:
                print("https://example.test/pull/7001")
            elif args[:2] == ["pr", "view"]:
                # Return a valid JSON object for PR metadata
                print(json.dumps({
                    "title": "Resume Test PR",
                    "body": "Mock body",
                    "url": "https://example.test/pull/7001",
                    "files": [{"path": "file1.swift", "additions": 10, "deletions": 2}],
                    "commits": [{"oid": "abc123", "message": "Initial commit"}]
                }))
            elif args[:2] == ["pr", "diff"]:
                print("--- file1.swift\\n+++ file1.swift\\n@@ -1,1 +1,1 @@\\n-old\\n+new")
            elif args[:2] == ["pr", "comment"]:
                print("")
            elif args[:2] == ["pr", "edit"]:
                print("")
            elif "copilot" in args:
                print('{"hypothesis": "Fake hypothesis", "action": "Fake action"}')
            else:
                # Return a valid empty object if it looks like an LLM call, otherwise error
                if "exec" in args:
                    print("{}")
                else:
                    print(f"Unknown gh command: {args}", file=sys.stderr)
                    sys.exit(1)
            """
        ),
    )

    write_executable(
        fake_bin_dir / "xcodebuild",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import sys

            args = sys.argv[1:]
            mode = os.environ.get("FAKE_XCODEBUILD_MODE", "success")
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("xcodebuild " + " ".join(args) + "\\n")

            if "build" in args and mode == "build_fail":
                print("Fake build failure", file=sys.stderr)
                sys.exit(65)
            if "test" in args and mode == "test_fail":
                print("Fake test failure", file=sys.stderr)
                sys.exit(65)

            print("Fake xcodebuild success")
            sys.exit(0)
            """
        ),
    )

    write_executable(
        fake_bin_dir / "ssh",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys

            args = sys.argv[1:]
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("ssh " + " ".join(args) + "\\n")

            mode = os.environ.get("FAKE_SSH_MODE", "fail_probes")
            full_command = " ".join(args)

            if "probe_machine.py --probe-local" in full_command:
                if mode == "remote_ok":
                    payload = {
                        "machine": "mac2-ssh",
                        "reachable": True,
                        "hw": {"cpu_model": "M1", "logical_cores": 8, "physical_cores": 8, "total_mem_gb": 16},
                        "cpu_load_1m": 0.4,
                        "cpu_load_5m": 0.4,
                        "mem_free_mb": 14000,
                        "mem_pressure": "normal",
                        "disk_free_gb": 100,
                        "disk_total_gb": 100,
                        "active_xcodebuild_count": 0,
                        "active_simulator_count": 0,
                        "active_ai_jobs": 0,
                        "repo_exists": True,
                        "repo_path_ok": True,
                        "git_branch": "main",
                        "git_head_hash": "abc",
                        "git_dirty": False,
                        "binaries": {"gemini": True, "claude": True, "codex": True, "gh": True, "ollama": True, "opencode": True, "xcodebuild": True, "firebase": True},
                        "stale_processes": [],
                        "timestamp": "2026-04-23T21:00:00-05:00",
                        "supports_xcode": True
                    }
                    print(json.dumps(payload))
                    sys.exit(0)

                print("fake ssh probe failure", file=sys.stderr)
                sys.exit(255)

            sys.exit(0)
            """
        ),
    )

    write_executable(
        fake_bin_dir / "scp",
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import sys

            args = sys.argv[1:]
            log_path = os.environ.get("FAKE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("scp " + " ".join(args) + "\\n")
            sys.exit(0)
            """
        ),
    )


def run_subprocess(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    stdin_text: str = "",
) -> subprocess.CompletedProcess[str]:
    # Stream to stdout/stderr so the parent (dev_console) can show progress
    print(f"      [exec] {' '.join(args)}")
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        input=stdin_text,
        text=True,
        capture_output=False,
        stdout=sys.stdout,
        stderr=sys.stderr,
        check=False,
    )


def read_single_job(runtime_dir: Path) -> dict:
    jobs = sorted((runtime_dir / "jobs").glob("*.json"))
    if len(jobs) != 1:
        raise AssertionError(f"Expected exactly one job file, found {len(jobs)}")
    return json.loads(jobs[0].read_text(encoding="utf-8"))


def expected_branch(issue_number: int, title: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().strip()).strip("-")[:60]
    return f"ai/issue-{issue_number}-{slug}"


def assert_log_contains(log_path: Path, needle: str) -> None:
    text = log_path.read_text(encoding="utf-8")
    if needle not in text:
        raise AssertionError(f"Missing log entry: {needle}\n\n{text}")


def create_fixture_project(temp_dir: Path) -> Path:
    project_root = temp_dir / "SwiftFixture"
    (project_root / "MyApp.xcodeproj").mkdir(parents=True)
    (project_root / "MyApp").mkdir()
    (project_root / "MyAppTests").mkdir()
    (project_root / "docs").mkdir()
    (project_root / "AGENTS.md").write_text("Use MVVM and keep changes focused.\n", encoding="utf-8")
    (project_root / "docs" / "architecture.md").write_text("Fixture architecture docs.\n", encoding="utf-8")
    (project_root / "docs" / "coding-standards.md").write_text("Fixture coding standards.\n", encoding="utf-8")
    (project_root / "docs" / "build-test-commands.md").write_text(
        """# Build and Test

## iOS app build
```bash
xcodebuild build -project MyApp.xcodeproj -scheme MyApp
```

## iOS app tests
```bash
xcodebuild test -project MyApp.xcodeproj -scheme MyApp
```
""",
        encoding="utf-8",
    )
    (project_root / "MyApp" / "SettingsViewModel.swift").write_text("final class SettingsViewModel {}\n", encoding="utf-8")
    (project_root / "MyApp" / "DetailView.swift").write_text("struct DetailView {}\n", encoding="utf-8")
    (project_root / "MyAppTests" / "SettingsViewModelTests.swift").write_text(
        "import XCTest\nfinal class SettingsViewModelTests: XCTestCase {}\n",
        encoding="utf-8",
    )

    # Add distribution scripts for Firebase verification
    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "ExportOptions.plist").write_text("<plist></plist>", encoding="utf-8")
    write_executable(
        scripts_dir / "distribute_ios.sh",
        "#!/bin/bash\necho 'Mock distribution successful'\nexit 0\n"
    )

    return project_root


def scenario_env(base_env: dict[str, str], project_root: Path, runtime_dir: Path, fake_bin_dir: Path, log_path: Path) -> dict[str, str]:
    env = dict(base_env)
    env["ORCHESTRATOR_PROJECT_ROOT"] = str(project_root)
    env["ORCHESTRATOR_RUNTIME_DIR"] = str(runtime_dir)
    env["ORCHESTRATOR_FAKE_DISK_FREE_GB"] = "100"
    env["ORCHESTRATOR_DISABLE_NOTIFICATIONS"] = "1"
    env["FAKE_LOG_PATH"] = str(log_path)
    env["PYTHONPATH"] = f"{PACKAGE_ROOT.parent}:{env.get('PYTHONPATH', '')}"
    env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
    
    # 1. Create mock machines.json
    config_dir = runtime_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    machines_json = {
        "version": 1,
        "machines": [
            {
                "name": "mac1",
                "enabled": True,
                "execution_mode": "local",
                "ssh_target": None,
                "repo_path": str(project_root),
                "roles": ["planner", "reviewer", "worker", "build", "test"],
                "models": ["gemini-3.1-pro-preview", "gpt-5.4", "claude-sonnet-4-6", "gemini", "codex", "claude"],
                "priority": 100,
                "max_concurrent_jobs": 2,
                "max_heavy_jobs": 1,
                "supports_xcode": True,
                "supports_simulator": True,
                "supports_backend_tests": True,
                "interactive_reserved": False,
                "tags": ["interactive"]
            },
            {
                "name": "mac2-ssh",
                "enabled": True,
                "execution_mode": "ssh",
                "ssh_target": "leemo",
                "repo_path": "/fake/remote/repo",
                "roles": ["worker", "build", "test"],
                "models": ["gemini-3.1-pro-preview", "gpt-5.4", "claude-sonnet-4-6", "gemini", "codex", "claude"],
                "priority": 90,
                "max_concurrent_jobs": 2,
                "max_heavy_jobs": 1,
                "supports_xcode": True,
                "supports_simulator": True,
                "supports_backend_tests": True,
                "interactive_reserved": False,
                "tags": ["remote"]
            }
        ]
    }
    (config_dir / "machines.json").write_text(json.dumps(machines_json), encoding="utf-8")
    
    return env


def run_local_bug_scenario(name: str, xcode_mode: str, expected_status: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{name}-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        runtime_dir = temp_dir / "runtime"
        project_root = create_fixture_project(temp_dir)
        fake_bin_dir = temp_dir / "fake-bin"
        log_path = temp_dir / "commands.log"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        create_fake_binaries(fake_bin_dir)

        env = scenario_env(os.environ, project_root, runtime_dir, fake_bin_dir, log_path)
        env["FAKE_SSH_MODE"] = "fail_probes"
        env["FAKE_XCODEBUILD_MODE"] = xcode_mode

        result = run_subprocess(
            [sys.executable, str(SCRIPTS_DIR / "new_job.py"), "bug"],
            env=env,
            cwd=project_root,
            stdin_text="Display name in the detail view stays stale after editing it in settings.",
        )
        if result.returncode != 0:
            raise AssertionError(f"{name} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        job = read_single_job(runtime_dir)
        assert job["issue_number"] == 9001, job
        assert job["assigned_machine"] == "mac1", job
        assert job["assigned_model"] == "gpt-5.4", job
        assert job["branch"] == expected_branch(job["issue_number"], job["title"]), job
        assert job["task_groups"][0]["status"] == "scheduled", job
        assert job["status"] == expected_status, job

        if expected_status == "review-needed":
            assert job["pr_number"] == 7001, job
            assert_log_contains(log_path, "gh pr create")
            assert_log_contains(log_path, "xcodebuild build")
            assert_log_contains(log_path, "xcodebuild test")
        else:
            assert job["pr_number"] is None, job
            assert_log_contains(log_path, "build-analysis-agent-trigger")

        assert_log_contains(log_path, "gh issue create")
        assert_log_contains(log_path, "git fetch origin")
        assert_log_contains(log_path, "codex")

        print(f"Scenario {name} passed. Final status: {job['status']}.")


def run_local_feature_scenario() -> None:
    name = "local-feature-success"
    with tempfile.TemporaryDirectory(prefix=f"{name}-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        runtime_dir = temp_dir / "runtime"
        project_root = create_fixture_project(temp_dir)
        fake_bin_dir = temp_dir / "fake-bin"
        log_path = temp_dir / "commands.log"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        create_fake_binaries(fake_bin_dir)

        env = scenario_env(os.environ, project_root, runtime_dir, fake_bin_dir, log_path)
        env["FAKE_SSH_MODE"] = "fail_probes"
        env["FAKE_XCODEBUILD_MODE"] = "success"

        result = run_subprocess(
            [sys.executable, str(SCRIPTS_DIR / "new_job.py"), "feature"],
            env=env,
            cwd=project_root,
            stdin_text="Add a dark mode toggle to the settings screen.",
        )
        if result.returncode != 0:
            raise AssertionError(f"{name} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        job = read_single_job(runtime_dir)
        assert job["issue_number"] == 9001, job
        assert job["type"] == "feature-plan", job
        assert job["status"] == "review-needed", job
        assert job["pr_number"] == 7001, job

        print("Scenario local-feature-success passed.")


def run_remote_dispatch_scenario() -> None:
    with tempfile.TemporaryDirectory(prefix="remote-dispatch-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        runtime_dir = temp_dir / "runtime"
        project_root = create_fixture_project(temp_dir)
        fake_bin_dir = temp_dir / "fake-bin"
        log_path = temp_dir / "commands.log"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        create_fake_binaries(fake_bin_dir)

        env = scenario_env(os.environ, project_root, runtime_dir, fake_bin_dir, log_path)
        env["FAKE_SSH_MODE"] = "remote_ok"
        env["FAKE_XCODEBUILD_MODE"] = "success"

        result = run_subprocess(
            [sys.executable, str(SCRIPTS_DIR / "new_job.py"), "bug", "--allowed-machines", "mac2-ssh"],
            env=env,
            cwd=project_root,
            stdin_text="Dispatch this bug remotely.",
        )
        if result.returncode != 0:
            raise AssertionError(f"remote-dispatch failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        job = read_single_job(runtime_dir)
        assert job["issue_number"] == 9001, job
        assert job["assigned_machine"] == "mac2-ssh", job
        assert job["assigned_model"] == "gpt-5.4", job
        assert job["status"] == "planned", job
        assert job["task_groups"][0]["status"] == "scheduled", job

        assert_log_contains(log_path, "ssh leemo")
        assert_log_contains(log_path, "scp")
        assert_log_contains(log_path, "gh issue create")
        assert_log_contains(log_path, "gemini")

        print("Scenario remote-dispatch passed. Remote probe and dispatch subprocess paths executed.")


def run_resume_scenario() -> None:
    with tempfile.TemporaryDirectory(prefix="resume-smoke-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        runtime_dir = temp_dir / "runtime"
        project_root = create_fixture_project(temp_dir)
        fake_bin_dir = temp_dir / "fake-bin"
        log_path = temp_dir / "commands.log"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        
        (runtime_dir / "jobs").mkdir(parents=True, exist_ok=True)
        (runtime_dir / "output").mkdir(parents=True, exist_ok=True)
        (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)

        create_fake_binaries(fake_bin_dir)

        job_id = "20260428-resume-test"
        job_file = runtime_dir / "jobs" / f"{job_id}.json"
        job_data = {
            "job_id": job_id,
            "type": "bug-fix",
            "issue_number": 123,
            "title": "Resume Test",
            "status": "executing",
            "builder": "codex",
            "planner": "gemini",
            "reviewer": "gemini",
            "branch": "ai/resume-test",
            "allowed_models": ["gemini", "codex"],
            "plan": {
                "summary": "test",
                "repro_steps": ["step 1"],
                "expected_behavior": "expected",
                "acceptance_criteria": ["criteria 1"],
                "constraints": ["constraint 1"],
                "likely_files": ["file 1"]
            }
        }
        job_file.write_text(json.dumps(job_data), encoding="utf-8")

        output_dir = runtime_dir / "output" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_file = output_dir / "builder_summary.md"
        summary_file.write_text("Previous AI thinking results", encoding="utf-8")

        env = os.environ.copy()
        env["ORCHESTRATOR_PROJECT_ROOT"] = str(project_root)
        env["ORCHESTRATOR_RUNTIME_DIR"] = str(runtime_dir)
        env["ORCHESTRATOR_DISABLE_NOTIFICATIONS"] = "1"
        env["FAKE_LOG_PATH"] = str(log_path)
        env["PYTHONPATH"] = f"{PACKAGE_ROOT.parent}:{env.get('PYTHONPATH', '')}"
        env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
        env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"

        print(f"      - Running worker_run.py --resume for job {job_id}...")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "worker_run.py"), str(job_file), "--resume"],
            cwd=str(project_root),
            env=env,
            text=True,
            capture_output=False,
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=False,
        )

        if result.returncode != 0:
            raise AssertionError(f"Resume smoke test failed with code {result.returncode}")

        commands_log = log_path.read_text(encoding="utf-8")
        
        # Verify Builder LLM (codex) was NOT called
        if "codex " in commands_log:
            raise AssertionError(f"Builder LLM (codex) was called despite resume mode!\nLog:\n{commands_log}")
            
        # Verify xcodebuild WAS called
        if "xcodebuild " not in commands_log:
            raise AssertionError(f"xcodebuild was NOT called despite resume mode!\nLog:\n{commands_log}")

        # Verify Review LLM (gemini) WAS called
        if "gemini " not in commands_log:
             raise AssertionError(f"Review LLM (gemini) was NOT called!\nLog:\n{commands_log}")

        print("Scenario resume passed. Builder LLM skipped and build/test/review executed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run subprocess-level smoke tests for the AI workflow using fake CLI tools on PATH."
    )
    parser.add_argument(
        "--scenario",
        choices=["local-success", "local-feature-success", "local-build-fail", "local-test-fail", "remote-dispatch", "resume", "all"],
        default="all",
    )
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario != "all" else [
        "local-success",
        "local-feature-success",
        "local-build-fail",
        "local-test-fail",
        "remote-dispatch",
        "resume",
    ]

    for scenario in scenarios:
        if scenario == "local-success":
            run_local_bug_scenario("local-success", "success", "review-needed")
        elif scenario == "local-feature-success":
            run_local_feature_scenario()
        elif scenario == "local-build-fail":
            run_local_bug_scenario("local-build-fail", "build_fail", "debugging")
        elif scenario == "local-test-fail":
            run_local_bug_scenario("local-test-fail", "test_fail", "debugging")
        elif scenario == "remote-dispatch":
            run_remote_dispatch_scenario()
        elif scenario == "resume":
            run_resume_scenario()
        else:
            raise ValueError(f"Unsupported scenario: {scenario}")


if __name__ == "__main__":
    main()

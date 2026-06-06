from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from orchestrator.project_config import DEFAULT_RUNTIME_DIRNAME, find_project_root
from orchestrator.project_config import load_project_config
from orchestrator.config_validation import validate_machine_config, validate_project_config


RUNTIME_GITIGNORE = """# Generated Swift Orchestrator runtime output
jobs/
logs/
output/
state/
*.pyc
__pycache__/
"""


def write_text_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        print(f"Already exists: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


def run_json_command(args: list[str], root: Path) -> dict:
    try:
        result = subprocess.run(
            args,
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def infer_xcode(root: Path) -> tuple[str | None, str | None, str, list[str], list[str]]:
    xcode_project = next(iter(sorted(root.glob("*.xcodeproj"))), None)
    xcode_workspace = next(iter(sorted(root.glob("*.xcworkspace"))), None)
    args = ["xcodebuild", "-list", "-json"]
    if xcode_workspace:
        args.extend(["-workspace", xcode_workspace.name])
    elif xcode_project:
        args.extend(["-project", xcode_project.name])
    data = run_json_command(args, root) if (xcode_project or xcode_workspace) else {}
    container = data.get("workspace") or data.get("project") or {}
    schemes = sorted(container.get("schemes") or [])
    targets = sorted(container.get("targets") or [])
    fallback_scheme = (xcode_project or xcode_workspace).stem if (xcode_project or xcode_workspace) else root.name
    scheme = schemes[0] if schemes else fallback_scheme
    return (
        xcode_project.name if xcode_project else None,
        xcode_workspace.name if xcode_workspace else None,
        scheme,
        schemes,
        targets,
    )


def git_remote(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def build_test_docs(config: dict) -> str:
    if config["build_command"]:
        build_command = config["build_command"]
    elif config["xcode_workspace"]:
        build_command = f"xcodebuild build -workspace {config['xcode_workspace']} -scheme {config['scheme']}"
    elif config["xcode_project"]:
        build_command = f"xcodebuild build -project {config['xcode_project']} -scheme {config['scheme']}"
    else:
        build_command = "swift build"

    if config["test_command"]:
        test_command = config["test_command"]
    elif config["xcode_workspace"]:
        test_command = f"xcodebuild test -workspace {config['xcode_workspace']} -scheme {config['scheme']}"
    elif config["xcode_project"]:
        test_command = f"xcodebuild test -project {config['xcode_project']} -scheme {config['scheme']}"
    else:
        test_command = "swift test"

    return f"""# Build And Test Commands

Canonical validation commands for this project.

## iOS app build

```bash
{build_command}
```

## iOS app tests

```bash
{test_command}
```

## Orchestrator config check

```bash
swift-orchestrator check-config
```
"""


def ai_workflow_docs(project_name: str) -> str:
    return f"""# AI Workflow

Use `swift-orchestrator console` from the repository root to create and manage jobs for {project_name}.

Recommended flow:

1. Run `swift-orchestrator check` after initial setup or toolchain changes.
2. Run `swift-orchestrator check-config` after editing `.swift-orchestrator/project.json` or machine config.
3. Create jobs from the console.
4. Review generated branches and pull requests before merging.
5. Keep generated `.swift-orchestrator/jobs/`, `logs/`, `output/`, and `state/` files out of Git.
"""


def agents_docs(project_name: str) -> str:
    return f"""# AGENTS.md

Repository guidance for coding agents working on {project_name}.

- Use `docs/build-test-commands.md` for canonical validation commands.
- Prefer minimal, reviewable diffs.
- Do not modify unrelated files.
- Do not commit secrets, generated runtime logs, or unrelated environment changes.
- Run `swift-orchestrator check-config` after changing `.swift-orchestrator/project.json`.
"""


def helper_script() -> str:
    return """#!/usr/bin/env sh
set -eu
exec swift-orchestrator "$@"
"""


def write_starter_docs(root: Path, config: dict, force: bool) -> None:
    write_text_file(root / "docs" / "build-test-commands.md", build_test_docs(config), force)
    write_text_file(root / "docs" / "ai-workflow.md", ai_workflow_docs(config["project_name"]), force)
    write_text_file(root / "AGENTS.md", agents_docs(config["project_name"]), force)


def write_helper_script(root: Path, force: bool) -> None:
    script_path = root / "scripts" / "orchestrator"
    write_text_file(script_path, helper_script(), force)
    script_path.chmod(script_path.stat().st_mode | 0o111)


def init_project(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve() if args.root else find_project_root()
    runtime_dir = root / DEFAULT_RUNTIME_DIRNAME
    config_dir = runtime_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ["jobs/inbox", "jobs/archive", "logs", "output", "state/machines"]:
        (runtime_dir / subdir).mkdir(parents=True, exist_ok=True)

    xcode_project, xcode_workspace, detected_scheme, detected_schemes, detected_targets = infer_xcode(root)
    project_name = args.project_name or root.name
    scheme = args.scheme or detected_scheme
    test_target = args.test_target or next((target for target in detected_targets if target.endswith("Tests")), f"{scheme}Tests")
    config = {
        "project_name": project_name,
        "base_branch": args.base_branch,
        "pr_base_branch": args.base_branch,
        "branch_prefix": "ai/issue",
        "git_remote": git_remote(root),
        "xcode_project": xcode_project,
        "xcode_workspace": xcode_workspace,
        "scheme": scheme,
        "detected_schemes": detected_schemes,
        "test_target": test_target,
        "detected_targets": detected_targets,
        "derived_data_path": f"/tmp/{project_name.lower()}_orchestrator_dd",
        "build_command": None,
        "test_command": None,
        "backend_test_command": None,
        "app_bundle_id": None,
        "visual_app_path": None,
        "delivery_provider": None,
        "distribution_script_path": None,
        "firebase_plist_path": None,
        "remote_package_install_path": "~/.swift-orchestrator/package",
        "firebase_distribution": False,
        "notification_display_name": f"{project_name} AI Orchestrator",
    }

    project_file = runtime_dir / "project.json"
    if project_file.exists() and not args.force:
        print(f"Project config already exists: {project_file}")
    else:
        project_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"Created {project_file}")

    machines_file = config_dir / "machines.json"
    if not machines_file.exists() or args.force:
        machines_file.write_text(json.dumps({
            "version": 1,
            "machines": [
                {
                    "name": "local",
                    "enabled": True,
                    "execution_mode": "local",
                    "ssh_target": None,
                    "repo_path": str(root),
                    "roles": ["planner", "reviewer", "worker", "build", "test"],
                    "models": ["gemini", "codex", "claude"],
                    "priority": 100,
                    "max_concurrent_jobs": 1,
                    "max_heavy_jobs": 1,
                    "supports_xcode": True,
                    "supports_simulator": True,
                    "supports_backend_tests": False,
                    "interactive_reserved": True,
                    "tags": ["interactive", "primary"],
                }
            ],
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Created {machines_file}")

    settings_file = config_dir / "settings.json"
    if not settings_file.exists() or args.force:
        settings_file.write_text(json.dumps({
            "notification_emails": [],
            "notification_provider": "resend",
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Created {settings_file}")

    gitignore_file = runtime_dir / ".gitignore"
    if not gitignore_file.exists() or args.force:
        gitignore_file.write_text(RUNTIME_GITIGNORE, encoding="utf-8")
        print(f"Created {gitignore_file}")

    if args.with_starter_docs:
        write_starter_docs(root, config, args.force)

    if args.with_helper_script:
        write_helper_script(root, args.force)

    print("Run: swift-orchestrator check")
    return 0


def validate_config_command() -> int:
    config = load_project_config()
    errors = validate_project_config(config)
    errors.extend(validate_machine_config(config.config_dir))
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Configuration OK")
    return 0


def run_script(script_name: str, script_args: list[str]) -> int:
    scripts_dir = Path(__file__).resolve().parent / "scripts"
    env = os.environ.copy()
    env.setdefault("SWIFT_ORCHESTRATOR_PROJECT_ROOT", str(find_project_root()))
    return subprocess.call([sys.executable, str(scripts_dir / script_name), *script_args], env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swift-orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--root")
    init_parser.add_argument("--project-name")
    init_parser.add_argument("--scheme")
    init_parser.add_argument("--test-target")
    init_parser.add_argument("--base-branch", default="main")
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--with-starter-docs", action="store_true")
    init_parser.add_argument("--with-helper-script", action="store_true")

    subparsers.add_parser("console")
    subparsers.add_parser("check")
    subparsers.add_parser("check-config")
    worker_check = subparsers.add_parser("worker-check")
    worker_check.add_argument("--machine")
    worker_install = subparsers.add_parser("worker-install")
    worker_install.add_argument("--machine")

    passthrough = subparsers.add_parser("script")
    passthrough.add_argument("script_name")
    passthrough.add_argument("script_args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    if args.command == "init":
        return init_project(args)
    if args.command == "console":
        return run_script("dev_console.py", [])
    if args.command == "check":
        return run_script("check_setup.py", [])
    if args.command == "check-config":
        return validate_config_command()
    if args.command == "worker-check":
        script_args = ["check"]
        if args.machine:
            script_args.extend(["--machine", args.machine])
        return run_script("worker_tools.py", script_args)
    if args.command == "worker-install":
        script_args = ["install"]
        if args.machine:
            script_args.extend(["--machine", args.machine])
        return run_script("worker_tools.py", script_args)
    if args.command == "script":
        return run_script(args.script_name, args.script_args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

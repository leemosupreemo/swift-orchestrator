from __future__ import annotations

import argparse
import json
import os
import shutil
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


def write_starter_docs(root: Path, config: dict, force: bool) -> list[Path]:
    paths = [
        root / "AGENTS.md",
        root / "docs" / "build-test-commands.md",
        root / "docs" / "ai-workflow.md",
    ]
    write_text_file(paths[1], build_test_docs(config), force)
    write_text_file(paths[2], ai_workflow_docs(config["project_name"]), force)
    write_text_file(paths[0], agents_docs(config["project_name"]), force)
    return paths


def write_helper_script(root: Path, force: bool) -> Path:
    script_path = root / "scripts" / "orchestrator"
    write_text_file(script_path, helper_script(), force)
    script_path.chmod(script_path.stat().st_mode | 0o111)
    return script_path


def read_json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {path}")


def prompt_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def prompt_yes_no(label: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_ssh_machine(value: str) -> dict:
    try:
        name, rest = value.split("=", 1)
        ssh_target, repo_path = rest.split(":", 1)
    except ValueError as exc:
        raise ValueError("--ssh-machine must use NAME=SSH_TARGET:/absolute/repo/path") from exc
    if not name or not ssh_target or not repo_path.startswith("/"):
        raise ValueError("--ssh-machine must use NAME=SSH_TARGET:/absolute/repo/path")
    return {
        "name": name,
        "enabled": True,
        "execution_mode": "ssh",
        "ssh_target": ssh_target,
        "repo_path": repo_path,
        "orchestrator_package_path": "~/.swift-orchestrator/package",
        "orchestrator_runtime_dir": ".swift-orchestrator",
        "roles": ["worker", "build", "test"],
        "models": [],
        "priority": 90,
        "max_concurrent_jobs": 1,
        "max_heavy_jobs": 1,
        "supports_xcode": True,
        "supports_simulator": True,
        "supports_backend_tests": False,
        "interactive_reserved": False,
        "tags": ["remote"],
    }


def copy_prompt_overrides(root: Path, force: bool) -> list[Path]:
    prompts_source = Path(__file__).resolve().parent / "prompts"
    prompts_dest = root / DEFAULT_RUNTIME_DIRNAME / "prompts"
    prompts_dest.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for prompt_file in sorted(prompts_source.glob("*.md")):
        dest = prompts_dest / prompt_file.name
        if dest.exists() and not force:
            print(f"Already exists: {dest}")
            copied.append(dest)
            continue
        shutil.copyfile(prompt_file, dest)
        print(f"Created {dest}")
        copied.append(dest)
    return copied


def update_machine_models(config_dir: Path, models: list[str], ssh_machines: list[dict]) -> None:
    machines_file = config_dir / "machines.json"
    machines_config = read_json_file(machines_file)
    existing = {machine["name"]: machine for machine in machines_config.get("machines", [])}
    for machine in existing.values():
        machine["models"] = models
    for machine in ssh_machines:
        machine["models"] = models
        existing[machine["name"]] = machine
    machines_config["machines"] = list(existing.values())
    write_json_file(machines_file, machines_config)


def update_firebase_config(
    project_file: Path,
    enabled: bool,
    distribution_script_path: str | None,
    firebase_plist_path: str | None,
) -> None:
    config = read_json_file(project_file)
    config["firebase_distribution"] = enabled
    config["delivery_provider"] = "firebase" if enabled else None
    config["distribution_script_path"] = distribution_script_path if enabled else None
    config["firebase_plist_path"] = firebase_plist_path if enabled else None
    write_json_file(project_file, config)


def verify_wizard_setup(install_workers: list[str]) -> int:
    check_result = run_script("check_setup.py", [])
    config_result = validate_config_command()
    worker_failures = 0
    for machine_name in install_workers:
        install_result = run_script("worker_tools.py", ["install", "--machine", machine_name])
        check_worker_result = run_script("worker_tools.py", ["check", "--machine", machine_name])
        if install_result != 0 or check_worker_result != 0:
            worker_failures += 1
    return 1 if check_result != 0 or config_result != 0 or worker_failures else 0


def run_wizard(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve() if args.root else find_project_root()
    models = parse_csv(args.models)
    if args.non_interactive and not models:
        print("Wizard requires at least one model. Pass --models codex or run interactively.")
        return 1
    if args.non_interactive and args.firebase and (not args.distribution_script_path or not args.firebase_plist_path):
        print("Firebase setup requires --distribution-script-path and --firebase-plist-path.")
        return 1

    try:
        ssh_machines = [parse_ssh_machine(value) for value in args.ssh_machine]
    except ValueError as exc:
        print(str(exc))
        return 1

    runtime_dir = root / DEFAULT_RUNTIME_DIRNAME
    project_file = runtime_dir / "project.json"
    needs_init = args.force or not project_file.exists()
    review_paths: list[Path] = []
    if needs_init:
        init_args = argparse.Namespace(
            root=str(root),
            project_name=args.project_name,
            scheme=args.scheme,
            test_target=args.test_target,
            base_branch=args.base_branch,
            force=args.force,
            with_starter_docs=True,
            with_helper_script=True,
        )
        init_project(init_args)
        review_paths.extend([
            root / "AGENTS.md",
            root / "docs" / "build-test-commands.md",
            root / "docs" / "ai-workflow.md",
        ])
    else:
        review_paths.extend(write_starter_docs(root, read_json_file(project_file), args.force))
        write_helper_script(root, args.force)

    if not models and not args.non_interactive:
        print("\nChoose at least one LLM/model alias. Examples: codex, gemini, claude")
        models = parse_csv(prompt_text("Models", "codex"))
    if not models:
        print("Wizard requires at least one model. Pass --models codex or run interactively.")
        return 1

    copy_prompts = args.copy_prompt_overrides
    if not copy_prompts and not args.non_interactive:
        copy_prompts = prompt_yes_no("Copy role prompt .md files into .swift-orchestrator/prompts for project editing?", True)
    if copy_prompts:
        review_paths.extend(copy_prompt_overrides(root, args.force))

    if not args.non_interactive and prompt_yes_no("Add an SSH worker machine now?", False):
        name = prompt_text("Machine name", "mac2")
        target = prompt_text("SSH target", name)
        repo_path = prompt_text("Remote repo path")
        try:
            ssh_machines.append(parse_ssh_machine(f"{name}={target}:{repo_path}"))
        except ValueError as exc:
            print(str(exc))
            return 1
    update_machine_models(runtime_dir / "config", models, ssh_machines)

    firebase_enabled = args.firebase
    distribution_script_path = args.distribution_script_path
    firebase_plist_path = args.firebase_plist_path
    if not firebase_enabled and not args.non_interactive:
        firebase_enabled = prompt_yes_no("Configure Firebase distribution now?", False)
    if firebase_enabled:
        distribution_script_path = distribution_script_path or (
            None if args.non_interactive else prompt_text("Distribution script path", "scripts/distribute_ios.sh")
        )
        firebase_plist_path = firebase_plist_path or (
            None if args.non_interactive else prompt_text("Firebase plist path", f"{root.name}/GoogleService-Info.plist")
        )
        if not distribution_script_path or not firebase_plist_path:
            print("Firebase setup requires --distribution-script-path and --firebase-plist-path.")
            return 1
    update_firebase_config(project_file, firebase_enabled, distribution_script_path, firebase_plist_path)

    print("\nFirst-run wizard complete.")
    print("Review these Markdown/config files before creating jobs:")
    for path in [
        *review_paths,
        runtime_dir / "project.json",
        runtime_dir / "config" / "machines.json",
        runtime_dir / "config" / "settings.json",
    ]:
        print(f"  - {path.relative_to(root)}")
    print("Run: swift-orchestrator check")
    print("Run: swift-orchestrator check-config")
    install_workers = [machine["name"] for machine in ssh_machines] if args.install_workers else []
    if not args.non_interactive and ssh_machines and not install_workers:
        if prompt_yes_no("Install/check SSH worker packages now?", False):
            install_workers = [machine["name"] for machine in ssh_machines]
    if args.verify or install_workers:
        return verify_wizard_setup(install_workers)
    return 0


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

    wizard_parser = subparsers.add_parser("wizard")
    wizard_parser.add_argument("--root")
    wizard_parser.add_argument("--project-name")
    wizard_parser.add_argument("--scheme")
    wizard_parser.add_argument("--test-target")
    wizard_parser.add_argument("--base-branch", default="main")
    wizard_parser.add_argument("--force", action="store_true")
    wizard_parser.add_argument("--models", help="Comma-separated model aliases or model IDs, for example codex,gemini")
    wizard_parser.add_argument("--copy-prompt-overrides", action="store_true")
    wizard_parser.add_argument("--ssh-machine", action="append", default=[], help="Add SSH worker as NAME=SSH_TARGET:/absolute/repo/path")
    wizard_parser.add_argument("--firebase", action="store_true")
    wizard_parser.add_argument("--distribution-script-path")
    wizard_parser.add_argument("--firebase-plist-path")
    wizard_parser.add_argument("--verify", action="store_true", help="Run setup and config checks before exiting")
    wizard_parser.add_argument("--install-workers", action="store_true", help="Run worker install/check for SSH machines added by this wizard")
    wizard_parser.add_argument("--non-interactive", action="store_true")

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
    if args.command == "wizard":
        return run_wizard(args)
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

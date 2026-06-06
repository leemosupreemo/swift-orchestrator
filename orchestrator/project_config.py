from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_RUNTIME_DIRNAME = ".swift-orchestrator"


def find_project_root(start: Path | None = None) -> Path:
    explicit = os.environ.get("SWIFT_ORCHESTRATOR_PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
        if any(candidate.glob("*.xcodeproj")) or any(candidate.glob("*.xcworkspace")):
            return candidate
    return current


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _first_match(root: Path, pattern: str) -> str | None:
    matches = sorted(root.glob(pattern))
    return matches[0].name if matches else None


def _git_remote(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


@dataclass(frozen=True)
class ProjectConfig:
    root: Path
    runtime_dir: Path
    package_prompts_dir: Path
    project_name: str
    base_branch: str
    git_remote: str | None
    xcode_project: str | None
    xcode_workspace: str | None
    scheme: str | None
    test_target: str
    derived_data_path: str
    build_command: str | None
    test_command: str | None
    app_bundle_id: str | None
    backend_test_command: str | None
    branch_prefix: str
    pr_base_branch: str
    delivery_provider: str | None
    distribution_script_path: str | None
    firebase_plist_path: str | None
    visual_app_path: str | None
    remote_package_install_path: str
    firebase_distribution: bool
    notification_display_name: str

    @property
    def config_dir(self) -> Path:
        return self.runtime_dir / "config"

    @property
    def prompts_dir(self) -> Path:
        project_prompts = self.runtime_dir / "prompts"
        return project_prompts if project_prompts.exists() else self.package_prompts_dir


def load_project_config() -> ProjectConfig:
    root = find_project_root()
    config_path = os.environ.get("SWIFT_ORCHESTRATOR_CONFIG")
    if config_path:
        config_file = Path(config_path).expanduser().resolve()
    else:
        config_file = root / DEFAULT_RUNTIME_DIRNAME / "project.json"

    data = _load_json(config_file)
    runtime_dir = Path(
        os.environ.get(
            "SWIFT_ORCHESTRATOR_RUNTIME_DIR",
            os.environ.get("AI_RUNTIME_DIR", str(root / DEFAULT_RUNTIME_DIRNAME)),
        )
    ).expanduser()
    if not runtime_dir.is_absolute():
        runtime_dir = root / runtime_dir
    runtime_dir = runtime_dir.resolve()

    project_name = data.get("project_name") or root.name
    xcode_project = data.get("xcode_project") or _first_match(root, "*.xcodeproj")
    xcode_workspace = data.get("xcode_workspace") or _first_match(root, "*.xcworkspace")
    scheme = data.get("scheme") or (Path(xcode_project).stem if xcode_project else project_name)
    test_target = data.get("test_target") or f"{scheme}Tests"
    derived_data_path = data.get("derived_data_path") or f"/tmp/{project_name.lower()}_orchestrator_dd"

    return ProjectConfig(
        root=root,
        runtime_dir=runtime_dir,
        package_prompts_dir=PACKAGE_ROOT / "prompts",
        project_name=project_name,
        base_branch=data.get("base_branch", "main"),
        git_remote=data.get("git_remote") or _git_remote(root),
        xcode_project=xcode_project,
        xcode_workspace=xcode_workspace,
        scheme=scheme,
        test_target=test_target,
        derived_data_path=derived_data_path,
        build_command=data.get("build_command"),
        test_command=data.get("test_command"),
        app_bundle_id=data.get("app_bundle_id"),
        backend_test_command=data.get("backend_test_command"),
        branch_prefix=data.get("branch_prefix", "ai/issue"),
        pr_base_branch=data.get("pr_base_branch", data.get("base_branch", "main")),
        delivery_provider=data.get("delivery_provider"),
        distribution_script_path=data.get("distribution_script_path"),
        firebase_plist_path=data.get("firebase_plist_path"),
        visual_app_path=data.get("visual_app_path"),
        remote_package_install_path=data.get("remote_package_install_path", "~/.swift-orchestrator/package"),
        firebase_distribution=bool(data.get("firebase_distribution", False)),
        notification_display_name=data.get("notification_display_name", f"{project_name} AI Orchestrator"),
    )


PROJECT_CONFIG = load_project_config()

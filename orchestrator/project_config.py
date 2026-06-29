from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_RUNTIME_DIRNAME = ".orchestrator"
USER_STATE_DIR_ENV = "ORCHESTRATOR_USER_STATE_DIR"


def user_state_dir() -> Path:
    explicit = os.environ.get(USER_STATE_DIR_ENV)
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (Path.home() / ".orchestrator").resolve()


def recent_projects_path() -> Path:
    return user_state_dir() / "projects.json"


def load_recent_projects() -> dict[str, Any]:
    path = recent_projects_path()
    if not path.exists():
        return {"version": 1, "active": None, "projects": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "active": None, "projects": []}
    data.setdefault("version", 1)
    data.setdefault("active", None)
    data.setdefault("projects", [])
    return data


def save_recent_projects(data: dict[str, Any]) -> None:
    path = recent_projects_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def project_display_name(root: Path) -> str:
    config_path = root / DEFAULT_RUNTIME_DIRNAME / "project.json"
    data = _load_json(config_path)
    return data.get("project_name") or root.name


def remember_project(root: Path, name: str | None = None, active: bool = True) -> None:
    root = root.expanduser().resolve()
    display_name = name or project_display_name(root)
    data = load_recent_projects()
    projects = [
        project for project in data.get("projects", [])
        if Path(project.get("root", "")).expanduser().resolve() != root
        and project.get("name") != display_name
    ]
    projects.insert(0, {"name": display_name, "root": str(root)})
    data["projects"] = projects[:20]
    if active:
        data["active"] = display_name
    save_recent_projects(data)


def resolve_project_reference(reference: str | None) -> Path | None:
    if not reference:
        return None
    candidate = Path(reference).expanduser()
    if candidate.exists() or "/" in reference or reference.startswith("."):
        return candidate.resolve()
    data = load_recent_projects()
    for project in data.get("projects", []):
        if project.get("name") == reference:
            return Path(project["root"]).expanduser().resolve()
    return None


def active_project_root() -> Path | None:
    data = load_recent_projects()
    active = data.get("active")
    if not active:
        return None
    return resolve_project_reference(active)


def find_project_root(start: Path | None = None) -> Path:
    explicit = os.environ.get("ORCHESTRATOR_PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
        if any(candidate.glob("*.xcodeproj")) or any(candidate.glob("*.xcworkspace")):
            return candidate
        if (candidate / DEFAULT_RUNTIME_DIRNAME / "project.json").exists():
            return candidate
        if (candidate / "Package.swift").exists():
            return candidate
    active = active_project_root()
    if active and start is None:
        return active
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
    delivery_method: str | None = None
    firebase_plist_path: str | None = None
    provisioning_profile_specifier: str | None = None
    development_team: str | None = None
    asc_key_id: str | None = None
    asc_issuer_id: str | None = None
    asc_key_path: str | None = None
    visual_app_path: str | None = None
    remote_package_install_path: str = "~/.orchestrator/package"
    firebase_distribution: bool = False
    notification_display_name: str = ""
    signing_style: str | None = None

    @property
    def config_dir(self) -> Path:
        return self.runtime_dir / "config"

    def validate_distribution_config(self) -> list[str]:
        """Returns a list of missing required fields for iOS distribution."""
        errors = []
        if not self.development_team:
            errors.append("Apple Development Team ID (development_team) is not set.")
        if not self.delivery_method:
            errors.append("Distribution method (delivery_method) is not set (e.g., 'ad-hoc' or 'development').")
        
        # Check for either ASC keys OR a confirmed local account setup via provisioning profile
        # Only if signing style is not automatic
        signing_style = self.signing_style or "automatic"
        if signing_style != "automatic":
            has_asc_keys = all([self.asc_key_id, self.asc_issuer_id, self.asc_key_path])
            has_manual_profile = bool(self.provisioning_profile_specifier)

            if not has_asc_keys and not has_manual_profile:
                errors.append(
                    "Neither App Store Connect API keys nor a manual Provisioning Profile Specifier are configured. "
                    "For automated builds, providing ASC API keys is highly recommended to avoid 'No Accounts' errors."
                )
            elif any([self.asc_key_id, self.asc_issuer_id, self.asc_key_path]) and not has_asc_keys:
                 errors.append("App Store Connect API keys are partially configured. Please provide all three (ID, Issuer, Path).")
        
        return errors

    @property
    def prompts_dir(self) -> Path:
        project_prompts = self.runtime_dir / "prompts"
        return project_prompts if project_prompts.exists() else self.package_prompts_dir


def load_project_config() -> ProjectConfig:
    root = find_project_root()
    config_path = os.environ.get("ORCHESTRATOR_CONFIG")
    if config_path:
        config_file = Path(config_path).expanduser().resolve()
    else:
        config_file = root / DEFAULT_RUNTIME_DIRNAME / "project.json"

    data = _load_json(config_file)
    runtime_dir = Path(
        os.environ.get(
            "ORCHESTRATOR_RUNTIME_DIR",
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
        delivery_method=data.get("delivery_method"),
        firebase_plist_path=data.get("firebase_plist_path"),
        provisioning_profile_specifier=data.get("provisioning_profile_specifier"),
        development_team=data.get("development_team"),
        asc_key_id=data.get("asc_key_id"),
        asc_issuer_id=data.get("asc_issuer_id"),
        asc_key_path=data.get("asc_key_path"),
        visual_app_path=data.get("visual_app_path"),
        remote_package_install_path=data.get("remote_package_install_path", "~/.orchestrator/package"),
        firebase_distribution=bool(data.get("firebase_distribution", False)),
        notification_display_name=data.get("notification_display_name", f"{project_name} AI Orchestrator"),
        signing_style=data.get("signing_style", "automatic"),
    )


PROJECT_CONFIG = load_project_config()

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from orchestrator.config_validation import validate_machine_config, validate_project_config  # noqa: E402
from orchestrator.project_config import ProjectConfig  # noqa: E402


def make_config(root: Path, **overrides) -> ProjectConfig:
    data = {
        "root": root,
        "runtime_dir": root / ".swift-orchestrator",
        "package_prompts_dir": PACKAGE_ROOT / "orchestrator" / "prompts",
        "project_name": "SampleApp",
        "base_branch": "main",
        "git_remote": None,
        "xcode_project": "SampleApp.xcodeproj",
        "xcode_workspace": None,
        "scheme": "SampleApp",
        "test_target": "SampleAppTests",
        "derived_data_path": "/tmp/sampleapp_dd",
        "build_command": None,
        "test_command": None,
        "app_bundle_id": None,
        "backend_test_command": None,
        "branch_prefix": "ai/issue",
        "pr_base_branch": "main",
        "delivery_provider": None,
        "distribution_script_path": None,
        "firebase_plist_path": None,
        "visual_app_path": None,
        "remote_package_install_path": "~/.swift-orchestrator/package",
        "firebase_distribution": False,
        "notification_display_name": "SampleApp AI Orchestrator",
    }
    data.update(overrides)
    return ProjectConfig(**data)


class ConfigValidationTests(unittest.TestCase):
    def test_project_config_accepts_basic_xcode_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()

            self.assertEqual(validate_project_config(make_config(root)), [])

    def test_project_config_requires_existing_xcode_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = validate_project_config(make_config(Path(temp_dir)))

            self.assertIn("xcode_project does not exist: SampleApp.xcodeproj", errors)

    def test_project_config_validates_firebase_distribution_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()
            errors = validate_project_config(make_config(
                root,
                firebase_distribution=True,
                delivery_provider="firebase",
                distribution_script_path="scripts/distribute_ios.sh",
                firebase_plist_path="SampleApp/GoogleService-Info.plist",
            ))

            self.assertIn("distribution_script_path does not exist: scripts/distribute_ios.sh", errors)
            self.assertIn("firebase_plist_path does not exist: SampleApp/GoogleService-Info.plist", errors)

    def test_project_config_validates_visual_check_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()
            errors = validate_project_config(make_config(root, visual_app_path="build/SampleApp.app"))

            self.assertIn("visual_app_path does not exist: build/SampleApp.app", errors)
            self.assertIn("visual_app_path requires app_bundle_id for simulator launch.", errors)

    def test_machine_config_validates_ssh_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            (config_dir / "machines.json").write_text(
                json.dumps({
                    "machines": [
                        {
                            "name": "remote",
                            "execution_mode": "ssh",
                            "repo_path": "/Users/me/App",
                        }
                    ]
                }),
                encoding="utf-8",
            )

            errors = validate_machine_config(config_dir)

            self.assertIn("remote: ssh_target is required for SSH machines.", errors)


if __name__ == "__main__":
    unittest.main()

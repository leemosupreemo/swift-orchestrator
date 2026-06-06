from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from orchestrator import cli  # noqa: E402


class CliTests(unittest.TestCase):
    def test_init_project_scaffolds_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="swift-orchestrator-init-") as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()

            result = cli.main([
                "init",
                "--root",
                str(root),
                "--project-name",
                "SampleApp",
                "--base-branch",
                "develop",
            ])

            self.assertEqual(result, 0)
            runtime = root / ".swift-orchestrator"
            project = json.loads((runtime / "project.json").read_text(encoding="utf-8"))
            machines = json.loads((runtime / "config" / "machines.json").read_text(encoding="utf-8"))
            settings = json.loads((runtime / "config" / "settings.json").read_text(encoding="utf-8"))
            gitignore = (runtime / ".gitignore").read_text(encoding="utf-8")

            self.assertEqual(project["project_name"], "SampleApp")
            self.assertEqual(project["base_branch"], "develop")
            self.assertEqual(project["xcode_project"], "SampleApp.xcodeproj")
            self.assertEqual(project["scheme"], "SampleApp")
            self.assertEqual(project["test_target"], "SampleAppTests")
            self.assertEqual(
                Path(machines["machines"][0]["repo_path"]).resolve(),
                root.resolve(),
            )
            self.assertEqual(settings["notification_emails"], [])
            self.assertIn("jobs/", gitignore)
            self.assertIn("logs/", gitignore)
            self.assertIn("output/", gitignore)
            self.assertIn("state/", gitignore)

    def test_init_project_can_generate_starter_docs_and_helper_script(self) -> None:
        with tempfile.TemporaryDirectory(prefix="swift-orchestrator-init-") as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()

            result = cli.main([
                "init",
                "--root",
                str(root),
                "--project-name",
                "SampleApp",
                "--with-starter-docs",
                "--with-helper-script",
            ])

            self.assertEqual(result, 0)
            build_docs = (root / "docs" / "build-test-commands.md").read_text(encoding="utf-8")
            workflow_docs = (root / "docs" / "ai-workflow.md").read_text(encoding="utf-8")
            agents_docs = (root / "AGENTS.md").read_text(encoding="utf-8")
            helper = root / "scripts" / "orchestrator"

            self.assertIn("xcodebuild build -project SampleApp.xcodeproj -scheme SampleApp", build_docs)
            self.assertIn("xcodebuild test -project SampleApp.xcodeproj -scheme SampleApp", build_docs)
            self.assertIn("swift-orchestrator console", workflow_docs)
            self.assertIn("Run `swift-orchestrator check-config`", agents_docs)
            self.assertTrue(helper.exists())
            self.assertTrue(helper.stat().st_mode & 0o111)

    @patch("orchestrator.cli.subprocess.run")
    def test_init_project_uses_xcodebuild_json_for_scheme_and_targets(self, mock_run) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "project": {
                    "schemes": ["AppScheme"],
                    "targets": ["App", "AppUnitTests"],
                }
            }),
            stderr="",
        )
        with tempfile.TemporaryDirectory(prefix="swift-orchestrator-init-") as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()

            result = cli.main(["init", "--root", str(root)])

            self.assertEqual(result, 0)
            project = json.loads((root / ".swift-orchestrator" / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project["scheme"], "AppScheme")
            self.assertEqual(project["test_target"], "AppUnitTests")
            self.assertEqual(project["detected_schemes"], ["AppScheme"])
            self.assertEqual(project["detected_targets"], ["App", "AppUnitTests"])

    @patch("orchestrator.cli.validate_machine_config", return_value=[])
    @patch("orchestrator.cli.validate_project_config", return_value=[])
    def test_check_config_returns_success_for_valid_config(self, _project, _machines) -> None:
        self.assertEqual(cli.main(["check-config"]), 0)

    @patch("orchestrator.cli.validate_machine_config", return_value=["machines error"])
    @patch("orchestrator.cli.validate_project_config", return_value=["project error"])
    def test_check_config_returns_failure_for_errors(self, _project, _machines) -> None:
        self.assertEqual(cli.main(["check-config"]), 1)

    @patch("orchestrator.cli.run_script", return_value=0)
    def test_worker_commands_dispatch_to_worker_tools(self, mock_run_script) -> None:
        self.assertEqual(cli.main(["worker-check", "--machine", "mac2"]), 0)
        mock_run_script.assert_called_with("worker_tools.py", ["check", "--machine", "mac2"])

        self.assertEqual(cli.main(["worker-install"]), 0)
        mock_run_script.assert_called_with("worker_tools.py", ["install"])


if __name__ == "__main__":
    unittest.main()

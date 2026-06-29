from __future__ import annotations

import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import deliver_build  # noqa: E402
import simulator_visual_check  # noqa: E402


class VisualDeliveryConfigTests(unittest.TestCase):
    def test_visual_check_command_replaces_destination(self) -> None:
        command = "xcodebuild build -project App.xcodeproj -destination old-destination"

        updated = simulator_visual_check.command_with_destination(command, "platform=iOS Simulator,id=NEW")

        self.assertEqual(updated.count("-destination"), 1)
        self.assertIn("'platform=iOS Simulator,id=NEW'", updated)
        self.assertNotIn("old-destination", updated)

    @patch("deliver_build.send_final_notification")
    @patch("deliver_build.subprocess.Popen")
    @patch("deliver_build.subprocess.check_output")
    def test_deliver_build_uses_configured_distribution_script(self, mock_check_output, mock_popen, _notify) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SampleApp.xcodeproj").mkdir()
            (root / "tools").mkdir()
            script = root / "tools" / "ship.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            job_path = root / "job.json"
            job_path.write_text(
                json.dumps({
                    "job_id": "job-1",
                    "title": "Ship build",
                    "branch": "feature/build",
                    "issue_number": 1,
                }),
                encoding="utf-8",
            )

            mock_check_output.side_effect = [b"feature/build\n", b"2026-06-06 00:00:00\n"]
            process = MagicMock()
            process.stdout = []
            process.wait.return_value = 0
            mock_popen.return_value = process
            
            from orchestrator.project_config import ProjectConfig
            config = MagicMock(spec=ProjectConfig)
            config.distribution_script_path = "tools/ship.sh"
            config.xcode_project = "SampleApp.xcodeproj"
            config.validate_distribution_config.return_value = []
            config.scheme = None
            config.xcode_workspace = None
            config.provisioning_profile_specifier = None
            config.development_team = None
            config.delivery_method = None
            config.asc_key_id = None
            config.asc_issuer_id = None
            config.asc_key_path = None

            with (
                patch.object(deliver_build, "ROOT", root),
                patch.object(deliver_build, "PROJECT_CONFIG", config),
                self.assertRaises(SystemExit) as exit_context,
            ):
                deliver_build.deliver_build(job_path)

            self.assertEqual(exit_context.exception.code, 0)
            cmd = mock_popen.call_args.args[0]
            self.assertEqual(cmd[0:2], ["/bin/bash", str(script)])
            self.assertIn("--project", cmd)
            self.assertIn(str(root / "SampleApp.xcodeproj"), cmd)

    @patch("simulator_visual_check.plistlib.load")
    @patch("simulator_visual_check.open", create=True)
    @patch("pathlib.Path.exists")
    @patch("simulator_visual_check.get_best_simulator_destination")
    @patch("simulator_visual_check.simulator_udid")
    @patch("simulator_visual_check.stream_command")
    @patch("simulator_visual_check.run_simctl")
    @patch("simulator_visual_check.write_text")
    @patch("simulator_visual_check.time.sleep")
    @patch("simulator_visual_check.cleanup_logs")
    def test_visual_check_auto_resolves_bundle_id(
        self, mock_cleanup_logs, mock_sleep, mock_write_text, mock_run_simctl, mock_stream_cmd,
        mock_udid, mock_best_dest, mock_path_exists, mock_open_file, mock_plist_load
    ) -> None:
        # Mock sys.argv / argparse
        test_args = SimpleNamespace(
            no_build=False,
            bundle_id="",
            app_path="/tmp/test.app",
            wait=3.0,
            screenshots=1,
            interval=1.0
        )

        mock_path_exists.return_value = True
        mock_plist_load.return_value = {"CFBundleIdentifier": "com.test.resolved-bundle-id"}
        mock_best_dest.return_value = "id=test-udid"
        mock_udid.return_value = "test-udid"
        mock_stream_cmd.return_value = True
        mock_run_simctl.return_value = True

        with (
            patch("argparse.ArgumentParser.parse_args", return_value=test_args),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.unlink"),
            patch("pathlib.Path.is_symlink", return_value=False),
            patch("pathlib.Path.symlink_to"),
        ):
            try:
                simulator_visual_check.main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)

            # Verify simctl launch step was called with the resolved bundle ID
            launch_call = [call for call in mock_run_simctl.call_args_list if call[0][0][0] == "launch"]
            self.assertTrue(len(launch_call) > 0)
            self.assertEqual(launch_call[0][0][0][2], "com.test.resolved-bundle-id")


if __name__ == "__main__":
    unittest.main()

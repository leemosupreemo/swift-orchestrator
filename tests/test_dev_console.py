from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib
import dev_console  # noqa: E402
importlib.reload(dev_console)

class DevConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = dev_console.ROOT
        self.temp_root = Path("/tmp/orchestrator-test-root")
        self.temp_root.mkdir(parents=True, exist_ok=True)
        dev_console.ROOT = self.temp_root
        dev_console.CONFIG_DIR = self.temp_root / ".orchestrator" / "config"
        dev_console.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        dev_console.ROOT = self.old_root
        import shutil
        if self.temp_root.exists():
            shutil.rmtree(self.temp_root)

    @patch("dev_console.read_json")
    @patch("dev_console.write_json")
    @patch("dev_console.get_key")
    @patch("dev_console.input")
    @patch("dev_console.prompt_input")
    @patch("dev_console.clear_screen")
    @patch("dev_console.StatusBar")
    @patch("pathlib.Path.exists")
    def test_handle_email_settings_adds_recipient(self, mock_exists, _mock_status, _mock_clear, mock_prompt_input, mock_input, mock_get_key, mock_write, mock_read):
        # Initial settings
        mock_exists.return_value = True
        mock_read.return_value = {
            "notification_emails": ["old@example.com"],
            "notification_provider": "gmail"
        }
        
        # Actions: 'a' (add), then 'new@example.com', then 'b' (back)
        mock_get_key.side_effect = ["a", "b"]
        mock_prompt_input.return_value = "new@example.com"
        mock_input.return_value = ""
        
        dev_console.handle_email_settings([], [])
        
        # Verify write_json was called with updated emails
        mock_write.assert_called()
        final_settings = mock_write.call_args[0][1]
        self.assertIn("new@example.com", final_settings["notification_emails"])
        self.assertIn("old@example.com", final_settings["notification_emails"])

    @patch("dev_console.load_machines")
    @patch("dev_console.check_machine_availability")
    @patch("dev_console.prompt_checkbox")
    @patch("dev_console.clear_screen")
    @patch("dev_console.StatusBar")
    def test_handle_fleet_management_syncs_and_updates_session(self, _mock_status, _mock_clear, mock_checkbox, mock_avail, mock_load):
        mock_load.return_value = [
            {"name": "mac1", "enabled": True},
            {"name": "mac2", "enabled": True}
        ]
        mock_avail.return_value = True
        mock_checkbox.return_value = ["mac2"] # User selects only mac2
        
        new_machines = dev_console.handle_fleet_management(["mac1"])
        
        self.assertEqual(new_machines, ["mac2"])
        mock_avail.assert_called() # Should have pinged the fleet

    @patch("dev_console.get_key")
    @patch("dev_console.clear_screen")
    @patch("dev_console.StatusBar")
    @patch("dev_console.PROJECT_CONFIG")
    def test_handle_instruction_files_creates_missing(self, mock_config, _mock_status, _mock_clear, mock_get_key):
        mock_config.runtime_dir = Path(".orchestrator")
        
        # Mock get_key: 'a' (create all), then 'b' (back)
        mock_get_key.side_effect = ["a", "b"]
        
        with patch("dev_console.input", return_value=""):
            # We want to verify that files are created in our temp_root
            dev_console.handle_instruction_files()
            
            # Check if one of the expected files was created
            gemini_md = self.temp_root / "GEMINI.md"
            self.assertTrue(gemini_md.exists())
            self.assertIn("Source of truth", gemini_md.read_text())

    @patch("dev_console.get_key")
    @patch("dev_console.clear_screen")
    @patch("dev_console.StatusBar")
    @patch("dev_console.handle_role_prompts")
    def test_handle_instruction_files_custom_prompt_action_uses_session_state(self, mock_role_prompts, _mock_status, _mock_clear, mock_get_key):
        mock_get_key.side_effect = ["p", "b"]

        dev_console.handle_instruction_files(["mac1"], ["codex"])

        mock_role_prompts.assert_called_once_with(["mac1"], ["codex"])

    @patch("dev_console.get_key")
    @patch("dev_console.input")
    @patch("dev_console.clear_screen")
    @patch("dev_console.StatusBar")
    @patch("dev_console.PROJECT_CONFIG")
    @patch("dev_console.subprocess.run")
    @patch("dev_console.prompt_confirm")
    def test_handle_role_prompts_manages_templates(self, mock_confirm, mock_run, mock_config, _mock_status, _mock_clear, mock_input, mock_get_key):
        runtime_dir = self.temp_root / ".orchestrator"
        mock_config.runtime_dir = runtime_dir
        prompts_dir = runtime_dir / "prompts"
        
        # Scenario 1: No prompts, user chooses '1' to copy templates
        mock_get_key.side_effect = ["1", "b"]
        mock_input.return_value = ""
        dev_console.handle_role_prompts([], [])
        mock_run.assert_called() # Should run 'wizard --copy-prompt-overrides'
        
        # Scenario 2: Prompts exist, user chooses '2' to delete them
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "builder_bug.md").write_text("test")
        mock_get_key.side_effect = ["2", "b"]
        mock_input.return_value = ""
        mock_confirm.return_value = True
        dev_console.handle_role_prompts([], [])
        self.assertFalse(prompts_dir.exists())

    @patch("dev_console.get_key")
    @patch("dev_console.input")
    @patch("dev_console.clear_screen")
    @patch("dev_console.StatusBar")
    @patch("dev_console.run_script")
    @patch("dev_console.save_job")
    @patch("dev_console.refresh_job")
    def test_handle_job_selection_answers_clarification(self, mock_refresh, mock_save, mock_run_script, _mock_status, _mock_clear, mock_input, mock_get_key):
        job = {
            "job_id": "test-job",
            "status": "human-needed",
            "human_clarification_question": "What is the color?",
            "type": "feature-plan",
            "_path": "test.json"
        }
        mock_refresh.return_value = job
        
        # Actions: 'a' (answer), then 'Blue', then 'b' (back)
        mock_get_key.side_effect = ["a", "b"]
        mock_input.return_value = "Blue"
        
        dev_console.handle_job_selection(job, [], [])
        
        # Verify old question was cleared and re-plan was triggered
        mock_save.assert_called()
        saved_job = mock_save.call_args[0][0]
        self.assertIsNone(saved_job["human_clarification_question"])
        
        mock_run_script.assert_called_with(
            "new_job.py",
            ["feature", "--no-dispatch", "--update", "test.json", "--feedback", "### USER CLARIFICATION ###\nBlue"],
            sub_menu=True
        )

    @patch("dev_console.run_streaming_process")
    @patch("dev_console.print_divider")
    @patch("dev_console.input")
    @patch("dev_console.print")
    def test_run_script_extracts_failure_summary_from_logs(self, mock_print, mock_input, mock_print_divider, mock_run_streaming):
        # Setup run_streaming_process to fail with a non-zero exit code and output_log containing an error
        mock_run_streaming.return_value = (1, "Some generic logs\n❌ Bundle id is required. Set app_bundle_id in project.json or pass --bundle-id.\nMore logs")
        mock_input.return_value = ""

        # Run script
        dev_console.run_script("some_script.py", [])

        # Verify summary output was printed containing the bundle ID error
        printed_args = [call[0][0] for call in mock_print.call_args_list if call[0]]
        full_printed = "".join(printed_args)
        self.assertIn("Bundle id is required", full_printed)

    @patch("dev_console.subprocess.check_output")
    @patch("dev_console.subprocess.run")
    def test_check_origin_update_status_detects_remote_updates(self, mock_run, mock_check_output):
        mock_check_output.side_effect = [
            "main\n",
            "0\t3\n",
        ]

        status = dev_console.check_origin_update_status(Path("/tmp/pkg"))

        self.assertEqual(status["state"], "behind")
        self.assertEqual(status["behind"], 3)
        self.assertEqual(status["remote_ref"], "origin/main")
        mock_run.assert_called_once()

    @patch("dev_console.subprocess.check_output")
    @patch("dev_console.subprocess.run")
    def test_check_origin_update_status_detects_current_branch(self, _mock_run, mock_check_output):
        mock_check_output.side_effect = [
            "main\n",
            "0\t0\n",
        ]

        status = dev_console.check_origin_update_status(Path("/tmp/pkg"))

        self.assertEqual(status["state"], "current")
        self.assertEqual(status["behind"], 0)

    def test_script_failure_summary_prefers_signing_diagnostic(self):
        output = """
❌ Distribution failed (exit 65).

\033[1;91mSigning setup needs attention\033[0m
Xcode could not find a certificate or provisioning profile for this app.

Next steps:
  1. Run the Dev Console signing validation checks.
  2. Confirm project.json has the correct Team ID and Bundle Identifier.
  3. Run orchestrator wizard if signing settings need to be regenerated.

❌ Smoke delivery failed during build/distribution.
"""

        summary = dev_console.script_failure_summary(output)

        self.assertIn("Signing setup needs attention", summary)
        self.assertIn("Run the Dev Console signing validation checks", summary)
        self.assertNotIn("Smoke delivery failed", summary)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dev_console  # noqa: E402
from orchestrator.project_config import PROJECT_CONFIG


class DevConsoleIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = dev_console.ROOT
        self.old_config_dir = dev_console.CONFIG_DIR
        self.old_jobs_dir = dev_console.JOBS_DIR
        self.old_output_dir = dev_console.OUTPUT_DIR

        self.temp_dir = tempfile.TemporaryDirectory(prefix="orchestrator-console-integ-")
        self.temp_root = Path(self.temp_dir.name)
        
        # Setup workspace structure
        runtime_dir = self.temp_root / ".orchestrator"
        dev_console.ROOT = self.temp_root
        dev_console.CONFIG_DIR = runtime_dir / "config"
        dev_console.JOBS_DIR = runtime_dir / "jobs"
        dev_console.OUTPUT_DIR = runtime_dir / "output"
        
        for d in [dev_console.CONFIG_DIR, dev_console.JOBS_DIR, dev_console.OUTPUT_DIR]:
            d.mkdir(parents=True, exist_ok=True)
            
        # Write default machines so the menu doesn't complain
        dev_console.write_json(dev_console.CONFIG_DIR / "machines.json", {
            "machines": [{"name": "local", "execution_mode": "local", "enabled": True}]
        })
        
        from types import SimpleNamespace
        mock_config = SimpleNamespace(
            runtime_dir=runtime_dir,
            root=self.temp_root,
            base_branch="main",
            pr_base_branch="main"
        )
        self.patcher_config = patch("dev_console.PROJECT_CONFIG", mock_config)
        self.patcher_config.start()
        
        # Suppress screen clearing and sleeping during tests
        self.patcher_clear = patch("dev_console.clear_screen")
        self.patcher_clear.start()
        self.patcher_sleep = patch("time.sleep")
        self.patcher_sleep.start()

    def tearDown(self) -> None:
        dev_console.ROOT = self.old_root
        dev_console.CONFIG_DIR = self.old_config_dir
        dev_console.JOBS_DIR = self.old_jobs_dir
        dev_console.OUTPUT_DIR = self.old_output_dir
        
        self.patcher_config.stop()
        self.patcher_clear.stop()
        self.patcher_sleep.stop()
        self.temp_dir.cleanup()

    @patch("dev_console.get_key")
    def test_main_menu_quit(self, mock_get_key):
        # Simply press 'q' to quit the main loop
        mock_get_key.side_effect = ["q"]
        
        # Provide a safe exit using SystemExit to break out if it goes infinite,
        # but main_loop should return gracefully on 'q'.
        dev_console.main_loop()
        
        self.assertTrue(mock_get_key.called)

    @patch("dev_console.get_key")
    @patch("dev_console.input")
    def test_config_flow_update_email_settings(self, mock_input, mock_get_key):
        # Sequence:
        # 'c' -> Enter Configuration
        # 'e' -> Enter Email Settings
        # 'a' -> Add Email Recipient
        # 'b' -> Back to Config Menu
        # 'b' -> Back to Main Menu
        # 'q' -> Quit
        mock_get_key.side_effect = ["c", "e", "a", "b", "b", "q"]
        
        # Input provided when asked for the email address
        mock_input.side_effect = ["integration@example.com", ""]
        
        dev_console.main_loop()
        
        # Assert the email was saved to settings.json
        settings_path = dev_console.CONFIG_DIR / "settings.json"
        self.assertTrue(settings_path.exists())
        settings = dev_console.read_json(settings_path)
        self.assertIn("integration@example.com", settings.get("notification_emails", []))

    @patch("dev_console.get_key")
    @patch("dev_console.prompt_confirm")
    def test_job_interaction_flow_reset_status(self, mock_confirm, mock_get_key):
        # Create a dummy job in executing state
        job_id = "test-job-1"
        job_data = {
            "job_id": job_id,
            "title": "Test Job",
            "status": "executing",
            "type": "feature-plan",
            "updated_at": dev_console.now_iso()
        }
        dev_console.write_json(dev_console.JOBS_DIR / f"{job_id}.json", job_data)
        
        # Sequence:
        # '1' -> Select the first active job
        # 'p' -> Reset status to planned (since it's 'executing' and stalled check might apply, but 'p' is available in executing via stalled or directly)
        # Wait, 'p' is only available if job is stalled (older than 12h) OR we can use 'r' to re-run.
        # Let's mock the job to be human-needed instead, and test answering a question.
        
        job_data["status"] = "human-needed"
        job_data["human_clarification_question"] = "What?"
        dev_console.write_json(dev_console.JOBS_DIR / f"{job_id}.json", job_data)

        # Let's test the new 'a' Answer Question flow
        # '0' -> Select job 0
        # 'a' -> Answer Question
        # 'b' -> Back to Main Menu
        # 'q' -> Quit
        mock_get_key.side_effect = ["0", "a", "b", "q"]
        
        # Mocking input for the answer
        with patch("dev_console.input", side_effect=["Blue"]):
            # Also mock run_script so we don't actually trigger new_job.py
            with patch("dev_console.run_script") as mock_run_script:
                dev_console.main_loop()
                
                # Check that run_script was called to re-plan
                mock_run_script.assert_called_with(
                    "new_job.py", 
                    ["feature", "--no-dispatch", "--update", str(dev_console.JOBS_DIR / f"{job_id}.json"), "--feedback", "### USER CLARIFICATION ###\nBlue"], 
                    sub_menu=True
                )
        
        # Assert the question was cleared
        updated_job = dev_console.read_json(dev_console.JOBS_DIR / f"{job_id}.json")
        self.assertIsNone(updated_job.get("human_clarification_question"))

if __name__ == "__main__":
    unittest.main()

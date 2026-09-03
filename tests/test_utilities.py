from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure paths
TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "orchestrator" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import notify
import export_job
import trace_braces

class UtilitiesTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    @patch("notify.subprocess.run")
    @patch("notify.send_email_notification")
    def test_notify_desktop_and_email(self, mock_email, mock_subproc):
        """Verify notify triggers osascript and email notification."""
        mock_email.return_value = True
        mock_subproc.return_value = MagicMock(returncode=0)

        res = notify.notify("Test Title", "Test Message", job_id="job-123", summary="Done")
        self.assertTrue(res)
        mock_subproc.assert_called_once()
        self.assertIn("osascript", mock_subproc.call_args[0][0])
        mock_email.assert_called_once_with("Test Title", "Test Message", "job-123", "Done")

    def test_notify_disabled_env(self):
        """Verify notification skips when ORCHESTRATOR_DISABLE_NOTIFICATIONS=1."""
        with patch.dict(os.environ, {"ORCHESTRATOR_DISABLE_NOTIFICATIONS": "1"}):
            res = notify.notify("Test", "Message")
            self.assertFalse(res)

    def test_trace_braces_balanced(self):
        """Verify trace_braces handles valid Swift code without error output."""
        swift_file = self.temp_root / "Valid.swift"
        swift_file.write_text("""// Comment {
func test() {
    let str = "{ Hello }"
    /* Block { */
    if true {
        return
    }
}
""")
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            trace_braces.trace_braces(str(swift_file))
        self.assertEqual(captured_output.getvalue().strip(), "")

    def test_trace_braces_unclosed(self):
        """Verify trace_braces detects unclosed opening braces."""
        swift_file = self.temp_root / "Unclosed.swift"
        swift_file.write_text("""func test() {
    if true {
}
""")
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            trace_braces.trace_braces(str(swift_file))
        self.assertIn("Unclosed braces", captured_output.getvalue())

    def test_export_job_zip(self):
        """Verify export_job creates a valid zip containing job files and manifest."""
        job_file = self.temp_root / "job-1.json"
        job_file.write_text(json.dumps({"job_id": "job-1", "title": "Test Job"}))
        zip_out = self.temp_root / "export.zip"

        export_job.export_job(str(job_file), str(zip_out))
        self.assertTrue(zip_out.exists())

if __name__ == "__main__":
    unittest.main()

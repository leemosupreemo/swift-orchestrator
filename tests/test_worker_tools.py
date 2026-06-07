from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import worker_tools  # noqa: E402


class WorkerToolsTests(unittest.TestCase):
    def test_remote_import_check_uses_configured_package_path(self) -> None:
        machine = {
            "name": "mac2",
            "execution_mode": "ssh",
            "ssh_target": "worker-host",
            "repo_path": "/Users/me/App",
            "orchestrator_package_path": "/opt/orchestrator",
        }

        command = worker_tools.remote_import_check_command(machine)

        self.assertIn("cd /Users/me/App", command)
        self.assertIn("PYTHONPATH=/opt/orchestrator:$PYTHONPATH", command)
        self.assertIn("import orchestrator.scripts.worker_run", command)

    @patch("worker_tools.subprocess.run")
    def test_check_remote_reports_missing_package(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="No module named orchestrator", stdout="")
        machine = {
            "name": "mac2",
            "execution_mode": "ssh",
            "ssh_target": "worker-host",
            "repo_path": "/Users/me/App",
        }

        result = worker_tools.check_remote(machine)

        self.assertEqual(result, 1)
        args = mock_run.call_args.args[0]
        self.assertEqual(args[:4], ["ssh", "-o", "BatchMode=yes", "-o"])
        self.assertIn("import orchestrator.scripts.worker_run", args[-1])
        self.assertIn("command -v xcodebuild", args[-1])

    @patch("worker_tools.check_remote", return_value=0)
    @patch("worker_tools.subprocess.run")
    def test_install_remote_syncs_package_then_checks_worker(self, mock_run, mock_check_remote) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        machine = {
            "name": "mac2",
            "execution_mode": "ssh",
            "ssh_target": "worker-host",
            "repo_path": "/Users/me/App",
            "orchestrator_package_path": "/remote/package",
        }

        result = worker_tools.install_remote(machine)

        self.assertEqual(result, 0)
        mkdir_args = mock_run.call_args_list[0].args[0]
        rsync_args = mock_run.call_args_list[1].args[0]
        self.assertEqual(mkdir_args, ["ssh", "worker-host", "mkdir -p /remote/package"])
        self.assertEqual(rsync_args[0], "rsync")
        self.assertIn("--delete", rsync_args)
        self.assertEqual(rsync_args[-1], "worker-host:/remote/package/orchestrator/")
        mock_check_remote.assert_called_once_with(machine)


if __name__ == "__main__":
    unittest.main()


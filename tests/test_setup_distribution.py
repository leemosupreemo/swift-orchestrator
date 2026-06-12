from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator.project_config import find_project_root  # noqa: E402
from setup_distribution import infer_firebase_plist_path, setup_distribution  # noqa: E402


class SetupDistributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_project_root = os.environ.get("ORCHESTRATOR_PROJECT_ROOT")

    def tearDown(self) -> None:
        if self.old_project_root is None:
            os.environ.pop("ORCHESTRATOR_PROJECT_ROOT", None)
        else:
            os.environ["ORCHESTRATOR_PROJECT_ROOT"] = self.old_project_root

    def test_env_project_root_overrides_current_repo_markers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orchestrator-app-") as temp_dir:
            app_root = Path(temp_dir).resolve()
            os.environ["ORCHESTRATOR_PROJECT_ROOT"] = str(app_root)

            self.assertEqual(find_project_root(PACKAGE_ROOT), app_root)

    def test_setup_distribution_creates_files_and_project_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orchestrator-app-") as temp_dir:
            app_root = Path(temp_dir).resolve()
            runtime = app_root / ".orchestrator"
            runtime.mkdir()
            (app_root / "Themis.xcodeproj").mkdir()
            (app_root / "Themis").mkdir()
            (runtime / "project.json").write_text(
                json.dumps({
                    "project_name": "Themis",
                    "xcode_project": "Themis.xcodeproj",
                    "firebase_plist_path": "Themis/GoogleService-Info.plist",
                    "firebase_distribution": False,
                }),
                encoding="utf-8",
            )
            os.environ["ORCHESTRATOR_PROJECT_ROOT"] = str(app_root)

            setup_distribution(team_id="ABC123DEFG")

            project = json.loads((runtime / "project.json").read_text(encoding="utf-8"))
            self.assertTrue((app_root / "scripts" / "distribute_ios.sh").exists())
            self.assertTrue((app_root / "scripts" / "ExportOptions.plist").exists())
            self.assertTrue((app_root / "scripts" / "distribute_ios.sh").stat().st_mode & 0o111)
            self.assertTrue(project["firebase_distribution"])
            self.assertEqual(project["delivery_provider"], "firebase")
            self.assertEqual(project["distribution_script_path"], "scripts/distribute_ios.sh")
            self.assertEqual(project["firebase_plist_path"], "Themis/GoogleService-Info.plist")
            self.assertEqual(project["development_team"], "ABC123DEFG")
            
            # Verify teamID in ExportOptions.plist
            export_opts = (app_root / "scripts" / "ExportOptions.plist").read_text(encoding="utf-8")
            self.assertIn("<key>teamID</key>", export_opts)
            self.assertIn("<string>ABC123DEFG</string>", export_opts)

    def test_infer_firebase_plist_path_prefers_project_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orchestrator-app-") as temp_dir:
            app_root = Path(temp_dir).resolve()
            (app_root / "SampleApp").mkdir()
            (app_root / "SampleApp" / "GoogleService-Info.plist").write_text("<plist />", encoding="utf-8")

            self.assertEqual(infer_firebase_plist_path(app_root, "SampleApp"), "SampleApp/GoogleService-Info.plist")


if __name__ == "__main__":
    unittest.main()

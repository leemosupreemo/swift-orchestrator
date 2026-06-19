from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PACKAGE_ROOT / "orchestrator" / "scripts"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import common  # noqa: E402


class CommonTests(unittest.TestCase):
    @patch("common.get_best_simulator_destination", return_value="platform=iOS Simulator,id=TEST_SIM")
    def test_extract_commands_reads_ios_app_tests_section(self, _mock_destination) -> None:
        project_config = SimpleNamespace(
            build_command=None,
            test_command=None,
            xcode_project="App.xcodeproj",
            xcode_workspace=None,
            scheme="App",
            derived_data_path="/tmp/dd",
            root=common.ROOT,
            runtime_dir=common.ORCHESTRATOR_RUNTIME_DIR,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(common, "DOCS_DIR", Path(tmp)), patch.object(common, "PROJECT_CONFIG", project_config):
                build_command, test_command = common.extract_commands()

        self.assertIn("xcodebuild build", build_command)
        self.assertIn("xcodebuild test", test_command)
        self.assertIn("-destination", test_command)
        self.assertIn("platform=iOS Simulator,id=TEST_SIM", test_command)

    @patch("common.get_best_simulator_destination", return_value="platform=iOS Simulator,id=TEST_SIM")
    def test_extract_commands_no_duplicate_destination(self, _mock_destination) -> None:
        project_config = SimpleNamespace(
            build_command=None,
            test_command=None,
            xcode_project="App.xcodeproj",
            xcode_workspace=None,
            scheme="App",
            derived_data_path="/tmp/dd",
            root=common.ROOT,
            runtime_dir=common.ORCHESTRATOR_RUNTIME_DIR,
        )
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "build-test-commands.md").write_text(
                """## iOS app build
```bash
xcodebuild build -destination 'platform=iOS Simulator,id=EXISTING'
```

## iOS app tests
```bash
xcodebuild test -destination 'platform=iOS Simulator,id=EXISTING'
```
""",
                encoding="utf-8",
            )
            with patch.object(common, "DOCS_DIR", docs_dir), patch.object(common, "PROJECT_CONFIG", project_config):
                build_command, test_command = common.extract_commands()
        
        # Count occurrences of -destination
        self.assertEqual(build_command.count("-destination"), 1)
        self.assertEqual(test_command.count("-destination"), 1)

    @patch("common.get_best_simulator_destination", return_value="platform=iOS Simulator,id=TEST_SIM")
    def test_extract_commands_resolves_pwd_before_shell_quoting(self, _mock_destination) -> None:
        project_config = SimpleNamespace(
            build_command=None,
            test_command=None,
            xcode_project="App.xcodeproj",
            xcode_workspace=None,
            scheme="App",
            derived_data_path="/tmp/dd",
            root=common.ROOT,
            runtime_dir=common.ORCHESTRATOR_RUNTIME_DIR,
        )
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "build-test-commands.md").write_text(
                """## iOS app build
```bash
xcodebuild build CLANG_MODULE_CACHE_PATH=$(pwd)/.clang-module-cache
```

## iOS app tests
```bash
xcodebuild test CLANG_MODULE_CACHE_PATH=$(pwd)/.clang-module-cache
```
""",
                encoding="utf-8",
            )
            with patch.object(common, "DOCS_DIR", docs_dir), patch.object(common, "PROJECT_CONFIG", project_config):
                build_command, test_command = common.extract_commands()

        expected_cache_path = f"CLANG_MODULE_CACHE_PATH={common.ROOT}/.clang-module-cache"

        self.assertNotIn("$(pwd)", build_command)
        self.assertNotIn("$(pwd)", test_command)
        self.assertIn(expected_cache_path, build_command)
        self.assertIn(expected_cache_path, test_command)


    def test_extract_commands_does_not_add_xcode_flags_to_custom_commands(self) -> None:
        project_config = SimpleNamespace(
            build_command="swift build",
            test_command="swift test",
            xcode_project=None,
            xcode_workspace=None,
            scheme="TrialPackage",
            derived_data_path="/tmp/trial_dd",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(common, "DOCS_DIR", Path(tmp)), patch.object(common, "PROJECT_CONFIG", project_config):
                build_command, test_command = common.extract_commands()

        self.assertEqual(build_command, "swift build")
        self.assertEqual(test_command, "swift test")
        self.assertNotIn("-derivedDataPath", build_command)
        self.assertNotIn("-derivedDataPath", test_command)

    def test_choice_prompt_shows_cursor_and_positions_it_in_field(self) -> None:
        prompt = common.get_choice_prompt("Choice:", "(number or letter)")

        self.assertTrue(prompt.startswith("\033[?25h"))
        self.assertTrue(prompt.endswith("\033[20D"))
        self.assertIn("\033[48;5;236m\033[90m (number or letter) ", prompt)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key")
    @patch("sys.stdout.write")
    def test_prompt_input_back_behavior(self, mock_write, mock_get_key, mock_isatty) -> None:
        # If allow_back=False (default), typing 'b' should just insert 'b' and not raise BackException
        mock_get_key.side_effect = ["b", "u", "i", "l", "d", "enter"]
        res = common.prompt_input("Path:", allow_back=False)
        self.assertEqual(res, "build")

        # If allow_back=True, typing 'b' as the first key should raise BackException
        mock_get_key.side_effect = ["b"]
        with self.assertRaises(common.BackException):
            common.prompt_input("Path:", allow_back=True)


if __name__ == "__main__":
    unittest.main()

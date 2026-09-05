from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    def test_header_string_normalizes_title_to_caps(self) -> None:
        header = common.get_header_string("select models")

        self.assertIn("SELECT MODELS", header)
        self.assertNotIn("select models", header)

    def test_header_string_keeps_parenthetical_helper_text_lowercase(self) -> None:
        header = common.get_header_string(
            "Load spec from a local file or web address? (useful for large multi-page docs)"
        )

        self.assertIn("LOAD SPEC FROM A LOCAL FILE OR WEB ADDRESS?", header)
        self.assertIn("(useful for large multi-page docs)", header)
        self.assertNotIn("(USEFUL FOR LARGE MULTI-PAGE DOCS)", header)

    @patch("common.sys.stdout.isatty", return_value=True)
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_progress_indicator_hides_cursor_while_rendering(self, mock_write, _mock_flush, _mock_isatty) -> None:
        indicator = common.ProgressIndicator()

        indicator.render(force=True)
        indicator.clear()

        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("\033[?25l", written)
        self.assertIn("\033[?25h", written)
        self.assertNotIn("\0337", written)
        self.assertNotIn("\0338", written)

    @patch("common.sys.stdout.isatty", return_value=False)
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_progress_indicator_is_silent_when_stdout_is_not_tty(self, mock_write, _mock_flush, _mock_isatty) -> None:
        indicator = common.ProgressIndicator()

        indicator.render(force=True)
        indicator.clear()

        mock_write.assert_not_called()

    @patch("common.os.get_terminal_size", return_value=(45, 24))
    def test_progress_indicator_clamps_to_terminal_width(self, _mock_size) -> None:
        indicator = common.ProgressIndicator(
            label="Thinking: Deep Reasoning model active",
            hint="Ctrl-C to cancel"
        )
        line = indicator.get_line(last_activity_time=100.0)
        # Strip ANSI escape codes to measure visible character length
        import re
        plain = re.sub(r"\033\[[0-9;]*m", "", line)
        self.assertLessEqual(len(plain), 43)
        self.assertNotIn("......", plain)

    def test_progress_indicator_does_not_duplicate_trailing_dots(self) -> None:
        indicator = common.ProgressIndicator(label="Consulting gemini...")
        line = indicator.get_line()
        import re
        plain = re.sub(r"\033\[[0-9;]*m", "", line)
        self.assertNotIn("......", plain)
        self.assertIn("Consulting gemini...", plain)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.sys.stdout.isatty", return_value=True)
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_processing_status_bar_hides_cursor_until_reset(
        self, mock_write, _mock_flush, _mock_stdout_isatty, _mock_stdin_isatty
    ) -> None:
        status_bar = common.StatusBar(is_processing=True)
        status_bar.anchor_to_bottom = True

        status_bar.set_scroll_region()
        status_bar.reset_scroll_region()

        writes = [call.args[0] for call in mock_write.call_args_list]
        self.assertTrue(writes[0].startswith("\033[?25l"))
        self.assertIn("\033[?25h", writes[-1])

    @patch("common.StatusBar._get_branch", return_value="main")
    @patch("common.StatusBar._get_size", return_value=(100, 24))
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_status_bar_prompt_has_compact_pipe_spacing(
        self, mock_write, _mock_flush, _mock_size, _mock_branch
    ) -> None:
        status_bar = common.StatusBar(sub_menu=True)

        status_bar.render(force=True)

        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn(" B to go back | dir:", written)
        self.assertNotIn(" B to go back       | dir:", written)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_radio_prompt_uses_aligned_selector_gutter(
        self, mock_write, _mock_flush, _mock_get_key, _mock_isatty
    ) -> None:
        options = [
            "✨ Brand New Feature (Design-First)",
            "🛠️ Iterating / Small Refactor (Plan or Quick Mode)",
        ]

        choice = common.prompt_radio("Select Job Type:", options, default=options[1])

        self.assertEqual(choice, options[1])
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("\033[?25l\033[r\033[2J\033[H", written)
        self.assertIn("(Arrows: navigate, Enter: select, B: back)\033[0m\n\n", written)
        self.assertIn("  [ ]  ✨ Brand New Feature", written)
        self.assertIn("> [x]  🛠️ Iterating", written)
        self.assertIn("[\033[1;91mB\033[0m] Back", written)
        self.assertIn("\033[J", written)
        self.assertIn("Choice: \033[1;96m🛠️ Iterating / Small Refactor", written)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_radio_prompt_renders_parenthetical_text_as_description(
        self, mock_write, _mock_flush, _mock_get_key, _mock_isatty
    ) -> None:
        options = [
            "new (creates a new branch automatically)",
            "manual (no git actions; skip checkout/pull)",
        ]

        choice = common.prompt_radio("Branch selection:", options, default=options[0])

        self.assertEqual(choice, options[0])
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("> [x]  new", written)
        self.assertIn("       \033[90mcreates a new branch automatically\033[0m", written)
        self.assertNotIn("> [x]  new (creates a new branch automatically)", written)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_confirm_prompt_can_show_description_under_short_title(
        self, mock_write, _mock_flush, _mock_get_key, _mock_isatty
    ) -> None:
        result = common.prompt_confirm(
            "YOLO mode?",
            default=False,
            description="Automatically dispatch after planning.",
        )

        self.assertFalse(result)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("YOLO MODE?", written)
        self.assertIn("\033[90mAutomatically dispatch after planning.\033[0m", written)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_confirm_prompt_uses_plain_banner_title(
        self, mock_write, _mock_flush, _mock_get_key, _mock_isatty
    ) -> None:
        result = common.prompt_confirm("Load spec from a local file or web address?", default=False)

        self.assertFalse(result)
        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("LOAD SPEC FROM A LOCAL FILE OR WEB ADDRESS?", written)
        self.assertNotIn("\033[1;97mLoad spec", written)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_checkbox_footer_actions_are_visible_below_options(
        self, mock_write, _mock_flush, _mock_get_key, _mock_isatty
    ) -> None:
        footer = "[R] Sync Registry  [D] Live Discovery  [B] Back"

        common.prompt_checkbox("select models", ["model-a"], ["model-a"], footer=footer)

        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertGreater(written.index(footer), written.index("model-a"))
        self.assertIn("(Arrows: navigate, Space: toggle, Enter: save, B: back)\033[0m\n\n", written)
        self.assertIn(f"\n{footer}", written)

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("common.sys.stdout.flush")
    @patch("common.sys.stdout.write")
    def test_checkbox_max_selection_line_shows_selected_count(
        self, mock_write, _mock_flush, _mock_get_key, _mock_isatty
    ) -> None:
        common.prompt_checkbox("active machines", ["macair"], ["macair"], max_selections=10)

        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("Selected machines:", written)
        self.assertIn("1 of 10", written)
        self.assertIn("machine limit", written)
        self.assertNotIn("Fleet limit:", written)

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

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("sys.stdout.write")
    def test_prompt_input_default_hint_confirms_enter(self, _mock_write, _mock_get_key, _mock_isatty) -> None:
        status_bar = SimpleNamespace(render=Mock())
        with patch.object(common, "_ACTIVE_STATUS_BAR", status_bar):
            res = common.prompt_input("Remote repo path:", default="/repo/path")

        self.assertEqual(res, "/repo/path")
        status_bar.render.assert_called_with(at_bottom=True, force=True, q_msg="Enter to confirm")

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", return_value="enter")
    @patch("sys.stdout.write")
    def test_prompt_input_empty_default_hint_submits_enter(self, _mock_write, _mock_get_key, _mock_isatty) -> None:
        status_bar = SimpleNamespace(render=Mock())
        with patch.object(common, "_ACTIVE_STATUS_BAR", status_bar):
            res = common.prompt_input("Enter release notes for this build:")

        self.assertEqual(res, "")
        status_bar.render.assert_called_with(at_bottom=True, force=True, q_msg="Enter to submit | Ctrl-C to exit")

    @patch("common.sys.stdin.isatty", return_value=True)
    @patch("common.get_key", side_effect=["u", "p", "d", "a", "t", "e", "enter"])
    @patch("sys.stdout.write")
    def test_prompt_input_can_render_field_below_label(self, mock_write, mock_get_key, _mock_isatty) -> None:
        result = common.prompt_input("Briefly describe what should change", placeholder="specific behavior", field_below=True)

        written = "".join(call.args[0] for call in mock_write.call_args_list)
        self.assertEqual(result, "update")
        self.assertIn("Briefly describe what should change", written)
        self.assertIn("specific behavior", written)
        self.assertEqual(written.count("Briefly describe what should change"), 1)
        self.assertIn("\033[?25h", written)
        self.assertGreaterEqual(mock_get_key.call_count, 1)


class MarkdownFormatterTests(unittest.TestCase):
    def test_format_inline_markdown_bold(self) -> None:
        text = "This is **bold** text."
        formatted = common.format_inline_markdown(text)
        self.assertEqual(formatted, "This is \033[1;97mbold\033[0m text.")

    def test_format_inline_markdown_italic(self) -> None:
        text = "This is *italic* text."
        formatted = common.format_inline_markdown(text)
        self.assertEqual(formatted, "This is \033[3mitalic\033[0m text.")

    def test_format_inline_markdown_code(self) -> None:
        text = "Run `orchestrator check` to verify."
        formatted = common.format_inline_markdown(text)
        self.assertEqual(formatted, "Run \033[1;93morchestrator check\033[0m to verify.")

    def test_format_inline_markdown_link(self) -> None:
        text = "Go to [User Guide](docs/user-guide.md) now."
        formatted = common.format_inline_markdown(text)
        self.assertEqual(formatted, "Go to \033[4;94mUser Guide\033[0m \033[90m(docs/user-guide.md)\033[0m now.")

    def test_format_inline_markdown_no_overlap(self) -> None:
        text = "Run `orchestrator_check_env` with [Guide](doc_link.md)."
        formatted = common.format_inline_markdown(text)
        self.assertIn("\033[1;93morchestrator_check_env\033[0m", formatted)
        self.assertIn("\033[4;94mGuide\033[0m \033[90m(doc_link.md)\033[0m", formatted)

    def test_format_markdown_for_terminal_headers(self) -> None:
        text = "# H1 Title\n## H2 Subtitle\n### H3 Section"
        formatted = common.format_markdown_for_terminal(text)
        self.assertIn("\033[1;95mH1 TITLE\033[0m", formatted)
        self.assertIn("\033[1;96mH2 Subtitle\033[0m", formatted)
        self.assertIn("\033[1;93mH3 Section\033[0m", formatted)

    def test_format_markdown_for_terminal_lists(self) -> None:
        text = "- Item 1\n- Item 2\n1. Numbered Item"
        formatted = common.format_markdown_for_terminal(text)
        self.assertIn("•", formatted)
        self.assertIn("1.", formatted)

    def test_format_markdown_for_terminal_code_blocks(self) -> None:
        text = "```bash\nswift build\n```"
        formatted = common.format_markdown_for_terminal(text)
        self.assertIn("┌", formatted)
        self.assertIn("│", formatted)
        self.assertIn("└", formatted)
        self.assertIn("swift build", formatted)


    def test_get_simulator_diagnostic(self) -> None:
        diag = common.get_simulator_diagnostic()
        self.assertIn("has_simctl", diag)
        self.assertIn("has_runtimes", diag)
        self.assertIn("available_devices_count", diag)
        self.assertIn("best_destination", diag)
        self.assertIsInstance(diag["has_simctl"], bool)
        self.assertIsInstance(diag["has_runtimes"], bool)


class StepExtractorTests(unittest.TestCase):
    def test_extract_phase_steps(self) -> None:
        self.assertEqual(common.extract_step_from_line("=== 🧠 PLANNING ==="), "Planning feature")
        self.assertEqual(common.extract_step_from_line("=== ⚙️ SUB-TASK 1/3: ADD AUTH SERVICE ==="), "Task 1/3: Add Auth Service")
        self.assertEqual(common.extract_step_from_line("=== 📡 SCHEDULING: SYNCING CODE TO MAC2 ==="), "Syncing code to worker")
        self.assertEqual(common.extract_step_from_line("=== 🌿 GIT_PREP ==="), "Preparing git branch")
        self.assertEqual(common.extract_step_from_line("=== ⚙️ STATUS_UPDATE ==="), "Updating job status")
        self.assertEqual(common.extract_step_from_line("=== 🔨 IMPLEMENTATION ==="), "Generating code changes")
        self.assertEqual(common.extract_step_from_line("=== ⚙️ BUILDING ==="), "Building project (xcodebuild)")
        self.assertEqual(common.extract_step_from_line("=== 🧪 TESTING ==="), "Running test suite")
        self.assertEqual(common.extract_step_from_line("=== 👀 REVIEW ==="), "Reviewing changes")
        self.assertEqual(common.extract_step_from_line("=== 🚀 PULL_REQUEST ==="), "Creating pull request")
        self.assertEqual(common.extract_step_from_line("=== ⚙️ DELIVERY: FIREBASE DISTRIBUTION ==="), "Distributing build (Firebase)")
        self.assertEqual(common.extract_step_from_line("=== 🐞 DEBUG 1/8: DIAGNOSING ERRORS ==="), "Debugging (1/8): Diagnosing Errors")

    def test_extract_bracketed_steps(self) -> None:
        self.assertEqual(
            common.extract_step_from_line("[1/3] Planning feature (Stitch AI Mode: Off) using gemini-3.1-pro-preview..."),
            "[1/3] Planning feature"
        )
        self.assertEqual(
            common.extract_step_from_line("[2/3] Creating GitHub issue: Flush Test..."),
            "[2/3] Creating GitHub issue"
        )
        self.assertEqual(
            common.extract_step_from_line("[1/4] Preparing git branch: ai/issue-123..."),
            "[1/4] Preparing git branch"
        )
        self.assertEqual(
            common.extract_step_from_line("[2/4] Updating issue #123 status to 'executing'..."),
            "[2/4] Updating issue #123 status to 'executing'"
        )
        self.assertEqual(
            common.extract_step_from_line("[3/4] Reviewing and validating changes..."),
            "[3/4] Reviewing and validating changes"
        )
        self.assertEqual(
            common.extract_step_from_line("[4/4] Creating pull request and updating issue..."),
            "[4/4] Creating pull request and updating issue"
        )

    def test_extract_compiler_and_tool_steps(self) -> None:
        self.assertEqual(common.extract_step_from_line("CompileSwiftSources normal arm64 ..."), "Compiling Swift sources")
        self.assertEqual(common.extract_step_from_line("Test Suite 'All Tests' started at 2026-09-05"), "Running test suite")
        self.assertEqual(common.extract_step_from_line("      - Running tests: swift test (Attempt 1)"), "Running test suite")
        self.assertEqual(common.extract_step_from_line("      - Running build: xcodebuild (Attempt 1)"), "Building project")
        self.assertEqual(common.extract_step_from_line("        [progress] received 30 lines of response..."), "Generating code")
        self.assertEqual(common.extract_step_from_line("      - Committing 2 modified and 1 untracked files..."), "Committing changes")
        self.assertEqual(common.extract_step_from_line("      - Syncing code to worker mac2..."), "Syncing code to worker")


class StatusReportTests(unittest.TestCase):
    def test_format_distributed_status(self) -> None:
        from worker_run import format_distributed_status
        
        success_msg = "SUCCESS via Firebase App Distribution (ad-hoc) at 2026-09-05 13:16:28"
        colored_success = format_distributed_status(success_msg)
        self.assertIn("\033[1;92mSUCCESS\033[0m", colored_success)
        self.assertIn("Firebase App Distribution", colored_success)
        
        failed_msg = "FAILED (exit code 1)"
        colored_failed = format_distributed_status(failed_msg)
        self.assertIn("\033[1;91mFAILED\033[0m", colored_failed)
        
        skipped_msg = "Skipped (Firebase distribution disabled)"
        colored_skipped = format_distributed_status(skipped_msg)
        self.assertIn("\033[90mSkipped", colored_skipped)
        
        self.assertEqual(format_distributed_status(None), "")

    @patch("worker_run.sys.stdout.isatty", return_value=True)
    def test_print_status_report_prefers_builder_summary(self, _mock_isatty) -> None:
        from io import StringIO
        from worker_run import print_status_report
        
        job = {
            "job_id": "20260905-130559-bug-79",
            "status": "review-needed",
            "plan": {"summary": "The risk tab fails to display risks. This requires investigating full data flow."},
            "builder_summary": "Fixed model binding in ReportViewModel and added async state listener."
        }
        
        saved_stdout = sys.stdout
        try:
            sys.stdout = out = StringIO()
            print_status_report(
                job,
                build_ok=True,
                test_ok=True,
                pr_number=75,
                pr_url="https://github.com/leemosupreemo/Themis/pull/75",
                distributed_status="SUCCESS via Firebase App Distribution (debugging) at 2026-09-05 13:16:28"
            )
            output = out.getvalue()
        finally:
            sys.stdout = saved_stdout
            
        self.assertIn("Accomplishment:", output)
        self.assertIn("Fixed model binding in ReportViewModel", output)
        self.assertNotIn("This requires investigating full data flow", output)

    @patch("worker_run.sys.stdout.isatty", return_value=True)
    def test_print_status_report_falls_back_to_plan_summary_label(self, _mock_isatty) -> None:
        from io import StringIO
        from worker_run import print_status_report
        
        job = {
            "job_id": "20260905-130559-bug-79",
            "status": "review-needed",
            "plan": {"summary": "The risk tab fails to display risks."}
        }
        
        saved_stdout = sys.stdout
        try:
            sys.stdout = out = StringIO()
            print_status_report(job, build_ok=True, test_ok=True, pr_number=75)
            output = out.getvalue()
        finally:
            sys.stdout = saved_stdout
            
        self.assertIn("Plan Summary:", output)
        self.assertIn("The risk tab fails to display risks.", output)


class ClarificationHelperTests(unittest.TestCase):
    def test_record_clarification_appends_history_and_clears_active_question(self) -> None:
        job = {
            "job_id": "20260905-130559-bug-79",
            "status": "human-needed",
            "human_clarification_question": "Should risks default to high severity?",
            "last_error": "Builder clarification needed: Should risks default to high severity?"
        }
        common.record_clarification(job, "Should risks default to high severity?", "Yes, default to high severity.")
        
        self.assertIsNone(job["human_clarification_question"])
        self.assertIsNone(job["last_error"])
        self.assertEqual(len(job["clarification_history"]), 1)
        self.assertEqual(job["clarification_history"][0]["question"], "Should risks default to high severity?")
        self.assertEqual(job["clarification_history"][0]["answer"], "Yes, default to high severity.")
        self.assertTrue(job["clarification_history"][0]["timestamp"])

    def test_format_clarification_history_renders_markdown(self) -> None:
        history = [
            {"question": "What database framework?", "answer": "SwiftData with schema v2"},
            {"question": "Include dark mode?", "answer": "Yes, support automatic appearance"}
        ]
        markdown = common.format_clarification_history(history)
        self.assertIn("### User Clarifications & Technical Decisions", markdown)
        self.assertIn("1. **Question**: What database framework?", markdown)
        self.assertIn("**Answer / Decision**: SwiftData with schema v2", markdown)
        self.assertIn("2. **Question**: Include dark mode?", markdown)
        self.assertIn("**Answer / Decision**: Yes, support automatic appearance", markdown)

    def test_format_clarification_history_handles_empty(self) -> None:
        self.assertEqual(common.format_clarification_history([]), "")
        self.assertEqual(common.format_clarification_history(None), "")


class FollowupAndLogTests(unittest.TestCase):
    def test_find_latest_runtime_log_discovers_newest_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            output_dir = tmp_root / ".orchestrator" / "output"
            logs_dir = tmp_root / "logs"
            job_output = output_dir / "test-job-123"
            manual_dir = output_dir / "manual"

            job_output.mkdir(parents=True)
            logs_dir.mkdir(parents=True)
            manual_dir.mkdir(parents=True)

            log1 = logs_dir / "20260905-010000-build.log"
            log1.write_text("log 1", encoding="utf-8")

            # Older batch test results should be ignored
            log_batch = logs_dir / "batch_test_results.log"
            log_batch.write_text("batch log", encoding="utf-8")

            # Newest log in job_output
            log2 = job_output / "runtime.log"
            log2.write_text("log 2", encoding="utf-8")

            with patch.object(common, "ROOT", tmp_root), \
                 patch.object(common, "OUTPUT_DIR", output_dir), \
                 patch.object(common, "LOGS_DIR", logs_dir):
                result = common.find_latest_runtime_log("test-job-123")

            self.assertEqual(result, ".orchestrator/output/test-job-123/runtime.log")

    @patch("debug_job.run_debug_iteration")
    def test_trigger_followup_iteration_updates_job_and_runs_debug(self, mock_debug_iter) -> None:
        import worker_run
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            job_path = tmp_root / "job.json"
            job = {
                "job_id": "test-job-123",
                "status": "review-needed",
                "iteration": 1,
                "last_manual_log_paths": ["logs/old.log"]
            }
            common.write_json(job_path, job)

            with patch("worker_run.find_latest_runtime_log", return_value="logs/latest.log"):
                worker_run.trigger_followup_iteration(job_path, job, "Risk tab is not populated")

            saved_job = common.read_json(job_path)
            self.assertEqual(saved_job["status"], "debugging")
            self.assertEqual(saved_job["debug_phase"], "propose")
            self.assertEqual(saved_job["iteration"], 2)
            self.assertIn("logs/latest.log", saved_job["last_manual_log_paths"])
            self.assertEqual(len(saved_job["debug_history"]), 1)
            self.assertEqual(saved_job["debug_history"][0]["implementation_plan"], "Risk tab is not populated")
            mock_debug_iter.assert_called_once_with(job_path)

    @patch("debug_job.run_debug_iteration")
    def test_trigger_followup_iteration_for_feature_job(self, mock_debug_iter) -> None:
        import worker_run
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            job_path = tmp_root / "job.json"
            job = {
                "job_id": "test-job-456",
                "type": "feature-plan",
                "status": "review-needed",
                "iteration": 0,
            }
            common.write_json(job_path, job)

            with patch("worker_run.find_latest_runtime_log", return_value=None):
                worker_run.trigger_followup_iteration(job_path, job, "Save button missing loading indicator")

            saved_job = common.read_json(job_path)
            self.assertEqual(saved_job["status"], "debugging")
            self.assertEqual(saved_job["iteration"], 1)
            self.assertEqual(saved_job["debug_history"][0]["hypothesis"], "User reported bug or missing functionality in new feature.")
            self.assertEqual(saved_job["debug_history"][0]["implementation_plan"], "Save button missing loading indicator")
            mock_debug_iter.assert_called_once_with(job_path)


if __name__ == "__main__":
    unittest.main()


